#!/usr/bin/env bash
# =============================================================================
# Script: plan_rebalance_testnet4.sh
# Descripción: Analiza local y remote balance de todos los canales activos
#              buscando pares desbalanceados (ej. target óptimo 50/50).
#              Emite en consola una lista de combinaciones origen/destino (From/To)
#              recomendadas para ejecutar rebalanceo, ignorando aquellos con HTLCs.
# Dependencias: jq, awk, sort
# Uso: ./plan_rebalance_testnet4.sh
# =============================================================================

set -euo pipefail

echo "lncli version:"
lncli-debug --version

NETWORK="testnet4"
TARGET_RATIO="${TARGET_RATIO:-50}"
MIN_SHIFT_SATS="${MIN_SHIFT_SATS:-1000}"
MAX_OPTIONS="${MAX_OPTIONS:-20}"
LNCLI_BIN="${LNCLI_BIN:-lncli-debug}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: falta el comando '$1'" >&2
    exit 1
  }
}

need_cmd "$LNCLI_BIN"
need_cmd jq
need_cmd awk
need_cmd sort

json="$($LNCLI_BIN -network="$NETWORK" listchannels)"

count=$(jq '.channels | length' <<<"$json")
if [[ "$count" -eq 0 ]]; then
  echo "No hay canales abiertos en $NETWORK"
  exit 0
fi

echo "=== Resumen de canales en $NETWORK ==="
printf '%-4s %-20s %-18s %-8s %-10s %-10s %-10s %-10s %-8s %-8s\n' \
  "#" "peer_alias" "scid/chan" "active" "capacity" "local" "remote" "shift50" "send" "recv"

PLAN_FILE=$(mktemp)
OPTIONS_FILE=$(mktemp)
trap 'rm -f "$PLAN_FILE" "$OPTIONS_FILE"' EXIT

jq -r '.channels[] | [
  .peer_alias,
  (.scid_str // .chan_id),
  (.active|tostring),
  (.capacity|tonumber),
  (.local_balance|tonumber),
  (.remote_balance|tonumber),
  (.private|tostring),
  (.initiator|tostring),
  .remote_pubkey,
  .chan_id,
  .scid_str,
  (.local_chan_reserve_sat|tonumber),
  (.remote_chan_reserve_sat|tonumber),
  (.commit_fee|tonumber),
  (.pending_htlcs|length)
] | @tsv' <<<"$json" | \
awk -F'\t' -v target="$TARGET_RATIO" -v plan_file="$PLAN_FILE" '
BEGIN { idx=0 }
{
  idx++
  peer=$1; scid_or_chan=$2; active=$3; cap=$4; local=$5; remote=$6; private=$7; initiator=$8;
  pubkey=$9; chan_id=$10; scid=$11; local_reserve=$12; remote_reserve=$13; commit_fee=$14; pending=$15;

  target_local = int((cap * target) / 100)
  delta = local - target_local
  if (delta > 0) { sendable = delta; receivable = 0 }
  else { sendable = 0; receivable = -delta }

  shift50 = (delta >= 0 ? delta : -delta)

  printf "%-4d %-20s %-18s %-8s %-10d %-10d %-10d %-10d %-8d %-8d\n", idx, peer, scid_or_chan, active, cap, local, remote, shift50, sendable, receivable

  printf "%d\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t%s\t%d\t%d\t%d\t%d\n", idx, peer, chan_id, scid, cap, local, remote, sendable, receivable, active, private, initiator, local_reserve, remote_reserve, commit_fee, pending >> plan_file
}
'

echo
echo "=== Opciones sugeridas de rebalanceo interno (NO ejecuta nada) ==="

awk -F'\t' -v minshift="$MIN_SHIFT_SATS" '
NR==FNR {
  idx[NR]=$1; peer[NR]=$2; chan_id[NR]=$3; scid[NR]=$4; cap[NR]=$5; local[NR]=$6; remote[NR]=$7;
  sendable[NR]=$8; receivable[NR]=$9; active[NR]=$10; private[NR]=$11; initiator[NR]=$12;
  local_reserve[NR]=$13; remote_reserve[NR]=$14; commit_fee[NR]=$15; pending[NR]=$16;
  n=NR; next
}
END {
  for (i=1; i<=n; i++) {
    if (active[i] != "true") continue
    if (pending[i] != 0) continue
    if (sendable[i] < minshift) continue
    for (j=1; j<=n; j++) {
      if (i == j) continue
      if (active[j] != "true") continue
      if (pending[j] != 0) continue
      if (receivable[j] < minshift) continue
      amount = (sendable[i] < receivable[j] ? sendable[i] : receivable[j])
      if (amount < minshift) continue
      score = amount
      printf "%d\t%s\t%s\t%s\t%s\t%d\t%d\t%d\n", score, scid[i], scid[j], peer[i], peer[j], amount, local[i], local[j]
    }
  }
}
' "$PLAN_FILE" "$PLAN_FILE" | sort -t$'\t' -k1,1nr | head -n "$MAX_OPTIONS" > "$OPTIONS_FILE"

if [[ ! -s "$OPTIONS_FILE" ]]; then
  echo "No encontré pares claros from->to con los criterios actuales."
  echo "Prueba bajando MIN_SHIFT_SATS o revisa si tus canales ya están equilibrados."
  exit 0
fi

printf '%-4s %-18s %-18s %-20s %-20s %-12s\n' "#" "from" "to" "peer_from" "peer_to" "monto_sats"
awk -F'\t' '{printf "%-4d %-18s %-18s %-20s %-20s %-12d\n", NR, $2, $3, $4, $5, $6}' "$OPTIONS_FILE"

echo
echo "=== Plantillas de comando para analizar después ==="
awk -F'\t' '{
  printf "# Opcion %d\n", NR
  printf "# from=%s (%s) -> to=%s (%s) monto=%s sats\n", $2, $4, $3, $5, $6
  printf "# Ejemplo con rebalance-lnd:\n"
  printf "rebalance.py -f %s -t %s -a %s\n\n", $2, $3, $6
}' "$OPTIONS_FILE"

echo "=== Detalle adicional recomendado por canal ==="
jq -r '.channels[] | [
  (.peer_alias // ""),
  (.scid_str // .chan_id),
  .remote_pubkey,
  .capacity,
  .local_balance,
  .remote_balance,
  .local_chan_reserve_sat,
  .remote_chan_reserve_sat,
  .commit_fee,
  .fee_per_kw,
  .csv_delay,
  .private,
  .active,
  (.pending_htlcs | length),
  .num_updates,
  .uptime,
  .lifetime
] | @tsv' <<<"$json" | \
awk -F'\t' '{
  printf "canal=%s | peer=%s | pubkey=%s | cap=%s | local=%s | remote=%s | local_reserve=%s | remote_reserve=%s | commit_fee=%s | fee_per_kw=%s | csv_delay=%s | private=%s | active=%s | pending_htlcs=%s | num_updates=%s | uptime=%s | lifetime=%s\n",
    $2, $1, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
}'
