# Prompt: AI Gateway (OpenRouter) — Ruang Kita Backend

Gunakan prompt ini setelah fondasi auth (Tahap 1) sudah berjalan. Prompt ini membangun Tahap 3: AI Gateway layer, sebagai persiapan sebelum fitur chatbot (Pahami) dan analisis jurnal (Kenali) dibangun.

---

## PROMPT

Backend Ruang Kita (FastAPI + MySQL) sudah punya fondasi auth yang berjalan (register, login, `/me`, JWT). Sekarang saya mau membangun **AI Gateway layer** — service perantara ke LLM yang nantinya dipakai oleh fitur chatbot refleksi (Pahami) dan analisis jurnal (Kenali). Ini masih tahap testing/development, belum production.

### Provider AI

- **Provider:** OpenRouter (`https://openrouter.ai/api/v1`) — satu API key untuk akses banyak model
- **Model:** prioritaskan model dengan tier gratis (biasanya bertanda `:free` di nama model OpenRouter). Karena ini tahap testing, boleh eksplorasi beberapa model gratis yang tersedia dan bandingkan kualitasnya untuk use case chatbot reflektif — sampaikan hasil perbandingan kalau ada insight menarik.
- **Auth ke OpenRouter:** Bearer token dari `OPENROUTER_API_KEY` di `.env`, JANGAN hardcode di kode

### Struktur yang Diinginkan

```
app/
  services/
    ai/
      openrouter_client.py   # wrapper httpx.AsyncClient ke OpenRouter API
      router.py               # logic pilih model + fallback antar model kalau kena rate limit/error
      prompts/
        chat_prompt.py         # template prompt untuk chatbot refleksi (Pahami)
        journal_prompt.py      # template prompt untuk analisis jurnal (Kenali)
```

Sesuaikan struktur ini kalau ada pola yang lebih baik.

### Kebutuhan Fungsional AI Gateway

**1. Chat service (untuk Pahami, dibangun setelah gateway ini siap)**
Fungsi generate response percakapan multi-turn — perlu menerima histori pesan sebagai context, bukan cuma single-turn.

**2. Journal analysis service (untuk Kenali, dibangun setelah gateway ini siap)**
Fungsi analisis satu entri jurnal → hasil insight ringkas. Ini one-shot, bukan percakapan.

Untuk sesi ini, fokus dulu ke **fondasi gateway-nya** (client + router + fallback), bukan langsung ke chat/journal service lengkap — itu menyusul di sesi berikutnya setelah gateway-nya teruji.

### Fallback & Error Handling

- Kalau model yang dipanggil kena rate limit (biasanya HTTP 429) atau error dari OpenRouter, `router.py` harus otomatis coba model gratis lain dari daftar fallback, bukan langsung gagal ke user
- Simpan daftar model fallback ini di konfigurasi (`.env` atau config file), jangan hardcode di tengah kode — supaya gampang diubah kalau OpenRouter mengubah ketersediaan model gratis
- Kalau semua model di daftar fallback gagal, kembalikan error yang jelas (bukan silent fail), supaya endpoint pemanggil bisa menampilkan pesan yang wajar ke user

### Guardrail yang WAJIB Ada dari Awal

Karena AI Gateway ini nantinya menangani konten terkait kondisi psikologis pengguna:

1. **Disclaimer layer** — setiap response dari chat/journal AI harus melewati lapisan ini sebelum dikembalikan ke endpoint pemanggil. Untuk sesi ini, cukup siapkan strukturnya (misal fungsi `apply_disclaimer()` yang bisa diisi logic lebih detail nanti), tidak perlu logic lengkap.
2. **Crisis detection hook** — siapkan titik intersepsi di gateway ini (bukan logic deteksinya secara penuh dulu) supaya nanti input/output yang mengandung indikasi risiko tinggi (self-harm, dll) bisa dialihkan ke jalur berbeda, bukan diproses sebagai AI response biasa. Untuk sesi ini cukup buat stub function-nya dan titik pemanggilannya di alur, logic detection detail menyusul.

### Logging Pemakaian (untuk Tahap Testing)

Karena masih tahap testing dan model gratis punya rate limit ketat, siapkan logging sederhana tiap kali gateway ini dipanggil: model apa yang dipakai, sukses/gagal, kapan. Ini membantu saya tahu pola pemakaian dan kapan perlu ganti model fallback. Simpan sebagai tabel `ai_usage_log` — silakan usulkan struktur kolom yang menurut kamu perlu (misal: `id`, `model_used`, `endpoint_type`, `success`, `created_at`, dan lainnya jika relevan).

### Ruang Kebebasan untuk AI (PENTING)

1. **Boleh install package tambahan** di luar `httpx` (yang sudah terpasang dari setup awal) jika memang dibutuhkan — jelaskan alasannya.
2. **Boleh mengusulkan insight** soal pemilihan model gratis OpenRouter mana yang paling cocok untuk chatbot reflektif (butuh nada empatik, bukan cuma jawaban teknis cepat), atau soal struktur prompt yang lebih baik. Sampaikan sebagai catatan, saya yang putuskan.
3. **Boleh menyesuaikan struktur folder/kode** dari contoh di atas jika ada pola yang lebih baik untuk FastAPI async service layer — jelaskan alasannya.
4. **Boleh membuat keputusan teknis kecil** (format response internal, cara logging, dll) tanpa menunggu konfirmasi saya.

### Yang TIDAK Boleh Diubah Tanpa Diskusi Dulu

- Provider tetap OpenRouter untuk sesi ini (bukan diganti Gemini/Groq langsung tanpa dibahas)
- Guardrail disclaimer layer & crisis detection hook harus tetap ada strukturnya, meski logic detailnya belum lengkap — jangan diskip dengan alasan "ini baru testing"
- Skema auth dan database inti yang sudah dibangun di Tahap 1 tidak boleh diubah dari sesi ini

### Langkah yang Saya Minta Sekarang

1. Buat `openrouter_client.py` — wrapper client ke OpenRouter API
2. Buat `router.py` — logic pemilihan model + fallback
3. Siapkan struktur folder `prompts/` (boleh kosong/placeholder dulu untuk chat & journal prompt, isi lengkapnya menyusul)
4. Buat stub `apply_disclaimer()` dan crisis detection hook di titik yang tepat dalam alur gateway
5. Buat model & migration untuk tabel `ai_usage_log`
6. Update `.env.example` dengan `OPENROUTER_API_KEY` dan daftar model fallback
7. Buat satu endpoint test sederhana (misal `POST /api/v1/ai/test`) yang memanggil gateway ini end-to-end, supaya saya bisa verifikasi semuanya nyambung sebelum lanjut ke chat/journal service sungguhan
8. Setelah selesai, ringkas: apa yang sudah dibuat, model gratis mana yang kamu pilih sebagai default + fallback dan kenapa, serta insight apapun yang menurutmu relevan untuk langkah selanjutnya

Kerjakan bertahap, beri ringkasan di tiap langkah besar.