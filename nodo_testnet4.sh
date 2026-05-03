#!/bin/bash
# =============================================================================
# Script: nodo_testnet4.sh
# Descripción: Script de conveniencia para la inicialización de los demonios requeridos
#              (Bitcoin Core y LND) en la red Testnet4, y la creación de billetera.
# Uso: ./nodo_testnet4.sh
# =============================================================================

# 1. Iniciar Bitcoin Core en la testnet4 (sincronización On-Chain)
bitcoind -testnet4

# 2. Crear wallet On-Chain (sólo necesario la primera vez, falla sin problema si ya existe)
bitcoin-cli -testnet4 createwallet "bitcoin-onchain"

# Dirección guardada como referencia rápida
# Address: tb1qrmgv8cvx2n36su79vmmwj6u0mjltvxsejvc8uy

# 3. Iniciar el demonio LND especificando que funciona con la backend de testnet4
lnd --bitcoin.testnet4

# 4. Consultar la informacion global de nuestro nodo en la red lightning
lncli --network=testnet4 getinfo