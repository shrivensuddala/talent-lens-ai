from ai.resume import embed_texts
from core.config import get_settings
import logging

logger = logging.getLogger(__name__)

class TalentLensEmbeddings:
    def embed_documents(self, texts): return embed_texts(texts)
    def embed_query(self, text): return embed_texts([text])[0]

def retrieve_evidence(application_id: int, query: str) -> list[str]:
    """Qdrant retrieval always filters by application_id."""
    settings=get_settings()
    if not settings.qdrant_url: return []
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        client=QdrantClient(url=settings.qdrant_url,api_key=settings.qdrant_api_key)
        scope=Filter(must=[FieldCondition(key="application_id",match=MatchValue(value=application_id))])
        # Resume vectors use a deliberately simple, root-level metadata payload.
        # Query it directly while the prompt/LLM part of this RAG workflow stays LangChain-based.
        results=client.search(
            collection_name=settings.qdrant_collection,
            query_vector=TalentLensEmbeddings().embed_query(query),
            query_filter=scope,
            limit=5,
        )
        return [point.payload["text"] for point in results if point.payload.get("text")]
    except Exception as exc:
        logger.warning("Could not retrieve evidence for application %s: %s", application_id, exc)
        return []

def make_verdict(job, application, evidence: list[str]) -> dict:
    prompt=("You are assisting a recruiter. Use only the provided job requirements and resume evidence. Explain strengths, gaps and relevant experience. Do not invent information and do not calculate a numeric match score. Return JSON with verdict, strengths and gaps.\n\n"+f"Job: {job.title}\nRequired: {', '.join(job.required_skills or [])}\nPreferred: {', '.join(job.preferred_skills or [])}\nResume evidence:\n"+"\n".join(evidence))
    if get_settings().groq_api_key and evidence:
        try:
            from langchain_core.output_parsers import JsonOutputParser
            from langchain_core.prompts import PromptTemplate
            from langchain_groq import ChatGroq
            data=(PromptTemplate.from_template("{prompt}") | ChatGroq(api_key=get_settings().groq_api_key,model=get_settings().groq_model,temperature=0) | JsonOutputParser()).invoke({"prompt":prompt})
            return {"verdict":str(data.get("verdict","")),"strengths":data.get("strengths",[]),"gaps":data.get("gaps",[])}
        except Exception: pass
    strengths=application.matched_skills or []; gaps=application.missing_skills or []
    return {"verdict":f"Evidence shows relevant experience with {', '.join(strengths) or 'the listed requirements'}. Missing or unsupported requirements: {', '.join(gaps) or 'none identified'}.","strengths":strengths,"gaps":gaps}
