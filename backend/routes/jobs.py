from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import Application, Job, User, get_db
from core.schemas import JobInput, JobResponse, JobUpdate
from routes.auth import require_role
router = APIRouter(tags=["jobs"])
def current_status(job: Job) -> str: return "CLOSED" if job.status == "CLOSED" or datetime.utcnow() >= job.deadline else "OPEN"
def as_utc_naive(value: datetime) -> datetime: return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
def job_data(job: Job, count: int = 0) -> dict:
    return {"id":job.id,"recruiter_id":job.recruiter_id,"title":job.title,"description":job.description,"required_skills":job.required_skills or [],"preferred_skills":job.preferred_skills or [],"experience_required":job.experience_required,"deadline":job.deadline,"status":current_status(job),"created_at":job.created_at,"applicant_count":count}
@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    return [job_data(job) for job in (await db.scalars(select(Job).order_by(Job.created_at.desc()))).all() if current_status(job) == "OPEN"]
@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return job_data(job)
@router.post("/recruiter/jobs", response_model=JobResponse, status_code=201)
async def create_job(data: JobInput, user: User = Depends(require_role("RECRUITER")), db: AsyncSession = Depends(get_db)):
    deadline=as_utc_naive(data.deadline)
    if deadline <= datetime.utcnow():
        raise HTTPException(status_code=400, detail=f"Deadline must be later than the server time: {datetime.utcnow().isoformat(timespec='minutes')} UTC")
    job = Job(recruiter_id=user.id, **data.model_dump(exclude={"deadline"}), deadline=deadline); db.add(job); await db.commit(); await db.refresh(job)
    return job_data(job)
@router.get("/recruiter/jobs", response_model=list[JobResponse])
async def recruiter_jobs(user: User = Depends(require_role("RECRUITER")), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(Job, func.count(Application.id)).outerjoin(Application).where(Job.recruiter_id == user.id).group_by(Job.id).order_by(Job.created_at.desc()))
    return [job_data(job, count) for job, count in rows.all()]
@router.put("/recruiter/jobs/{job_id}", response_model=JobResponse)
async def update_job(job_id: int, data: JobUpdate, user: User = Depends(require_role("RECRUITER")), db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    if job.recruiter_id != user.id: raise HTTPException(status_code=403, detail="You can only manage your own jobs")
    for key, value in data.model_dump(exclude_none=True).items(): setattr(job, key, as_utc_naive(value) if key == "deadline" else value)
    await db.commit(); await db.refresh(job)
    return job_data(job)
