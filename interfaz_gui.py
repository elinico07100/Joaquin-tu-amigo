"""
Interfaz Gráfica Moderna para Mi Asistente IA (PyQt6).
Características:
- Ventana compacta estilo Spotlight / Asistente flotante.
- Tema oscuro moderno con burbujas de chat estilizadas.
- Botón de micrófono para dictado por voz (Whisper STT).
- Botón de voz en alta voz (TTS con edge-tts en español).
- Ejecución asíncrona en hilos para una interfaz siempre fluida.
- Atajos de teclado (Enter para enviar, Esc para minimizar/ocultar).
"""

import sys
import os
import threading
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextBrowser, QTextEdit, QPushButton, QLabel, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QTextCursor

from agente import AgenteAsistente
from voz import (
    hablar, detener_habla, get_whisper,
    grabar_audio_pulsado, transcribir_array_audio
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
        self.agente = AgenteAsistente()
        self.leer_voz = False
        self.grabando = False
        self.hilo_voz = None
        self.hilo_proceso = None

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Mi Asistente IA")
        self.setMinimumSize(480, 620)
        self.resize(520, 680)

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

        self.lbl_estado = QLabel("🟢 Listo")
        self.lbl_estado.setFont(QFont("Ubuntu", 10))
        self.lbl_estado.setStyleSheet("color: #a6adc8; margin-left: 8px;")
        barra_superior.addWidget(self.lbl_estado)

        barra_superior.addStretch()

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
            "¡Hola! Soy tu asistente de escritorio. Puedo ayudarte a crear y organizar carpetas, "
            "documentos, abrir programas, buscar en la web y responder lo que necesites."
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
        else:
            super().keyPressEvent(event)

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
        # Convertir saltos de línea a <br> y enlaces
        texto_html = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        texto_html = texto_html.replace("\n", "<br>")
        # Negrita básica
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
        if "carpeta" in nombre_accion:
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
                # Volver a estado listo en el hilo de la UI
                QTimer.singleShot(0, lambda: self.lbl_estado.setText("🟢 Listo"))

            hablar(respuesta, callback_fin=al_terminar_habla)

    def on_error_recibido(self, error: str):
        self.set_estado_pensando(False)
        self.agregar_mensaje_sistema(f"❌ Error: {error}")

    def toggle_grabacion(self):
        if not self.grabando:
            # Iniciar grabación
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
            # Detener grabación
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
    ventana = VentanaAsistente()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
