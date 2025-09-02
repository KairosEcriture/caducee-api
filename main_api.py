# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 1.7 (Correction de la syntaxe 'Optional')
#  Date : 02/09/2025
# =============================================================================
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional # LA CORRECTION EST ICI
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware

# --- 1. CONFIGURATION ---
app = FastAPI(title="Caducée API", version="1.7.0")
# ... (le reste de la configuration CORS est correct)

# --- 2. MODÈLES DE DONNÉES ---
# ... (SymptomRequest et AnalysisResponse sont corrects)

class RefineRequest(BaseModel):
    symptoms: str
    history: List[Dict[str, str]]

class RefineResponse(BaseModel):
    next_question: Optional[str] = None # On utilise 'Optional'
    final_recommendation: Optional[str] = None # On utilise 'Optional'

# ... (le reste du code est correct)