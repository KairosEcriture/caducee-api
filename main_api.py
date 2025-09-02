# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 1.5 (Correction du bug de CORS)
#  Date : 02/09/2025
# =============================================================================
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="1.5.0")

# --- LA CORRECTION EST ICI ---
origins = [
    "https://caducee-frontend.onrender.com",
    "http://localhost",
    "http://localhost:8080", # Au cas où vous testeriez en local avec certains outils
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# --- FIN DE LA CORRECTION ---

try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Erreur de configuration de Gemini : {e}")
    GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES ---
class SymptomRequest(BaseModel):
    symptoms: str

class AnalysisResponse(BaseModel):
    symptom: str
    differential_diagnoses: List[str]
    questions_to_ask: List[str]
    recommendations: List[str]
    disclaimer: str

# --- 3. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root():
    return {"status": "Caducée API v1.5 est en ligne."}

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="Clé API Google non configurée sur le serveur.")

    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    prompt = f"""
    Analyse les symptômes suivants : "{request.symptoms}".
    Fournis une pré-analyse structurée. Ta réponse DOIT être un objet JSON valide.
    L'objet JSON doit contenir 5 clés :
    1. "symptom": Un résumé court du symptôme principal.
    2. "differential_diagnoses": Une liste de 5 à 7 diagnostics différentiels possibles, du plus probable au moins probable.
    3. "questions_to_ask": Une liste de 5 à 7 questions pertinentes à poser au patient pour affiner l'analyse.
    4. "recommendations": Une liste de 3 à 5 conseils de première intention.
    5. "disclaimer": Le message d'avertissement suivant : "Attention : Cette analyse est générée par une IA et ne constitue pas un diagnostic médical. Consultez un professionnel de santé qualifié pour un avis médical."
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        analysis_data = json.loads(cleaned_response)
        
        return AnalysisResponse(
            symptom=analysis_data.get("symptom", "N/A"),
            differential_diagnoses=analysis_data.get("differential_diagnoses", []),
            questions_to_ask=analysis_data.get("questions_to_ask", []),
            recommendations=analysis_data.get("recommendations", []),
            disclaimer=analysis_data.get("disclaimer", "")
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erreur de communication avec l'IA: {e}")