#!/usr/bin/env bash
# vecinos_canales.sh
# Consulta los vecinos (peers de tus peers) de todos los nodos con los que tienes canal abierto.
# Muestra: alias, pubkey, dirección P2P, URI, capacidad, fees, disabled, uptime proxy,
#          número de canales del nodo en el graph, capacidad total, max_htlc_msat.
# Al finalizar exporta un CSV con la red completa para visualización 3D.
#
# USO:   sh vecinos_canales.sh
# OPC:   NETWORK=testnet4 LNCLI_BIN=lncli-debug sh vecinos_canales.sh

set -euo pipefail

NETWORK="${NETWORK:-testnet4}"
LNCLI_BIN="${LNCLI_BIN:-lncli-debug}"
CSV_OUT="${CSV_OUT:-lightning_network.csv}"
NOW=$(date +%s)

need_cmd() {
  command -v "$1" > /dev/null 2>&1 || {
    echo "Error: falta el comando '$1'" >&2
    exit 1
  }
}
need_cmd "$LNCLI_BIN"
need_cmd jq

# ─── Función: timestamp → fecha legible + "hace N días" ───────────────────────
fmt_date() {
  local ts="$1"
  if [[ "$ts" == "0" || -z "$ts" ]]; then
    echo "nunca"
    return
  fi
  local fecha diff days
  fecha=$(date -d "@${ts}" '+%Y-%m-%d %H:%M' 2>/dev/null || date -r "${ts}" '+%Y-%m-%d %H:%M')
  diff=$(( NOW - ts ))
  days=$(( diff / 86400 ))
  echo "${fecha} (hace ${days} días)"
}

# ─── Función: sats → formato legible ──────────────────────────────────────────
fmt_sats() {
  local n="$1"
  [[ -z "$n" || "$n" == "null" ]] && echo "?" && return
  printf "%'d sats" "$n"
}

echo "Obteniendo canales abiertos..."
channels_json=$($LNCLI_BIN -network="$NETWORK" listchannels)
my_peers=$(echo "$channels_json" | jq -r '.channels[].remote_pubkey' | sort -u)

if [[ -z "$my_peers" ]]; then
  echo "No tienes canales abiertos." >&2
  exit 1
fi

echo "Obteniendo graph de la red (puede tardar unos segundos)..."
graph_json=$($LNCLI_BIN -network="$NETWORK" describegraph)

echo
echo "================================================================"
echo " VECINOS DE TUS PEERS (nodos a 2 saltos de distancia)"
echo "================================================================"

# ─── SECCIÓN 1: Detalle por peer ──────────────────────────────────────────────
while IFS= read -r my_peer; do

  peer_alias=$(echo "$graph_json" | jq -r --arg pub "$my_peer" \
    '.nodes[] | select(.pub_key == $pub) | .alias // "sin_alias"')

  peer_last_update=$(echo "$graph_json" | jq -r --arg pub "$my_peer" \
    '.nodes[] | select(.pub_key == $pub) | .last_update // 0')

  peer_channels=$(echo "$graph_json" | jq --arg pub "$my_peer" \
    '[.edges[] | select(.node1_pub == $pub or .node2_pub == $pub)] | length')

  peer_total_cap=$(echo "$graph_json" | jq --arg pub "$my_peer" \
    '[.edges[] | select(.node1_pub == $pub or .node2_pub == $pub) | .capacity | tonumber] | add // 0')

  echo
  echo "┌─────────────────────────────────────────────────────────────────────"
  echo "│ PEER: ${peer_alias}"
  echo "│ PUBKEY: ${my_peer}"
  printf "│ Última actualización gossip: %s\n" "$(fmt_date "$peer_last_update")"
  printf "│ Canales en el graph: %s   |   Capacidad total: %s\n" \
    "$peer_channels" "$(fmt_sats "$peer_total_cap")"
  echo "├─────────────────────────────────────────────────────────────────────"

  neighbors=$(echo "$graph_json" | jq -r --arg pub "$my_peer" '
    .edges[] |
    select(.node1_pub == $pub or .node2_pub == $pub) |
    if .node1_pub == $pub then .node2_pub else .node1_pub end
  ' | sort -u)

  if [[ -z "$neighbors" ]]; then
    echo "│  (sin vecinos conocidos en el graph local)"
  else
    neighbor_count=0
    while IFS= read -r neighbor; do

      our_own=$(echo "$channels_json" | jq -r '.channels[].remote_pubkey' \
        | grep -c "^${neighbor}$" || true)
      if [[ "$our_own" -gt 0 ]]; then
        tag="[YA TIENES CANAL]"
      else
        tag=""
      fi

      # ── Info del nodo vecino ───────────────────────────────────────────
      nb_alias=$(echo "$graph_json" | jq -r --arg pub "$neighbor" \
        '.nodes[] | select(.pub_key == $pub) | .alias // "sin_alias"')

      nb_addr=$(echo "$graph_json" | jq -r --arg pub "$neighbor" \
        '.nodes[] | select(.pub_key == $pub) | .addresses[0].addr // "sin_dirección"')

      nb_last_update=$(echo "$graph_json" | jq -r --arg pub "$neighbor" \
        '.nodes[] | select(.pub_key == $pub) | .last_update // 0')

      nb_channels=$(echo "$graph_json" | jq --arg pub "$neighbor" \
        '[.edges[] | select(.node1_pub == $pub or .node2_pub == $pub)] | length')

      nb_total_cap=$(echo "$graph_json" | jq --arg pub "$neighbor" \
        '[.edges[] | select(.node1_pub == $pub or .node2_pub == $pub) | .capacity | tonumber] | add // 0')

      # ── Info del canal entre my_peer ↔ neighbor ────────────────────────
      # Usamos `first` para obtener UN solo objeto; el graph tiene un edge
      # por dirección y sin `first` jq emite múltiples líneas.
      edge_json=$(echo "$graph_json" | jq -c --arg pub "$my_peer" --arg nb "$neighbor" '
        first(.edges[] | select(
          (.node1_pub == $pub and .node2_pub == $nb) or
          (.node2_pub == $pub and .node1_pub == $nb)
        )) // {}
      ')

      capacity=$(echo "$edge_json" | jq -r '.capacity // "?"')
      max_htlc=$(echo "$edge_json" | jq -r '.node1_policy.max_htlc_msat // .node2_policy.max_htlc_msat // "?"')
      fee_base=$(echo "$edge_json" | jq -r '.node1_policy.fee_base_msat  // .node2_policy.fee_base_msat  // "?"')
      fee_rate=$(echo "$edge_json" | jq -r '.node1_policy.fee_rate_milli_msat // .node2_policy.fee_rate_milli_msat // "?"')
      cltv=$(echo     "$edge_json" | jq -r '.node1_policy.time_lock_delta // .node2_policy.time_lock_delta // "?"')
      disabled_raw=$(echo "$edge_json" | jq -r '
        if .node1_policy.disabled == true or .node2_policy.disabled == true
        then "⚠ DESHABILITADO"
        else "✓ activo"
        end')

      # ── Calcular max_htlc en sats (head -1 por si acaso) ───────────────
      max_htlc_clean=$(echo "$max_htlc" | head -n1)
      if [[ "$max_htlc_clean" =~ ^[0-9]+$ ]]; then
        max_htlc_sats=$(( max_htlc_clean / 1000 ))
        max_htlc_fmt="${max_htlc_sats} sats"
      else
        max_htlc_fmt="?"
      fi

      echo "│"
      echo "│  ▸ vecino: ${nb_alias:-sin_alias} $tag"
      echo "│    pubkey:        $neighbor"
      echo "│    p2p addr:      ${nb_addr:-sin_dirección}"
      echo "│    p2p uri:       ${neighbor}@${nb_addr:-?}"
      printf "│    Última gossip: %s\n" "$(fmt_date "$nb_last_update")"
      printf "│    Canales red:   %s   |   Cap. total nodo: %s\n" \
        "$nb_channels" "$(fmt_sats "$nb_total_cap")"
      echo "│    ── Canal peer↔vecino ──────────────────────────────"
      printf "│    Capacidad:     %s\n" "$(fmt_sats "$capacity")"
      printf "│    Max HTLC:      %s\n" "$max_htlc_fmt"
      printf "│    Fee base:      %s msat\n" "$fee_base"
      printf "│    Fee rate:      %s ppm\n" "$fee_rate"
      printf "│    CLTV delta:    %s bloques\n" "$cltv"
      printf "│    Estado:        %s\n" "$disabled_raw"

      neighbor_count=$((neighbor_count + 1))
    done <<< "$neighbors"
    echo "│"
    echo "│  Total vecinos: $neighbor_count"
  fi

  echo "└─────────────────────────────────────────────────────────────────────"

done <<< "$my_peers"

# ─── SECCIÓN 2: Resumen candidatos ────────────────────────────────────────────
echo
echo "================================================================"
echo " RESUMEN: Candidatos para nuevo canal (vecinos SIN canal tuyo)"
echo "================================================================"
echo

all_neighbors_file=$(mktemp)
my_peers_file=$(mktemp)

while IFS= read -r my_peer; do
  echo "$graph_json" | jq -r --arg pub "$my_peer" '
    .edges[] |
    select(.node1_pub == $pub or .node2_pub == $pub) |
    if .node1_pub == $pub then .node2_pub else .node1_pub end
  ' >> "$all_neighbors_file"
done <<< "$my_peers"

sort -u "$all_neighbors_file" -o "$all_neighbors_file"
echo "$channels_json" | jq -r '.channels[].remote_pubkey' | sort -u > "$my_peers_file"

candidates=$(comm -23 "$all_neighbors_file" "$my_peers_file")

if [[ -z "$candidates" ]]; then
  echo "  No se encontraron candidatos adicionales en el graph local."
else
  echo "  Nodos vecinos con los que podrías abrir un canal:"
  echo
  printf "  %-28s | %-6s | %-12s | %-10s | %-8s | %-8s | %s\n" \
    "ALIAS" "CANALES" "CAP.TOTAL" "CAPACIDAD" "FEE_BASE" "FEE_PPM" "CONNECT URI"
  printf "  %s\n" "$(printf '%.0s-' {1..150})"

  while IFS= read -r cand; do
    cand_alias=$(echo "$graph_json" | jq -r --arg pub "$cand" \
      '.nodes[] | select(.pub_key == $pub) | .alias // "sin_alias"')

    cand_addr=$(echo "$graph_json" | jq -r --arg pub "$cand" \
      '.nodes[] | select(.pub_key == $pub) | .addresses[0].addr // "sin_dirección"')

    cand_ch=$(echo "$graph_json" | jq --arg pub "$cand" \
      '[.edges[] | select(.node1_pub == $pub or .node2_pub == $pub)] | length')

    cand_total_cap=$(echo "$graph_json" | jq --arg pub "$cand" \
      '[.edges[] | select(.node1_pub == $pub or .node2_pub == $pub) | .capacity | tonumber] | add // 0')

    shared=$(echo "$graph_json" | jq --arg cand "$cand" \
      --argjson mypeers "$(echo "$my_peers" | jq -R . | jq -s .)" '
      [.edges[] | select(
        (.node1_pub == $cand or .node2_pub == $cand) and
        ((.node1_pub as $n | $mypeers | index($n) != null) or
         (.node2_pub as $n | $mypeers | index($n) != null))
      )] | length
    ')

    # Fees del mejor canal que conecta a este candidato con algún my_peer
    fee_base_c=$(echo "$graph_json" | jq -r --arg cand "$cand" \
      --argjson mypeers "$(echo "$my_peers" | jq -R . | jq -s .)" '
      [.edges[] | select(
        (.node1_pub == $cand or .node2_pub == $cand) and
        ((.node1_pub as $n | $mypeers | index($n) != null) or
         (.node2_pub as $n | $mypeers | index($n) != null))
      ) | .node1_policy.fee_base_msat // .node2_policy.fee_base_msat // 0 | tonumber]
      | if length > 0 then min else "?" end
    ')

    fee_rate_c=$(echo "$graph_json" | jq -r --arg cand "$cand" \
      --argjson mypeers "$(echo "$my_peers" | jq -R . | jq -s .)" '
      [.edges[] | select(
        (.node1_pub == $cand or .node2_pub == $cand) and
        ((.node1_pub as $n | $mypeers | index($n) != null) or
         (.node2_pub as $n | $mypeers | index($n) != null))
      ) | .node1_policy.fee_rate_milli_msat // .node2_policy.fee_rate_milli_msat // 0 | tonumber]
      | if length > 0 then min else "?" end
    ')

    printf "  %-28s | %-6s | %-12s | %-10s | %-8s | %-8s | %s@%s\n" \
      "${cand_alias:-sin_alias}" \
      "$cand_ch" \
      "$cand_total_cap" \
      "$shared" \
      "$fee_base_c" \
      "$fee_rate_c" \
      "$cand" \
      "${cand_addr:-?}"
  done <<< "$candidates"
fi

rm -f "$all_neighbors_file" "$my_peers_file"

# ─── SECCIÓN 3: Exportar CSV de la red completa ───────────────────────────────
echo
echo "================================================================"
echo " EXPORTANDO RED AL CSV: $CSV_OUT"
echo "================================================================"

# Cabecera
printf '%s\n' \
  "source_pubkey,source_alias,target_pubkey,target_alias,capacity_sats,fee_base_msat,fee_rate_ppm,max_htlc_sats,cltv_delta,disabled,source_last_update,target_last_update,source_channels,target_channels,source_total_cap,target_total_cap" \
  > "$CSV_OUT"

# Función auxiliar: devuelve campo de un nodo desde el graph (precomputado)
# Exportamos todos los edges del graph completo (no solo los de nuestros peers)
echo "$graph_json" | jq -r '
  .edges[] |
  [
    .node1_pub,
    .node2_pub,
    (.capacity // "0"),
    (.node1_policy.fee_base_msat // "0"),
    (.node1_policy.fee_rate_milli_msat // "0"),
    (if .node1_policy.max_htlc_msat then (.node1_policy.max_htlc_msat | tonumber / 1000 | floor | tostring) else "0" end),
    (.node1_policy.time_lock_delta // "0"),
    (if (.node1_policy.disabled == true or .node2_policy.disabled == true) then "1" else "0" end)
  ] | @csv
' > /tmp/edges_raw.csv

# Para cada edge, enriquecemos con alias, last_update, canales y cap total de cada nodo
# Construimos un lookup dict de nodos
node_lookup=$(echo "$graph_json" | jq -c '
  [.nodes[] | {
    key: .pub_key,
    value: {
      alias: (.alias // ""),
      last_update: (.last_update // 0),
      channels: 0,
      total_cap: 0
    }
  }] | from_entries
')

# Contamos canales y capacidad total por nodo
echo "$graph_json" | jq -r --argjson lookup "$node_lookup" '
  reduce .edges[] as $e (
    $lookup;
    . as $lk |
    ($e.node1_pub) as $n1 |
    ($e.node2_pub) as $n2 |
    ($e.capacity | tonumber) as $cap |
    (if $lk[$n1] then .[$n1].channels += 1 | .[$n1].total_cap += $cap else . end) |
    (if $lk[$n2] then .[$n2].channels += 1 | .[$n2].total_cap += $cap else . end)
  ) |
  to_entries[] |
  [.key, .value.alias, (.value.last_update | tostring), (.value.channels | tostring), (.value.total_cap | tostring)] |
  @csv
' > /tmp/node_lookup.csv

# Unir edges con nodos usando un script Python inline para el JOIN
python3 - <<'PYEOF'
import csv, sys

nodes = {}
with open('/tmp/node_lookup.csv', newline='', encoding='utf-8') as f:
    for row in csv.reader(f):
        if len(row) >= 5:
            pubkey, alias, last_update, channels, total_cap = row[0], row[1], row[2], row[3], row[4]
            nodes[pubkey] = {
                'alias': alias,
                'last_update': last_update,
                'channels': channels,
                'total_cap': total_cap
            }

out_file = open('lightning_network.csv', 'a', newline='', encoding='utf-8')
import os
# detect CSV_OUT from environment
csv_out = os.environ.get('CSV_OUT', 'lightning_network.csv')
# reopen with correct path
out_file.close()
out_file = open(csv_out, 'a', newline='', encoding='utf-8')
writer = csv.writer(out_file)

with open('/tmp/edges_raw.csv', newline='', encoding='utf-8') as f:
    for row in csv.reader(f):
        if len(row) < 8:
            continue
        n1, n2, cap, fee_base, fee_rate, max_htlc, cltv, disabled = row
        info1 = nodes.get(n1, {'alias':'', 'last_update':'0', 'channels':'0', 'total_cap':'0'})
        info2 = nodes.get(n2, {'alias':'', 'last_update':'0', 'channels':'0', 'total_cap':'0'})
        writer.writerow([
            n1, info1['alias'],
            n2, info2['alias'],
            cap, fee_base, fee_rate, max_htlc, cltv, disabled,
            info1['last_update'], info2['last_update'],
            info1['channels'], info2['channels'],
            info1['total_cap'], info2['total_cap']
        ])

out_file.close()
print(f"CSV exportado correctamente a: {csv_out}")
PYEOF

rm -f /tmp/edges_raw.csv /tmp/node_lookup.csv

echo "Listo. Ejecuta:  python3 visualizar_red_3d.py"