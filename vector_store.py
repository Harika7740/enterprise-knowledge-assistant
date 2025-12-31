from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import nltk

nltk.download('punkt', quiet=True)

embedder = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text, chunk_size=800, overlap=150):
    sentences = nltk.sent_tokenize(text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current.split()) + len(sentence.split()) > chunk_size:
            chunks.append(current.strip())
            current = " ".join(current.split()[-overlap:]) + " " + sentence
        else:
            current += " " + sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks

def create_index(documents):
    all_chunks = []
    for text, _ in documents:
        all_chunks.extend(chunk_text(text))

    if not all_chunks:
        return None, []

    embeddings = embedder.encode(all_chunks, normalize_embeddings=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))
    return index, all_chunks

def retrieve_chunks(index, chunks, query, top_k=10):
    if index is None:
        return []
    query_emb = embedder.encode([query], normalize_embeddings=True)
    D, I = index.search(query_emb.astype('float32'), top_k)
    return [chunks[i] for i in I[0]]