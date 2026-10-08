# Baseline Evaluasi (v0.1-baseline)

Run: `eval/results/20261008-2119_baseline.json` (8 Oktober 2026)
Config: index `ordal-filkom-v2`, embedding `llama-text-embed-v2` (768), LLM `openai/gpt-oss-120b`, judge `qwen/qwen3.8-27b`, `top_k=30`, leaf chunk 128 token.

## Angka

**Retrieval** (22 pertanyaan yang punya sumber)

| hit@1 | hit@3 | hit@5 | hit@10 | hit@30 | MRR |
|---|---|---|---|---|---|
| 0.50 | 0.59 | 0.68 | 0.73 | 0.86 | 0.57 |

**Jawaban** (24 dinilai, 1 error timeout dikeluarkan)

| Skor | Correct | Partial | Incorrect | Median latensi |
|---|---|---|---|---|
| 0.625 | 10 | 10 | 4 | 9.7 s |

Per tipe: out_of_scope 1.00 · factual 0.64 · disambiguation 0.58 · table 0.50 · trap 0.00

**Noise:** run kedua (9 item sebelum kena limit) menghasilkan satu verdict yang berbeda (akd-03). Anggap selisih ±1 item (≈0.04) sebagai noise, bukan perbaikan.

## Temuan

1. **Prompt "Zero Hallucination" tidak pernah dipakai.** `as_chat_engine(chat_mode="context", text_qa_template=...)` mengabaikan `text_qa_template`. LLM hanya menerima prompt default LlamaIndex. Ini menjelaskan jawaban berupa tabel panjang dan kutipan `【...】` yang dikarang.
2. **LlamaParse mengarang isi halaman.** 86 halaman teks hasil parsing jauh lebih panjang dari teks PDF aslinya. Sebagian wajar (deskripsi diagram), tapi beberapa terbukti karangan:
   - sampul kurikulum SI berisi "144 SKS = 90 wajib + 54 pilihan" (aslinya 145 SKS);
   - p3 Proposal Skripsi berisi "Times New Roman 12" (aslinya Calibri, dan halaman itu cuma daftar isi).
3. **Tabel kurikulum per prodi gagal di-retrieve.** kur-04, kur-05, dan kur-07 tidak masuk top 30. Leaf chunk 128 token memotong tabel dari judulnya (nama prodi, semester), jadi chunk "Tugas Akhir / Skripsi 4" tidak membawa konteks prodinya.
4. **Halaman benar sudah di-retrieve tapi jawabannya tetap salah.** Contohnya mhs-04 (rank 1, menjawab 1000 padahal 1500) dan skr-02 (rank 1, menjawab 14 pt padahal 16 pt). Teks parsing-nya benar. Dugaannya: 30 potongan kecil yang mirip satu sama lain membuat LLM mencampur angka dari tabel lain.
5. **Dokumen kecil tenggelam oleh dokumen besar.** Jawaban akd-01 ada di dokumen 3 halaman, tapi rank-nya 26 karena kalah oleh Pedoman UB (246 halaman). Ini kandidat untuk hybrid search (BM25), karena kata kuncinya spesifik ("terlambat").
6. **Semantic refinement hampir tidak berefek.** Jumlah chunk cuma berubah dari 15.392 ke 15.398, tapi tetap memakan waktu dan biaya embedding.
7. **Out-of-scope sudah aman.** Ketiga pertanyaan di luar dokumen ditolak dengan benar, walaupun prompt anti-halusinasinya tidak aktif.

## Batasan anggaran

Groq free tier membatasi `gpt-oss-120b` di **200k token/hari**. Satu eval jawaban penuh memakai sekitar 170k token, jadi hanya muat sekitar satu run per hari. **Kuota ini juga dipakai app yang live.**

Cara kerja yang disarankan:
- Eval retrieval (`scripts/eval.py`) murah, jadi jadikan alat utama untuk eksperimen chunking/retrieval.
- `--answers` dipakai untuk konfirmasi akhir, atau dengan `--only` untuk subset.

## Hipotesis Fase 2 (urut dari yang paling murah)

| # | Eksperimen | Ukur dengan | Target |
|---|---|---|---|
| 1 | Pasang prompt dengan benar (`system_prompt`/`context_template`) | `--answers` | skor jawaban naik, terutama partial → correct |
| 2 | Chunk lebih besar (~512 token, tanpa semantic refinement) dan `top_k` lebih kecil (5–8) | retrieval, lalu `--answers` | hit@5 naik, token per query turun |
| 3 | Bersihkan halaman karangan LlamaParse (parse ulang tanpa instruksi LLM, atau pakai teks PyMuPDF untuk halaman teks biasa) | retrieval + item `trap` | trap > 0 |
| 4 | Sisipkan nama prodi/dokumen ke teks chunk (contextual chunk header) | item `disambiguation` | kur-04/05/07 masuk top 5 |
| 5 | Hybrid search (BM25 + vektor) dan/atau reranker | retrieval | akd-01 naik ke top 5 |
