#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ðŸš€ LANZADOR LICITACIONES MERCADO PÃšBLICO
Interfaz grÃ¡fica para ejecutar el pipeline de licitaciones MP
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import threading
import os
from pathlib import Path
import time

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.verificador_entorno import VerificadorEntorno  # noqa: E402


class LanzadorLicitaciones:

    # â”€â”€ Paleta de colores â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    C_AZUL      = "#1565C0"
    C_AZUL_OSC  = "#0D47A1"
    C_VERDE     = "#2E7D32"
    C_ROJO      = "#C62828"
    C_NARANJA   = "#E65100"
    C_FONDO     = "#F0F2F5"
    C_CARD      = "#FFFFFF"
    C_TEXTO     = "#212121"
    C_GRIS_SUB  = "#757575"

    ETAPAS = [
        ("0", "Descarga"),
        ("1", "AuditorÃ­a"),
        ("2", "Filtrado"),
        ("3", "Enriquec."),
        ("4", "Reporte"),
        ("5", "Incremental"),
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MP â€” Licitaciones Mercado PÃºblico")
        self.root.geometry("680x820")
        self.root.resizable(False, False)
        self.root.configure(bg=self.C_FONDO)

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()  // 2) - 340
        y = (self.root.winfo_screenheight() // 2) - 390
        self.root.geometry(f"680x820+{x}+{y}")

        self._verificador  = VerificadorEntorno(Path(__file__).parent)
        self._frame_checks: tk.Frame | None = None
        self._etapa_labels: list[tk.Label] = []
        self.proceso_activo = False
        self._proceso_actual: "subprocess.Popen | None" = None
        self._proceso_detenido = False

        self.root.protocol("WM_DELETE_WINDOW", self.salir)
        self._setup_ui()
        self._actualizar_checks()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ SETUP UI â”€

    def _setup_ui(self):
        # 1. BANNER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        banner = tk.Frame(self.root, bg=self.C_AZUL, height=84)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)

        tk.Label(banner,
                 text="ðŸ›ï¸  MP CONSULTING",
                 font=("Arial", 20, "bold"),
                 fg="white", bg=self.C_AZUL
                 ).pack(anchor=tk.W, padx=24, pady=(16, 0))
        tk.Label(banner,
                 text="Sistema de Licitaciones â€” Mercado PÃºblico Chile",
                 font=("Arial", 10),
                 fg="#BBDEFB", bg=self.C_AZUL
                 ).pack(anchor=tk.W, padx=27)

        # 2. BODY â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        body = tk.Frame(self.root, bg=self.C_FONDO, padx=20, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        # 2a. CARD ESTADO ENTORNO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._frame_checks = tk.Frame(
            body, bg=self.C_CARD,
            highlightthickness=1, highlightbackground="#D0D0D0")
        self._frame_checks.pack(fill=tk.X, pady=(0, 12))

        # 2b. BOTONES PRINCIPALES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        btn_row = tk.Frame(body, bg=self.C_FONDO)
        btn_row.pack(fill=tk.X, pady=(0, 10))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.btn_completo = tk.Button(
            btn_row,
            text="ðŸš€  PIPELINE COMPLETO",
            font=("Arial", 11, "bold"),
            bg=self.C_AZUL, fg="white",
            activebackground=self.C_AZUL_OSC, activeforeground="white",
            height=2, relief=tk.FLAT, cursor="hand2",
            command=self.ejecutar_pipeline_completo)
        self.btn_completo.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        self.btn_incremental = tk.Button(
            btn_row,
            text="ðŸ“Š  SOLO INCREMENTAL",
            font=("Arial", 11, "bold"),
            bg=self.C_VERDE, fg="white",
            activebackground="#1B5E20", activeforeground="white",
            height=2, relief=tk.FLAT, cursor="hand2",
            command=self.ejecutar_solo_incremental)
        self.btn_incremental.grid(row=0, column=1, sticky=tk.EW, padx=(5, 0))

        self.btn_detener = tk.Button(
            body,
            text="\u23f9  DETENER PROCESO",
            font=("Arial", 10, "bold"),
            bg="#616161", fg="white",
            activebackground=self.C_ROJO, activeforeground="white",
            height=1, relief=tk.FLAT, cursor="hand2",
            state=tk.DISABLED,
            command=self.detener_proceso)
        self.btn_detener.pack(fill=tk.X, pady=(0, 6))

        # 2c. TRACKER DE ETAPAS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        etapa_card = tk.Frame(
            body, bg=self.C_CARD,
            highlightthickness=1, highlightbackground="#D0D0D0")
        etapa_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(etapa_card, text="Progreso de ejecuciÃ³n",
                 font=("Arial", 8, "bold"),
                 fg=self.C_GRIS_SUB, bg=self.C_CARD
                 ).pack(anchor=tk.W, padx=12, pady=(7, 2))

        etapa_row = tk.Frame(etapa_card, bg=self.C_CARD)
        etapa_row.pack(fill=tk.X, padx=16, pady=(0, 10))

        self._etapa_labels = []
        for i, (num, nombre) in enumerate(self.ETAPAS):
            col = tk.Frame(etapa_row, bg=self.C_CARD)
            col.pack(side=tk.LEFT, expand=True)

            lbl = tk.Label(col, text=num,
                           font=("Arial", 10, "bold"),
                           fg="#9E9E9E", bg="#E8E8E8",
                           width=3, height=1, relief=tk.FLAT)
            lbl.pack()
            tk.Label(col, text=nombre,
                     font=("Arial", 7), fg="#9E9E9E", bg=self.C_CARD,
                     wraplength=72).pack()
            self._etapa_labels.append(lbl)

            if i < len(self.ETAPAS) - 1:
                tk.Label(etapa_row, text="â€º",
                         font=("Arial", 16, "bold"),
                         fg="#BDBDBD", bg=self.C_CARD
                         ).pack(side=tk.LEFT, pady=(0, 14))

        # 2d. BARRA ESTADO + PROGRESO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        estado_row = tk.Frame(body, bg=self.C_FONDO)
        estado_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(estado_row, text="Estado:",
                 font=("Arial", 9, "bold"),
                 fg=self.C_TEXTO, bg=self.C_FONDO).pack(side=tk.LEFT)

        self.lbl_estado = tk.Label(estado_row,
                                    text="âœ… Sistema listo",
                                    font=("Arial", 9),
                                    fg=self.C_VERDE, bg=self.C_FONDO)
        self.lbl_estado.pack(side=tk.LEFT, padx=6)

        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(2, 8))

        # 2e. LOG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        tk.Label(body, text="Log de ejecuciÃ³n",
                 font=("Arial", 9, "bold"),
                 fg=self.C_TEXTO, bg=self.C_FONDO).pack(anchor=tk.W)

        log_outer = tk.Frame(body, bg="#1E1E1E",
                              highlightthickness=1,
                              highlightbackground="#3C3C3C")
        log_outer.pack(fill=tk.BOTH, expand=True, pady=(4, 10))

        self.text_log = tk.Text(
            log_outer,
            font=("Consolas", 9),
            bg="#1E1E1E", fg="#D4D4D4",
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=8, pady=6,
            wrap=tk.WORD)

        self.text_log.tag_config("ts",      foreground="#6A9955")
        self.text_log.tag_config("default", foreground="#D4D4D4")
        self.text_log.tag_config("ok",      foreground="#4EC9B0")
        self.text_log.tag_config("exito",   foreground="#4EC9B0",
                                  font=("Consolas", 9, "bold"))
        self.text_log.tag_config("error",   foreground="#F44747")
        self.text_log.tag_config("warn",    foreground="#CE9178")
        self.text_log.tag_config("etapa",   foreground="#569CD6",
                                  font=("Consolas", 9, "bold"))

        sb = ttk.Scrollbar(log_outer, orient=tk.VERTICAL,
                            command=self.text_log.yview)
        self.text_log.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 2f. BOTONES INFERIORES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        bottom = tk.Frame(body, bg=self.C_FONDO)
        bottom.pack(fill=tk.X)

        self.btn_resultados = tk.Button(
            bottom,
            text="ðŸ“‚  Abrir carpeta de resultados",
            font=("Arial", 9),
            bg="#455A64", fg="white",
            activebackground="#263238", activeforeground="white",
            relief=tk.FLAT, cursor="hand2", padx=10, pady=5,
            command=self.abrir_carpeta_resultados)
        self.btn_resultados.pack(side=tk.LEFT)

        self.btn_salir = tk.Button(
            bottom,
            text="âœ•  Salir",
            font=("Arial", 9),
            bg=self.C_ROJO, fg="white",
            activebackground="#B71C1C", activeforeground="white",
            relief=tk.FLAT, cursor="hand2", padx=10, pady=5,
            command=self.salir)
        self.btn_salir.pack(side=tk.RIGHT)

        self.agregar_log("ðŸŽ¯ Sistema de licitaciones MP iniciado")
        self.agregar_log("ðŸ’¡ Selecciona una opciÃ³n para comenzar")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ CHECKS PANEL â”€â”€â”€â”€

    def _actualizar_checks(self) -> None:
        if self._frame_checks is None:
            return
        for w in self._frame_checks.winfo_children():
            w.destroy()

        resultados = self._verificador.verificar_todo()

        fila = tk.Frame(self._frame_checks, bg=self.C_CARD)
        fila.pack(fill=tk.X, padx=12, pady=(8, 2))

        for i, r in enumerate(resultados):
            if r.ok:
                icono, fg = "âœ…", self.C_VERDE
            elif r.critico:
                icono, fg = "âŒ", self.C_ROJO
            else:
                icono, fg = "âš ï¸", self.C_NARANJA

            cell = tk.Frame(fila, bg=self.C_CARD)
            cell.grid(row=0, column=i, padx=8, sticky=tk.W)
            tk.Label(cell, text=icono,
                     font=("Arial", 11), bg=self.C_CARD).pack(side=tk.LEFT)
            tk.Label(cell, text=r.nombre,
                     font=("Arial", 8, "bold"),
                     fg=fg, bg=self.C_CARD).pack(side=tk.LEFT, padx=(2, 0))

        tk.Button(
            self._frame_checks,
            text="ðŸ”„ Re-verificar",
            font=("Arial", 8),
            bg="#E3F2FD", fg=self.C_AZUL,
            relief=tk.FLAT, cursor="hand2", padx=6,
            command=self._actualizar_checks,
        ).pack(anchor=tk.E, padx=12, pady=(2, 6))

        hay_error = self._verificador.hay_errores_criticos(resultados)
        estado = tk.DISABLED if hay_error else tk.NORMAL
        self.btn_completo.config(state=estado)
        self.btn_incremental.config(state=estado)
        if hay_error:
            self.actualizar_estado("âš ï¸ ConfiguraciÃ³n incompleta â€” revisa el panel", self.C_ROJO)
        else:
            self.actualizar_estado("âœ… Sistema listo para ejecutar", self.C_VERDE)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ LOG â”€â”€â”€â”€â”€

    def _tag_para_linea(self, texto: str) -> str:
        t = texto.lower()
        if any(x in t for x in ("error", "âŒ", "fallo", "failed", "exception", "traceback")):
            return "error"
        if any(x in t for x in ("warning", "warn", "âš ", "advertencia")):
            return "warn"
        if any(x in t for x in ("âœ…", "completad", "Ã©xito", "exito", "success", "ðŸŽ‰", "[ok]")):
            return "exito"
        if any(x in t for x in ("etapa", "stage", "â–º", "â–¶", "iniciando", "ejecutando etapa")):
            return "etapa"
        return "default"

    def agregar_log(self, mensaje: str):
        self.text_log.config(state=tk.NORMAL)
        # Si la lÃ­nea ya trae timestamp del logger (ej: "12:49:00 | INFO |") no aÃ±adir otro
        import re as _re
        tiene_ts = bool(_re.match(r'^\d{2}:\d{2}:\d{2}', mensaje)
                        or _re.match(r'^\d{4}-\d{2}-\d{2}', mensaje))
        if not tiene_ts:
            self.text_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] ", "ts")
        self.text_log.insert(tk.END, mensaje + "\n", self._tag_para_linea(mensaje))
        self.text_log.see(tk.END)
        self.text_log.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def actualizar_estado(self, mensaje: str, color: str = "black"):
        self.lbl_estado.config(text=mensaje, fg=color)
        self.root.update_idletasks()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ ETAPA TRACKER â”€â”€â”€â”€

    def _set_etapa(self, idx: int, estado: str):
        estilos = {
            "pending": ("#9E9E9E", "#E8E8E8"),
            "running": ("white",   self.C_AZUL),
            "done":    ("white",   self.C_VERDE),
            "error":   ("white",   self.C_ROJO),
        }
        fg, bg = estilos.get(estado, estilos["pending"])
        if 0 <= idx < len(self._etapa_labels):
            self._etapa_labels[idx].config(fg=fg, bg=bg)
            self.root.update_idletasks()

    def _reset_etapas(self):
        for i in range(len(self._etapa_labels)):
            self._set_etapa(i, "pending")

    def _detectar_etapa(self, linea: str) -> int | None:
        l = linea.lower()
        for i, (num, nombre) in enumerate(self.ETAPAS):
            if f"etapa {num}" in l or f"etapa{num}" in l:
                return i
        return None

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ PROCESO â”€â”€â”€â”€â”€

    def deshabilitar_botones(self):
        self.btn_completo.config(state=tk.DISABLED)
        self.btn_incremental.config(state=tk.DISABLED)
        self.btn_detener.config(state=tk.NORMAL, bg=self.C_ROJO)
        self.progress.start(12)
        self.proceso_activo = True

    def habilitar_botones(self):
        self.btn_completo.config(state=tk.NORMAL)
        self.btn_incremental.config(state=tk.NORMAL)
        self.btn_detener.config(state=tk.DISABLED, bg="#616161")
        self.progress.stop()
        self.proceso_activo = False

    def detener_proceso(self):
        """Termina el proceso en ejecucion de forma segura."""
        if self._proceso_actual and self._proceso_actual.poll() is None:
            self._proceso_detenido = True
            try:
                self._proceso_actual.terminate()
            except OSError:
                pass
            self.agregar_log("[STOP] Solicitud de detencion enviada al proceso")
            self.actualizar_estado("[STOP] Deteniendo proceso...", self.C_NARANJA)
            self.btn_detener.config(state=tk.DISABLED)

    def _lanzar_proceso(self, cmd, msg_inicio, msg_ok, msg_err,
                         estado_ok, estado_err, popup_ok, popup_err,
                         etapas_esperadas: list | None = None):
        if self.proceso_activo:
            return

        def ejecutar():
            try:
                self.deshabilitar_botones()
                self._reset_etapas()
                self.actualizar_estado(msg_inicio, self.C_AZUL)
                self.agregar_log(f"â–¶  {msg_inicio}")

                env = os.environ.copy()
                env["PYTHONUNBUFFERED"]  = "1"
                env["PYTHONUTF8"]        = "1"   # fuerza UTF-8 en stdout del subprocess
                env["PYTHONIOENCODING"]  = "utf-8"

                proceso = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,  # descarta stderr para evitar duplicados
                    text=True,
                    bufsize=1,                  # lÃ­nea a lÃ­nea
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    cwd=Path(__file__).parent,
                )

                self._proceso_actual = proceso
                assert proceso.stdout is not None  # stdout=PIPE garantiza que no es None
                etapa_actual = None
                for linea in iter(proceso.stdout.readline, ""):
                    linea = linea.rstrip()
                    if not linea:
                        continue
                    self.agregar_log(linea)
                    idx = self._detectar_etapa(linea)
                    if idx is not None and idx != etapa_actual:
                        if etapa_actual is not None:
                            self._set_etapa(etapa_actual, "done")
                        etapa_actual = idx
                        self._set_etapa(idx, "running")

                proceso.stdout.close()
                proceso.wait()

                if etapa_actual is not None:
                    self._set_etapa(etapa_actual,
                                    "done" if proceso.returncode == 0 else "error")

                if self._proceso_detenido:
                    self.actualizar_estado("[STOP] Proceso detenido por el usuario", self.C_NARANJA)
                    self.agregar_log("[STOP] Proceso detenido")
                elif proceso.returncode == 0:
                    self.actualizar_estado(estado_ok, self.C_VERDE)
                    self.agregar_log(f"ðŸŽ‰ {msg_ok}")
                    messagebox.showinfo("Completado", popup_ok)
                else:
                    self.actualizar_estado(estado_err, self.C_ROJO)
                    self.agregar_log(f"âŒ {msg_err}")
                    messagebox.showerror("Error", popup_err)

            except Exception as e:
                self.actualizar_estado("âŒ Error crÃ­tico", self.C_ROJO)
                self.agregar_log(f"âŒ Error inesperado: {e}")
                messagebox.showerror("Error CrÃ­tico", f"Error inesperado:\n{e}")
            finally:
                self._proceso_actual = None
                self._proceso_detenido = False
                self.habilitar_botones()

        threading.Thread(target=ejecutar, daemon=True).start()

    def ejecutar_pipeline_completo(self):
        script_path = Path(__file__).parent / "run_pipeline.py"
        self._lanzar_proceso(
            cmd=[sys.executable, "-u", str(script_path)],
            msg_inicio="Ejecutando pipeline completo (Etapas 0 â†’ 5)...",
            msg_ok="Â¡Pipeline completado correctamente!",
            msg_err="Error durante el pipeline",
            estado_ok="âœ… Pipeline completado",
            estado_err="âŒ Error en el pipeline",
            popup_ok="Â¡Pipeline ejecutado correctamente!\n\nResultados en:\ndata/2. OUTPUT/5. PRESENTACION/",
            popup_err="Hubo un error en el pipeline.\nRevisa el log para mÃ¡s detalles.",
            etapas_esperadas=list(range(6)),
        )

    def ejecutar_solo_incremental(self):
        script_path = Path(__file__).parent / "run_pipeline.py"
        self._lanzar_proceso(
            cmd=[sys.executable, "-u", str(script_path), "--etapas", "5"],
            msg_inicio="Ejecutando anÃ¡lisis incremental (Etapa 5)...",
            msg_ok="Â¡AnÃ¡lisis incremental completado!",
            msg_err="Error en el anÃ¡lisis",
            estado_ok="âœ… Incremental completado",
            estado_err="âŒ Error en el incremental",
            popup_ok="Â¡AnÃ¡lisis incremental completado!\n\nResultados en:\ndata/2. OUTPUT/5. PRESENTACION/INCREMENTALES/",
            popup_err="Error en el anÃ¡lisis.\nRevisa el log.",
            etapas_esperadas=[5],
        )

    def abrir_carpeta_resultados(self):
        carpeta = Path(__file__).parent / "data" / "2. OUTPUT" / "5. PRESENTACION"
        carpeta.mkdir(parents=True, exist_ok=True)
        os.startfile(str(carpeta))

    def salir(self):
        if self.proceso_activo:
            if messagebox.askyesno("Confirmar", "Hay un proceso en ejecuciÃ³n.\nÂ¿Deseas salir?"):
                if self._proceso_actual and self._proceso_actual.poll() is None:
                    self._proceso_actual.terminate()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass


def main():
    try:
        app = LanzadorLicitaciones()
        app.run()
    except Exception as e:
        print(f"Error crÃ­tico: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

