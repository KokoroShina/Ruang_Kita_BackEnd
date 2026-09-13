"""Guardrail layer AI Gateway Ruang Kita.

v2 — normalisasi + typo-tolerant matching + negasi kontekstual:
1. Normalisasi      — lowercase, collapse huruf berulang ("matiii"->"mati"),
                      slang map (gk/ga/nggak -> gak), clitic strip ("dirinya"->"diri").
2. Matching 3 mode  — exact (token-level), compact (tanpa spasi, cth "bunuhdiri"),
                      fuzzy anchor (typo-tolerant via difflib, stdlib).
3. Negasi presisi   — "aku gak mau bunuh diri" TIDAK flag, TAPI keluarga
                      dual-meaning ("gak kuat hidup") & multi-klausa tetap flag.

v3 — scope enforcement (moderat):
4. detect_offtopic() — deteksi PERMINTAAN di luar refleksi (koding, tugas,
                      prompt injection) SEBELUM LLM dipanggil. Sengaja moderat:
                      topik netral lain (resep, fakta umum) TIDAK di-hard-reject,
                      cukup ditolak halus oleh prompt system. Urutan guardrail:
                      crisis dulu, baru offtopic — kalimat distres yang kebetulan
                      meminta hal teknis tetap masuk jalur dukungan.

Kontrak alur gateway (diperbarui):
1. detect_crisis()   — dipanggil pada INPUT sebelum LLM & OUTPUT sebelum dikirim user.
2. detect_offtopic() — dipanggil pada INPUT chat; flagged -> tolak tanpa panggil LLM.
3. apply_disclaimer()— WAJIB dilewati setiap output AI chat/analisis jurnal.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

# Ambang kemiripan — anchor cukup longgar (0.75, hanya kata spesifik), gram vs
# target lebih ketat (0.82) supaya window fuzzy tidak melahirkan noise.
_ANCHOR_FUZZY_THRESHOLD = 0.75
_GRAM_FUZZY_THRESHOLD = 0.82
_FUZZY_WINDOW = 3


@dataclass(slots=True)
class CrisisCheckResult:
    flagged: bool
    matched_keyword: str | None = None


@dataclass(slots=True)
class OffTopicCheckResult:
    flagged: bool
    matched_pattern: str | None = None


# ---------------------------------------------------------------------------
# 1. Normalisasi
# ---------------------------------------------------------------------------

# Slang/gaul -> bentuk baku (kunci & nilai lowercase, post-collapse).
_SLANG_MAP: dict[str, str] = {
    "gk": "gak",
    "ga": "gak",
    "g": "gak",
    "nggak": "gak",
    "enggak": "gak",
    "mw": "mau",
    "mo": "mau",
    "pengen": "pengin",
    "pingin": "pengin",
    "mikir": "pikir",
    "tdk": "tidak",
    "dri": "diri",
    "don't": "dont",
    "can't": "cant",
    "won't": "wont",
    "didn't": "didnt",
}

# Clitic/akhiran yang dilepas dari token (stem minimal 4 huruf).
_CLITIC_RE = re.compile(r"^(.{4,}?)(?:nya|ku|mu|kah|lah|pun)$")


def _collapse_repeats(text: str) -> str:
    """"pengennn matiii" -> "pengen mati".

    (1) Run >= 3 huruf sama -> satu ("matiii" -> "mati", khas chat anak muda).
    (2) Vokal ganda tersisa ("matii") -> satu; kata Indonesia baku hampir
    tidak punya vokal ganda. Konsonan ganda dibiarkan (aman utk serapan).
    """
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"([aeiou])\1+", r"\1", text)
    return text


def _strip_clitics(token: str) -> str:
    if len(token) < 6:
        return token
    m = _CLITIC_RE.match(token)
    return m.group(1) if m else token


def _normalize(text: str) -> str:
    text = text.lower()
    tokens: list[str] = []
    for tok in re.findall(r"[a-z0-9]+(?:'[a-z]+)?|[^\sa-z0-9]", text):
        if not tok[0].isalnum():
            tokens.append(_CLAUSE_BOUNDARY)  # tanda baca = batas klausa
            continue
        tok = _collapse_repeats(tok)
        tok = _SLANG_MAP.get(tok, tok)
        tokens.append(_strip_clitics(tok))
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# 2. Keywords
# ---------------------------------------------------------------------------

CRISIS_KEYWORDS: tuple[str, ...] = (
    # Bahasa Indonesia — keinginan mengakhiri hidup
    "bunuh diri",
    "membunuh diri",
    "ingin bunuh diri",
    "pengin bunuh diri",
    "mau bunuh diri",
    "akhiri hidup",
    "akhiri hidupku",
    "mengakhiri hidup",
    "ending hidup",
    # Ingin mati / tidak ingin hidup
    "ingin mati",
    "pengin mati",
    "mau mati",
    "mati aja",
    "mati saja",
    # Capek/lelah hidup — euphemisme risiko tinggi di konteks youth Indonesia
    "capek hidup",
    "capek banget hidup",
    "lelah hidup",
    "penat hidup",
    # Tidak kuat hidup — dual meaning: nyaris selalu ekspresi distress berat
    "gak kuat hidup",
    "nggak kuat hidup",
    "tidak kuat hidup",
    "gak sanggup hidup",
    # Tidak mau/ingin hidup (negasi internal = kalimat risiko, bukan penolakan)
    "gak mau hidup",
    "gak ingin hidup",
    "tidak mau hidup",
    "tidak ingin hidup",
    # Melukai diri
    "melukai diri",
    "menyakiti diri",
    "nyakitin diri",
    "nyakiti diri",
    "lukai diri",
    "luka sendiri",
    # Varian kolokial penting
    "akhiri semuanya",
    "menghilang selamanya",
    "hilang dari dunia",
    "pergi selamanya",
    # English (umum di campuran bahasa anak muda)
    "suicide",
    "suicidal",
    "kill myself",
    "end my life",
    "want to die",
    "wanna die",
    "self harm",
    "harm myself",
    "hurt myself",
    "tired of living",
    "tired of life",
    "no reason to live",
    "want to disappear",
    "not worth living",
    "better off dead",
    "better off without me",
)

# Bentuk tanpa spasi ("bunuhdiri", "killmyself") — mode compact.
_COMPACT_KEYWORDS: tuple[str, ...] = tuple(
    dict.fromkeys(kw.replace(" ", "").replace("'", "") for kw in CRISIS_KEYWORDS)
)

# Keluarga dual-meaning: kalimat yang SUDAH mengandung negasi internal
# ("gak kuat hidup" = ekspresi distres, bukan penolakan). Negasi di depannya
# tidak menetralkan — hanya melindungi kalimat literal ("aku gak mau bunuh diri").
_DUAL_MEANING_FAMILIES = {
    "gak kuat hidup",
    "nggak kuat hidup",
    "tidak kuat hidup",
    "gak sanggup hidup",
    "gak mau hidup",
    "gak ingin hidup",
    "tidak mau hidup",
    "tidak ingin hidup",
    "tired of living",
    "tired of life",
    "no reason to live",
    "not worth living",
}

# Marker batas klausa hasil normalisasi (dari tanda baca).
_CLAUSE_BOUNDARY = "|"

# Kata negasi (bentuk post-normalisasi).
_NEGATION_WORDS = {
    "gak", "tidak", "jangan", "bukan", "tak",
    "never", "not", "no", "dont", "cant", "wont", "didnt",
}

# Kata benda barang/konteks non-psikologis — menetralkan "mau mati"
# ("hp aku mau mati", "sinyal mau mati") yang sangat ambigu.
_DEVICE_WORDS = {
    "hp", "handphone", "hape", "phone", "batre", "baterai", "battery",
    "sinyal", "signal", "wifi", "kuota", "listrik", "mesin", "motor",
    "mobil", "ac", "tv", "kipas", "lampu", "komputer", "laptop",
    "keyboard", "mouse", "headset", "earphone", "charger", "galon",
}

# Kata benda barang/konteks non-psikologis — menetralkan "mau mati"
# ("hp aku mau mati", "sinyal mau mati") yang sangat ambigu.
_DEVICE_WORDS = {
    "hp", "handphone", "hape", "phone", "batre", "baterai", "battery",
    "sinyal", "signal", "wifi", "kuota", "listrik", "mesin", "motor",
    "mobil", "ac", "tv", "kipas", "lampu", "komputer", "laptop",
    "keyboard", "mouse", "headset", "earphone", "charger", "galon",
}

# Anchor fuzzy: (anchor, target). Anchor spesifik saja — kata generik
# (hidup/diri/mati) sengaja TIDAK dipakai sebagai anchor (noise tinggi).
_FUZZY_ANCHORS: tuple[tuple[str, str], ...] = (
    ("bunuh", "bunuh diri"),
    ("membunuh", "membunuh diri"),
    ("mengakhiri", "mengakhiri hidup"),
    ("mengakhirin", "mengakhiri hidup"),
    ("nyakitin", "nyakitin diri"),
    ("nyakiti", "nyakiti diri"),
    ("lukai", "lukai diri"),
    ("suicid", "suicidal"),
    ("kill", "kill myself"),
)


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _positions_of(tokens: list[str], keyword: str) -> list[int]:
    """Index token awal tiap kemunculan keyword (token-level)."""
    ktoks = keyword.split()
    n = len(ktoks)
    if n == 1:
        return [i for i, t in enumerate(tokens) if t == ktoks[0]]
    return [i for i in range(len(tokens) - n + 1) if tokens[i : i + n] == ktoks]


def _has_negation_before(tokens: list[str], idx: int) -> bool:
    """Ada negasi <3 token sebelum idx (tanpa menembus batas klausa '|')?
    Connective ("akan", "mikir", dst.) boleh mengisi slot di antara.
    """
    window: list[str] = []
    for t in reversed(tokens[:idx]):
        if t == _CLAUSE_BOUNDARY:
            break
        if len(window) >= 3:
            break
        window.append(t)
    return any(t in _NEGATION_WORDS for t in window)


def _match_exact(tokens: list[str]) -> str | None:
    for kw in CRISIS_KEYWORDS:
        positions = _positions_of(tokens, kw)
        if not positions:
            continue
        if kw in _DUAL_MEANING_FAMILIES:
            return kw
        for i in positions:
            if _has_negation_before(tokens, i):
                continue
            if kw == "mau mati" and any(
                t in _DEVICE_WORDS for t in tokens[max(0, i - 3) : i]
            ):
                continue  # "hp aku mau mati" — konteks perangkat, bukan diri
            return kw
    return None


# Negasi tertanam di dalam token compact: "akugakMAUbunuhdiri" -> sebelum
# keyword "bunuhdiri" ada "gak[mau]". Toleransi: varian connector (mau/pengen/
# pengin/...) + lem morpheme sisa ("meng" di "mengakhiri") max 5 huruf.
# (?<!a) mengecualikan "agak" (kata "agakbunuhdiri" tidak boleh di-suppress).
_COMPACT_NEGATION_RE = re.compile(
    r"(?:(?<!a)gak|tidak|jangan|bukan|tak|never|not|dont|cant|wont|didnt)"
    r"(?:mau|pengin|pengen|ingin|akan|bakal|pernah|mikir|pikir)?[a-z]{0,5}$"
)


def _match_compact(tokens: list[str]) -> str | None:
    """Keyword tertempel tanpa spasi di-level TOKEN ("bunuhdiri" satu token),
    bukan full-text substring — supaya "maumati" di dalam "maumatikan" tidak
    false-hit. Negasi di token sebelumnya ("gak pengen bunuhdiri") maupun
    tertanam di dalam token ("akugakmaubunuhdiri") dua-duanya dihormati.
    """
    for i, tok in enumerate(tokens):
        if len(tok) < 8 or tok == _CLAUSE_BOUNDARY:
            continue
        for kw in _COMPACT_KEYWORDS:
            if not (tok == kw or tok.startswith(kw) or tok.endswith(kw)):
                continue
            if _has_negation_before(tokens, i):
                continue
            if tok != kw:
                # Negasi tertanam: bagian token sebelum keyword
                prefix = tok[: len(tok) - len(kw)] if tok.endswith(kw) else tok[len(kw):]
                if _COMPACT_NEGATION_RE.search(prefix):
                    continue
            return kw
    return None


def _match_fuzzy(tokens: list[str]) -> str | None:
    """Typo-tolerant via anchor. Cuma evaluasi window kecil di sekitar
    anchor — biaya O(n) kecil dan noise terkendali. Negasi diperiksa
    ulang supaya fuzzy tidak men-flag ulang yang sudah di-suppress.
    """
    for i, tok in enumerate(tokens):
        for anchor, target in _FUZZY_ANCHORS:
            if tok != anchor and not (
                len(anchor) >= 5 and _ratio(tok, anchor) >= _ANCHOR_FUZZY_THRESHOLD
            ):
                continue
            lo = max(0, i - _FUZZY_WINDOW)
            hi = min(len(tokens), i + _FUZZY_WINDOW + 1)
            window = tokens[lo:hi]
            tlen = len(target.split())
            for span in range(min(tlen, len(window)), 0, -1):
                for j in range(len(window) - span + 1):
                    gram = " ".join(window[j : j + span])
                    if _ratio(gram, target) >= _GRAM_FUZZY_THRESHOLD:
                        abs_idx = lo + j
                        if _has_negation_before(tokens, abs_idx):
                            continue
                        return gram
    return None


# ---------------------------------------------------------------------------
# 3. Scope enforcement — permintaan di luar refleksi (moderat)
# ---------------------------------------------------------------------------
#
# Pendekatan dua sisi (aksi + objek) pada token hasil normalisasi RINGAN
# (lowercase, collapse, slang — TANPA clitic-strip supaya "makalah" tidak
# rusak jadi "maka"). Flag hanya bila kata PERMINTAAN muncul dekat OBJEK
# teknis/tugas — menyebut kata teknis dalam curhat tidak tertangkap.

# Kata aksi permintaan konten/tugas
_REQUEST_ACTIONS: frozenset[str] = frozenset(
    {"buat", "buatkan", "buatlah", "bikin", "bikinin", "bikinlah", "tulis", "tuliskan", "tulislah"}
)

# Kata aksi mengerjakan — hanya dipasangkan dengan objek tugas/soal
# (bukan esai: "habis ngerjain esai" = curhat lampau, bukan permintaan)
_DO_HOMEWORK_ACTIONS: frozenset[str] = frozenset({"kerjakan", "kerjain"})

# Objek teknis (koding) & tugas akademik/kreatif
_TECH_OBJECTS: frozenset[str] = frozenset(
    {
        "array", "kode", "program", "website", "web", "aplikasi", "app",
        "fungsi", "function", "script", "bot", "api", "query", "sql",
        "python", "javascript", "java", "html", "css", "react", "algoritma",
        "server", "database", "website",
    }
)
_TASK_OBJECTS: frozenset[str] = frozenset(
    {
        "esai", "essay", "makalah", "ppt", "powerpoint", "tugas", "soal",
        "puisi", "rangkuman", "papper", "paper",
    }
)
_HOMEWORK_OBJECTS: frozenset[str] = frozenset({"tugas", "soal"})

# Jarak maksimum token aksi → objek (partikel "sebuah/tentang/dong" mengisi slot)
_ACTION_OBJECT_WINDOW = 3

# Marker prompt injection — diuji sebagai substring pada teks ternormalisasi
# (bahasa Indonesia + English campuran khas chat anak muda).
_INJECTION_MARKERS: tuple[str, ...] = (
    # English — klassik jailbreak
    "ignore previous instruction",
    "ignore all previous instruction",
    "ignore the previous",
    "disregard previous",
    "disregard all previous",
    "forget your instruction",
    "forget all previous",
    "forget previous instruction",
    "system prompt",
    "reveal your prompt",
    "show your prompt",
    "print your instruction",
    "your instruction is",
    "pretend you are",
    "act as",
    "act like you are",
    "you are now",
    "new instructions",
    "override instruction",
    "developer mode",
    "jailbreak",
    "dan mode",
    # Indonesia
    "abaikan instruksi",
    "abaikan semua instruksi",
    "abaikan aturan",
    "abaikan semua aturan",
    "abaikan prompt",
    "lupakan instruksi",
    "lupakan semua instruksi",
    "lupakan aturan",
    "lupakan peranmu",
    "sekarang kamu adalah",
    "kamu sekarang adalah",
    "kamu adalah asisten",
    "kamu adalah ai",
    "ubah instruksi",
    "ubah aturanmu",
    "ganti instruksi",
    "tampilkan instruksi",
    "tampilkan prompt",
    "keluarkan prompt",
    "apa instruksi sistemmu",
    "apa prompt sistemmu",
    "mode pengembang",
)


def _normalize_light(text: str) -> list[str]:
    """Normalisasi ringan tanpa clitic-strip — untuk pencocokan aksi/objek."""
    tokens: list[str] = []
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        tok = _collapse_repeats(tok)
        tok = _SLANG_MAP.get(tok, tok)
        tokens.append(tok)
    return tokens


def detect_offtopic(text: str | None) -> OffTopicCheckResult:
    """Deteksi permintaan di luar scope refleksi — chat Pahami.

    Moderat: hanya koding/tugas-akademik/injection yang di-hard-reject;
    topik netral lain dibiarkan masuk LLM (prompt system yang menolak halus).
    Dipanggil SETELAH detect_crisis — distres selalu menang atas offtopic.
    Pemanggil mengalihkan ke balasan SCOPE_REDIRECT_TEXT tanpa memanggil LLM.
    """
    if not text:
        return OffTopicCheckResult(flagged=False)

    # 1) Aksi permintaan + objek teknis/tugas dalam jendela ±3 token.
    light = _normalize_light(text)
    for i, tok in enumerate(light):
        if tok in _REQUEST_ACTIONS:
            lo = max(0, i - _ACTION_OBJECT_WINDOW)
            hi = min(len(light), i + _ACTION_OBJECT_WINDOW + 1)
            window = light[lo:hi]
            hit = next(
                (o for o in window if o in _TECH_OBJECTS or o in _TASK_OBJECTS),
                None,
            )
            if hit:
                return OffTopicCheckResult(flagged=True, matched_pattern=f"{tok} … {hit}")
        if tok in _DO_HOMEWORK_ACTIONS:
            lo = max(0, i - _ACTION_OBJECT_WINDOW)
            hi = min(len(light), i + _ACTION_OBJECT_WINDOW + 1)
            hit = next((o for o in light[lo:hi] if o in _HOMEWORK_OBJECTS), None)
            if hit:
                return OffTopicCheckResult(flagged=True, matched_pattern=f"{tok} … {hit}")

    # 2) Marker injection — substring pada teks ternormalisasi penuh
    #    (tanpa tanda baca tapi dengan spasi) supaya variasi tetap kena.
    tokens = _normalize(text).split()
    if tokens:
        squeezed = " ".join(tokens)
        for marker in _INJECTION_MARKERS:
            if marker in squeezed:
                return OffTopicCheckResult(flagged=True, matched_pattern=marker)

    return OffTopicCheckResult(flagged=False)


# ---------------------------------------------------------------------------
# 4. API publik
# ---------------------------------------------------------------------------


def detect_crisis(text: str | None) -> CrisisCheckResult:
    """Hook crisis detection — titik intersepsi input/output di gateway.

    v2: normalisasi + 3 mode match + negasi kontekstual. Bias keamanan:
    bentuk yang tidak pasti tetap dianggap flagged (false positive lebih
    murah daripada false negative di domain ini).
    Pemanggil WAJIB mengalihkan ke jalur dukungan khusus jika flagged=True.
    """
    if not text:
        return CrisisCheckResult(flagged=False)

    tokens = _normalize(text).split()
    if not tokens:
        return CrisisCheckResult(flagged=False)

    hit = _match_exact(tokens)
    if hit:
        return CrisisCheckResult(flagged=True, matched_keyword=hit)

    hit = _match_compact(tokens)
    if hit:
        return CrisisCheckResult(flagged=True, matched_keyword=hit)

    hit = _match_fuzzy(tokens)
    if hit:
        return CrisisCheckResult(flagged=True, matched_keyword=hit)

    return CrisisCheckResult(flagged=False)


# ---------------------------------------------------------------------------
# Disclaimer layer (tidak berubah dari v1)
# ---------------------------------------------------------------------------

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

# Balasan standar saat permintaan di luar scope refleksi (chat Pahami).
# Tone sama dengan disclaimer: hangat, tanpa menghakimi, arahkan kembali.
SCOPE_REDIRECT_TEXT = (
    "Hmm, sepertinya itu di luar bidangku. Aku di sini khusus untuk menemani kamu "
    "merefleksikan perasaan dan pengalamanmu — bukan untuk membantu tugas teknis "
    "atau hal lainnya. Tapi kalau ada yang sedang membebani pikiranmu, atau kamu "
    "penasaran dengan apa yang kamu rasakan belakangan ini, aku senang sekali "
    "mendengar ceritamu. Mau mulai dari situ?"
)
