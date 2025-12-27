import os
import streamlit as st
import logging
from dotenv import load_dotenv

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
                        
                        # PRIMARY REFERENCE (Top 1)
                        if response.source_nodes:
                            top_node = response.source_nodes[0]
                            file_name = top_node.metadata.get('file_name', 'Unknown')
                            page = top_node.metadata.get('page_label', 'Unknown')
                            # Handle potential None score
                            score = f"{top_node.score:.2f}" if top_node.score is not None else "N/A"
                            
                            st.info(f"📖 **Referensi Utama:** {file_name} (Halaman {page}) | Relevansi: {score}")

                        # DEBUG: Show Source Nodes
                        with st.expander("🔍 Lihat Semua Sumber (Debug)"):
                            for node in response.source_nodes:
                                st.markdown(f"**File:** `{node.metadata.get('file_name', 'Unknown')}`")
                                st.markdown(f"**Page:** `{node.metadata.get('page_label', 'Unknown')}`")
                                st.caption(node.text[:300] + "...")
                                st.divider()

                        st.session_state.messages.append({"role": "assistant", "content": response.response})
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
