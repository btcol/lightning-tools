# Lightning Node Gamification: De Herramienta a Juego

Este documento recoge la lluvia de ideas para transformar el `lightning-dashboard` y `lightning-web` en una experiencia gamificada y divertida, donde el usuario aprende a gestionar su nodo Lightning Network superando retos y consiguiendo objetivos visuales.

## 1. Sistema de Puntuación (Score) y Rango del Nodo
En lugar de mostrar solo métricas financieras, se traducen a "Puntos de Experiencia (XP)":
- **XP por Enrutamiento:** Puntos por cada satoshi ganado en comisiones. Multiplicadores si el enrutamiento pasó por canales recientemente rebalanceados.
- **Rangos (Niveles):** El usuario evoluciona: *“Aprendiz de Satoshi”* -> *“Novato del Rayo”* -> *“Enrutador Activo”* -> *“Maestro de Liquidez”* -> *“Hub de la Red”*. 
- **Salud del Nodo (HP - Health Points):** Una barra (0 al 100%). Baja si hay "Zombies" (>30 días inactivos), si la liquidez está vaciada hacia un lado, o si los UTXOs on-chain están fragmentados.

## 2. Misiones y Desafíos (Quests)
Un panel de "Misiones Activas" para fomentar el aprendizaje práctico:
- **"El Equilibrador":** Lograr que 3 canales tengan un ratio perfecto (50/50).
- **"Cazador de Zombies":** Identificar y cerrar un canal inactivo (Force o Coop).
- **"El Diplomático":** Abrir un canal usando sugerencias de la red (peer con alta capacidad).
- **"Francotirador de Fees":** Consolidar UTXOs pagando una tarifa muy baja (ej. < 5 sats/vbyte).

## 3. Logros Desbloqueables (Badges / Trofeos)
Vitrina visual de medallas:
- 🏆 **Primera Sangre:** Enrutaste tu primera transacción.
- 🏆 **Rayo Dorado:** Todos los canales en el Cockpit 3D están de color amarillo brillante (balanceados).
- 🏆 **Manos de Diamante:** Acumulaste 100,000 sats en comisiones ganadas.
- 🏆 **Insomne:** 100% de Uptime del nodo en los últimos 7 días.

## 4. Feedbacks Visuales y "Micro-Recompensas"
- **Confeti / Animaciones:** Al finalizar un rebalanceo exitoso o ganar un logro.
- **Grafo 3D Vivo:** Nodos que "palpitan" cuando ganan muchas comisiones o parpadean en rojo pidiendo ayuda si están muy desbalanceados.
- **Sonidos:** Pequeños efectos sonoros (tipo moneda) cuando el stream SSE notifica una ganancia de ruteo.

## 5. Tablas de Récords (Leaderboard Local)
- **Comisiones vs Mes Pasado:** Gráfico comparativo para superarse a sí mismo.
- **Récords Personales:** "Mayor pago enrutado: X sats", "Día más rentable", etc.
