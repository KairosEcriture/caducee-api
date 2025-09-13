# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 5.0 (Gestion des Utilisateurs et du Profil Médical)
#  Date : 13/09/2025
# =============================================================================
import os; import json; import google.generativeai as genai; import googlemaps; import re; import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from sqlmodel import Field, Session, SQLModel, create_engine, select

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="5.0.0")
origins = ["https://caducee-frontend.onrender.com", "http://localhost", "http://localhost:8080", "null"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Clés secrètes
SECRET_KEY = os.environ.get("SECRET_KEY", "secret_dev_key")
ALGORITHM = "HS256"; ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Base de données
DATABASE_URL = "sqlite:///./caducee.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables(): SQLModel.metadata.create_all(engine)
@app.on_event("startup")
def on_startup(): create_db_and_tables()
def get_session():
    with Session(engine) as session: yield session

# --- 2. MODÈLES DE DONNÉES ---
class User(SQLModel, table=True):
    email: str = Field(primary_key=True)
    hashed_password: str
    age: Optional[int] = None
    sex: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None

class Consultation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symptom: str
    final_recommendation: str
    severity_level: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_email: str = Field(foreign_key="user.email")

# ... (Le reste des modèles viendra ensuite)
# --- 3. MODÈLES D'API (Pydantic) ---
class Token(BaseModel): access_token: str; token_type: str
class UserCreate(BaseModel): email: EmailStr; password: str
class UserPublic(BaseModel):
    email: EmailStr
    age: Optional[int] = None
    sex: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None
class UserUpdate(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None

class ConsultationPublic(BaseModel):
    id: int
    symptom: str
    final_recommendation: str
    severity_level: str
    created_at: datetime

class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; answer_type: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel): next_question: Optional[str] = None; answer_type: str = "yes_no"; final_recommendation: Optional[str] = None; severity_level: Optional[str] = None
class NearbyDoctorsRequest(BaseModel): latitude: float; longitude: float
class Doctor(BaseModel): name: str; address: str; rating: Optional[float] = None; url: str

# --- 4. FONCTIONS UTILITAIRES & SÉCURITÉ ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password):
    return pwd_context.hash(password)
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = session.get(User, email)
    if user is None:
        raise credentials_exception
    return user
# --- 5. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v5.0 (Comptes Utilisateurs) est en ligne."}

# --- ENDPOINTS D'AUTHENTIFICATION & PROFIL ---
@app.post("/token", response_model=Token, tags=["User"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.get(User, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED, tags=["User"])
def create_user(user: UserCreate, session: Session = Depends(get_session)):
    db_user = session.get(User, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@app.get("/users/me", response_model=UserPublic, tags=["User"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.put("/users/me", response_model=UserPublic, tags=["User"])
async def update_user_me(user_update: UserUpdate, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    user_data = user_update.model_dump(exclude_unset=True)
    for key, value in user_data.items():
        setattr(current_user, key, value)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user
# --- ENDPOINTS D'ANALYSE (maintenant sécurisés) ---
@app.get("/consultations", response_model=List[ConsultationPublic], tags=["Analysis"])
async def read_consultations(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    consultations = session.exec(select(Consultation).where(Consultation.owner_email == current_user.email)).all()
    return consultations

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest, current_user: User = Depends(get_current_user)):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    # On enrichit le prompt avec le profil de l'utilisateur
    user_profile_context = f"Contexte patient: Âge {current_user.age}, Sexe {current_user.sex}. Antécédents: {current_user.medical_history}. Allergies: {current_user.allergies}."
    prompt = f'{user_profile_context}\n\nAnalyse les symptômes suivants : "{request.symptoms}".\nTa réponse DOIT être un objet JSON valide...'
    
    try:
        response = model.generate_content(prompt)
        analysis_data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        return AnalysisResponse(**analysis_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    
    user_profile_context = f"Contexte patient: Âge {current_user.age}, Sexe {current_user.sex}. Antécédents: {current_user.medical_history}. Allergies: {current_user.allergies}."
    prompt = f'{user_profile_context}\n\nSymptômes initiaux : "{request.symptoms}".\nHistorique: {history_str}\n\nTACHE: ...'
    
    try:
        response = model.generate_content(prompt)
        refine_data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        
        # Si c'est la recommandation finale, on la sauvegarde
        if refine_data.get("final_recommendation"):
            new_consultation = Consultation(
                symptom=request.symptoms,
                final_recommendation=refine_data["final_recommendation"],
                severity_level=refine_data["severity_level"],
                owner_email=current_user.email
            )
            session.add(new_consultation)
            session.commit()

        return RefineResponse(**refine_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

@app.post("/doctors/nearby", response_model=List[Doctor], tags=["Geolocation"])
def find_nearby_doctors(request: NearbyDoctorsRequest):
    # Cet endpoint reste public pour l'instant
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not GOOGLE_MAPS_API_KEY: raise HTTPException(status_code=500, detail="Service de géolocalisation non configuré.")
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    try:
        places_result = gmaps.places_nearby(location=(request.latitude, request.longitude), radius=5000, keyword="médecin généraliste", language="fr")
        return [Doctor(name=p.get('name'), address=p.get('vicinity'), rating=p.get('rating'), url=f"https://www.google.com/maps/place/?q=place_id:{p.get('place_id')}") for p in places_result.get('results', [])[:3]]
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur du service de géolocalisation: {e}")