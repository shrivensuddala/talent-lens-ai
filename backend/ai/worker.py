import logging
from ai.matching import calculate_match
from ai.resume import chunk_resume, clean_text, embed_texts, extract_text, store_chunks
from core.database import Application, AsyncSessionLocal
logger=logging.getLogger(__name__)
async def process_application(application_id: int) -> None:
    """A lightweight in-process background worker. Submission returns before this runs."""
    async with AsyncSessionLocal() as db:
        application=await db.get(Application,application_id)
        if not application: return
        try:
            application.processing_status="PROCESSING"; await db.commit()
            text=clean_text(extract_text(application.resume_path))
            if not text: raise ValueError("Resume did not contain readable text")
            chunks=chunk_resume(text); vectors=embed_texts([item["text"] for item in chunks]); store_chunks(application.id,application.candidate_id,application.job_id,chunks,vectors)
            await db.refresh(application,attribute_names=["job"])
            result=calculate_match(text,application.job); application.match_score=result["match_score"]; application.match_breakdown=result["breakdown"]; application.matched_skills=result["matched_skills"]; application.missing_skills=result["missing_skills"]; application.status="READY"; application.processing_status="COMPLETED"
            await db.commit(); logger.info("Resume processing completed for application %s",application_id)
        except Exception:
            logger.exception("Resume processing failed for application %s",application_id); application.processing_status="FAILED"; await db.commit()
