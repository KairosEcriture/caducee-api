# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 1.0 (MVP - Squelette)
#  Date : 31/08/2025
# =============================================================================
import os; import jwt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlmodel import Field, Session, SQLModel, create_engine, select
from enum import Enum

# --- 1. CONFIGURATION ---
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./caducee.db").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SECRET_KEY = os.environ.get("SECRET_KEY", "secret_dev_key_caducee")
ALGORITHM = "HS256"; ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(title="Caducée API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- 2. MODÈLES DE DONNÉES ---
class User(SQLModel, table=True):
    email: str = Field(primary_key=True)
    hashed_password: str

def create_db_and_tables(): SQLModel.metadata.create_all(engine)
@app.on_event("startup")
def on_startup(): create_db_and_tables()

def get_session():
    with Session(engine) as session: yield session
class Token(BaseModel): access_token: str; token_type: str
class UserCreate(BaseModel): email: EmailStr; password: str
class UserPublic(BaseModel): email: EmailStr

# --- 3. FONCTIONS UTILITAIRES & SÉCURITÉ ---
def verify_password(p, h): return pwd_context.verify(p, h)
def get_password_hash(p): return pwd_context.hash(p)
def create_access_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy(); to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try: payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]); email: str = payload.get("sub")
    except jwt.PyJWTError: raise credentials_exception
    user = session.get(User, email)
    if user is None: raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    return user
# --- 4. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v1.0 est en ligne."}

@app.post("/token", response_model=Token, tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.get(User, form_data.username);
    if not user or not verify_password(form_data.password, user.hashed_password): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return {"access_token": create_access_token(data={"sub": user.email}), "token_type": "bearer"}

@app.post("/users/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register(user_create: UserCreate, session: Session = Depends(get_session)):
    if session.get(User, user_create.email): raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    db_user = User(email=user_create.email, hashed_password=get_password_hash(user_create.password))
    session.add(db_user); session.commit(); session.refresh(db_user)
    return db_user

@app.get("/users/me", response_model=UserPublic, tags=["Users"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
# --- ENDPOINTS DE DÉVELOPPEMENT ---
@app.post("/dev/reset-database", tags=["Development Tools"], status_code=status.HTTP_204_NO_CONTENT)
async def reset_database():
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    return None

@app.get("/dev/check-env", tags=["Development Tools"])
async def check_environment_variables():
    return {
        "DATABASE_URL_status": "Présente" if os.environ.get("DATABASE_URL") else "Absente",
        "SECRET_KEY_status": "Présente" if os.environ.get("SECRET_KEY") else "Absente",
    }