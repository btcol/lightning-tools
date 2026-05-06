#!/usr/bin/env python3
"""
visualizar_red_3d.py
Visualización interactiva 3D de la red Lightning desde el CSV generado
por vecinos_canales.sh.

Dependencias:
    pip install pandas plotly networkx

Uso:
    python3 visualizar_red_3d.py [lightning_network.csv] [--my-pubkey <pubkey>]

    Si no se indica --my-pubkey, el script intenta detectar tu nodo
    automáticamente llamando a `lncli-debug -network=testnet4 getinfo`.
"""

import sys
import os
import math
import csv
import json
import subprocess
import webbrowser
from datetime import datetime, timezone

# ── Dependencias ───────────────────────────────────────────────────────────────
try:
    import pandas as pd
    import plotly.graph_objects as go
    import networkx as nx
except ImportError:
    print("Instalando dependencias...")
    os.system(f"{sys.executable} -m pip install pandas plotly networkx --quiet")
    import pandas as pd
    import plotly.graph_objects as go
    import networkx as nx

# ── Config ─────────────────────────────────────────────────────────────────────
CSV_FILE = sys.argv[1] if len(sys.argv) > 1 else "lightning_network.csv"
MAX_NODES    = 300   # limitar para performance (los más conectados)
EDGE_SAMPLE  = 3000  # máx edges a dibujar
NOW          = datetime.now(timezone.utc).timestamp()

# ── Detectar pubkey propia ────────────────────────────────────────────────────
def detect_my_pubkey():
    """Intenta obtener la pubkey del nodo local via lncli getinfo."""
    # 1) argumento --my-pubkey <pubkey>
    for i, arg in enumerate(sys.argv):
        if arg == "--my-pubkey" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    # 2) variable de entorno
    if os.environ.get("MY_PUBKEY"):
        return os.environ["MY_PUBKEY"]
    # 3) lncli getinfo automático
    network  = os.environ.get("NETWORK",  "testnet4")
    lncli    = os.environ.get("LNCLI_BIN", "lncli-debug")
    try:
        out = subprocess.check_output(
            [lncli, f"-network={network}", "getinfo"],
            stderr=subprocess.DEVNULL, timeout=10
        )
        info = json.loads(out)
        pk = info.get("identity_pubkey", "")
        if pk:
            print(f"  Mi nodo detectado: {info.get('alias', pk[:16])} ({pk[:20]}...)")
            return pk
    except Exception:
        pass
    print("  ⚠ No se pudo detectar tu nodo (usa --my-pubkey <pubkey>).")
    return None

MY_PUBKEY = detect_my_pubkey()

# ── Carga de datos ─────────────────────────────────────────────────────────────
print(f"Cargando {CSV_FILE}...")

cols = [
    "source_pubkey","source_alias","target_pubkey","target_alias",
    "capacity_sats","fee_base_msat","fee_rate_ppm","max_htlc_sats",
    "cltv_delta","disabled",
    "source_last_update","target_last_update",
    "source_channels","target_channels",
    "source_total_cap","target_total_cap"
]

df = pd.read_csv(CSV_FILE, names=cols, header=0, dtype=str).fillna("")

# Conversión numérica segura
for c in ["capacity_sats","fee_base_msat","fee_rate_ppm","max_htlc_sats",
          "source_channels","target_channels","source_total_cap","target_total_cap"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

df["disabled"] = df["disabled"].astype(str).str.strip() == "1"

for c in ["source_last_update","target_last_update"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

print(f"  Edges totales en CSV: {len(df)}")

# ── Construir grafo ────────────────────────────────────────────────────────────
# Usamos nx.Graph (no dirigido). Para evitar que A→B y B→A se fusionen en
# un solo edge perdiendo visibilidad, deduplicamos explícitamente:
# guardamos UN edge por par ordenado (min, max) pero solo si no existe ya.
G = nx.Graph()

# Primero, acumular metadatos de nodos
for _, r in df.iterrows():
    for side in ("source","target"):
        pk   = r[f"{side}_pubkey"]
        al   = r[f"{side}_alias"] or pk[:10]
        lu   = r[f"{side}_last_update"]
        ch   = r[f"{side}_channels"]       # canales reportados por gossip
        cap  = r[f"{side}_total_cap"]
        days = int((NOW - lu) / 86400) if lu > 0 else 9999
        if not G.has_node(pk):
            G.add_node(pk, alias=al, last_update=lu, channels_gossip=ch,
                       total_cap=cap, days_ago=days)

# Agregar edges desduplicados:
# El CSV puede traer A->B y B->A (dos filas para el mismo canal).
# nx.Graph los fusiona silenciosamente dejando sólo 1.  Para evitarlo,
# usamos el par ordenado como clave y solo tomamos la primera ocurrencia.
seen_edges = set()
for _, r in df.iterrows():
    u, v = r["source_pubkey"], r["target_pubkey"]
    key  = tuple(sorted([u, v]))
    if key not in seen_edges:
        seen_edges.add(key)
        G.add_edge(
            u, v,
            capacity=r["capacity_sats"],
            fee_base=r["fee_base_msat"],
            fee_rate=r["fee_rate_ppm"],
            max_htlc=r["max_htlc_sats"],
            disabled=r["disabled"]
        )

print(f"  Nodos únicos: {G.number_of_nodes()}  |  Edges únicos: {G.number_of_edges()}"
      f"  (filas CSV: {len(df)})")

# ── Reducir si el grafo es muy grande ─────────────────────────────────────────
if G.number_of_nodes() > MAX_NODES:
    print(f"  Reduciendo a los {MAX_NODES} nodos más conectados...")
    top_nodes = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:MAX_NODES]
    top_pks   = {n for n, _ in top_nodes}
    # Forzar que mi nodo esté aunque sea pequeño
    if MY_PUBKEY and MY_PUBKEY in G and MY_PUBKEY not in top_pks:
        top_pks.add(MY_PUBKEY)
        print("  (forzando inclusión de tu nodo en la vista reducida)")
    G = G.subgraph(top_pks).copy()

# ── Layout 3D (spring layout en 3D) ──────────────────────────────────────────
print("  Calculando layout 3D...")
pos3d = nx.spring_layout(G, dim=3, seed=42, k=0.5)

# ── Preparar datos de nodos ───────────────────────────────────────────────────
node_pks    = list(G.nodes())
node_x      = [pos3d[n][0] for n in node_pks]
node_y      = [pos3d[n][1] for n in node_pks]
node_z      = [pos3d[n][2] for n in node_pks]

node_aliases  = [G.nodes[n].get("alias","?") or n[:10] for n in node_pks]
# channels_gossip: valor del grafo público (puede ser mayor que lo visible en CSV)
channel_gossip= [G.nodes[n].get("channels_gossip", 0) for n in node_pks]
# degree real en este grafo (canales visibles en la gráfica)
node_channels = [G.degree(n) for n in node_pks]
node_total_cap= [G.nodes[n].get("total_cap", 0) for n in node_pks]
node_days     = [G.nodes[n].get("days_ago", 9999) for n in node_pks]

# Tamaño de nodo: según número de canales (escala logarítmica)
def safe_log(x, base=2):
    return math.log(max(x, 1), base)

node_sizes  = [max(4, safe_log(c, 2) * 4) for c in node_channels]

# Color: según días desde last_update (verde=reciente, rojo=viejo)
def days_to_hex(days):
    t = min(days / 30, 1.0)          # 0=hoy,  1=>=30 días
    r = int(80 + 170 * t)
    g = int(230 - 180 * t)
    b = int(100)
    return f"rgb({r},{g},{b})"

node_colors = [days_to_hex(d) for d in node_days]

# Hover text rico
node_text = []
for i, pk in enumerate(node_pks):
    days = node_days[i]
    uptime_str = f"{days} días atrás" if days < 9999 else "desconocido"
    cap_str    = f"{node_total_cap[i]:,}" if node_total_cap[i] else "?"
    deg        = node_channels[i]        # canales visibles en este CSV
    gossip_ch  = channel_gossip[i]       # canales reportados por gossip
    ch_extra   = f" (gossip: {gossip_ch})" if gossip_ch and gossip_ch != deg else ""
    node_text.append(
        f"<b>{node_aliases[i]}</b><br>"
        f"Pubkey: {pk[:20]}...<br>"
        f"Canales en gráfica: {deg}{ch_extra}<br>"
        f"Cap. total: {cap_str} sats<br>"
        f"Ult. gossip: {uptime_str}"
    )

# ── Preparar edges (sample si hay muchos) ────────────────────────────────────
edges = list(G.edges(data=True))
if len(edges) > EDGE_SAMPLE:
    import random
    random.seed(42)
    edges = random.sample(edges, EDGE_SAMPLE)

edge_x, edge_y, edge_z = [], [], []
edge_colors = []
edge_widths = []

for u, v, data in edges:
    if u not in pos3d or v not in pos3d:
        continue
    x0,y0,z0 = pos3d[u]
    x1,y1,z1 = pos3d[v]
    edge_x += [x0, x1, None]
    edge_y += [y0, y1, None]
    edge_z += [z0, z1, None]

    # Color por capacidad (informativo, el renderizado real usa edge_colors_map)
    cap = data.get("capacity", 0)
    if data.get("disabled"):
        col = "rgba(255,50,50,0.45)"    # rojo → deshabilitado
    elif cap >= 5_000_000:
        col = "rgba(255,215,0,0.55)"    # amarillo → gran capacidad
    elif cap >= 1_000_000:
        col = "rgba(100,180,255,0.45)"  # azul → media
    else:
        col = "rgba(150,255,150,0.30)"  # verde → pequeña
    edge_colors.append(col)

# Plotly no admite color por segmento en Scatter3d, usamos opacidad global
# Dividimos en grupos por categoría para leyenda de aristas
def split_edges_by_cap(edges, pos3d):
    groups = {"Grande (≥5M sat)": [], "Media (1M-5M sat)": [], "Pequeña (<1M sat)": [], "Deshabilitado": []}
    for u, v, data in edges:
        if u not in pos3d or v not in pos3d:
            continue
        x0,y0,z0 = pos3d[u]
        x1,y1,z1 = pos3d[v]
        seg = ([x0,x1,None],[y0,y1,None],[z0,z1,None])
        if data.get("disabled"):
            groups["Deshabilitado"].append(seg)
        elif data.get("capacity", 0) >= 5_000_000:
            groups["Grande (≥5M sat)"].append(seg)
        elif data.get("capacity", 0) >= 1_000_000:
            groups["Media (1M-5M sat)"].append(seg)
        else:
            groups["Pequeña (<1M sat)"].append(seg)
    return groups

def flatten_segs(segs):
    xs, ys, zs = [], [], []
    for (x,y,z) in segs:
        xs += x; ys += y; zs += z
    return xs, ys, zs

edge_groups = split_edges_by_cap(edges, pos3d)
edge_colors_map = {
    "Grande (≥5M sat)":   "rgba(255,215,0,0.6)",    # Amarillo
    "Media (1M-5M sat)":  "rgba(100,180,255,0.5)",  # Azul
    "Pequeña (<1M sat)":  "rgba(100,255,100,0.35)", # Verde
    "Deshabilitado":      "rgba(255,60,60,0.4)",    # Rojo
}

# ── Construir figura Plotly ───────────────────────────────────────────────────
print("  Generando visualización 3D...")

fig = go.Figure()

# Trazar edges por grupo
for grp_name, segs in edge_groups.items():
    if not segs:
        continue
    xs, ys, zs = flatten_segs(segs)
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode="lines",
        name=grp_name,
        line=dict(color=edge_colors_map[grp_name], width=1),
        hoverinfo="skip",
        legendgroup=grp_name,
    ))

# Separar mi nodo del resto para renderizarlo aparte
my_idx = None
if MY_PUBKEY and MY_PUBKEY in node_pks:
    my_idx = node_pks.index(MY_PUBKEY)

other_idx = [i for i in range(len(node_pks)) if i != my_idx]

# Trazar nodos de la red (todos excepto el mío)
fig.add_trace(go.Scatter3d(
    x=[node_x[i] for i in other_idx],
    y=[node_y[i] for i in other_idx],
    z=[node_z[i] for i in other_idx],
    mode="markers+text",
    name="Nodos",
    marker=dict(
        size=[node_sizes[i] for i in other_idx],
        color=[node_colors[i] for i in other_idx],
        opacity=0.9,
        line=dict(width=0.5, color="rgba(255,255,255,0.3)"),
        symbol="circle",
    ),
    text=[node_aliases[i] if node_channels[i] > 5 else "" for i in other_idx],
    textfont=dict(size=7, color="white"),
    textposition="top center",
    hovertext=[node_text[i] for i in other_idx],
    hoverinfo="text",
    legendgroup="Nodos",
))

# Trazar MI NODO con estilo destacado
my_scene_annotation = []
if my_idx is not None:
    mx, my, mz = node_x[my_idx], node_y[my_idx], node_z[my_idx]
    my_alias   = node_aliases[my_idx]
    my_size    = max(14, node_sizes[my_idx] * 1.4)   # siempre grande y visible

    fig.add_trace(go.Scatter3d(
        x=[mx], y=[my], z=[mz],
        mode="markers",
        name="⭐ Mi nodo",
        marker=dict(
            size=my_size,
            color="#FFD700",          # dorado
            opacity=1.0,
            symbol="diamond",
            line=dict(width=2, color="white"),
        ),
        hovertext=[node_text[my_idx]],
        hoverinfo="text",
        legendgroup="Mi nodo",
    ))

    # Anotación 3D con flecha discreta apuntando al nodo
    my_scene_annotation = [dict(
        x=mx, y=my, z=mz,
        text=f"<b>◀ {my_alias}</b>",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=1.5,
        arrowcolor="#FFD700",
        ax=70, ay=-55,              # desplazamiento en píxeles de pantalla
        font=dict(size=11, color="#FFD700"),
        bgcolor="rgba(10,10,30,0.7)",
        bordercolor="#FFD700",
        borderwidth=1,
        opacity=0.9,
    )]
    print(f"  ⭐ Tu nodo '{my_alias}' marcado con flecha dorada.")
else:
    if MY_PUBKEY:
        print("  ⚠ Tu nodo no aparece en el graph local (sin canales anunciados).")

# Layout dark theme
now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
fig.update_layout(
    title=dict(
        text=f"<b>⚡ Red Lightning — Visualización 3D</b><br>"
             f"<sub>{G.number_of_nodes()} nodos · {len(edges)} canales · {now_str}</sub>",
        x=0.5, xanchor="center",
        font=dict(size=18, color="white"),
    ),
    scene=dict(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   backgroundcolor="rgb(10,10,20)", title=""),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   backgroundcolor="rgb(10,10,20)", title=""),
        zaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   backgroundcolor="rgb(10,10,20)", title=""),
        bgcolor="rgb(10,10,20)",
        annotations=my_scene_annotation,
    ),
    paper_bgcolor="rgb(8,8,18)",
    plot_bgcolor="rgb(8,8,18)",
    font=dict(color="white"),
    legend=dict(
        bgcolor="rgba(20,20,40,0.8)",
        bordercolor="rgba(100,100,150,0.5)",
        borderwidth=1,
        font=dict(size=11),
        title=dict(text="<b>Canales por capacidad</b>"),
    ),
    margin=dict(l=0, r=0, t=80, b=0),
    hoverlabel=dict(
        bgcolor="rgba(20,20,50,0.95)",
        bordercolor="rgba(100,150,255,0.8)",
        font=dict(size=12, color="white"),
    ),
    annotations=[
        dict(
            text=(
                "<b>🟢 Verde:</b> gossip reciente  "
                "<b>🔴 Rojo:</b> >30 días sin actualizar<br>"
                "Tamaño del nodo ∝ nº canales  |  "
                "Arrastre para rotar · Scroll para zoom"
            ),
            showarrow=False, xref="paper", yref="paper",
            x=0.5, y=0, xanchor="center", yanchor="bottom",
            font=dict(size=10, color="rgba(180,180,220,0.8)"),
            bgcolor="rgba(10,10,30,0.6)",
        )
    ],
)

# ── Construir lookup de nodos para la búsqueda JS ────────────────────────────
# Incluye todos los nodos (no sólo los renderizados) para búsquedas fieles
import json
node_lookup_js = {}
for i, pk in enumerate(node_pks):
    alias = node_aliases[i]
    entry = {
        "pk":      pk,
        "alias":   alias,
        "x":       node_x[i],
        "y":       node_y[i],
        "z":       node_z[i],
        "ch":      node_channels[i],
        "cap":     node_total_cap[i],
        "days":    node_days[i],
    }
    node_lookup_js[pk] = entry                      # buscar por pubkey completa
    node_lookup_js[pk[:20]] = entry                 # por prefijo (20 chars)
    node_lookup_js[alias.lower()] = entry           # por alias (case-insensitive)

nl_json = json.dumps(node_lookup_js, ensure_ascii=False)

# ── JavaScript inyectado en el HTML ─────────────────────────────────────────
SEARCH_JS = f"""
(function() {{
  // ── Lookup de nodos embebido desde Python ──────────────────────────────────
  const NODE_LOOKUP = {nl_json};

  // Índice del trace de búsqueda (lo añadiremos dinámicamente)
  let searchTraceIdx = null;

  // ── Panel de búsqueda ─────────────────────────────────────────────────────
  const panel = document.createElement('div');
  panel.id = 'search-panel';
  panel.style.cssText = `
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-family: monospace;
  `;

  const row = document.createElement('div');
  row.style.cssText = 'display:flex; gap:6px; align-items:center;';

  const input = document.createElement('input');
  input.id = 'node-search-input';
  input.type = 'text';
  input.placeholder = '🔍 alias o pubkey...';
  input.style.cssText = `
    background: rgba(10,10,30,0.92);
    border: 1px solid rgba(0,220,255,0.55);
    border-radius: 6px;
    color: #00dcff;
    font-size: 13px;
    padding: 6px 10px;
    width: 220px;
    outline: none;
    box-shadow: 0 0 8px rgba(0,220,255,0.25);
  `;

  const btn = document.createElement('button');
  btn.textContent = 'Buscar';
  btn.style.cssText = `
    background: rgba(0,180,255,0.18);
    border: 1px solid rgba(0,220,255,0.55);
    border-radius: 6px;
    color: #00dcff;
    font-size: 13px;
    padding: 6px 12px;
    cursor: pointer;
  `;

  const clearBtn = document.createElement('button');
  clearBtn.textContent = '✕';
  clearBtn.title = 'Limpiar búsqueda';
  clearBtn.style.cssText = `
    background: rgba(255,60,60,0.15);
    border: 1px solid rgba(255,100,100,0.5);
    border-radius: 6px;
    color: #ff6666;
    font-size: 13px;
    padding: 6px 10px;
    cursor: pointer;
  `;

  const status = document.createElement('div');
  status.id = 'search-status';
  status.style.cssText = `
    color: rgba(180,220,255,0.85);
    font-size: 11px;
    padding: 4px 8px;
    background: rgba(10,10,30,0.75);
    border-radius: 4px;
    display: none;
  `;

  row.appendChild(input);
  row.appendChild(btn);
  row.appendChild(clearBtn);
  panel.appendChild(row);
  panel.insertAdjacentHTML('beforeend', `
    <div style="font-weight:bold;color:#fff;margin-bottom:4px;font-size:13px;margin-top:10px;">ℹ️ Leyenda de Nodos</div>
    <div><span style="font-size:14px;">◉</span> <b>Tamaño:</b> Proporcional al Nº de canales</div>
    <div><span style="font-size:14px;">🎨</span> <b>Color:</b> Último chisme (gossip)</div>
    <div style="display:flex;align-items:center;margin-top:4px;">
      <span style="background:#50e664;width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px;"></span> Reciente (< 30 días)
    </div>
    <div style="display:flex;align-items:center;margin-top:2px;">
      <span style="background:#f03264;width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px;"></span> Inactivo (> 30 días)
    </div>
    <hr style="border:0;border-top:1px solid rgba(255,255,255,0.2);margin:8px 0;width:100%;">
    <div style="display:flex;align-items:center;justify-content:space-between;">
      <label for="camSpeed" style="cursor:pointer;font-weight:bold;color:#00ffed;">↻ Auto-Giro:</label>
      <input type="range" id="camSpeed" min="0" max="50" value="6" style="width:80px;cursor:pointer;">
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-top:5px;">
      <label for="autoReload" style="cursor:pointer;font-weight:bold;color:#ffcc00;">🔁 Auto-Refresco:</label>
      <div style="display:flex;align-items:center;gap:5px;">
        <input type="checkbox" id="autoReload" style="cursor:pointer;">
        <input type="number" id="reloadSecs" value="30" min="5" style="width:35px;background:#000;color:#ffcc00;border:1px solid #ffcc00;font-size:10px;text-align:center;">
      </div>
    </div>
  `);
  panel.appendChild(status);
  document.body.appendChild(panel);

  // ── Lógica de búsqueda ─────────────────────────────────────────────────────
  // Ojo: Plotly renderiza en un div que envuelve la clase js-plotly-plot
  function getGd() {{
      return document.querySelector('.js-plotly-plot');
  }}

  function removeSearchTrace() {{
    const gd = getGd();
    if (!gd) return;
    if (searchTraceIdx !== null) {{
      Plotly.deleteTraces(gd, searchTraceIdx);
      searchTraceIdx = null;
    }}
  }}

  function doSearch() {{
    const gd = getGd();
    if (!gd) return;
    
    const q = input.value.trim();
    sessionStorage.setItem('savedSearchQuery', q);
    if (!q) {{ removeSearchTrace(); status.style.display='none'; return; }}

    // Buscar por pubkey exacta, prefijo o alias (case-insensitive)
    const ql = q.toLowerCase();
    let found = NODE_LOOKUP[q]              // pubkey exacta
             || NODE_LOOKUP[q.slice(0,20)]  // prefijo pubkey
             || NODE_LOOKUP[ql];            // alias exacto

    // Si no hay éxito directo, buscar alias que contenga el texto
    if (!found) {{
      for (const [key, val] of Object.entries(NODE_LOOKUP)) {{
        if (key.toLowerCase().includes(ql) && val.alias) {{
          found = val;
          break;
        }}
      }}
    }}

    removeSearchTrace();

    if (!found) {{
      status.textContent = '⚠ Nodo no encontrado en la gráfica interactiva.';
      status.style.color  = '#ff8888';
      status.style.display= 'block';
      return;
    }}

    const days_str  = found.days < 9999 ? found.days + ' días' : 'desc.';
    const cap_str   = found.cap  ? found.cap.toLocaleString() + ' sats' : '?';

    // Trace destacado: diamante cian grande
    const newTrace = {{
      type: 'scatter3d',
      x: [found.x], y: [found.y], z: [found.z],
      mode: 'markers',
      name: '🔍 Encontrado',
      marker: {{
        size: 18,
        color: '#00ffed',
        opacity: 1.0,
        symbol: 'diamond',
        line: {{ width: 2, color: 'white' }},
      }},
      hovertext: [
        '<b>' + found.alias + '</b><br>'
        + 'Pubkey: ' + found.pk.slice(0,20) + '...<br>'
        + 'Canales (red): ' + found.ch + '<br>'
        + 'Cap. total: ' + cap_str + '<br>'
        + 'Últ. gossip: ' + days_str
      ],
      hoverinfo: 'text',
      showlegend: true,
    }};

    Plotly.addTraces(gd, newTrace).then(fig => {{
      searchTraceIdx = gd.data.length - 1;
    }});

    // Anotación 3D con flecha cian
    const currentAnnotations = gd.layout.scene.annotations || [];
    // Eliminar anotación de búsqueda anterior (etiqueta '🔍 ...')
    const cleaned = currentAnnotations.filter(a => !a.text.startsWith('<b>🔍'));
    const newAnnot = {{
      x: found.x, y: found.y, z: found.z,
      text: '<b>🔍 ' + found.alias + '</b>',
      showarrow: true,
      arrowhead: 2,
      arrowsize: 1.5,
      arrowwidth: 1.5,
      arrowcolor: '#00ffed',
      ax: -70, ay: 55,
      font: {{ size: 12, color: '#00ffed' }},
      bgcolor: 'rgba(0,30,30,0.8)',
      bordercolor: '#00ffed',
      borderwidth: 1,
      opacity: 0.95,
    }};
    Plotly.relayout(gd, {{ 'scene.annotations': [...cleaned, newAnnot] }});

    status.innerHTML  = '✅ <b>' + found.alias + '</b> | ch: ' + found.ch + ' | cap: ' + cap_str;
    status.style.color = '#aaffee';
    status.style.display = 'block';
  }}

  function doClear() {{
    input.value = '';
    removeSearchTrace();
    sessionStorage.removeItem('savedSearchQuery');
    
    // Restaurar solo las anotaciones sin la búsqueda
    const gd = getGd();
    if (gd) {{
      const current = gd.layout.scene.annotations || [];
      const restored = current.filter(a => !a.text.startsWith('<b>🔍'));
      Plotly.relayout(gd, {{ 'scene.annotations': restored }});
    }}
    status.style.display = 'none';
  }}

  btn.addEventListener('click', doSearch);
  clearBtn.addEventListener('click', doClear);
  input.addEventListener('keydown', e => {{ if (e.key === 'Enter') doSearch(); }});

  // LÓGICA DE AUTO-REFRESCO (Persistente)
  const autoReloadCheck = document.getElementById('autoReload');
  const reloadSecsInput = document.getElementById('reloadSecs');
  
  autoReloadCheck.checked = localStorage.getItem('autoReload') === 'true';
  reloadSecsInput.value = localStorage.getItem('reloadSecs') || '30';

  let reloadTimer = null;
  const startReloadTimer = () => {{
    if (reloadTimer) clearTimeout(reloadTimer);
    if (autoReloadCheck.checked) {{
      const ms = Math.max(5, parseInt(reloadSecsInput.value)) * 1000;
      reloadTimer = setTimeout(() => {{ 
         console.log('Auto-refrescando gráfica...');
         const gd = getGd();
         if (gd && gd.layout && gd.layout.scene && gd.layout.scene.camera) {{
             sessionStorage.setItem('savedCamera', JSON.stringify(gd.layout.scene.camera));
         }}
         const slider = document.getElementById('camSpeed');
         if (slider) sessionStorage.setItem('savedCamSpeed', slider.value);
         location.reload(); 
      }}, ms);
    }}
  }};

  autoReloadCheck.onchange = () => {{
    localStorage.setItem('autoReload', autoReloadCheck.checked);
    startReloadTimer();
  }};
  reloadSecsInput.onchange = () => {{
    localStorage.setItem('reloadSecs', reloadSecsInput.value);
    if (autoReloadCheck.checked) startReloadTimer();
  }};

  // Eliminar flash blanco
  document.body.style.backgroundColor = 'rgb(10,10,20)';

  // Restaurar estado de cámara previo al refresco
  setTimeout(() => {{
      const gd = getGd();
      if (gd) {{
          const savedCamStr = sessionStorage.getItem('savedCamera');
          if (savedCamStr) {{
              try {{
                  Plotly.relayout(gd, {{'scene.camera': JSON.parse(savedCamStr)}});
              }} catch(e) {{}}
          }}
      }}
      const savedCamSpeed = sessionStorage.getItem('savedCamSpeed');
      if (savedCamSpeed) {{
          const slider = document.getElementById('camSpeed');
          if (slider) slider.value = savedCamSpeed;
      }}
      
      const savedSearchQuery = sessionStorage.getItem('savedSearchQuery');
      if (savedSearchQuery) {{
          input.value = savedSearchQuery;
          doSearch();
      }}
  }}, 100);

  console.log('Buscador inicializado. Nodos interactivos disponibles.');
  startReloadTimer();
}})();
"""

# ── Exportar HTML con búsqueda integrada ──────────────────────────────────────
out_html = CSV_FILE.replace(".csv", "_red_3d.html")
fig.write_html(out_html, include_plotlyjs="cdn", post_script=SEARCH_JS)
print(f"\n✅ Visualización guardada en: {out_html}")
print("   Búsqueda integrada: alias o pubkey en el panel superior derecho.")

abs_path = os.path.abspath(out_html)
print(f"   Abriendo: file://{abs_path}")
try:
    webbrowser.open(f"file://{abs_path}")
except Exception as e:
    print(f"   No se pudo abrir automáticamente: {e}")
    print(f"   Abre manualmente: {abs_path}")
