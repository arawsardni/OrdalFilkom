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
from src.ui.dataset_browser import render_dataset_browser, render_pdf_preview

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page Configuration
st.set_page_config(
    page_title=Settings.PAGE_TITLE,
    page_icon=Settings.PAGE_ICON,
    layout=Settings.LAYOUT
)


# Render dataset browser in sidebar
render_dataset_browser()

# Initialize RAG Engine & Chat Handler
@st.cache_resource
def init_chat_handler():
    try:
        logger.info("Initializing RAG engine...")
        engine = RAGEngine()
        handler = ChatHandler(engine.get_engine())
        logger.info("Initialization successful")
        return handler
    except ValueError as e:
        st.error(f"Error: {str(e)}")
        logger.error(f"Initialization failed: {e}")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        logger.error(f"Unexpected initialization error: {e}")
        return None

# UI Header
st.title("🎓 Ordal Filkom")
st.markdown("*Asisten Akademik Virtual FILKOM UB (Zero Hallucination Protocol)*")

# Initialize Session State for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize session state for retry mechanism
if "pending_retry" not in st.session_state:
    st.session_state.pending_retry = None
if "available_models" not in st.session_state:
    st.session_state.available_models = None

# Load Chat Handler
chat_handler = init_chat_handler()

# Render PDF viewer dialog if selected from sidebar
render_pdf_preview()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display sources if available (for assistant messages)
        if message["role"] == "assistant" and "sources" in message and message["sources"]:
            display_sources(message["sources"])

# Show retry UI if there's a pending retry with model options
if st.session_state.pending_retry and st.session_state.available_models:
    st.warning(f"⚠️ Rate limit pada model sebelumnya. Pilih model alternatif untuk retry:")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        retry_model = st.selectbox(
            "Pilih Model Alternatif:",
            options=[m["model"] for m in st.session_state.available_models],
            format_func=lambda x: next(
                (f"{m['description']} ({m['tpm']} TPM)" for m in st.session_state.available_models if m["model"] == x),
                x
            ),
            key="retry_model_selector"
        )
    
    with col2:
        if st.button("🔄 Coba Lagi", type="primary"):
            # Update selected model in session state
            st.session_state.selected_model = retry_model
            
            # Retry the query with new model
            if chat_handler:
                with st.chat_message("assistant"):
                    with st.spinner("Mencoba dengan model alternatif..."):
                        response_text, sources, error, model_options = chat_handler.process_query(
                            st.session_state.pending_retry,
                            model_name=retry_model
                        )
                        
                        if error:
                            st.error(error)
                            logger.error(f"Retry failed: {error}")
                            # Update available models if new options returned
                            if model_options:
                                st.session_state.available_models = model_options
                        else:
                            # Success - clear retry state
                            st.session_state.pending_retry = None
                            st.session_state.available_models = None
                            
                            # Display response
                            st.markdown(response_text)
                            
                            # Display sources
                            if sources:
                                display_sources(sources)
                            
                            # Save to session state
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": response_text,
                                "sources": sources if sources else []
                            })
                            
                            st.rerun()

# Custom CSS to make dropdown immutable (read-only)
st.markdown("""
<style>
/* Make selectbox input read-only - prevent user from typing */
div[data-baseweb="select"] input {
    caret-color: transparent !important;
    pointer-events: none !important;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "selected_model" not in st.session_state:
    st.session_state.selected_model = Settings.LLM_MODEL

# Get all models
all_models = Settings.get_all_available_models()

# Model selector in sidebar bottom
with st.sidebar:
    st.markdown("---")
    st.markdown("##### 🤖 Model")
    selected_model = st.selectbox(
        "Model",
        options=[m["model"] for m in all_models],
        format_func=lambda x: next(
            (f"{m['description']} - {m['note']}" for m in all_models if m["model"] == x),
            x
        ),
        index=[m["model"] for m in all_models].index(st.session_state.selected_model)
            if st.session_state.selected_model in [m["model"] for m in all_models]
            else 0,
        key="model_selector",
        help="Pilih model AI",
        label_visibility="collapsed"
    )
    st.session_state.selected_model = selected_model

# Normal sticky chat input
if prompt := st.chat_input("tanya apapun tentang akademik FILKOM..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    if chat_handler:
        with st.chat_message("assistant"):
            with st.spinner("sbar, msih cari ingfo dari dokumen..."):
                # Process query with user-selected model
                response_text, sources, error, model_options = chat_handler.process_query(
                    prompt, 
                    model_name=st.session_state.selected_model
                )
                
                if error and model_options:
                    # Rate limit with alternative models available
                    st.warning(error)
                    st.session_state.pending_retry = prompt
                    st.session_state.available_models = model_options
                    logger.warning(f"Rate limit on {st.session_state.selected_model}. Offering alternatives.")
                    st.rerun()  # Rerun to show retry UI
                elif error:
                    # Error without alternative models (e.g., all quota exhausted)
                    st.error(error)
                    logger.error(f"Query processing failed: {error}")
                else:
                    # Display response with streaming effect (preserving markdown)
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    # Stream word by word while preserving newlines and formatting
                    import time
                    import re
                    
                    # Split but keep whitespace and newlines
                    tokens = re.findall(r'\S+|\n', response_text)
                    
                    for i, token in enumerate(tokens):
                        if token == '\n':
                            full_response += '\n'
                        else:
                            full_response += token
                            if i < len(tokens) - 1 and tokens[i + 1] != '\n':
                                full_response += ' '
                        
                        message_placeholder.markdown(full_response + "▌")  
                        time.sleep(0.05)
                    
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
        st.error("Sistem msih kocaks. Coba cek API Keys di .env file.")

# Footer
st.markdown("---")
st.caption("⚠️ Disclaimer: Ordal Filkom cuma asisten AI, pls cek dokumen aslinya, kalo salah salah ya maap :)")

