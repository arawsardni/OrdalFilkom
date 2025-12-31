# 🎓 Ordal Filkom

**RAG System untuk Akademik FILKOM UB**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🌐 Live Demo

**Try it now:** [https://ordalfilkom.streamlit.app/](https://ordalfilkom.streamlit.app/)

## 📸 Preview

### Chat Interface
![Main Chat Interface](assets/Screenshot%202025-12-29%20091311.png)
*Clean and intuitive chat interface untuk bertanya tentang akademik FILKOM*

### Source Citations
![Source Citations](assets/Screenshot%202025-12-29%20091402.png)
*Top-3 source ranking dengan file, halaman, dan relevance score*

### Document Browser
![Document Browser 1](assets/Screenshot%202025-12-29%20091413.png)
![Document Browser 2](assets/Screenshot%202025-12-29%20091423.png)
*Multiple sources dengan citations yang jelas*

## ✨ Key Features

### 🤖 RAG Capabilities
- **Hybrid Chunking Strategy** - LlamaParse + Hierarchical + Semantic
- **Table & Diagram Aware** - Tables extracted as markdown, diagrams described
- **Zero-Hallucination Protocol** - Balanced prompt engineering
- **High Retrieval Coverage** - top_k=30
- **Visual Source Citations** - PDF page preview untuk verifikasi sumber
- **Top-3 Source Ranking** - Menampilkan sumber paling relevan dengan confidence score
- **Conversation Memory** - Source citations persist di chat history

### 🏗️ Production Architecture
- **Modular Design** - Separated concerns (config, core, UI, utils)
- **Reusable Components** - DRY principle, easy maintenance
- **Type Hints** - Better IDE support and code documentation
- **Centralized Configuration** - Single source of truth untuk settings

### 📚 Dataset
- 19 dokumen akademik resmi FILKOM UB
- 4 kategori: Akademik Umum, Kurikulum, Skripsi/PKL, Kemahasiswaan
- Update 2025 Desember

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- API Keys: 
  - Google (Gemini) - for embeddings
  - Pinecone - for vector storage
  - Groq - for LLM inference
  - LlamaCloud - for PDF parsing

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/ordal-filkom.git
cd ordal-filkom

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment variables
cp .env.example .env
# Edit .env dengan API keys Anda

# 5. Ingest documents ke Pinecone
python scripts/ingest.py

# 6. Run application
streamlit run frontend/app.py
```

### Access
- **Web UI**: http://localhost:8501
- **Default port**: 8501

## 📁 Project Structure

```
OrdalFIlkom/
├── src/                        # Source code package
│   ├── config/                 # Configuration management
│   │   ├── settings.py         # Centralized settings
│   │   └── prompts.py          # Prompt templates
│   ├── core/                   # Business logic
│   │   ├── rag_engine.py       # RAG initialization
│   │   └── chat_handler.py     # Query processing
│   ├── ui/                     # User interface
│   │   ├── document_browser.py # Document browser UI
│   │   └── source_display.py   # Source citation UI
│   └── utils/                  # Utilities
│       ├── metadata.py         # Metadata extraction
│       └── pdf_renderer.py     # PDF to image
├── scripts/                    # Standalone scripts
│   └── ingest.py               # Document ingestion
├── frontend/                   # Streamlit UI
│   └── app.py                  # Main application
├── dataset/                    # Academic documents
│   ├── 01_Akademik_Umum/
│   ├── 02_Kurikulum/
│   ├── 03_Skripsi_dan_PKL/
│   └── 04_Kemahasiswaan_dan_Lomba/
├── .env.example                # Environment template
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## 🛠️ Tech Stack

### AI/ML
- **RAG Framework**: LlamaIndex 0.10+
- **PDF Parser**: LlamaParse (tables → markdown, images → descriptions)
- **Chunking**: Hybrid strategy (Hierarchical + Semantic + Guardrails)
- **Vector Store**: Pinecone
- **LLM**: Groq (Llama 3.3 70B Versatile)
- **Embeddings**: Google Gemini text-embedding-004

### Backend
- **Language**: Python 3.10+
- **PDF Processing**: PyMuPDF (fitz) + LlamaParse
- **Image Processing**: Pillow

### Frontend
- **Framework**: Streamlit 1.31+
- **UI**: Interactive chat interface dengan source citations

## 🔧 Development

### Adding New Documents
1. Place PDF in appropriate `dataset/` category folder
2. Follow naming convention: `YYYY_Kategori_Judul.pdf`
3. Run ingestion: `python scripts/ingest.py`

### Modifying Prompts
Edit `src/config/prompts.py` untuk experiment dengan prompt engineering.

### Extending Functionality
- **New LLM**: Modify `src/core/rag_engine.py`
- **New UI Component**: Add to `src/ui/`
- **New Utility**: Add to `src/utils/`

## 🎯 Roadmap

### ✅ Completed
- [x] Core RAG implementation
- [x] Visual PDF citations
- [x] Modular architecture
- [x] **LlamaParse integration** (table/diagram extraction)
- [x] **Hybrid chunking strategy** (Hierarchical + Semantic + Guardrails)

### 🚧 In Progress / Future
- [ ] Hybrid retrieval (Vector + BM25)
- [ ] RAG evaluation
- [ ] Automated testing (pytest)

## 📝 License

MIT License - feel free to use for your projects!

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

⭐ **Star this repo if you find it useful!**
