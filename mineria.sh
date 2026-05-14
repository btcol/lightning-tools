#!/bin/bash
# =============================================================================
# Script: mineria.sh
# Descripción: Script de minería continua para testnet4.
#              Genera una dirección de la wallet de LND y la usa
#              como destino para minar bloques utilizando bitcoin-cli.
# Uso: ./mineria.sh
# =============================================================================

echo "========================================"
echo "Iniciando Minero Testnet4 (LND Target)"
echo "========================================"

# ── Cargar variables de entorno ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

NETWORK="${NETWORK:-testnet4}"
LNCLI_BIN="${LNCLI_BIN:-lncli-debug}"
BITCOIN_CLI_BIN="${BITCOIN_CLI_BIN:-bitcoin-cli}"

# Genera una nueva direccion p2tr (Taproot) para LND. Si prefieres Segwit, puedes cambiar a p2wkh.
echo "[*] Generando direccion destino en LND..."
ADDRESS=$(${LNCLI_BIN} --network=${NETWORK} newaddress p2tr | jq -r '.address')

if [ -z "$ADDRESS" ] || [ "$ADDRESS" == "null" ]; then
    echo "[!] Error al generar la direccion con lncli. Asegurate de que LND este corriendo y desbloqueado."
    exit 1
fi

echo "[+] Direccion generada exitosamente: $ADDRESS"
echo "[*] Iniciando bucle de mineria..."
echo "========================================"

INTENTOS=0
BLOQUES_ENCONTRADOS=0

while true; do
    INTENTOS=$((INTENTOS+1))
    
    # Consultar el tiempo del último bloque de la red global y calcular el promedio
    BEST_HASH=$(${BITCOIN_CLI_BIN} -${NETWORK} getbestblockhash 2>/dev/null)
    if [ -n "$BEST_HASH" ] && [ "$BEST_HASH" != "$LAST_KNOWN_BEST_HASH" ]; then
        LAST_KNOWN_BEST_HASH="$BEST_HASH"
        
        BLOCK_INFO=$(${BITCOIN_CLI_BIN} -${NETWORK} getblockheader "$BEST_HASH" 2>/dev/null)
        LAST_TIME_EPOCH=$(echo "$BLOCK_INFO" | jq -r '.time' 2>/dev/null)
        HEIGHT=$(echo "$BLOCK_INFO" | jq -r '.height' 2>/dev/null)
        
        if [ -n "$LAST_TIME_EPOCH" ] && [ "$LAST_TIME_EPOCH" != "null" ]; then
            RED_ULTIMA_HORA=$(date -d @"$LAST_TIME_EPOCH" "+%H:%M:%S" 2>/dev/null)
            
            # Calcular el promedio de tiempo de los ultimos 5 bloques
            if [ -n "$HEIGHT" ] && [ "$HEIGHT" -ge 5 ]; then
                HASH_5_AGO=$(${BITCOIN_CLI_BIN} -${NETWORK} getblockhash $((HEIGHT - 5)) 2>/dev/null)
                if [ -n "$HASH_5_AGO" ]; then
                    TIME_5_AGO=$(${BITCOIN_CLI_BIN} -${NETWORK} getblockheader "$HASH_5_AGO" 2>/dev/null | jq -r '.time' 2>/dev/null)
                    if [ -n "$TIME_5_AGO" ] && [ "$TIME_5_AGO" != "null" ]; then
                        DIFF_SEC=$((LAST_TIME_EPOCH - TIME_5_AGO))
                        # Calcular promedio en segundos
                        AVG_SEC=$((DIFF_SEC / 5))
                        # Convertir a minutos con 1 decimal
                        AVG_MIN=$(awk "BEGIN {printf \"%.1f\", $AVG_SEC/60}")
                        PROMEDIO_MIN="Prom: $AVG_MIN min"
                    fi
                fi
            fi
        fi
    fi

    INFO_GLOBAL=""
    if [ -n "$RED_ULTIMA_HORA" ]; then
        INFO_GLOBAL="(Red: $RED_ULTIMA_HORA | $PROMEDIO_MIN)"
    fi
    
    # Imprime el estado actual sobre la misma linea
    printf "\r[*] Intento #%d minando... %s " "$INTENTOS" "$INFO_GLOBAL"
    
    OUTPUT=$(${BITCOIN_CLI_BIN} -${NETWORK} generatetoaddress 1 "$ADDRESS" 2>&1)
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        ARRAY_LEN=$(echo "$OUTPUT" | jq 'length' 2>/dev/null)
        
        if [ "$ARRAY_LEN" == "0" ] || [ -z "$ARRAY_LEN" ]; then
            # Salida vacia, no se pudo minar a tiempo, limpiamos la linea o simplemente reintentamos
            sleep 1
        else
            # ¡Bloque minado con éxito! Limpiamos la línea actual para imprimir el mensaje de éxito
            printf "\r\033[K"
            BLOQUES_ENCONTRADOS=$((BLOQUES_ENCONTRADOS+1))
            HASH=$(echo "$OUTPUT" | jq -r '.[0]' 2>/dev/null)
            ULTIMA_HORA=$(date "+%H:%M:%S")
            
            echo "[+] Bloque LOCAL minado con exito a las $ULTIMA_HORA! Total en sesion: $BLOQUES_ENCONTRADOS (Intento #$INTENTOS)"
            echo "    Hash: $HASH"
        fi
    else
        # Si falla por error de conexión o demonio
        if [[ "$OUTPUT" == *"couldn't connect"* ]]; then
            printf "\r\033[K"
            echo "[!] No se pudo conectar a bitcoind. Esperando 5 segundos..."
            sleep 5
        else
            sleep 1
        fi
    fi
done
