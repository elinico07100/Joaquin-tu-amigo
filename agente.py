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
import urllib.request
from openai import OpenAI
from herramientas import TOOLS_DEFINITIONS, ejecutar_herramienta, normalizar_ruta
from config import cargar_config, verificar_servidor_listo

SISTEMA_OPERATIVO = platform.system()


PROMPT_SISTEMA = (
    f"Sos un asistente de escritorio personal eficiente y proactivo que corre localmente en la PC del usuario.\n"
    f"Sistema Operativo: Linux Mint ({platform.platform()}).\n"
    f"Idioma principal: Español.\n\n"
    "Tenés acceso a herramientas REALES integradas con el sistema. Nunca digas que no podés interactuar "
    "con el sistema, abrir programas, navegar por internet, crear carpetas o editar archivos: SÍ PODÉS "
    "usando las funciones (tools) disponibles.\n\n"
    "ESTRUCTURA DE ARCHIVOS Y REGLAS CRÍTICAS:\n"
    "1. Las carpetas principales del usuario están en español: '~/Escritorio', '~/Documentos', "
    "'~/Descargas', '~/Imágenes', '~/Música', '~/Vídeos'. NUNCA uses '~/Desktop' o 'Desktop', usá SIEMPRE '~/Escritorio'.\n"
    "2. Cuando el usuario te pida 'iniciar una carpeta', 'crear una carpeta' o 'hacer una carpeta', "
    "DEBES llamar a 'crear_carpeta'. Si te pide iniciarla en el escritorio y solo da un nombre (ej: 'inicia una carpeta proyectos'), "
    "usá '~/Escritorio/proyectos'.\n"
    "3. Para crear archivos o documentos (como .txt, notas, scripts), usá 'crear_documento'.\n"
    "4. Para abrir una carpeta en la ventana del explorador de archivos gráfico, usá 'abrir_carpeta'.\n"
    "5. Para eliminar archivos o carpetas, usá 'eliminar_documento' o 'eliminar_carpeta' (se envían a la papelera por seguridad).\n"
    "6. Para buscar archivos o carpetas por nombre, usá 'buscar_archivo'.\n"
    "7. Para explorar una carpeta específica, usá 'listar_archivos'.\n"
    "8. Para buscar información actual en internet, usá 'buscar_web'.\n"
    "9. Para abrir YouTube o buscar videos en YouTube, usá 'abrir_youtube' o 'buscar_youtube'.\n"
    "10. Para abrir páginas o sitios web generales en el navegador, usá 'abrir_navegador'.\n"
    "11. Para abrir programas como VS Code, navegador, terminal, usá 'abrir_programa'.\n\n"
    "FORMATO DE RESPUESTA:\n"
    "- Respondé en español claro, conciso y directo.\n"
    "- Cuando ejecutes una herramienta y recibas el resultado, confirmale al usuario amablemente lo que hiciste "
    "mencionando la ruta completa o el resultado obtenido."
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


class AgenteAsistente:
    def __init__(self):
        self.config = {}
        self.base_url = ""
        self.modelo = ""
        self.client = None
        self.actualizar_configuracion()
        self.historial = [
            {"role": "system", "content": PROMPT_SISTEMA}
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
            {"role": "system", "content": PROMPT_SISTEMA}
        ]

    def procesar_mensaje(self, mensaje_usuario: str, callback_accion=None) -> str:
        """Procesa un mensaje del usuario, ejecuta herramientas si es necesario,
        y devuelve la respuesta final en texto."""
        asegurar_servidor_activo()

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

            # Caso 3: Respuesta final para el usuario
            self.historial.append({"role": "assistant", "content": contenido_texto})
            return contenido_texto

        return "Se alcanzó el límite de pasos para completar la solicitud."
