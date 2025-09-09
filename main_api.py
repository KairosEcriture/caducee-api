# =============================================================================
# CADUCEE - BACKEND API
# Version : 3.0 (Grand Chelem - Dialogue Intelligent & Recommandation Nuancée)
# Date : 08/09/2025
# =============================================================================
import os; import json; from fastapi import FastAPI, HTTPException; from pydantic import BaseModel; from typing import List, Dict, Optional; import google.generativeai as genai; from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="3.0.0")
origins = ["https://caducee-frontend.onrender.com", "http://localhost", "http://localhost:8080"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],)
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e: GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES ---
class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; answer_type: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel):
    next_question: Optional[str] = None
    answer_type: str = "yes_no"
    final_recommendation: Optional[str] = None
    severity_level: Optional[str] = None

# --- 3. FONCTIONS ---
def clean_gemini_response(raw_text: str) -> dict:
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if not match: raise ValueError("Aucun JSON trouvé dans la réponse de l'IA.")
    json_str = match.group(0)
    try: return json.loads(json_str)
    except json.JSONDecodeError as e: raise ValueError(f"JSON invalide. Erreur: {e}")

# --- 4. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v3.0 (Grand Chelem) est en ligne."}

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    prompt = f"""
    Analyse les symptômes suivants : "{request.symptoms}".
    Fournis une pré-analyse structurée. Ta réponse DOIT être un objet JSON valide avec 6 clés :
    1. "symptom": Un résumé court du symptôme principal.
    2. "differential_diagnoses": Une liste de 5 diagnostics différentiels possibles.
    3. "questions_to_ask": Une liste de 5 questions pertinentes.
    4. "first_question": La première question de la liste "questions_to_ask".
    5. "answer_type": Le type de réponse attendu pour la "first_question" (soit "yes_no", soit "open_text").
    6. "recommendations": Une liste de 3 conseils de première intention.
    7. "disclaimer": Le message d'avertissement standard.
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
    - Si action 1: objet avec "next_question" ET "answer_type" ("yes_no" ou "open_text").
    - Si action 2: objet avec "severity_level" ("Bénin", "Modéré", "Urgent") ET "final_recommendation".
    """
    try:
        response = model.generate_content(prompt)
        refine_data = clean_gemini_response(response.text)
        return RefineResponse(**refine_data)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur IA: {e}")

