# Joaquin-tu-amigo
Asistente de IA personal que corre enteramente en tu PC, sin APIs pagas ni envío de datos a terceros. Conecta un modelo de lenguaje local a herramientas reales — búsqueda web, navegación del sistema de archivos, consulta de documentos propios y dictado por voz — todo construido de forma conversacional junto a un agente de IA.

# Asistente de escritorio local

Asistente de IA personal que corre 100% en tu propia PC, sin depender de
APIs pagas ni enviar datos a servidores externos. Usa un modelo de lenguaje
local (vía [LM Studio](https://lmstudio.ai/)) con capacidad real de usar
herramientas: buscar en internet, navegar tu sistema de archivos, consultar
tus propios documentos, y dictado por voz.

> **Nota sobre cómo se construyó este proyecto:** todo el código de este
> repositorio fue escrito con la asistencia de un agente de IA (Claude, de
> Anthropic), de forma conversacional e iterativa. No hay otros
> colaboradores humanos en el desarrollo del código. Se comparte como
> proyecto de aprendizaje personal.

## ¿Qué hace?

- 💬 Chat continuo con memoria de la conversación
- 🔍 Búsqueda real en internet (DuckDuckGo, sin necesidad de API key)
- 📁 Navegación del sistema de archivos: buscar, listar, leer, crear carpetas
  y escribir archivos
- 🖥️ Abrir programas y carpetas en el explorador gráfico
- 📺 Búsqueda de videos en YouTube
- 📚 RAG sobre documentos propios (código, apuntes, notas) usando una base
  de datos vectorial local (Chroma)
- 🎤 Dictado por voz con transcripción casi en vivo (Whisper, corriendo
  localmente)

Todo corre en tu máquina. Ningún dato sale de tu PC salvo las búsquedas web
en sí mismas.

## Requisitos

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) con un modelo cargado (recomendado:
  `Qwen2.5-Coder-7B-Instruct-GGUF`, quant `Q4_K_M`, de un publisher
  confiable como `lmstudio-community` o `bartowski`)
- GPU recomendada (no obligatoria): al menos 8GB de VRAM para que la
  inferencia sea cómoda. Con NVIDIA + CUDA el rendimiento es mejor que con
  AMD + Vulkan, aunque ambos funcionan.

## Instalación

```bash
# Cloná el repo y entrá a la carpeta
git clone <url-del-repo>
cd <carpeta-del-repo>

# Creá y activá un entorno virtual
python3 -m venv asistente-ia
source asistente-ia/bin/activate      # Linux/Mac
# asistente-ia\Scripts\Activate.ps1   # Windows (PowerShell)

# Instalá las dependencias
pip install -r requirements.txt
```

Si vas a usar GPU NVIDIA, instalá PyTorch con soporte CUDA siguiendo las
instrucciones de [pytorch.org](https://pytorch.org/) antes del paso
anterior.

## Uso

1. Abrí LM Studio, cargá el modelo, y andá a la pestaña **Developer** →
   **Start Server** (por defecto en `http://localhost:1234`).
2. Corré el asistente:
   ```bash
   python3 asistente_chat.py
   ```
3. (Opcional) Para que el asistente pueda consultar tus propios documentos,
   indexalos primero:
   ```bash
   python3 indexar_documentos.py "/ruta/a/tu/carpeta"
   ```
4. Para dictar en vez de escribir, escribí `escuchar` en el chat y hablá.
   El texto aparece en vivo en `~/dictado_en_vivo.txt`.

## Estructura del proyecto

```
.
├── asistente_chat.py        # Script principal: loop de chat + herramientas + voz
├── indexar_documentos.py    # Indexa documentos propios para RAG
├── requirements.txt         # Dependencias de Python
└── chroma_db/                # Base de datos vectorial (se genera sola)
```

## Estado del proyecto

Fase 1 (agente funcional con herramientas y RAG) completa. Ver
`PROYECTO_ESTADO.md` para el detalle técnico completo, decisiones de
diseño, y roadmap de próximos pasos (interfaz gráfica, fine-tuning, etc.).

## Limitaciones conocidas

- El modelo local (7B) a veces comete errores al elegir qué herramienta
  usar o con qué parámetros — hay manejo de errores para que esto no
  crashee el programa, pero puede requerir reformular el pedido.
- No hay ejecución de comandos/código arbitrario por decisión de diseño
  (riesgo de seguridad). Las acciones disponibles son un set fijo de
  herramientas predefinidas.
- Probado en Linux y Windows; no probado en Mac (debería funcionar, el
  código está escrito para ser multiplataforma).

## Licencia

Proyecto personal de aprendizaje, sin licencia formal por ahora.
