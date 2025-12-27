import os
import streamlit as st
import logging
from dotenv import load_dotenv
from utils import render_pdf_page

from llama_index.core import (
    VectorStoreIndex,
    Settings,
    StorageContext,
    PromptTemplate
)
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.groq import Groq
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from pinecone import Pinecone

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Env
load_dotenv()

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]   
except:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

INDEX_NAME = "ordal-filkom"

# Page Config
st.set_page_config(
    page_title="Ordal Filkom - Asisten Akademik",
    page_icon="🎓",
    layout="centered"
)

# Initialize Resources (Cached)
@st.cache_resource
def init_chat_engine():
    if not GOOGLE_API_KEY or not PINECONE_API_KEY or not GROQ_API_KEY:
        st.error("API Keys missing in .env (Check GOOGLE, PINECONE, and GROQ)")
        return None

    # Settings
    Settings.embed_model = GoogleGenAIEmbedding(
        model_name="models/text-embedding-004", api_key=GOOGLE_API_KEY
    )
    Settings.llm = Groq(
        model="llama-3.3-70b-versatile", 
        api_key=GROQ_API_KEY,
        temperature=0.2
    )

    # Pinecone Connection
    pc = Pinecone(api_key=PINECONE_API_KEY)
    vector_store = PineconeVectorStore(
        pinecone_index=pc.Index(INDEX_NAME)
    )
    
    # Load Index
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    # STRICT QA PROMPT
    qa_prompt_tmpl = (
        "Anda adalah Ordal Filkom, asisten akademik yang membantu mahasiswa FILKOM UB. "
        "Tugas utama Anda adalah menjawab pertanyaan berdasarkan DOKUMEN yang diberikan.\n"
        "---------------------\n"
        "DOKUMEN:\n"
        "{context_str}\n"
        "---------------------\n"
        "Pertanyaan: {query_str}\n\n"
        "ATURAN PENTING:\n"
        "1. Jawab HANYA berdasarkan informasi di atas. Jika tidak ada, katakan 'Maaf, info tidak ditemukan.'\n"
        "2. Jangan menambah-nambahkan informasi yang tidak ada di dokumen (Anti-Halusinasi).\n"
        "3. SITASI WAJIB: Di akhir jawaban, tuliskan sumber referensi yang Anda gunakan.\n"
        "   Lihat metadata 'file_name' dan 'page_label' pada setiap bagian dokumen di atas.\n"
        "   Format: (Sumber: [Nama File], Halaman [Hal])\n"
        "Jawaban:"
    )
    qa_prompt = PromptTemplate(qa_prompt_tmpl)

    # Chat Engine
    chat_engine = index.as_chat_engine(
        chat_mode="context",
        text_qa_template=qa_prompt,
        similarity_top_k=7
    )
    return chat_engine

# UI Logic
st.title("🎓 Ordal Filkom")
st.markdown("*Asisten Akademik Virtual FILKOM UB (Zero Hallucination Protocol)*")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Load Engine
chat_engine = init_chat_engine()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display sources if available (for assistant messages)
        if message["role"] == "assistant" and "sources" in message and message["sources"]:
            st.markdown("---")
            st.markdown("### 📚 Sumber Referensi")
            
            for idx, source_info in enumerate(message["sources"], 1):
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{idx}. {source_info['file_name']}**")
                        st.caption(f"📄 Halaman {source_info['page']} • 📁 {source_info['category']}")
                    with col2:
                        st.metric("Relevansi", source_info['score'], label_visibility="collapsed")
                    
                    # Show PDF page preview
                    with st.expander("👁️ Lihat halaman PDF"):
                        pdf_path = os.path.join("dataset", source_info['category'], source_info['file_name'])
                        
                        if os.path.exists(pdf_path):
                            try:
                                page_num = int(source_info['page']) - 1 if source_info['page'] != 'Unknown' else 0
                                img = render_pdf_page(pdf_path, page_num, dpi=120)
                                
                                if img:
                                    st.image(img, caption=f"Halaman {source_info['page']} dari {source_info['file_name']}", use_container_width=True)
                                else:
                                    st.warning("Gagal merender halaman PDF")
                            except Exception as e:
                                st.error(f"Error menampilkan PDF: {e}")
                        else:
                            st.warning(f"File tidak ditemukan: {pdf_path}")
                    
                    if idx < len(message["sources"]):
                        st.divider()

# Chat Input
if prompt := st.chat_input("Tanya seputar akademik FILKOM..."):
    # User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant Response
    if chat_engine:
        with st.chat_message("assistant"):
            with st.spinner("Sedang mencari di dokumen..."):
                retry_count = 0
                max_retries = 3
                while retry_count < max_retries:
                    try:
                        response = chat_engine.chat(prompt)
                        st.markdown(response.response)
                        
                        # DISPLAY SOURCES IN USER-FRIENDLY FORMAT
                        sources_data = []  # Store sources for session state
                        
                        if response.source_nodes:
                            st.markdown("---")
                            st.markdown("### 📚 Sumber Referensi")
                            
                            # Show top 3 most relevant sources
                            for idx, node in enumerate(response.source_nodes[:3], 1):
                                file_name = node.metadata.get('file_name', 'Unknown')
                                page = node.metadata.get('page_label', 'Unknown')
                                category = node.metadata.get('category', 'Unknown')
                                score = f"{node.score:.0%}" if node.score is not None else "N/A"
                                
                                # Store source info for later display
                                sources_data.append({
                                    'file_name': file_name,
                                    'page': page,
                                    'category': category,
                                    'score': score
                                })
                                
                                # Create a nice card for each source
                                with st.container():
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.markdown(f"**{idx}. {file_name}**")
                                        st.caption(f"📄 Halaman {page} • 📁 {category}")
                                    with col2:
                                        st.metric("Relevansi", score, label_visibility="collapsed")
                                    
                                    # Show PDF page preview
                                    with st.expander("👁️ Lihat halaman PDF"):
                                        # Construct PDF path
                                        pdf_path = os.path.join("dataset", category, file_name)
                                        
                                        if os.path.exists(pdf_path):
                                            try:
                                                # Convert page label to 0-indexed page number
                                                page_num = int(page) - 1 if page != 'Unknown' else 0
                                                
                                                # Render PDF page
                                                img = render_pdf_page(pdf_path, page_num, dpi=120)
                                                
                                                if img:
                                                    st.image(img, caption=f"Halaman {page} dari {file_name}", use_container_width=True)
                                                else:
                                                    st.warning("Gagal merender halaman PDF")
                                            except Exception as e:
                                                st.error(f"Error menampilkan PDF: {e}")
                                        else:
                                            st.warning(f"File tidak ditemukan: {pdf_path}")
                                    
                                    if idx < len(response.source_nodes[:3]):
                                        st.divider()

                        # Save message WITH sources to session state
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response.response,
                            "sources": sources_data  # Include sources!
                        })
                        break # Success, exit loop
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            retry_count += 1
                            if retry_count == max_retries:
                                st.error(f"Maaf, server atau kuota sedang penuh. Silakan coba lagi nanti. (Error: {e})")
                            else:
                                wait_time = 25 * retry_count  # Increased from 5 to 25 to match the ~20s wait typical of free tier
                                st.warning(f"Kuota sibuk. Menunggu {wait_time} detik sebelum mencoba lagi... ({retry_count}/{max_retries})")
                                import time
                                time.sleep(wait_time)
                        else:
                            st.error(f"Terjadi kesalahan: {e}")
                            break
    else:
        st.error("Sistem belum siap. Cek API Keys.")

# Footer
st.markdown("---")
st.caption("Disclaimer: Ordal Filkom adalah asisten AI. Mohon cek kembali dokumen asli untuk kepastian hukum.")
