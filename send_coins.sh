#!/bin/bash
# =============================================================================
# Script: send_coins.sh
# Descripción: Script interactivo para construir, firmar y enviar manualmente 
#              una transacción On-Chain ("Raw Transaction"). Envía un monto fijo
#              desde la wallet "bitcoin-onchain" a una dirección generada por 
#              el nodo Lightning ("lightning-onchain").
# Uso: ./send_coins.sh
# Dependencias: bitcoin-cli, lncli-debug, jq
# =============================================================================

# ── Cargar variables de entorno ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

NETWORK="${NETWORK:-testnet4}"
LNCLI_BIN="${LNCLI_BIN:-lncli-debug}"
BITCOIN_CLI_BIN="${BITCOIN_CLI_BIN:-bitcoin-cli}"

${BITCOIN_CLI_BIN} -${NETWORK} loadwallet "bitcoin-onchain"

${BITCOIN_CLI_BIN} -${NETWORK} -rpcwallet="bitcoin-onchain" listunspent

# Consolidacion de todos los utxos
inputs=$(${BITCOIN_CLI_BIN} -${NETWORK} -rpcwallet="bitcoin-onchain" listunspent | jq -c 'map({txid: .txid, vout: .vout})')

echo "Inputs: $inputs"

# Genera una direccion de cambio para bitcoin-onchain
changeaddress=$(${BITCOIN_CLI_BIN} -${NETWORK} -rpcwallet="bitcoin-onchain" -named getnewaddress label="Cambio")
echo "Direccion de cambio: $changeaddress"

# Genera una direccion para la wallet lightning-onchain
addres_lightning=$(${LNCLI_BIN} --network=${NETWORK} newaddress p2wkh | jq -r '.address')
echo "Direccion lightning: $addres_lightning"

# Crear la transaccion activando el replace-by-fee (RBF)
rawtxhex=$(${BITCOIN_CLI_BIN} -${NETWORK} -named createrawtransaction inputs="$inputs" outputs='''{"'$addres_lightning'": 0.0035, "'$changeaddress'": 0.00038176}''')

echo "Transaccion raw: $rawtxhex"

# Firmamos la transaccion
signedtxhex=$(${BITCOIN_CLI_BIN} -${NETWORK} -rpcwallet="bitcoin-onchain" -named signrawtransactionwithwallet hexstring=$rawtxhex | jq -r '.hex')
echo "Transaccion firmada: $signedtxhex"

# Transmitimos la transaccion
transactionid=$(${BITCOIN_CLI_BIN} -${NETWORK} -named sendrawtransaction hexstring=$signedtxhex)
echo "Transaccion transmitida: $transactionid"

