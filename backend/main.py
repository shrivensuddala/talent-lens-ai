from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import get_settings
from core.database import init_db
from routes.auth import router as auth_router
from routes.applications import router as applications_router
from routes.jobs import router as jobs_router
from routes.recruiters import router as recruiters_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(); yield
app=FastAPI(title="TalentLens AI — AI-Powered Recruitment Portal",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=get_settings().cors_origins.split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(auth_router); app.include_router(jobs_router); app.include_router(applications_router); app.include_router(recruiters_router)
# Keep /api for the Vite/nginx development proxy while the unprefixed routes
# remain available exactly as documented in the project API.
app.include_router(auth_router, prefix="/api"); app.include_router(jobs_router, prefix="/api"); app.include_router(applications_router, prefix="/api"); app.include_router(recruiters_router, prefix="/api")
@app.get("/health")
async def health(): return {"status":"healthy"}
