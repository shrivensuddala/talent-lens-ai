from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ai.rag import make_verdict, retrieve_evidence
from core.database import AIVerdict, Application, Candidate, CandidateLock, Job, User, get_db
from core.schemas import CandidateDetail, VerdictResponse
from routes.applications import application_data
from routes.auth import require_role
router=APIRouter(prefix="/recruiter",tags=["recruiter"])
async def owned_application(application_id:int,user:User,db:AsyncSession)->Application:
    item=await db.get(Application,application_id)
    if not item: raise HTTPException(status_code=404,detail="Application not found")
    await db.refresh(item,attribute_names=["job","candidate"])
    if item.job.recruiter_id!=user.id: raise HTTPException(status_code=403,detail="This job belongs to another recruiter")
    return item
@router.get("/jobs/{job_id}/applications")
async def applicants(job_id:int,user:User=Depends(require_role("RECRUITER")),db:AsyncSession=Depends(get_db)):
    job=await db.get(Job,job_id)
    if not job: raise HTTPException(status_code=404,detail="Job not found")
    if job.recruiter_id!=user.id: raise HTTPException(status_code=403,detail="You can only view your own job")
    rows=await db.execute(
        select(Application, User.name)
        .select_from(Application)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .join(User, Candidate.user_id == User.id)
        .where(Application.job_id == job.id)
        .order_by(Application.match_score.desc().nullslast(), Application.applied_at)
    )
    return [application_data(item,candidate_name=name,job_title=job.title) for item,name in rows.all()]
@router.get("/applications/{application_id}",response_model=CandidateDetail)
async def candidate_detail(application_id:int,user:User=Depends(require_role("RECRUITER")),db:AsyncSession=Depends(get_db)):
    item=await owned_application(application_id,user,db); await db.refresh(item.candidate,attribute_names=["user"])
    lock=await db.scalar(select(CandidateLock).where(CandidateLock.candidate_id==item.candidate_id,CandidateLock.active==True,CandidateLock.expires_at>datetime.utcnow()))
    return {**application_data(item,item.candidate.user.name,item.job.title),"candidate_email":item.candidate.user.email,"match_breakdown":item.match_breakdown or {},"lock_active":bool(lock)}
@router.post("/applications/{application_id}/verdict",response_model=VerdictResponse)
async def verdict(application_id:int,user:User=Depends(require_role("RECRUITER")),db:AsyncSession=Depends(get_db)):
    item=await owned_application(application_id,user,db); saved=await db.scalar(select(AIVerdict).where(AIVerdict.application_id==item.id))
    if saved and saved.evidence:return {"verdict":saved.verdict,"strengths":saved.strengths,"gaps":saved.gaps,"evidence":saved.evidence,"cached":True}
    if saved:
        await db.delete(saved)
        await db.flush()
    evidence=retrieve_evidence(item.id,f"{item.job.title} {' '.join(item.job.required_skills or [])}"); result=make_verdict(item.job,item,evidence); db.add(AIVerdict(application_id=item.id,evidence=evidence,**result)); await db.commit()
    return {**result,"evidence":evidence,"cached":False}
@router.post("/applications/{application_id}/reserve")
async def reserve(application_id:int,user:User=Depends(require_role("RECRUITER")),db:AsyncSession=Depends(get_db)):
    item=await owned_application(application_id,user,db); await db.execute(select(Candidate).where(Candidate.id==item.candidate_id).with_for_update())
    old=await db.scalar(select(CandidateLock).where(CandidateLock.candidate_id==item.candidate_id,CandidateLock.active==True))
    if old and old.expires_at<=datetime.utcnow(): old.active=False; await db.flush(); old=None
    if old: raise HTTPException(status_code=409,detail="Candidate is already reserved")
    db.add(CandidateLock(candidate_id=item.candidate_id,job_id=item.job_id,recruiter_id=user.id,expires_at=datetime.utcnow()+timedelta(days=7)))
    try: await db.commit()
    except IntegrityError: await db.rollback(); raise HTTPException(status_code=409,detail="Candidate is already reserved")
    return {"message":"Candidate reserved"}
@router.post("/applications/{application_id}/release")
async def release(application_id:int,user:User=Depends(require_role("RECRUITER")),db:AsyncSession=Depends(get_db)):
    item=await owned_application(application_id,user,db); lock=await db.scalar(select(CandidateLock).where(CandidateLock.candidate_id==item.candidate_id,CandidateLock.recruiter_id==user.id,CandidateLock.active==True))
    if not lock: raise HTTPException(status_code=404,detail="Active reservation not found")
    lock.active=False; await db.commit(); return {"message":"Reservation released"}
