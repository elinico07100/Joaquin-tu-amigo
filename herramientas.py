"""
Módulo de herramientas del Asistente Personal.
Provee funciones para:
- Crear, abrir, listar, buscar y eliminar carpetas (con papelera segura).
- Crear, leer, modificar y eliminar documentos/archivos.
- Mover y renombrar archivos y carpetas.
- Buscar en la web (DuckDuckGo), YouTube y abrir navegador.
- Abrir aplicaciones del sistema.
- RAG: consultar documentos propios indexados.
"""

import os
import shutil
import subprocess
import webbrowser
import platform
import json
import urllib.request
import urllib.parse
from ddgs import DDGS
from recordatorios import (
    crear_recordatorio, listar_recordatorios,
    eliminar_recordatorio, marcar_recordatorio_completado
)

SISTEMA_OPERATIVO = platform.system()  # 'Linux', 'Windows', 'Darwin'
HOME_DIR = os.path.expanduser("~")

# Mapeo de nombres en inglés/variantes a carpetas reales en Linux en español
MAPEO_CARPETAS_ESP = {
    "desktop": "Escritorio",
    "escritorio": "Escritorio",
    "documents": "Documentos",
    "documentos": "Documentos",
    "downloads": "Descargas",
    "descargas": "Descargas",
    "pictures": "Imágenes",
    "imagenes": "Imágenes",
    "imágenes": "Imágenes",
    "music": "Música",
    "musica": "Música",
    "música": "Música",
    "videos": "Vídeos",
    "vídeos": "Vídeos"
}

RUTAS_PROTEGIDAS = {
    "/",
    "/root",
    HOME_DIR,
    os.path.join(HOME_DIR, "Escritorio"),
    os.path.join(HOME_DIR, "Documentos"),
    os.path.join(HOME_DIR, "Descargas"),
    os.path.join(HOME_DIR, "Imágenes"),
    os.path.join(HOME_DIR, "Música"),
    os.path.join(HOME_DIR, "Vídeos"),
    "/bin", "/usr", "/etc", "/var", "/lib", "/boot", "/dev", "/proc", "/sys"
}


def normalizar_ruta(ruta: str) -> str:
    """Normaliza rutas relativas, tildes (~), y carpetas estándar en español/inglés."""
    if not ruta:
        return HOME_DIR

    ruta = ruta.strip().strip("'").strip('"')

    # Reemplazar ~ por HOME
    if ruta.startswith("~/"):
        ruta = os.path.join(HOME_DIR, ruta[2:])
    elif ruta == "~":
        return HOME_DIR
    elif not ruta.startswith("/"):
        # Ruta relativa
        partes = ruta.split(os.sep)
        primero_lower = partes[0].lower()
        if primero_lower in MAPEO_CARPETAS_ESP:
            partes[0] = MAPEO_CARPETAS_ESP[primero_lower]
            ruta = os.path.join(HOME_DIR, *partes)
        else:
            # Si no especifica carpeta raíz, asumimos que está en la carpeta personal
            ruta = os.path.join(HOME_DIR, ruta)

    # Reemplazar ~/Desktop si aparece en la ruta absoluta
    desktop_en = os.path.join(HOME_DIR, "Desktop")
    desktop_es = os.path.join(HOME_DIR, "Escritorio")
    if ruta.startswith(desktop_en):
        ruta = desktop_es + ruta[len(desktop_en):]

    return os.path.abspath(ruta)


def crear_carpeta(ruta: str) -> str:
    """Crea una carpeta o directorio nuevo en la ruta especificada."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Creando carpeta: {ruta_norm}")
    try:
        if os.path.exists(ruta_norm):
            if os.path.isdir(ruta_norm):
                return f"La carpeta ya existe en: {ruta_norm}"
            else:
                return f"Error: Ya existe un archivo con ese nombre en: {ruta_norm}"

        os.makedirs(ruta_norm, exist_ok=True)
        return f"Carpeta creada exitosamente en: {ruta_norm}"
    except Exception as e:
        return f"Error al crear la carpeta '{ruta_norm}': {e}"


def abrir_carpeta(ruta: str, crear_si_no_existe: bool = False) -> str:
    """Abre una carpeta en el explorador de archivos (Nemo/XDG).
    Si crear_si_no_existe es True y no existe, la crea primero."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Abriendo carpeta: {ruta_norm}")

    if not os.path.exists(ruta_norm):
        if crear_si_no_existe:
            try:
                os.makedirs(ruta_norm, exist_ok=True)
                print(f"[SISTEMA] Carpeta creada previamente para abrir: {ruta_norm}")
            except Exception as e:
                return f"Error al crear la carpeta '{ruta_norm}': {e}"
        else:
            return f"Error: La carpeta '{ruta_norm}' no existe."

    if not os.path.isdir(ruta_norm):
        return f"Error: '{ruta_norm}' no es una carpeta, es un archivo."

    try:
        if SISTEMA_OPERATIVO == "Windows":
            subprocess.Popen(f'explorer "{ruta_norm}"')
        elif SISTEMA_OPERATIVO == "Darwin":
            subprocess.Popen(["open", ruta_norm])
        else:
            subprocess.Popen(["xdg-open", ruta_norm])
        return f"Carpeta abierta en el explorador de archivos: {ruta_norm}"
    except Exception as e:
        return f"Error al abrir la carpeta: {e}"


def eliminar_carpeta(ruta: str, usar_papelera: bool = True) -> str:
    """Elimina una carpeta de forma segura. Por defecto la envía a la papelera de reciclaje."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Eliminando carpeta: {ruta_norm}")

    if not os.path.exists(ruta_norm):
        return f"Error: La carpeta '{ruta_norm}' no existe."

    if not os.path.isdir(ruta_norm):
        return f"Error: '{ruta_norm}' no es una carpeta. Usá eliminar_documento para archivos."

    # Comprobación de seguridad
    if ruta_norm in RUTAS_PROTEGIDAS or os.path.dirname(ruta_norm) == "/":
        return f"Acción denegada: '{ruta_norm}' es una carpeta protegida del sistema o del usuario."

    if usar_papelera:
        # Intentar enviar a la papelera con gio trash (estándar en Linux Mint / GNOME)
        try:
            res = subprocess.run(["gio", "trash", ruta_norm], capture_output=True, text=True)
            if res.returncode == 0:
                return f"Carpeta '{ruta_norm}' enviada a la Papelera de reciclaje (se puede restaurar si querés)."
        except Exception:
            pass

    # Si falla la papelera o no se usa papelera
    try:
        shutil.rmtree(ruta_norm)
        return f"Carpeta '{ruta_norm}' eliminada permanentemente con todo su contenido."
    except Exception as e:
        return f"Error al eliminar la carpeta '{ruta_norm}': {e}"


def crear_documento(ruta: str, contenido: str = "") -> str:
    """Crea un nuevo documento o archivo de texto en la ruta especificada."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Creando documento: {ruta_norm}")

    try:
        dir_padre = os.path.dirname(ruta_norm)
        if dir_padre and not os.path.exists(dir_padre):
            os.makedirs(dir_padre, exist_ok=True)

        with open(ruta_norm, "w", encoding="utf-8") as f:
            f.write(contenido)

        return f"Documento creado exitosamente en: {ruta_norm} (tamaño: {len(contenido)} caracteres)"
    except Exception as e:
        return f"Error al crear el documento '{ruta_norm}': {e}"


def leer_documento(ruta: str) -> str:
    """Lee y devuelve el contenido de texto de un archivo específico."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Leyendo documento: {ruta_norm}")

    if not os.path.exists(ruta_norm):
        return f"Error: El archivo '{ruta_norm}' no existe."

    if not os.path.isfile(ruta_norm):
        return f"Error: '{ruta_norm}' es una carpeta, no un archivo de texto."

    try:
        with open(ruta_norm, "r", encoding="utf-8", errors="ignore") as f:
            contenido = f.read()

        LIMITE = 4000
        if len(contenido) > LIMITE:
            contenido = contenido[:LIMITE] + f"\n\n[...contenido truncado, el archivo tiene {len(contenido)} caracteres en total...]"

        return contenido if contenido.strip() else "(El archivo está vacío)"
    except Exception as e:
        return f"Error al leer el archivo: {e}"


def modificar_documento(ruta: str, contenido: str, modo: str = "agregar") -> str:
    """Modifica un documento existente. 'modo' puede ser 'agregar' (append) o 'sobrescribir'."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Modificando documento ({modo}): {ruta_norm}")

    if not os.path.exists(ruta_norm):
        # Si no existe, lo creamos
        return crear_documento(ruta_norm, contenido)

    try:
        if modo.lower() == "agregar":
            with open(ruta_norm, "a", encoding="utf-8") as f:
                f.write("\n" + contenido)
            return f"Contenido agregado exitosamente al final de '{ruta_norm}'."
        else:
            with open(ruta_norm, "w", encoding="utf-8") as f:
                f.write(contenido)
            return f"Documento '{ruta_norm}' sobrescrito exitosamente."
    except Exception as e:
        return f"Error al modificar el documento: {e}"


def eliminar_documento(ruta: str, usar_papelera: bool = True) -> str:
    """Elimina un documento o archivo. Por defecto lo envía a la papelera."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Eliminando documento: {ruta_norm}")

    if not os.path.exists(ruta_norm):
        return f"Error: El archivo '{ruta_norm}' no existe."

    if not os.path.isfile(ruta_norm):
        return f"Error: '{ruta_norm}' no es un archivo, es una carpeta. Usá eliminar_carpeta."

    if usar_papelera:
        try:
            res = subprocess.run(["gio", "trash", ruta_norm], capture_output=True, text=True)
            if res.returncode == 0:
                return f"Archivo '{ruta_norm}' enviado a la Papelera de reciclaje."
        except Exception:
            pass

    try:
        os.remove(ruta_norm)
        return f"Archivo '{ruta_norm}' eliminado permanentemente."
    except Exception as e:
        return f"Error al eliminar el archivo: {e}"


def mover_o_renombrar(origen: str, destino: str) -> str:
    """Mueve o renombra un archivo o carpeta."""
    orig_norm = normalizar_ruta(origen)
    dest_norm = normalizar_ruta(destino)
    print(f"\n[SISTEMA] Moviendo/renombrando: {orig_norm} -> {dest_norm}")

    if not os.path.exists(orig_norm):
        return f"Error: El origen '{orig_norm}' no existe."

    try:
        dest_dir = os.path.dirname(dest_norm)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        shutil.move(orig_norm, dest_norm)
        return f"Operación exitosa: '{orig_norm}' movido/renombrado a '{dest_norm}'."
    except Exception as e:
        return f"Error al mover/renombrar: {e}"


def listar_archivos(ruta: str = "~") -> str:
    """Lista las carpetas y archivos dentro de una ruta dada."""
    ruta_norm = normalizar_ruta(ruta)
    print(f"\n[SISTEMA] Listando archivos en: {ruta_norm}")

    if not os.path.exists(ruta_norm):
        return f"Error: '{ruta_norm}' no existe."

    if not os.path.isdir(ruta_norm):
        return f"Error: '{ruta_norm}' no es una carpeta."

    try:
        entradas = os.listdir(ruta_norm)
    except PermissionError:
        return f"Error: sin permisos para leer '{ruta_norm}'."

    if not entradas:
        return f"La carpeta '{ruta_norm}' está vacía."

    carpetas = sorted([e for e in entradas if os.path.isdir(os.path.join(ruta_norm, e)) and not e.startswith(".")])
    archivos = sorted([e for e in entradas if os.path.isfile(os.path.join(ruta_norm, e)) and not e.startswith(".")])

    salida = [f"Contenido de {ruta_norm}:"]
    if carpetas:
        salida.append("📁 Carpetas: " + ", ".join(carpetas))
    if archivos:
        salida.append("📄 Archivos: " + ", ".join(archivos))

    return "\n".join(salida)


def buscar_archivo(nombre_archivo: str, carpeta_inicio: str = "~") -> str:
    """Busca archivos o carpetas recursivamente por coincidencia de nombre."""
    inicio_norm = normalizar_ruta(carpeta_inicio)
    print(f"\n[SISTEMA] Buscando '{nombre_archivo}' desde {inicio_norm}...")

    if not os.path.isdir(inicio_norm):
        return f"Error: '{inicio_norm}' no existe o no es una carpeta."

    LIMITE_RESULTADOS = 10
    termino = nombre_archivo.lower()
    encontrados = []

    for raiz, carpetas, archivos in os.walk(inicio_norm):
        carpetas[:] = [c for c in carpetas if not c.startswith(".")]

        for carpeta in carpetas:
            if termino in carpeta.lower():
                encontrados.append(f"📁 [Carpeta] {os.path.join(raiz, carpeta)}")
                if len(encontrados) >= LIMITE_RESULTADOS:
                    break

        for archivo in archivos:
            if termino in archivo.lower():
                encontrados.append(f"📄 [Archivo] {os.path.join(raiz, archivo)}")
                if len(encontrados) >= LIMITE_RESULTADOS:
                    break

        if len(encontrados) >= LIMITE_RESULTADOS:
            break

    if not encontrados:
        return f"No se encontró nada que coincida con '{nombre_archivo}' dentro de {inicio_norm}."

    return "Resultados encontrados:\n" + "\n".join(encontrados)


def obtener_clima(ciudad: str = "Buenos Aires") -> str:
    """Obtiene el pronóstico y clima actual en tiempo real para cualquier ciudad."""
    if not ciudad or not ciudad.strip():
        ciudad = "Buenos Aires"

    ciudad_limpia = ciudad.strip().strip("'").strip('"')
    print(f"\n[SISTEMA] Consultando clima en tiempo real para: '{ciudad_limpia}'")

    # 1. Intentar con wttr.in en español
    try:
        url = f"https://wttr.in/{urllib.parse.quote(ciudad_limpia)}?format=j1&lang=es"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode())
            current = data["current_condition"][0]
            temp = current.get("temp_C", "?")
            feels = current.get("FeelsLikeC", temp)
            desc_list = current.get("lang_es", [])
            desc = desc_list[0]["value"] if desc_list else current.get("weatherDesc", [{}])[0].get("value", "Condición variable")
            humedad = current.get("humidity", "")
            viento = current.get("windspeedKmph", "")

            pronostico_str = ""
            if "weather" in data and len(data["weather"]) > 0:
                hoy = data["weather"][0]
                t_max = hoy.get("maxtempC", "")
                t_min = hoy.get("mintempC", "")
                pronostico_str = f" | Mín: {t_min}°C, Máx: {t_max}°C"

            return (
                f"🌤️ Clima actual en {ciudad_limpia}: {desc}, {temp}°C (Sensación térmica: {feels}°C){pronostico_str}. "
                f"Humedad: {humedad}%, Viento: {viento} km/h."
            )
    except Exception as e_wttr:
        print(f"[CLIMA] wttr.in falló ({e_wttr}), buscando vía DuckDuckGo...")

    # 2. Fallback: DuckDuckGo
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(f"clima actual temperatura tiempo {ciudad_limpia}", max_results=3))
            if resultados:
                resumen = " | ".join(f"{r['title']}: {r['body']}" for r in resultados)
                return f"Datos del clima para {ciudad_limpia}:\n{resumen}"
    except Exception as e_ddg:
        return f"No se pudo obtener el clima para '{ciudad_limpia}': {e_ddg}"

    return f"No se encontró información del clima para '{ciudad_limpia}'."


def buscar_web(query: str) -> str:
    """Busca información actual en DuckDuckGo."""
    print(f"\n[SISTEMA] Buscando en internet: '{query}'")
    query_lower = query.lower()

    # Si la búsqueda es sobre el clima, enriquecer con la herramienta especializada de clima
    clima_extra = ""
    if any(k in query_lower for k in ["clima", "temperatura", "pronostico", "pronóstico", "tiempo en"]):
        # Intentar extraer nombre de ciudad si hay
        palabras = [p for p in query.split() if p.lower() not in ("clima", "del", "el", "de", "en", "temperatura", "hoy", "actual", "pronostico", "pronóstico", "tiempo", "que", "qué")]
        ciudad = " ".join(palabras) if palabras else "Buenos Aires"
        clima_extra = obtener_clima(ciudad) + "\n\nResultados adicionales de la web:\n"

    resultados = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                resultados.append(f"- {r['title']}: {r['body']}")
        if not resultados:
            if clima_extra:
                return clima_extra.strip()
            return "No se encontraron resultados en internet."
        return clima_extra + "\n".join(resultados)
    except Exception as e:
        if clima_extra:
            return clima_extra.strip()
        return f"Error al buscar en internet: {e}"


def abrir_navegador(url: str = "https://www.google.com", **kwargs) -> str:
    """Abre el navegador web predeterminado en una URL específica."""
    url_final = (url or kwargs.get("pagina", "") or kwargs.get("sitio", "") or "").strip()
    if not url_final:
        url_final = "https://www.google.com"

    # Si se pide abrir youtube a través del navegador
    if url_final.lower() in ("youtube", "youtube.com", "www.youtube.com", "pagina youtube", "página youtube"):
        return abrir_youtube()

    if not url_final.startswith("http://") and not url_final.startswith("https://"):
        if "." in url_final:
            url_final = "https://" + url_final
        else:
            if url_final.lower() in ("google", "buscador"):
                url_final = "https://www.google.com"
            else:
                url_final = f"https://www.google.com/search?q={url_final}"

    print(f"\n[SISTEMA] Abriendo navegador en: {url_final}")
    try:
        webbrowser.open(url_final)
        return f"Navegador abierto en {url_final}"
    except Exception as e:
        return f"Error al abrir el navegador: {e}"


def abrir_youtube(query: str = "", url: str = "", **kwargs) -> str:
    """Abre YouTube en el navegador web predeterminado.
    Si se especifica un término de búsqueda, busca los videos en YouTube."""
    from urllib.parse import quote
    termino = (query or url or kwargs.get("busqueda", "") or "").strip()
    termino_lower = termino.lower()

    if not termino or termino_lower in (
        "youtube", "https://youtube.com", "https://www.youtube.com",
        "http://youtube.com", "http://www.youtube.com",
        "pagina youtube", "página youtube", "inicio", "home"
    ):
        target_url = "https://www.youtube.com"
        print(f"\n[SISTEMA] Abriendo YouTube: {target_url}")
        try:
            webbrowser.open(target_url)
            return "Página de YouTube abierta correctamente en el navegador."
        except Exception as e:
            return f"Error al abrir YouTube: {e}"

    target_url = f"https://www.youtube.com/results?search_query={quote(termino)}"
    print(f"\n[SISTEMA] Abriendo búsqueda en YouTube: {target_url}")
    try:
        webbrowser.open(target_url)
        return f"YouTube abierto con la búsqueda: '{termino}'"
    except Exception as e:
        return f"Error al abrir YouTube: {e}"


def buscar_youtube(query: str = "", **kwargs) -> str:
    """Busca videos en YouTube y abre los resultados en el navegador."""
    return abrir_youtube(query=query, **kwargs)


def abrir_programa(nombre: str) -> str:
    """Abre una aplicación instalada en el sistema."""
    print(f"\n[SISTEMA] Intentando abrir el programa: {nombre}")
    nombre_limpio = (nombre or "").strip()
    if nombre_limpio.lower() in ("youtube", "youtube.com"):
        return abrir_youtube()

    candidatos = [nombre_limpio, nombre_limpio.lower(), nombre_limpio.lower().replace(" ", "-"), nombre_limpio.lower().replace(" ", "")]
    alias_conocidos = {
        "vs code": "code",
        "visual studio code": "code",
        "vscode": "code",
        "navegador": "google-chrome",
        "chrome": "google-chrome",
        "google chrome": "google-chrome",
        "firefox": "firefox",
        "archivos": "nemo",
        "explorador": "nemo",
        "terminal": "x-terminal-emulator"
    }
    if nombre_limpio.lower() in alias_conocidos:
        candidatos.insert(0, alias_conocidos[nombre_limpio.lower()])

    for candidato in candidatos:
        ruta_ejecutable = shutil.which(candidato)
        if ruta_ejecutable:
            try:
                subprocess.Popen([ruta_ejecutable])
                return f"Se abrió '{candidato}' correctamente."
            except Exception as e:
                return f"Se encontró '{candidato}' pero falló al abrirlo: {e}"

    return f"No se encontró el programa '{nombre_limpio}' instalado o en el PATH del sistema."


# RAG diferido (lazy loading para no demorar el inicio)
_modelo_embeddings = None
_coleccion_chroma = None

def consultar_mis_documentos(pregunta: str) -> str:
    """Consulta la base vectorial local de documentos propios indexados."""
    global _modelo_embeddings, _coleccion_chroma
    print(f"\n[SISTEMA] Consultando documentos propios sobre: '{pregunta}'")
    try:
        if _coleccion_chroma is None:
            import chromadb
            from sentence_transformers import SentenceTransformer
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
            _modelo_embeddings = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
            cliente_chroma = chromadb.PersistentClient(path=db_path)
            _coleccion_chroma = cliente_chroma.get_or_create_collection(name="mis_documentos")

        if _coleccion_chroma.count() == 0:
            return "Todavía no hay documentos indexados. Corré indexar_documentos.py primero."

        embedding_pregunta = _modelo_embeddings.encode([pregunta]).tolist()
        resultados = _coleccion_chroma.query(query_embeddings=embedding_pregunta, n_results=4)

        documentos = resultados.get("documents", [[]])[0]
        metadatas = resultados.get("metadatas", [[]])[0]

        if not documentos:
            return "No se encontró información relevante en tus documentos."

        partes = []
        for doc, meta in zip(documentos, metadatas):
            partes.append(f"[Fuente: {meta.get('archivo', 'desconocido')}]\n{doc}")

        return "\n\n---\n\n".join(partes)
    except Exception as e:
        return f"Error al consultar documentos propios: {e}"


# Definiciones de herramientas para OpenAI function calling
TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "crear_carpeta",
            "description": "Crea o inicializa una nueva carpeta o directorio. Usá esta función cuando el usuario pida iniciar, crear o hacer una carpeta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta de la carpeta a crear, ej: '~/Escritorio/mi_proyecto' o 'Escritorio/nueva_carpeta'"
                    }
                },
                "required": ["ruta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_carpeta",
            "description": "Abre una carpeta en el explorador gráfico de archivos (Nemo/XDG).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta de la carpeta a abrir, ej: '~/Escritorio' o '~/Documentos'"
                    },
                    "crear_si_no_existe": {
                        "type": "boolean",
                        "description": "Si es True y la carpeta no existe, la crea antes de abrirla."
                    }
                },
                "required": ["ruta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_carpeta",
            "description": "Elimina una carpeta y la envía a la papelera de reciclaje de forma segura.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta de la carpeta a eliminar"
                    }
                },
                "required": ["ruta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_documento",
            "description": "Crea o escribe un nuevo documento o archivo de texto (ej: .txt, .md, .py, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta completa del archivo a crear, ej: '~/Escritorio/notas.txt'"
                    },
                    "contenido": {
                        "type": "string",
                        "description": "Contenido de texto inicial del documento (opcional)"
                    }
                },
                "required": ["ruta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "leer_documento",
            "description": "Lee el contenido de texto de un archivo específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta del archivo a leer"
                    }
                },
                "required": ["ruta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modificar_documento",
            "description": "Modifica un documento existente, agregando texto al final o sobrescribiéndolo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta del archivo a modificar"
                    },
                    "contenido": {
                        "type": "string",
                        "description": "El nuevo contenido a agregar o con el que sobrescribir"
                    },
                    "modo": {
                        "type": "string",
                        "enum": ["agregar", "sobrescribir"],
                        "description": "'agregar' para anexar al final, o 'sobrescribir' para reemplazar todo"
                    }
                },
                "required": ["ruta", "contenido"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_documento",
            "description": "Elimina un archivo y lo envía a la papelera de reciclaje de forma segura.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta del archivo a eliminar"
                    }
                },
                "required": ["ruta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mover_o_renombrar",
            "description": "Mueve o renombra un archivo o carpeta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origen": {
                        "type": "string",
                        "description": "Ruta del archivo o carpeta original"
                    },
                    "destino": {
                        "type": "string",
                        "description": "Ruta o nombre final de destino"
                    }
                },
                "required": ["origen", "destino"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_archivos",
            "description": "Lista los archivos y carpetas dentro de un directorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta de la carpeta a listar (por defecto '~' para la carpeta personal)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_archivo",
            "description": "Busca archivos o carpetas por nombre de forma recursiva.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_archivo": {
                        "type": "string",
                        "description": "Nombre o parte del nombre del archivo o carpeta"
                    },
                    "carpeta_inicio": {
                        "type": "string",
                        "description": "Carpeta donde comenzar la búsqueda (por defecto '~')"
                    }
                },
                "required": ["nombre_archivo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_web",
            "description": "Busca información actual en internet sobre cualquier tema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Los términos de búsqueda"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_navegador",
            "description": "Abre el navegador web predeterminado en una URL o sitio web específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "La URL o sitio web a abrir, ej: 'https://github.com', 'google.com'"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_youtube",
            "description": "Abre YouTube en el navegador web predeterminado. Opcionalmente busca un video o tema si se indica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Término o tema opcional para buscar en YouTube (dejar vacío para abrir la página principal)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_youtube",
            "description": "Busca videos en YouTube y abre los resultados en el navegador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Qué buscar en YouTube"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_programa",
            "description": "Abre un programa instalado por su nombre (ej: 'code', 'firefox', 'nemo').",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {
                        "type": "string",
                        "description": "Nombre del programa a abrir"
                    }
                },
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_mis_documentos",
            "description": "Busca información en los documentos personales del usuario indexados en la base local.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": "Pregunta o tema a consultar"
                    }
                },
                "required": ["pregunta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_clima",
            "description": "Obtiene el pronóstico del clima actual en tiempo real, temperatura, sensación térmica, humedad y viento para cualquier ciudad o localidad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ciudad": {
                        "type": "string",
                        "description": "Nombre de la ciudad o localidad (ej: 'Buenos Aires', 'Córdoba', 'Rosario', 'Madrid', etc.)"
                    }
                },
                "required": ["ciudad"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_recordatorio",
            "description": "Guarda un recordatorio con fecha, hora y prioridad/importancia (Alta, Media, Baja). La prioridad se asigna automáticamente según la importancia del evento (ej: competencias, exámenes, turnos médicos -> Alta) si no se especifica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descripcion": {
                        "type": "string",
                        "description": "Descripción o título del recordatorio (ej: 'Competencia', 'Turno con el médico', 'Comprar café')"
                    },
                    "fecha": {
                        "type": "string",
                        "description": "Fecha del recordatorio en lenguaje natural o numérico (ej: 'domingo 17 de noviembre', 'mañana', '2026-11-17')"
                    },
                    "hora": {
                        "type": "string",
                        "description": "Hora opcional del evento (ej: '10:00', '15:30')"
                    },
                    "prioridad": {
                        "type": "string",
                        "description": "Prioridad deseada: 'Alta', 'Media', 'Baja' o 'Auto' para evaluación automática según importancia"
                    }
                },
                "required": ["descripcion", "fecha"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_recordatorios",
            "description": "Muestra los recordatorios guardados, ordenados según su nivel de importancia y prioridad (Alta primero, luego Media y Baja) y por proximidad de fecha.",
            "parameters": {
                "type": "object",
                "properties": {
                    "solo_pendientes": {
                        "type": "boolean",
                        "description": "True para mostrar solo recordatorios pendientes (por defecto), False para incluir completados"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_recordatorio",
            "description": "Elimina un recordatorio por su número de ID o buscando texto en su descripción.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identificador": {
                        "type": "string",
                        "description": "Número de ID (ej: '1') o nombre/texto del recordatorio a eliminar"
                    }
                },
                "required": ["identificador"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_recordatorio_completado",
            "description": "Marca un recordatorio como completado o realizado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identificador": {
                        "type": "string",
                        "description": "Número de ID o texto del recordatorio a marcar como completado"
                    }
                },
                "required": ["identificador"]
            }
        }
    }
]


def ejecutar_herramienta(nombre: str, argumentos: dict) -> str:
    """Despacha la ejecución de la función solicitada con sus argumentos."""
    mapa = {
        "crear_carpeta": crear_carpeta,
        "abrir_carpeta": abrir_carpeta,
        "eliminar_carpeta": eliminar_carpeta,
        "crear_documento": crear_documento,
        "leer_documento": leer_documento,
        "leer_archivo": leer_documento,
        "modificar_documento": modificar_documento,
        "eliminar_documento": eliminar_documento,
        "mover_o_renombrar": mover_o_renombrar,
        "listar_archivos": listar_archivos,
        "buscar_archivo": buscar_archivo,
        "buscar_web": buscar_web,
        "abrir_navegador": abrir_navegador,
        "abrir_web": abrir_navegador,
        "navegar": abrir_navegador,
        "abrir_youtube": abrir_youtube,
        "buscar_youtube": buscar_youtube,
        "buscar_en_youtube": buscar_youtube,
        "abrir_programa": abrir_programa,
        "consultar_mis_documentos": consultar_mis_documentos,
        "obtener_clima": obtener_clima,
        "consultar_clima": obtener_clima,
        "clima": obtener_clima,
        "crear_recordatorio": crear_recordatorio,
        "agendar_recordatorio": crear_recordatorio,
        "recordatorio": crear_recordatorio,
        "listar_recordatorios": listar_recordatorios,
        "ver_recordatorios": listar_recordatorios,
        "mostrar_recordatorios": listar_recordatorios,
        "consultar_recordatorios": listar_recordatorios,
        "eliminar_recordatorio": eliminar_recordatorio,
        "borrar_recordatorio": eliminar_recordatorio,
        "marcar_recordatorio_completado": marcar_recordatorio_completado,
    }

    if nombre not in mapa:
        nombre_lower = (nombre or "").lower()
        if "clima" in nombre_lower or "tiempo" in nombre_lower or "weather" in nombre_lower:
            return obtener_clima(**argumentos)
        elif "recordatorio" in nombre_lower or "recordar" in nombre_lower:
            if "list" in nombre_lower or "ver" in nombre_lower or "mostrar" in nombre_lower:
                return listar_recordatorios(**argumentos)
            return crear_recordatorio(**argumentos)
        elif "youtube" in nombre_lower:
            return abrir_youtube(**argumentos)
        elif "navegador" in nombre_lower or "browser" in nombre_lower or "pagina" in nombre_lower or "web" in nombre_lower:
            return abrir_navegador(**argumentos)
        return f"Error: La función '{nombre}' no está disponible."

    try:
        return mapa[nombre](**argumentos)
    except TypeError as e:
        return f"Error en los parámetros de '{nombre}': {e}"
    except Exception as e:
        return f"Error ejecutando '{nombre}': {e}"
