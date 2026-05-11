# lightning-tools

![Lightning Dashboard](lightning-dashboard/images/ln-cockpit-Big.png)

> [!IMPORTANT]
> **🚀 NUEVA VERSIÓN GRÁFICA:** Te sugerimos encarecidamente dirigirte a la subcarpeta [`lightning-dashboard`](./lightning-dashboard/). Allí encontrarás una interfaz gráfica (GUI) unificada que contiene elementos nuevos y procesos mucho más automatizados (gestión de billetera on-chain, apertura inteligente de canales con Push Amount, rebalanceo circular predictivo y métricas en tiempo real) que reemplazan el uso de los scripts individuales de este directorio.

Multiples herramientas para administrar de forma mas amigable los nodos en Lightning Network, basado en comandos LNCLI y Python.

## Entorno de Nodos Lightning (Testnet4)

Este directorio contiene herramientas primarias de CLI (línea de comandos) para gestionar un nodo Lightning LND operando en `testnet4`. Incluye rutinas para inicialización rápida, generación gráfica 3D del estado de la red y scripts base para rebalanceo circular de canales.

Ajusta las variables de entorno segun tu sistema operativo, las pruebas se han realizado en la red testnet4 pero sirve para cualquier red, segun la necesidad, solo configure correctamente las variables de entorno que se encuentran al inicio de cada script.

## Funcionamiento del Software
El conjunto de utilidades funciona interactuando directamente con la interfaz de línea de comandos (CLI) de `lnd` (`lncli`) y `bitcoind`. Los scripts bash se encargaban de la comunicación de bajo nivel para administrar operaciones diarias (consultas de peers, pagos on-chain, generación de facturas). Paralelamente, los scripts de Python asumian las tareas computacionalmente pesadas: procesaban el grafo público de canales mediante algoritmos de búsqueda, filtraban topologías complejas y estructuran los datos para generar representaciones visuales interactivas en 3D de la Lightning Network de manera local sin depender de servidores externos.

## Componentes Principales
- `nodo_testnet4.sh`: Inicializa `bitcoind` y `lnd` sobre la testnet4, junto al entorno base de billeteras on-chain.
- `mineria.sh`: Script persistente de minería en Testnet4 con auto-recuperación que interactúa directamente con el nodo LND.
- `send_coins.sh`: Utilidad on-chain de envío programable de transacciones crudas a la cartera del nodo.
- `start-server-protocol.sh`: Script auxiliar para la inicialización de protocolos.

> **Nota:** Herramientas antiguas (como `vecinos_canales.sh`, `visualizar_red_3d.py`, generadores de rebalanceo y listado de peers en CLI) han sido deprecadas. Todas esas funcionalidades fueron mejoradas e integradas dentro de la GUI en la subcarpeta `lightning-dashboard`.

## Instalación de Dependencias
Ver `requirements.txt` para dependencias de los analizadores escritos en Python.
Instala usando:
```bash
pip install -r requirements.txt
```
Además requiere de `bitcoin-cli`, `lnd`, `lncli`, y utilería como `jq` instalados a nivel sistema u operativos localmente como `lncli-debug`.

---

## Créditos y Derechos de Uso

En caso de utilizar partes de este repositorio o su totalidad para tus propios proyectos, debes mencionar a los autores originales. Atribución requerida: **[btcol](https://github.com/btcol)** en GitHub.
