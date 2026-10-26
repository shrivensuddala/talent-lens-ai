from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from core.config import get_settings

engine = create_async_engine(get_settings().database_url, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    candidate: Mapped["Candidate | None"] = relationship(back_populates="user", uselist=False)


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    user: Mapped[User] = relationship(back_populates="candidate")
    applications: Mapped[list["Application"]] = relationship(back_populates="candidate")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_required: Mapped[float] = mapped_column(Float, default=0)
    deadline: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    __table_args__ = (Index("ix_jobs_status_deadline", "status", "deadline"),)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    resume_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="APPLIED")
    processing_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    matched_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    candidate: Mapped[Candidate] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(back_populates="applications")
    verdicts: Mapped[list["AIVerdict"]] = relationship(back_populates="application")
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_application"), Index("ix_applications_job_match", "job_id", "match_score"))


class CandidateLock(Base):
    __tablename__ = "candidate_locks"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (Index("ix_candidate_locks_candidate_active", "candidate_id", "active"), Index("uq_active_candidate_lock", "candidate_id", unique=True, sqlite_where=active.is_(True), postgresql_where=active.is_(True)))


class AIVerdict(Base):
    __tablename__ = "ai_verdicts"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), unique=True)
    verdict: Mapped[str] = mapped_column(Text)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    application: Mapped[Application] = relationship(back_populates="verdicts")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
