#!/bin/bash
# Script para iniciar llama-server leyendo la configuración dinámica del Asistente

# Resolver ruta real del script siguiendo symlinks
TARGET="${BASH_SOURCE[0]}"
while [ -h "$TARGET" ]; do
    DIR="$(cd -P "$(dirname "$TARGET")" >/dev/null 2>&1 && pwd)"
    TARGET="$(readlink "$TARGET")"
    [[ $TARGET != /* ]] && TARGET="$DIR/$TARGET"
done
PROYECTO_DIR="$(cd -P "$(dirname "$TARGET")" >/dev/null 2>&1 && pwd)"
PYTHON_EXEC="$PROYECTO_DIR/../bin/python3"
if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="python3"
fi

# Leer configuración dinámica desde config.py
CFG_INFO=$("$PYTHON_EXEC" -c "
import sys, os
sys.path.insert(0, '$PROYECTO_DIR')
try:
    from config import obtener_datos_lanzador
    datos = obtener_datos_lanzador()
    print(f\"{datos['backend_dir']}|{datos['modelo_path']}|{datos['modelo_nombre']}|{datos['host']}|{datos['puerto']}|{datos['ctx_size']}|{datos['n_gpu_layers']}\")
except Exception as e:
    sys.exit(1)
" 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$CFG_INFO" ]; then
    IFS='|' read -r BACKEND_DIR MODEL_PATH ALIAS HOST PORT CTX_SIZE GPU_LAYERS <<< "$CFG_INFO"
fi

# Valores por defecto de respaldo
if [ -z "$BACKEND_DIR" ]; then
    BACKEND_DIR="/home/estudiante/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.50.0"
fi
if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="/home/estudiante/.lmstudio/models/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
fi
if [ -z "$ALIAS" ]; then ALIAS="default"; fi
if [ -z "$HOST" ]; then HOST="127.0.0.1"; fi
if [ -z "$PORT" ]; then PORT="1234"; fi
if [ -z "$CTX_SIZE" ]; then CTX_SIZE="8192"; fi
if [ -z "$GPU_LAYERS" ]; then GPU_LAYERS="99"; fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: No se encontró el modelo en $MODEL_PATH"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/llama-server" ]; then
    echo "Error: No se encontró llama-server en $BACKEND_DIR"
    exit 1
fi

export LD_LIBRARY_PATH="$BACKEND_DIR:$LD_LIBRARY_PATH"

echo "Iniciando llama-server con modelo: $MODEL_PATH ($ALIAS) en $HOST:$PORT..."
exec "$BACKEND_DIR/llama-server" \
    --model "$MODEL_PATH" \
    --alias "$ALIAS,default" \
    --host "$HOST" \
    --port "$PORT" \
    --ctx-size "$CTX_SIZE" \
    --n-gpu-layers "$GPU_LAYERS" \
    --flash-attn on \
    --threads 4 \
    --jinja
