import hashlib, logging, re
from pathlib import Path
from core.config import get_settings
logger = logging.getLogger(__name__)
def extract_text(path: str) -> str:
    file_path = Path(path)
    if file_path.suffix.lower() == ".pdf":
        import pdfplumber
        with pdfplumber.open(file_path) as pdf: return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return file_path.read_text(encoding="utf-8", errors="ignore")
def clean_text(text: str) -> str: return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()
def chunk_resume(text: str) -> list[dict]:
    sections = re.split(r"(?im)^\s*(summary|skills|experience|education|projects|certifications)\s*:?[ \t]*$", text)
    labelled = [("summary", sections[0])] + [(sections[i].lower(), sections[i + 1]) for i in range(1, len(sections)-1, 2)] if len(sections) > 1 else [("resume", text)]
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        split = RecursiveCharacterTextSplitter(chunk_size=750, chunk_overlap=100)
        return [{"section": s, "text": c} for s, value in labelled for c in split.split_text(value) if c.strip()]
    except ImportError: return [{"section":s,"text":value[i:i+750]} for s,value in labelled for i in range(0,len(value),650) if value.strip()]
def _hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector=[0.0]*dimensions
    for word in re.findall(r"[a-z0-9+#.]+", text.lower()): vector[int(hashlib.sha256(word.encode()).hexdigest(),16)%dimensions]+=1
    size=sum(v*v for v in vector)**.5 or 1
    return [v/size for v in vector]
_model = None
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Create compact ONNX semantic embeddings without installing PyTorch.

    FastEmbed downloads its small model only when the first resume is processed.
    Hash embeddings remain a local fallback if the model download is unavailable.
    """
    global _model
    try:
        if _model is None:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=get_settings().embedding_model)
        return [vector.tolist() for vector in _model.embed(texts)]
    except Exception as exc:
        logger.warning("Semantic embedding unavailable; using local fallback: %s", exc)
        return [_hash_embedding(text) for text in texts]
def store_chunks(application_id: int, candidate_id: int, job_id: int, chunks: list[dict], vectors: list[list[float]]) -> None:
    settings=get_settings()
    if not settings.qdrant_url:
        logger.info("Qdrant not configured; vectors skipped for local development"); return
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    client=QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    if not client.collection_exists(settings.qdrant_collection): client.create_collection(settings.qdrant_collection, vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
    points=[PointStruct(id=application_id*100000+i, vector=vector, payload={"application_id":application_id,"candidate_id":candidate_id,"job_id":job_id,"document_type":"resume","section":chunk["section"],"text":chunk["text"]}) for i,(chunk,vector) in enumerate(zip(chunks,vectors))]
    client.upsert(settings.qdrant_collection, points=points, wait=True)
