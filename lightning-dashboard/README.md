# ⚡ Lightning Dashboard

Un panel de control gráfico (GUI) unificado construido nativamente en Python/Tkinter para facilitar el manejo, exploración y rebalanceo circular de nodos en la Lightning Network. Es un Wrapper funcional creado para operar sin depender de manipulación constante en la terminal, las pruebas de operacion se realizaron con el nodo en la red testnet4, el ajuste para la red mainnet es directo, solo hay que modificar las variables de entorno según tu sistema operativo y lnd.

## Funcionamiento del Software
El dashboard funciona como un orquestador central que se comunica de manera asíncrona con tu nodo `lnd` local. Al iniciar, ejecuta de forma automatizada rutinas de recolección para mapear la liquidez de tus canales y la topología pública de la Lightning Network. Toda la información es procesada internamente (con algoritmos en Python) para alimentar módulos inteligentes, como el motor de sugerencias predictivas de rebalanceo y la renderización de la red en 3D. Esto permite generar facturas (invoices) y realizar pagos circulares con topes de comisiones de manera local, ejecutando los comandos exactos de `lncli` en subprocesos, manteniendo total privacidad y sin utilizar servicios externos de loop.

## Paneles Incorporados
1. **🌐 Red & Vista 3D**: Orquesta rutinas en segundo plano para escanear public graphs. Despliega un modelo orbital astronómico renderizado dinámicamente, actualizando un entorno interactivo con tu roster, métricas interconectadas (actividad de chismes/gossips, liquidez). Soporta autorotación.
2. **👥 Gestión de Peers**: Vista en tabla de tus peers P2P detectando cruces si sostienes canales mutuos abiertos.
3. **⚖️ Sugerencias y Rebalanceo**: Módulo automatizado predictivo. Deduce el origen (excedente local) y destinos (excedente remoto) y sugiere combinaciones de balanceo sin depender de HTLC requests a loop services de terceros.
4. **🔄 Ejecutor Circular**: Configuración de `invoice` automática de retorno y de `payinvoice` auto-permitida estableciendo límites fijos por PPM. Log central transparente para inspección de rutas y fallos.
5. **🔌 Apertura de Canales (Smart Open)**: Integrador que lee al vuelo tu saldo onchain y los pre-combina con los nodos Top detectados en los grafos circundantes (activos & alta cantidad de canales públicos) para automatizar los comandos `connect` y `openchannel`.

## Ejecución y Set-up
Asegúrate de que tus demonios LND estén listos en el background.

Dependencias:
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
