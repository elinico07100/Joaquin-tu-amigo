"""
Asistente con chat continuo en terminal + tool calling local.
Comandos especiales:
- 'escuchar' o '/voz': Grabar por voz y transcribir con Whisper.
- '/leer': Activar/desactivar lectura en voz alta (TTS) de las respuestas.
- '/modelo' o '/config': Ver o cambiar el modelo estándar de la computadora.
- 'limpiar': Reiniciar la conversación.
- 'salir': Terminar el asistente.
"""

import sys
import os
from agente import AgenteAsistente
from voz import grabar_y_transcribir_en_vivo, hablar, detener_habla
from config import (
    cargar_config, guardar_config, escanear_modelos_locales,
    establecer_modelo_estandar, reiniciar_servidor_modelo
)


def seleccionar_modelo_cli() -> str:
    """Muestra un menú interactivo en terminal para seleccionar el modelo estándar."""
    print("\n" + "=" * 65)
    print("🧠 Buscando modelos .gguf en tu computadora...")
    modelos = escanear_modelos_locales()
    cfg = cargar_config()
    modelo_actual = cfg.get("modelo_path", "")

    if not modelos:
        print("⚠️ No se encontraron modelos en las rutas predeterminadas.")
        ruta = input("Ingresá la ruta completa a tu archivo .gguf: ").strip()
        if os.path.isfile(ruta):
            establecer_modelo_estandar(ruta)
            reiniciar_servidor_modelo(callback_progreso=lambda m: print(f"  [SERVIDOR] {m}"))
            return os.path.basename(ruta)
        else:
            print("Ruta inválida.")
            return cfg.get("modelo_nombre", "default")

    print(f"Modelos encontrados ({len(modelos)}):")
    for i, m in enumerate(modelos, 1):
        marca = " (ESTÁNDAR ACTUAL) ⭐️" if m["ruta"] == modelo_actual else ""
        print(f"  [{i}] {m['nombre']} — ({m['tamano']}){marca}")
    print(f"  [{len(modelos) + 1}] Ingresar otra ruta de archivo manualmente...")
    print("=" * 65)

    while True:
        try:
            opcion = input(f"Elegí un modelo (1-{len(modelos) + 1}) [Enter para mantener actual]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("")
            return cfg.get("modelo_nombre", "default")

        if not opcion:
            return cfg.get("modelo_nombre", "default")

        if opcion.isdigit():
            idx = int(opcion)
            if 1 <= idx <= len(modelos):
                seleccionado = modelos[idx - 1]
                print(f"\nEstableciendo '{seleccionado['nombre']}' como modelo estándar...")
                establecer_modelo_estandar(seleccionado["ruta"])
                ok, msg = reiniciar_servidor_modelo(timeout_espera=35, callback_progreso=lambda m: print(f"  [SERVIDOR] {m}"))
                if ok:
                    print(f"✅ {msg}\n")
                else:
                    print(f"⚠️ {msg}\n")
                return seleccionado["nombre"]
            elif idx == len(modelos) + 1:
                ruta = input("Ingresá la ruta completa al archivo .gguf: ").strip()
                if os.path.isfile(ruta):
                    establecer_modelo_estandar(ruta)
                    reiniciar_servidor_modelo(timeout_espera=35, callback_progreso=lambda m: print(f"  [SERVIDOR] {m}"))
                    return os.path.basename(ruta)
                else:
                    print("Archivo no encontrado.")

        print("Opción inválida. Intentá de nuevo.")


def main():
    cfg = cargar_config()

    # Si se pasó --config o es la primera vez que se ejecuta, invocar selector
    if "--config" in sys.argv or "--modelo" in sys.argv or cfg.get("primera_vez", True) or not os.path.isfile(cfg.get("modelo_path", "")):
        seleccionar_modelo_cli()
        cfg = cargar_config()

    agente = AgenteAsistente()
    leer_voz_alta = False

    print("=" * 65)
    print("🤖 Mi Asistente IA (Modo Terminal)")
    print(f"Modelo activo: {cfg.get('modelo_nombre')} (llama-server CUDA)")
    print("Comandos: 'escuchar' (voz), '/leer' (TTS), '/modelo' (cambiar modelo), 'salir'")
    print("=" * 65 + "\n")

    while True:
        try:
            entrada = input("\nVos: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nChau!")
            break

        if not entrada:
            continue

        if entrada.lower() in ("salir", "exit", "quit"):
            detener_habla()
            print("¡Hasta luego!")
            break

        if entrada.lower() in ("/modelo", "modelo", "/config", "config"):
            detener_habla()
            nuevo_nombre = seleccionar_modelo_cli()
            agente.actualizar_configuracion()
            print(f"[SISTEMA] Modelo cambiado a: {nuevo_nombre}")
            continue

        if entrada.lower() in ("escuchar", "/voz", "voz"):
            detener_habla()
            dictado = grabar_y_transcribir_en_vivo()
            if not dictado:
                print("No se detectó audio o se canceló.")
                continue
            print(f"Vos (por voz): {dictado}")
            entrada = dictado

        if entrada.lower() in ("/leer", "leer"):
            leer_voz_alta = not leer_voz_alta
            estado = "activada 🔊" if leer_voz_alta else "desactivada 🔇"
            print(f"[VOZ] Lectura en voz alta {estado}")
            continue

        if entrada.lower() in ("limpiar", "/cls", "clear"):
            agente.reiniciar_conversacion()
            print("[SISTEMA] Conversación reiniciada.")
            continue

        detener_habla()

        def mostrar_accion(nombre, args):
            print(f"  ⚡ Ejecutando: {nombre} ({args})")

        respuesta = agente.procesar_mensaje(entrada, callback_accion=mostrar_accion)
        print(f"\nAsistente: {respuesta}")

        if leer_voz_alta:
            hablar(respuesta)


if __name__ == "__main__":
    main()
