#!/usr/bin/env bash
# =============================================================================
# Script: listpeers.sh
# Descripción: Lista todas las conexiones P2P (Peers) actuales del nodo e indica,
#              mediante una comparación con 'listchannels', si tenemos un canal 
#              Lightning abierto o si solo es una conexión a nivel de red P2P (gossip).
# Uso: ./listpeers.sh
# Dependencias: jq, awk
# =============================================================================

echo "=== Todos los peers con su estado ==="

# 1. Obtener un arreglo JSON con las pubkeys remotas de todos nuestros canales abiertos
chan_pubkeys=$(lncli-debug -n testnet4 listchannels | jq -r '[.channels[].remote_pubkey]')

# 2. Consultar todos los peers conectados actualmemte, e iterar sobre ellos.
#    Por cada peer, comprobamos si su pub_key está en el arreglo 'chan_pubkeys'.
#    Si existe, marcamos como "CON_CANAL"; de lo contrario, "SIN_CANAL".
lncli-debug -n testnet4 listpeers | jq -r --argjson chans "$chan_pubkeys" \
  '.peers[] | [
    if (.pub_key as $p | $chans | index($p) != null) then "CON_CANAL" else "SIN_CANAL" end,
    .pub_key,
    .address
  ] | @tsv' | awk -F'\t' '{printf "%-12s | %s | %s\n", $1, $2, $3}'