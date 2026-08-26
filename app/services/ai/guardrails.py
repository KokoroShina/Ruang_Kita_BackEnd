"""Guardrail layer AI Gateway Ruang Kita.

Sesi ini menyediakan STRUKTUR + versi minimal yang sudah berfungsi.
Logic lengkap (klasifikasi halus, jalur konseling nyata) menyusul di sesi berikutnya.

Dua komponen wajib dalam alur gateway:
1. detect_crisis()   — dipanggil pada INPUT sebelum LLM & OUTPUT sebelum dikirim user.
2. apply_disclaimer()— WAJIB dilewati setiap output AI chat/analisis jurnal.
"""

import re
from dataclasses import dataclass


@dataclass(slots=True)
class CrisisCheckResult:
    flagged: bool
    matched_keyword: str | None = None


# Seed keyword sederhana (id/en) — STUB v1, BELUM deteksi kontekstual.
# TODO(sesi berikutnya): klasifikasi konteks, ambang sensitivitas, negasi
# ("gak mau mati-matian"), dan integrasi model moderasi terpisah.
CRISIS_KEYWORDS: tuple[str, ...] = (
    # Bahasa Indonesia
    "bunuh diri",
    "membunuh diri",
    "mau mati",
    # Varian ejaan "ingin mati" — formal & kolokial (kasus nyata: "aku pingin mati" lolos)
    "ingin mati",
    "pingin mati",
    "pengen mati",
    "pengin mati",
    "ga mau hidup",
    "gak mau hidup",
    "nggak mau hidup",
    "tidak ingin hidup",
    "capek hidup",
    "lelah hidup",
    "ga kuat hidup",
    "gak kuat hidup",
    "akhiri hidupku",
    "melukai diri",
    "menyakiti diri",
    "nyakitin diri",
    "nyakit diri",
    # English (umum di campuran bahasa anak muda)
    "suicide",
    "suicidal",
    "kill myself",
    "end my life",
    "want to die",
    "wanna die",
    "self-harm",
    "harm myself",
)

_CRISIS_PATTERN = re.compile("|".join(re.escape(k) for k in CRISIS_KEYWORDS))


def detect_crisis(text: str | None) -> CrisisCheckResult:
    """Hook crisis detection — titik intersepsi input/output di gateway.

    Return flagged=False saat ini kecuali keyword cocok persis.
    Pemanggil WAJIB mengalihkan ke jalur dukungan khusus jika flagged=True
    (bukan melanjutkan sebagai AI response biasa).
    """
    if not text:
        return CrisisCheckResult(flagged=False)
    match = _CRISIS_PATTERN.search(text.lower())
    if match:
        return CrisisCheckResult(flagged=True, matched_keyword=match.group(0))
    return CrisisCheckResult(flagged=False)


# Disclaimer per endpoint_type — versi awal, satu kalimat standar.
# TODO(sesi berikutnya): variasi dinamis sesuai tingkat sensitivitas topik.
_DISCLAIMERS: dict[str, str] = {
    "chat": (
        "\n\n_(Catatan: aku teman refleksi, bukan pengganti psikolog atau psikiater. "
        "Kalau bebanmu terasa terlalu berat, ngobrol sama tenaga profesional itu langkah yang berani.)_"
    ),
    "journal_analysis": (
        "\n\n_(Refleksi ini bersifat dukungan umum, bukan diagnosis profesional.)_"
    ),
    # Internal/utility calls — TIDAK diberi disclaimer
    "session_title": "",
}


def apply_disclaimer(content: str, endpoint_type: str) -> str:
    """Disclaimer layer — SEMUA output AI konsumen wajib melewati fungsi ini.

    Tipe yang belum terdaftar di _DISCLAIMERS otomatis dapat disclaimer chat
    (safe default). Tipe internal/utility didaftarkan eksplisit dengan suffix "".
    """
    suffix = _DISCLAIMERS.get(endpoint_type, _DISCLAIMERS["chat"])
    return f"{content}{suffix}"


# Balasan standar jalur dukungan (chat & jurnal). SEJIWA 119 ext.8 = layanan
# Kemenkes RI 24 jam. Dipakai saat crisis detection menangkap indikasi risiko.
SUPPORT_REDIRECT_TEXT = (
    "Terima kasih sudah berani ngomongin ini — itu langkah yang nggak mudah. "
    "Aku pengen pastikan kamu sekarang didampingi orang yang tepat: "
    "coba hubungi SEJIWA 119 ext. 8 (gratis, 24 jam), atau cerita hari ini juga ke "
    "orang dewasa yang kamu percaya — keluarga, guru BK, atau konselor. "
    "Kamu nggak harus melewati ini sendirian. 💙"
)
