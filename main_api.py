# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 1.9 (Correction du bug de clé dans l'historique)
#  Date : 02/09/2025
# =============================================================================
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="1.9.0")
# ... (le reste de la configuration CORS est correct)

# --- 2. MODÈLES DE DONNÉES ---
# ... (SymptomRequest et AnalysisResponse sont corrects)

class RefineRequest(BaseModel):
    symptoms: str
    # LA CORRECTION EST ICI : On s'attend à recevoir une liste de dictionnaires
    # avec les clés 'role' et 'content'
    history: List[Dict[str, str]]

class RefineResponse(BaseModel):
    next_question: Optional[str] = None
    final_recommendation: Optional[str] = None

# ... (le reste du code est correct)

@app.post("/analysis/refine", response_model=RefineResponse, tags=["Analysis"])
async def refine_analysis(request: RefineRequest):
    if not GOOGLE_API_KEY: raise HTTPException(status_code=500, detail="Clé API Google non configurée.")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    # LA CORRECTION EST ICI : On lit 'role' et 'content'
    history_str = "\n".join([f"{h['role']}: {h['content']}" for h in request.history])
    
    prompt = f"""
    Contexte : Un patient a décrit les symptômes initiaux suivants : "{request.symptoms}".
    Voici l'historique de la conversation :
    {history_str}
    
    Tâche : En te basant sur tout ce contexte, détermine la prochaine question la plus pertinente à poser, OU si tu as assez d'informations, fournis une recommandation finale.
    Ta réponse DOIT être un objet JSON valide avec une seule clé :
    - Soit "next_question".
    - Soit "final_recommendation".
    """
    try:
        response = model.generate_content(prompt)
        # ... (le reste de la fonction est correct)
    except Exception as e: raise HTTPException(status_code=503, detail=f"Erreur de communication avec l'IA: {e}")