import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()


class Settings:    
    # API Keys
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
    
    @staticmethod
    def get_google_api_key():
        """Only used by scripts/eval.py for the Gemini judge"""
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    # Vector Store Configuration
    INDEX_NAME = "ordal-filkom-v2"
    
    # Model Configuration
    EMBEDDING_MODEL = "llama-text-embed-v2"  # hosted by Pinecone inference
    EMBEDDING_DIM = 768
    
    # LLM Configuration with Fallback
    LLM_MODEL = "openai/gpt-oss-120b"  # Primary model
    LLM_TEMPERATURE = 0.2
    SIMILARITY_TOP_K = 10  # chunks sent to the LLM as numbered sources
    HISTORY_TURNS = 3  # earlier question/answer pairs sent with each question
    HISTORY_MAX_CHARS = 800  # per earlier message
    FOLLOW_UP_MAX_WORDS = 6  # shorter questions are retrieved together with the previous question
    
    # Fallback models (ordered by priority when primary hits rate limit)
    # Format: (model_name, TPM_limit, description, note)
    FALLBACK_MODELS = [
        ("qwen/qwen3.8-27b", 8000, "Qwen3.8 27B", "mid 🙂"),
        ("openai/gpt-oss-20b", 8000, "GPT-OSS 20B", "agak kocaks 😹"),
    ]
    
    # Eval judge: a different provider than the app, so evals don't spend the live app's Groq quota
    JUDGE_MODEL = "gemini-3.5-flash-lite"
    
    @staticmethod
    def get_all_available_models():
        """
        Get list of all available models (primary + fallbacks)
        
        Returns:
            list: List of dicts with model metadata
                - model: model identifier
                - description: human-readable name
                - tpm: tokens per minute limit
                - note: fun description
        """
        models = [
            {
                "model": Settings.LLM_MODEL,
                "description": "GPT-OSS 120B",
                "tpm": "8,000",
                "note": "paling bagus 🔥"
            }
        ]
        
        # Add fallback models
        for model_name, tpm_limit, description, note in Settings.FALLBACK_MODELS:
            models.append({
                "model": model_name,
                "description": description,
                "tpm": f"{tpm_limit:,}",
                "note": note
            })
        
        return models
    
    # Paths
    STATIC_DIR = "static"  # served at app/static/ (server.enableStaticServing)
    DATASET_DIR = "static/dataset"
    
    # UI Configuration
    PAGE_TITLE = "Ordal Filkom - Asisten Akademik"
    PAGE_ICON = "🎓"
    LAYOUT = "centered"
    
    # PDF viewer
    PDF_VIEWER_HEIGHT = 700  # px
