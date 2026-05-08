# ⚡ Guía de Métricas — Lightning Cockpit HUD

Referencia completa de todos los indicadores del panel de instrumentos.  
Los datos provienen de `data/node_history.db`, recolectados por `scripts/collect_stats.py`.

---

## 🔝 Barra Superior (Top Bar)

### Nodo (Alias)
El nombre que tu nodo anuncia al grafo Lightning (`alias` en `getinfo`).  
**Comportamiento esperado:** debe coincidir con el alias configurado en `lnd.conf`. Si aparece vacío, revisar la configuración del nodo.

### Sync
Indica si el nodo está sincronizado con la blockchain (`synced_to_chain`) y el grafo de canales (`synced_to_graph`).  
- 🟢 **OK** — nodo sincronizado, operativo.  
- 🔴 **NO** — nodo offline o atrasado. Ningún pago puede enrutarse.  
**Comportamiento esperado:** siempre en OK. Si aparece NO repetidamente, revisar bitcoind y la conexión de red.

### Bloque
Altura de bloque actual que conoce el nodo.  
**Comportamiento esperado:** debe estar al día con la altura real de la red. Un bloque atrasado >6 bloques indica problema de sincronización.

### Peers
Número de peers P2P conectados actualmente (`num_peers` en `getinfo`).  
**Comportamiento esperado:** ≥3 peers activos. Más peers = mejor conectividad y más rutas disponibles. Menos de 2 es señal de aislamiento.

### Wallet (On-chain)
Saldo confirmado en la wallet on-chain (sats). Fuente: `walletbalance`.  
**Comportamiento esperado:** mantener suficiente saldo para abrir nuevos canales cuando sea necesario. Demasiado en on-chain = capital no trabajando en canales.

### Uptime 24h
Porcentaje de snapshots de las últimas 24 horas en que `synced_to_chain = true`.  
**Comportamiento esperado:** 100%. Valores por debajo del 95% indican reinicios frecuentes o problemas de red que interrumpen el enrutamiento.

---

## ◀ Panel Izquierdo — Canales & Liquidez

### 📡 Canales Activos / Total
Canales activos vs. total de canales abiertos. Un canal activo tiene al peer conectado y puede enrutar pagos.  
**Comportamiento esperado:**
- Ratio activo/total ≥ 80% es saludable.
- Canales inactivos indican que el peer se desconectó. Si persiste >24h, considerar cerrar el canal.
- En testnet4 es normal tener más inactividad por la menor participación de nodos.

### 💧 Liquidez Local (Gauge circular)
Porcentaje de la liquidez total que está en tu lado: `local / (local + remote) × 100`.  
**Comportamiento esperado:**
- **40–60%** → zona óptima: puedes enviar y recibir por igual.
- **< 20%** → casi sin liquidez saliente; no puedes iniciar pagos ni rebalanceos.
- **> 80%** → casi sin liquidez entrante; no puedes recibir pagos.
- El gauge cambia de color: verde (equilibrado), ámbar (extremo), rojo (crítico).

### ⚡ Capacidad Total
Suma de sats bloqueados en todos tus canales activos (local + remote).  
**Comportamiento esperado:**
- A mayor capacidad, mayor atractivo como hub de enrutamiento.
- En mainnet, nodos relevantes tienen >10M sats de capacidad total.
- En testnet4 los valores son menores; lo importante es la proporción relativa.

### 🧟 Canales Zombie
Canales que llevan **más de 7 días activos sin recibir actualizaciones** (`num_updates` delta < 5 en ese período). El capital ahí está bloqueado e improductivo.  
**Comportamiento esperado:**
- **0 zombies** → todos tus canales tienen actividad.
- Si hay zombies: evaluar si el peer está activo y si vale la pena mantener el canal.
- Un zombie persistente durante semanas es candidato a cierre para liberar capital.

---

## ▶ Panel Derecho — Enrutamiento & Rentabilidad

### 📈 Fees Ganadas (acumulado)
Suma acumulada de milisatoshi (msat) ganados por enrutar pagos de terceros a través de tu nodo. Fuente: `fwdinghistory` → campo `fee_msat`.  
**Comportamiento esperado:**
- En mainnet, nodos bien conectados ganan cientos de miles de msat/mes.
- En testnet4 el tráfico es mínimo; cifras bajas son normales.
- Tendencia creciente = tu nodo está siendo utilizado como hub.

### 📉 Fees Pagadas (acumulado)
Suma acumulada de msat pagados como comisión al rebalancear tus canales. Fuente: `listpayments` → pagos SUCCEEDED.  
**Comportamiento esperado:**
- Debe ser **menor** que las fees ganadas para que el nodo sea rentable.
- Si supera lo ganado, estás subsidiando la red en lugar de ganar.
- Rebalanceos excesivos con fees altas son la causa más común de pérdida.

### ⚡ Forwards (acumulado)
Número total de pagos enrutados por tu nodo desde que empezó la recolección.  
- **Vol:** volumen en sats enrutado en total.  
**Comportamiento esperado:**
- Número creciente indica que tu nodo aparece en las rutas de otros.
- Forwards con volúmenes grandes = participas en pagos relevantes.
- Muchos forwards con volumen pequeño = enrutamiento de micropagos.

### ⚖️ Ratio Rebalanceo/Enrutamiento
`fees_paid / fees_earned × 100` — qué porcentaje de lo ganado se va en rebalanceos.  
**Comportamiento esperado:**
- **< 50%** → excelente, el nodo es claramente rentable.
- **50–100%** → aceptable, hay margen pero se puede optimizar.
- **> 100%** → estás perdiendo dinero. Reducir frecuencia/costo de rebalanceos o subir las fees de enrutamiento.
- En testnet4 con poco tráfico este ratio puede distorsionarse; lo importante es la tendencia.

### 🎯 Eficiencia de Capital
`sats_enrutados / capacidad_total` — qué fracción del capital bloqueado está "trabajando" en enrutamiento.  
**Comportamiento esperado:**
- **> 1%** mensual es aceptable en mainnet.
- **> 5%** es muy bueno.
- **0%** o muy bajo en testnet4 es normal por la baja actividad de la red de prueba.
- Si en mainnet es persistentemente 0%, tu nodo no aparece en rutas → revisar fees, conectividad y liquidez.

---

## 🔽 Barra Inferior (Bottom Bar)

### 📊 Fees Ganadas vs Pagadas — 7 días
Gráfico de barras diarias: verde = fees ganadas, amarillo = fees pagadas.  
**Cómo interpretar:**
- Barras verdes más altas que amarillas cada día → el nodo es rentable día a día.
- Días con solo barra amarilla → hubo rebalanceos sin enrutamiento que los compense.
- Días vacíos → sin actividad (normal en testnet4).

### ⚡ Forwards por hora — 24h
Sparkline (línea) del número de pagos enrutados por hora en las últimas 24 horas.  
**Cómo interpretar:**
- Picos = horas de alta actividad de enrutamiento.
- Línea plana en 0 = sin tráfico en esas horas (inactividad, liquidez agotada, o canales inactivos).
- Tendencia creciente = el nodo está ganando relevancia como hub.
- En testnet4 es casi siempre plana; en mainnet se ven patrones diurnos.

### 💰 Net Profit 7d
Ganancia neta de los últimos 7 días: `fees_earned - fees_paid` en msat.  
**Comportamiento esperado:**
- **Positivo (verde)** → el nodo genera ingresos reales.
- **Negativo (rojo)** → estás perdiendo dinero en rebalanceos. Revisar estrategia.
- En testnet4 valores pequeños son normales; lo importante es que sea positivo.

### 🕒 Último Snapshot
Timestamp del snapshot más reciente en `node_history.db`.  
**Comportamiento esperado:**
- Debe ser reciente (últimos minutos si el intervalo es 5min).
- Si está desactualizado horas o días, el colector autónomo no está corriendo o tuvo un error.

---

## 🔧 Notas Técnicas

| Tabla SQLite | Contenido | Retención |
|---|---|---|
| `snapshots` | Una fila por ejecución del colector | Últimas 5,000 filas (~17 días a 5 min) |
| `channel_snapshots` | Detalle de cada canal por snapshot | CASCADE con snapshots |
| `daily_stats` | Agregados diarios | 365 días |
| `hourly_stats` | Agregados por hora | 168 horas (7 días) |

**Intervalo recomendado del colector:**
- `300s` (5 min) → balance entre granularidad e historial
- `60s` → mayor detalle pero solo ~3.5 días de historia raw
- `900s` (15 min) → menor consumo, ~52 días de historia raw
