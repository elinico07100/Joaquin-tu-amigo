"""
Módulo de Configuración y Detección de Modelos Locales.
Permite:
- Detectar y escanear modelos .gguf en la computadora (~/.lmstudio, ~/.ollama, ~/.cache/huggingface, ~/Descargas, etc.).
- Guardar y leer la configuración estándar en config.json.
- Administrar el servidor local de inferencia (llama-server) y reiniciar con el modelo seleccionado.
"""

import os
import json
import time
import subprocess
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.expanduser("~/.config/asistente-ia")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Rutas estándar de búsqueda de modelos GGUF
RUTAS_BUSQUEDA_DEFECTO = [
    "~/.lmstudio/models",
    "~/.cache/huggingface/hub",
    "~/.ollama/models",
    "~/modelos",
    "~/Modelos",
    "~/Descargas",
    "~/Documentos"
]

CONFIG_POR_DEFECTO = {
    "modelo_path": "/home/estudiante/.lmstudio/models/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "modelo_nombre": "Qwen2.5-Coder-7B-Instruct-Q4_K_M",
    "backend_dir": "/home/estudiante/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.50.0",
    "host": "127.0.0.1",
    "puerto": 1234,
    "ctx_size": 8192,
    "n_gpu_layers": 99,
    "flash_attn": True,
    "threads": 4,
    "rutas_busqueda": RUTAS_BUSQUEDA_DEFECTO,
    "primera_vez": True
}


def cargar_config() -> dict:
    """Carga la configuración desde ~/.config/asistente-ia/config.json o archivo local.
    Si no existe, la crea con valores por defecto."""
    config = dict(CONFIG_POR_DEFECTO)
    ruta_a_cargar = None

    if os.path.isfile(CONFIG_PATH):
        ruta_a_cargar = CONFIG_PATH
    elif os.path.isfile(LOCAL_CONFIG_PATH):
        ruta_a_cargar = LOCAL_CONFIG_PATH

    if ruta_a_cargar:
        try:
            with open(ruta_a_cargar, "r", encoding="utf-8") as f:
                datos = json.load(f)
                config.update(datos)
        except Exception as e:
            print(f"[CONFIG] Error al leer configuración: {e}")

    # Si el modelo configurado no existe en disco, intentar autodetectar el primero disponible
    if not os.path.isfile(config.get("modelo_path", "")):
        modelos = escanear_modelos_locales(config.get("rutas_busqueda", []))
        if modelos:
            config["modelo_path"] = modelos[0]["ruta"]
            config["modelo_nombre"] = modelos[0]["nombre"]

    return config


def guardar_config(nueva_config: dict):
    """Guarda la configuración tanto en ~/.config/asistente-ia/ como en la carpeta del proyecto."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(nueva_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[CONFIG] Error al guardar en {CONFIG_PATH}: {e}")

    try:
        with open(LOCAL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(nueva_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[CONFIG] Error al guardar en {LOCAL_CONFIG_PATH}: {e}")


def escanear_modelos_locales(rutas_adicionales=None) -> list:
    """Escanea el disco en busca de archivos .gguf utilizables como LLMs.
    Filtra modelos de visión (mmproj) o embeddings para listar solo modelos de conversación/código."""
    cfg = {}
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
    except Exception:
        pass

    modelo_actual = cfg.get("modelo_path", "")

    rutas = list(RUTAS_BUSQUEDA_DEFECTO)
    if rutas_adicionales:
        for r in rutas_adicionales:
            if r not in rutas:
                rutas.append(r)

    modelos_encontrados = []
    rutas_vistas = set()

    for ruta_base in rutas:
        ruta_exp = os.path.expanduser(ruta_base)
        if not os.path.exists(ruta_exp):
            continue

        for raiz, _, archivos in os.walk(ruta_exp):
            for archivo in archivos:
                if not archivo.endswith(".gguf"):
                    continue

                # Filtrar proyectores multimodales y embeddings
                archivo_lower = archivo.lower()
                if archivo_lower.startswith("mmproj-") or "-mmproj-" in archivo_lower:
                    continue
                if "embed" in archivo_lower:
                    continue

                ruta_completa = os.path.abspath(os.path.join(raiz, archivo))
                if ruta_completa in rutas_vistas:
                    continue
                rutas_vistas.add(ruta_completa)

                try:
                    tamano_bytes = os.path.getsize(ruta_completa)
                    tamano_gb = tamano_bytes / (1024 ** 3)
                    tamano_str = f"{tamano_gb:.2f} GB" if tamano_gb >= 1.0 else f"{tamano_bytes / (1024**2):.1f} MB"
                except Exception:
                    tamano_str = "Desconocido"

                # Nombre limpio
                nombre_base = archivo[:-5] if archivo.endswith(".gguf") else archivo
                # Si está dentro de una carpeta con nombre de modelo representativo
                nombre_carpeta = os.path.basename(raiz)

                es_seleccionado = (ruta_completa == modelo_actual)

                modelos_encontrados.append({
                    "nombre": nombre_base,
                    "nombre_carpeta": nombre_carpeta,
                    "archivo": archivo,
                    "ruta": ruta_completa,
                    "tamano": tamano_str,
                    "seleccionado": es_seleccionado
                })

    # Ordenar: primero los recomendados/actuales, luego alfabéticamente
    modelos_encontrados.sort(key=lambda m: (not m["seleccionado"], m["nombre"].lower()))
    return modelos_encontrados


def establecer_modelo_estandar(ruta_modelo: str) -> bool:
    """Configura una ruta de modelo .gguf como el estándar del asistente."""
    if not os.path.isfile(ruta_modelo):
        print(f"[CONFIG] Error: El archivo '{ruta_modelo}' no existe.")
        return False

    cfg = cargar_config()
    cfg["modelo_path"] = os.path.abspath(ruta_modelo)

    archivo = os.path.basename(ruta_modelo)
    nombre = archivo[:-5] if archivo.endswith(".gguf") else archivo
    cfg["modelo_nombre"] = nombre
    cfg["primera_vez"] = False

    guardar_config(cfg)
    print(f"[CONFIG] Modelo estándar establecido en: {nombre} ({ruta_modelo})")
    return True


def obtener_datos_lanzador() -> dict:
    """Retorna los datos requeridos por iniciar_servidor_modelo.sh."""
    cfg = cargar_config()
    return {
        "backend_dir": cfg.get("backend_dir", "/home/estudiante/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.50.0"),
        "modelo_path": cfg.get("modelo_path", ""),
        "modelo_nombre": cfg.get("modelo_nombre", "default"),
        "host": cfg.get("host", "127.0.0.1"),
        "puerto": cfg.get("puerto", 1234),
        "ctx_size": cfg.get("ctx_size", 8192),
        "n_gpu_layers": cfg.get("n_gpu_layers", 99)
    }


def verificar_servidor_listo(url="http://127.0.0.1:1234/v1/models", timeout=2.0) -> bool:
    """Verifica si el servidor HTTP responde."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def reiniciar_servidor_modelo(timeout_espera=25, callback_progreso=None) -> tuple[bool, str]:
    """Reinicia el servicio systemd del modelo y espera a que esté listo."""
    if callback_progreso:
        callback_progreso("Reiniciando servicio asistente-modelo...")

    try:
        subprocess.run(["systemctl", "--user", "restart", "asistente-modelo.service"], check=False)
    except Exception as e:
        return False, f"Error al ejecutar systemctl: {e}"

    inicio = time.time()
    url = "http://127.0.0.1:1234/v1/models"
    while time.time() - inicio < timeout_espera:
        time.sleep(0.8)
        restante = int(timeout_espera - (time.time() - inicio))
        if callback_progreso:
            callback_progreso(f"Cargando modelo en VRAM... ({restante}s restantes)")
        if verificar_servidor_listo(url, timeout=1.5):
            return True, "Servidor iniciado y modelo cargado con éxito en memoria."

    return False, "El servidor tardó demasiado en responder tras el reinicio."
