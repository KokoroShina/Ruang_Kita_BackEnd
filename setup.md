# Prompt: Setup Awal Backend "Ruang Kita"

Gunakan prompt ini untuk memulai vibe engineering backend Ruang Kita dari nol.

---

## PROMPT

Saya sedang membangun backend untuk **Ruang Kita**, sebuah PWA literasi kesejahteraan (wellbeing) untuk anak muda usia 15–23 tahun. Aplikasi ini punya tiga pilar utama: **Kenali** (jurnal & mood tracker), **Pahami** (chatbot refleksi berbasis AI), dan **Temukan** (rekomendasi konten personal).

Tolong bantu saya setup project ini dari awal dengan ketentuan berikut.

### Stack & Arsitektur

- **Framework:** FastAPI (async, Python 3.12+)
- **Database:** PostgreSQL, akses via SQLAlchemy (async) + Alembic untuk migration
- **Auth:** Email + password manual (bukan OAuth), JWT untuk session token, hashing password pakai bcrypt langsung (bukan passlib — ada known issue passlib/bcrypt v5 incompatibility)
- **AI Provider:** API gratis — Gemini API dan Groq API. Buat AI Gateway layer yang abstrak dari kedua provider ini, dengan mekanisme fallback (kalau satu provider kena rate limit, otomatis pindah ke yang lain)
- **Environment:** gunakan virtual environment (`venv`), package manager `pip`

### Instalasi & Package Awal

Tolong install dan setup package berikut, sesuaikan versi ke yang paling stabil/compatible saat ini:

- `fastapi` + `uvicorn` (server)
- `sqlalchemy` (async mode) + `asyncpg` (driver PostgreSQL)
- `alembic` (migration)
- `pydantic` + `pydantic-settings` (validasi & config dari env)
- `python-jose` atau `pyjwt` (JWT handling — pilih salah satu yang lebih maintained)
- `bcrypt` (hashing password langsung, JANGAN pakai passlib)
- `httpx` (async HTTP client, untuk panggil Gemini/Groq API)
- `python-dotenv` (load `.env`)
- `python-multipart` (kalau nanti butuh form/file upload)

### Struktur Folder yang Diinginkan

Buat struktur folder yang modular dan rapi, kurang lebih begini (silakan sesuaikan/optimalkan kalau ada pola yang lebih baik):

```
ruang_kita_backend/
  app/
    core/           # config, security, dependencies
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    api/            # route handlers, dikelompokkan per fitur
    services/
      ai/           # AI gateway (gemini_client, groq_client, router)
    prompts/         # template prompt AI per fitur, terpisah dari kode
    db/             # session, base
  alembic/
  .env.example
  requirements.txt
  main.py
```

### Skema Database Awal (Tahap 1 — Fondasi)

Buatkan model untuk:
- `users` — data akun (email, hashed password, nama, created_at, dll)
- `journal_entries` — entri jurnal user (teks bebas, timestamp, nanti ada kolom insight dari AI)
- `mood_logs` — pencatatan mood terpisah dari jurnal teks (skala/kategori mood, timestamp)
- `chat_sessions` — sesi percakapan chatbot refleksi
- `chat_messages` — pesan-pesan dalam satu sesi
- `content_library` — konten psikoedukasi yang dikurasi manual (untuk pilar Temukan nanti)  

Tolong desain relasi antar tabel yang masuk akal (misal `journal_entries.user_id` → FK ke `users`, dll).

### Fitur yang Perlu Diperhatikan (bukan untuk dibangun semua sekaligus, tapi jadi konteks arsitektur)

- Ada mini self-check onboarding setelah registrasi
- Aplikasi berurusan dengan data sensitif terkait kondisi psikologis, jadi butuh disclaimer layer dan **crisis detection** (deteksi indikasi risiko tinggi seperti self-harm di jurnal/chat, yang nanti akan mengarahkan ke jalur berbeda — bukan diproses sebagai AI biasa)
- Privasi dan consent harus eksplisit — siapkan struktur yang memudahkan penambahan fitur export data pribadi di masa depan

### Ruang Kebebasan untuk AI (PENTING)

Saya memberi kebebasan penuh untuk hal-hal berikut, tanpa perlu tanya persetujuan saya dulu di setiap langkah kecil:

1. **Boleh install package tambahan** di luar daftar di atas, jika memang dibutuhkan untuk best practice atau menyelesaikan masalah teknis (misalnya linter, testing tool, atau library pendukung lain) — cukup jelaskan alasannya secara singkat setelah instalasi.
2. **Boleh mengusulkan insight, fitur, atau perbaikan arsitektur** yang menurut kamu relevan dan belum saya sebutkan — baik itu soal keamanan, struktur data, developer experience, atau bahkan ide fitur baru yang mendukung tiga pilar (Kenali/Pahami/Temukan). Sampaikan sebagai catatan/insight, saya yang akan putuskan mau dipakai atau tidak.
3. **Boleh menyesuaikan struktur folder atau penamaan** dari yang saya contohkan di atas, jika ada pola yang lebih baik secara konvensi FastAPI modern — jelaskan alasannya.
4. **Boleh membuat keputusan teknis kecil** (versi package, cara error handling, dll) tanpa menunggu konfirmasi saya, selama itu tidak mengubah keputusan besar (seperti provider AI, jenis auth, atau struktur database inti) yang sudah saya tetapkan di atas.

### Yang TIDAK boleh diubah tanpa diskusi dulu

- Provider AI (tetap Gemini/Groq, bukan diganti provider berbayar)
- Metode auth (tetap email/password manual, bukan diganti OAuth)
- Skema tabel inti yang sudah disebutkan di atas (boleh ditambah kolom/tabel baru, tapi jangan hapus/ubah total tanpa bilang)

### Langkah yang Saya Minta Sekarang

1. Setup virtual environment dan install semua package di atas
2. Buat struktur folder sesuai rancangan
3. Buat model database untuk Tahap 1 (fondasi) di atas
4. Setup Alembic dan jalankan migration awal
5. Buat `.env.example` dengan variabel yang dibutuhkan (termasuk `GEMINI_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, `JWT_SECRET`, dll)
6. Setelah semua siap, buatkan ringkasan singkat: apa saja yang sudah dibuat, keputusan teknis apa yang kamu ambil, dan insight/saran apa (jika ada) untuk langkah selanjutnya

Tolong kerjakan bertahap dan beri saya ringkasan progress di setiap langkah besar, jangan langsung lompat ke fitur AI Gateway atau chatbot dulu — fokus ke fondasi (auth + skema database) di sesi ini.