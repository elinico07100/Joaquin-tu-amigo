"""
Módulo de voz para el Asistente:
- STT (Speech-to-Text): Transcripción de voz a texto usando Whisper (CUDA/CPU) con carga diferida.
- TTS (Text-to-Speech): Síntesis de voz usando edge-tts (voz en español natural es-AR-TomasNeural) con fallback.
"""

import os
import threading
import queue
import time
import asyncio
import numpy as np
import sounddevice as sd

# Variables globales para carga diferida (lazy loading)
_modelo_whisper = None
_whisper_lock = threading.Lock()

_reproduciendo_audio = False
_hilo_habla = None


def get_whisper():
    """Carga el modelo Whisper de manera diferida para acelerar el inicio."""
    global _modelo_whisper
    with _whisper_lock:
        if _modelo_whisper is None:
            from faster_whisper import WhisperModel
            print("\n[VOZ] Cargando modelo Whisper (small)...")
            try:
                _modelo_whisper = WhisperModel("small", device="cuda", compute_type="float16")
                print("[VOZ] Whisper cargado con aceleración CUDA.")
            except Exception:
                print("[VOZ] CUDA no disponible para Whisper, usando CPU (int8)...")
                _modelo_whisper = WhisperModel("small", device="cpu", compute_type="int8")
        return _modelo_whisper


def combinar_con_solape(texto_previo: str, texto_nuevo: str) -> str:
    """Evita repetición de palabras en la ventana deslizante."""
    palabras_previas = texto_previo.split()
    palabras_nuevas = texto_nuevo.split()
    max_solape = min(len(palabras_previas), len(palabras_nuevas), 10)
    coincidencia = 0
    for n in range(max_solape, 0, -1):
        if palabras_previas[-n:] == palabras_nuevas[:n]:
            coincidencia = n
            break
    return " ".join(palabras_nuevas[coincidencia:])


def grabar_y_transcribir_en_vivo(evento_detener: threading.Event = None, callback_progreso=None) -> str:
    """Graba audio y transcribe en vivo. Si evento_detener es None, espera Enter por teclado."""
    whisper = get_whisper()
    SAMPLERATE = 16000
    DURACION_VENTANA = 4
    SOLAPE = 1
    AVANCE = DURACION_VENTANA - SOLAPE

    cola_audio = queue.Queue()
    detener = evento_detener if evento_detener is not None else threading.Event()
    texto_completo = []

    def callback_stream(indata, frames, time_info, status):
        cola_audio.put(indata.copy())

    def hilo_transcripcion():
        buffer_ventana = np.zeros((0, 1), dtype="float32")
        muestras_avance = int(SAMPLERATE * AVANCE)
        muestras_ventana = int(SAMPLERATE * DURACION_VENTANA)
        ultimo_texto = ""

        while not detener.is_set() or not cola_audio.empty():
            try:
                bloque = cola_audio.get(timeout=0.2)
            except queue.Empty:
                continue

            buffer_ventana = np.concatenate([buffer_ventana, bloque], axis=0)
            listo = len(buffer_ventana) >= muestras_avance
            forzar_final = detener.is_set() and cola_audio.empty() and len(buffer_ventana) > SAMPLERATE * 0.3

            if listo or forzar_final:
                ventana = buffer_ventana[-muestras_ventana:] if len(buffer_ventana) > muestras_ventana else buffer_ventana
                audio_plano = ventana.flatten()

                try:
                    segmentos, _ = whisper.transcribe(audio_plano, language="es")
                    texto_ventana = " ".join(seg.text.strip() for seg in segmentos).strip()
                except Exception as e:
                    print(f"[VOZ] Error en transcripción: {e}")
                    texto_ventana = ""

                if texto_ventana:
                    nuevo = combinar_con_solape(ultimo_texto, texto_ventana)
                    if nuevo:
                        texto_completo.append(nuevo)
                        if callback_progreso:
                            callback_progreso(" ".join(texto_completo))
                        else:
                            print(f"  📝 {nuevo}")
                    ultimo_texto = texto_ventana

                muestras_conservar = int(SAMPLERATE * SOLAPE)
                buffer_ventana = buffer_ventana[-muestras_conservar:] if muestras_conservar > 0 else np.zeros((0, 1), dtype="float32")

                if forzar_final:
                    break

    hilo = threading.Thread(target=hilo_transcripcion, daemon=True)

    try:
        with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="float32", callback=callback_stream):
            hilo.start()
            if evento_detener is None:
                print("\n🎤 Grabando... Presioná Enter para terminar de hablar.\n")
                input()
                detener.set()
            hilo.join(timeout=10)
    except Exception as e:
        print(f"[VOZ] Error accediendo al micrófono: {e}")
        return ""

    resultado = " ".join(texto_completo).strip()
    return resultado


def grabar_audio_pulsado(evento_grabando: threading.Event) -> np.ndarray:
    """Graba audio mientras evento_grabando esté activo."""
    SAMPLERATE = 16000
    cola = queue.Queue()

    def callback(indata, frames, time_info, status):
        if evento_grabando.is_set():
            cola.put(indata.copy())

    with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="float32", callback=callback):
        while evento_grabando.is_set():
            time.sleep(0.05)

    trozos = []
    while not cola.empty():
        trozos.append(cola.get())

    if not trozos:
        return np.zeros(0, dtype="float32")
    return np.concatenate(trozos, axis=0).flatten()


def transcribir_array_audio(audio: np.ndarray) -> str:
    """Transcribe un arreglo numpy de audio directamente."""
    if len(audio) < 16000 * 0.3:  # Menos de 300 ms
        return ""
    whisper = get_whisper()
    try:
        segmentos, _ = whisper.transcribe(audio, language="es")
        return " ".join(seg.text.strip() for seg in segmentos).strip()
    except Exception as e:
        print(f"[VOZ] Error en transcripción directa: {e}")
        return ""


def detener_habla():
    """Detiene cualquier reproducción de voz actual."""
    global _reproduciendo_audio
    _reproduciendo_audio = False
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def _reproducir_texto_hilo(texto: str, voz: str = "es-AR-TomasNeural", callback_fin=None):
    global _reproduciendo_audio
    _reproduciendo_audio = True

    # Limpiar formato markdown para que el TTS lea con fluidez
    texto_limpio = texto.replace("*", "").replace("#", "").replace("`", "").replace("> ", "")
    # Quitar URLs largas
    import re
    texto_limpio = re.sub(r'https?://\S+', 'enlace', texto_limpio)
    # Truncar si es excesivamente largo para no monopolizar el audio
    if len(texto_limpio) > 1200:
        texto_limpio = texto_limpio[:1200] + "... y más detalles en pantalla."

    if not texto_limpio.strip():
        if callback_fin:
            callback_fin()
        return

    archivo_temp = "/tmp/asistente_voz.mp3"

    try:
        import edge_tts
        import pygame

        async def _generar():
            com = edge_tts.Communicate(texto_limpio, voz)
            await com.save(archivo_temp)

        asyncio.run(_generar())

        if not _reproduciendo_audio:
            if callback_fin:
                callback_fin()
            return

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(archivo_temp)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy() and _reproduciendo_audio:
            time.sleep(0.1)

    except Exception as e:
        print(f"[VOZ] Fallo edge-tts ({e}), intentando fallback con spd-say...")
        try:
            import subprocess
            subprocess.run(["spd-say", "-l", "es", texto_limpio[:250]], check=False)
        except Exception:
            pass

    _reproduciendo_audio = False
    if callback_fin:
        try:
            callback_fin()
        except Exception:
            pass


def hablar(texto: str, voz: str = "es-AR-TomasNeural", callback_fin=None):
    """Sintetiza y reproduce el texto en segundo plano de manera no bloqueante."""
    global _hilo_habla
    detener_habla()
    _hilo_habla = threading.Thread(
        target=_reproducir_texto_hilo,
        args=(texto, voz, callback_fin),
        daemon=True
    )
    _hilo_habla.start()
