# 🎓 Ordal Filkom

**RAG System untuk Akademik FILKOM UB**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

> Arah produk, prinsip, batasan (zero cost), dan roadmap: [docs/PRODUCT.md](docs/PRODUCT.md)

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
  - Pinecone - for vector store & embeddings (inference API)
  - Pinecone - for vector storage
  - Groq - for LLM inference
  - LlamaCloud - for PDF parsing

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/ordal-filkom.git
cd ordal-filkom

# 2. Install dependencies (membuat .venv otomatis via uv)

# (uv: https://docs.astral.sh/uv/getting-started/installation/)
uv sync

# 3. Setup environment variables
cp .env.example .env
# Edit .env dengan API keys Anda

# 4. Ingest documents ke Pinecone
uv run scripts/ingest.py

# 5. Run application
uv run streamlit run frontend/app.py
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
│   │   ├── rag_engine.py       # Retrieval (Pinecone) + Groq LLM clients
│   │   ├── chat_handler.py     # Answer generation from numbered sources
│   │   ├── citations.py        # [n] citations -> cited pages (+ highlight phrase)
│   │   └── embeddings.py       # Pinecone inference embeddings
│   ├── ui/                     # User interface
│   │   ├── dataset_browser.py  # Document browser + PDF.js viewer dialog
│   │   └── source_display.py   # Cited pages under each answer
│   └── utils/                  # Utilities
│       └── metadata.py         # Metadata extraction
├── scripts/                    # Standalone scripts
│   ├── ingest.py               # Document ingestion
│   └── eval.py                 # RAG evaluation
├── eval/                       # Evaluation
│   ├── dataset.jsonl           # Questions + reference answers + source pages
│   └── results/                # Saved eval runs (compare over time)
├── frontend/                   # Streamlit UI
│   └── app.py                  # Main application
├── static/                     # Served at app/static/ (server.enableStaticServing)
│   ├── dataset/                # Academic documents (PDF)
│   │   ├── 01_Akademik_Umum/
│   │   ├── 02_Kurikulum/
│   │   ├── 03_Skripsi_dan_PKL/
│   │   └── 04_Kemahasiswaan_dan_Lomba/
│   └── pdfjs/                  # Mozilla PDF.js viewer (v6.3.289, legacy build)
├── .streamlit/config.toml      # Enables static file serving
├── .env.example                # Environment template
├── pyproject.toml              # Dependencies (uv)
├── uv.lock                     # Lockfile
└── README.md                   # This file
```

## 🛠️ Tech Stack

### AI/ML
- **RAG Framework**: LlamaIndex 0.10+
- **PDF Parser**: LlamaParse (tables → markdown, images → descriptions)
- **Chunking**: Hybrid strategy (Hierarchical + Semantic + Guardrails)
- **Vector Store**: Pinecone
- **LLM**: Groq (GPT-OSS 120B, fallback Qwen3.8 27B / GPT-OSS 20B)
- **Embeddings**: Pinecone inference llama-text-embed-v2 (768 dim)

### Backend
- **Language**: Python 3.10+
- **PDF Processing**: PyMuPDF (fitz) + LlamaParse
- **Image Processing**: Pillow

### Frontend
- **Framework**: Streamlit 1.31+
- **UI**: Interactive chat interface dengan source citations
- **PDF Viewer**: [PDF.js](https://github.com/mozilla/pdf.js) (viewer Firefox) di-embed lewat iframe. Viewer bawaan Chrome tidak bisa di-embed langsung karena Streamlit Cloud menjalankan app di iframe ber-`sandbox`.

## 🔧 Development

### Adding New Documents
1. Place PDF in appropriate `static/dataset/` category folder
2. Follow naming convention: `YYYY_Kategori_Judul.pdf`
3. Run ingestion: `uv run scripts/ingest.py`

### Evaluation
`eval/dataset.jsonl` berisi pertanyaan dengan jawaban referensi dan halaman sumber yang sudah dicek ke PDF asli. Setiap perubahan pada chunking, retrieval, atau prompt sebaiknya diukur dulu:

```bash
uv run scripts/eval.py --check-dataset          # cek kunci jawaban vs PDF asli (tanpa API)
uv run scripts/eval.py --label <nama>           # retrieval: hit@k & MRR (cepat)
uv run scripts/eval.py --answers --label <nama> # + jawaban: groundedness & kebenaran (~20 menit)
```

`--answers` mengukur **groundedness** (metrik utama, lihat [docs/PRODUCT.md](docs/PRODUCT.md)): faithfulness klaim terhadap konteks, apakah sumber yang ditampilkan memuat halaman kunci jawaban, dan penolakan (out-of-scope ditolak, pertanyaan biasa tidak ditolak), plus kebenaran terhadap jawaban referensi. Judge-nya Gemini (`GOOGLE_API_KEY`), supaya eval tidak menghabiskan kuota Groq yang dipakai app live. Satu run penuh tetap memakai sekitar 170k token Groq untuk menghasilkan jawaban, jadi gunakan `--only` untuk percobaan kecil.

Hasil tiap run tersimpan di `eval/results/` untuk dibandingkan antar eksperimen.

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
