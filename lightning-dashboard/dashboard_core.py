#!/usr/bin/env python3
"""
dashboard_core.py
======================
Lógica principal del dashboard unificado para gestión de canales Lightning Network.

Dependencias:
  pip install pandas plotly networkx
"""

import os
import sys
import csv
import json
import math
import queue
import shutil
import threading
import subprocess
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

# ── Intentar importar dependencias opcionales ─────────────────────────────────
try:
    import pandas as pd
    import plotly.graph_objects as go
    import networkx as nx
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

# Red y binario lncli (sobreescribibles via variables de entorno)
NETWORK   = os.environ.get("NETWORK",   "testnet4")
LNCLI_BIN = os.environ.get("LNCLI_BIN", "lncli-debug")

# Rutas relativas al directorio del script
BASE_DIR    = Path(__file__).parent.resolve()
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR    = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"

# Archivo CSV generado por 01_scan_network.sh
CSV_FILE  = DATA_DIR / "lightning_network.csv"
# HTML de visualización 3D
HTML_FILE = EXPORTS_DIR / "lightning_network_red_3d.html"

# Parámetros de rebalanceo por defecto
DEFAULT_AMT_SATS      = 10000
DEFAULT_MAX_FEE_SATS  = 100
DEFAULT_MAX_FEE_PPM   = 1000
DEFAULT_CLTV_DELTA    = 40
TARGET_RATIO          = 50   # % de balance local objetivo
MIN_SHIFT_SATS        = 1000 # sats mínimos para sugerir rebalanceo

# Colores del tema oscuro
CLR_BG       = "#0a0a14"   # fondo principal
CLR_PANEL    = "#12121e"   # fondo de paneles
CLR_ACCENT   = "#00dcff"   # cian eléctrico (acento)
CLR_ACCENT2  = "#7b2fff"   # violeta (acento secundario)
CLR_GOLD     = "#ffd700"   # dorado (mi nodo)
CLR_GREEN    = "#00ff88"   # verde (éxito / activo)
CLR_RED      = "#ff4466"   # rojo (error / deshabilitado)
CLR_YELLOW   = "#ffcc00"   # amarillo (advertencia)
CLR_TEXT     = "#e0e0f0"   # texto principal
CLR_SUBTEXT  = "#8888aa"   # texto secundario
CLR_BORDER   = "#2a2a40"   # bordes


# =============================================================================
# UTILIDADES GENERALES
# =============================================================================

def run_lncli(*args, timeout=30):
    """
    Ejecuta lncli-debug con los argumentos dados y devuelve el JSON parseado.
    Lanza RuntimeError si el comando falla o el timeout expira.
    """
    cmd = [LNCLI_BIN, f"-network={NETWORK}"] + list(args)
    try:
        result = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=timeout
        )
        return json.loads(result)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"lncli error: {e.output.decode(errors='replace')}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout ejecutando: {' '.join(cmd)}")


def scid_to_uint64(scid: str) -> int:
    """
    Convierte un SCID en formato 'blockxTxIndexxVout' (ej: '129925x3x0')
    al entero uint64 que acepta payinvoice --outgoing_chan_id.
    """
    parts = scid.split("x")
    block, tx, vout = int(parts[0]), int(parts[1]), int(parts[2])
    return (block << 40) | (tx << 16) | vout


def fmt_sats(n) -> str:
    try:
        return f"{int(n):,} sats"
    except (ValueError, TypeError):
        return "? sats"


def days_since(ts) -> int:
    try:
        return int((datetime.now(timezone.utc).timestamp() - int(ts)) / 86400)
    except Exception:
        return 9999


def get_node_info():
    try:
        return run_lncli("getinfo", timeout=10)
    except Exception:
        return None


def get_channels():
    try:
        data = run_lncli("listchannels")
        return data.get("channels", [])
    except Exception:
        return []


def get_wallet_balance():
    try:
        return run_lncli("walletbalance", timeout=10)
    except Exception:
        return {}


def get_all_channels():
    channels = []
    
    # Canales activos
    try:
        active = run_lncli("listchannels", timeout=15).get("channels", [])
        for ch in active:
            channels.append({
                "chan_point": ch.get("channel_point", ""),
                "pubkey": ch.get("remote_pubkey", ""),
                "alias": ch.get("peer_alias", ""),
                "local": int(ch.get("local_balance", 0)),
                "remote": int(ch.get("remote_balance", 0)),
                "status": "OPEN",
                "active": ch.get("active", False)
            })
    except Exception:
        pass
        
    # Canales pendientes
    try:
        pending = run_lncli("pendingchannels", timeout=15)
        
        for c in pending.get("pending_open_channels", []):
            ch = c.get("channel", {})
            channels.append({
                "chan_point": ch.get("channel_point", ""),
                "pubkey": ch.get("remote_node_pub", ""),
                "alias": "pendiente_abrir", 
                "local": int(ch.get("local_balance", 0)),
                "remote": int(ch.get("remote_balance", 0)),
                "status": "PENDING_OPEN",
                "active": False
            })
            
        for c in pending.get("pending_closing_channels", []):
            ch = c.get("channel", {})
            channels.append({
                "chan_point": ch.get("channel_point", ""),
                "pubkey": ch.get("remote_node_pub", ""),
                "alias": "pendiente_cerrar",
                "local": int(ch.get("local_balance", 0)),
                "remote": int(ch.get("remote_balance", 0)),
                "status": "PENDING_CLOSE",
                "active": False
            })
            
        for c in pending.get("pending_force_closing_channels", []):
            ch = c.get("channel", {})
            channels.append({
                "chan_point": ch.get("channel_point", ""),
                "pubkey": ch.get("remote_node_pub", ""),
                "alias": "force_close",
                "local": int(ch.get("local_balance", 0)),
                "remote": int(ch.get("remote_balance", 0)),
                "status": "FORCE_CLOSING",
                "active": False
            })
            
        for c in pending.get("waiting_close_channels", []):
            ch = c.get("channel", {})
            channels.append({
                "chan_point": ch.get("channel_point", ""),
                "pubkey": ch.get("remote_node_pub", ""),
                "alias": "esperando_cierre",
                "local": int(ch.get("local_balance", 0)),
                "remote": int(ch.get("remote_balance", 0)),
                "status": "WAITING_CLOSE",
                "active": False
            })
            
    except Exception:
        pass
        
    return channels


def execute_closechannel(chan_point: str, force: bool, log_callback) -> bool:
    log = log_callback
    log(f"[{datetime.now().strftime('%H:%M:%S')}] Petición de cierre para {chan_point} ...")
    
    if ":" not in chan_point:
        log("❌ El identificador del canal debe contener ':' (txid:index)")
        return False
        
    txid, index = chan_point.split(":")
    
    cmd = [LNCLI_BIN, f"-network={NETWORK}", "closechannel", f"--funding_txid={txid}", f"--output_index={index}"]
    if force:
        cmd.append("--force")
        
    log(f"   Ejecutando: {' '.join(cmd)}")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in proc.stdout:
            log(f"   {line.rstrip()}")
        proc.wait(timeout=90)
        
        if proc.returncode == 0:
            log("✅ ¡Comando closechannel enviado exitosamente!")
            return True
        else:
            log(f"❌ closechannel falló con código {proc.returncode}")
            return False
    except subprocess.TimeoutExpired:
        proc.kill()
        log("❌ Timeout ejecutando closechannel.")
        return False
    except Exception as e:
        log(f"❌ Excepción ejecutando closechannel: {e}")
        return False


# =============================================================================
# LÓGICA DE REBALANCEO
# =============================================================================

def suggest_rebalances(channels: list, target_ratio=TARGET_RATIO,
                       min_shift=MIN_SHIFT_SATS, max_options=20) -> list:
    enriched = []
    for ch in channels:
        if not ch.get("active"):
            continue
        if len(ch.get("pending_htlcs", [])) > 0:
            continue
        cap   = int(ch.get("capacity", 0))
        local = int(ch.get("local_balance", 0))
        remote= int(ch.get("remote_balance", 0))
        scid  = ch.get("scid_str") or ch.get("chan_id", "")
        peer  = ch.get("peer_alias", "")
        pub   = ch.get("remote_pubkey", "")

        target_local = int((cap * target_ratio) / 100)
        delta = local - target_local
        sendable   = delta if delta > 0 else 0
        receivable = -delta if delta < 0 else 0

        enriched.append({
            "scid": scid, "peer": peer, "pub": pub,
            "cap": cap, "local": local, "remote": remote,
            "sendable": sendable, "receivable": receivable
        })

    suggestions = []
    for i, src in enumerate(enriched):
        if src["sendable"] < min_shift:
            continue
        for j, dst in enumerate(enriched):
            if i == j:
                continue
            if dst["receivable"] < min_shift:
                continue
            amount = min(src["sendable"], dst["receivable"])
            if amount < min_shift:
                continue
            suggestions.append({
                "score":      amount,
                "from_scid":  src["scid"],
                "to_scid":    dst["scid"],
                "from_peer":  src["peer"],
                "to_peer":    dst["peer"],
                "amount":     amount,
                "from_local": src["local"],
                "to_local":   dst["local"],
                "from_pub":   src["pub"],
                "to_pub":     dst["pub"],
            })

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:max_options]


def fee_analysis(amt_sats: int, max_fee_sats: int, max_fee_ppm: int) -> dict:
    if amt_sats <= 0:
        return {}
    fee_estimado   = (max_fee_ppm / 1_000_000) * amt_sats
    fee_ppm_if_max = (max_fee_sats / amt_sats)  * 1_000_000
    monto_min      = (max_fee_sats / max_fee_ppm) * 1_000_000 if max_fee_ppm > 0 else 0
    return {
        "fee_estimado":   fee_estimado,
        "fee_ppm_if_max": fee_ppm_if_max,
        "monto_min":      monto_min,
        "ok":             fee_estimado <= max_fee_sats,
    }


def execute_rebalance(from_scid: str, to_pub: str, amt_sats: int,
                      max_fee_sats: int, log_callback) -> bool:
    log = log_callback

    log(f"[1/3] Creando invoice de {amt_sats:,} sats en el nodo local...")
    try:
        inv = run_lncli(
            "addinvoice",
            f"--amt={amt_sats}",
            f"--memo=rebalance-{from_scid}",
            "--private",
            timeout=20
        )
    except RuntimeError as e:
        log(f"❌ Error creando invoice: {e}")
        return False

    payment_request = inv.get("payment_request", "")
    payment_hash    = inv.get("r_hash") or inv.get("r_hash_str") or inv.get("payment_hash", "")
    log(f"   ✅ Invoice creada. Hash: {payment_hash[:20]}...")

    log(f"[2/3] Calculando chan_id uint64 para SCID {from_scid}...")
    try:
        from_chan_id = scid_to_uint64(from_scid)
        log(f"   ✅ chan_id uint64 = {from_chan_id}")
    except Exception as e:
        log(f"❌ Error calculando chan_id: {e}")
        return False

    log(f"[3/3] Ejecutando payinvoice...")
    log(f"   outgoing_chan_id = {from_chan_id}")
    log(f"   last_hop         = {to_pub[:20]}...")
    log(f"   fee_limit        = {max_fee_sats} sats")

    cmd = [
        LNCLI_BIN, f"-network={NETWORK}",
        "payinvoice",
        "--allow_self_payment",
        f"--outgoing_chan_id={from_chan_id}",
        f"--last_hop={to_pub}",
        f"--fee_limit={max_fee_sats}",
        "--force",
        payment_request
    ]
    log(f"   CMD: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in proc.stdout:
            log(f"   {line.rstrip()}")
        proc.wait(timeout=120)
        if proc.returncode == 0:
            log("✅ ¡Rebalanceo exitoso!")
            return True
        else:
            log(f"❌ payinvoice terminó con código {proc.returncode}")
            return False
    except subprocess.TimeoutExpired:
        proc.kill()
        log("❌ Timeout: el pago tardó más de 120 segundos.")
        return False
    except Exception as e:
        log(f"❌ Error ejecutando payinvoice: {e}")
        return False


def get_channel_candidates(min_channels=3, max_days=30):
    """
    Lee la red desde el graph local (getnetworkinfo / describegraph) para
    encontrar nodos saludables con los que NO tenemos canal.
    Se usa el CSV pre-generado si existe para rapidez.
    """
    if not CSV_FILE.exists():
        return []
        
    # Mis canales actuales
    my_chans = get_channels()
    my_peers = set(ch.get("remote_pubkey") for ch in my_chans)
    
    my_info = get_node_info()
    my_pubkey = my_info.get("identity_pubkey", "") if my_info else ""
    
    nodes = {}
    import csv
    try:
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # skip header
            now_ts = datetime.now(timezone.utc).timestamp()
            
            for row in reader:
                if len(row) < 16: continue
                n1, a1, n2, a2 = row[0], row[1], row[2], row[3]
                lu1, lu2 = int(row[10] or 0), int(row[11] or 0)
                ch1, ch2 = int(row[12] or 0), int(row[13] or 0)
                cap1, cap2 = int(row[14] or 0), int(row[15] or 0)
                
                if n1 not in nodes:
                    nodes[n1] = {"pubkey": n1, "alias": a1, "channels": ch1, "cap": cap1, "last_update": lu1}
                if n2 not in nodes:
                    nodes[n2] = {"pubkey": n2, "alias": a2, "channels": ch2, "cap": cap2, "last_update": lu2}
    except Exception:
        pass
        
    candidates = []
    now_ts = datetime.now(timezone.utc).timestamp()
    
    for pubkey, data in nodes.items():
        if pubkey == my_pubkey or pubkey in my_peers:
            continue
        if data["channels"] < min_channels:
            continue
            
        days_ago = (now_ts - data["last_update"]) / 86400 if data["last_update"] > 0 else 9999
        if days_ago > max_days:
            continue
            
        candidates.append({
            "pubkey": pubkey,
            "alias": data["alias"],
            "channels": data["channels"],
            "capacity": data["cap"],
            "days_ago": int(days_ago)
        })
        
    # Ordenar por capacidad descendente
    candidates.sort(key=lambda x: x["capacity"], reverse=True)
    return candidates[:100]


def execute_openchannel(pubkey: str, amt_sats: int, log_callback) -> bool:
    log = log_callback
    
    # 1. Intentar obtener la URI del nodo (host)
    log(f"[1/3] Consultando direcciones para {pubkey[:16]}...")
    host = None
    try:
        info = run_lncli("getnodeinfo", f"--pub_key={pubkey}")
        addrs = info.get("node", {}).get("addresses", [])
        if addrs:
            host = addrs[0]["addr"]
            log(f"   Encontrado: {host}")
        else:
            log("   ⚠️ No se encontraron p2p_addresses públicas en el graph para este nodo.")
    except Exception as e:
        log(f"   ⚠️ Fallo al obtener info del nodo: {e}")
        
    # 2. Conectar al nodo si tenemos el host
    if host:
        uri = f"{pubkey}@{host}"
        log(f"[2/3] Conectando a {uri} ...")
        cmd_conn = [LNCLI_BIN, f"-network={NETWORK}", "connect", uri]
        try:
            res = subprocess.run(cmd_conn, capture_output=True, text=True, timeout=15)
            out = res.stdout + res.stderr
            if "already connected to peer" in out:
                log("   Ya conectado.")
            elif res.returncode == 0:
                log("   ✅ Conexión P2P exitosa.")
            else:
                log(f"   ⚠️ Fallo en connect: {out.strip()}")
        except Exception as e:
            log(f"   ⚠️ Error en connect: {e}")
    else:
        log("[2/3] Saltando conexión directa, confiando en tabla de ruteo interna...")

    # 3. Ejecutar openchannel
    log(f"[3/3] Abriendo canal con un fondo local de {amt_sats:,} sats...")
    cmd_open = [
        LNCLI_BIN, f"-network={NETWORK}",
        "openchannel",
        f"--node_key={pubkey}",
        f"--local_amt={amt_sats}"
    ]
    
    try:
        # Popen en block
        proc = subprocess.Popen(cmd_open, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            log(f"   {line.rstrip()}")
        proc.wait(timeout=60)
        
        if proc.returncode == 0:
            log(f"✅ ¡Comando openchannel enviado exitosamente!")
            return True
        else:
            log(f"❌ openchannel falló con código {proc.returncode}")
            return False
    except Exception as e:
        log(f"❌ Excepción ejecutando openchannel: {e}")
        return False


# =============================================================================
# VISUALIZACIÓN 3D
# =============================================================================

def generate_3d_html(csv_path: Path, html_path: Path,
                     my_pubkey: str = None, log_cb=print) -> bool:
    if not HAS_PLOTLY:
        log_cb("❌ Faltan dependencias: pip install pandas plotly networkx")
        return False

    if not csv_path.exists():
        log_cb(f"❌ CSV no encontrado: {csv_path}")
        return False

    log_cb(f"Cargando {csv_path.name}...")
    cols = [
        "source_pubkey","source_alias","target_pubkey","target_alias",
        "capacity_sats","fee_base_msat","fee_rate_ppm","max_htlc_sats",
        "cltv_delta","disabled",
        "source_last_update","target_last_update",
        "source_channels","target_channels",
        "source_total_cap","target_total_cap"
    ]
    df = pd.read_csv(csv_path, names=cols, header=0, dtype=str).fillna("")

    for c in ["capacity_sats","fee_base_msat","fee_rate_ppm","max_htlc_sats",
              "source_channels","target_channels","source_total_cap","target_total_cap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["disabled"] = df["disabled"].astype(str).str.strip() == "1"
    for c in ["source_last_update","target_last_update"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    log_cb(f"  Edges en CSV: {len(df)}")
    NOW = datetime.now(timezone.utc).timestamp()
    MAX_NODES, EDGE_SAMPLE = 300, 3000

    G = nx.Graph()
    for _, r in df.iterrows():
        for side in ("source", "target"):
            pk  = r[f"{side}_pubkey"]
            al  = r[f"{side}_alias"] or pk[:10]
            lu  = r[f"{side}_last_update"]
            ch  = r[f"{side}_channels"]
            cap = r[f"{side}_total_cap"]
            d   = int((NOW - lu) / 86400) if lu > 0 else 9999
            if not G.has_node(pk):
                G.add_node(pk, alias=al, last_update=lu,
                           channels_gossip=ch, total_cap=cap, days_ago=d)

    seen = set()
    for _, r in df.iterrows():
        u, v = r["source_pubkey"], r["target_pubkey"]
        key = tuple(sorted([u, v]))
        if key not in seen:
            seen.add(key)
            G.add_edge(u, v, capacity=r["capacity_sats"],
                       fee_base=r["fee_base_msat"], fee_rate=r["fee_rate_ppm"],
                       max_htlc=r["max_htlc_sats"], disabled=r["disabled"])

    # Forzar la inclusión de canales vivos del usuario
    my_live_chans = get_channels()
    my_peers_to_keep = set()
    
    if my_pubkey:
        if not G.has_node(my_pubkey):
            my_info = get_node_info()
            my_alias = my_info.get("alias", "Mi Nodo") if my_info else "Mi Nodo"
            G.add_node(my_pubkey, alias=my_alias, last_update=NOW, channels_gossip=len(my_live_chans), total_cap=0, days_ago=0)
            
        for ch in my_live_chans:
            pub = ch.get("remote_pubkey")
            if not pub: continue
            my_peers_to_keep.add(pub)
            if not G.has_node(pub):
                al = ch.get("peer_alias") or pub[:10]
                G.add_node(pub, alias=al, last_update=NOW, channels_gossip=1, total_cap=int(ch.get("capacity",0)), days_ago=0)
            
            if not G.has_edge(my_pubkey, pub) and not G.has_edge(pub, my_pubkey):
                G.add_edge(my_pubkey, pub, capacity=int(ch.get("capacity",0)), fee_base=0, fee_rate=0, max_htlc=0, disabled=False)

    log_cb(f"  Nodos: {G.number_of_nodes()}  |  Edges: {G.number_of_edges()}")

    if G.number_of_nodes() > MAX_NODES:
        log_cb(f"  Reduciendo a {MAX_NODES} nodos más conectados...")
        top_pks = {n for n, _ in sorted(G.degree(), key=lambda x: x[1], reverse=True)[:MAX_NODES]}
        if my_pubkey:
            top_pks.add(my_pubkey)
            top_pks.update(my_peers_to_keep) # Proteger peers directos de ser eliminados
        G = G.subgraph(top_pks).copy()

    log_cb("  Calculando layout 3D...")
    pos3d = nx.spring_layout(G, dim=3, seed=42, k=0.5)

    node_pks = list(G.nodes())
    node_x = [pos3d[n][0] for n in node_pks]
    node_y = [pos3d[n][1] for n in node_pks]
    node_z = [pos3d[n][2] for n in node_pks]
    node_aliases  = [G.nodes[n].get("alias","") or n[:10] for n in node_pks]
    node_channels = [G.degree(n) for n in node_pks]
    node_total_cap= [G.nodes[n].get("total_cap",0) for n in node_pks]
    node_days     = [G.nodes[n].get("days_ago",9999) for n in node_pks]
    node_gossip   = [G.nodes[n].get("channels_gossip",0) for n in node_pks]

    def safe_log(x, base=2):
        return math.log(max(x, 1), base)
    node_sizes = [max(4, safe_log(c, 2) * 4) for c in node_channels]

    def days_to_hex(days):
        t = min(days / 30, 1.0)
        return f"rgb({int(80+170*t)},{int(230-180*t)},100)"
    node_colors = [days_to_hex(d) for d in node_days]

    node_text = []
    for i, pk in enumerate(node_pks):
        d = node_days[i]
        uptime = f"{d} días atrás" if d < 9999 else "desconocido"
        cap_s  = f"{node_total_cap[i]:,}" if node_total_cap[i] else "?"
        g      = node_gossip[i]
        extra  = f" (gossip: {g})" if g and g != node_channels[i] else ""
        node_text.append(
            f"<b>{node_aliases[i]}</b><br>"
            f"Pubkey: {pk[:20]}...<br>"
            f"Canales: {node_channels[i]}{extra}<br>"
            f"Cap. total: {cap_s} sats<br>"
            f"Últ. gossip: {uptime}"
        )

    edges = list(G.edges(data=True))
    if len(edges) > EDGE_SAMPLE:
        import random; random.seed(42)
        edges = random.sample(edges, EDGE_SAMPLE)

    groups = {"Grande (≥5M sat)":[],"Media (1M-5M sat)":[],"Pequeña (<1M sat)":[],"Deshabilitado":[]}
    for u, v, data in edges:
        if u not in pos3d or v not in pos3d: continue
        x0,y0,z0 = pos3d[u]; x1,y1,z1 = pos3d[v]
        seg = ([x0,x1,None],[y0,y1,None],[z0,z1,None])
        if data.get("disabled"):               groups["Deshabilitado"].append(seg)
        elif data.get("capacity",0) >= 5000000:groups["Grande (≥5M sat)"].append(seg)
        elif data.get("capacity",0) >= 1000000:groups["Media (1M-5M sat)"].append(seg)
        else:                                  groups["Pequeña (<1M sat)"].append(seg)

    clr = {"Grande (≥5M sat)":"rgba(255,215,0,0.6)","Media (1M-5M sat)":"rgba(100,180,255,0.5)",
           "Pequeña (<1M sat)":"rgba(100,255,100,0.35)","Deshabilitado":"rgba(255,60,60,0.4)"}

    log_cb("  Generando visualización 3D...")
    fig = go.Figure()

    for grp, segs in groups.items():
        if not segs: continue
        xs,ys,zs = [],[],[]
        for (x,y,z) in segs: xs+=x; ys+=y; zs+=z
        fig.add_trace(go.Scatter3d(x=xs,y=ys,z=zs,mode="lines",name=grp,
            line=dict(color=clr[grp],width=1),hoverinfo="skip",legendgroup=grp))

    my_idx = node_pks.index(my_pubkey) if my_pubkey and my_pubkey in node_pks else None
    other  = [i for i in range(len(node_pks)) if i != my_idx]

    fig.add_trace(go.Scatter3d(
        x=[node_x[i] for i in other], y=[node_y[i] for i in other],
        z=[node_z[i] for i in other], mode="markers+text", name="Nodos",
        marker=dict(size=[node_sizes[i] for i in other],
                    color=[node_colors[i] for i in other],
                    opacity=0.9, line=dict(width=0.5,color="rgba(255,255,255,0.3)")),
        text=[node_aliases[i] if node_channels[i]>5 else "" for i in other],
        textfont=dict(size=7,color="white"), textposition="top center",
        hovertext=[node_text[i] for i in other], hoverinfo="text"))

    my_annot = []
    if my_idx is not None:
        mx,my_,mz = node_x[my_idx],node_y[my_idx],node_z[my_idx]
        fig.add_trace(go.Scatter3d(
            x=[mx],y=[my_],z=[mz],mode="markers",name="⭐ Mi nodo",
            marker=dict(size=max(14,node_sizes[my_idx]*1.4),color="#FFD700",
                        opacity=1.0,symbol="diamond",line=dict(width=2,color="white")),
            hovertext=[node_text[my_idx]],hoverinfo="text"))
        my_annot = [dict(x=mx,y=my_,z=mz,text=f"<b>◀ {node_aliases[my_idx]}</b>",
            showarrow=True,arrowhead=2,arrowsize=1.5,arrowwidth=1.5,
            arrowcolor="#FFD700",ax=70,ay=-55,
            font=dict(size=11,color="#FFD700"),
            bgcolor="rgba(10,10,30,0.7)",bordercolor="#FFD700",borderwidth=1)]
        log_cb(f"  ⭐ Tu nodo '{node_aliases[my_idx]}' marcado en dorado.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.update_layout(
        title=dict(text=f"<b>⚡ Red Lightning — Visualización 3D</b><br>"
                        f"<sub>{G.number_of_nodes()} nodos · {len(edges)} canales · {now_str}</sub>",
                   x=0.5,xanchor="center",font=dict(size=18,color="white")),
        scene=dict(
            xaxis=dict(showgrid=False,zeroline=False,showticklabels=False,
                       backgroundcolor="rgb(10,10,20)",title=""),
            yaxis=dict(showgrid=False,zeroline=False,showticklabels=False,
                       backgroundcolor="rgb(10,10,20)",title=""),
            zaxis=dict(showgrid=False,zeroline=False,showticklabels=False,
                       backgroundcolor="rgb(10,10,20)",title=""),
            bgcolor="rgb(10,10,20)", annotations=my_annot),
        paper_bgcolor="rgb(8,8,18)", font=dict(color="white"),
        legend=dict(bgcolor="rgba(20,20,40,0.8)",bordercolor="rgba(100,100,150,0.5)",
                    borderwidth=1,font=dict(size=11),
                    title=dict(text="<b>Canales por capacidad</b>")),
        margin=dict(l=0,r=0,t=80,b=0),
        hoverlabel=dict(bgcolor="rgba(20,20,50,0.95)",
                        bordercolor="rgba(100,150,255,0.8)",
                        font=dict(size=12,color="white")),
    )

    node_lookup_js = {}
    for i, pk in enumerate(node_pks):
        al = node_aliases[i]
        entry = {"pk":pk,"alias":al,"x":node_x[i],"y":node_y[i],"z":node_z[i],
                 "ch":node_channels[i],"cap":node_total_cap[i],"days":node_days[i]}
        node_lookup_js[pk]       = entry
        node_lookup_js[pk[:20]]  = entry
        node_lookup_js[al.lower()]= entry
    nl_json = json.dumps(node_lookup_js, ensure_ascii=False)

    SEARCH_JS = f"""
(function() {{
  const NODE_LOOKUP = {nl_json};
  let searchTraceIdx = null;

  // PANEL DE BÚSQUEDA
  const panel = document.createElement('div');
  panel.style.cssText = `position:fixed;top:16px;right:16px;z-index:9999;
    display:flex;flex-direction:column;gap:6px;font-family:monospace;`;
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:6px;align-items:center;';
  const input = document.createElement('input');
  input.type='text'; input.placeholder='🔍 alias o pubkey...';
  input.style.cssText=`background:rgba(10,10,30,0.92);border:1px solid rgba(0,220,255,0.55);
    border-radius:6px;color:#00dcff;font-size:13px;padding:6px 10px;width:220px;outline:none;
    box-shadow:0 0 8px rgba(0,220,255,0.25);`;
  const btn = document.createElement('button'); btn.textContent='Buscar';
  btn.style.cssText=`background:rgba(0,180,255,0.18);border:1px solid rgba(0,220,255,0.55);
    border-radius:6px;color:#00dcff;font-size:13px;padding:6px 12px;cursor:pointer;`;
  const clearBtn = document.createElement('button'); clearBtn.textContent='✕';
  clearBtn.style.cssText=`background:rgba(255,60,60,0.15);border:1px solid rgba(255,100,100,0.5);
    border-radius:6px;color:#ff6666;font-size:13px;padding:6px 10px;cursor:pointer;`;
  const status = document.createElement('div');
  status.style.cssText=`color:rgba(180,220,255,0.85);font-size:11px;padding:4px 8px;
    background:rgba(10,10,30,0.75);border-radius:4px;display:none;`;
  row.appendChild(input); row.appendChild(btn); row.appendChild(clearBtn);
  panel.appendChild(row); panel.appendChild(status);
  document.body.appendChild(panel);

  // PANEL DE LEYENDA Y CONTROLES DE CÁMARA
  const leg = document.createElement('div');
  leg.style.cssText = `position:fixed;bottom:20px;left:20px;z-index:9999;
    display:flex;flex-direction:column;gap:5px;font-family:sans-serif;font-size:12px;
    background:rgba(12,12,35,0.85);border:1px solid rgba(100,150,255,0.4);
    border-radius:8px;padding:12px;color:#ddd;box-shadow:0 8px 16px rgba(0,0,0,0.6);`;
  
  leg.innerHTML = `
    <div style="font-weight:bold;color:#fff;margin-bottom:4px;font-size:13px;">ℹ️ Leyenda de Nodos</div>
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
  `;
  document.body.appendChild(leg);

  // FUNCIONALIDAD DE BÚSQUEDA
  function getGd() {{ return document.querySelector('.js-plotly-plot'); }}
  function removeSearchTrace() {{
    const gd=getGd(); if(!gd||searchTraceIdx===null) return;
    Plotly.deleteTraces(gd,searchTraceIdx); searchTraceIdx=null;
  }}
  function doSearch() {{
    const gd=getGd(); if(!gd) return;
    const q=input.value.trim(); sessionStorage.setItem('savedSearchQuery', q);
    if(!q){{removeSearchTrace();status.style.display='none';return;}}
    const ql=q.toLowerCase();
    let found=NODE_LOOKUP[q]||NODE_LOOKUP[q.slice(0,20)]||NODE_LOOKUP[ql];
    if(!found) for(const [k,v] of Object.entries(NODE_LOOKUP))
      if(k.toLowerCase().includes(ql)&&v.alias){{found=v;break;}}
    removeSearchTrace();
    if(!found){{status.textContent='⚠ Nodo no encontrado.';status.style.color='#ff8888';
      status.style.display='block';return;}}
    const days_s=found.days<9999?found.days+' días':'desc.';
    const cap_s=found.cap?found.cap.toLocaleString()+' sats':'?';
    Plotly.addTraces(gd,{{type:'scatter3d',x:[found.x],y:[found.y],z:[found.z],
      mode:'markers',name:'🔍 Encontrado',
      marker:{{size:18,color:'#00ffed',opacity:1.0,symbol:'diamond',
               line:{{width:2,color:'white'}}}},
      hovertext:['<b>'+found.alias+'</b><br>Pubkey:'+found.pk.slice(0,20)+'...<br>'+
                 'Canales:'+found.ch+'<br>Cap:'+cap_s+'<br>Gossip:'+days_s],
      hoverinfo:'text',showlegend:true}}).then(f=>{{searchTraceIdx=gd.data.length-1;}});
    const cur=gd.layout.scene.annotations||[];
    const cleaned=cur.filter(a=>!a.text.startsWith('<b>🔍'));
    Plotly.relayout(gd,{{'scene.annotations':[...cleaned,{{x:found.x,y:found.y,z:found.z,
      text:'<b>🔍 '+found.alias+'</b>',showarrow:true,arrowhead:2,
      arrowcolor:'#00ffed',ax:-70,ay:55,
      font:{{size:12,color:'#00ffed'}},bgcolor:'rgba(0,30,30,0.8)',
      bordercolor:'#00ffed',borderwidth:1}}]}});
    status.innerHTML='✅ <b>'+found.alias+'</b> | ch:'+found.ch+' | cap:'+cap_s;
    status.style.color='#aaffee'; status.style.display='block';
  }}
  function doClear() {{
    input.value=''; removeSearchTrace(); sessionStorage.removeItem('savedSearchQuery');
    const gd=getGd(); if(gd){{
      const cur=gd.layout.scene.annotations||[];
      Plotly.relayout(gd,{{'scene.annotations':cur.filter(a=>!a.text.startsWith('<b>🔍'))}});
    }}
    status.style.display='none';
  }}
  btn.addEventListener('click',doSearch);
  clearBtn.addEventListener('click',doClear);
  input.addEventListener('keydown',e=>{{if(e.key==='Enter')doSearch();}});

  // AUTO-ROTACIÓN DE CÁMARA
  let isInteracting = false;
  let lastTime = performance.now();
  let rafId = null;

  document.addEventListener('mousedown', () => isInteracting = true);
  document.addEventListener('mouseup', () => isInteracting = false);
  document.addEventListener('touchstart', () => isInteracting = true);
  document.addEventListener('touchend', () => isInteracting = false);
  
  // Rueda del ratón congela la rotación un instante
  let wheelTimer;
  document.addEventListener('wheel', () => {{
    isInteracting = true;
    clearTimeout(wheelTimer);
    wheelTimer = setTimeout(() => isInteracting = false, 1500);
  }});

  function rotateCamera(now) {{
    rafId = requestAnimationFrame(rotateCamera);
    const dt = now - lastTime;
    lastTime = now;
    
    // Evitar saltos si minimizan la pestaña
    if (dt > 100) return;

    const gd = getGd();
    if (!gd || !gd.layout || !gd.layout.scene) return;

    const slider = document.getElementById('camSpeed');
    const speed = slider ? parseFloat(slider.value) : 0;

    // Pausa si el giro está en 0 o el usuario está interactuando (drag/zoom)
    if (speed === 0 || isInteracting) return;
    
    // Obtener cámara actual
    const cam = gd.layout.scene.camera;
    if (!cam || !cam.eye) return;
    
    const rSpeed = speed * -0.00003 * dt; // Dirección y factor escala

    const x = cam.eye.x;
    const y = cam.eye.y;
    const z = cam.eye.z;
    
    const r = Math.sqrt(x*x + y*y);
    if (r < 0.01) return; // evitar glitch en centro
    
    const currentAngle = Math.atan2(y, x);
    const newAngle = currentAngle + rSpeed;
    
    const nextX = r * Math.cos(newAngle);
    const nextY = r * Math.sin(newAngle);
    
    Plotly.relayout(gd, {{
      'scene.camera': {{
        eye: {{x: nextX, y: nextY, z: z}},
        up: cam.up || {{x:0, y:0, z:1}},
        center: cam.center || {{x:0, y:0, z:0}}
      }}
    }});
  }}
  
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

  // Iniciar loops
  startReloadTimer();
  requestAnimationFrame(rotateCamera);
}})();
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(html_path), include_plotlyjs="cdn", post_script=SEARCH_JS)
    log_cb(f"✅ HTML guardado en: {html_path.name}")
    return True
