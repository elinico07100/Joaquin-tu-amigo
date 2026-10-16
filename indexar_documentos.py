"""
Indexa tus documentos (código, apuntes, notas) en una base de datos vectorial local.
Corré este script cada vez que agregues o cambies archivos en la carpeta de documentos.

Soporta: .txt, .md, .py

Uso:
    python indexar_documentos.py "C:\\ruta\\a\\tu\\carpeta"
"""

import sys
import os
import chromadb
from sentence_transformers import SentenceTransformer

EXTENSIONES_VALIDAS = (".txt", ".md", ".py")
TAMANO_CHUNK = 500       # caracteres aproximados por fragmento
SOLAPAMIENTO = 50        # caracteres de solapamiento entre fragmentos consecutivos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_modelo_embeddings = None
_coleccion = None

def get_coleccion():
    global _modelo_embeddings, _coleccion
    if _coleccion is None:
        import chromadb
        from sentence_transformers import SentenceTransformer
        print("Cargando modelo de embeddings (paraphrase-multilingual-MiniLM-L12-v2)...")
        _modelo_embeddings = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        cliente_chroma = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
        _coleccion = cliente_chroma.get_or_create_collection(name="mis_documentos")
    return _modelo_embeddings, _coleccion


def dividir_en_chunks(texto: str, tamano: int = TAMANO_CHUNK, solapamiento: int = SOLAPAMIENTO):
    """Divide un texto largo en fragmentos más chicos, con algo de solapamiento
    para no perder contexto en los bordes de cada corte."""
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + tamano
        chunks.append(texto[inicio:fin])
        inicio += tamano - solapamiento
    return chunks


def indexar_carpeta(ruta_carpeta: str):
    ruta_carpeta = os.path.abspath(os.path.expanduser(ruta_carpeta))
    if not os.path.isdir(ruta_carpeta):
        print(f"Error: '{ruta_carpeta}' no es una carpeta válida.")
        return

    total_chunks = 0
    modelo_embeddings, coleccion = get_coleccion()

    for raiz, _, archivos in os.walk(ruta_carpeta):
        for archivo in archivos:
            if not archivo.lower().endswith(EXTENSIONES_VALIDAS):
                continue

            ruta_completa = os.path.join(raiz, archivo)
            try:
                with open(ruta_completa, "r", encoding="utf-8", errors="ignore") as f:
                    contenido = f.read()
            except Exception as e:
                print(f"  [omitido] {ruta_completa}: {e}")
                continue

            if not contenido.strip():
                continue

            chunks = dividir_en_chunks(contenido)
            embeddings = modelo_embeddings.encode(chunks).tolist()

            ids = [f"{ruta_completa}::{i}" for i in range(len(chunks))]
            metadatas = [{"archivo": ruta_completa, "fragmento": i} for i in range(len(chunks))]

            coleccion.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )

            total_chunks += len(chunks)
            print(f"  Indexado: {ruta_completa} ({len(chunks)} fragmentos)")

    print(f"\nListo. Total de fragmentos indexados: {total_chunks}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python indexar_documentos.py ~/Documentos")
        sys.exit(1)

    carpeta = sys.argv[1]
    print(f"Indexando carpeta: {carpeta}\n")
    indexar_carpeta(carpeta)
