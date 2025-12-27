# 🎓 Ordal Filkom

**Production-Ready RAG System untuk Akademik FILKOM UB**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

> Agentic RAG-powered academic assistant dengan systematic evaluation, modern architecture, dan user-friendly interface.

## ✨ Key Features

### 🤖 Advanced RAG Capabilities
- **Zero-Hallucination Protocol** - Strict prompt engineering untuk jawaban akurat
- **Visual Source Citations** - PDF page preview untuk verifikasi mudah
- **Top-3 Source Ranking** - Menampilkan sumber paling relevan dengan confidence score
- **Conversation Memory** - Source citations persist di chat history

### 🏗️ Production Architecture
- **Modular Design** - Separated concerns (config, core, UI, utils)
- **Reusable Components** - DRY principle, easy maintenance
- **Type Hints** - Better IDE support dan code documentation
- **Centralized Configuration** - Single source of truth untuk settings

### 📚 Comprehensive Dataset
- 19 dokumen akademik resmi FILKOM UB
- 4 kategori: Akademik Umum, Kurikulum, Skripsi/PKL, Kemahasiswaan
- Update 2024-2025

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- API Keys: Google (Gemini), Pinecone, Groq

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/ordal-filkom.git
cd ordal-filkom

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

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
│   ├── ui/                     # UI components
│   │   └── source_display.py  # Source citation UI
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
- **Vector Store**: Pinecone (managed, production-grade)
- **LLM**: Groq (Llama 3.3 70B Versatile) - ultra-fast inference
- **Embeddings**: Google Gemini text-embedding-004 (768 dims)

### Backend
- **Language**: Python 3.10+
- **PDF Processing**: PyMuPDF (fitz)
- **Image Processing**: Pillow

### Frontend
- **Framework**: Streamlit 1.31+
- **UI**: Interactive chat interface dengan source citations

## ⚙️ Configuration

Edit `src/config/settings.py` untuk customize:

```python
# Model Configuration
EMBEDDING_MODEL = "models/text-embedding-004"
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.2
SIMILARITY_TOP_K = 7

# Display Configuration
TOP_SOURCES_TO_DISPLAY = 3
PDF_RENDER_DPI = 120
```

## 📖 Usage Examples

### Basic Query
```
User: "Berapa SKS untuk lulus S1 di FILKOM?"

Ordal: "Untuk lulus S1 di FILKOM, mahasiswa harus menempuh 
        minimal 145 SKS..."

📚 Sumber Referensi:
1. 2020_Pedoman_Akademik_FILKOM.pdf
   📄 Halaman 12 • 📁 01_Akademik_Umum
   Relevansi: 87%
   [👁️ Lihat halaman PDF - shows actual page]
```

### Complex Query
```
User: "Apa saja mata kuliah untuk learning path NLP Engineer?"

Ordal: "Learning Path NLP Engineer di S1 Teknik Informatika meliputi..."
[Shows top 3 relevant sources with page previews]
```

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

- [x] Core RAG implementation
- [x] Visual PDF citations
- [x] Modular architecture
- [ ] FastAPI REST API backend
- [ ] React TypeScript frontend
- [ ] Agentic features (multi-tool orchestration)
- [ ] RAG evaluation framework
- [ ] Automated testing (pytest)
- [ ] Docker deployment
- [ ] CI/CD pipeline

## 📝 License

MIT License - feel free to use for your projects!

## 🙏 Acknowledgments

- **FILKOM UB** untuk dataset dokumen akademik
- **DOT Indonesia** untuk inspirasi tech stack
- **LlamaIndex** untuk RAG framework
- **Streamlit** untuk rapid UI development

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📧 Contact

Built by [Your Name] as portfolio project untuk AI Engineer internship application.

---

⭐ **Star this repo if you find it useful!**
