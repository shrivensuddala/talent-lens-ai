import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ai.worker import process_application
from core.config import get_settings
from core.database import Application, Candidate, Job, User, get_db
from core.schemas import ApplicationResponse
from routes.auth import current_user, require_role
from routes.jobs import current_status
router=APIRouter(tags=["applications"])
def application_data(item: Application,candidate_name: str|None=None,job_title: str|None=None) -> dict:
    return {"id":item.id,"candidate_id":item.candidate_id,"job_id":item.job_id,"status":item.status,"processing_status":item.processing_status,"match_score":item.match_score,"matched_skills":item.matched_skills or [],"missing_skills":item.missing_skills or [],"applied_at":item.applied_at,"candidate_name":candidate_name,"job_title":job_title}
@router.post("/applications",response_model=ApplicationResponse,status_code=status.HTTP_202_ACCEPTED)
async def apply(background: BackgroundTasks,job_id: int=Form(...),resume: UploadFile=File(...),user: User=Depends(require_role("CANDIDATE")),db: AsyncSession=Depends(get_db)):
    job=await db.get(Job,job_id)
    if not job: raise HTTPException(status_code=404,detail="Job not found")
    if current_status(job)!="OPEN" or job.deadline<=datetime.utcnow(): raise HTTPException(status_code=409,detail="This job is closed")
    candidate=await db.scalar(select(Candidate).where(Candidate.user_id==user.id))
    suffix=Path(resume.filename or "resume.txt").suffix.lower()
    if suffix not in {".pdf",".txt"}: raise HTTPException(status_code=400,detail="Upload a PDF or text resume")
    folder=Path(get_settings().upload_dir); folder.mkdir(parents=True,exist_ok=True); path=folder/f"{uuid4().hex}{suffix}"
    with path.open("wb") as output: shutil.copyfileobj(resume.file,output)
    item=Application(candidate_id=candidate.id,job_id=job.id,resume_path=str(path)); db.add(item)
    try: await db.commit()
    except IntegrityError:
        await db.rollback(); path.unlink(missing_ok=True); raise HTTPException(status_code=409,detail="You have already applied to this job")
    await db.refresh(item); background.add_task(process_application,item.id)
    return application_data(item,job_title=job.title)
@router.get("/applications/me",response_model=list[ApplicationResponse])
async def my_applications(user: User=Depends(require_role("CANDIDATE")),db: AsyncSession=Depends(get_db)):
    rows=await db.execute(select(Application,Job.title).join(Candidate).join(Job).where(Candidate.user_id==user.id).order_by(Application.applied_at.desc()))
    return [application_data(item,job_title=title) for item,title in rows.all()]
@router.get("/applications/{application_id}",response_model=ApplicationResponse)
async def get_application(application_id:int,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    item=await db.get(Application,application_id)
    if not item: raise HTTPException(status_code=404,detail="Application not found")
    await db.refresh(item,attribute_names=["candidate","job"])
    if user.role=="CANDIDATE" and item.candidate.user_id!=user.id: raise HTTPException(status_code=403,detail="This is not your application")
    if user.role=="RECRUITER" and item.job.recruiter_id!=user.id: raise HTTPException(status_code=403,detail="This job belongs to another recruiter")
    await db.refresh(item.candidate,attribute_names=["user"])
    return application_data(item,item.candidate.user.name,item.job.title)
