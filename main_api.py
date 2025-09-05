# =============================================================================
# CADUCEE - BACKEND API
# Version : 2.0 (Ajout de logs de débogage pour Gemini)
# Date : 05/09/2025
# =============================================================================
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="2.0.0")
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
class RefineResponse(BaseModel): next_question: Optional[str] = None; final_recommendation: Optional[str] = None

# --- 3. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v2.0 (Debug) est en ligne."}

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    prompt = f'Analyse : "{request.symptoms}". Réponse JSON...';
    try:
        response = model.generate_content(prompt)
        # --- LE MOUCHARD EST ICI ---
        print(f"Réponse brute de Gemini: {response.text}")
        # --- FIN DU MOUCHARD ---
        
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        analysis_data = json.loads(cleaned_response)
        questions = analysis_data.get("questions_to_ask", [])
        return AnalysisResponse(symptom=analysis_data.get("symptom", "N/A"), differential_diagnoses=analysis_data.get("differential_diagnoses", []), first_question=questions[0] if questions else "Avez-vous d'autres symptômes ?", recommendations=analysis_data.get("recommendations", []), disclaimer=analysis_data.get("disclaimer", ""))
    except Exception as e:
        print(f"ERREUR CRITIQUE lors de l'analyse : {e}")
        raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    prompt = f'Contexte: "{request.symptoms}". Historique: {history_str}. Tâche: Prochaine question ou recommandation finale. Réponse JSON...';
    try:
        response = model.generate_content(prompt)
        # --- LE MOUCHARD EST ICI AUSSI ---
        print(f"Réponse brute de Gemini (affinage): {response.text}")
        # --- FIN DU MOUCHARD ---

        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        refine_data = json.loads(cleaned_response)
        return RefineResponse(next_question=refine_data.get("next_question"), final_recommendation=refine_data.get("final_recommendation"))
    except Exception as e:
        print(f"ERREUR CRITIQUE lors de l'affinage : {e}")
        raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")