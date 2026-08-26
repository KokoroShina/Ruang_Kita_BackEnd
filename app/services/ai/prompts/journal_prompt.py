"""Prompt analisis jurnal — pilar Kenali. One-shot, bukan percakapan. (Versi awal.)"""

ANALYSIS_INSTRUCTION = """Kamu membantu pengguna muda Indonesia merefleksikan jurnal hariannya.

Analisis teks jurnal berikut, lalu jawab dalam format ringkas berikut:
1. Refleksi: 2-3 kalimat yang memvalidasi perasaan penulis dan menangkap inti yang ia tulis.
2. Pertanyaan introspeksi: 2 pertanyaan terbuka untuk membantunya melihat lebih dalam.
3. Satu langkah kecil: satu sugesti aktivitas kecil dan realistis untuk hari ini.

Aturan:
- Bahasa Indonesia hangat, tanpa menggurui, tanpa diagnosis medis/psikologis.
- Berbasis HANYA pada isi jurnal; jangan mengaruh detail yang tidak ada.
- Jika isinya netral/positif, jangan dipaksakan terdengar bermasalah."""


def build_journal_messages(
    journal_text: str,
    context_snippets: list[str] | None = None,
) -> list[dict[str, str]]:
    """One-shot: satu entri jurnal masuk, satu analisis keluar.

    context_snippets: HOOK RAG (fase berikutnya) — cuplikan konten psikoedukasi
    relevan untuk memperkaya sugesti pada analisis.
    """
    system = ANALYSIS_INSTRUCTION
    if context_snippets:
        blok = "\n---\n".join(context_snippets)
        system += (
            "\n\nReferensi psikoedukasi terkurasi berikut BOLEH dipakai untuk memperkaya sugesti:\n"
            f"{blok}\n"
            "Aturan pakai referensi:\n"
            "- JANGAN gunakan referensi untuk menuliskan diagnosis — tetap non-diagnostik.\n"
            "- Sebutkan halaman bacaannya secara natural maksimal satu kali, hanya jika relevan dengan isian jurnal.\n"
            "- Jangan mengarang detail di luar referensi dan isi jurnal."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Teks jurnal:\n\"\"\"\n{journal_text}\n\"\"\""},
    ]
