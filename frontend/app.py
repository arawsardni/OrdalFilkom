"""Streamlit frontend for Ordal Filkom - RAG Academic Assistant"""
import os
import sys
import streamlit as st
import logging

# Add parent directory to path for src imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.settings import Settings
from src.core.rag_engine import RAGEngine
from src.core.chat_handler import ChatHandler
from src.ui.source_display import display_sources

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page Configuration
st.set_page_config(
    page_title=Settings.PAGE_TITLE,
    page_icon=Settings.PAGE_ICON,
    layout=Settings.LAYOUT
)

# Initialize RAG Engine & Chat Handler
@st.cache_resource
def init_chat_handler():
    """Initialize RAG engine and chat handler (cached for performance)"""
    try:
        logger.info("Initializing RAG engine...")
        engine = RAGEngine()
        handler = ChatHandler(engine.get_engine())
        logger.info("Initialization successful")
        return handler
    except ValueError as e:
        st.error(f"❌ {str(e)}")
        logger.error(f"Initialization failed: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Gagal menginisialisasi sistem: {e}")
        logger.error(f"Unexpected initialization error: {e}")
        return None

# UI Header
st.title("🎓 Ordal Filkom")
st.markdown("*Asisten Akademik Virtual FILKOM UB (Zero Hallucination Protocol)*")

# Initialize Session State for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Load Chat Handler
chat_handler = init_chat_handler()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display sources if available (for assistant messages)
        if message["role"] == "assistant" and "sources" in message and message["sources"]:
            display_sources(message["sources"])

# Chat Input
if prompt := st.chat_input("Tanya seputar akademik FILKOM..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    if chat_handler:
        with st.chat_message("assistant"):
            with st.spinner("Sedang mencari di dokumen..."):
                # Process query with retry logic
                response_text, sources, error = chat_handler.process_query(prompt)
                
                if error:
                    # Handle errors
                    st.error(f"❌ {error}")
                    logger.error(f"Query processing failed: {error}")
                else:
                    # Display response with streaming effect (preserving markdown)
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    # Stream word by word while preserving newlines and formatting
                    import time
                    import re
                    
                    # Split but keep whitespace and newlines
                    # This regex splits on spaces but keeps newlines
                    tokens = re.findall(r'\S+|\n', response_text)
                    
                    for i, token in enumerate(tokens):
                        if token == '\n':
                            full_response += '\n'
                        else:
                            full_response += token
                            # Add space after word (except before newline or at end)
                            if i < len(tokens) - 1 and tokens[i + 1] != '\n':
                                full_response += ' '
                        
                        # Update placeholder with accumulated text (with markdown rendering)
                        message_placeholder.markdown(full_response + "▌")  
                        time.sleep(0.05)
                    
                    # Final render without cursor
                    message_placeholder.markdown(full_response)
                    
                    # Display sources with PDF preview
                    if sources:
                        display_sources(sources)
                    
                    # Save to session state (with sources for persistence)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "sources": sources if sources else []
                    })
    else:
        st.error("❌ Sistem belum siap. Cek API Keys di .env file.")

# Footer
st.markdown("---")
st.caption("⚠️ Disclaimer: Ordal Filkom adalah asisten AI. Mohon cek kembali dokumen asli untuk kepastian hukum.")
