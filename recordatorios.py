"""
Módulo de Gestión de Recordatorios con Prioridad e Importancia.
Permite:
- Guardar recordatorios con fecha, hora, descripción y prioridad asignada.
- Asignación inteligente de prioridad (Alta, Media, Baja) según el tipo de evento (competencias, exámenes, pagos, turnos, etc.).
- Listar y ordenar recordatorios según importancia y proximidad temporal.
- Persistencia local en recordatorios.json.
"""

import os
import json
import datetime
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.expanduser("~/.config/asistente-ia")
REMINDERS_PATH = os.path.join(CONFIG_DIR, "recordatorios.json")
LOCAL_REMINDERS_PATH = os.path.join(BASE_DIR, "recordatorios.json")

MESES_ESP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

NOMBRES_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Palabras clave para inferir prioridad automáticamente
PALABRAS_ALTA = [
    "competencia", "torneo", "campeonato", "examen", "parcial", "final",
    "medico", "médico", "doctor", "dentista", "operacion", "operación",
    "urgente", "vuelo", "viaje", "entrevista", "plazo", "vencimiento", "factura",
    "pagar", "audiencia", "entrega final", "tesis"
]

PALABRAS_MEDIA = [
    "trabajo", "tarea", "entrega", "reunion", "reunión", "llamada", "llamar",
    "comprar", "supermercado", "mandado", "estudiar", "repaso", "cumpleaños",
    "aniversario", "entrenamiento", "gimnasio", "clase"
]


def cargar_recordatorios() -> list:
    """Carga los recordatorios del archivo JSON."""
    ruta = REMINDERS_PATH if os.path.isfile(REMINDERS_PATH) else LOCAL_REMINDERS_PATH
    if os.path.isfile(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[RECORDATORIOS] Error al leer: {e}")
    return []


def guardar_recordatorios(lista: list):
    """Guarda los recordatorios en la carpeta de configuración y local."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(REMINDERS_PATH, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[RECORDATORIOS] Error guardando en {REMINDERS_PATH}: {e}")

    try:
        with open(LOCAL_REMINDERS_PATH, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[RECORDATORIOS] Error guardando en {LOCAL_REMINDERS_PATH}: {e}")


def evaluar_prioridad(descripcion: str, prioridad_manual: str = "Auto") -> tuple[str, int, str]:
    """Determina el nivel de prioridad (Alta=1, Media=2, Baja=3) y su justificación."""
    if prioridad_manual and prioridad_manual.lower() not in ("auto", "ninguna", "default", "none", ""):
        p_clean = prioridad_manual.strip().capitalize()
        if "alta" in p_clean.lower():
            return "Alta", 1, "Asignada manualmente por el usuario"
        elif "baja" in p_clean.lower():
            return "Baja", 3, "Asignada manualmente por el usuario"
        elif "media" in p_clean.lower():
            return "Media", 2, "Asignada manualmente por el usuario"

    desc_lower = descripcion.lower()

    for palabra in PALABRAS_ALTA:
        if palabra in desc_lower:
            return "Alta", 1, f"Evento crítico o con fecha inamovible ('{palabra}')"

    for palabra in PALABRAS_MEDIA:
        if palabra in desc_lower:
            return "Media", 2, f"Compromiso relevante ('{palabra}')"

    return "Baja", 3, "Actividad o nota general sin urgencia crítica detectada"


def normalizar_fecha(fecha_str: str) -> tuple[str, str, datetime.date | None]:
    """Normaliza texto libre de fecha en fecha ISO (YYYY-MM-DD) y formato legible."""
    if not fecha_str:
        hoy = datetime.date.today()
        return hoy.isoformat(), f"Hoy ({hoy.strftime('%d/%m/%Y')})", hoy

    ahora = datetime.datetime.now()
    fecha_l = fecha_str.lower().strip()

    # 1. ISO format: 2026-11-17
    m_iso = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', fecha_l)
    if m_iso:
        dt = datetime.date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        nombre_dia = DIAS_SEMANA[dt.weekday()]
        legible = f"{nombre_dia} {dt.day} de {NOMBRES_MESES[dt.month]} de {dt.year}"
        return dt.isoformat(), legible, dt

    # 2. Casos relativos
    if "hoy" in fecha_l:
        dt = ahora.date()
        return dt.isoformat(), f"Hoy ({dt.day} de {NOMBRES_MESES[dt.month]})", dt
    if "pasado mañana" in fecha_l:
        dt = ahora.date() + datetime.timedelta(days=2)
        nombre_dia = DIAS_SEMANA[dt.weekday()]
        return dt.isoformat(), f"Pasado mañana ({nombre_dia} {dt.day} de {NOMBRES_MESES[dt.month]})", dt
    if "mañana" in fecha_l:
        dt = ahora.date() + datetime.timedelta(days=1)
        nombre_dia = DIAS_SEMANA[dt.weekday()]
        return dt.isoformat(), f"Mañana ({nombre_dia} {dt.day} de {NOMBRES_MESES[dt.month]})", dt

    # 3. Formato '17 de noviembre' o 'domingo 17 de noviembre' o '17 de noviembre de 2026'
    m_mes = re.search(r'(\d{1,2})\s+(?:de\s+)?([a-z]+)(?:\s+(?:de\s+)?(\d{4}))?', fecha_l)
    if m_mes:
        dia = int(m_mes.group(1))
        mes_txt = m_mes.group(2)
        anio = int(m_mes.group(3)) if m_mes.group(3) else ahora.year
        if mes_txt in MESES_ESP:
            mes = MESES_ESP[mes_txt]
            try:
                dt = datetime.date(anio, mes, dia)
                # Si el mes ya pasó y no se aclaró año, presumir el próximo año
                if dt < ahora.date() and not m_mes.group(3):
                    dt = datetime.date(anio + 1, mes, dia)
                nombre_dia = DIAS_SEMANA[dt.weekday()]
                legible = f"{nombre_dia} {dt.day} de {NOMBRES_MESES[dt.month]} de {dt.year}"
                return dt.isoformat(), legible, dt
            except ValueError:
                pass

    # 4. Formato numérico DD/MM/YYYY o DD/MM
    m_num = re.search(r'(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?', fecha_l)
    if m_num:
        dia, mes = int(m_num.group(1)), int(m_num.group(2))
        anio = int(m_num.group(3)) if m_num.group(3) else ahora.year
        if anio < 100:
            anio += 2000
        try:
            dt = datetime.date(anio, mes, dia)
            nombre_dia = DIAS_SEMANA[dt.weekday()]
            legible = f"{nombre_dia} {dt.day} de {NOMBRES_MESES[dt.month]} de {dt.year}"
            return dt.isoformat(), legible, dt
        except ValueError:
            pass

    # Si no se pudo parsear como fecha estructurada, guardar el texto tal como vino
    return "sin-fecha", fecha_str.strip().capitalize(), None


def crear_recordatorio(descripcion: str, fecha: str, hora: str = None, prioridad: str = "Auto") -> str:
    """Crea un recordatorio asignando prioridad según la importancia del evento."""
    if not descripcion or not descripcion.strip():
        return "Error: Debe especificarse una descripción para el recordatorio."

    descripcion = descripcion.strip()
    fecha_iso, fecha_legible, dt_fecha = normalizar_fecha(fecha)
    p_nombre, p_nivel, p_motivo = evaluar_prioridad(descripcion, prioridad)

    recordatorios = cargar_recordatorios()
    nuevo_id = 1
    if recordatorios:
        nuevo_id = max(r.get("id", 0) for r in recordatorios) + 1

    hora_limpia = None
    if hora and hora.strip():
        hora_limpia = hora.strip()

    nuevo_item = {
        "id": nuevo_id,
        "descripcion": descripcion,
        "fecha_iso": fecha_iso,
        "fecha_legible": fecha_legible,
        "hora": hora_limpia,
        "prioridad": p_nombre,
        "nivel_prioridad": p_nivel,
        "motivo_prioridad": p_motivo,
        "completado": False,
        "creado_el": datetime.datetime.now().isoformat()
    }

    recordatorios.append(nuevo_item)
    guardar_recordatorios(recordatorios)

    icono_p = "🔴" if p_nivel == 1 else ("🟡" if p_nivel == 2 else "🟢")
    hora_str = f" a las {hora_limpia}" if hora_limpia else ""

    return (
        f"✅ Recordatorio agendado con éxito:\n"
        f"• Tarea: {descripcion}\n"
        f"• Fecha: {fecha_legible}{hora_str}\n"
        f"• Importancia/Prioridad: {icono_p} {p_nombre.upper()} ({p_motivo})\n"
        f"• ID: #{nuevo_id}"
    )


def listar_recordatorios(solo_pendientes: bool = True) -> str:
    """Retorna la lista de recordatorios ordenados por prioridad (Alta -> Media -> Baja) y fecha."""
    items = cargar_recordatorios()
    if not items:
        return "No tenés recordatorios guardados en este momento."

    if solo_pendientes:
        items = [r for r in items if not r.get("completado", False)]
        if not items:
            return "No tenés recordatorios pendientes pendientes. ¡Estás al día!"

    hoy = datetime.date.today()

    # Ordenar por:
    # 1. Nivel de prioridad (1 = Alta, 2 = Media, 3 = Baja)
    # 2. Fecha ISO
    def criterio_orden(r):
        nivel = r.get("nivel_prioridad", 2)
        fecha_iso = r.get("fecha_iso", "9999-99-99")
        if fecha_iso == "sin-fecha":
            fecha_iso = "9999-99-99"
        return (nivel, fecha_iso)

    items.sort(key=criterio_orden)

    lineas = [f"📋 Tus Recordatorios (Ordenados por Prioridad e Importancia):\n"]

    for r in items:
        rid = r.get("id")
        desc = r.get("descripcion", "")
        p_nombre = r.get("prioridad", "Media")
        p_nivel = r.get("nivel_prioridad", 2)
        fecha_legible = r.get("fecha_legible", "")
        fecha_iso = r.get("fecha_iso", "")
        hora = r.get("hora")
        completado = r.get("completado", False)

        icono_p = "🔴" if p_nivel == 1 else ("🟡" if p_nivel == 2 else "🟢")
        estado_str = " (Completado ✅)" if completado else ""

        # Calcular días restantes
        tiempo_str = ""
        if fecha_iso and fecha_iso != "sin-fecha":
            try:
                y, m, d = map(int, fecha_iso.split("-"))
                dt_item = datetime.date(y, m, d)
                dif = (dt_item - hoy).days
                if dif == 0:
                    tiempo_str = " [¡ES HOY! ⚡]"
                elif dif == 1:
                    tiempo_str = " [MAÑANA ⏳]"
                elif dif > 1:
                    tiempo_str = f" [En {dif} días]"
                elif dif < 0:
                    tiempo_str = f" [Pasado hace {-dif} días ⚠️]"
            except Exception:
                pass

        hora_str = f" a las {hora}" if hora else ""

        lineas.append(
            f"{icono_p} [Prioridad {p_nombre.upper()}] #{rid}: {desc}{estado_str}\n"
            f"   📅 Fecha: {fecha_legible}{hora_str}{tiempo_str}\n"
            f"   ℹ️ Motivo: {r.get('motivo_prioridad', 'Importancia asignada')}\n"
        )

    return "\n".join(lineas).strip()


def eliminar_recordatorio(identificador: str) -> str:
    """Elimina un recordatorio por su ID o buscando texto en la descripción."""
    items = cargar_recordatorios()
    if not items:
        return "No hay recordatorios para eliminar."

    identificador_limpio = str(identificador).strip().lstrip("#").lower()

    # 1. Búsqueda por ID exacto
    if identificador_limpio.isdigit():
        target_id = int(identificador_limpio)
        nuevos = [r for r in items if r.get("id") != target_id]
        if len(nuevos) < len(items):
            guardar_recordatorios(nuevos)
            return f"Recordatorio #{target_id} eliminado exitosamente."

    # 2. Búsqueda por coincidencia en descripción
    encontrado = None
    for r in items:
        if identificador_limpio in r.get("descripcion", "").lower():
            encontrado = r
            break

    if encontrado:
        items.remove(encontrado)
        guardar_recordatorios(items)
        return f"Recordatorio #{encontrado.get('id')} ('{encontrado.get('descripcion')}') eliminado exitosamente."

    return f"No se encontró ningún recordatorio que coincida con '{identificador}'."


def marcar_recordatorio_completado(identificador: str) -> str:
    """Marca un recordatorio como completado."""
    items = cargar_recordatorios()
    identificador_limpio = str(identificador).strip().lstrip("#").lower()

    encontrado = None
    for r in items:
        if str(r.get("id")) == identificador_limpio or identificador_limpio in r.get("descripcion", "").lower():
            encontrado = r
            break

    if encontrado:
        encontrado["completado"] = True
        guardar_recordatorios(items)
        return f"Recordatorio #{encontrado.get('id')} ('{encontrado.get('descripcion')}') marcado como completado ✅."

    return f"No se encontró el recordatorio '{identificador}'."
