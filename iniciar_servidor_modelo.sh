#!/bin/bash
# Script para iniciar llama-server directamente sin LM Studio
BACKEND_DIR="/home/estudiante/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.50.0"
MODEL_PATH="/home/estudiante/.lmstudio/models/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: No se encontró el modelo en $MODEL_PATH"
    exit 1
fi

export LD_LIBRARY_PATH="$BACKEND_DIR:$LD_LIBRARY_PATH"

echo "Iniciando llama-server con modelo Qwen2.5-Coder-7B..."
exec "$BACKEND_DIR/llama-server" \
    --model "$MODEL_PATH" \
    --alias "qwen2.5-coder-7b-instruct,default" \
    --host 127.0.0.1 \
    --port 1234 \
    --ctx-size 8192 \
    --n-gpu-layers 99 \
    --flash-attn on \
    --threads 4 \
    --jinja
