import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()


class Settings:    
    # API Keys
    @staticmethod
    def get_google_api_key():
        try:
            return st.secrets["GOOGLE_API_KEY"]
        except:
            return os.getenv("GOOGLE_API_KEY")
    
    @staticmethod
    def get_pinecone_api_key():
        try:
            return st.secrets["PINECONE_API_KEY"]
        except:
            return os.getenv("PINECONE_API_KEY")
    
    @staticmethod
    def get_groq_api_key():
        try:
            return st.secrets["GROQ_API_KEY"]
        except:
            return os.getenv("GROQ_API_KEY")
    
    # Vector Store Configuration
    INDEX_NAME = "ordal-filkom"
    
    # Model Configuration
    EMBEDDING_MODEL = "models/text-embedding-004"
    
    # LLM Configuration with Fallback
    LLM_MODEL = "llama-3.3-70b-versatile"  # Primary model
    LLM_TEMPERATURE = 0.2
    SIMILARITY_TOP_K = 30
    
    # Fallback models (ordered by priority when primary hits rate limit)
    # Format: (model_name, TPM_limit, description)
    FALLBACK_MODELS = [
        ("meta-llama/llama-4-scout-17b-16e-instruct", 30000, "Llama 4 Scout"),
        ("llama-3.1-8b-instant", 6000, "Llama 3.1 8B"),
    ]
    
    # Paths
    DATASET_DIR = "dataset"
    
    # UI Configuration
    PAGE_TITLE = "Ordal Filkom - Asisten Akademik"
    PAGE_ICON = "🎓"
    LAYOUT = "centered"
    
    # Chat Configuration
    MAX_RETRIES = 3
    RETRY_WAIT_BASE = 25
    TOP_SOURCES_TO_DISPLAY = 3
    PDF_RENDER_DPI = 120
