# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 2.9 (Nettoyage robuste de la réponse IA et prompt final)
#  Date : 08/09/2025
# =============================================================================
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="2.9.0")
origins = ["https://caducee-frontend.onrender.com", "http://localhost", "http://localhost:8080"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"],)
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e: GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES ---
class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel):
    next_question: Optional[str] = None
    answer_type: str = "yes_no"
    final_recommendation: Optional[str] = None
    severity_level: Optional[str] = None

# --- 3. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v2.9 (Stable) est en ligne."}

def clean_gemini_response(raw_text: str) -> dict:
    # Trouve le début et la fin du JSON
    start = raw_text.find('{')
    end = raw_text.rfind('}') + 1
    if start == -1 or end == 0:
        raise ValueError("Aucun objet JSON trouvé dans la réponse de l'IA.")
    
    json_str = raw_text[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"La réponse de l'IA n'est pas un JSON valide, même après nettoyage. Erreur: {e}")

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    prompt = f'Analyse : "{request.symptoms}". Réponse JSON...';
    try:
        response = model.generate_content(prompt)
        analysis_data = clean_gemini_response(response.text)
        questions = analysis_data.get("questions_to_ask", [])
        return AnalysisResponse(symptom=analysis_data.get("symptom", "N/A"), differential_diagnoses=analysis_data.get("differential_diagnoses", []), first_question=questions[0] if questions else "Avez-vous d'autres symptômes ?", recommendations=analysis_data.get("recommendations", []), disclaimer=analysis_data.get("disclaimer", ""))
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    
    prompt = f"""
    ROLE: Tu es un assistant médical IA.
    CONTEXTE: Un patient a décrit les symptômes initiaux suivants : "{request.symptoms}".
    Voici l'historique de la conversation : {history_str}
    
    TACHE: Choisis UNE SEULE des deux actions suivantes :
    1. Si l'historique contient MOINS de 5 questions, génère la prochaine question la plus pertinente.
    2. Si l'historique contient 5 questions ou PLUS, génère une recommandation finale.

    FORMAT DE SORTIE OBLIGATOIRE: Ta réponse DOIT être un objet JSON valide.
    - Si action 1: objet avec "next_question" et "answer_type".
    - Si action 2: objet avec "severity_level" et "final_recommendation".
    """
    
    try:
        response = model.generate_content(prompt)
        refine_data = clean_gemini_response(response.text)
        return RefineResponse(
            next_question=refine_data.get("next_question"),
            answer_type=refine_data.get("answer_type", "yes_no"),
            final_recommendation=refine_data.get("final_recommendation"),
            severity_level=refine_data.get("severity_level")
        )
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")