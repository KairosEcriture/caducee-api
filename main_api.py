# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 4.2 (Stabilité Finale avec CORS Corrigé)
#  Date : 13/09/2025
# =============================================================================
import os; import json; import google.generativeai as genai; import googlemaps; import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="4.2.0")

# === LA CORRECTION CORS DÉFINITIVE EST ICI ===
origins = [
    "https://caducee-frontend.onrender.com",
    "http://localhost",
    "http://localhost:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Autorise POST, GET, OPTIONS, etc.
    allow_headers=["*"], # Autorise tous les en-têtes
)
# === FIN DE LA CORRECTION ===

try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
except Exception: GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES ---
class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; answer_type: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel): next_question: Optional[str] = None; answer_type: str = "yes_no"; final_recommendation: Optional[str] = None; severity_level: Optional[str] = None
class NearbyDoctorsRequest(BaseModel): latitude: float; longitude: float
class Doctor(BaseModel): name: str; address: str; rating: Optional[float] = None; url: str

# --- 3. FONCTIONS ---
def clean_gemini_response(raw_text: str) -> dict:
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if not match: raise ValueError("Aucun JSON trouvé dans la réponse de l'IA.")
    json_str = match.group(0)
    try: return json.loads(json_str)
    except json.JSONDecodeError as e: raise ValueError(f"JSON invalide. Erreur: {e}")

# --- 4. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v4.2 (Stable) est en ligne."}

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    prompt = f"""
    Analyse les symptômes suivants : "{request.symptoms}".
    Ta réponse DOIT être un objet JSON valide avec 6 clés : "symptom", "differential_diagnoses", "first_question", "answer_type" (soit "yes_no" ou "open_text"), "recommendations", et "disclaimer".
    """
    try:
        response = model.generate_content(prompt)
        analysis_data = clean_gemini_response(response.text)
        return AnalysisResponse(**analysis_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    prompt = f"""
    ROLE: Tu es un assistant médical IA.
    CONTEXTE: Symptômes initiaux : "{request.symptoms}". Historique: {history_str}
    TACHE: Choisis UNE SEULE action :
    1. Si tu as besoin de plus d'infos, génère la prochaine question.
    2. Si tu as assez d'infos, génère une recommandation finale.
    FORMAT DE SORTIE OBLIGATOIRE: Un objet JSON valide.
    - Si action 1: objet avec "next_question" ET "answer_type".
    - Si action 2: objet avec "severity_level" ("Bénin", "Modéré", "Urgent") ET "final_recommendation".
    """
    try:
        response = model.generate_content(prompt)
        refine_data = clean_gemini_response(response.text)
        return RefineResponse(**refine_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

@app.post("/doctors/nearby", response_model=List[Doctor], tags=["Geolocation"])
def find_nearby_doctors(request: NearbyDoctorsRequest):
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=500, detail="Service de géolocalisation non configuré.")
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    try:
        places_result = gmaps.places_nearby(
            location=(request.latitude, request.longitude), radius=5000,
            keyword="médecin généraliste", language="fr", rank_by="prominence"
        )
        doctors = []
        for place in places_result.get('results', [])[:3]:
            doctors.append(Doctor(
                name=place.get('name'), address=place.get('vicinity'),
                rating=place.get('rating'), url=f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}"
            ))
        return doctors
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur du service de géolocalisation: {e}")