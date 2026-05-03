#!/usr/bin/env python3
"""
lightning_dashboard.py
======================
Panel interactivo para visualizar y rebalancear la red Lightning.
Integra la lógica de dashboard_core.py.
"""

import threading
import subprocess
import webbrowser
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

# Importar toda la lógica del núcleo
import dashboard_core as core

class RedirectText:
    """Clase aux para redirigir stdout/stderr a un widget de texto."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.update_idletasks()

    def flush(self):
        pass

class LightningDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ Lightning Network Dashboard")
        self.geometry("1050x700")
        self.configure(bg=core.CLR_BG)

        # Tema oscuro (estilos ttk)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except:
            pass
        
        style.configure("TFrame", background=core.CLR_BG)
        style.configure("TLabel", background=core.CLR_BG, foreground=core.CLR_TEXT, font=("Segoe UI", 10))
        style.configure("TButton", background=core.CLR_PANEL, foreground=core.CLR_TEXT, font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[("active", core.CLR_ACCENT)])
        
        style.configure("TNotebook", background=core.CLR_BG, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background=core.CLR_PANEL, foreground=core.CLR_TEXT, font=("Segoe UI", 10, "bold"), padding=[15, 5])
        style.map("TNotebook.Tab", background=[("selected", core.CLR_ACCENT)], foreground=[("selected", core.CLR_BG)])
        
        style.configure("Treeview", background=core.CLR_PANEL, foreground=core.CLR_TEXT, fieldbackground=core.CLR_PANEL, rowheight=25)
        style.map("Treeview", background=[("selected", core.CLR_ACCENT2)])
        style.configure("Treeview.Heading", background=core.CLR_BG, foreground=core.CLR_TEXT, font=("Segoe UI", 10, "bold"))
        
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground=core.CLR_ACCENT)

        # Barra de estado superior
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_node_info = ttk.Label(self.status_frame, text="Detectando nodo...", font=("Segoe UI", 11, "bold"), foreground=core.CLR_GOLD)
        self.lbl_node_info.pack(side=tk.LEFT)

        # Notebook (Pestañas)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Crear pestañas
        self.tab_network = ttk.Frame(self.notebook)
        self.tab_peers = ttk.Frame(self.notebook)
        self.tab_suggest = ttk.Frame(self.notebook)
        self.tab_execute = ttk.Frame(self.notebook)
        self.tab_open = ttk.Frame(self.notebook)
        self.tab_close = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_network, text="🌐 Red & Vista 3D")
        self.notebook.add(self.tab_peers, text="👥 Peers")
        self.notebook.add(self.tab_suggest, text="⚖️ Sugerencias Rebalanceo")
        self.notebook.add(self.tab_execute, text="🔄 Ejecutar Rebalanceo")
        self.notebook.add(self.tab_open, text="🔌 Apertura Canales")
        self.notebook.add(self.tab_close, text="✂️ Cierre Canales")

        # Construir cada panel
        self._build_tab_network()
        self._build_tab_peers()
        self._build_tab_suggest()
        self._build_tab_execute()
        self._build_tab_open()
        self._build_tab_close()

        # Iniciar detección asíncrona del nodo local
        self.my_pubkey = None
        threading.Thread(target=self._detect_node, daemon=True).start()

    def _detect_node(self):
        info = core.get_node_info()
        if info:
            self.my_pubkey = info.get("identity_pubkey", "")
            alias = info.get("alias", "sin_alias")
            height = info.get("block_height", 0)
            # En Tkinter, es seguro modificar widget text desde thread si no es agresivo
            self.lbl_node_info.config(text=f"⭐ Nodo: {alias}  |  Pubkey: {self.my_pubkey[:16]}...  |  Altura: {height}  |  Red: {core.NETWORK}")
        else:
            self.lbl_node_info.config(text="⚠ Nodo local no detectado. ¿Está LND en ejecución?")

    # =========================================================================
    # PANEL A: RED Y VISTA 3D
    # =========================================================================
    def _build_tab_network(self):
        top = ttk.Frame(self.tab_network)
        top.pack(fill=tk.X, pady=10)
        
        ttk.Label(top, text="Análisis Global de la Red", style="Header.TLabel").pack(side=tk.LEFT)
        
        btn_3d = ttk.Button(top, text="🌍 Generar y Abrir Vista 3D", command=self._action_open_3d)
        btn_3d.pack(side=tk.RIGHT, padx=5)

        btn_scan = ttk.Button(top, text="🔍 Escanear Red Pública (Actualizar)", command=self._action_scan_network)
        btn_scan.pack(side=tk.RIGHT, padx=5)

        self.var_hops = tk.StringVar(value="2")
        cmb_hops = ttk.Combobox(top, textvariable=self.var_hops, values=["1", "2", "3", "4", "5"], width=3, state="readonly")
        cmb_hops.pack(side=tk.RIGHT, padx=(0, 5))
        ttk.Label(top, text="Saltos:").pack(side=tk.RIGHT)

        # Log
        self.log_net = scrolledtext.ScrolledText(self.tab_network, height=25, bg=core.CLR_PANEL, fg=core.CLR_GREEN, font=("Consolas", 10))
        self.log_net.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_net.insert(tk.END, "Presiona 'Escanear Red Pública' para generar el dataset y luego 'Abrir Vista 3D'.\n")

    def _action_scan_network(self):
        max_hops = int(self.var_hops.get())
        self.log_net.insert(tk.END, f"\n[⚙] Iniciando escaneo de red hasta {max_hops} saltos...\n", "info")
        self.log_net.see(tk.END)
        
        def run_script():
            script = core.SCRIPTS_DIR / "01_scan_network.sh"
            env = os.environ.copy()
            env["MAX_HOPS"] = str(max_hops)
            try:
                proc = subprocess.Popen(["bash", str(script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                for line in proc.stdout:
                    self.log_net.insert(tk.END, line)
                    self.log_net.see(tk.END)
                proc.wait()
                self.log_net.insert(tk.END, f"\n✅ Proceso terminado con código {proc.returncode}\n")
            except Exception as e:
                self.log_net.insert(tk.END, f"❌ Error: {e}\n")
        
        threading.Thread(target=run_script, daemon=True).start()

    def _action_open_3d(self):
        def generate():
            def log_ui(msg):
                self.log_net.insert(tk.END, msg + "\n")
                self.log_net.see(tk.END)

            log_ui("\n[⚙] Generando visualización 3D...")
            ok = core.generate_3d_html(core.CSV_FILE, core.HTML_FILE, self.my_pubkey, log_ui)
            if ok:
                log_ui("🌍 Abriendo en el navegador...")
                try:
                    webbrowser.open(f"file://{core.HTML_FILE.resolve()}")
                except Exception as e:
                    log_ui(f"❌ No se pudo abrir navegador: {e}")
        
        threading.Thread(target=generate, daemon=True).start()

    # =========================================================================
    # PANEL B: PEERS
    # =========================================================================
    def _build_tab_peers(self):
        top = ttk.Frame(self.tab_peers)
        top.pack(fill=tk.X, pady=10)
        
        ttk.Label(top, text="Conexiones P2P (Peers)", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="Refrescar Peers", command=self._action_refresh_peers).pack(side=tk.RIGHT)

        cols = ("estado", "pubkey", "address")
        self.tree_peers = ttk.Treeview(self.tab_peers, columns=cols, show="headings", height=20)
        self.tree_peers.heading("estado", text="ESTADO")
        self.tree_peers.heading("pubkey", text="PUBKEY")
        self.tree_peers.heading("address", text="DIRECCIÓN")
        
        self.tree_peers.column("estado", width=120, anchor=tk.CENTER)
        self.tree_peers.column("pubkey", width=450)
        self.tree_peers.column("address", width=300)
        
        self.tree_peers.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tree_peers.tag_configure("CON_CANAL", foreground=core.CLR_GREEN)
        self.tree_peers.tag_configure("SIN_CANAL", foreground=core.CLR_SUBTEXT)

    def _action_refresh_peers(self):
        for row in self.tree_peers.get_children():
            self.tree_peers.delete(row)
        
        def run_script():
            script = core.SCRIPTS_DIR / "02_list_peers.sh"
            try:
                out = subprocess.check_output(["bash", str(script)], text=True)
                for line in out.splitlines():
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) == 3:
                            tag = parts[0]
                            self.tree_peers.insert("", tk.END, values=(parts[0], parts[1], parts[2]), tags=(tag,))
            except Exception as e:
                messagebox.showerror("Error", f"Fallo al listar peers:\n{e}")
                
        threading.Thread(target=run_script, daemon=True).start()

    # =========================================================================
    # PANEL C: SUGERENCIAS REBALANCEO
    # =========================================================================
    def _build_tab_suggest(self):
        top = ttk.Frame(self.tab_suggest)
        top.pack(fill=tk.X, pady=10)
        
        ttk.Label(top, text="Top Candidatos de Rebalanceo", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="Calcular Sugerencias", command=self._action_calc_suggestions).pack(side=tk.RIGHT)

        cols = ("monto", "from_scid", "to_scid", "from_peer", "to_peer")
        self.tree_sug = ttk.Treeview(self.tab_suggest, columns=cols, show="headings", height=20)
        self.tree_sug.heading("monto", text="MONTO (SATS)")
        self.tree_sug.heading("from_scid", text="FROM SCID")
        self.tree_sug.heading("to_scid", text="TO SCID")
        self.tree_sug.heading("from_peer", text="PEER FROM")
        self.tree_sug.heading("to_peer", text="PEER TO")

        self.tree_sug.column("monto", width=120, anchor=tk.E)
        self.tree_sug.column("from_scid", width=150, anchor=tk.CENTER)
        self.tree_sug.column("to_scid", width=150, anchor=tk.CENTER)
        
        self.tree_sug.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.current_suggestions = []
        self.tree_sug.bind("<Double-1>", self._on_suggestion_double_click)
        
        ttk.Label(self.tab_suggest, text="* Doble clic en una fila para enviarla al Panel de Ejecución.", foreground=core.CLR_SUBTEXT).pack(anchor=tk.W)

    def _action_calc_suggestions(self):
        for row in self.tree_sug.get_children():
            self.tree_sug.delete(row)
            
        def fetch():
            channels = core.get_channels()
            if not channels:
                self.bell()
                return
            sugs = core.suggest_rebalances(channels)
            self.current_suggestions = sugs
            
            for s in sugs:
                self.tree_sug.insert("", tk.END, values=(
                    f"{s['amount']:,}",
                    s["from_scid"],
                    s["to_scid"],
                    s["from_peer"],
                    s["to_peer"]
                ))
                
        threading.Thread(target=fetch, daemon=True).start()

    def _on_suggestion_double_click(self, event):
        item = self.tree_sug.selection()
        if not item: return
        idx = self.tree_sug.index(item[0])
        sug = self.current_suggestions[idx]
        
        # Cargar campos en el panel de ejecución
        self.var_from.set(sug["from_scid"])
        self.var_to_scid.set(sug["to_scid"])
        self.var_to_pub.set(sug["to_pub"])
        self.var_amt.set(str(sug["amount"]))
        
        # Saltar al panel D
        self.notebook.select(self.tab_execute)

    # =========================================================================
    # PANEL D: EJECUTAR REBALANCEO
    # =========================================================================
    def _build_tab_execute(self):
        ttk.Label(self.tab_execute, text="Control Manual de Rebalanceo", style="Header.TLabel").pack(pady=(10, 0), anchor=tk.W)

        frame_inputs = ttk.Frame(self.tab_execute)
        frame_inputs.pack(fill=tk.X, pady=10)

        # Variables
        self.var_from = tk.StringVar()
        self.var_to_scid = tk.StringVar()
        self.var_to_pub = tk.StringVar()
        self.var_amt = tk.StringVar(value=str(core.DEFAULT_AMT_SATS))
        self.var_fee = tk.StringVar(value=str(core.DEFAULT_MAX_FEE_SATS))
        self.var_ppm = tk.StringVar(value=str(core.DEFAULT_MAX_FEE_PPM))

        # Cuadrícula
        ttk.Label(frame_inputs, text="FROM SCID:").grid(row=0, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_from, width=20).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(frame_inputs, text="TO SCID (ref):").grid(row=0, column=2, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_to_scid, width=20).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(frame_inputs, text="TO PUBKEY:").grid(row=1, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_to_pub, width=45).grid(row=1, column=1, columnspan=3, sticky=tk.W)

        ttk.Label(frame_inputs, text="Monto (sats):").grid(row=2, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_amt, width=20).grid(row=2, column=1, sticky=tk.W)
        
        ttk.Label(frame_inputs, text="Max Fee (sats):").grid(row=2, column=2, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_fee, width=20).grid(row=2, column=3, sticky=tk.W)

        btn_row = ttk.Frame(self.tab_execute)
        btn_row.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_row, text="1. Analizar Rentabilidad", command=self._action_simulate_fee).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="2. EJECUTAR REBALANCEO", command=self._action_execute_reb).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Limpiar Log", command=lambda: self.log_exec.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

        self.log_exec = scrolledtext.ScrolledText(self.tab_execute, height=20, bg=core.CLR_BG, fg=core.CLR_TEXT, font=("Consolas", 10))
        self.log_exec.pack(fill=tk.BOTH, expand=True, pady=5)

    def _action_simulate_fee(self):
        try:
            amt = int(self.var_amt.get())
            max_fee = int(self.var_fee.get())
            max_ppm = int(self.var_ppm.get())
        except ValueError:
            messagebox.showerror("Error", "Los valores de monto y fee deben ser enteros.")
            return

        res = core.fee_analysis(amt, max_fee, max_ppm)
        if not res: return
        
        self.log_exec.insert(tk.END, f"\n--- Análisis de Rentabilidad ({amt:,} sats) ---\n", "info")
        self.log_exec.insert(tk.END, f"Fee Limit Configurado: {max_fee:,} sats\n")
        self.log_exec.insert(tk.END, f"PPM si pagas el máximo: {res['fee_ppm_if_max']:.0f} ppm\n")
        self.log_exec.insert(tk.END, f"Fee esperado @ {max_ppm} ppm: {res['fee_estimado']:.1f} sats\n")
        
        if res["ok"]:
            self.log_exec.insert(tk.END, "✅ El fee estimado está dentro del límite.\n")
        else:
            self.log_exec.insert(tk.END, f"⚠ AVISO: El fee esperado supera el límite.\n")
        self.log_exec.see(tk.END)

    def _action_execute_reb(self):
        fscid = self.var_from.get().strip()
        tpub  = self.var_to_pub.get().strip()
        try:
            amt = int(self.var_amt.get())
            fee = int(self.var_fee.get())
        except ValueError:
            messagebox.showerror("Error", "Monto y fee deben ser enteros.")
            return

        if not fscid or not tpub:
            messagebox.showerror("Error", "Falta FROM_SCID o TO_PUBKEY.")
            return
            
        if amt <= 0 or fee <= 0:
            messagebox.showerror("Error", "Valores deben ser positivos.")
            return

        def logger(msg):
            self.log_exec.insert(tk.END, msg + "\n")
            self.log_exec.see(tk.END)

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando Rebalanceo 🚀")
        logger(f"   FROM {fscid}")
        logger(f"   TO   {tpub[:20]}...")
        logger(f"   AMT  {amt:,} sats\n")

        def run_reb():
            success = core.execute_rebalance(fscid, tpub, amt, fee, logger)
            if success:
                logger("\n[⚡] Operación completada con éxito.")
            else:
                logger("\n[❌] La operación falló. Ajusta fee o busca otra ruta.")
                
        threading.Thread(target=run_reb, daemon=True).start()

    # =========================================================================
    # PANEL E: APERTURA DE CANALES
    # =========================================================================
    def _build_tab_open(self):
        top = ttk.Frame(self.tab_open)
        top.pack(fill=tk.X, pady=10)
        
        ttk.Label(top, text="Balance de Billetera (Wallet)", style="Header.TLabel").pack(side=tk.LEFT)
        self.lbl_wallet = ttk.Label(top, text="Consultando saldos...", font=("Segoe UI", 11, "bold"), foreground=core.CLR_GREEN)
        self.lbl_wallet.pack(side=tk.LEFT, padx=20)
        
        ttk.Button(top, text="Refrescar Balance", command=self._action_refresh_wallet).pack(side=tk.RIGHT)

        ttk.Separator(self.tab_open, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # Opciones para tabla de candidatos
        frame_cand = ttk.Frame(self.tab_open)
        frame_cand.pack(fill=tk.X, pady=5)
        ttk.Label(frame_cand, text="Candidatos a nuevos pares (Top saludables sin canal)", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(frame_cand, text="Escanear Candidatos", command=self._action_scan_candidates).pack(side=tk.RIGHT)

        cols = ("alias", "pubkey", "channels", "cap", "days")
        self.tree_cand = ttk.Treeview(self.tab_open, columns=cols, show="headings", height=10)
        self.tree_cand.heading("alias", text="ALIAS")
        self.tree_cand.heading("pubkey", text="PUBKEY")
        self.tree_cand.heading("channels", text="Nº CANALES")
        self.tree_cand.heading("cap", text="CAP TOTAL (SATS)")
        self.tree_cand.heading("days", text="ÚLTIMO GOSSIP")

        self.tree_cand.column("alias", width=200)
        self.tree_cand.column("pubkey", width=400)
        self.tree_cand.column("channels", width=100, anchor=tk.CENTER)
        self.tree_cand.column("cap", width=150, anchor=tk.E)
        self.tree_cand.column("days", width=120, anchor=tk.CENTER)
        
        self.tree_cand.pack(fill=tk.X, pady=5)
        
        self.current_candidates = []
        self.tree_cand.bind("<Double-1>", self._on_candidate_double_click)
        ttk.Label(self.tab_open, text="* Doble clic en una fila para rellenar formulario de apertura.", foreground=core.CLR_SUBTEXT).pack(anchor=tk.W)

        # Formulario de apertura
        frame_inputs = ttk.Frame(self.tab_open)
        frame_inputs.pack(fill=tk.X, pady=10)

        self.var_open_pubkey = tk.StringVar()
        self.var_open_amt = tk.StringVar(value="50000")

        ttk.Label(frame_inputs, text="Destino (PUBKEY):").grid(row=0, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_open_pubkey, width=70).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(frame_inputs, text="Local Amt (sats):").grid(row=1, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_open_amt, width=20).grid(row=1, column=1, sticky=tk.W)

        btn_row = ttk.Frame(self.tab_open)
        btn_row.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_row, text="3. ABRIR CANAL", command=self._action_open_channel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Limpiar Log", command=lambda: self.log_open.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

        self.log_open = scrolledtext.ScrolledText(self.tab_open, height=10, bg=core.CLR_BG, fg=core.CLR_TEXT, font=("Consolas", 10))
        self.log_open.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Fetch balance on start
        self.after(1000, self._action_refresh_wallet)

    def _action_refresh_wallet(self):
        def fetch():
            data = core.get_wallet_balance()
            conf = data.get("confirmed_balance", 0)
            unconf = data.get("unconfirmed_balance", 0)
            if data:
                self.lbl_wallet.config(text=f"Confirmado: {int(conf):,} sats   |   Sin confirmar: {int(unconf):,} sats")
            else:
                self.lbl_wallet.config(text="⚠ No se pudo obtener el saldo.")
        threading.Thread(target=fetch, daemon=True).start()

    def _action_scan_candidates(self):
        for row in self.tree_cand.get_children():
            self.tree_cand.delete(row)
            
        def fetch():
            cands = core.get_channel_candidates(min_channels=3, max_days=30)
            self.current_candidates = cands
            if not cands:
                messagebox.showinfo("Candidatos", "No se encontraron candidatos generados. Ejecuta 'Escanear Red Pública' en la Pestaña 1 primero.")
                return
            
            for c in cands:
                days_txt = f"hace {c['days_ago']} d" if c['days_ago'] < 9999 else "nunca"
                self.tree_cand.insert("", tk.END, values=(
                    c["alias"],
                    c["pubkey"],
                    c["channels"],
                    f"{c['capacity']:,}",
                    days_txt
                ))
                
        threading.Thread(target=fetch, daemon=True).start()

    def _on_candidate_double_click(self, event):
        item = self.tree_cand.selection()
        if not item: return
        idx = self.tree_cand.index(item[0])
        cand = self.current_candidates[idx]
        self.var_open_pubkey.set(cand["pubkey"])

    def _action_open_channel(self):
        pubkey = self.var_open_pubkey.get().strip()
        amt_str = self.var_open_amt.get().strip()
        
        if not pubkey:
            messagebox.showerror("Error", "Falta la PUBKEY del nodo destino.")
            return
            
        try:
            amt = int(amt_str)
            if amt <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El monto de fondos (sats) debe ser entero positivo.")
            return
            
        def logger(msg):
            self.log_open.insert(tk.END, msg + "\n")
            self.log_open.see(tk.END)

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando Apertura de Canal 🔌")
        logger(f"   Destino (Pubkey): {pubkey[:20]}...")
        logger(f"   Local Amt: {amt:,} sats\n")

        def run_open():
            success = core.execute_openchannel(pubkey, amt, logger)
            if success:
                logger("\n[⚡] Canal en estado pending. ¡Revisa tu lista de peers pronto!")
                self._action_refresh_wallet()
            else:
                logger("\n[❌] No se pudo abrir el canal.")
                
        threading.Thread(target=run_open, daemon=True).start()

    # =========================================================================
    # PANEL F: CIERRE DE CANALES
    # =========================================================================
    def _build_tab_close(self):
        top = ttk.Frame(self.tab_close)
        top.pack(fill=tk.X, pady=10)
        
        ttk.Label(top, text="Gestión de Cierre de Canales", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="Refrescar Canales", command=self._action_refresh_close_channels).pack(side=tk.RIGHT)

        cols = ("alias", "pubkey", "status", "local", "remote", "chanpoint")
        self.tree_close = ttk.Treeview(self.tab_close, columns=cols, show="headings", height=10)
        self.tree_close.heading("alias", text="ALIAS")
        self.tree_close.heading("pubkey", text="PUBKEY")
        self.tree_close.heading("status", text="ESTADO")
        self.tree_close.heading("local", text="LOCAL (SATS)")
        self.tree_close.heading("remote", text="REMOTE (SATS)")
        self.tree_close.heading("chanpoint", text="CHANNEL POINT")

        self.tree_close.column("alias", width=150)
        self.tree_close.column("pubkey", width=200)
        self.tree_close.column("status", width=100, anchor=tk.CENTER)
        self.tree_close.column("local", width=120, anchor=tk.E)
        self.tree_close.column("remote", width=120, anchor=tk.E)
        self.tree_close.column("chanpoint", width=250)
        
        self.tree_close.pack(fill=tk.X, pady=5)
        
        self.current_close_channels = []
        self.tree_close.bind("<Double-1>", self._on_close_candidate_double_click)
        ttk.Label(self.tab_close, text="* Doble clic en una fila para rellenar formulario de cierre.", foreground=core.CLR_SUBTEXT).pack(anchor=tk.W)

        # Formulario de cierre
        frame_inputs = ttk.Frame(self.tab_close)
        frame_inputs.pack(fill=tk.X, pady=10)

        self.var_close_chanpoint = tk.StringVar()
        self.var_close_force = tk.BooleanVar(value=False)

        ttk.Label(frame_inputs, text="Channel Point (TXID:IDX):").grid(row=0, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_close_chanpoint, width=70).grid(row=0, column=1, sticky=tk.W)

        ttk.Checkbutton(frame_inputs, text="Force Close (Unilateral)", variable=self.var_close_force).grid(row=1, column=1, sticky=tk.W, pady=5)

        btn_row = ttk.Frame(self.tab_close)
        btn_row.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_row, text="✂️ CERRAR CANAL", command=self._action_close_channel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Limpiar Log", command=lambda: self.log_close.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

        self.log_close = scrolledtext.ScrolledText(self.tab_close, height=10, bg=core.CLR_BG, fg=core.CLR_TEXT, font=("Consolas", 10))
        self.log_close.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.after(1500, self._action_refresh_close_channels)

    def _action_refresh_close_channels(self):
        for row in self.tree_close.get_children():
            self.tree_close.delete(row)
            
        def fetch():
            chans = core.get_all_channels()
            self.current_close_channels = chans
            
            for c in chans:
                self.tree_close.insert("", tk.END, values=(
                    c["alias"],
                    c["pubkey"][:16] + "...",
                    c["status"],
                    f"{c['local']:,}",
                    f"{c['remote']:,}",
                    c["chan_point"]
                ))
                
        threading.Thread(target=fetch, daemon=True).start()

    def _on_close_candidate_double_click(self, event):
        item = self.tree_close.selection()
        if not item: return
        idx = self.tree_close.index(item[0])
        cand = self.current_close_channels[idx]
        self.var_close_chanpoint.set(cand["chan_point"])

    def _action_close_channel(self):
        chanpoint = self.var_close_chanpoint.get().strip()
        force = self.var_close_force.get()
        
        if not chanpoint:
            messagebox.showerror("Error", "Falta el Channel Point del canal a cerrar.")
            return
            
        if force:
            ans = messagebox.askyesno("Confirmar Force Close", "ATENCIÓN: Un force close bloqueará tus fondos por un tiempo y puede requerir más comisiones.\n\n¿Estás seguro de forzar el cierre de este canal?")
            if not ans: return
            
        def logger(msg):
            self.log_close.insert(tk.END, msg + "\n")
            self.log_close.see(tk.END)

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando Cierre de Canal {'(FORCE)' if force else ''} ✂️")
        logger(f"   Channel Point: {chanpoint[:25]}...\n")

        def run_close():
            success = core.execute_closechannel(chanpoint, force, logger)
            if success:
                logger("\n[⚡] Comando enviado. El canal pasará a WaitClose.")
                self._action_refresh_close_channels()
            else:
                logger("\n[❌] No se pudo cerrar el canal.")
                
        threading.Thread(target=run_close, daemon=True).start()

if __name__ == "__main__":
    app = LightningDashboard()
    app.mainloop()
