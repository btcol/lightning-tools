#!/usr/bin/env bash
# Aborta si cualquier comando falla (-e), si se usa variable sin definir (-u),
# o si falla algún pipe (-o pipefail). Esto evita errores silenciosos.
set -euo pipefail

# =============================================================================
# REBALANCEO CIRCULAR DE CANALES LIGHTNING — MODO PLAN (SIN EJECUCIÓN)
#
# Lógica general:
#   1. Se crea una invoice en tu PROPIO nodo (eres el destinatario).
#   2. Se envía el pago saliendo por el canal OUTGOING (mucho local_balance).
#   3. El pago viaja por la red Lightning a través de peers intermedios.
#   4. El pago regresa a tu nodo entrando por el canal INCOMING (poco local_balance).
#   5. Resultado neto: tu nodo paga y recibe la misma invoice → balance de sats sin cambio.
#      Solo se pagan fees de routing. El efecto es mover liquidez entre canales.
#
# USO:
#   OUTGOING_SCID=<scid_from> INCOMING_SCID=<scid_to> [AMT_SATS=10000] sh plan_rebalance_invoice_testnet4.sh
#
# Ejemplo:
#   OUTGOING_SCID=129925x3x0 INCOMING_SCID=130000x1x0 AMT_SATS=5000 sh plan_rebalance_invoice_testnet4.sh
# =============================================================================

# --- Parámetros configurables vía variables de entorno ---
# NETWORK: red LND a usar (mainnet, testnet4, regtest, etc.)
NETWORK="${NETWORK:-testnet4}"
# LNCLI_BIN: binario de lncli a usar (puede ser lncli, lncli-debug, etc.)
LNCLI_BIN="${LNCLI_BIN:-lncli-debug}"
# AMT_SATS: monto en satoshis a mover entre canales
AMT_SATS="${AMT_SATS:-10000}"
# OUTGOING_SCID: SCID del canal por donde SALE el pago (el que tiene mucho local_balance)
OUTGOING_SCID="${OUTGOING_SCID:-}"
# INCOMING_SCID: SCID del canal por donde ENTRA el retorno (el que queremos recargar)
INCOMING_SCID="${INCOMING_SCID:-}"
# FINAL_CLTV_DELTA: delta de bloques CLTV para el último hop de la ruta
FINAL_CLTV_DELTA="${FINAL_CLTV_DELTA:-40}"
# MAX_FEE_SATS: límite ABSOLUTO de fee en satoshis que estás dispuesto a pagar por el rebalanceo
# Si la ruta cuesta más, payinvoice rechazará el pago automáticamente antes de ejecutarlo.
MAX_FEE_SATS="${MAX_FEE_SATS:-100}"
# MAX_FEE_PPM: límite RELATIVO en partes por millón (ppm) del monto a mover.
# Sirve para razonar en términos de porcentaje: 1000 ppm = 0.1%, 5000 ppm = 0.5%
# Se usa SOLO para el análisis de rentabilidad mostrado en el plan (no se pasa a lncli).
# El límite efectivo para lncli es MAX_FEE_SATS.
MAX_FEE_PPM="${MAX_FEE_PPM:-1000}"

# --- Función auxiliar: verifica que un comando esté disponible en PATH ---
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: falta el comando '$1'" >&2
    exit 1
  }
}

# Verificar dependencias mínimas antes de continuar
need_cmd "$LNCLI_BIN"  # cliente LND
need_cmd jq            # procesador JSON
need_cmd python3       # usado para posibles cálculos auxiliares

# =============================================================================
# SECCIÓN 1: Listar canales y validar que hay suficientes para rebalancear
# =============================================================================

# Obtener todos los canales del nodo en formato JSON (una sola llamada, reutilizable)
json="$($LNCLI_BIN -network="$NETWORK" listchannels)"

# Contar cuántos canales tiene el nodo
count=$(jq '.channels | length' <<< "$json")

# El rebalanceo circular requiere al menos 2 canales: uno de salida y uno de entrada
if [[ "$count" -lt 2 ]]; then
  echo "Necesitas al menos 2 canales para planear un rebalanceo circular."
  exit 1
fi

# Si no se proporcionaron los SCIDs, mostrar la lista de canales disponibles y salir
if [[ -z "$OUTGOING_SCID" || -z "$INCOMING_SCID" ]]; then
  echo "Uso: OUTGOING_SCID=<scid_from> INCOMING_SCID=<scid_to> [AMT_SATS=10000] $0"
  echo
  echo "Canales disponibles:"
  # Mostrar cada canal con sus datos clave: SCID, alias del peer, pubkey, capacidad,
  # balance local, balance remoto y si está activo
  jq -r '.channels[] | [(.scid_str // .chan_id), (.peer_alias // ""), .remote_pubkey, .capacity, .local_balance, .remote_balance, (.active|tostring)] | @tsv' <<< "$json" | \
  awk -F'\t' '{printf "- scid=%s | peer=%s | pubkey=%s | cap=%s | local=%s | remote=%s | active=%s\n", $1, $2, $3, $4, $5, $6, $7}'
  exit 0
fi

# =============================================================================
# SECCIÓN 2: Extraer datos del canal OUTGOING (el que tiene mucho local_balance)
# =============================================================================
# scid_str es el formato legible (ej: 129925x3x0); chan_id es el ID numérico interno.
# Usamos (.scid_str // .chan_id) como fallback en caso de que scid_str no exista.

from_peer=$(jq -r --arg scid "$OUTGOING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .peer_alias' <<< "$json")
from_pub=$(jq -r --arg scid "$OUTGOING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .remote_pubkey' <<< "$json")
from_local=$(jq -r --arg scid "$OUTGOING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .local_balance' <<< "$json")
from_active=$(jq -r --arg scid "$OUTGOING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .active' <<< "$json")

# NOTA: En este build de LND para testnet4, el campo .chan_id del JSON NO es el uint64 de la
# especificación BOLT — contiene el txid del funding tx en byte-order interno (little-endian).
# Por eso extraemos el chan_id raw solo como referencia, y calculamos el uint64 correcto desde
# scid_str usando la codificación BOLT: chan_id_uint64 = (block << 40) | (tx_index << 16) | vout
from_chan_id_raw=$(jq -r --arg scid "$OUTGOING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .chan_id' <<< "$json")

# Calcular el chan_id uint64 desde scid_str (ej: "129951x4x0" → número uint64)
# Este es el valor que acepta payinvoice --outgoing_chan_id
from_chan_id=$(python3 -c "
parts = '$OUTGOING_SCID'.split('x')
block, tx, vout = int(parts[0]), int(parts[1]), int(parts[2])
print((block << 40) | (tx << 16) | vout)
")

# channel_point: txid:output_index del canal (útil para referencia, ej: closechannel)
from_channel_point=$(jq -r --arg scid "$OUTGOING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .channel_point' <<< "$json")

# =============================================================================
# SECCIÓN 3: Extraer datos del canal INCOMING (el que queremos recargar)
# =============================================================================

to_peer=$(jq -r --arg scid "$INCOMING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .peer_alias' <<< "$json")
# to_pub: pubkey del peer del canal INCOMING → se usa como --last_hop en payinvoice
# para forzar que el último salto de la ruta entre por ese peer
to_pub=$(jq -r --arg scid "$INCOMING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .remote_pubkey' <<< "$json")
to_local=$(jq -r --arg scid "$INCOMING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .local_balance' <<< "$json")
to_active=$(jq -r --arg scid "$INCOMING_SCID" '.channels[] | select((.scid_str // .chan_id)==$scid) | .active' <<< "$json")

# Debug: confirmar los valores extraídos antes de las validaciones
echo "DEBUG: from_chan_id_raw (txid hex, NO usar en payinvoice) = $from_chan_id_raw"
echo "DEBUG: from_chan_id_uint64 (correcto para payinvoice)      = $from_chan_id"
echo "DEBUG: from_channel_point = $from_channel_point"
echo "DEBUG: to_pub             = $to_pub"

# =============================================================================
# SECCIÓN 4: Validaciones previas al rebalanceo
# =============================================================================

# Verificar que se pudo calcular el chan_id uint64 para el canal OUTGOING
if [[ -z "$from_chan_id" || "$from_chan_id" == "null" ]]; then
  echo "ERROR: No se pudo calcular el chan_id uint64 para OUTGOING_SCID=$OUTGOING_SCID"
  echo "       Verifica que el formato sea correcto (ej: 129951x4x0)"
  exit 1
fi

# Verificar que ambos SCIDs corresponden a canales reales del nodo
if [[ -z "$from_pub" || "$from_pub" == "null" ]]; then
  echo "No encontré el canal OUTGOING_SCID=$OUTGOING_SCID"
  exit 1
fi
if [[ -z "$to_pub" || "$to_pub" == "null" ]]; then
  echo "No encontré el canal INCOMING_SCID=$INCOMING_SCID"
  exit 1
fi

# Ambos canales deben estar activos (conectados con el peer) para poder rutear
if [[ "$from_active" != "true" || "$to_active" != "true" ]]; then
  echo "Ambos canales deben estar activos."
  exit 1
fi

# No tiene sentido rebalancear un canal consigo mismo
if [[ "$OUTGOING_SCID" == "$INCOMING_SCID" ]]; then
  echo "from y to no pueden ser el mismo canal."
  exit 1
fi

# El monto debe ser positivo
if (( AMT_SATS <= 0 )); then
  echo "AMT_SATS debe ser > 0"
  exit 1
fi

# El canal de salida debe tener suficiente local_balance para enviar el monto
if (( from_local <= AMT_SATS )); then
  echo "El canal from no tiene suficiente local_balance para planear ese monto."
  exit 1
fi

# =============================================================================
# SECCIÓN 5: Crear la invoice en el propio nodo
# =============================================================================
# En un rebalanceo circular, TÚ eres tanto el pagador como el destinatario.
# addinvoice crea una invoice que SOLO tu nodo puede cobrar.
# El payment_request es el código BOLT-11 que se pasa a payinvoice o sendtoroute.
# El payment_hash sirve para identificar el pago; payment_addr evita ataques de probe.

invoice_json="$($LNCLI_BIN -network="$NETWORK" addinvoice --amt="$AMT_SATS" --memo="rebalance-plan-$OUTGOING_SCID-to-$INCOMING_SCID" --private)"
payment_request=$(jq -r '.payment_request' <<< "$invoice_json")
payment_hash=$(jq -r '.r_hash // .r_hash_str // .payment_hash' <<< "$invoice_json")
payment_addr=$(jq -r '.payment_addr' <<< "$invoice_json")

# =============================================================================
# SECCIÓN 6: Mostrar el plan (sin ejecutar ningún pago)
# =============================================================================

cat <<EOF
=== Plan manual de rebalanceo circular (NO ejecuta pago) ===
network        : $NETWORK
lncli bin      : $LNCLI_BIN
monto          : $AMT_SATS sats
from canal     : $OUTGOING_SCID  (chan_id: $from_chan_id)
from peer      : $from_peer
from pubkey    : $from_pub
to canal       : $INCOMING_SCID
to peer        : $to_peer
to pubkey      : $to_pub
final cltv     : $FINAL_CLTV_DELTA
EOF

echo
echo "=== Invoice creada en tu propio nodo ==="
echo "payment_request: $payment_request"
echo "payment_hash   : $payment_hash"
echo "payment_addr   : $payment_addr"

# =============================================================================
# SECCIÓN 7: Opción simple — payinvoice con salida y último hop forzados
# =============================================================================
# --allow_self_payment: permite que tu nodo se pague a sí mismo (circular)
# --outgoing_chan_id:   fuerza la SALIDA del pago por el canal OUTGOING (chan_id numérico)
# --last_hop:           fuerza que el ÚLTIMO hop sea el peer del canal INCOMING
#                       para asegurar que el pago entre por ese canal específico
echo
echo "=== Opcion simple a probar manualmente con payinvoice ==="
# --fee_limit: rechaza rutas que superen MAX_FEE_SATS antes de ejecutar el pago
echo "$LNCLI_BIN -n $NETWORK payinvoice --allow_self_payment --outgoing_chan_id=\"$from_chan_id\" --last_hop=\"$to_pub\" --fee_limit=\"$MAX_FEE_SATS\" \"$payment_request\""
echo
echo "Esa orden intenta forzar la salida por el canal 'from' y el ultimo hop por el peer del canal 'to'."
echo "Si existe una ruta valida en la red, el pago circular deberia aumentar el balance remoto del canal 'to'."

# =============================================================================
# SECCIÓN 8: Opción avanzada — buildroute + sendtoroute con control total de la ruta
# =============================================================================
# Esta opción te permite:
#   1. Elegir manualmente los pubkeys intermedios (hops) de la ruta.
#   2. Inyectar el payment_addr en el último hop (requerido para pagos MPP/AMP).
#   3. Revisar la ruta completa antes de enviar.
#   4. Ejecutar sendtoroute solo si te convence.
echo
echo "=== Opcion avanzada con buildroute/sendtoroute (plan, no ejecucion automatica) ==="
cat <<EOF
1) Construye una ruta tentativa con hop pubkeys intermedias que tu elijas.
2) Inserta el payment_addr en el ultimo hop como mpp_record.
3) Revisa la ruta.
4) Ejecuta sendtoroute manualmente solo si te convence.
EOF

echo
echo "Plantilla buildroute (reemplaza <pubkey1,pubkey2,...> con los hops reales):"
echo "$LNCLI_BIN -network=$NETWORK buildroute --amt=$AMT_SATS --final_cltv_delta=$FINAL_CLTV_DELTA --hops=<pubkey1,pubkey2,...,$to_pub>"

echo
echo "Plantilla para inyectar payment_addr y total_amt_msat en el ultimo hop (requerido para MPP):"
cat <<EOF
$LNCLI_BIN -network=$NETWORK buildroute --amt=$AMT_SATS --final_cltv_delta=$FINAL_CLTV_DELTA --hops=<pubkey1,pubkey2,...,$to_pub> \\
| jq '.route.hops[-1].mpp_record = {payment_addr: "$payment_addr", total_amt_msat: "${AMT_SATS}000"}'
EOF

echo
echo "Plantilla sendtoroute (ejecuta el pago con la ruta construida arriba):"
cat <<EOF
$LNCLI_BIN -network=$NETWORK buildroute --amt=$AMT_SATS --final_cltv_delta=$FINAL_CLTV_DELTA --hops=<pubkey1,pubkey2,...,$to_pub> \\
| jq '.route.hops[-1].mpp_record = {payment_addr: "$payment_addr", total_amt_msat: "${AMT_SATS}000"}' \\
| $LNCLI_BIN -network=$NETWORK sendtoroute --payment_hash=$payment_hash -
EOF

# =============================================================================
# SECCIÓN 9: Análisis de rentabilidad del fee
# =============================================================================
# Explicación de las métricas:
#   fee_ppm_actual  = cuánto pagas por mover estos sats (en partes por millón)
#   fee_max_sats    = límite absoluto configurado (MAX_FEE_SATS)
#   monto_min_util  = mínimo de sats a mover para que el fee no supere MAX_FEE_PPM
#   fee_esperado    = fee estimado para AMT_SATS dado el MAX_FEE_PPM configurado
#
# NOTA: el fee real de la ruta lo negocia LND al momento de pagar.
# Estas cifras son estimaciones para ayudarte a elegir un monto razonable.
echo
echo "=== Analisis de rentabilidad del rebalanceo ==="
python3 - <<PYEOF
amt       = $AMT_SATS
max_fee   = $MAX_FEE_SATS
max_ppm   = $MAX_FEE_PPM

# Fee rate actual si se pagara el máximo absoluto
fee_ppm_if_max = (max_fee / amt) * 1_000_000

# Monto mínimo para que el fee máximo absoluto represente como mucho max_ppm
monto_min = (max_fee / max_ppm) * 1_000_000

# Fee esperado (en sats) para el monto elegido, dado el rate máximo en ppm
fee_esperado = (max_ppm / 1_000_000) * amt

print(f"monto a rebalancear : {amt:>10,} sats")
print(f"fee limit absoluto  : {max_fee:>10,} sats  (--fee_limit que se pasa a lncli)")
print(f"fee limit relativo  : {max_ppm:>10,} ppm   = {max_ppm/10000:.2f}%  (referencia, configurable con MAX_FEE_PPM=)")
print()
print(f"fee estimado para {amt:,} sats @ {max_ppm} ppm : {fee_esperado:.1f} sats")
print(f"fee rate si pagas el max absoluto ({max_fee} sats): {fee_ppm_if_max:,.0f} ppm = {fee_ppm_if_max/10000:.3f}%")
print()
print(f"Monto minimo para que {max_fee} sats de fee sea <= {max_ppm} ppm : {monto_min:,.0f} sats (~{monto_min/100_000_000:.6f} BTC)")
print()
if fee_esperado > max_fee:
    print(f"AVISO: con {max_ppm} ppm el fee esperado ({fee_esperado:.1f} sats) supera tu fee_limit ({max_fee} sats).")
    print(f"       Sube MAX_FEE_SATS o reduce MAX_FEE_PPM, o mueve al menos {monto_min:,.0f} sats.")
else:
    print(f"OK: el fee esperado ({fee_esperado:.1f} sats) esta dentro del fee_limit ({max_fee} sats).")
PYEOF

# =============================================================================
# SECCIÓN 10: Recomendaciones finales
# =============================================================================
echo
echo "=== Siguiente validacion recomendada ==="
echo "- Verifica si tu LND permite self-payments/circular routes."
echo "- Ajusta AMT_SATS y MAX_FEE_SATS segun el analisis de rentabilidad de arriba."
echo "- Si payinvoice falla con TEMPORARY_CHANNEL_FAILURE, el problema es falta de liquidez"
echo "  en los nodos intermedios, NO el fee limit. Prueba buildroute con otros hops."
echo "- Si payinvoice falla con FEE_INSUFFICIENT, sube MAX_FEE_SATS."
echo "- Cuando termines las pruebas, limpia invoices no usadas si quieres mantener orden."