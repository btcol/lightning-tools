# ⚡ Lightning Dashboard

![Lightning Dashboard Cockpit](images/ln-cockpit-Big.png)
Un panel de control gráfico (GUI) unificado construido nativamente en Python/Tkinter para facilitar el manejo, exploración y rebalanceo circular de nodos en la Lightning Network. Es un Wrapper funcional creado para operar sin depender de manipulación constante en la terminal, las pruebas de operacion se realizaron con el nodo en la red testnet4, el ajuste para la red mainnet es directo, solo hay que modificar las variables de entorno según tu sistema operativo y lnd.

## Funcionamiento del Software
El dashboard funciona como un orquestador central que se comunica de manera asíncrona con tu nodo `lnd` local. Al iniciar, ejecuta de forma automatizada rutinas de recolección para mapear la liquidez de tus canales y la topología pública de la Lightning Network, utilizando un algoritmo dinámico de búsqueda en amplitud (BFS) nativo en Python. La información es procesada internamente para alimentar módulos inteligentes y visualizaciones, persistiendo además un historial de rendimiento en una base de datos SQLite local (`node_history.db`) para llevar métricas de rentabilidad a largo plazo. Toda la operación ocurre de manera estricta y local en tu máquina, orquestando comandos exactos de `lncli` mediante subprocesos para asegurar tu total soberanía y privacidad.

## Paneles Incorporados
1. **🏠 btcol (Home)**: Pestaña principal de bienvenida que presenta información práctica sobre el orquestador y muestra dinámicamente la última fecha de actualización (commit) del repositorio junto al logo del dashboard.
2. **🌐 Red & Cockpit HUD**: Orquesta el escaneo del public graph. Despliega un modelo orbital astronómico 3D de tu nodo e integra la generación de un Cockpit HTML interactivo (Heads-Up Display) para monitorear en tiempo real métricas clave de rentabilidad, canales zombies, liquidez y uptime basados en tu historial.
3. **👛 Wallet On-chain**: Control centralizado de tu liquidez en capa base. Permite monitorear balances confirmados/no-confirmados, generar nuevas direcciones, detectar alta fragmentación y consolidar UTXOs con comisiones personalizadas. También gestiona la exportación manual y visualiza el estado de los Backups Estáticos de Canales (SCB).
4. **⚖️ Sugerencias de Rebalanceo**: Módulo automatizado predictivo. Deduce el origen (excedente local) y destinos (excedente remoto) y sugiere combinaciones ideales de balanceo circular interno.
5. **🔄 Ejecutar Rebalanceo**: Control manual para la creación automática de invoices de retorno y pagos auto-enrutados estableciendo topes configurables en SATs o PPM. Incluye simulación de rentabilidad y un log central de fácil lectura.
6. **🔌 Apertura de Canales (Smart Open)**: Módulo integrador que lee al vuelo tu saldo onchain para permitir conexiones a nodos top (1ml/amboss). Incluye **filtros dinámicos integrados en la interfaz** (Mínimo de canales y Máximo de días desde el último gossip) para rastrear inteligentemente y sugerir candidatos óptimos desde el public graph, automatizando `connect`, `openchannel` y el envío de liquidez inicial (**Push Amount**).
7. **❌ Cierre de Canales**: Interfaz unificada para gestionar cierres cooperativos o unilaterales (Force Close). Permite visualizar el estado de canales inactivos, pendientes o bloqueados en "WaitClose" y proceder con un clic.

## Ejecución y Set-up
Asegúrate de que tus demonios LND y Bitcoin estén listos en el background.

**Configuración:**
1. Copia el archivo de configuración de ejemplo que se encuentra en la raíz del repositorio:
   ```bash
   cp ../.env.example ../.env
   ```
2. Edita `../.env` para ajustar la red (`NETWORK`) y los binarios de ejecución si es necesario (`LNCLI_BIN`, `BITCOIN_CLI_BIN`).

**Dependencias:**
```bash
pip install -r requirements.txt
```

Para ingresar al dashboard:
```bash
python3 lightning_dashboard.py
```

## Arquitectura de Diseño
- `dashboard_core.py`: Lógica profunda enrutadora. Controla subprocess execution y transformaciones Graph a data models de visualización.
- `lightning_dashboard.py`: Contrucción declarativa de Widgets utilizando Tkinter (`ttk`). Define Threads asincrónicos para no bloquear la app.
- `scripts/`: Wrappers bash (`01_scan_network.sh`, etc.) modularizados con finalidades de reporting estructurado para el core Python. Mantenidos por legibilidad y compatibilidad legacy.

## Créditos y Derechos de Uso

En caso de utilizar partes de este repositorio o su totalidad para tus propios proyectos, debes mencionar a los autores originales. Atribución requerida: **[btcol](https://github.com/btcol)** en GitHub.
