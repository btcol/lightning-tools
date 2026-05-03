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

bitcoin-cli -testnet4 loadwallet "bitcoin-onchain"

bitcoin-cli -testnet4 -rpcwallet="bitcoin-onchain" listunspent

# Consolidacion de todos los utxos
inputs=$(bitcoin-cli -testnet4 -rpcwallet="bitcoin-onchain" listunspent | jq -c 'map({txid: .txid, vout: .vout})')

echo "Inputs: $inputs"

# Genera una direccion de cambio para bitcoin-onchain
changeaddress=$(bitcoin-cli -testnet4 -rpcwallet="bitcoin-onchain" -named getnewaddress label="Cambio")
echo "Direccion de cambio: $changeaddress"

# Genera una direccion para la wallet lightning-onchain
addres_lightning=$(lncli-debug --network=testnet4 newaddress p2wkh | jq -r '.address')
echo "Direccion lightning: $addres_lightning"

# Crear la transaccion activando el replace-by-fee (RBF)
rawtxhex=$(bitcoin-cli -testnet4 -named createrawtransaction inputs="$inputs" outputs='''{"'$addres_lightning'": 0.0035, "'$changeaddress'": 0.00038176}''')

echo "Transaccion raw: $rawtxhex"

# Firmamos la transaccion
signedtxhex=$(bitcoin-cli -testnet4 -rpcwallet="bitcoin-onchain" -named signrawtransactionwithwallet hexstring=$rawtxhex | jq -r '.hex')
echo "Transaccion firmada: $signedtxhex"

# Transmitimos la transaccion
transactionid=$(bitcoin-cli -testnet4 -named sendrawtransaction hexstring=$signedtxhex)
echo "Transaccion transmitida: $transactionid"

