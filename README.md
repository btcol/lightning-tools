# lightning-tools

![Lightning Dashboard](lightning-dashboard/images/ln-cockpit-Big.png)

> [!IMPORTANT]
> **🌐 NUEVA VERSIÓN WEB (VPS-Ready & Responsive):** Si administras tu nodo en un servidor remoto sin entorno de escritorio, dirígete a la subcarpeta [`lightning-web`](./lightning-web/). Ofrece un dashboard web unificado con **diseño adaptable a móviles**, dando acceso a todas las herramientas (billetera, piloto automático de rebalanceo, métricas y el Cockpit 3D) desde cualquier navegador.

> [!IMPORTANT]
> **🖥️ NUEVA VERSIÓN GRÁFICA (Desktop):** Si utilizas un sistema con entorno de ventanas, utiliza la subcarpeta [`lightning-dashboard`](./lightning-dashboard/). Contiene una interfaz gráfica (GUI) unificada y automatizada basada en Tkinter.

Multiples herramientas para administrar de forma mas amigable los nodos en Lightning Network, basado en comandos LNCLI y Python.

## Entorno de Nodos Lightning (Testnet4)

Este directorio contiene herramientas primarias de CLI (línea de comandos) para gestionar un nodo Lightning LND operando en `testnet4`. Incluye rutinas para inicialización rápida, generación gráfica 3D del estado de la red y scripts base para rebalanceo circular de canales.

## Configuración Universal (.env)

Ajusta las variables de entorno según tu sistema operativo. Anteriormente se usaba un único `.env` en la raíz, pero ahora **cada subproyecto (`lightning-dashboard` y `lightning-web`) cuenta con su propio archivo `.env` independiente**.

Antes de usar los dashboards, copia el archivo `.env.example` o configura el archivo `.env` correspondiente dentro de la subcarpeta que vayas a utilizar. Allí se configuran credenciales, red (`NETWORK`) y las rutas a los binarios (`LNCLI_BIN` y `BITCOIN_CLI_BIN`).

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

## Apoya el Proyecto

Si estas herramientas de código abierto te han sido de utilidad y quieres ayudar a que el proyecto siga creciendo, ¡tu apoyo es muy bienvenido! El desarrollador principal te lo agradecerá inmensamente, lo que le permitirá continuar dedicando tiempo a crear y mantener estas y más herramientas para la comunidad.

<img src="btcol_invoice.svg" width="200" alt="QR de Donación Lightning">

---

## Créditos y Derechos de Uso

En caso de utilizar partes de este repositorio o su totalidad para tus propios proyectos, debes mencionar a los autores originales. Atribución requerida: **[btcol](https://github.com/btcol)** en GitHub.
