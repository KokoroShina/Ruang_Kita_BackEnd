"""Unit test murni guardrails — tanpa HTTP, tanpa DB."""

import pytest

from app.services.ai.guardrails import (
    SUPPORT_REDIRECT_TEXT,
    apply_disclaimer,
    detect_crisis,
)


@pytest.mark.parametrize(
    "text",
    [
        "aku pengen mati aja",
        "Aku capek banget sampai mikir PENGEN MATI",
        "kadang kepikiran bunuh diri",
        "I want to die",
        "maybe I should kill myself",
        "gak mau hidup lagi rasanya",
        "mulai terpikir buat mengakhiri hidupku",
        # Varian ejaan yang sebelumnya lolos filter
        "aku pingin mati",
        "rasanya ingin mati saja",
        "aku capek hidup banget",
        "gak kuat hidup lagi kayaknya",
    ],
)
def test_detect_crisis_flags(text):
    result = detect_crisis(text)
    assert result.flagged is True
    assert result.matched_keyword


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "hari ini aku senang sekali karena lulus ujian",
        "capek banget kerjanya, butuh istirahat",
    ],
)
def test_detect_crisis_clean_text_not_flagged(text):
    assert detect_crisis(text).flagged is False


def test_apply_disclaimer_chat():
    out = apply_disclaimer("Halo.", "chat")
    assert out.startswith("Halo.")
    assert "bukan pengganti psikolog" in out


def test_apply_disclaimer_journal_analysis():
    out = apply_disclaimer("Refleksimu bagus.", "journal_analysis")
    assert "bukan diagnosis profesional" in out


def test_apply_disclaimer_session_title_empty():
    # internal utility: TANPA disclaimer
    assert apply_disclaimer("Judul", "session_title") == "Judul"


def test_apply_disclaimer_unknown_type_defaults_to_chat():
    out = apply_disclaimer("X", "tipe_baru_belum_didaftar")
    assert "teman refleksi" in out


def test_support_redirect_mentions_hotline():
    assert "119" in SUPPORT_REDIRECT_TEXT
