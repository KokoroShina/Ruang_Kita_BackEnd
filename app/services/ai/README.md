# AI Gateway (OpenRouter)

Layer perantara ke LLM via OpenRouter — satu API key, banyak model.
Dipakai fitur chatbot refleksi (Pahami) dan analisis jurnal (Kenali).

## Struktur

```
services/ai/
  openrouter_client.py  # wrapper httpx.AsyncClient -> /chat/completions (error bertipe)
  router.py             # generate_text(): fallback antar model + guardrail hooks + logging
  guardrails.py         # detect_crisis() + apply_disclaimer() [stub v1]
  prompts/
    chat_prompt.py      # builder pesan multi-turn (pilar Pahami)
    journal_prompt.py   # builder prompt analisis jurnal one-shot (pilar Kenali)
```

## Aturan pemakaian

- Modul lain HANYA boleh memanggil `router.generate_text()` — tidak langsung ke client.
- Model default + daftar fallback dikonfigurasi di `.env` (`AI_MODEL_DEFAULT`,
  `AI_MODEL_FALLBACKS`) — jangan hardcode di kode.
- Setiap attempt tercatat di tabel `ai_usage_log` (sukses/gagal/latency/tokens).
- Semua output wajib lewat `apply_disclaimer()`; input/output wajib melewati
  `detect_crisis()` — flagged = jalur dukungan khusus, bukan AI response biasa.

## Error semantics

| Exception            | Arti                                  | Aksi endpoint                    |
| -------------------- | ------------------------------------- | -------------------------------- |
| `CrisisDetectedError`| Indikasi risiko tinggi pada in/output | Respons jalur khusus (bukan error)|
| `AIConfigurationError`| Key invalid / config salah           | 500 (fail-fast, tanpa fallback)  |
| `AIGatewayError`     | Semua model kandidat gagal            | 503, pesan wajar ke user         |
