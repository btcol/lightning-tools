# ⚡ Lightning Web Dashboard

Versión web del Lightning Dashboard, diseñada para correr en **VPS sin escritorio gráfico**.
Cuenta con un **diseño completamente Responsive**, adaptable a teléfonos móviles, tablets y escritorio.
Mismas 6 pestañas del Tkinter original, incluyendo el **Piloto Automático de Rebalanceo**, accesibles desde cualquier navegador.

## Inicio rápido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar el .env local (lightning-web/.env)
#    Ajusta LNCLI_BIN y las credenciales web:
#    WEB_USER=admin
#    WEB_PASS=tu_password_segura

# 3. Arrancar
python3 app.py
# → http://0.0.0.0:9630
```

## Variables de entorno (en `.env` local)

| Variable | Default | Descripción |
|---|---|---|
| `WEB_USER` | `admin` | Usuario para acceso web |
| `WEB_PASS` | `lightning` | Contraseña para acceso web |
| `WEB_PORT` | `9630` | Puerto del servidor |
| `WEB_HOST` | `0.0.0.0` | Interfaz de red |
| `NETWORK` | `testnet4` | Red LND |
| `LNCLI_BIN` | `lncli-debug` | Binario lncli |

## Uso en VPS (recomendado con tmux)

```bash
tmux new -s lightning-web
python3 app.py
# Ctrl+B, D para desvincular
```

O como servicio systemd — ver la documentación del proyecto principal.

## Arquitectura

- `app.py` — servidor Flask (REST API + SSE)
- `dashboard_core.py` — copia del core original (independiente)
- `scripts/` — copia de los scripts .sh del dashboard original
- `static/` — frontend HTML/CSS/JS (sin frameworks, con **diseño Responsive** para móviles)

El proyecto es 100% autónomo. Los datos (base SQLite, exportaciones HTML y backups SCB) se almacenan en sus propios directorios (`data/`, `exports/`, `backups/`) dentro de `lightning-web/`.

---

## Apoya el Proyecto

Si estas herramientas de código abierto te han sido de utilidad y quieres ayudar a que el proyecto siga creciendo, ¡tu apoyo es muy bienvenido! El desarrollador principal (actualmente desempleado) te lo agradecerá inmensamente, lo que le permitirá continuar dedicando tiempo a crear y mantener estas y más herramientas para la comunidad.

<img src="images/btcol_invoice.svg" width="200" alt="QR de Donación Lightning">

---

Atribución: **[btcol](https://github.com/btcol)**
