# =============================================================================
#  CADUCEE - BACKEND API
#  Version : 6.1.1 (Correction finale de la politique CORS)
#  Date : 14/09/2025
# =============================================================================
import os; import json; import google.generativeai as genai; import googlemaps; import re; import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone, date
from sqlmodel import Field, Session, SQLModel, create_engine, select
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv()
app = FastAPI(title="Caducée API", version="6.1.1")

# === LA CORRECTION CORS DÉFINITIVE EST ICI ===
origins = ["*"] # On autorise TOUT LE MONDE pour le dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# === FIN DE LA CORRECTION ===

# ... (le reste du code de la V6.1 est identique et correct)