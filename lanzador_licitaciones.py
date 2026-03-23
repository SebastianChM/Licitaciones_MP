#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 LANZADOR LICITACIONES MERCADO PÚBLICO
Interfaz gráfica simple para ejecutar el pipeline de licitaciones
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import threading
import os
from pathlib import Path
import time

# Hacer disponibles los módulos de src/ sin necesidad de instalar el paquete
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.verificador_entorno import VerificadorEntorno  # noqa: E402

class LanzadorLicitaciones:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🏛️ MP - Licitaciones Mercado Público")
        self.root.geometry("600x540")
        self.root.resizable(False, False)

        # Centrar ventana
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.root.winfo_screenheight() // 2) - (540 // 2)
        self.root.geometry(f"600x540+{x}+{y}")

        # Colores corporativos MP
        self.color_azul_mp = "#0066CC"
        self.color_gris = "#F5F5F5"
        self.root.configure(bg=self.color_gris)

        self._verificador = VerificadorEntorno(Path(__file__).parent)
        self._frame_checks: tk.LabelFrame | None = None

        self.proceso_activo = False
        self.setup_ui()
        self._actualizar_checks()
    
    def setup_ui(self):
        """Configurar interfaz de usuario"""
        # Frame principal
        main_frame = tk.Frame(self.root, bg=self.color_gris, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Logo/Título
        titulo = tk.Label(main_frame, 
                         text="🏛️ MP CONSULTING",
                         font=("Arial", 18, "bold"),
                         fg=self.color_azul_mp,
                         bg=self.color_gris)
        titulo.pack(pady=(0, 5))
        
        subtitulo = tk.Label(main_frame,
                            text="Sistema de Licitaciones Mercado Público",
                            font=("Arial", 12),
                            fg="gray",
                            bg=self.color_gris)
        subtitulo.pack(pady=(0, 8))

        # --- Panel de estado del entorno ---
        self._frame_checks = tk.LabelFrame(
            main_frame,
            text=" Estado del entorno ",
            font=("Arial", 9, "bold"),
            bg=self.color_gris,
            pady=4,
        )
        self._frame_checks.pack(fill=tk.X, pady=(0, 10))

        # Botones principales
        self.btn_completo = tk.Button(main_frame,
                                     text="🚀 EJECUTAR PIPELINE COMPLETO",
                                     font=("Arial", 12, "bold"),
                                     bg=self.color_azul_mp,
                                     fg="white",
                                     width=40,
                                     height=2,
                                     command=self.ejecutar_pipeline_completo,
                                     cursor="hand2")
        self.btn_completo.pack(pady=10)
        
        self.btn_incremental = tk.Button(main_frame,
                                        text="📊 SOLO ANÁLISIS INCREMENTAL",
                                        font=("Arial", 12, "bold"),
                                        bg="#00AA00",
                                        fg="white",
                                        width=40,
                                        height=2,
                                        command=self.ejecutar_solo_incremental,
                                        cursor="hand2")
        self.btn_incremental.pack(pady=10)

        self.btn_resultados = tk.Button(main_frame,
                                        text="📂 Abrir carpeta de resultados",
                                        font=("Arial", 10),
                                        bg="#555555",
                                        fg="white",
                                        width=40,
                                        command=self.abrir_carpeta_resultados,
                                        cursor="hand2")
        self.btn_resultados.pack(pady=(0, 10))

        # Separador
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=20)
        
        # Área de estado
        estado_frame = tk.Frame(main_frame, bg=self.color_gris)
        estado_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(estado_frame, text="Estado:", font=("Arial", 10, "bold"),
                bg=self.color_gris).pack(anchor=tk.W)
        
        self.lbl_estado = tk.Label(estado_frame,
                                  text="✅ Sistema listo para ejecutar",
                                  font=("Arial", 10),
                                  fg="green",
                                  bg=self.color_gris)
        self.lbl_estado.pack(anchor=tk.W, pady=(5, 10))
        
        # Barra de progreso
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)
        
        # Área de log
        log_frame = tk.Frame(main_frame, bg=self.color_gris)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tk.Label(log_frame, text="Log de ejecución:", font=("Arial", 10, "bold"),
                bg=self.color_gris).pack(anchor=tk.W)
        
        # Text widget con scrollbar
        text_frame = tk.Frame(log_frame, bg=self.color_gris)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_log = tk.Text(text_frame, height=8, width=70,
                               font=("Consolas", 9),
                               bg="black", fg="lime",
                               state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_log.yview)
        self.text_log.configure(yscrollcommand=scrollbar.set)
        
        self.text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botón salir
        self.btn_salir = tk.Button(main_frame,
                                  text="❌ Salir",
                                  font=("Arial", 10),
                                  bg="#CC0000",
                                  fg="white",
                                  width=15,
                                  command=self.salir,
                                  cursor="hand2")
        self.btn_salir.pack(pady=10)
        
        # Log inicial
        self.agregar_log("🎯 Sistema de licitaciones MP iniciado")
        self.agregar_log("💡 Selecciona una opción para comenzar")

    def _actualizar_checks(self) -> None:
        """Ejecuta las verificaciones de entorno y actualiza el panel de estado."""
        if self._frame_checks is None:
            return

        # Limpiar contenido anterior del panel
        for widget in self._frame_checks.winfo_children():
            widget.destroy()

        resultados = self._verificador.verificar_todo()

        for r in resultados:
            if r.ok:
                icono, color = "✅", "#1a7a1a"
            elif r.critico:
                icono, color = "❌", "#cc0000"
            else:
                icono, color = "⚠️ ", "#cc8800"

            tk.Label(
                self._frame_checks,
                text=f"{icono}  {r.nombre}: {r.mensaje}",
                font=("Arial", 8),
                fg=color,
                bg=self.color_gris,
                anchor=tk.W,
            ).pack(fill=tk.X, padx=10, pady=1)

        # Botón de re-verificación en la última fila
        btn_frame = tk.Frame(self._frame_checks, bg=self.color_gris)
        btn_frame.pack(fill=tk.X, padx=10, pady=(2, 4))
        tk.Button(
            btn_frame,
            text="🔄 Re-verificar",
            font=("Arial", 8),
            bg="#e0e0e0",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._actualizar_checks,
        ).pack(anchor=tk.E)

        # Bloquear botones principales si hay errores críticos
        hay_error = self._verificador.hay_errores_criticos(resultados)
        estado_btn = tk.DISABLED if hay_error else tk.NORMAL
        self.btn_completo.config(state=estado_btn)
        self.btn_incremental.config(state=estado_btn)

        if hay_error:
            self.actualizar_estado("⚠️ Configuración incompleta — revisa el panel superior", "red")
        else:
            self.actualizar_estado("✅ Sistema listo para ejecutar", "green")
    
    def agregar_log(self, mensaje):
        """Agregar mensaje al área de log"""
        timestamp = time.strftime("%H:%M:%S")
        mensaje_completo = f"[{timestamp}] {mensaje}\n"
        
        self.text_log.config(state=tk.NORMAL)
        self.text_log.insert(tk.END, mensaje_completo)
        self.text_log.see(tk.END)
        self.text_log.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def actualizar_estado(self, mensaje, color="black"):
        """Actualizar mensaje de estado"""
        self.lbl_estado.config(text=mensaje, fg=color)
        self.root.update_idletasks()
    
    def deshabilitar_botones(self):
        """Deshabilitar botones durante ejecución"""
        self.btn_completo.config(state=tk.DISABLED)
        self.btn_incremental.config(state=tk.DISABLED)
        self.progress.start()
        self.proceso_activo = True
    
    def habilitar_botones(self):
        """Habilitar botones tras ejecución"""
        self.btn_completo.config(state=tk.NORMAL)
        self.btn_incremental.config(state=tk.NORMAL)
        self.progress.stop()
        self.proceso_activo = False
    
    def ejecutar_pipeline_completo(self):
        """Ejecutar pipeline completo en hilo separado"""
        if self.proceso_activo:
            return
        
        def ejecutar():
            try:
                self.deshabilitar_botones()
                self.actualizar_estado("🚀 Ejecutando pipeline completo...", "blue")
                self.agregar_log("🔄 Iniciando pipeline completo (Etapas 0-5)")
                
                # Ejecutar pipeline
                script_path = Path(__file__).parent / "run_pipeline.py"
                
                proceso = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=Path(__file__).parent
                )
                
                # Leer output en tiempo real
                while True:
                    output = proceso.stdout.readline()
                    if output == '' and proceso.poll() is not None:
                        break
                    if output:
                        self.agregar_log(output.strip())
                
                proceso.wait()
                
                if proceso.returncode == 0:
                    self.actualizar_estado("✅ Pipeline completado exitosamente", "green")
                    self.agregar_log("🎉 ¡Pipeline ejecutado correctamente!")
                    self.agregar_log("📊 Revisa los archivos generados en data/2. OUTPUT/")
                    messagebox.showinfo("Éxito", 
                                      "¡Pipeline ejecutado correctamente!\n\n" +
                                      "Los reportes han sido generados en:\n" +
                                      "data/2. OUTPUT/5. PRESENTACION/")
                else:
                    self.actualizar_estado("❌ Error en la ejecución", "red")
                    self.agregar_log("❌ Error durante la ejecución")
                    messagebox.showerror("Error", "Ocurrió un error durante la ejecución.\nRevisa los logs para más detalles.")
                
            except Exception as e:
                self.actualizar_estado("❌ Error crítico", "red")
                self.agregar_log(f"❌ Error: {str(e)}")
                messagebox.showerror("Error Crítico", f"Error inesperado:\n{str(e)}")
            finally:
                self.habilitar_botones()
        
        thread = threading.Thread(target=ejecutar, daemon=True)
        thread.start()
    
    def ejecutar_solo_incremental(self):
        """Ejecutar solo análisis incremental"""
        if self.proceso_activo:
            return
        
        def ejecutar():
            try:
                self.deshabilitar_botones()
                self.actualizar_estado("📊 Ejecutando análisis incremental...", "blue")
                self.agregar_log("🔄 Iniciando análisis incremental (Solo Etapa 5)")
                
                # Ejecutar solo etapa 5
                script_path = Path(__file__).parent / "run_pipeline.py"
                
                proceso = subprocess.Popen(
                    [sys.executable, str(script_path), "--etapas", "5"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=Path(__file__).parent
                )
                
                # Leer output en tiempo real
                while True:
                    output = proceso.stdout.readline()
                    if output == '' and proceso.poll() is not None:
                        break
                    if output:
                        self.agregar_log(output.strip())
                
                proceso.wait()
                
                if proceso.returncode == 0:
                    self.actualizar_estado("✅ Análisis incremental completado", "green")
                    self.agregar_log("🎉 ¡Análisis incremental ejecutado correctamente!")
                    self.agregar_log("📊 Revisa los reportes incrementales generados")
                    messagebox.showinfo("Éxito", 
                                      "¡Análisis incremental completado!\n\n" +
                                      "Los reportes incrementales han sido generados en:\n" +
                                      "data/2. OUTPUT/5. PRESENTACION/INCREMENTALES/")
                else:
                    self.actualizar_estado("❌ Error en el análisis", "red")
                    self.agregar_log("❌ Error durante el análisis incremental")
                    messagebox.showerror("Error", "Ocurrió un error durante el análisis.\nRevisa los logs para más detalles.")
                
            except Exception as e:
                self.actualizar_estado("❌ Error crítico", "red")
                self.agregar_log(f"❌ Error: {str(e)}")
                messagebox.showerror("Error Crítico", f"Error inesperado:\n{str(e)}")
            finally:
                self.habilitar_botones()
        
        thread = threading.Thread(target=ejecutar, daemon=True)
        thread.start()
    
    def abrir_carpeta_resultados(self):
        """Abre la carpeta de resultados en el Explorador de Windows."""
        carpeta = Path(__file__).parent / "data" / "2. OUTPUT" / "5. PRESENTACION"
        carpeta.mkdir(parents=True, exist_ok=True)
        os.startfile(str(carpeta))

    def salir(self):
        """Salir de la aplicación"""
        if self.proceso_activo:
            if messagebox.askyesno("Confirmar", "Hay un proceso en ejecución.\n¿Deseas salir de todas formas?"):
                self.root.quit()
        else:
            self.root.quit()
    
    def run(self):
        """Ejecutar la aplicación"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

def main():
    """Punto de entrada principal"""
    try:
        app = LanzadorLicitaciones()
        app.run()
    except Exception as e:
        print(f"Error crítico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()