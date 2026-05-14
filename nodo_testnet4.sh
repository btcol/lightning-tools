#!/bin/bash
# =============================================================================
# Script: nodo_testnet4.sh
# Descripción: Script de conveniencia para la inicialización de los demonios requeridos
#              (Bitcoin Core y LND) en la red Testnet4, y la creación de billetera.
# Uso: ./nodo_testnet4.sh
# =============================================================================

# ── Cargar variables de entorno ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

NETWORK="${NETWORK:-testnet4}"
LNCLI_BIN="${LNCLI_BIN:-lncli-debug}"
BITCOIN_CLI_BIN="${BITCOIN_CLI_BIN:-bitcoin-cli}"

# 1. Iniciar Bitcoin Core en la red especificada (sincronización On-Chain)
bitcoind -${NETWORK}

# 2. Crear wallet On-Chain (sólo necesario la primera vez, falla sin problema si ya existe)
${BITCOIN_CLI_BIN} -${NETWORK} createwallet "bitcoin-onchain"

# Dirección guardada como referencia rápida
# Address: tb1qrmgv8cvx2n36su79vmmwj6u0mjltvxsejvc8uy

# 3. Iniciar el demonio LND especificando que funciona con la backend correspondiente
lnd --bitcoin.${NETWORK}

# 4. Consultar la informacion global de nuestro nodo en la red lightning
${LNCLI_BIN} --network=${NETWORK} getinfo