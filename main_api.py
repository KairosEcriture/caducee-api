# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 1.6 (Implémentation du Dialogue Guidé)
#  Date : 02/09/2025
# =============================================================================
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="1.6.0")

origins = ["https://caducee-frontend.onrender.com", "http://localhost", "http://localhost:8080"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["GET", "POST"], allow_headers=["*"],
)

try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e: GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES ---
class SymptomRequest(BaseModel):
    symptoms: str

class AnalysisResponse(BaseModel):
    symptom: str
    differential_diagnoses: List[str]
    first_question: str # Changement : on ne renvoie que la première question
    recommendations: List[str]
    disclaimer: str

class RefineRequest(BaseModel):
    symptoms: str
    history: List[Dict[str, str]] # ex: [{"question": "...", "answer": "..."}]

class RefineResponse(BaseModel):
    next_question: Optional[str] = None # Il n'y a peut-être pas de question suivante
    final_recommendation: Optional[str] = None # Si le dialogue est terminé

# --- 3. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v1.6 est en ligne."}

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    prompt = f"""
    Analyse les symptômes suivants : "{request.symptoms}".
    Fournis une pré-analyse structurée. Ta réponse DOIT être un objet JSON valide avec 5 clés :
    1. "symptom": Un résumé court du symptôme principal.
    2. "differential_diagnoses": Une liste de 5 diagnostics différentiels possibles.
    3. "questions_to_ask": Une liste de 5 questions pertinentes à poser au patient.
    4. "recommendations": Une liste de 3 conseils de première intention.
    5. "disclaimer": Le message d'avertissement standard.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        analysis_data = json.loads(cleaned_response)
        
        questions = analysis_data.get("questions_to_ask", [])
        
        return AnalysisResponse(
            symptom=analysis_data.get("symptom", "N/A"),
            differential_diagnoses=analysis_data.get("differential_diagnoses", []),
            first_question=questions[0] if questions else "Avez-vous d'autres symptômes ?",
            recommendations=analysis_data.get("recommendations", []),
            disclaimer=analysis_data.get("disclaimer", "")
        )
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur de communication avec l'IA: {e}")

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    
    prompt = f"""
    Contexte : Un patient a décrit les symptômes initiaux suivants : "{request.symptoms}".
    Voici l'historique des questions déjà posées et des réponses du patient :
    {history_str}
    
    Tâche : En te basant sur tout ce contexte, détermine la prochaine question la plus pertinente à poser pour affiner le diagnostic, OU si tu as assez d'informations, fournis une recommandation finale.
    Ta réponse DOIT être un objet JSON valide avec une seule clé :
    - Soit "next_question" (une chaîne de caractères contenant la question).
    - Soit "final_recommendation" (une chaîne de caractères contenant la recommandation finale et le disclaimer).
    Ne fournis qu'une seule de ces deux clés.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        refine_data = json.loads(cleaned_response)
        
        return RefineResponse(
            next_question=refine_data.get("next_question"),
            final_recommendation=refine_data.get("final_recommendation")
        )
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur de communication avec l'IA: {e}")