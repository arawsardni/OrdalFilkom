# Ordal Filkom: Product Brief

> Dokumen acuan utama pengembangan. Setiap fitur, eksperimen, atau perubahan teknis harus bisa dijelaskan kontribusinya terhadap tujuan dan metrik di dokumen ini. Kalau tidak bisa, tunda atau ubah dulu dokumen ini secara sadar.

Terakhir diperbarui: 9 Oktober 2026

---

## 1. Masalah dan tujuan

Informasi akademik FILKOM UB tersebar di puluhan dokumen PDF yang panjang (pedoman akademik, kurikulum, panduan skripsi/PKL, dan lain-lain), di web fakultas dan FILKOM Apps. Untuk menjawab satu pertanyaan sederhana seperti "berapa SKS minimal untuk lulus?", mahasiswa harus tahu dokumen mana yang relevan, mengunduhnya, lalu mencari halamannya sendiri.

**Tujuan:** memotong proses mencari informasi itu. Mahasiswa bertanya dalam bahasa sehari-hari, lalu mendapat jawaban ringkas **beserta sumber halaman yang bisa langsung dibuka dan dicek**.

Ordal Filkom adalah **jalan pintas menuju dokumen resmi**, bukan pengganti dokumen resmi atau dosen PA. Pengguna diharapkan tidak menelan jawaban mentah-mentah, melainkan memverifikasinya lewat sumber yang ditampilkan.

## 2. Pengguna

Seluruh mahasiswa Fakultas Ilmu Komputer UB, dari jenjang S1 sampai Doktor.

| Jenjang | Prodi | Cakupan dokumen saat ini |
|---|---|---|
| S1 | Teknik Informatika, Teknik Komputer, Sistem Informasi, Teknologi Informasi, Pendidikan TI | Baik: kurikulum per prodi, pedoman akademik, skripsi, PKL, kemahasiswaan |
| S2 | Magister Ilmu Komputer, Magister Sistem Informasi | Sebagian: kurikulum ada; aturan tesis hanya dari pedoman UB |
| S3 | Doktor Ilmu Komputer | Minim: tidak ada pedoman khusus di web resmi; hanya aturan umum di pedoman UB |

## 3. Prinsip produk

Dipakai untuk memutuskan trade-off. Urutannya menunjukkan prioritas.

1. **Grounded di atas fasih.** Setiap klaim dalam jawaban harus didukung dokumen. Jawaban pendek yang benar dan bersumber lebih baik daripada jawaban panjang yang terdengar meyakinkan.
2. **Sumber harus bisa dicek.** Sumber yang ditampilkan ke pengguna harus benar-benar memuat informasi yang dipakai di jawaban. Tujuannya verifikasi, bukan sekadar daftar dokumen.
3. **Tolak kalau tidak ada.** Kalau informasinya tidak ada di dokumen, katakan tidak ada. Jangan mengisi celah dengan pengetahuan umum LLM.
4. **Zero cost.** Pengembangan, deploy, dan maintenance harus gratis (lihat Bagian 7). Fitur yang butuh biaya tidak dikerjakan, atau dicari alternatif gratisnya.
5. **Ukur sebelum mengubah.** Perubahan pada pipeline harus dibandingkan dengan baseline lewat `scripts/eval.py`.

## 4. Cakupan

**Dalam cakupan:** pertanyaan apa pun yang jawabannya ada di dokumen akademik resmi FILKOM/UB yang masuk korpus, terkait proses akademik di FILKOM UB.

**Di luar cakupan:**
- Pertanyaan non-akademik, atau yang tidak terkait proses akademik FILKOM UB.
- Pertanyaan akademik yang jawabannya tidak ada di dokumen (misalnya besaran UKT, jadwal wisuda tertentu). Asisten harus menolak dengan sopan dan, kalau bisa, menyebut ke mana mahasiswa sebaiknya bertanya.
- Keputusan yang bukan wewenang dokumen, misalnya persetujuan KRS atau dispensasi. Asisten boleh menjelaskan aturannya, tapi keputusan tetap di dosen PA atau bagian akademik.

**Nanti (bukan prioritas sekarang):** keluaran generatif selain jawaban, misalnya menyusun rencana studi/jadwal per semester, memetakan mata kuliah dan prasyaratnya, atau checklist syarat skripsi berdasarkan kondisi mahasiswa. Fitur ini baru dikerjakan setelah jawaban dasar terbukti grounded.

## 5. Jenis pertanyaan dan perilaku yang diharapkan

Dari pengamatan log pemakaian Desember 2025 (log tidak tersimpan, ini dari ingatan pemilik project):

| Jenis | Contoh | Perilaku yang diharapkan |
|---|---|---|
| **Fakta satu sumber** (paling sering, juga dipakai untuk "ngetes") | SKS minimal lulus, syarat skripsi, silabus/gambaran umum mata kuliah | Jawaban singkat dan langsung, plus sumber halaman yang tepat. |
| **Personal/advisory** | "SKS saya sekarang X, minat saya Y, sebaiknya ambil apa?"; pertanyaan seputar skripsi | Terapkan aturan dari dokumen ke kondisi pengguna. Pisahkan dengan jelas **aturan resmi (bersumber)** dari **saran (penalaran asisten)**. Arahkan keputusan akhir ke dosen PA. Jangan mengarang aturan. |
| **Di luar cakupan** | UKT, biaya wisuda, hal non-akademik | Nyatakan informasinya tidak tersedia di dokumen. Jangan mengarang angka. |

Catatan: silabus mata kuliah ada di dokumen kurikulum masing-masing prodi, tapi cakupannya tidak merata (lihat Bagian 8).

## 6. Definisi berhasil dan metrik

### Metrik utama: groundedness
Pengguna percaya pada produk kalau apa yang dikatakan asisten bisa dicek di sumber yang ditunjukkan. Ada tiga komponen:

| Komponen | Definisi | Cara ukur |
|---|---|---|
| **Faithfulness** | Setiap klaim di jawaban didukung oleh konteks yang di-retrieve | LLM judge (Gemini Flash-Lite, supaya tidak memakai kuota Groq app live): jawaban vs konteks yang diberikan ke LLM |
| **Akurasi sitasi** | Sumber yang dikutip dan ditampilkan ke pengguna memang memuat bukti untuk jawaban | LLM menulis sitasi inline (dokumen + halaman); parser deterministik mengecek halaman yang dikutip ada di konteks yang diberikan. Tanpa judge, jadi murah dan tanpa noise. |
| **Penolakan yang benar** | Pertanyaan di luar cakupan ditolak tanpa mengarang, dan pertanyaan yang bisa dijawab tidak ditolak | Deterministik: penanda penolakan di jawaban, untuk item `out_of_scope` maupun item biasa (false refusal) |

**Target awal:** akurasi sitasi ≥ 90% dan penolakan out-of-scope 100%. Faithfulness ditargetkan setelah ada baseline-nya. Target ini ditinjau ulang setelah eval set diperluas dengan pertanyaan nyata.

### Metrik pendukung (nice to have)
- Kebenaran jawaban terhadap referensi (sudah diukur di `scripts/eval.py --answers`)
- Retrieval hit@k dan MRR (sudah diukur)
- Latensi, dan token per pertanyaan (penting karena kuota, lihat Bagian 7)

### Celah saat ini
- **Eval belum mengukur groundedness.** Yang diukur baru kebenaran terhadap referensi. Menambahkan faithfulness dan akurasi sitasi ke `scripts/eval.py` adalah prioritas.
- **Sumber yang ditampilkan belum tentu sumber yang dipakai.** UI menampilkan 3 chunk teratas hasil retrieval, sementara LLM membaca 30 chunk. Jawaban bisa berasal dari chunk yang tidak ditampilkan, sehingga fitur verifikasi sumber, yang merupakan inti produk, bisa menyesatkan. Contoh di baseline: kur-04 menampilkan halaman yang tidak memuat jawabannya.

## 7. Batasan: zero cost

Semua komponen harus berjalan di free tier. Free tier bisa berubah tanpa pemberitahuan: di 2026 model embedding `text-embedding-004` dan tiga model Llama di Groq dihapus, dan app mati sampai diperbaiki.

| Komponen | Layanan (free tier) | Batas yang relevan | Implikasi |
|---|---|---|---|
| LLM | Groq | ~200k token/hari per model, 8k token/menit | Dengan ~5–7k token/pertanyaan, model utama hanya muat **±30–40 pertanyaan/hari**. Eval memakai kuota yang sama dengan app live. |
| Embedding + vector DB | Pinecone Starter (inference + index) | Kuota embedding bulanan, maksimal 5 index | Ingest ulang penuh (~1 juta token) harus jarang dilakukan |
| PDF parsing | LlamaParse | Kredit gratis per bulan | Hasil parse di-cache (`data/parsed/`); jangan parse ulang tanpa alasan |
| Hosting | Streamlit Community Cloud | RAM maks 2,7 GB; tidur setelah 12 jam tanpa trafik; log tidak permanen; app berjalan di iframe ber-`sandbox` di path `/~/+/` | Log pertanyaan harus disimpan di tempat lain; URL file statis harus relatif terhadap path app |
| Penyimpanan log/feedback | Belum ada (kandidat: Google Sheets, Supabase free) | | Harus gratis dan tidak butuh perawatan |

**Konsekuensi desain:**
- **Token per pertanyaan adalah metrik biaya.** Mengurangi konteks (misalnya `top_k` lebih kecil) menambah kapasitas harian.
- **Provider harus mudah diganti lewat konfigurasi** (`src/config/settings.py`), dengan model cadangan.
- **Perlu health check berkala** untuk mendeteksi model atau layanan yang dihapus sebelum pengguna menemukannya.

### Tech stack (ditinjau 9 Oktober 2026)

| Lapisan | Pilihan | Catatan |
|---|---|---|
| Hosting | Streamlit Community Cloud | Tetap. Hugging Face Spaces (Gradio/Docker) sekarang butuh paket berbayar; Render free tidur setelah 15 menit idle. Bisa mengajukan resource lebih lewat program "Good for the world" Streamlit. |
| Vector DB + embedding | Pinecone Starter (`llama-text-embed-v2`) | Tetap. Gratis: storage 2 GB, 1 juta read unit/bulan, embedding 5 juta token/bulan, index full-text tersedia untuk hybrid search. Reranker gratisnya hanya 500 request/bulan, jadi tidak dipakai. |
| LLM | Groq (`gpt-oss-120b`, cadangan `qwen3.8-27b`, `gpt-oss-20b`) | Rencana: tambah Gemini Flash-Lite (free tier) sebagai cadangan lintas provider. Free tier Gemini memakai data untuk melatih model; perlu disebut di pemberitahuan app. |
| Generasi | `ContextChatEngine` LlamaIndex | Rencana: ditulis sendiri (retrieve → prompt → LLM) supaya prompt dan sitasi bisa dikendalikan penuh. LlamaIndex tetap untuk ingest dan retrieval. |
| PDF parsing | LlamaParse (LLM mode) | Rencana: parser lokal non-generatif (Docling atau PyMuPDF4LLM), karena LlamaParse terbukti mengarang isi halaman. |
| PDF viewer | PDF.js v6.3.289 (legacy build) di `static/pdfjs`, di-embed lewat iframe `srcdoc` | Viewer bawaan Chrome tidak bisa di-embed karena app berjalan di iframe ber-`sandbox`. PDF.js mendukung `#page=` dan `#search=` untuk menyorot teks sumber. |
| Log + feedback | Belum ada | Kandidat: Google Sheets (gspread) atau Cloudflare D1 (HTTP API). |
| CI, health check, pemantau dokumen | Belum ada | GitHub Actions (gratis untuk repo publik). |

Project serupa yang dijadikan acuan: [UAJY Academic RAG](https://github.com/BenyRonald77/uajy-academic-rag-chatbot) (cara mengukur sitasi dan groundedness), [Gunadarma RAG](https://github.com/YAMA2063/chatbot-rag-universitas-gunadarma) (hybrid search, metadata prodi).

**Pemicu untuk mempertimbangkan pindah hosting** (misalnya ke Cloudflare Workers + Vectorize + D1): halaman "app sedang tidur" atau UX di HP terbukti membuat pengguna pergi (terlihat dari log), atau free tier Streamlit Cloud berubah. Pindah ke Cloudflare berarti menulis ulang backend ke TypeScript.

## 8. Korpus dokumen

### Sumber
Korpus **hanya** diambil dari kanal resmi fakultas:
1. Web resmi: https://filkom.ub.ac.id/profil/dokumen-resmi/ (publik)
2. FILKOM Apps (perlu login mahasiswa): panduan, penilaian, dan template skripsi. Isinya tidak memuat data kredensial atau pribadi, sehingga **boleh ditampilkan publik** di document browser.

Dokumen internal prodi yang belum dipublikasikan di kanal resmi (misalnya silabus SI/PTI yang mungkin beredar di prodi) **tidak dimasukkan**, walaupun isinya relevan.

### Kriteria
**Masukkan:** dokumen resmi yang masih berlaku dan memuat aturan atau proses akademik yang sering dicari mahasiswa.

**Jangan masukkan:**
- Sertifikat/SK akreditasi.
- Formulir dan template kosong (.docx).
- Dokumen yang sudah digantikan versi baru.

Formulir bisa dipertimbangkan nanti sebagai katalog tautan ("form izin tidak masuk kuliah ada di mana?"), bukan sebagai teks yang di-embed.

### Dokumen yang bertentangan

Di korpus ini, "bertentangan" jarang berarti dua dokumen berlaku yang benar-benar saling membantah. Yang sering terjadi ada lima jenis:

| Jenis | Contoh nyata | Penanganan |
|---|---|---|
| **A. Versi lama vs baru** | Panduan SKM 2020 (di korpus) vs SKM 2026 (di web) | **Kurasi:** hanya simpan versi berlaku; versi lama dikeluarkan dari korpus |
| **B. Dokumen yang mengubah sebagian dokumen lain** | Edaran Dekan 2022 mengubah mekanisme pemberkasan seminar hasil di Panduan Skripsi/PKL 2018 | **Kurasi + metadata:** keduanya disimpan, edaran diberi tanda `mengubah: Panduan Skripsi 2018`. Kalau keduanya ter-retrieve, aturan dari edaran yang menang. |
| **C. Level berbeda: universitas vs fakultas vs prodi** | Cumlaude: Pedoman UB 2023 dan Pedoman FILKOM 2020 sama-sama IPK > 3,50; FILKOM menambah aturan 2 tahun untuk alih program | Biasanya saling melengkapi, bukan bertentangan. Jawab dengan aturan yang paling spesifik dan sebut tambahan dari level lain. |
| **D. Cakupan berbeda: jenjang/prodi/angkatan** | Cumlaude S1 IPK > 3,50 (UB p160) vs profesi IPK > 3,75 (UB p170); skripsi 4 SKS di TIF vs 6 SKS di TEKKOM; aturan peralihan kurikulum untuk angkatan lama | Ini **bukan konflik**, tapi paling sering menyebabkan jawaban salah, karena angka dari konteks yang berbeda tercampur. Lihat aturan runtime di bawah. |
| **E. Konflik palsu karena data rusak** | Sampul kurikulum SI hasil LlamaParse berisi "144 SKS" (aslinya 145) | **Perbaiki data**, bukan ditangani di prompt |

**Prinsipnya: selesaikan konflik di data, bukan di LLM.** Jenis A, B, dan E diselesaikan saat kurasi dan ingest, sehingga tidak pernah sampai ke pengguna. Yang tersisa untuk ditangani saat runtime hanya C dan D.

**Metadata per dokumen** (disimpan di katalog dokumen dan di metadata chunk): judul, penerbit (`universitas`/`fakultas`/`prodi`), prodi, jenjang, tahun, status (`berlaku`/`digantikan`), dan `mengubah` (dokumen yang diubah sebagian).

**Aturan runtime untuk asisten:**
1. **Jangan mencampur angka dari cakupan berbeda.** Setiap angka di jawaban harus berasal dari sumber yang cakupannya sesuai dengan pertanyaan.
2. **Kalau jawabannya berbeda per prodi/jenjang dan pengguna tidak menyebutnya:** berikan jawaban per prodi secara ringkas, atau minta pengguna menyebut prodinya. Jangan memilih satu prodi diam-diam.
3. **Kalau dua sumber berlaku berbeda:** jawaban utama dari sumber yang paling spesifik dan paling baru, lalu sebutkan perbedaannya beserta nama dokumen dan tahunnya. Pengguna yang memutuskan, sesuai prinsip "sumber harus bisa dicek".
4. **Nanti:** kalau prodi/jenjang pengguna diketahui (misalnya dipilih di UI), retrieval difilter dengan metadata supaya dokumen prodi lain tidak ikut terambil.

### Inventaris (dicek 8 Oktober 2026)

| Dokumen | Di korpus | Status |
|---|---|---|
| Pedoman Akademik UB 2023-2024 | ✅ | OK |
| Pedoman Akademik FILKOM 2020 | ✅ | OK. Sampulnya bertuliskan masa berlaku 2020–2024, tapi belum ada versi lebih baru (dikonfirmasi 9 Oktober 2026), jadi tetap dipakai. |
| Panduan PKL 2018 | ✅ | OK |
| Kurikulum 2024: TIF, TEKKOM, SI, TI, PTI, MILKOM; Kurikulum S2 SI 2025 | ✅ | OK |
| Standar Pembelajaran Daring | ✅ | OK |
| Tata Tertib UTS/UAS 2016 | ✅ | OK |
| Panduan RPL 2023 | ✅ | OK |
| PKL Jalur Kompetisi 2023 | ✅ | OK |
| **Panduan SKM** | ⚠️ versi 2020 (nama file 2024) | **Usang.** Web sudah punya versi 2026 (rev 22-05-2026). Item eval mhs-03/mhs-04 perlu dicek ulang setelah diganti. |
| **Edaran Dekan: Perubahan Mekanisme Pemberkasan Seminar Hasil Skripsi & PKL (2022)** | ❌ | **Belum masuk.** Mengubah prosedur di Panduan Skripsi/PKL 2018. |
| Peta Proses Bisnis FILKOM 2025 | ❌ | Kandidat (diunggah Juni 2026); perlu dicek isinya |
| Panduan skripsi (Penulisan 2015, Proposal 2015, Penilaian 2017, Panduan Skripsi 2018) | ✅ | Dari FILKOM Apps; masih versi terbaru di sana (dikonfirmasi) |
| Pedoman Penilaian IP PTIIK 2015, Pedoman UB 2016/2017 | ❌ | Sengaja tidak dimasukkan (usang) |
| Pedoman khusus S3 | ❌ | Tidak tersedia di web resmi |

**Cakupan silabus** (halaman yang memuat silabus, deskripsi mata kuliah, atau CPMK, per dokumen kurikulum): TIF 62, TEKKOM 51, TI 51, S2 SI 38, MILKOM 27, **PTI 5, SI 3**. Silabus SI dan PTI tidak tersedia di kanal resmi; dokumen PTI di web memang berjudul "Ringkasan Kurikulum". Ini **keterbatasan yang diketahui**: pertanyaan silabus SI/PTI diperlakukan sebagai di luar cakupan dan ditolak dengan sopan.

### Kualitas data
LlamaParse terbukti **mengarang isi** pada sebagian halaman, terutama sampul dan daftar isi; lihat `eval/BASELINE.md`. Halaman karangan ini mencemari index dan langsung melanggar prinsip #1. Kebersihan korpus harus diperlakukan sama pentingnya dengan kualitas retrieval.

## 9. Roadmap

Disusun berdasarkan prinsip di atas: groundedness dulu, baru fitur.

**Sekarang (Fase 2): fondasi groundedness**
1. Tambahkan metrik groundedness ke eval (akurasi sitasi, penolakan, faithfulness), lalu ukur baseline pada app yang sekarang.
2. Tulis ulang langkah generasi: prompt dipasang dengan benar (termasuk aturan konflik dokumen), LLM menulis sitasi inline, UI menampilkan halaman yang dikutip dan membukanya di PDF.js dengan teks sumber tersorot.
3. Kurangi token per pertanyaan (`top_k` lebih kecil) untuk kapasitas dan biaya, lalu ukur ulang dan bandingkan dengan baseline.

**Berikutnya: korpus, feedback, operasional**
4. Bersihkan korpus: parser non-generatif menggantikan LlamaParse; refresh dokumen usang (SKM 2026, Edaran Dekan 2022); buat katalog dokumen dengan metadata cakupan (Bagian 8) dan bawa metadata itu ke setiap chunk; ingest ulang secara inkremental (hanya file yang berubah, berdasarkan hash).
5. Simpan log pertanyaan + feedback 👍/👎 (gratis, tanpa identitas pengguna, dengan pemberitahuan di UI). Pertanyaan nyata masuk ke eval set.
6. Health check berkala untuk model/layanan free tier.
7. **Pemantau dokumen resmi:** skrip terjadwal (GitHub Actions, misalnya seminggu sekali) yang memeriksa https://filkom.ub.ac.id/profil/dokumen-resmi/, mendeteksi file baru atau berubah (daftar link + header `ETag`/`Last-Modified`, tanpa mengunduh ulang file yang sama), lalu mengunduh file tersebut ke sebuah PR untuk direview. **Tidak langsung di-ingest**: tetap dikurasi manual sesuai kriteria di Bagian 8 (formulir dan sertifikat diabaikan, versi lama ditandai digantikan). FILKOM Apps tidak dipantau.
   - Sudah dicek 9 Oktober 2026: `robots.txt` situs kosong, halaman berupa HTML statis (45 link PDF bisa diambil tanpa JavaScript), dan bot dengan User-Agent jujur (`OrdalFilkomDocChecker/0.1 (+repo URL)`) diterima. User-Agent bawaan library Python ditolak (403), jadi skrip harus mengirim User-Agent sendiri.
   - Perlu dicek saat implementasi: apakah IP runner GitHub Actions ikut diblokir Cloudflare situs tersebut.

**Nanti**
8. Perbaikan retrieval lanjutan (hybrid search) kalau eval menunjukkan perlu.
9. Fitur generatif: rencana studi, peta mata kuliah, checklist syarat.
10. Cakupan S2/S3 yang lebih baik kalau dokumennya tersedia.

## 10. Pertanyaan terbuka

Belum ada pertanyaan terbuka. Yang sudah terjawab:

- [x] ~~Aturan dokumen bertentangan?~~ Disetujui (Bagian 8).
- [x] ~~Silabus SI dan PTI?~~ Tidak ada di kanal resmi; diterima sebagai keterbatasan.
- [x] ~~Dokumen FILKOM Apps boleh ditampilkan publik?~~ Boleh, isinya tidak memuat kredensial atau data pribadi.
- [x] ~~Sumber RPS?~~ Yang dimaksud silabus, dan silabus ada di dokumen kurikulum tiap prodi.
- [x] ~~Panduan skripsi masih versi terbaru?~~ Ya, FILKOM Apps masih memakai versi 2018.
- [x] ~~Target metrik?~~ Mengikuti usulan (Bagian 6).

## 11. Catatan keputusan

| Tanggal | Keputusan | Alasan |
|---|---|---|
| 2026-10-08 | Embedding pindah ke Pinecone inference (`llama-text-embed-v2`, 768 dim) | `text-embedding-004` dihapus; free tier Gemini 1.000 embed/hari tidak cukup untuk ~15k chunk; Pinecone gratis dan mengurangi jumlah provider |
| 2026-10-08 | LLM: `openai/gpt-oss-120b`, cadangan `qwen/qwen3.8-27b` dan `openai/gpt-oss-20b` | Model Llama di Groq dihapus |
| 2026-10-08 | Hasil LlamaParse di-cache di `data/parsed/` | Menghemat kredit parse saat eksperimen chunking |
| 2026-10-08 | Eval set + `scripts/eval.py` sebagai syarat sebelum mengubah pipeline | Mencegah perbaikan yang bergerak ke arah yang salah |
| 2026-10-08 | Dokumen FILKOM Apps boleh ditampilkan publik di app | Hanya berisi panduan dan template, tanpa kredensial atau data pribadi |
| 2026-10-08 | Korpus dibatasi ke kanal resmi fakultas (web resmi + FILKOM Apps) | Menjaga keresmian sumber; dokumen internal prodi tidak dimasukkan walaupun relevan |
| 2026-10-08 | Konflik dokumen diselesaikan di data (kurasi + metadata), sisanya lewat aturan runtime | Jenis A/B/E tidak boleh sampai ke pengguna; C/D ditangani prompt dan nantinya filter metadata |
| 2026-10-08 | Metrik utama: groundedness, dengan target akurasi sitasi ≥ 90% dan penolakan out-of-scope 100% | Pengguna diharapkan memverifikasi lewat sumber, jadi sumber yang benar lebih penting daripada jawaban yang fasih |
| 2026-10-09 | Tetap di Streamlit Community Cloud | Masalah utama produk (groundedness, data) tidak terkait hosting; alternatif gratis lain lebih buruk atau butuh rewrite |
| 2026-10-09 | Viewer PDF memakai PDF.js yang di-bundle; dataset dipindah ke `static/dataset` dan disajikan lewat static file serving | Viewer Chrome diblokir sandbox Streamlit Cloud; PDF.js jalan di sandbox dan di HP, dan mendukung lompat halaman + sorot teks untuk sitasi |
| 2026-10-09 | Sitasi diukur dengan parser deterministik (gaya UAJY); judge hanya untuk faithfulness | Lebih murah dan tanpa noise daripada semuanya dinilai LLM |
| 2026-10-09 | Pemantau dokumen resmi dijadwalkan setelah fase groundedness; hasilnya masuk PR, tidak langsung di-ingest | Mencegah unduh ulang manual tanpa melewati kurasi |
