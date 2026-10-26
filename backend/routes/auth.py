from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import get_settings
from core.database import Candidate, User, get_db
from core.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])
passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()
def make_token(user: User) -> str:
    settings = get_settings()
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": datetime.utcnow() + timedelta(minutes=settings.access_token_minutes)}, settings.jwt_secret, settings.jwt_algorithm)
async def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    try:
        claims = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
        user = await db.get(User, int(claims["sub"]))
    except (JWTError, KeyError, ValueError):
        user = None
    if not user: raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
def require_role(role: str):
    async def check(user: User = Depends(current_user)) -> User:
        if user.role != role: raise HTTPException(status_code=403, detail=f"{role.title()} access required")
        return user
    return check
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(User).where(User.email == data.email.lower())): raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(name=data.name.strip(), email=data.email.lower(), password_hash=passwords.hash(data.password), role=data.role)
    db.add(user); await db.flush()
    if user.role == "CANDIDATE": db.add(Candidate(user_id=user.id))
    await db.commit()
    return TokenResponse(access_token=make_token(user), role=user.role, name=user.name)
@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not passwords.verify(data.password, user.password_hash): raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=make_token(user), role=user.role, name=user.name)
