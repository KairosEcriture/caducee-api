# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 1.4 (Version Finale Stable)
#  Date : 31/08/2025
# =============================================================================
import os; import jwt; import google.generativeai as genai; import json
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlmodel import Field, Session, SQLModel, create_engine, select

# --- 1. CONFIGURATION ---
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./caducee.db").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SECRET_KEY = os.environ.get("SECRET_KEY", "secret_dev_key_caducee")
ALGORITHM = "HS256"; ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(title="Caducée API", version="1.4.0")
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

class SymptomRequest(BaseModel):
    symptoms: str
class Diagnosis(BaseModel):
    condition: str
    probability: str
    specialist: str
class AnalysisResponse(BaseModel):
    differential_diagnosis: List[Diagnosis]
    urgency_level: str
    warning: str

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
def read_root(): return {"status": "Caducée API v1.4 (Stable) est en ligne."}

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
# --- ENDPOINT D'ANALYSE IA (maintenant public) ---
@app.post("/analysis", response_model=AnalysisResponse, tags=["AI Services"])
async def get_symptom_analysis(request: SymptomRequest):
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de configuration Gemini: {e}")

    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    system_prompt = (
        "ROLE: Tu es Caducée, un assistant IA d'aide à la pré-analyse médicale..." # Le prompt complet est ici
    )
    
    full_prompt = f"Analyse ces symptômes en respectant scrupuleusement tes instructions.\n\nSYMPTÔMES: \"{request.symptoms}\""

    try:
        response = model.generate_content([system_prompt, full_prompt], generation_config=genai.types.GenerationConfig(response_mime_type="application/json"))
        analysis_data = json.loads(response.text)
        return analysis_data
    except Exception as e:
        print(f"ERREUR CRITIQUE lors de l'appel à Gemini : {e}")
        raise HTTPException(status_code=503, detail=f"Erreur de communication avec l'assistant IA.")

# --- ENDPOINTS DE DÉVELOPPEMENT ---
@app.post("/dev/reset-database", tags=["Development Tools"], status_code=status.HTTP_204_NO_CONTENT)
async def reset_database():
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    return None
