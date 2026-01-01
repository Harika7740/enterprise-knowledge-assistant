# vector_store.py - FINAL FIXED for Streamlit Cloud (punkt_tab issue solved)
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import nltk

# Download both punkt and punkt_tab safely
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)

embedder = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text, chunk_size=700, overlap=140):
    sentences = nltk.sent_tokenize(text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current.split()) + len(s.split()) > chunk_size:
            if current.strip():
                chunks.append(current.strip())
            current = " ".join(current.split()[-overlap:]) + " " + s
        else:
            current += " " + s
    if current.strip():
        chunks.append(current.strip())
    return chunks

def create_vector_index(texts_with_meta):
    all_chunks = []
    all_meta = []

    for text, meta in texts_with_meta:
        chunks = chunk_text(text)
        for c in chunks:
            all_chunks.append(c)
            all_meta.append({**meta, "chunk_text": c})

    if not all_chunks:
        return None, []

    embeddings = embedder.encode(all_chunks, normalize_embeddings=True)
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))

    return index, all_meta
