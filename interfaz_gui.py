"""
Interfaz Gráfica Moderna para Mi Asistente IA (PyQt6).
Características:
- Menú desplegable y buscador automático de modelos .gguf en tu computadora.
- Selector de modelo estándar al inicio (primera vez) y ventana de configuración accesible con ⚙️.
- Ventana compacta estilo Spotlight / Asistente flotante.
- Tema oscuro moderno con burbujas de chat estilizadas (Catppuccin).
- Botón de micrófono para dictado por voz (Whisper STT).
- Botón de voz en alta voz (TTS con edge-tts en español).
- Ejecución asíncrona en hilos para una interfaz siempre fluida.
- Atajos de teclado: Enter para enviar, Esc para minimizar/ocultar, Ctrl+L limpiar, Ctrl+, ajustes.
"""

import sys
import os
import threading
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextBrowser, QTextEdit, QPushButton, QLabel, QFrame,
    QGraphicsDropShadowEffect, QDialog, QComboBox, QFileDialog,
    QProgressBar, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QTextCursor

from agente import AgenteAsistente
from voz import (
    hablar, detener_habla, get_whisper,
    grabar_audio_pulsado, transcribir_array_audio
)
from config import (
    cargar_config, guardar_config, escanear_modelos_locales,
    establecer_modelo_estandar, reiniciar_servidor_modelo,
    verificar_servidor_listo
)


class HiloProcesarMensaje(QThread):
    senal_accion = pyqtSignal(str, str)
    senal_finalizado = pyqtSignal(str)
    senal_error = pyqtSignal(str)

    def __init__(self, agente: AgenteAsistente, mensaje: str):
        super().__init__()
        self.agente = agente
        self.mensaje = mensaje

    def run(self):
        def on_accion(nombre, args):
            self.senal_accion.emit(nombre, str(args))

        try:
            respuesta = self.agente.procesar_mensaje(self.mensaje, callback_accion=on_accion)
            self.senal_finalizado.emit(respuesta)
        except Exception as e:
            self.senal_error.emit(str(e))


class HiloGrabacionVoz(QThread):
    senal_progreso = pyqtSignal(str)
    senal_transcrito = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.evento_grabando = threading.Event()

    def run(self):
        self.evento_grabando.set()
        self.senal_progreso.emit("Grabando audio...")
        audio = grabar_audio_pulsado(self.evento_grabando)

        if len(audio) > 0:
            self.senal_progreso.emit("Transcribiendo con Whisper...")
            texto = transcribir_array_audio(audio)
            self.senal_transcrito.emit(texto)
        else:
            self.senal_transcrito.emit("")

    def detener(self):
        self.evento_grabando.clear()


class HiloCambioModelo(QThread):
    senal_progreso = pyqtSignal(str)
    senal_finalizado = pyqtSignal(bool, str)

    def __init__(self, ruta_modelo: str, ctx_size: int = 8192, n_gpu_layers: int = 99):
        super().__init__()
        self.ruta_modelo = ruta_modelo
        self.ctx_size = ctx_size
        self.n_gpu_layers = n_gpu_layers

    def run(self):
        try:
            cfg = cargar_config()
            cfg["modelo_path"] = self.ruta_modelo
            nombre = os.path.basename(self.ruta_modelo)
            if nombre.endswith(".gguf"):
                nombre = nombre[:-5]
            cfg["modelo_nombre"] = nombre
            cfg["ctx_size"] = int(self.ctx_size)
            cfg["n_gpu_layers"] = int(self.n_gpu_layers)
            cfg["primera_vez"] = False
            guardar_config(cfg)

            def al_progresar(msg):
                self.senal_progreso.emit(msg)

            ok, mensaje = reiniciar_servidor_modelo(timeout_espera=35, callback_progreso=al_progresar)
            self.senal_finalizado.emit(ok, mensaje)
        except Exception as e:
            self.senal_finalizado.emit(False, str(e))


class DialogoConfiguracion(QDialog):
    """Diálogo modal moderno para elegir y cambiar el modelo estándar de la computadora."""
    def __init__(self, parent=None, es_primera_vez=False):
        super().__init__(parent)
        self.es_primera_vez = es_primera_vez
        self.hilo_cambio = None
        self.config = cargar_config()
        self.init_ui()

    def init_ui(self):
        titulo_ventana = "Bienvenido - Elegir Modelo Estándar" if self.es_primera_vez else "Configuración del Asistente y Modelo"
        self.setWindowTitle(titulo_ventana)
        self.setFixedWidth(560)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Ubuntu', sans-serif;
            }
            QLabel {
                color: #cdd6f4;
            }
            QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #89b4fa;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e2e;
                color: #cdd6f4;
                selection-background-color: #89b4fa;
                selection-color: #11111b;
                border: 1px solid #45475a;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
            QPushButton#btn_primario {
                background-color: #89b4fa;
                color: #11111b;
                font-weight: bold;
                border: none;
            }
            QPushButton#btn_primario:hover {
                background-color: #b4befe;
            }
            QProgressBar {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                text-align: center;
                color: #cdd6f4;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Encabezado
        layout_header = QHBoxLayout()
        lbl_icono = QLabel("🚀" if self.es_primera_vez else "⚙️")
        lbl_icono.setStyleSheet("font-size: 30px;")
        layout_header.addWidget(lbl_icono)

        layout_titulos = QVBoxLayout()
        lbl_titulo = QLabel("Elegir Modelo Estándar" if self.es_primera_vez else "Configuración de Modelo")
        lbl_titulo.setFont(QFont("Ubuntu", 14, QFont.Weight.Bold))
        lbl_subtitulo = QLabel(
            "Detectamos estos modelos en tu compu. Elegí cuál usar como estándar antes de comenzar:"
            if self.es_primera_vez else
            "Seleccioná el modelo que responderá tus órdenes o examiná un archivo nuevo:"
        )
        lbl_subtitulo.setStyleSheet("color: #a6adc8; font-size: 12px;")
        lbl_subtitulo.setWordWrap(True)
        layout_titulos.addWidget(lbl_titulo)
        layout_titulos.addWidget(lbl_subtitulo)
        layout_header.addLayout(layout_titulos, 1)
        layout.addLayout(layout_header)

        # Separador horizontal
        linea = QFrame()
        linea.setFrameShape(QFrame.Shape.HLine)
        linea.setStyleSheet("color: #313244;")
        layout.addWidget(linea)

        # Sección Modelo
        lbl_model_tag = QLabel("🧠 Modelos GGUF encontrados en tu computadora:")
        lbl_model_tag.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_model_tag)

        # Menú desplegable + Botones Examinar y Refrescar
        layout_selector = QHBoxLayout()
        self.combo_modelos = QComboBox()
        self.combo_modelos.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        layout_selector.addWidget(self.combo_modelos, 1)

        self.btn_examinar = QPushButton("📁 Examinar...")
        self.btn_examinar.setToolTip("Buscar otro archivo .gguf en cualquier carpeta de tu compu")
        self.btn_examinar.clicked.connect(self.examinar_archivo)
        layout_selector.addWidget(self.btn_examinar)

        self.btn_refrescar = QPushButton("🔄")
        self.btn_refrescar.setToolTip("Volver a escanear modelos en la computadora")
        self.btn_refrescar.setFixedWidth(40)
        self.btn_refrescar.clicked.connect(self.refrescar_modelos)
        layout_selector.addWidget(self.btn_refrescar)

        layout.addLayout(layout_selector)

        # Ruta completa
        self.lbl_ruta_modelo = QLabel("")
        self.lbl_ruta_modelo.setStyleSheet("color: #6c7086; font-size: 11px; font-family: monospace;")
        self.lbl_ruta_modelo.setWordWrap(True)
        layout.addWidget(self.lbl_ruta_modelo)

        # Parámetros avanzados
        layout_opciones = QHBoxLayout()

        # Contexto
        v_ctx = QVBoxLayout()
        lbl_ctx = QLabel("Ventana de Contexto:")
        lbl_ctx.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.combo_ctx = QComboBox()
        for c in [2048, 4096, 8192, 16384, 32768]:
            self.combo_ctx.addItem(f"{c} tokens", c)
        idx_ctx = self.combo_ctx.findData(self.config.get("ctx_size", 8192))
        if idx_ctx >= 0:
            self.combo_ctx.setCurrentIndex(idx_ctx)
        v_ctx.addWidget(lbl_ctx)
        v_ctx.addWidget(self.combo_ctx)
        layout_opciones.addLayout(v_ctx)

        # Aceleración GPU
        v_gpu = QVBoxLayout()
        lbl_gpu = QLabel("Aceleración:")
        lbl_gpu.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.combo_gpu = QComboBox()
        self.combo_gpu.addItem("GPU Completa (CUDA)", 99)
        self.combo_gpu.addItem("Solo CPU (0 capas)", 0)
        idx_gpu = self.combo_gpu.findData(self.config.get("n_gpu_layers", 99))
        if idx_gpu >= 0:
            self.combo_gpu.setCurrentIndex(idx_gpu)
        v_gpu.addWidget(lbl_gpu)
        v_gpu.addWidget(self.combo_gpu)
        layout_opciones.addLayout(v_gpu)

        layout.addLayout(layout_opciones)

        # Checkbox estándar
        self.chk_estandar = QCheckBox("Guardar como modelo estándar predeterminado en config.json")
        self.chk_estandar.setChecked(True)
        self.chk_estandar.setStyleSheet("color: #a6adc8; font-size: 12px; margin-top: 4px;")
        layout.addWidget(self.chk_estandar)

        # Indicador de estado y barra de progreso
        self.lbl_progreso = QLabel("")
        self.lbl_progreso.setStyleSheet("color: #f9e2af; font-size: 12px; font-weight: bold;")
        self.lbl_progreso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_progreso)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.hide()
        layout.addWidget(self.barra_progreso)

        # Botones inferiores
        layout_botones = QHBoxLayout()
        layout_botones.addStretch()

        self.btn_cancelar = QPushButton("Salir" if self.es_primera_vez else "Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        layout_botones.addWidget(self.btn_cancelar)

        texto_accion = "🚀 Iniciar Asistente" if self.es_primera_vez else "💾 Guardar y Aplicar"
        self.btn_aplicar = QPushButton(texto_accion)
        self.btn_aplicar.setObjectName("btn_primario")
        self.btn_aplicar.clicked.connect(self.al_aplicar)
        layout_botones.addWidget(self.btn_aplicar)

        layout.addLayout(layout_botones)

        # Conectar eventos
        self.combo_modelos.currentIndexChanged.connect(self.al_cambiar_combo)

        # Cargar lista inicial
        self.refrescar_modelos()

    def al_cambiar_combo(self):
        ruta = self.combo_modelos.currentData()
        if ruta:
            self.lbl_ruta_modelo.setText(f"📁 {ruta}")

    def refrescar_modelos(self):
        self.combo_modelos.clear()
        modelos = escanear_modelos_locales()
        modelo_actual = self.config.get("modelo_path", "")

        seleccion_idx = 0
        for i, m in enumerate(modelos):
            self.combo_modelos.addItem(f"{m['nombre']} — ({m['tamano']})", m["ruta"])
            if m["ruta"] == modelo_actual:
                seleccion_idx = i

        if self.combo_modelos.count() > 0:
            self.combo_modelos.setCurrentIndex(seleccion_idx)
            self.al_cambiar_combo()
        else:
            self.lbl_ruta_modelo.setText("⚠️ No se encontraron modelos .gguf en las carpetas usuales. Usá 'Examinar...'.")

    def examinar_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar modelo GGUF",
            os.path.expanduser("~"),
            "Modelos GGUF (*.gguf);;Todos los archivos (*)"
        )
        if ruta:
            nombre = os.path.basename(ruta)
            if nombre.endswith(".gguf"):
                nombre = nombre[:-5]
            tamano_gb = os.path.getsize(ruta) / (1024**3)
            # Buscar si ya está en la lista
            for i in range(self.combo_modelos.count()):
                if self.combo_modelos.itemData(i) == ruta:
                    self.combo_modelos.setCurrentIndex(i)
                    return
            self.combo_modelos.addItem(f"{nombre} — ({tamano_gb:.2f} GB)", ruta)
            self.combo_modelos.setCurrentIndex(self.combo_modelos.count() - 1)
            self.al_cambiar_combo()

    def al_aplicar(self):
        ruta = self.combo_modelos.currentData()
        if not ruta or not os.path.isfile(ruta):
            QMessageBox.warning(self, "Modelo requerido", "Por favor seleccioná un archivo de modelo .gguf existente.")
            return

        ctx_size = self.combo_ctx.currentData()
        n_gpu_layers = self.combo_gpu.currentData()

        # Bloquear controles mientras recarga
        self.btn_aplicar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.combo_modelos.setEnabled(False)
        self.btn_examinar.setEnabled(False)
        self.btn_refrescar.setEnabled(False)
        self.combo_ctx.setEnabled(False)
        self.combo_gpu.setEnabled(False)
        self.barra_progreso.show()
        self.lbl_progreso.setText("Iniciando servicio y cargando modelo...")

        self.hilo_cambio = HiloCambioModelo(ruta, ctx_size, n_gpu_layers)
        self.hilo_cambio.senal_progreso.connect(self.lbl_progreso.setText)
        self.hilo_cambio.senal_finalizado.connect(self.on_cambio_finalizado)
        self.hilo_cambio.start()

    def on_cambio_finalizado(self, ok: bool, mensaje: str):
        self.barra_progreso.hide()
        if ok:
            self.lbl_progreso.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.lbl_progreso.setText("✅ " + mensaje)
            QTimer.singleShot(700, self.accept)
        else:
            self.lbl_progreso.setStyleSheet("color: #f38ba8; font-weight: bold;")
            self.lbl_progreso.setText("❌ " + mensaje)
            self.btn_aplicar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            self.combo_modelos.setEnabled(True)
            self.btn_examinar.setEnabled(True)
            self.btn_refrescar.setEnabled(True)
            self.combo_ctx.setEnabled(True)
            self.combo_gpu.setEnabled(True)


class InputTextEdit(QTextEdit):
    senal_enviar = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.senal_enviar.emit()
        else:
            super().keyPressEvent(event)


class VentanaAsistente(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = cargar_config()
        self.agente = AgenteAsistente()
        self.leer_voz = False
        self.grabando = False
        self.hilo_voz = None
        self.hilo_proceso = None

        self.init_ui()

    def obtener_nombre_modelo(self) -> str:
        nombre = self.config.get("modelo_nombre", "Modelo")
        # Truncar si es excesivamente largo
        if len(nombre) > 22:
            return nombre[:20] + "…"
        return nombre

    def init_ui(self):
        self.setWindowTitle("Mi Asistente IA")
        self.setMinimumSize(500, 640)
        self.resize(540, 700)

        # Widget central y layout principal
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.setContentsMargins(16, 16, 16, 16)
        layout_principal.setSpacing(12)

        # --- Encabezado / Barra superior ---
        barra_superior = QHBoxLayout()

        lbl_icono = QLabel("🤖")
        lbl_icono.setStyleSheet("font-size: 22px;")
        barra_superior.addWidget(lbl_icono)

        lbl_titulo = QLabel("Mi Asistente")
        lbl_titulo.setFont(QFont("Ubuntu", 14, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #cdd6f4;")
        barra_superior.addWidget(lbl_titulo)

        # Badge interactivo que muestra el modelo actual
        self.btn_modelo_badge = QPushButton(f"⚡ {self.obtener_nombre_modelo()}")
        self.btn_modelo_badge.setToolTip(f"Modelo actual: {self.config.get('modelo_nombre')}\nHacé clic para cambiar de modelo")
        self.btn_modelo_badge.setStyleSheet("""
            QPushButton {
                background-color: #24273a;
                color: #89b4fa;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #89b4fa;
                background-color: #313244;
            }
        """)
        self.btn_modelo_badge.clicked.connect(self.abrir_configuracion)
        barra_superior.addWidget(self.btn_modelo_badge)

        self.lbl_estado = QLabel("🟢 Listo")
        self.lbl_estado.setFont(QFont("Ubuntu", 10))
        self.lbl_estado.setStyleSheet("color: #a6adc8; margin-left: 6px;")
        barra_superior.addWidget(self.lbl_estado)

        barra_superior.addStretch()

        # Botón Configuración (⚙️)
        self.btn_config = QPushButton("⚙️")
        self.btn_config.setToolTip("Configurar modelo y opciones del asistente (Ctrl+,)")
        self.btn_config.setFixedSize(36, 32)
        self.btn_config.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 6px;
                border: 1px solid #45475a;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
        """)
        self.btn_config.clicked.connect(self.abrir_configuracion)
        barra_superior.addWidget(self.btn_config)

        # Botón toggle voz
        self.btn_voz_toggle = QPushButton("🔊")
        self.btn_voz_toggle.setToolTip("Activar/Desactivar lectura en voz alta")
        self.btn_voz_toggle.setFixedSize(36, 32)
        self.btn_voz_toggle.setCheckable(True)
        self.btn_voz_toggle.setChecked(False)
        self.btn_voz_toggle.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 6px;
                border: 1px solid #45475a;
                font-size: 14px;
            }
            QPushButton:checked {
                background-color: #89b4fa;
                color: #11111b;
            }
            QPushButton:hover {
                border-color: #89b4fa;
            }
        """)
        self.btn_voz_toggle.clicked.connect(self.toggle_voz)
        barra_superior.addWidget(self.btn_voz_toggle)

        # Botón limpiar chat
        btn_limpiar = QPushButton("🗑️")
        btn_limpiar.setToolTip("Limpiar chat y reiniciar conversación (Ctrl+L)")
        btn_limpiar.setFixedSize(36, 32)
        btn_limpiar.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 6px;
                border: 1px solid #45475a;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #f38ba8;
            }
        """)
        btn_limpiar.clicked.connect(self.limpiar_chat)
        barra_superior.addWidget(btn_limpiar)

        layout_principal.addLayout(barra_superior)

        # --- Área de Chat (Historial) ---
        self.visor_chat = QTextBrowser()
        self.visor_chat.setOpenExternalLinks(True)
        self.visor_chat.setStyleSheet("""
            QTextBrowser {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 12px;
                padding: 12px;
                font-size: 13px;
                font-family: 'Ubuntu', sans-serif;
            }
        """)
        layout_principal.addWidget(self.visor_chat, 1)

        # Mensaje de bienvenida inicial
        self.agregar_mensaje_sistema(
            f"¡Hola! Soy tu asistente de escritorio. Corriendo con <b>{self.config.get('modelo_nombre')}</b>.<br>"
            "Puedo ayudarte a organizar carpetas, archivos, abrir programas, buscar en la web y responder lo que necesites."
        )

        # --- Barra inferior (Entrada y botones) ---
        barra_entrada = QHBoxLayout()
        barra_entrada.setSpacing(8)

        # Botón Micrófono
        self.btn_mic = QPushButton("🎙️")
        self.btn_mic.setToolTip("Dictar por voz (Whisper)")
        self.btn_mic.setFixedSize(44, 44)
        self.btn_mic.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 22px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
        """)
        self.btn_mic.clicked.connect(self.toggle_grabacion)
        barra_entrada.addWidget(self.btn_mic)

        # Campo de texto multilínea con Enter para enviar
        self.input_texto = InputTextEdit()
        self.input_texto.setPlaceholderText("Escribí o dictá una orden... (Enter para enviar)")
        self.input_texto.setFixedHeight(44)
        self.input_texto.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 13px;
                font-family: 'Ubuntu', sans-serif;
            }
            QTextEdit:focus {
                border: 1px solid #89b4fa;
            }
        """)
        self.input_texto.senal_enviar.connect(self.enviar_mensaje)
        barra_entrada.addWidget(self.input_texto, 1)

        # Botón Enviar
        self.btn_enviar = QPushButton("➤")
        self.btn_enviar.setToolTip("Enviar mensaje")
        self.btn_enviar.setFixedSize(44, 44)
        self.btn_enviar.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
                border-radius: 22px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #6c7086;
            }
        """)
        self.btn_enviar.clicked.connect(self.enviar_mensaje)
        barra_entrada.addWidget(self.btn_enviar)

        layout_principal.addLayout(barra_entrada)

        # Fondo general de la ventana
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
        """)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.showMinimized()
        elif event.key() == Qt.Key.Key_L and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.limpiar_chat()
        elif event.key() == Qt.Key.Key_M and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.toggle_grabacion()
        elif event.key() == Qt.Key.Key_Comma and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.abrir_configuracion()
        else:
            super().keyPressEvent(event)

    def abrir_configuracion(self):
        """Abre el diálogo de configuración para cambiar de modelo u opciones."""
        detener_habla()
        dialogo = DialogoConfiguracion(self, es_primera_vez=False)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.config = cargar_config()
            self.agente.actualizar_configuracion()
            self.actualizar_badge_modelo()
            self.agregar_mensaje_sistema(
                f"🔄 Modelo estándar cambiado exitosamente a: <b>{self.config.get('modelo_nombre')}</b>"
            )

    def actualizar_badge_modelo(self):
        self.btn_modelo_badge.setText(f"⚡ {self.obtener_nombre_modelo()}")
        self.btn_modelo_badge.setToolTip(f"Modelo actual: {self.config.get('modelo_nombre')}\nHacé clic para cambiar de modelo")

    def toggle_voz(self):
        self.leer_voz = self.btn_voz_toggle.isChecked()
        if not self.leer_voz:
            detener_habla()

    def limpiar_chat(self):
        detener_habla()
        self.agente.reiniciar_conversacion()
        self.visor_chat.clear()
        self.agregar_mensaje_sistema("Conversación reiniciada. ¿En qué te ayudo ahora?")

    def agregar_mensaje_usuario(self, texto: str):
        html = f"""
        <div style="margin: 8px 0; text-align: right;">
            <span style="display: inline-block; background-color: #313244; color: #89b4fa; 
                         padding: 8px 14px; border-radius: 12px 12px 2px 12px; 
                         border: 1px solid #45475a; max-width: 80%; text-align: left;">
                <b>Vos:</b> {texto}
            </span>
        </div>
        """
        self.visor_chat.append(html)
        self.scroll_al_final()

    def agregar_mensaje_asistente(self, texto: str):
        texto_html = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        texto_html = texto_html.replace("\n", "<br>")
        import re
        texto_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', texto_html)

        html = f"""
        <div style="margin: 8px 0; text-align: left;">
            <div style="display: inline-block; background-color: #1e1e2e; color: #cdd6f4; 
                        padding: 10px 14px; border-radius: 12px 12px 12px 2px; 
                        border: 1px solid #313244; max-width: 85%;">
                <span style="color: #a6e3a1; font-weight: bold;">Asistente:</span><br>
                {texto_html}
            </div>
        </div>
        """
        self.visor_chat.append(html)
        self.scroll_al_final()

    def agregar_mensaje_accion(self, nombre_accion: str, detalles: str):
        icono = "⚡"
        if "clima" in nombre_accion or "tiempo" in nombre_accion:
            icono = "🌤️"
        elif "recordatorio" in nombre_accion:
            icono = "⏰"
        elif "carpeta" in nombre_accion:
            icono = "📁"
        elif "documento" in nombre_accion or "archivo" in nombre_accion:
            icono = "📄"
        elif "youtube" in nombre_accion:
            icono = "▶️"
        elif "web" in nombre_accion or "navegador" in nombre_accion:
            icono = "🌐"
        elif "programa" in nombre_accion:
            icono = "🚀"

        html = f"""
        <div style="margin: 4px 0; text-align: center;">
            <span style="font-size: 11px; background-color: #24273a; color: #f9e2af; 
                         padding: 3px 10px; border-radius: 8px; border: 1px solid #45475a;">
                {icono} Ejecutando <b>{nombre_accion}</b>
            </span>
        </div>
        """
        self.visor_chat.append(html)
        self.scroll_al_final()

    def agregar_mensaje_sistema(self, texto: str):
        html = f"""
        <div style="margin: 6px 0; text-align: center;">
            <span style="font-size: 12px; color: #a6adc8; font-style: italic;">
                {texto}
            </span>
        </div>
        """
        self.visor_chat.append(html)
        self.scroll_al_final()

    def scroll_al_final(self):
        cursor = self.visor_chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.visor_chat.setTextCursor(cursor)

    def enviar_mensaje(self):
        texto = self.input_texto.toPlainText().strip()
        if not texto:
            return

        self.input_texto.clear()
        self.agregar_mensaje_usuario(texto)

        self.set_estado_pensando(True)
        detener_habla()

        self.hilo_proceso = HiloProcesarMensaje(self.agente, texto)
        self.hilo_proceso.senal_accion.connect(self.agregar_mensaje_accion)
        self.hilo_proceso.senal_finalizado.connect(self.on_respuesta_recibida)
        self.hilo_proceso.senal_error.connect(self.on_error_recibido)
        self.hilo_proceso.start()

    def set_estado_pensando(self, pensando: bool):
        if pensando:
            self.lbl_estado.setText("🟡 Pensando...")
            self.lbl_estado.setStyleSheet("color: #f9e2af;")
            self.btn_enviar.setEnabled(False)
            self.btn_mic.setEnabled(False)
        else:
            self.lbl_estado.setText("🟢 Listo")
            self.lbl_estado.setStyleSheet("color: #a6adc8;")
            self.btn_enviar.setEnabled(True)
            self.btn_mic.setEnabled(True)

    def on_respuesta_recibida(self, respuesta: str):
        self.set_estado_pensando(False)
        self.agregar_mensaje_asistente(respuesta)

        if self.leer_voz:
            self.lbl_estado.setText("🔊 Hablando...")
            self.lbl_estado.setStyleSheet("color: #89b4fa;")

            def al_terminar_habla():
                QTimer.singleShot(0, lambda: self.lbl_estado.setText("🟢 Listo"))

            hablar(respuesta, callback_fin=al_terminar_habla)

    def on_error_recibido(self, error: str):
        self.set_estado_pensando(False)
        self.agregar_mensaje_sistema(f"❌ Error: {error}")

    def toggle_grabacion(self):
        if not self.grabando:
            detener_habla()
            self.grabando = True
            self.btn_mic.setText("⏹️")
            self.btn_mic.setStyleSheet("""
                QPushButton {
                    background-color: #f38ba8;
                    color: #11111b;
                    border: 2px solid #eba0ac;
                    border-radius: 22px;
                    font-size: 16px;
                }
            """)
            self.lbl_estado.setText("🔴 Grabando voz...")
            self.lbl_estado.setStyleSheet("color: #f38ba8;")

            self.hilo_voz = HiloGrabacionVoz()
            self.hilo_voz.senal_progreso.connect(lambda msg: self.lbl_estado.setText(f"🔴 {msg}"))
            self.hilo_voz.senal_transcrito.connect(self.on_audio_transcrito)
            self.hilo_voz.start()
        else:
            self.grabando = False
            self.btn_mic.setText("🎙️")
            self.btn_mic.setStyleSheet("""
                QPushButton {
                    background-color: #313244;
                    border: 1px solid #45475a;
                    border-radius: 22px;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: #45475a;
                    border-color: #89b4fa;
                }
            """)
            self.lbl_estado.setText("⏳ Procesando voz...")
            if self.hilo_voz:
                self.hilo_voz.detener()

    def on_audio_transcrito(self, texto: str):
        self.lbl_estado.setText("🟢 Listo")
        self.lbl_estado.setStyleSheet("color: #a6adc8;")
        if texto.strip():
            self.input_texto.setPlainText(texto)
            self.enviar_mensaje()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mi Asistente IA")

    cfg = cargar_config()
    modelo_path = cfg.get("modelo_path", "")

    # Si se pasó el argumento --config, abrir directamente la ventana de configuración
    if "--config" in sys.argv:
        dialogo = DialogoConfiguracion(es_primera_vez=False)
        dialogo.exec()
        sys.exit(0)

    # Si es primera vez o el archivo de modelo no existe, mostrar diálogo de selección inicial
    if cfg.get("primera_vez", True) or not os.path.isfile(modelo_path):
        dialogo_inicial = DialogoConfiguracion(es_primera_vez=True)
        if dialogo_inicial.exec() != QDialog.DialogCode.Accepted:
            # El usuario cerró el diálogo sin seleccionar modelo
            sys.exit(0)

    ventana = VentanaAsistente()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
