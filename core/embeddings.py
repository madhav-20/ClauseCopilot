from sentence_transformers import SentenceTransformer

_model = None

def get_embedder(model_name: str = "all-MiniLM-L6-v2"):
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name)
    return _model

def embed_texts(texts, model_name="all-MiniLM-L6-v2"):
    model = get_embedder(model_name)
    return model.encode(texts, show_progress_bar=False).tolist()