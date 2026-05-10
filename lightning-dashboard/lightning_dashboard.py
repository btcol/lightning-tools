#!/usr/bin/env python3
"""
lightning_dashboard.py
=========================
Panel interactivo: red Lightning + Cockpit HUD (Heads-Up Display) con estadísticas históricas.
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
        self.title(" Lightning Network Dashboard — Cockpit HUD")
        self.geometry("1150x750")
        self.configure(bg=core.CLR_BG)

        # ── Fuentes base (aliases cortos) ──────────────────────────────────────
        FUI   = core._FONT_UI    # "DejaVu Sans"
        FMONO = core._FONT_MONO  # "DejaVu Sans Mono"

        # ── Tema oscuro (estilos ttk) ──────────────────────────────────────────
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame",
                        background=core.CLR_BG)

        style.configure("TLabel",
                        background=core.CLR_BG,
                        foreground=core.CLR_TEXT,
                        font=(FUI, 11))

        style.configure("TButton",
                        background=core.CLR_PANEL,
                        foreground=core.CLR_ACCENT,
                        font=(FUI, 11, "bold"),
                        relief="flat",
                        borderwidth=0)
        style.map("TButton",
                  background=[("active", "#0d0d2e"), ("pressed", "#050510")],
                  foreground=[("active", core.CLR_ACCENT)])

        style.configure("TNotebook",
                        background=core.CLR_BG,
                        tabmargins=[2, 6, 2, 0])
        style.configure("TNotebook.Tab",
                        background=core.CLR_PANEL,
                        foreground=core.CLR_SUBTEXT,
                        font=(FUI, 11, "bold"),
                        padding=[18, 7])
        style.map("TNotebook.Tab",
                  background=[("selected", "#0d1a2e")],
                  foreground=[("selected", core.CLR_ACCENT)])

        style.configure("Treeview",
                        background=core.CLR_PANEL,
                        foreground=core.CLR_TEXT,
                        fieldbackground=core.CLR_PANEL,
                        rowheight=28,
                        font=(FUI, 11))
        style.map("Treeview",
                  background=[("selected", "#0d1a30")],
                  foreground=[("selected", core.CLR_ACCENT)])
        style.configure("Treeview.Heading",
                        background=core.CLR_BG,
                        foreground=core.CLR_ACCENT,
                        font=(FUI, 11, "bold"))

        style.configure("Header.TLabel",
                        font=(FUI, 15, "bold"),
                        foreground=core.CLR_ACCENT)

        style.configure("TCheckbutton",
                        background=core.CLR_BG,
                        foreground=core.CLR_TEXT,
                        font=(FUI, 11))
        style.map("TCheckbutton",
                  background=[("active", core.CLR_BG)])

        style.configure("TCombobox",
                        background=core.CLR_PANEL,
                        foreground=core.CLR_TEXT,
                        fieldbackground=core.CLR_PANEL,
                        font=(FUI, 11))

        style.configure("TEntry",
                        fieldbackground=core.CLR_PANEL,
                        foreground=core.CLR_TEXT,
                        font=(FUI, 11))

        style.configure("TLabelframe",
                        background=core.CLR_BG,
                        foreground=core.CLR_ACCENT)
        style.configure("TLabelframe.Label",
                        background=core.CLR_BG,
                        foreground=core.CLR_ACCENT,
                        font=(FUI, 10, "bold"))

        style.configure("TSeparator",
                        background=core.CLR_BORDER)

        # ── Barra de estado superior ───────────────────────────────────────────
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill=tk.X, padx=10, pady=6)
        self.lbl_node_info = ttk.Label(
            self.status_frame,
            text="Detectando nodo...",
            font=(FUI, 12, "bold"),
            foreground=core.CLR_GOLD
        )
        self.lbl_node_info.pack(side=tk.LEFT)



        # Notebook (Pestañas)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Crear pestañas
        self.tab_main    = ttk.Frame(self.notebook)
        self.tab_wallet  = ttk.Frame(self.notebook)
        self.tab_peers   = ttk.Frame(self.notebook)
        self.tab_suggest = ttk.Frame(self.notebook)
        self.tab_open    = ttk.Frame(self.notebook)
        self.tab_close   = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_main,    text="Red & Cockpit HUD")
        self.notebook.add(self.tab_wallet,  text="Wallet On-chain")
        self.notebook.add(self.tab_peers,   text="Peers")
        self.notebook.add(self.tab_suggest, text="Rebalanceo")
        self.notebook.add(self.tab_open,    text="Apertura Canales")
        self.notebook.add(self.tab_close,   text="Cierre Canales")

        # Construir cada panel
        self._build_tab_main()
        self._build_tab_wallet()
        self._build_tab_peers()
        self._build_tab_suggest()
        self._build_tab_open()
        self._build_tab_close()


        # Iniciar detección asíncrona del nodo local
        self.my_pubkey = None
        threading.Thread(target=self._detect_node, daemon=True).start()

        # Arrancar colector autónomo de estadísticas históricas
        self._stats_interval_secs = 300  # cada 5 minutos por defecto
        self._start_auto_stats_loop()

        # Arrancar el hilo del piloto automático experimental
        threading.Thread(target=self._auto_rebalance_loop, daemon=True).start()

    def _detect_node(self):
        info = core.get_node_info()
        if info:
            self.my_pubkey = info.get("identity_pubkey", "")
            alias = info.get("alias", "sin_alias")
            height = info.get("block_height", 0)
            # En Tkinter, es seguro modificar widget text desde thread si no es agresivo
            self.lbl_node_info.config(text=f"⭐ Nodo: {alias}  |  Pubkey: {self.my_pubkey[:16]}...  |  Altura: {height}  |  Red: {core.NETWORK}")
        else:
            self.lbl_node_info.config(text="Nodo local no detectado. ¿Está LND en ejecución?")

    # =========================================================================
    # PANEL PRINCIPAL: COCKPIT HUD + RED
    # =========================================================================
    def _build_tab_main(self):
        # ── Fila 1: título + acciones principales ──
        top = ttk.Frame(self.tab_main)
        top.pack(fill=tk.X, pady=(10, 4))

        ttk.Label(top, text="Red & Cockpit HUD", style="Header.TLabel").pack(side=tk.LEFT)

        ttk.Button(top, text="Generar Cockpit",
                   command=self._action_open_cockpit).pack(side=tk.RIGHT, padx=5)

        ttk.Button(top, text="Escanear Red Pública",
                   command=self._action_scan_network).pack(side=tk.RIGHT, padx=5)

        self.var_hops = tk.StringVar(value="2")
        cmb_hops = ttk.Combobox(top, textvariable=self.var_hops,
                                values=["1", "2", "3", "4", "5"], width=3, state="readonly")
        cmb_hops.pack(side=tk.RIGHT, padx=(0, 4))
        ttk.Label(top, text="Saltos:").pack(side=tk.RIGHT)

        self.var_auto_scan = tk.BooleanVar(value=False)
        self.var_auto_scan_secs = tk.StringVar(value="300")
        chk_auto = ttk.Checkbutton(top, text="Auto-Escaneo (s):",
                                   variable=self.var_auto_scan,
                                   command=self._toggle_auto_scan)
        chk_auto.pack(side=tk.LEFT, padx=(20, 4))
        ttk.Entry(top, textvariable=self.var_auto_scan_secs, width=5).pack(side=tk.LEFT)

        # ── Fila 2: barra de stats ──
        stats_bar = ttk.Frame(self.tab_main)
        stats_bar.pack(fill=tk.X, padx=5, pady=(0, 4))

        self.lbl_stats_status = ttk.Label(
            stats_bar, text="Historial: esperando primer snapshot...",
            font=(core._FONT_UI, 10), foreground=core.CLR_SUBTEXT)
        self.lbl_stats_status.pack(side=tk.LEFT)

        self.var_stats_interval = tk.StringVar(value="300")
        ttk.Label(stats_bar, text="| Intervalo stats (s):",
                  font=(core._FONT_UI, 10), foreground=core.CLR_SUBTEXT).pack(side=tk.LEFT)
        ent_stats = ttk.Entry(stats_bar, textvariable=self.var_stats_interval, width=5)
        ent_stats.pack(side=tk.LEFT, padx=(2, 0))
        ent_stats.bind("<Return>", lambda e: self._update_stats_interval())
        ttk.Button(stats_bar, text="▶ Snapshot ahora",
                   command=self._collect_stats_async).pack(side=tk.RIGHT, padx=5)

        # ── Fila 3: grid de métricas ──
        ttk.Separator(self.tab_main, orient='horizontal').pack(fill=tk.X, pady=3)
        metrics_frame = ttk.LabelFrame(
            self.tab_main, text="Métricas Actuales (node_history.db) ", padding=8)
        metrics_frame.pack(fill=tk.X, padx=10, pady=2)

        labels = [
            (" Canales Activos", "cockpit_ch_active"),
            (" Liquidez Local",  "cockpit_liq"),
            (" Capacidad Total", "cockpit_cap"),
            (" Net Profit 7d",   "cockpit_net"),
            (" Fees Ganadas",    "cockpit_earned"),
            (" Fees Pagadas",    "cockpit_paid"),
            (" Zombies",         "cockpit_zombies"),
            (" Uptime 24h",      "cockpit_uptime"),
        ]
        self._cockpit_labels = {}
        for idx, (lbl_txt, key) in enumerate(labels):
            col = (idx % 4) * 2
            row = idx // 4
            ttk.Label(metrics_frame, text=lbl_txt + ":",
                      font=(core._FONT_UI, 10), foreground=core.CLR_SUBTEXT
                      ).grid(row=row, column=col, sticky=tk.E, padx=(10, 3), pady=3)
            val_lbl = ttk.Label(metrics_frame, text="—",
                                font=(core._FONT_UI, 11, "bold"),
                                foreground=core.CLR_ACCENT)
            val_lbl.grid(row=row, column=col + 1, sticky=tk.W, padx=(0, 18), pady=3)
            self._cockpit_labels[key] = val_lbl

        ttk.Button(metrics_frame, text="↺ Refrescar métricas",
                   command=self._cockpit_refresh_metrics
                   ).grid(row=2, column=0, columnspan=8, pady=(4, 0))

        # ── Log ──
        ttk.Separator(self.tab_main, orient='horizontal').pack(fill=tk.X, pady=3)
        self.log_main = scrolledtext.ScrolledText(
            self.tab_main, height=12,
            bg=core.CLR_PANEL, fg=core.CLR_GREEN, font=(core._FONT_MONO, 11))
        self.log_main.pack(fill=tk.BOTH, expand=True, padx=5, pady=4)
        self.log_main.insert(tk.END,
            "Presiona ' Escanear Red Pública' para actualizar el dataset,\n"
            "luego ' Generar Cockpit' para abrir la visualización completa.\n")


        # Cargar métricas al inicio
        self.after(2000, self._cockpit_refresh_metrics)

    def _action_scan_network(self):
        max_hops = int(self.var_hops.get())
        self.log_main.insert(tk.END, f"\n[] Iniciando escaneo de red hasta {max_hops} saltos...\n", "info")
        self.log_main.see(tk.END)
        
        def run_script():
            script = core.SCRIPTS_DIR / "01_scan_network.sh"
            env = os.environ.copy()
            env["MAX_HOPS"] = str(max_hops)
            try:
                proc = subprocess.Popen(["bash", str(script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                for line in proc.stdout:
                    self.log_main.insert(tk.END, line)
                    self.log_main.see(tk.END)
                proc.wait()
                self.log_main.insert(tk.END, f"\n Proceso terminado con código {proc.returncode}\n")
            except Exception as e:
                self.log_main.insert(tk.END, f" Error: {e}\n")
            finally:
                self._collect_stats_async()
        
        threading.Thread(target=run_script, daemon=True).start()

    def _toggle_auto_scan(self):
        if self.var_auto_scan.get():
            self.log_main.insert(tk.END, f"\n[] Auto-escaneo activado cada {self.var_auto_scan_secs.get()} segundos.\n", "info")
            self._auto_scan_loop()
        else:
            self.log_main.insert(tk.END, "\n[⏹] Auto-escaneo desactivado.\n")

    def _auto_scan_loop(self):
        if not self.var_auto_scan.get():
            return

        # 1. Ejecutar escaneo
        max_hops = int(self.var_hops.get())
        self.log_main.insert(tk.END, f"\n[] Auto-escaneo en curso ({datetime.now().strftime('%H:%M:%S')})...\n")
        
        def run_cycle():
            # Escaneo
            script = core.SCRIPTS_DIR / "01_scan_network.sh"
            env = os.environ.copy()
            env["MAX_HOPS"] = str(max_hops)
            try:
                subprocess.run(["bash", str(script)], capture_output=True, env=env)
                
                # Regenerar HTML (silenciosamente)
                def log_dummy(m): pass
                core.generate_3d_html(core.CSV_FILE, core.HTML_FILE, self.my_pubkey, log_dummy)
                
                self.log_main.insert(tk.END, " Ciclo de auto-escaneo completado.\n")
                self.log_main.see(tk.END)
            except Exception as e:
                self.log_main.insert(tk.END, f" Error en auto-escaneo: {e}\n")
            finally:
                # Registrar snapshot de métricas en la BD histórica
                self._collect_stats_async()

            # Programar siguiente ciclo
            try:
                wait_ms = int(self.var_auto_scan_secs.get()) * 1000
                if wait_ms < 10000: wait_ms = 10000 # mínimo 10s para seguridad
                self.after(wait_ms, self._auto_scan_loop)
            except:
                self.after(60000, self._auto_scan_loop)

        threading.Thread(target=run_cycle, daemon=True).start()

    def _collect_stats_async(self):
        """Lanza 04_collect_stats.sh en background y actualiza el indicador de estado."""
        stats_script = core.SCRIPTS_DIR / "04_collect_stats.sh"
        if not stats_script.exists():
            self.lbl_stats_status.config(
                text="Historial: script no encontrado (04_collect_stats.sh)",
                foreground=core.CLR_RED
            )
            return

        def _run():
            self.lbl_stats_status.config(
                text="Historial: recolectando...",
                foreground=core.CLR_YELLOW
            )
            try:
                env = os.environ.copy()
                result = subprocess.run(
                    ["bash", str(stats_script)],
                    capture_output=True, text=True, timeout=60, env=env
                )
                hora = datetime.now().strftime("%H:%M:%S")
                if result.returncode == 0:
                    resumen = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "OK"
                    self.lbl_stats_status.config(
                        text=f" Último snapshot: {hora} — {resumen}",
                        foreground=core.CLR_GREEN
                    )
                    self.log_main.insert(tk.END, f"   {resumen}\n")
                    self.log_main.see(tk.END)

                    # ── Auto-refrescar el cockpit HTML con los datos nuevos ──
                    # skip_graph=True: solo actualiza el JSON de stats, no regenera el 3D
                    cockpit_path = core.EXPORTS_DIR / "lightning_cockpit.html"
                    if cockpit_path.exists():
                        try:
                            core.generate_cockpit_html(
                                cockpit_path=cockpit_path,
                                my_pubkey=self.my_pubkey,
                                log_cb=lambda m: None,  # silencioso
                                skip_graph=True,
                            )
                        except Exception:
                            pass  # no interrumpir el ciclo por un fallo de refresco

                else:
                    err = result.stderr.strip()[:120] if result.stderr.strip() else result.stdout.strip()[:120]
                    self.lbl_stats_status.config(
                        text=f" Stats:  error a las {hora}",
                        foreground=core.CLR_RED
                    )
                    self.log_main.insert(tk.END, f"   Stats error: {err}\n")
            except Exception as e:
                self.lbl_stats_status.config(
                    text=f" Stats: excepción — {e}",
                    foreground=core.CLR_RED
                )
                self.log_main.insert(tk.END, f"   Error colector stats: {e}\n")

        threading.Thread(target=_run, daemon=True).start()



    def _start_auto_stats_loop(self):
        """Inicia el loop autónomo de recolección de estadísticas."""
        # Primer snapshot con pequeño retraso para que LND esté listo
        self.after(5000, self._auto_stats_cycle)

    def _auto_stats_cycle(self):
        """Ciclo periódico autónomo: recolecta stats y se reprograma."""
        self._collect_stats_async()
        try:
            interval_ms = max(30, int(self.var_stats_interval.get())) * 1000
        except (ValueError, AttributeError):
            interval_ms = self._stats_interval_secs * 1000
        self.after(interval_ms, self._auto_stats_cycle)

    def _update_stats_interval(self):
        """Actualiza el intervalo del colector desde el campo de entrada."""
        try:
            secs = max(30, int(self.var_stats_interval.get()))
            self._stats_interval_secs = secs
            self.var_stats_interval.set(str(secs))
            self.log_main.insert(tk.END, f"   Intervalo de stats actualizado a {secs}s\n")
        except ValueError:
            pass

    # =========================================================================

    # =========================================================================
    # PANEL W: WALLET ON-CHAIN
    # =========================================================================
    def _build_tab_wallet(self):
        FUI   = core._FONT_UI
        FMONO = core._FONT_MONO

        top = ttk.Frame(self.tab_wallet)
        top.pack(fill=tk.X, pady=(10, 4))
        ttk.Label(top, text="Wallet On-chain", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="Refrescar Todo",
                   command=self._wallet_refresh_all).pack(side=tk.RIGHT, padx=5)

        # Bloque A: Balance
        bal = ttk.LabelFrame(self.tab_wallet, text=" Balance y Reservas ", padding=10)
        bal.pack(fill=tk.X, padx=6, pady=4)

        row1 = ttk.Frame(bal); row1.pack(fill=tk.X)
        self.lbl_w_conf = ttk.Label(row1, text="Confirmado:  --",
                                    font=(FUI, 12, "bold"), foreground=core.CLR_GREEN)
        self.lbl_w_conf.pack(side=tk.LEFT, padx=(0, 30))
        self.lbl_w_unconf = ttk.Label(row1, text="Sin confirmar:  --",
                                      font=(FUI, 11), foreground=core.CLR_YELLOW)
        self.lbl_w_unconf.pack(side=tk.LEFT, padx=(0, 30))
        self.lbl_w_anchor = ttk.Label(row1, text="Reserva anchor:  --",
                                      font=(FUI, 11), foreground=core.CLR_SUBTEXT)
        self.lbl_w_anchor.pack(side=tk.LEFT)

        row2 = ttk.Frame(bal); row2.pack(fill=tk.X, pady=(4, 0))
        self.lbl_w_pending = ttk.Label(row2, text="",
                                       font=(FUI, 10), foreground=core.CLR_YELLOW)
        self.lbl_w_pending.pack(side=tk.LEFT)
        self.lbl_w_warn = ttk.Label(row2, text="",
                                    font=(FUI, 10, "bold"), foreground=core.CLR_RED)
        self.lbl_w_warn.pack(side=tk.LEFT, padx=(20, 0))

        # Bloque B: Nueva Direccion
        addr_f = ttk.LabelFrame(self.tab_wallet,
                                text=" Nueva Direccion para Recibir Fondos ", padding=10)
        addr_f.pack(fill=tk.X, padx=6, pady=4)

        addr_row = ttk.Frame(addr_f); addr_row.pack(fill=tk.X)
        ttk.Label(addr_row, text="Tipo:").pack(side=tk.LEFT)
        self.var_addr_type = tk.StringVar(value="p2wkh (bech32)")
        cmb_type = ttk.Combobox(addr_row, textvariable=self.var_addr_type,
                                 values=["p2wkh (bech32)", "np2wkh (segwit anidado)", "p2tr (taproot)"],
                                 width=22, state="readonly")
        cmb_type.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Button(addr_row, text="Generar Direccion",
                   command=self._wallet_gen_address).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(addr_row, text="Copiar",
                   command=self._wallet_copy_address).pack(side=tk.LEFT)

        self.var_new_addr = tk.StringVar(value="")
        ttk.Entry(addr_f, textvariable=self.var_new_addr,
                  width=70, font=(FMONO, 11)).pack(fill=tk.X, pady=(6, 0))

        # Bloque C: UTXOs
        utxo_f = ttk.LabelFrame(self.tab_wallet, text=" UTXOs (Fragmentacion) ", padding=8)
        utxo_f.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        cols = ("txid", "idx", "amount", "confs", "tipo")
        self.tree_utxo = ttk.Treeview(utxo_f, columns=cols, show="headings", height=6)
        self.tree_utxo.heading("txid",   text="TXID")
        self.tree_utxo.heading("idx",    text="N")
        self.tree_utxo.heading("amount", text="Monto (sats)")
        self.tree_utxo.heading("confs",  text="Confirmaciones")
        self.tree_utxo.heading("tipo",   text="Tipo")
        self.tree_utxo.column("txid",   width=340)
        self.tree_utxo.column("idx",    width=40,  anchor=tk.CENTER)
        self.tree_utxo.column("amount", width=130, anchor=tk.E)
        self.tree_utxo.column("confs",  width=120, anchor=tk.CENTER)
        self.tree_utxo.column("tipo",   width=160)
        self.tree_utxo.pack(fill=tk.BOTH, expand=True)
        self.tree_utxo.tag_configure("confirmed",   foreground=core.CLR_GREEN)
        self.tree_utxo.tag_configure("unconfirmed", foreground=core.CLR_YELLOW)
        self.tree_utxo.tag_configure("timelocked",  foreground=core.CLR_RED)

        cons_row = ttk.Frame(utxo_f); cons_row.pack(fill=tk.X, pady=(6, 0))
        self.lbl_utxo_summary = ttk.Label(cons_row, text="UTXOs: --",
                                          font=(FUI, 10), foreground=core.CLR_SUBTEXT)
        self.lbl_utxo_summary.pack(side=tk.LEFT)
        ttk.Label(cons_row, text="  Fee rate (sat/vbyte):").pack(side=tk.LEFT, padx=(20, 4))
        self.var_cons_fee = tk.StringVar(value="2")
        ttk.Entry(cons_row, textvariable=self.var_cons_fee, width=5).pack(side=tk.LEFT)
        ttk.Button(cons_row, text="Consolidar UTXOs",
                   command=self._wallet_consolidate).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(cons_row, text="Actualizar lista",
                   command=self._wallet_load_utxos).pack(side=tk.RIGHT)

        # Bloque D: SCB Backup
        scb_f = ttk.LabelFrame(self.tab_wallet,
                               text=" Backup de Canales (SCB) ", padding=10)
        scb_f.pack(fill=tk.X, padx=6, pady=4)

        scb_row = ttk.Frame(scb_f); scb_row.pack(fill=tk.X)
        self.lbl_scb_auto = ttk.Label(scb_row, text="SCB auto LND: buscando...",
                                      font=(FUI, 10), foreground=core.CLR_SUBTEXT)
        self.lbl_scb_auto.pack(side=tk.LEFT)

        scb_row2 = ttk.Frame(scb_f); scb_row2.pack(fill=tk.X, pady=(4, 0))
        self.lbl_scb_manual = ttk.Label(scb_row2, text="Ultimo backup manual: ninguno",
                                        font=(FUI, 10), foreground=core.CLR_SUBTEXT)
        self.lbl_scb_manual.pack(side=tk.LEFT)
        ttk.Button(scb_row2, text="Exportar SCB ahora",
                   command=self._wallet_export_scb).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(scb_row2, text="Abrir carpeta backups",
                   command=self._wallet_open_backups_dir).pack(side=tk.RIGHT)

        # Log
        ttk.Separator(self.tab_wallet, orient='horizontal').pack(fill=tk.X, pady=3)
        self.log_wallet = scrolledtext.ScrolledText(
            self.tab_wallet, height=7,
            bg=core.CLR_PANEL, fg=core.CLR_GREEN, font=(FMONO, 11))
        self.log_wallet.pack(fill=tk.BOTH, expand=False, padx=6, pady=4)
        self.log_wallet.insert(tk.END,
            "Presiona 'Refrescar Todo' para cargar balance y UTXOs.\n"
            "ATENCION: Consolidar UTXOs mueve TODOS los fondos disponibles.\n")

        self.after(1500, self._wallet_refresh_all)
        self.after(1600, self._wallet_update_scb_status)

    # -- Acciones Wallet ------------------------------------------------------

    def _wlog(self, msg):
        self.log_wallet.insert(tk.END, msg + "\n")
        self.log_wallet.see(tk.END)

    def _wallet_refresh_all(self):
        self._wallet_load_balance()
        self._wallet_load_utxos()
        self._wallet_update_scb_status()

    def _wallet_load_balance(self):
        def fetch():
            d = core.get_wallet_balance_detail()
            if d.get("error"):
                self.lbl_w_conf.config(text=f"Error: {d['error'][:40]}")
                return
            conf   = d["confirmed"]
            unconf = d["unconfirmed"]
            anchor = d["reserved_anchor"]
            pclose = d["pending_closing_sats"]
            popen  = d["pending_open_sats"]
            self.lbl_w_conf.config(
                text=f"Confirmado:  {conf:,} sats",
                foreground=core.CLR_GREEN if conf >= core.WALLET_MIN_RESERVE_SATS else core.CLR_RED)
            self.lbl_w_unconf.config(
                text=f"Sin confirmar:  {unconf:,} sats" if unconf else "")
            self.lbl_w_anchor.config(
                text=f"Reserva anchor:  {anchor:,} sats" if anchor else "")
            pending_txt = ""
            if pclose:
                pending_txt += f"  Cerrando canales: {pclose:,} sats bloqueados"
            if popen:
                pending_txt += f"  Abriendo canales: {popen:,} sats"
            self.lbl_w_pending.config(text=pending_txt)
            warn = ""
            if conf < core.WALLET_MIN_RESERVE_SATS:
                warn = f"[!] Saldo bajo -- mantener >= {core.WALLET_MIN_RESERVE_SATS:,} sats para emergencias"
            self.lbl_w_warn.config(text=warn)
        threading.Thread(target=fetch, daemon=True).start()

    def _wallet_load_utxos(self):
        for row in self.tree_utxo.get_children():
            self.tree_utxo.delete(row)
        def fetch():
            utxos = core.get_wallet_utxos(min_confs=0)
            total = sum(u["amount_sat"] for u in utxos)
            for u in utxos:
                confs  = u["confirmations"]
                tipo   = u["address_type"].replace("_", " ").title()
                txid_s = u["txid"][:20] + "..." + u["txid"][-8:] if len(u["txid"]) > 30 else u["txid"]
                tag    = "confirmed" if confs > 0 else "unconfirmed"
                conf_s = str(confs) if confs > 0 else "mempool"
                self.tree_utxo.insert("", tk.END, tags=(tag,), values=(
                    txid_s, u["output_index"], f"{u['amount_sat']:,}", conf_s, tipo))
            n = len(utxos)
            warn = "  [!] Alta fragmentacion: considera consolidar" if n >= core.UTXO_FRAGMENT_WARN else ""
            self.lbl_utxo_summary.config(
                text=f"Total: {n} UTXOs  |  {total:,} sats{warn}",
                foreground=core.CLR_RED if n >= core.UTXO_FRAGMENT_WARN else core.CLR_SUBTEXT)
        threading.Thread(target=fetch, daemon=True).start()

    def _wallet_gen_address(self):
        type_map = {
            "p2wkh (bech32)":          "p2wkh",
            "np2wkh (segwit anidado)": "np2wkh",
            "p2tr (taproot)":          "p2tr",
        }
        addr_type = type_map.get(self.var_addr_type.get(), "p2wkh")
        def fetch():
            addr = core.get_new_address(addr_type)
            if addr:
                self.var_new_addr.set(addr)
                self._wlog(f"Nueva direccion ({addr_type}): {addr}")
            else:
                self._wlog("[!] No se pudo generar la direccion. Verifica que LND este activo.")
        threading.Thread(target=fetch, daemon=True).start()

    def _wallet_copy_address(self):
        addr = self.var_new_addr.get().strip()
        if addr:
            self.clipboard_clear()
            self.clipboard_append(addr)
            self._wlog(f"Direccion copiada: {addr}")
        else:
            self._wlog("[!] Genera una direccion primero.")

    def _wallet_consolidate(self):
        try:
            fee = int(self.var_cons_fee.get().strip())
            if fee <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Fee rate debe ser entero positivo (sat/vbyte).")
            return
        dest = self.var_new_addr.get().strip()
        if not dest:
            messagebox.showerror("Error",
                "Genera primero una nueva direccion de destino.\n"
                "Los fondos consolidados se enviaran a esa direccion.")
            return
        if not messagebox.askyesno("Confirmar Consolidacion",
            f"Esto enviara TODOS los UTXOs a:\n{dest}\n\nFee: {fee} sat/vbyte\n\nContinuar?"):
            return
        self._wlog(f"\nConsolidando UTXOs -> {dest[:20]}...")
        def run():
            ok = core.execute_consolidate_utxos(dest, fee, self._wlog)
            if ok:
                self._wlog("\n[OK] Consolidacion enviada.")
                self.after(5000, self._wallet_refresh_all)
            else:
                self._wlog("\n[!] Fallo la consolidacion.")
        threading.Thread(target=run, daemon=True).start()

    def _wallet_update_scb_status(self):
        import time as _time
        auto_path = core.get_scb_auto_path()
        if auto_path.exists():
            age_h = (_time.time() - auto_path.stat().st_mtime) / 3600
            age_str = f"hace {age_h:.1f}h" if age_h < 24 else f"hace {age_h/24:.1f} dias"
            self.lbl_scb_auto.config(
                text=f"SCB auto LND: {auto_path}  ({age_str})",
                foreground=core.CLR_GREEN if age_h < 24 else core.CLR_YELLOW)
        else:
            self.lbl_scb_auto.config(
                text=f"SCB auto: no encontrado en {auto_path}",
                foreground=core.CLR_RED)
        backups = sorted(core.BACKUPS_DIR.glob("channel_backup_*.bin")) if core.BACKUPS_DIR.exists() else []
        if backups:
            last = backups[-1]
            age_h = (_time.time() - last.stat().st_mtime) / 3600
            age_str = f"hace {age_h:.1f}h" if age_h < 24 else f"hace {age_h/24:.1f} dias"
            self.lbl_scb_manual.config(
                text=f"Ultimo backup manual: {last.name}  ({age_str})",
                foreground=core.CLR_GREEN if age_h < 24 else core.CLR_YELLOW)
        else:
            self.lbl_scb_manual.config(
                text="Ultimo backup manual: ninguno -- exporta uno ahora",
                foreground=core.CLR_RED)

    def _wallet_export_scb(self):
        from datetime import datetime as _dt
        fname = f"channel_backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.bin"
        out_path = core.BACKUPS_DIR / fname
        def run():
            self._wlog(f"\nExportando SCB -> {fname} ...")
            ok = core.export_channel_backup(out_path, self._wlog)
            if ok:
                self._wlog(f"[OK] Backup guardado en: {out_path}")
                self._wallet_update_scb_status()
            else:
                self._wlog("[!] Error al exportar SCB.")
        threading.Thread(target=run, daemon=True).start()

    def _wallet_open_backups_dir(self):
        import subprocess as _sp
        core.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            _sp.Popen(["xdg-open", str(core.BACKUPS_DIR)])
        except Exception as e:
            self._wlog(f"[!] No se pudo abrir el directorio: {e}")

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
        self.tree_sug = ttk.Treeview(self.tab_suggest, columns=cols, show="headings", height=8)
        self.tree_sug.heading("monto", text="MONTO (SATS)")
        self.tree_sug.heading("from_scid", text="FROM SCID")
        self.tree_sug.heading("to_scid", text="TO SCID")
        self.tree_sug.heading("from_peer", text="PEER FROM")
        self.tree_sug.heading("to_peer", text="PEER TO")

        self.tree_sug.column("monto", width=120, anchor=tk.E)
        self.tree_sug.column("from_scid", width=150, anchor=tk.CENTER)
        self.tree_sug.column("to_scid", width=150, anchor=tk.CENTER)
        
        self.tree_sug.pack(fill=tk.X, pady=5)
        
        self.current_suggestions = []
        self.tree_sug.bind("<Double-1>", self._on_suggestion_double_click)
        
        ttk.Label(self.tab_suggest, text="* Doble clic en una fila para rellenar el formulario inferior.", foreground=core.CLR_SUBTEXT).pack(anchor=tk.W)

        ttk.Separator(self.tab_suggest, orient='horizontal').pack(fill=tk.X, pady=10)

        # ── FORMULARIO EJECUTAR REBALANCEO ──
        ttk.Label(self.tab_suggest, text="Control Manual de Rebalanceo", style="Header.TLabel").pack(pady=(0, 0), anchor=tk.W)

        frame_inputs = ttk.Frame(self.tab_suggest)
        frame_inputs.pack(fill=tk.X, pady=5)

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

        btn_row = ttk.Frame(self.tab_suggest)
        btn_row.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_row, text="1. Analizar Rentabilidad", command=self._action_simulate_fee).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="2. EJECUTAR REBALANCEO", command=self._action_execute_reb).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Limpiar Log", command=lambda: self.log_exec.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

        # ── PILOTO AUTOMÁTICO (EXPERIMENTAL) ──
        ttk.Separator(self.tab_suggest, orient='horizontal').pack(fill=tk.X, pady=5)
        
        frame_auto = ttk.Frame(self.tab_suggest)
        frame_auto.pack(fill=tk.X, pady=2)

        self.var_auto_reb = tk.BooleanVar(value=False)
        self.var_auto_interval = tk.StringVar(value="5")

        ttk.Label(frame_auto, text="🤖 Piloto Automático Experimental:", style="Header.TLabel").pack(side=tk.LEFT, padx=(0, 10))

        chk = ttk.Checkbutton(frame_auto, text="Activar (Fondo)", 
                              variable=self.var_auto_reb, command=self._on_auto_reb_toggle)
        chk.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame_auto, text="Intervalo (min):").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Entry(frame_auto, textvariable=self.var_auto_interval, width=4).pack(side=tk.LEFT)

        self.lbl_auto_status = ttk.Label(frame_auto, text="Estado: INACTIVO", foreground=core.CLR_SUBTEXT)
        self.lbl_auto_status.pack(side=tk.RIGHT, padx=5)
        
        ttk.Separator(self.tab_suggest, orient='horizontal').pack(fill=tk.X, pady=(5, 10))

        self.log_exec = scrolledtext.ScrolledText(self.tab_suggest, height=10, bg=core.CLR_BG, fg=core.CLR_TEXT, font=(core._FONT_MONO, 11))
        self.log_exec.pack(fill=tk.BOTH, expand=True, pady=5)

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
            self.log_exec.insert(tk.END, " El fee estimado está dentro del límite.\n")
        else:
            self.log_exec.insert(tk.END, f" AVISO: El fee esperado supera el límite.\n")
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

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando Rebalanceo ")
        logger(f"   FROM {fscid}")
        logger(f"   TO   {tpub[:20]}...")
        logger(f"   AMT  {amt:,} sats\n")

        def run_reb():
            success = core.execute_rebalance(fscid, tpub, amt, fee, logger)
            if success:
                logger("\n[] Operación completada con éxito.")
            else:
                logger("\n[] La operación falló. Ajusta fee o busca otra ruta.")
                
        threading.Thread(target=run_reb, daemon=True).start()

    def _on_auto_reb_toggle(self):
        if self.var_auto_reb.get():
            self.var_amt.set("1000")
            self.var_fee.set("1")
            self.lbl_auto_status.config(text="Estado: ACTIVO", foreground=core.CLR_GREEN)
            self.log_exec.insert(tk.END, f"\n[{datetime.now().strftime('%H:%M:%S')}] [AUTO-PILOTO] Activado. Monto y fee ajustados a 1000 y 1.\n")
            self.log_exec.see(tk.END)
        else:
            self.lbl_auto_status.config(text="Estado: INACTIVO", foreground=core.CLR_SUBTEXT)
            self.log_exec.insert(tk.END, f"\n[{datetime.now().strftime('%H:%M:%S')}] [AUTO-PILOTO] Desactivado.\n")
            self.log_exec.see(tk.END)

    def _auto_rebalance_loop(self):
        import time
        import random
        while True:
            time.sleep(10) # Evalúa cada 10 segundos
            if not getattr(self, 'var_auto_reb', None) or not self.var_auto_reb.get():
                continue
                
            try:
                interval_mins = int(self.var_auto_interval.get())
                if interval_mins <= 0: interval_mins = 1
            except ValueError:
                interval_mins = 5
                
            now = time.time()
            if not hasattr(self, 'last_auto_reb_time'):
                self.last_auto_reb_time = now - (interval_mins * 60) + 10 # Forzar ejecución pronta el primer ciclo
                
            if now - self.last_auto_reb_time < interval_mins * 60:
                continue
                
            self.last_auto_reb_time = now
            
            def logger(msg):
                self.log_exec.insert(tk.END, msg + "\n")
                self.log_exec.see(tk.END)
                
            logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] [AUTO-PILOTO] Iniciando ciclo de tráfico artificial...")
            
            channels = core.get_channels()
            if not channels:
                logger("   [!] No hay canales disponibles.")
                continue
                
            sugs = core.suggest_rebalances(channels)
            if not sugs:
                logger("   [!] No se encontraron rutas de rebalanceo viables.")
                continue
                
            top_sugs = sugs[:10]
            chosen = random.choice(top_sugs)
            
            try:
                amt = int(self.var_amt.get())
                fee = int(self.var_fee.get())
            except ValueError:
                amt, fee = 1000, 1
                
            fscid = chosen["from_scid"]
            tpub  = chosen["to_pub"]
            
            logger(f"   Selección Aleatoria: FROM {fscid} -> TO {tpub[:15]}...")
            
            max_retries = 15
            current_fee = fee
            
            for attempt in range(max_retries):
                logger(f"   [Intento {attempt+1}/{max_retries}] Moviendo {amt:,} sats (max fee: {current_fee:,} sats)")
                success = core.execute_rebalance(fscid, tpub, amt, current_fee, logger)
                
                if success:
                    logger(f"   [AUTO-PILOTO] ✅ Rebalanceo exitoso con fee de {current_fee} sats.")
                    # Actualizar la interfaz para que el próximo ciclo arranque desde este fee
                    self.var_fee.set(str(current_fee))
                    break
                else:
                    logger(f"   [AUTO-PILOTO] ❌ Falló con fee de {current_fee} sats.")
                    if attempt < max_retries - 1:
                        current_fee += 1
                        logger(f"   [AUTO-PILOTO] Incrementando fee a {current_fee} sats y reintentando...")
                    else:
                        logger(f"   [AUTO-PILOTO] ⚠️ Se alcanzó el límite de {max_retries} intentos. Se aborta esta pareja hasta el próximo ciclo.")

    # =========================================================================
    # PANEL E: APERTURA DE CANALES
    # =========================================================================
    def _build_tab_open(self):
        top = ttk.Frame(self.tab_open)
        top.pack(fill=tk.X, pady=10)

        ttk.Label(top, text="Balance de Billetera (Wallet)", style="Header.TLabel").pack(side=tk.LEFT)
        self.lbl_wallet = ttk.Label(top, text="Consultando saldos...",
                                    font=(core._FONT_UI, 12, "bold"), foreground=core.CLR_GREEN)
        self.lbl_wallet.pack(side=tk.LEFT, padx=20)
        ttk.Button(top, text="Refrescar Balance",
                   command=self._action_refresh_wallet).pack(side=tk.RIGHT)

        ttk.Separator(self.tab_open, orient='horizontal').pack(fill=tk.X, pady=5)

        # ── BLOQUE A: Nodo Externo ─────────────────────────────────────────────
        ext_frame = ttk.LabelFrame(
            self.tab_open,
            text="Conectar Nodo Externo (1ml.com / amboss.space) ",
            padding=10
        )
        ext_frame.pack(fill=tk.X, padx=5, pady=(0, 6))

        ttk.Label(ext_frame,
                  text="Pega la URI completa del nodo (pubkey@ip:port):",
                  font=(core._FONT_UI, 10), foreground=core.CLR_SUBTEXT
                  ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))

        self.var_ext_uri = tk.StringVar()
        ent_uri = ttk.Entry(ext_frame, textvariable=self.var_ext_uri, width=78)
        ent_uri.grid(row=1, column=0, sticky=tk.EW, padx=(0, 8))
        ext_frame.columnconfigure(0, weight=1)

        ttk.Button(ext_frame, text="Solo Conectar",
                   command=self._action_connect_only).grid(row=1, column=1, padx=(0, 4))
        ttk.Button(ext_frame, text="Conectar + Abrir Canal",
                   command=self._action_connect_and_open).grid(row=1, column=2)

        ttk.Label(ext_frame,
                  text="Ejemplo: 02ebe2b...9859@54.244.234.100:19996 | Ingresa el monto abajo antes de 'Conectar + Abrir'.",
                  font=(core._FONT_UI, 10), foreground=core.CLR_SUBTEXT
                  ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))

        ttk.Separator(self.tab_open, orient='horizontal').pack(fill=tk.X, pady=5)

        # ── BLOQUE B: Candidatos del grafo ────────────────────────────────────
        frame_cand = ttk.Frame(self.tab_open)
        frame_cand.pack(fill=tk.X, pady=5)
        ttk.Label(frame_cand, text="Candidatos del grafo local (sin canal)",
                  style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(frame_cand, text="Escanear Candidatos",
                   command=self._action_scan_candidates).pack(side=tk.RIGHT)

        frame_filters = ttk.Frame(self.tab_open)
        frame_filters.pack(fill=tk.X, pady=(0, 5))
        
        self.var_min_channels = tk.StringVar(value="2")
        self.var_max_days = tk.StringVar(value="30")
        
        ttk.Label(frame_filters, text="Mín. Canales:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(frame_filters, textvariable=self.var_min_channels, width=8).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(frame_filters, text="Máx. Días Gossip:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(frame_filters, textvariable=self.var_max_days, width=8).pack(side=tk.LEFT)

        cols = ("alias", "pubkey", "channels", "cap", "days")
        self.tree_cand = ttk.Treeview(self.tab_open, columns=cols, show="headings", height=6)
        self.tree_cand.heading("alias",    text="ALIAS")
        self.tree_cand.heading("pubkey",   text="PUBKEY")
        self.tree_cand.heading("channels", text="Nº CANALES")
        self.tree_cand.heading("cap",      text="CAP TOTAL (SATS)")
        self.tree_cand.heading("days",     text="ÚLTIMO GOSSIP")
        self.tree_cand.column("alias",    width=180)
        self.tree_cand.column("pubkey",   width=380)
        self.tree_cand.column("channels", width=90,  anchor=tk.CENTER)
        self.tree_cand.column("cap",      width=140, anchor=tk.E)
        self.tree_cand.column("days",     width=110, anchor=tk.CENTER)
        self.tree_cand.pack(fill=tk.X, pady=5)

        self.current_candidates = []
        self.tree_cand.bind("<Double-1>", self._on_candidate_double_click)
        ttk.Label(self.tab_open,
                  text="* Doble clic para rellenar el campo PUBKEY abajo.",
                  foreground=core.CLR_SUBTEXT).pack(anchor=tk.W)

        # ── BLOQUE C: Formulario monto + botón abrir ──────────────────────────
        frame_inputs = ttk.Frame(self.tab_open)
        frame_inputs.pack(fill=tk.X, pady=(8, 4))

        self.var_open_pubkey = tk.StringVar()
        self.var_open_amt    = tk.StringVar(value="50000")

        ttk.Label(frame_inputs, text="Destino (PUBKEY):").grid(
            row=0, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_open_pubkey, width=70).grid(
            row=0, column=1, sticky=tk.W)

        ttk.Label(frame_inputs, text="Local Amt (sats):").grid(
            row=1, column=0, sticky=tk.E, padx=5, pady=5)
        ttk.Entry(frame_inputs, textvariable=self.var_open_amt, width=20).grid(
            row=1, column=1, sticky=tk.W)

        btn_row = ttk.Frame(self.tab_open)
        btn_row.pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="ABRIR CANAL (grafo local)",
                   command=self._action_open_channel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Limpiar Log",
                   command=lambda: self.log_open.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

        self.log_open = scrolledtext.ScrolledText(
            self.tab_open, height=8,
            bg=core.CLR_BG, fg=core.CLR_TEXT, font=(core._FONT_MONO, 11))
        self.log_open.pack(fill=tk.BOTH, expand=True, pady=4)

        self.after(1000, self._action_refresh_wallet)

    def _action_refresh_wallet(self):
        def fetch():
            data = core.get_wallet_balance()
            conf = data.get("confirmed_balance", 0)
            unconf = data.get("unconfirmed_balance", 0)
            if data:
                self.lbl_wallet.config(text=f"Confirmado: {int(conf):,} sats   |   Sin confirmar: {int(unconf):,} sats")
            else:
                self.lbl_wallet.config(text="No se pudo obtener el saldo.")
        threading.Thread(target=fetch, daemon=True).start()

    def _action_connect_only(self):
        """Establece solo la conexión P2P con el nodo externo (sin abrir canal)."""
        uri = self.var_ext_uri.get().strip()
        if not uri:
            messagebox.showerror("Error", "Ingresa la URI del nodo (pubkey@ip:port).")
            return
        if "@" not in uri:
            messagebox.showerror("Error",
                "Formato incorrecto. Debe ser pubkey@ip:port\n"
                "Ejemplo: 02ebe2b...9859@54.244.234.100:19996")
            return

        def logger(msg):
            self.log_open.insert(tk.END, msg + "\n")
            self.log_open.see(tk.END)

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}]  Conectando a nodo externo...")
        logger(f"   URI: {uri}\n")

        def run():
            ok = core.execute_connect(uri, logger)
            if ok:
                # Auto-rellenar la pubkey para facilitar apertura posterior
                pubkey = uri.split("@")[0]
                self.var_open_pubkey.set(pubkey)
                logger("\n Peer conectado. Pubkey copiada al formulario de apertura.")
            else:
                logger("\n No se pudo conectar. Verifica la URI e intenta de nuevo.")

        threading.Thread(target=run, daemon=True).start()

    def _action_connect_and_open(self):
        """Conecta al nodo externo y abre un canal en un solo paso."""
        uri = self.var_ext_uri.get().strip()
        amt_str = self.var_open_amt.get().strip()

        if not uri:
            messagebox.showerror("Error", "Ingresa la URI del nodo (pubkey@ip:port).")
            return
        if "@" not in uri:
            messagebox.showerror("Error",
                "Formato incorrecto. Debe ser pubkey@ip:port\n"
                "Ejemplo: 02ebe2b...9859@54.244.234.100:19996")
            return
        try:
            amt = int(amt_str)
            if amt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El monto (Local Amt) debe ser un entero positivo.")
            return

        pubkey = uri.split("@")[0]

        def logger(msg):
            self.log_open.insert(tk.END, msg + "\n")
            self.log_open.see(tk.END)

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}]  Conectar + Abrir Canal")
        logger(f"   URI:    {uri}")
        logger(f"   Monto:  {amt:,} sats\n")

        def run():
            success = core.execute_openchannel(pubkey, amt, logger, host_uri=uri)
            if success:
                logger("\n[] Canal en estado pending. ¡Revisa tu lista de peers!")
                self._action_refresh_wallet()
            else:
                logger("\n[] No se pudo abrir el canal. Revisa el log.")

        threading.Thread(target=run, daemon=True).start()

    def _action_scan_candidates(self):

        for row in self.tree_cand.get_children():
            self.tree_cand.delete(row)
            
        try:
            min_c = int(self.var_min_channels.get())
            max_d = int(self.var_max_days.get())
        except ValueError:
            messagebox.showerror("Error", "Mínimo de canales y máximo de días deben ser números enteros.")
            return
            
        def fetch():
            cands = core.get_channel_candidates(min_channels=min_c, max_days=max_d)
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

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando Apertura de Canal ")
        logger(f"   Destino (Pubkey): {pubkey[:20]}...")
        logger(f"   Local Amt: {amt:,} sats\n")

        def run_open():
            success = core.execute_openchannel(pubkey, amt, logger)
            if success:
                logger("\n[] Canal en estado pending. ¡Revisa tu lista de peers pronto!")
                self._action_refresh_wallet()
            else:
                logger("\n[] No se pudo abrir el canal.")
                
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
        
        ttk.Button(btn_row, text="CERRAR CANAL", command=self._action_close_channel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Limpiar Log", command=lambda: self.log_close.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=5)

        self.log_close = scrolledtext.ScrolledText(self.tab_close, height=10, bg=core.CLR_BG, fg=core.CLR_TEXT, font=(core._FONT_MONO, 11))
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

        logger(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando Cierre de Canal {'(FORCE)' if force else ''} ")
        logger(f"   Channel Point: {chanpoint[:25]}...\n")

        def run_close():
            success = core.execute_closechannel(chanpoint, force, logger)
            if success:
                logger("\n[] Comando enviado. El canal pasará a WaitClose.")
                self._action_refresh_close_channels()
            else:
                logger("\n[] No se pudo cerrar el canal.")
                
        threading.Thread(target=run_close, daemon=True).start()

    def _cockpit_refresh_metrics(self):
        """Actualiza los labels de métricas del cockpit leyendo node_history.db."""
        def fetch():
            try:
                stats = core.read_history_stats()
                snap  = stats.get("snap", {})

                def fmt_sat(n):
                    n = int(n or 0)
                    if n >= 1_000_000: return f"{n/1e6:.2f}M sats"
                    if n >= 1_000:     return f"{n/1e3:.1f}k sats"
                    return f"{n} sats"

                def fmt_msat(n):
                    n = int(n or 0)
                    if n >= 1_000_000_000: return f"{n/1e9:.2f}M sat"
                    if n >= 1_000_000:     return f"{n/1e6:.1f}k sat"
                    return f"{n//1000} sat"

                ch_a   = snap.get("channels_active", "—")
                ch_t   = snap.get("channels_total", "?")
                liq    = snap.get("liquidity_ratio", None)
                liq_s  = f"{liq:.1f}%" if liq is not None else "—"
                cap    = fmt_sat(snap.get("capacity_total", 0))
                net7   = stats.get("net_profit_7d_msat", 0)
                net_s  = ("+ " if net7 >= 0 else "- ") + fmt_msat(abs(net7))
                earned = fmt_msat(snap.get("fwd_fees_cum_msat", 0))
                paid   = fmt_msat(snap.get("payments_fees_cum_msat", 0))
                zmb    = snap.get("zombie_channels", "—")
                upt    = f"{stats.get('uptime_pct_7d', 0):.1f}%"

                vals = {
                    "cockpit_ch_active": f"{ch_a} / {ch_t}",
                    "cockpit_liq":       liq_s,
                    "cockpit_cap":       cap,
                    "cockpit_net":       net_s,
                    "cockpit_earned":    earned,
                    "cockpit_paid":      paid,
                    "cockpit_zombies":   str(zmb),
                    "cockpit_uptime":    upt,
                }
                # Colores condicionales
                colors = {
                    "cockpit_net":     core.CLR_GREEN if net7 >= 0 else core.CLR_RED,
                    "cockpit_zombies": core.CLR_YELLOW if int(zmb or 0) > 0 else core.CLR_GREEN,
                }
                for key, lbl in self._cockpit_labels.items():
                    lbl.config(
                        text=vals.get(key, "—"),
                        foreground=colors.get(key, core.CLR_ACCENT)
                    )
            except Exception as e:
                self.log_main.insert(tk.END, f" Error al leer métricas: {e}\n")

        threading.Thread(target=fetch, daemon=True).start()

    def _action_open_cockpit(self):
        """Genera el cockpit HTML y lo abre en el navegador."""
        cockpit_path = core.EXPORTS_DIR / "lightning_cockpit.html"

        def log_ui(msg):
            self.log_main.insert(tk.END, msg + "\n")
            self.log_main.see(tk.END)

        def generate():
            log_ui(f"\n[{datetime.now().strftime('%H:%M:%S')}] Generando Cockpit HUD...")
            ok = core.generate_cockpit_html(
                csv_path=core.CSV_FILE,
                cockpit_path=cockpit_path,
                my_pubkey=self.my_pubkey,
                log_cb=log_ui,
            )
            if ok:
                log_ui(f" Abriendo cockpit en el navegador...")
                try:
                    webbrowser.open(f"file://{cockpit_path.resolve()}")
                    # Refrescar métricas tras generar
                    self._cockpit_refresh_metrics()
                except Exception as e:
                    log_ui(f" No se pudo abrir el navegador: {e}")
            else:
                log_ui(" Error generando el Cockpit. Revisa el log.")

        threading.Thread(target=generate, daemon=True).start()


if __name__ == "__main__":
    app = LightningDashboard()
    app.mainloop()
