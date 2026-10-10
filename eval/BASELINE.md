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

---

# Baseline Groundedness (Fase 2, langkah 1)

Run: `eval/results/20261009-2310_baseline-groundedness.json` (9 Oktober 2026)
Config sama dengan baseline di atas (prompt anti-halusinasi masih tidak aktif). Judge pindah ke `gemini-3.5-flash-lite` supaya eval tidak memakai kuota Groq app live.

## Angka

**Groundedness** (metrik utama)

| Faithfulness | Fully grounded | Sumber yang ditampilkan memuat halaman kunci | Penolakan out-of-scope | Penolakan yang salah |
|---|---|---|---|---|
| 0.874 | 0.714 | **0.591** | 1.00 | 0.045 (1 dari 22) |

- **Faithfulness:** rata-rata porsi klaim jawaban yang didukung konteks yang diterima LLM (judge Gemini, per klaim).
- **Fully grounded:** porsi jawaban yang semua klaimnya didukung konteks.
- **Sumber yang ditampilkan:** porsi pertanyaan yang bisa dijawab, di mana salah satu dari 3 sumber yang ditampilkan ke pengguna adalah halaman kunci jawaban. Ini yang paling dekat dengan pengalaman pengguna: **di 41% pertanyaan, sumber yang ditampilkan tidak memuat jawabannya.**
- **Penolakan yang salah:** akd-01 (jawabannya ada di dokumen 3 halaman yang rank-nya 26).

**Kebenaran** (judge Gemini): skor 0.70 (16 benar, 3 sebagian, 6 salah). Tidak bisa dibandingkan langsung dengan skor 0.625 di baseline pertama karena judge-nya berbeda (Qwen → Gemini) dan generasi tidak deterministik.

## Temuan

1. **Klaim yang tidak didukung hampir semuanya angka dari prodi lain.** kur-02 menyebut komposisi "118 wajib + 27 pilihan" untuk Sistem Informasi, padahal itu milik PTI; kur-04 menyebut skripsi TIF 6 SKS (angka Teknik Komputer); kur-07 menambahkan aturan konversi PKL dari prodi lain. Ini konflik jenis D di `docs/PRODUCT.md`, dan aturan runtime #1 ("jangan mencampur angka dari cakupan berbeda") harus masuk ke prompt.
2. **Jawaban benar belum tentu grounded.** kur-02 dinilai benar (145 SKS) tetapi faithfulness-nya 0.33 karena klaim tambahan yang dikarang. Mengukur kebenaran saja menyembunyikan masalah ini.
3. **Sumber yang ditampilkan adalah titik lemah terbesar** (0.591). Ini mengonfirmasi bahwa UI harus menampilkan halaman yang dikutip jawaban, bukan 3 chunk teratas hasil retrieval.

## Target langkah 2 (tulis ulang generasi)

| Metrik | Baseline | Target |
|---|---|---|
| Sumber yang ditampilkan memuat halaman kunci | 0.591 | ≥ 0.90 (target akurasi sitasi di PRODUCT.md) |
| Fully grounded | 0.714 | naik, tanpa klaim lintas prodi |
| Penolakan out-of-scope | 1.00 | tetap 1.00 |
| Penolakan yang salah | 0.045 | tidak naik |

---

# Langkah 2: generasi dengan sitasi inline (`citations-v1`)

Run: `eval/results/20261009-2355_citations-v1.json`. Prompt baru aktif, LLM menulis sitasi `[n]`, UI menampilkan halaman yang dikutip, `top_k` 30 → 10.

Catatan penilaian:
- Sitasi run ini dinilai ulang secara offline setelah parser diperbaiki untuk format bawaan gpt-oss `【n】` (jawaban yang sama; faithfulness dan kebenaran tidak berubah).
- Metrik sumber diperbaiki dan **kedua run dinilai ulang**: sumber dianggap tepat jika halamannya ada di kunci jawaban **atau** halaman PDF aslinya memuat teks bukti. Kunci jawaban tidak mungkin mencatat semua halaman yang menyebut suatu fakta.

| Metrik | Baseline | citations-v1 |
|---|---|---|
| Faithfulness | 0.874 | **0.921** |
| Fully grounded | 0.714 | **0.895** |
| Jawaban dengan sitasi | – | **1.00** |
| Jawaban dengan nomor sitasi tidak valid | – | **0.00** |
| Sumber yang ditampilkan memuat bukti jawaban | 0.682 | 0.636 |
| Penolakan out-of-scope | 1.00 | 1.00 |
| Penolakan yang salah | 0.045 | 0.136 (akd-01, akd-03, kur-04) |
| Kebenaran (judge) | 0.70 | 0.66 |
| Latensi median | 6.8 s | **4.4 s** |

Angka "sumber" baseline sedikit terbantu karena UI lama selalu menampilkan 3 chunk teratas apa pun isi jawabannya (mis. mhs-04 dihitung tepat padahal jawabannya salah).

## Temuan

1. **Lapisan generasi bekerja sesuai desain.** Klaim yang dikarang hampir hilang (fully grounded 0.71 → 0.90), setiap jawaban bersitasi valid, dan ketika bukti tidak ada di konteks model menolak alih-alih mengarang (kur-04 dulu menjawab "6 SKS" dari prodi lain, sekarang menolak).
2. **Kegagalan yang tersisa hampir semuanya di retrieval dan data**, bukan di generasi:
   - Halaman jawaban tidak ada di 10 sumber: akd-01 (rank 26), kur-04, kur-05, kur-07. Untuk kur-07 (Teknik Komputer) yang terambil hanya halaman PTI, sehingga jawabannya memakai aturan prodi lain.
   - **Chunk memotong tabel:** akd-03 ditolak karena chunk berhenti tepat di baris `IP < 1,50 | ...` dan nilai "< 12 SKS" ada di chunk berikutnya.
   - **Halaman karangan LlamaParse ikut dikutip:** kur-01 dan kur-02 mengutip sampul kurikulum (hal. 1) yang isinya dikarang parser.
   - LlamaParse menyimpan `<` sebagai `&#x3C;`; sudah di-decode sebelum masuk prompt.
3. **Konsekuensi:** penolakan yang salah naik (0.045 → 0.136). Ini sesuai prinsip produk #1 dan #3 (lebih baik menolak daripada mengarang), tetapi target berikutnya adalah menaikkan recall retrieval agar penolakan itu tidak perlu terjadi.

## Prioritas berikutnya (Fase 3)

Parser non-generatif (menghapus halaman karangan), chunk yang tidak memotong tabel/baris dan membawa konteks dokumen/prodi, lalu hybrid search untuk kata kunci eksak. Ukur dengan retrieval hit@10 (sekarang 0.727) dan penolakan yang salah.

---

# Fase 3: korpus dan chunking baru (`ordal-filkom-v3`)

Run: `eval/results/20261010-1159_v3-topk6.json` (10 Oktober 2026), retrieval pembanding `*_retrieval-ordal-filkom-v2.json` dan `*_retrieval-ordal-filkom-v3.json`.

Perubahan:
- Parser LlamaParse (LLM) → **pymupdf4llm** (non-generatif). Halaman tanpa lapisan teks (31 halaman, hampir semuanya sampul/kosong) dilewati, karena "OCR" LlamaParse di halaman itu kebanyakan karangan (contoh: "It seems that the content you provided is not sufficient...").
- Chunk **per halaman**, ±1.500 karakter, tidak memotong blok; tabel dipecah antar-baris dengan header diulang; judul bagian dibawa sebagai konteks; halaman daftar isi dibuang.
- Judul dokumen, cakupan (prodi/jenjang), dan bagian dari `static/dataset/catalog.json` ikut di-embed; judul katalog dan bagian juga tampil di prompt.
- Korpus: SKM 2020 → **SKM 2026**; **Edaran Dekan 2022** ditambahkan.
- 15.398 chunk → **2.598 chunk** (~0,73 juta token embedding); `top_k` 10 → **6**.

## Retrieval (22 pertanyaan bersumber)

| | hit@1 | hit@3 | hit@5 | hit@10 | hit@30 | MRR |
|---|---|---|---|---|---|---|
| v2 | 0.409 | 0.500 | 0.591 | 0.636 | 0.773 | 0.483 |
| **v3** | 0.409 | **0.864** | **0.909** | **0.909** | **0.909** | **0.608** |

(v2 dihitung dengan eval set terbaru; mhs-03/04 pasti meleset di v2 karena masih berisi SKM 2020.)

Yang dulu gagal dan sekarang ketemu: akd-01 (rank 26 → 2), kur-01 (15 → 3), kur-02 (14 → 2), kur-04 (– → 3), kur-05 (– → 3).

## Jawaban

| Metrik | v2 (Fase 2) | **v3** |
|---|---|---|
| Faithfulness | 0.921 | **0.942** |
| Fully grounded | 0.895 | **0.900** |
| Sumber yang ditampilkan memuat bukti jawaban | 0.636 | **0.818** |
| Jawaban dengan sitasi / sitasi tidak valid | 1.00 / 0.00 | 1.00 / 0.00 |
| Penolakan out-of-scope | 1.00 | 1.00 |
| Penolakan yang salah | 0.136 | **0.045** (kur-04) |
| Kebenaran (judge) | 0.66 | **0.82** (19 benar, 3 sebagian, 3 salah) |
| Latensi median | 4.4 s | **3.9 s** |

## Yang masih gagal

1. **akd-02/akd-03, konflik jenis C (universitas vs fakultas).** Pedoman UB hal. 66 memberi rentang (IP 2,50–2,99 → 19–21 SKS; IP < 1,50 → ≤ 12 SKS), Pedoman FILKOM hal. 15 memberi batas fakultas (21 SKS; < 12 SKS). Untuk akd-03 halaman FILKOM ikut terambil tetapi model tetap memakai aturan UB, jadi aturan "pakai yang paling spesifik" belum selalu dipatuhi.
2. **kur-04: tabel kompleks ter-parse kacau.** Halaman TIF hal. 22 terambil (rank 3), tetapi tabel semester 7–8 bergabung dan barisnya berantakan, sehingga model menolak.
3. **kur-07: prodi tercampur.** Halaman Teknik Komputer tidak terambil, dan model memakai angka PKL dari kurikulum **PTI** untuk pertanyaan Teknik Komputer (faithfulness 0). Ini konflik jenis D yang paling berbahaya.

## Kandidat langkah berikutnya

- **Filter metadata prodi** saat pertanyaan menyebut prodi/jenjang tertentu (kur-07): retrieval dibatasi ke dokumen prodi itu + dokumen fakultas/universitas.
- **Hybrid search (BM25 + vektor)** untuk istilah eksak dan tabel yang miskin kata (akd-02, kur-07).
- Perbaikan parsing tabel kompleks (kur-04) bila muncul di pertanyaan nyata.
