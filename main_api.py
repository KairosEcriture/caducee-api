# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 4.1 (Correction de la validation des coordonnées GPS)
#  Date : 11/09/2025
# =============================================================================
import os; import json; import google.generativeai as genai; import googlemaps; import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="4.1.0")
origins = ["https://caducee-frontend.onrender.com", "http://localhost", "http://localhost:8080"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
except Exception: GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES ---
class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; answer_type: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel): next_question: Optional[str] = None; answer_type: str = "yes_no"; final_recommendation: Optional[str] = None; severity_level: Optional[str] = None
class NearbyDoctorsRequest(BaseModel):
    latitude: float
    longitude: float
class Doctor(BaseModel): name: str; address: str; rating: Optional[float] = None; url: str

# --- 3. FONCTIONS ---
def clean_gemini_response(raw_text: str) -> dict: #... (inchangée)

# --- 4. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v4.1 (Stable) est en ligne."}

@app.post("/analysis", ...) # Inchangé
@app.post("/analysis/refine", ...) # Inchangé

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