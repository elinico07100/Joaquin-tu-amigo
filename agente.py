"""
Núcleo del Agente Inteligente:
- Conexión al servidor local de llama.cpp (OpenAI compatible en http://127.0.0.1:1234/v1).
- Verificación automática y arranque del servicio si está inactivo.
- Procesamiento de turnos, parsing robusto de herramientas y ejecución en bucle.
"""

import json
import os
import re
import time
import subprocess
import platform
import datetime
import urllib.request
from openai import OpenAI
from herramientas import TOOLS_DEFINITIONS, ejecutar_herramienta, normalizar_ruta
from config import cargar_config, verificar_servidor_listo

SISTEMA_OPERATIVO = platform.system()

DIAS_ESP = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_ESP = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def obtener_prompt_sistema() -> str:
    """Genera el prompt de sistema dinámico con la fecha y hora real exacta."""
    ahora = datetime.datetime.now()
    fecha_hoy = f"{DIAS_ESP[ahora.weekday()]} {ahora.day} de {MESES_ESP[ahora.month]} de {ahora.year}"
    hora_actual = ahora.strftime("%H:%M")

    return (
        f"Sos un asistente de escritorio personal eficiente, proactivo y autónomo que corre localmente en la PC del usuario.\n"
        f"Sistema Operativo: Linux Mint ({platform.platform()}).\n"
        f"Idioma principal: Español rioplatense / latino natural.\n"
        f"FECHA Y HORA ACTUAL DEL SISTEMA: {fecha_hoy}, {hora_actual} hs.\n\n"
        "REGLAS CRÍTICAS DE HERRAMIENTAS Y ACCESO EN TIEMPO REAL:\n"
        "1. SÍ TENÉS ACCESO A INTERNET Y DATOS EN TIEMPO REAL: NUNCA digas que no podés acceder a internet, que no tenés datos en tiempo real, que no podés saber el clima o que tu conocimiento está limitado a cierta fecha. ¡SÍ PODÉS! Tenés herramientas conectadas directamente y tu deber es invocarlas.\n"
        "2. CLIMA Y PRONÓSTICO: Si el usuario te pregunta por el clima, tiempo meteorológico, temperatura o pronóstico de cualquier lugar, LLAMÁ SIEMPRE a la herramienta 'obtener_clima'. Si no menciona ciudad, asumí 'Buenos Aires'.\n"
        "3. RECORDATORIOS Y AGENDA:\n"
        "   - Cuando el usuario te pida recordar algo o agendar un evento (ej: 'haceme un recordatorio para el domingo 17 de noviembre hay una competencia'), LLAMÁ A 'crear_recordatorio'.\n"
        "   - IMPORTANCIA Y PRIORIDAD: Cada recordatorio debe tener una prioridad ('Alta', 'Media', 'Baja'). Asignala de manera inteligente: eventos críticos, competencias, exámenes, turnos médicos, pagos o viajes son 'Alta'; tareas de trabajo/estudio son 'Media'; cosas casuales son 'Baja'.\n"
        "   - Cuando te pidan ver, listar o consultar qué tareas o recordatorios hay pendientes, LLAMÁ A 'listar_recordatorios'. Muestran la prioridad con 🔴, 🟡 y 🟢.\n"
        "   - Para borrar o completar recordatorios, usá 'eliminar_recordatorio' o 'marcar_recordatorio_completado'.\n"
        "4. BÚSQUEDA WEB: Para noticias, hechos actuales, búsquedas en internet o información general, usá 'buscar_web'.\n"
        "5. ARCHIVOS Y CARPETAS:\n"
        "   - Carpetas principales en español: '~/Escritorio', '~/Documentos', '~/Descargas', '~/Imágenes', '~/Música', '~/Vídeos'. NUNCA uses '~/Desktop', usá '~/Escritorio'.\n"
        "   - Para crear carpetas: 'crear_carpeta'.\n"
        "   - Para crear archivos o notas: 'crear_documento'.\n"
        "   - Para abrir carpetas en el explorador gráfico Nemo: 'abrir_carpeta'.\n"
        "   - Para eliminar a la papelera segura: 'eliminar_documento' o 'eliminar_carpeta'.\n"
        "   - Para buscar archivos por nombre: 'buscar_archivo'.\n"
        "   - Para ver contenidos de carpetas: 'listar_archivos'.\n"
        "6. MULTIMEDIA Y PROGRAMAS:\n"
        "   - Para YouTube: 'abrir_youtube' o 'buscar_youtube'.\n"
        "   - Para abrir sitios web: 'abrir_navegador'.\n"
        "   - Para lanzar aplicaciones del sistema: 'abrir_programa'.\n\n"
        "FORMATO DE RESPUESTA:\n"
        "- Respondé en español claro, conciso, educado y directo.\n"
        "- Si ejecutaste una herramienta, confirmale al usuario el resultado de forma agradable y clara."
    )



def asegurar_servidor_activo() -> bool:
    """Verifica si el servidor de llama.cpp en el host:puerto configurado responde.
    Si no responde, intenta levantarlo mediante el servicio systemd del usuario."""
    cfg = cargar_config()
    url = f"http://{cfg.get('host', '127.0.0.1')}:{cfg.get('puerto', 1234)}/v1/models"
    if verificar_servidor_listo(url, timeout=1.5):
        return True

    print("[SISTEMA] Servidor de modelo inactivo. Intentando iniciar servicio asistente-modelo...")
    try:
        subprocess.run(["systemctl", "--user", "start", "asistente-modelo.service"], check=False)
    except Exception as e:
        print(f"[SISTEMA] Error al iniciar servicio: {e}")

    # Esperar hasta 25 segundos a que el modelo cargue en GPU/RAM
    for i in range(25):
        time.sleep(1.0)
        if verificar_servidor_listo(url, timeout=1.0):
            print(f"[SISTEMA] Servidor de modelo iniciado y listo en {i+1}s.")
            return True

    return False


def extraer_llamadas_herramientas(contenido: str):
    """Extrae llamadas a herramientas de texto (fallback para modelos que devuelven JSON o tags)."""
    llamadas = []
    if not contenido:
        return llamadas

    # 1. Tags <tool_call> ... </tool_call>
    tool_blocks = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", contenido, re.DOTALL)
    for block in tool_blocks:
        try:
            data = json.loads(block.strip())
            if "name" in data:
                args = data.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                llamadas.append((data["name"], args))
        except Exception:
            pass

    if llamadas:
        return llamadas

    # 2. Bloques markdown de json ```json ... ``` o ``` ... ```
    code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", contenido, re.DOTALL)
    for block in code_blocks:
        try:
            data = json.loads(block.strip())
            if "name" in data and "arguments" in data:
                args = data["arguments"]
                if isinstance(args, str):
                    args = json.loads(args)
                llamadas.append((data["name"], args))
        except Exception:
            pass

    if llamadas:
        return llamadas

    # 3. Objeto JSON suelto en el texto
    matches = re.finditer(r"\{[^{}]*\"name\"\s*:\s*\"([^\"]+)\"[^{}]*\"arguments\"\s*:\s*(\{.*?\})\s*\}", contenido, re.DOTALL)
    for m in matches:
        try:
            nombre = m.group(1)
            args = json.loads(m.group(2))
            llamadas.append((nombre, args))
        except Exception:
            pass

    return llamadas


def detectar_intencion_directa(mensaje_usuario: str) -> tuple:
    """Detecta intenciones críticas (clima, recordatorios, búsqueda) como salvaguarda
    si el modelo rechaza erróneamente aduciendo no tener acceso a internet."""
    msg = mensaje_usuario.lower()

    if any(k in msg for k in ["clima", "temperatura", "que tiempo hace", "qué tiempo hace", "pronostico", "pronóstico", "tiempo hoy"]):
        palabras = [p for p in mensaje_usuario.split() if p.lower() not in (
            "clima", "temperatura", "del", "el", "de", "en", "hoy", "actual", "hace",
            "que", "qué", "tiempo", "esta", "está", "como", "cómo", "decime", "dime", "saber"
        )]
        ciudad = " ".join(palabras) if palabras else "Buenos Aires"
        return "obtener_clima", {"ciudad": ciudad}

    if any(k in msg for k in [
        "que tengo agendado", "qué tengo agendado", "mis recordatorios", "ver recordatorios",
        "mostrar recordatorios", "listar recordatorios", "que tengo que hacer", "qué tengo que hacer",
        "que compromisos tengo", "qué compromisos tengo"
    ]):
        return "listar_recordatorios", {}

    return None, {}


class AgenteAsistente:
    def __init__(self):
        self.config = {}
        self.base_url = ""
        self.modelo = ""
        self.client = None
        self.actualizar_configuracion()
        self.historial = [
            {"role": "system", "content": obtener_prompt_sistema()}
        ]

    def actualizar_configuracion(self):
        """Recarga la configuración desde config.json y actualiza el cliente."""
        self.config = cargar_config()
        self.base_url = f"http://{self.config.get('host', '127.0.0.1')}:{self.config.get('puerto', 1234)}/v1"
        self.modelo = self.config.get("modelo_nombre", "default")
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="no-key-needed"
        )

    def reiniciar_conversacion(self):
        self.historial = [
            {"role": "system", "content": obtener_prompt_sistema()}
        ]

    def procesar_mensaje(self, mensaje_usuario: str, callback_accion=None) -> str:
        """Procesa un mensaje del usuario, ejecuta herramientas si es necesario,
        y devuelve la respuesta final en texto."""
        asegurar_servidor_activo()

        # Mantener el prompt del sistema actualizado con la hora y fecha exacta
        if self.historial and self.historial[0]["role"] == "system":
            self.historial[0]["content"] = obtener_prompt_sistema()

        self.historial.append({"role": "user", "content": mensaje_usuario})

        MAX_ITERACIONES = 5
        iteracion = 0

        while iteracion < MAX_ITERACIONES:
            iteracion += 1

            try:
                respuesta = self.client.chat.completions.create(
                    model="default",
                    messages=self.historial,
                    tools=TOOLS_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.3
                )
            except Exception as e:
                error_msg = f"Error al comunicar con el modelo: {e}"
                print(f"[AGENTE] {error_msg}")
                return error_msg

            mensaje = respuesta.choices[0].message

            # Caso 1: API nativa con tool_calls
            if mensaje.tool_calls:
                self.historial.append(mensaje)
                for llamada in mensaje.tool_calls:
                    nombre = llamada.function.name
                    try:
                        args = json.loads(llamada.function.arguments)
                    except Exception:
                        args = {}

                    if callback_accion:
                        callback_accion(nombre, args)

                    resultado = ejecutar_herramienta(nombre, args)

                    self.historial.append({
                        "role": "tool",
                        "tool_call_id": llamada.id,
                        "content": str(resultado)
                    })
                continue

            # Caso 2: El modelo devolvió el tool call en el texto
            contenido_texto = mensaje.content or ""
            llamadas_texto = extraer_llamadas_herramientas(contenido_texto)

            if llamadas_texto:
                self.historial.append({"role": "assistant", "content": contenido_texto})
                for nombre, args in llamadas_texto:
                    if callback_accion:
                        callback_accion(nombre, args)

                    resultado = ejecutar_herramienta(nombre, args)
                    self.historial.append({
                        "role": "user",
                        "content": f"[Resultado de la herramienta '{nombre}']: {resultado}\n\nCon esta información, responde al usuario."
                    })
                continue

            # Salvaguarda: si en la primera iteración el modelo respondió que no puede acceder
            # a internet o al clima, pero la intención es clara, forzamos la herramienta
            if iteracion == 1:
                es_rechazo = any(frase in contenido_texto.lower() for frase in [
                    "no puedo acceder a internet", "no tengo acceso a internet", "no puedo navegar",
                    "no tengo la capacidad de buscar", "no puedo ver el clima", "no puedo saber el clima",
                    "como modelo de lenguaje", "no tengo acceso en tiempo real", "no dispongo de información en tiempo real"
                ])
                intencion_herramienta, intencion_args = detectar_intencion_directa(mensaje_usuario)
                if (es_rechazo or intencion_herramienta) and intencion_herramienta:
                    if callback_accion:
                        callback_accion(intencion_herramienta, intencion_args)
                    resultado = ejecutar_herramienta(intencion_herramienta, intencion_args)
                    self.historial.append({
                        "role": "user",
                        "content": (
                            f"[Herramienta del sistema '{intencion_herramienta}' ejecutada automáticamente con argumentos {intencion_args}]:\n"
                            f"{resultado}\n\n"
                            "Con estos datos reales obtenidos ahora mismo, responde amablemente y con precisión a la pregunta del usuario."
                        )
                    })
                    continue

            # Caso 3: Respuesta final para el usuario
            self.historial.append({"role": "assistant", "content": contenido_texto})
            return contenido_texto

        return "Se alcanzó el límite de pasos para completar la solicitud."
