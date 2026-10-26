import re
from ai.resume import embed_texts
def normalize(value: str) -> str: return re.sub(r"\s+", " ", value.lower().strip())
def cosine(a: list[float], b: list[float]) -> float: return sum(x*y for x,y in zip(a,b))/((sum(x*x for x in a)*sum(y*y for y in b))**.5 or 1)
def estimate_years(text: str) -> float: return max([float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\+?\s+years?", text.lower())] or [0])
def calculate_match(resume_text: str, job) -> dict:
    """Deterministic 50/30/10/10 score. An LLM is never used for this value."""
    text=normalize(resume_text); required=[x for x in job.required_skills or [] if x.strip()]; preferred=[x for x in job.preferred_skills or [] if x.strip()]
    matched=[skill for skill in required if normalize(skill) in text]; missing=[skill for skill in required if skill not in matched]
    required_score=len(matched)/len(required) if required else 1; preferred_score=sum(normalize(s) in text for s in preferred)/len(preferred) if preferred else 1
    resume_vector,job_vector=embed_texts([resume_text, f"{job.title}\n{job.description}\n{' '.join(required)}"])
    semantic=max(0,min(1,(cosine(resume_vector,job_vector)+1)/2)); experience=min(1,estimate_years(resume_text)/job.experience_required) if job.experience_required else 1
    return {"match_score":round(100*(.5*semantic+.3*required_score+.1*experience+.1*preferred_score),1),"matched_skills":matched,"missing_skills":missing,"breakdown":{"semantic_score":round(semantic*100,1),"required_skills_score":round(required_score*100,1),"experience_score":round(experience*100,1),"preferred_skills_score":round(preferred_score*100,1)}}
