#!/bin/bash
# Este script inicia el servidor Bitcoin/LND/LNbits en testnet4

############################3

# Inicializa el nodo de bitcoin
echo "Inicializando bitcoind ..."
screen -dmS bitcoind bash -c 'bitcoind -testnet4; exec bash'

echo "Esperando a que bitcoind se sincronice al 100%..."
while ! bitcoin-cli -testnet4 getblockchaininfo 2>/dev/null | grep -q '"initialblockdownload": false'; do
    sleep 5
done
sleep 2

echo "Inicializando lnd ..."
screen -dmS lnd bash -c 'lnd --bitcoin.testnet4; exec bash'

# Esperar a que lnd se inicie
echo "Esperando a que LND abra el puerto RPC..."
while ~/go/bin/lncli --network=testnet4 state 2>&1 | grep -q "connection refused"; do
    sleep 3
done
sleep 2 # Margen de seguridad extra

# Desbloquear la wallet existente
echo "Desbloqueando la wallet existente ..."
echo "BNtycvoplñ1" | ~/go/bin/lncli --network=testnet4 unlock --stdin


# Inicializa el servicio LNbits
echo "Inicializando LNbits ..."
screen -dmS lnbits bash -c 'cd lnbits && cv run lnbits; exec bash'

# Espacio reservado para la parte de caddy
# Aca debe ir la activacion del proxy inverso

# Servidor en linea
echo "Servicio Bitcoin/LND/LNbits en linea !!!"
