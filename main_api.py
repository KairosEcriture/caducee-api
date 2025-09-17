# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 6.1.1 (Version Finale Stable "Insubmersible")
#  Date : 14/09/2025
# =============================================================================
import os; import json; import google.generativeai as genai; import googlemaps; import re; import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone, date
from sqlmodel import Field, Session, SQLModel, create_engine, select
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv() # Lit le fichier .env

app = FastAPI(title="Caducée API", version="6.1.1")
origins = ["*"] # Configuration CORS agressive pour le dev et la prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.environ.get("SECRET_KEY", "secret_dev_key")
ALGORITHM = "HS256"; ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

DATABASE_URL = "sqlite:///./caducee.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables(): SQLModel.metadata.create_all(engine)
@app.on_event("startup")
def on_startup(): create_db_and_tables()
def get_session():
    with Session(engine) as session: yield session

# --- 2. MODÈLES DE DONNÉES ---
class User(SQLModel, table=True):
    email: str = Field(primary_key=True); hashed_password: str
    first_name: Optional[str] = None; last_name: Optional[str] = None
    birth_date: Optional[date] = None; birth_place: Optional[str] = None
    address: Optional[str] = None; phone_number: Optional[str] = None
    sex: Optional[str] = None; medical_history: Optional[str] = None; allergies: Optional[str] = None
class Consultation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True); symptom: str
    final_recommendation: str; severity_level: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_email: str = Field(foreign_key="user.email")

# --- 3. MODÈLES D'API (Pydantic) ---
class Token(BaseModel): access_token: str; token_type: str
class UserCreate(BaseModel): email: EmailStr; password: str
class UserPublic(BaseModel):
    email: EmailStr; first_name: Optional[str] = None; last_name: Optional[str] = None
    birth_date: Optional[date] = None; birth_place: Optional[str] = None
    address: Optional[str] = None; phone_number: Optional[str] = None
    sex: Optional[str] = None; medical_history: Optional[str] = None; allergies: Optional[str] = None
class UserUpdate(BaseModel):
    first_name: Optional[str] = None; last_name: Optional[str] = None
    birth_date: Optional[date] = None; birth_place: Optional[str] = None
    address: Optional[str] = None; phone_number: Optional[str] = None
    sex: Optional[str] = None; medical_history: Optional[str] = None; allergies: Optional[str] = None
class ConsultationPublic(BaseModel): id: int; symptom: str; final_recommendation: str; severity_level: str; created_at: datetime
class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; answer_type: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel): next_question: Optional[str] = None; answer_type: str = "yes_no"; final_recommendation: Optional[str] = None; severity_level: Optional[str] = None
class NearbyDoctorsRequest(BaseModel): latitude: float; longitude: float
class Doctor(BaseModel): name: str; address: str; rating: Optional[float] = None; url: str

# --- 4. FONCTIONS UTILITAIRES & SÉCURITÉ ---
def verify_password(p, h): return pwd_context.verify(p, h)
def get_password_hash(p): return pwd_context.hash(p)
def create_access_token(data: dict):
    to_encode = data.copy(); expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire}); return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]); email: str = payload.get("sub")
        if email is None: raise credentials_exception
    except jwt.PyJWTError: raise credentials_exception
    user = session.get(User, email)
    if user is None: raise credentials_exception
    return user

# --- 5. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v6.1.1 (Stable) est en ligne."}
@app.post("/token", response_model=Token, tags=["User"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.get(User, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user.email}); return {"access_token": access_token, "token_type": "bearer"}
@app.post("/users/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED, tags=["User"])
def create_user(user: UserCreate, session: Session = Depends(get_session)):
    if session.get(User, user.email): raise HTTPException(status_code=400, detail="Email already registered")
    db_user = User(email=user.email, hashed_password=get_password_hash(user.password)); session.add(db_user); session.commit(); session.refresh(db_user)
    return db_user
@app.get("/users/me", response_model=UserPublic, tags=["User"])
async def read_users_me(current_user: User = Depends(get_current_user)): return current_user
@app.put("/users/me", response_model=UserPublic, tags=["User"])
async def update_user_me(user_update: UserUpdate, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    user_data = user_update.model_dump(exclude_unset=True)
    for key, value in user_data.items(): setattr(current_user, key, value)
    session.add(current_user); session.commit(); session.refresh(current_user)
    return current_user
@app.get("/consultations", response_model=List[ConsultationPublic], tags=["Analysis"])
async def read_consultations(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(Consultation).where(Consultation.owner_email == current_user.email)).all()
@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest, current_user: User = Depends(get_current_user)):
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    user_profile_context = f"Contexte patient: Âge {current_user.age}, Sexe {current_user.sex}."
    prompt = f'{user_profile_context}\nAnalyse: "{request.symptoms}".\nRéponse JSON...'
    try:
        response = model.generate_content(prompt); analysis_data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        return AnalysisResponse(**analysis_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")
@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    user_profile_context = f"Contexte patient: Âge {current_user.age}, Sexe {current_user.sex}."
    prompt = f'{user_profile_context}\nSymptômes: "{request.symptoms}".\nHistorique: {history_str}\nTACHE: ...'
    try:
        response = model.generate_content(prompt); refine_data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        if refine_data.get("final_recommendation"):
            new_consultation = Consultation(symptom=request.symptoms, final_recommendation=refine_data["final_recommendation"], severity_level=refine_data["severity_level"], owner_email=current_user.email)
            session.add(new_consultation); session.commit()
        return RefineResponse(**refine_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")
@app.post("/doctors/nearby", response_model=List[Doctor], tags=["Geolocation"])
def find_nearby_doctors(request: NearbyDoctorsRequest):
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not GOOGLE_MAPS_API_KEY: raise HTTPException(status_code=500, detail="Service de géolocalisation non configuré.")
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    try:
        places_result = gmaps.places_nearby(location=(request.latitude, request.longitude), radius=5000, keyword="médecin généraliste", language="fr")
        return [Doctor(name=p.get('name'), address=p.get('vicinity'), rating=p.get('rating'), url=f"https://www.google.com/maps/place/?q=place_id:{p.get('place_id')}") for p in places_result.get('results', [])[:3]]
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur du service de géolocalisation: {e}")