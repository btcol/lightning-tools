# lightning-tools

Multiples herramientas para administrar de forma mas amigable los nodos en Lightning Network, basado en comandos LNCLI y Python.

## Entorno de Nodos Lightning (Testnet4)

Este directorio contiene herramientas primarias de CLI (línea de comandos) para gestionar un nodo Lightning LND operando en `testnet4`. Incluye rutinas para inicialización rápida, generación gráfica 3D del estado de la red y scripts base para rebalanceo circular de canales.

Ajusta las variables de entorno segun tu sistema operativo, las pruebas se han realizado en la red testnet4 pero sirve para cualquier red, segun la necesidad, solo configure correctamente las variables de entorno que se encuentran al inicio de cada script.

## Funcionamiento del Software
El conjunto de utilidades funciona interactuando directamente con la interfaz de línea de comandos (CLI) de `lnd` (`lncli`) y `bitcoind`. Los scripts bash se encargaban de la comunicación de bajo nivel para administrar operaciones diarias (consultas de peers, pagos on-chain, generación de facturas). Paralelamente, los scripts de Python asumian las tareas computacionalmente pesadas: procesaban el grafo público de canales mediante algoritmos de búsqueda, filtraban topologías complejas y estructuran los datos para generar representaciones visuales interactivas en 3D de la Lightning Network de manera local sin depender de servidores externos.

## Componentes Principales
- `nodo_testnet4.sh`: Inicializa `bitcoind` y `lnd` sobre la testnet4, junto al entorno base de billeteras on-chain.
- `listpeers.sh`: Imprime reporte rápido de la lista de peers P2P y su intersección con los canales abiertos locales.
- `vecinos_canales.sh`: Poderoso colector de red. Lee la estructura Graph pública y computa toda la red circundante al nodo, exportando un archivo `.csv`.
- `visualizar_red_3d.py`: Lee la información compilada y dibuja un escenario 3D interactivo con HTML dinámico vía Plotly.
- `plan_rebalance_testnet4.sh` / `plan_rebalance_invoice_testnet4.sh`: Generadores de planes y ejecutores manuales de rutas circulares limitadas por fee (PPM).
- `send_coins.sh`: Utilidad on-chain de envío programable de transacciones crudas a la cartera del nodo.

## Instalación de Dependencias
Ver `requirements.txt` para dependencias de los analizadores escritos en Python.
Instala usando:
```bash
pip install -r requirements.txt
```
Además requiere de `bitcoin-cli`, `lnd`, `lncli`, y utilería como `jq` instalados a nivel sistema u operativos localmente como `lncli-debug`.

---

**Nota:** Puedes encontrar una interfaz gráfica unificada que concentra todo el funcionamiento general de la terminal y del rebalanceo automatizado en la subcarpeta `lightning-dashboard`.

## Créditos y Derechos de Uso

En caso de utilizar partes de este repositorio o su totalidad para tus propios proyectos, debes mencionar a los autores originales. Atribución requerida: **[btcol](https://github.com/btcol)** en GitHub.
