# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 2.6 (Recommandation Nuancée avec Niveau de Gravité)
#  Date : 05/09/2025
# =============================================================================
import os; import json; from fastapi import FastAPI, HTTPException; from pydantic import BaseModel; from typing import List, Dict, Optional; import google.generativeai as genai; from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="2.6.0")
origins = ["https://caducee-frontend.onrender.com", "http://localhost", "http://localhost:8080"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"],)
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e: GOOGLE_API_KEY = None

# --- 2. MODÈLES DE DONNÉES (mis à jour) ---
class SymptomRequest(BaseModel): symptoms: str
class AnalysisResponse(BaseModel): symptom: str; differential_diagnoses: List[str]; first_question: str; recommendations: List[str]; disclaimer: str
class RefineRequest(BaseModel): symptoms: str; history: List[Dict[str, str]]
class RefineResponse(BaseModel):
    next_question: Optional[str] = None
    answer_type: str = "yes_no"
    final_recommendation: Optional[str] = None
    severity_level: Optional[str] = None # NOUVEAU CHAMP

# --- 3. ENDPOINTS API ---
@app.get("/", tags=["Status"])
def read_root(): return {"status": "Caducée API v2.6 (Recommandation Nuancée) est en ligne."}

def clean_gemini_response(raw_text: str) -> dict:
    cleaned_text = raw_text.strip().replace("```json", "").replace("```", "").strip()
    try: return json.loads(cleaned_text)
    except json.JSONDecodeError:
        try: return json.loads(cleaned_text.replace("'", '"'))
        except Exception: raise ValueError("La réponse de l'IA n'est pas un JSON valide.")

@app.post("/analysis", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_symptoms(request: SymptomRequest):
    # ... (code inchangé)
    return ...

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    history_str = "\n".join([f"Q: {h['question']}\nA: {h['answer']}" for h in request.history])
    
    # === LE PROMPT FINAL ET CORRIGÉ ===
    prompt = f"""
    ROLE: Tu es un assistant médical IA.
    CONTEXTE: Un patient a décrit les symptômes initiaux suivants : "{request.symptoms}".
    Voici l'historique de la conversation : {history_str}
    
    TACHE: Choisis UNE SEULE des deux actions suivantes :
    1. Si tu as besoin de plus d'informations, génère la prochaine question.
    2. Si tu as assez d'informations, génère une recommandation finale.

    FORMAT DE SORTIE OBLIGATOIRE: Ta réponse DOIT être un objet JSON valide.
    - Si tu choisis l'action 1, l'objet doit avoir DEUX clés : "next_question" et "answer_type" ("yes_no" ou "open_text").
    - Si tu choisis l'action 2, l'objet doit avoir DEUX clés : "severity_level" (une chaîne parmi "Bénin", "Consultation recommandée", "Urgent") ET "final_recommendation" (la recommandation détaillée).
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