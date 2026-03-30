import chromadb
from chromadb.config import Settings

from core.config import CHROMA_PATH


def get_chroma_client(path=None):
    path = path or CHROMA_PATH
    return chromadb.PersistentClient(path=path, settings=Settings(allow_reset=True))

def get_collection(client, name="contracts"):
    return client.get_or_create_collection(name=name)

def upsert_chunks(collection, contract_id: str, vendor: str, chunks: list, embeddings: list):
    ids = [f"{contract_id}_{i}" for i in range(len(chunks))]
    docs = [c["text"] for c in chunks]
    metadatas = [{"contract_id": contract_id, "vendor": vendor, "section": c["section"]} for c in chunks]
    collection.upsert(ids=ids, documents=docs, metadatas=metadatas, embeddings=embeddings)

def semantic_search(collection, query_embedding, top_k=5, vendor_filter=None, contract_filter=None):
    where = {}
    if vendor_filter:
        where["vendor"] = vendor_filter
    if contract_filter:
        where["contract_id"] = contract_filter
    
    # helper for chromadb: empty dict is usually fine, but None is better if really empty
    if not where:
        where = None
        
    res = collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
    return res