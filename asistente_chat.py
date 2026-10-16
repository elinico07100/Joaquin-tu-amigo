"""
Asistente con chat continuo en terminal + tool calling local.
Comandos especiales:
- 'escuchar' o '/voz': Grabar por voz y transcribir con Whisper.
- '/leer': Activar/desactivar lectura en voz alta (TTS) de las respuestas.
- 'limpiar': Reiniciar la conversación.
- 'salir': Terminar el asistente.
"""

import sys
from agente import AgenteAsistente
from voz import grabar_y_transcribir_en_vivo, hablar, detener_habla

def main():
    agente = AgenteAsistente()
    leer_voz_alta = False

    print("=" * 60)
    print("🤖 Mi Asistente IA (Modo Terminal)")
    print("Modelo: Qwen 2.5 Coder (llama-server local con CUDA)")
    print("Escribí tu consulta, 'escuchar' para dictar por voz, o 'salir'.")
    print("=" * 60 + "\n")

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
