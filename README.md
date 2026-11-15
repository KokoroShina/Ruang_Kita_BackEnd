<div align="center">

# Ruang Kita — Backend API

**REST API that powers a wellbeing-literacy PWA for Indonesian youth (15–23): self-recognition journaling & mood tracking, an AI reflection companion, and curated mental-health content.**

![FastAPI](https://img.shields.io/badge/FastAPI-0.141.1-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-aiomysql-4479A1?logo=mysql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.52-0078D4?logo=sqlalchemy&logoColor=white)
![OpenRouter](https://img.shields.io/badge/AI%20Gateway-OpenRouter-8A5CF6)
![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Status](https://img.shields.io/badge/status-in%20development-yellow)
![License](https://img.shields.io/badge/license-TBD-lightgrey)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Background & Problem](#background--problem)
3. [The Three Pillars](#the-three-pillars)
4. [Features](#features)
5. [Screenshots / Demo](#screenshots--demo)
6. [Architecture](#architecture)
7. [Tech Stack](#tech-stack)
8. [Project Structure](#project-structure)
9. [Database Schema](#database-schema)
10. [Getting Started](#getting-started)
11. [API Overview](#api-overview)
12. [AI Usage & Safety](#ai-usage--safety)
13. [Privacy & Security](#privacy--security)
14. [Deployment](#deployment)
15. [Roadmap](#roadmap)
16. [Contributing & License](#contributing--license)
17. [Author / Contact](#author--contact)

---

## Overview

Ruang Kita is a wellbeing-literacy platform for Indonesian youth aged 15–23. This repository is its **backend REST API**, built with FastAPI: it handles authentication, journaling, mood tracking, an AI reflection chatbot, a curated mental-health encyclopedia, rule-based content recommendations, and a dedicated AI gateway with safety guardrails.

It is **not** a therapy tool, not a diagnostic instrument, and not a replacement for professional help. Its goal is to be a safe, low-barrier first step: helping young people recognize what they feel, understand their emotions, and find credible next steps — in Bahasa Indonesia.

> **Ringkasan (Bahasa Indonesia):** Ruang Kita adalah API backend untuk PWA literasi kesejahteraan mental anak muda Indonesia (15–23 tahun). Pengguna bisa menulis jurnal, mencatat mood, mengobrol dengan chatbot refleksi berbasis AI, membaca ensiklopedia kesehatan mental, dan menerima rekomendasi konten. Aplikasi ini **bukan** alat terapi atau diagnosis — tujuannya menjadi langkah pertama yang aman sebelum mencari bantuan profesional.

| | |
|---|---|
| **Frontend repo** | [KokoroShina/Ruang_Kita_FrontEnd](https://github.com/KokoroShina/Ruang_Kita_FrontEnd) (Next.js + TypeScript + Tailwind, PWA) |
| **API docs** | Swagger UI at `/docs` when the server runs locally |
| **Status** | Development nearly complete — not yet deployed |

---

## Background & Problem

The 15–23 age range is a high-pressure transition period — school, college, first jobs — while mental-health stigma in Indonesia is still strong. In practice this creates a gap:

- **Stigma keeps questions private.** Many young people are reluctant to ask about what they feel, even to people close to them.
- **Untrustworthy sources.** What they do find online is often unreliable, uncurated, or not in their language.
- **No clear first step.** Between "I feel off" and "I should see a professional" there is no safe, accessible space to start.

Ruang Kita was designed to fill that gap: an Indonesian-language space where a young person can first **recognize** their condition, then **understand** it through credible psychoeducation, and finally **find** support and concrete next steps — including professional and crisis resources when needed.

---

## The Three Pillars

The pillar-to-feature mapping below reflects the actual codebase (see `main.py` app description and each router's module docstring).

### 1. Kenali (Know Yourself)
**Goal:** help users recognize and track their own condition.

| Verified feature | Code |
|---|---|
| Journaling (CRUD) with one-shot AI analysis → reflection insight, introspective questions, one small step | `app/api/v1/journal.py`, `journal_service.py` |
| Mood logging (1–5 score + free-form label), history filter, statistics: daily trend, score distribution, streak, top labels | `app/api/v1/mood.py`, `mood_service.py` |
| Crisis indication on journal content → separate support path, not normal AI analysis | `journal_service.py` |

### 2. Pahami (Understand)
**Goal:** help users make sense of emotions and mental-health topics.

| Verified feature | Code |
|---|---|
| Multi-turn AI reflection chatbot (session create/list/detail/delete, auto-generated session titles) | `app/api/v1/chat.py`, `chat_service.py` |
| Streaming replies via Server-Sent Events (`meta → model → delta×N → crisis/done/error`) | `chat.py`, `ai/router.py` |
| Mental-health encyclopedia (topics with summary, signs, causes, coping, myths vs facts, when-to-seek-help, support resources) | `app/api/v1/topics.py` |
| Retrieved encyclopedia/library snippets ground the AI's answers (RAG) | `app/services/ai/retriever.py` |

### 3. Temukan (Find Support)
**Goal:** help users find credible content and next steps.

| Verified feature | Code |
|---|---|
| Rule-based personal recommendations built from the user's own journal mentions, mood labels, and low-mood trends (no AI call) | `app/api/v1/discover.py`, `discover_service.py` |
| Browse curated psychoeducation content library (article / video / audio / exercise, filter by type, topic, search) | `discover.py` |
| Crisis support redirect (SEJIWA 119 ext. 8 — Indonesia's Ministry of Health 24-hour service) whenever risk signals are detected | `app/services/ai/guardrails.py` |

---

## Features

All features below are verified in this repository's code:

- **Auth:** email + password registration, JWT access token (HS256, 7-day default), generic error messages to prevent user enumeration.
- **AI reflection chat (Pahami):** multi-turn sessions with full history, optional SSE streaming, background LLM-generated session titles, per-session ownership checks.
- **AI journal analysis (Kenali):** one-shot reflection per entry, stored as `ai_insight`, re-analyzable; editing entry content invalidates stale insight.
- **Mood statistics (Kenali):** daily trend, score distribution, current streak, top labels over a 7–365 day window.
- **Mental-health encyclopedia:** protected read of published topics; full admin CRUD gated by email allowlist.
- **Content library & recommendations:** admin-managed content; rule-based personalized recommendations from local signals only.
- **Semantic RAG (optional):** lexical retrieval always on; when a Gemini API key is set, queries are embedded (`text-embedding-004`) and matched by cosine similarity, with automatic graceful fallback to lexical retrieval.
- **AI safety pipeline:** crisis detection on input *and* output (also incrementally during streaming), off-topic/scope enforcement, prompt-injection markers, mandatory disclaimer on every user-facing AI response.
- **Usage observability:** every gateway attempt (success or failure) logged to `ai_usage_log` — model requested/used, latency, tokens, error type, finish reason.
- **Data rights:** one-click full personal-data export (JSON download) and password-confirmed hard account deletion with cascading cleanup.
- **Image uploads:** admin-only image upload with MIME allowlist (JPEG/PNG/WebP), 5 MB cap, randomized filenames, served under `/media`.
- **Daily logs:** console + `logs/app.log` with midnight rotation and configurable retention.

---

## Screenshots / Demo

No live demo is deployed yet. Screenshots will be added here after the first deployment.

| Screen | Placeholder |
|---|---|
| Chat reflection (Pahami) | `<!-- TODO: screenshot of chat UI -->` |
| Journal with AI insight (Kenali) | `<!-- TODO: screenshot of journal UI -->` |
| Topic encyclopedia (Pahami) | `<!-- TODO: screenshot of topic page -->` |
| Recommendations feed (Temukan) | `<!-- TODO: screenshot of discover UI -->` |

<!-- TODO: add real screenshots and, once deployed, a live demo URL -->

---

## Architecture

```mermaid
flowchart LR
    subgraph Client["PWA Client"]
        FE["Next.js Frontend<br/>(separate repo)"]
    end

    subgraph Backend["FastAPI Backend (this repo)"]
        API["/api/v1 routers<br/>auth · chat · journal · mood ·<br/>topics · discover · account"]
        GW["AI Gateway<br/>(guardrails · fallback · logging)"]
        SVC["Services layer"]
    end

    DB[("MySQL<br/>aiomysql (async)")]
    OR["OpenRouter API<br/>(free-tier LLMs)"]
    GEM["Gemini Embeddings API<br/>(optional, semantic RAG)"]

    FE -->|"HTTPS + JWT Bearer"| API
    API --> SVC --> DB
    SVC --> GW
    GW -->|"typed errors,<br/>per-model fallback"| OR
    GW -->|"embedding query<br/>(semantic retrieval)"| GEM
```

**Data flow, briefly:**

1. The client authenticates with `POST /auth/login` and receives a JWT, sent back as an `Authorization: Bearer` header on every protected request. Admin capability is resolved from the `ADMIN_EMAILS` environment allowlist — not a role column.
2. Feature routers delegate to a services layer; each service queries MySQL asynchronously through SQLAlchemy (aiomysql driver) and enforces per-user ownership on every read/write.
3. Chat and journal-analysis requests go through the AI Gateway, which runs crisis detection before *and* after the LLM call, tries a default free-tier model then falls back through a configured list on rate-limit/timeout/provider errors, applies a mandatory disclaimer, and logs every attempt to `ai_usage_log` from a separate DB session so logging can never break the user flow.
4. Retrieved encyclopedia/library snippets (lexical or semantic) are injected into the system prompt to ground AI answers in curated, non-diagnostic content.

---

## Tech Stack

Versions are pinned in `requirements.txt`; rationale noted where the code makes it visible.

| Layer | Technology | Version | Why |
|---|---|---|---|
| Language | Python | 3.12+ (dev venv: 3.13) | async-first ecosystem |
| Web framework | FastAPI | 0.141.1 | async, Pydantic-native validation, auto OpenAPI docs |
| ASGI server | Uvicorn | 0.52.4 | standard dev/prod server for FastAPI |
| ORM | SQLAlchemy (async) | 2.0.52 | typed `Mapped` models, async sessions |
| Database | MySQL via aiomysql | 0.3.2 | relational integrity, mature hosting options |
| Migrations | Alembic | 1.19.1 | versioned schema evolution (9 migrations so far) |
| Auth | PyJWT + Bearer | 2.13.0 | stateless tokens, HS256 |
| Password hashing | bcrypt (direct) | 5.0.0 | cost 12; used directly, **not** passlib (known passlib/bcrypt 5 incompatibility) |
| Config & validation | pydantic + pydantic-settings | 2.13.4 | typed settings loaded from `.env` |
| HTTP client | httpx (async) | 0.28.1 | connection-pooled calls to OpenRouter / Gemini |
| AI gateway | OpenRouter | — | single key → many free-tier models with fallback |
| Embeddings (optional) | Gemini `text-embedding-004` | — | semantic RAG; degrades to lexical retrieval without a key |
| Testing | pytest + pytest-asyncio | 9.1.1 / 1.2.0 | async test suite against a separate test database |

---

## Project Structure

```
RuangKita_Backend/
├── main.py                  # App factory, CORS, request logging, /media static mount
├── alembic/                 # Migrations (9 revisions, initial → ai_usage_log → embeddings)
├── alembic.ini
├── app/
│   ├── core/
│   │   ├── config.py        # All typed settings from .env
│   │   ├── security.py      # bcrypt hashing + JWT create/decode
│   │   ├── dependencies.py  # CurrentUser / AdminUser gates, Bearer auth
│   │   └── logging_setup.py # Daily rotating file + console logs
│   ├── db/
│   │   ├── session.py       # Async engine, session factory, get_db dependency
│   │   └── base.py          # Declarative Base, UUID/Timestamp mixins
│   ├── models/              # SQLAlchemy ORM models (8 tables)
│   ├── schemas/             # Pydantic request/response models per feature
│   ├── api/v1/              # Routers: health, auth, account, ai, chat,
│   │                        #   journal, mood, topics, discover, uploads
│   └── services/
│       ├── chat_service.py     # Multi-turn chat flow, streaming, auto-title
│       ├── journal_service.py  # Journal CRUD + AI analysis
│       ├── mood_service.py     # Mood logs + statistics
│       ├── topic_service.py    # Encyclopedia CRUD
│       ├── discover_service.py # Rule-based recommendations + content library
│       ├── account_service.py  # Profile, data export, account deletion
│       └── ai/                 # AI Gateway internals:
│           ├── router.py          #   model fallback, guardrail hooks, usage logging
│           ├── openrouter_client.py # typed OpenRouter errors, streaming SSE parser
│           ├── guardrails.py      #   crisis + off-topic detection, disclaimers
│           ├── retriever.py       #   lexical + semantic RAG retrieval
│           ├── embeddings.py      #   Gemini embedding client (graceful degradation)
│           └── prompts/           # chat + journal system prompts
├── scripts/                 # create_admin, content/topic importers, backfills
├── tests/                   # pytest suite (async, separate test DB)
├── media/                   # Admin-uploaded images (gitignored)
├── logs/                    # Daily rotated app logs (gitignored)
├── .env.example             # All env vars with dummy values
├── requirements.txt         # Pinned runtime dependencies
└── requirements-dev.txt     # Runtime deps + pytest tooling
```

---

## Database Schema

Eight tables. All primary keys are UUIDs (stored as 32-char hex in MySQL, exposed with dashes via the API). Timestamps: `created_at` / `updated_at` on most tables.

```mermaid
erDiagram
    users ||--o{ journal_entries : "writes (CASCADE)"
    users ||--o{ mood_logs : "records (CASCADE)"
    users ||--o{ chat_sessions : "opens (CASCADE)"
    chat_sessions ||--o{ chat_messages : "contains (CASCADE)"
    users |o--o{ content_library : "curated_by (SET NULL)"
    users |o--o{ mental_health_topics : "created_by (SET NULL)"
    users |o--o{ ai_usage_log : "user_id (SET NULL)"

    users {
        char_32 id PK
        string_255 email UK "unique, indexed"
        string_255 hashed_password "bcrypt cost 12"
        string_255 full_name "nullable"
        bool is_active
        string_32 consent_version "nullable"
        datetime consent_accepted_at "nullable"
    }
    journal_entries {
        char_32 id PK
        char_32 user_id FK
        string_200 title "nullable"
        text content
        text ai_insight "nullable, AI reflection"
        bool crisis_flagged
    }
    mood_logs {
        char_32 id PK
        char_32 user_id FK
        smallint mood_score "1-5, CHECK constraint, nullable"
        string_64 mood_label "nullable"
        text note "nullable"
        string_32 source "manual | journal | chat | onboarding_selfcheck"
        datetime logged_at "indexed, separate from created_at"
    }
    chat_sessions {
        char_32 id PK
        char_32 user_id FK
        string_255 title "nullable, LLM auto-generated"
        string_32 status "active | closed | archived"
        bool crisis_flagged
        datetime last_message_at "indexed"
    }
    chat_messages {
        char_32 id PK
        char_32 session_id FK
        string_16 sender_role "user | assistant, CHECK constraint"
        text content
        string_128 provider "nullable, model that produced it"
        bool crisis_flagged
    }
    content_library {
        char_32 id PK
        string_160 slug UK
        string_255 title
        text summary
        text content_body
        string_32 content_type "article | video | audio | exercise"
        json topics "list of topic names"
        string_500 source_url
        string_500 image_url
        smallint duration_minutes
        string_8 language "default id"
        bool is_published
        json embedding "semantic RAG vector"
        char_32 curated_by FK "nullable"
    }
    mental_health_topics {
        char_32 id PK
        string_120 slug UK
        string_200 name
        json alt_names "popular terms"
        string_32 category "mood | anxiety | personality | trauma | eating | burnout | other"
        text summary
        json signs_symptoms
        text causes_risk_factors
        text coping_treatment
        json myths_facts
        text when_to_seek_help
        json support_resources
        json related_topic_slugs
        text sources
        string_500 image_url
        string_500 video_url
        bool is_published
        json embedding "semantic RAG vector"
        char_32 created_by FK "nullable"
    }
    ai_usage_log {
        char_32 id PK
        string_32 endpoint_type "test | chat | journal_analysis"
        string_128 model_requested
        string_128 model_used "on success"
        bool success
        string_64 error_type "rate_limit | timeout | provider_error | auth_error | crisis_input_detected | crisis_output_detected | offtopic_input_detected"
        text error_detail
        int latency_ms
        int input_tokens
        int output_tokens
        string_32 finish_reason
        char_32 user_id FK "nullable, SET NULL"
        datetime created_at "indexed"
    }
```

Design notes:

- **Cascading ownership:** deleting a user removes their journal entries, mood logs, chat sessions and messages (`ON DELETE CASCADE` + `passive_deletes`). Aggregated `ai_usage_log` rows survive as anonymized audit data (`user_id → SET NULL`).
- **Crisis flags** exist at both the entry/session level and the per-message level, making incidents auditable without reading full content.
- **Mood flexibility:** score is optional (1–5, DB-checked) alongside a free-form label, so the mood model can evolve without a destructive migration.
- **RAG vectors** are stored as JSON float arrays on both content tables, with `embedded_at` to track freshness.

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **MySQL 8** running locally (or any reachable MySQL instance)
- A free **[OpenRouter](https://openrouter.ai/keys) API key** (required for chat/journal AI features)
- *(Optional)* a free **Gemini API key** from [AI Studio](https://aistudio.google.com/apikey) to enable semantic RAG

### 1. Clone & install

```bash
git clone https://github.com/KokoroShina/Ruang_Kita_BackEnd.git
cd RuangKita_BackEnd

python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\pip.exe install -r requirements.txt
# Linux/macOS:
# source .venv/bin/activate && pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env   # Windows: Copy-Item .env.example .env
```

Then edit `.env` — at minimum set `DATABASE_URL`, `JWT_SECRET`, and `OPENROUTER_API_KEY`. Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Create the database & run migrations

Create an empty MySQL database (e.g. `ruang_kita_db`), then:

```bash
alembic upgrade head
```

### 4. Run the server

```bash
# Windows (as used in this project):
.\.venv\Scripts\uvicorn.exe main:app --reload
# or cross-platform:
python -m uvicorn main:app --reload
```

- Swagger UI: <http://localhost:8000/docs>
- Health check: `GET /api/v1/health` → `{"status": "ok", "database": "up"}`

### 5. Create an admin account

Admin capability is **not** a database role — it is an email allowlist in `.env` (`ADMIN_EMAILS`). The helper script does both steps:

```bash
.\.venv\Scripts\python.exe scripts\create_admin.py --email admin@ruangkita.id
# or: --email admin@ruangkita.id --password <pass> --name "Admin Ruang Kita"
```

Without `--password` it prompts securely (hidden input, not stored in shell history). The script creates the user if needed and registers the email in `ADMIN_EMAILS`. **Restart the server afterwards** so settings reload. With no admins configured, all admin endpoints return `403`.

### 6. Run tests

The test suite runs against a **separate test database** so development data is safe:

```bash
pip install -r requirements-dev.txt   # includes pytest + pytest-asyncio
.\.venv\Scripts\python.exe -m pytest
```

### Environment Variables

All variables verified against `app/core/config.py` and `.env.example`.

| Name | Function | Example (dummy) |
|---|---|---|
| `PROJECT_NAME` | Display name in OpenAPI docs | `Ruang Kita API` |
| `ENVIRONMENT` | `development` / `staging` / `production` (also gates SQL echo) | `development` |
| `API_V1_PREFIX` | Router prefix | `/api/v1` |
| `CORS_ORIGINS` | Allowed origins (JSON array) | `["http://localhost:3000"]` |
| `DATABASE_URL` | Async MySQL DSN (aiomysql driver) | `mysql+aiomysql://user:password@localhost:3306/ruang_kita_db` |
| `JWT_SECRET` | Token signing key — **must** be replaced in production | `<random-48-byte-urlsafe-string>` |
| `JWT_ALGORITHM` | Signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 7 days = 10080) | `10080` |
| `OPENROUTER_API_KEY` | AI gateway key (required for AI features) | `sk-or-v1-xxxx` |
| `OPENROUTER_BASE_URL` | OpenRouter API base | `https://openrouter.ai/api/v1` |
| `AI_TIMEOUT_SECONDS` | Per-call timeout for LLM requests | `90` |
| `AI_DISABLE_REASONING` | Suppress model reasoning leakage in chat answers | `true` |
| `AI_MODEL_DEFAULT` | Primary free-tier model | `meta-llama/llama-3.3-70b-instruct:free` |
| `AI_MODEL_FALLBACKS` | Ordered fallbacks (JSON array) tried on rate limit / error | `["google/gemini-2.0-flash-exp:free","qwen/qwen-2.5-72b-instruct:free"]` |
| `GEMINI_API_KEY` | Optional — enables semantic RAG embeddings | `AIza...xxxx` |
| `EMBEDDING_MODEL` | Gemini embedding model | `text-embedding-004` |
| `EMBEDDING_SIMILARITY_THRESHOLD` | Min cosine similarity for semantic matches | `0.55` |
| `RAG_SEMANTIC_ENABLED` | Toggle semantic retrieval | `true` |
| `GROQ_API_KEY` | Defined in config; **currently unused** (legacy of an earlier multi-provider plan) | *(leave empty)* |
| `ADMIN_EMAILS` | Admin email allowlist (JSON array; empty = all admin endpoints 403) | `["admin@ruangkita.id"]` |
| `IMPORT_ADMIN_EMAIL` / `IMPORT_ADMIN_PASSWORD` | Credentials used by `scripts/import_topics_bulk.py` to log in and bulk-import topics | `admin@ruangkita.id` / `xxxx` |
| `MEDIA_DIR` | Folder for admin-uploaded images | `media` |
| `UPLOAD_MAX_BYTES` | Upload size cap | `5242880` (5 MB) |
| `UPLOAD_ALLOWED_TYPES` | MIME → extension allowlist (config-level) | `{"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}` |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |
| `LOG_DIR` | Log folder | `logs` |
| `LOG_RETENTION_DAYS` | Days to keep rotated log files | `14` |

---

## API Overview

All endpoints are mounted under `/api/v1`. "Auth" = JWT Bearer header required; "Admin" = additionally the caller's email must be in `ADMIN_EMAILS`.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/health` | Service + database health | — |
| `POST` | `/auth/register` | Create account (email, password, name, consent version) | — |
| `POST` | `/auth/login` | Obtain JWT access token | — |
| `GET` | `/auth/me` | Current user profile | Yes |
| `PATCH` | `/auth/me` | Update profile (name and/or password; current password verified) | Yes |
| `GET` | `/me/export` | Download all personal data as JSON | Yes |
| `DELETE` | `/account` | Permanently delete account + all data (password confirmed) | Yes |
| `GET` | `/mood/logs` | List my mood logs (filter by last N days, paginated) | Yes |
| `POST` | `/mood/logs` | Record mood (score 1–5 + optional label/note/backdated time) | Yes |
| `PATCH` | `/mood/logs/{id}` | Update my mood log | Yes |
| `DELETE` | `/mood/logs/{id}` | Delete my mood log | Yes |
| `GET` | `/mood/stats` | Mood statistics: trend, distribution, streak, top labels | Yes |
| `GET` | `/journal/entries` | List my journal entries | Yes |
| `POST` | `/journal/entries` | Create entry | Yes |
| `GET` | `/journal/entries/{id}` | Entry detail | Yes |
| `PUT` | `/journal/entries/{id}` | Update entry (content change clears stored AI insight) | Yes |
| `DELETE` | `/journal/entries/{id}` | Delete entry | Yes |
| `POST` | `/journal/entries/{id}/analyze` | One-shot AI reflection → `ai_insight` (re-runnable) | Yes |
| `POST` | `/chat/sessions` | Create chat session | Yes |
| `GET` | `/chat/sessions` | List my sessions (paginated) | Yes |
| `GET` | `/chat/sessions/{id}` | Session detail with all messages | Yes |
| `DELETE` | `/chat/sessions/{id}` | Delete session + messages | Yes |
| `POST` | `/chat/sessions/{id}/messages` | Send message → full AI reply (multi-turn) | Yes |
| `POST` | `/chat/sessions/{id}/messages/stream` | Same, streamed as SSE (`meta/model/delta/crisis/done/error`) | Yes |
| `GET` | `/topics` | List published encyclopedia topics (filter category, search) | Yes |
| `GET` | `/topics/{slug}` | Topic detail | Yes |
| `GET` | `/discover/recommendations` | Personal rule-based recommendations from mood & journal | Yes |
| `GET` | `/content` | Browse published content library (filter type/topic/search) | Yes |
| `POST` | `/ai/test` | AI gateway end-to-end check (guardrails + fallback + logging) | Yes |
| `POST` | `/admin/uploads/image` | Upload image → `/media/uploads/<file>` path | Admin |
| `POST` | `/admin/topics` | Create encyclopedia topic | Admin |
| `PATCH` | `/admin/topics/{slug}` | Update topic | Admin |
| `DELETE` | `/admin/topics/{slug}` | Delete topic | Admin |
| `POST` | `/admin/content` | Create content item | Admin |
| `PATCH` | `/admin/content/{slug}` | Update content item | Admin |
| `DELETE` | `/admin/content/{slug}` | Delete content item | Admin |

---

## AI Usage & Safety

This section describes only what is implemented in `app/services/`.

### Gateway

All LLM traffic goes through one gateway (`ai/router.py`) on top of **OpenRouter** (OpenAI-compatible protocol). One API key accesses multiple **free-tier** models; a default model is tried first, and on rate-limit (429), timeout, or provider error the gateway falls back through `AI_MODEL_FALLBACKS` in order. Invalid API key (401/402) fails fast — no pointless fallback. Streaming requests fall back between models only *before* the first token is emitted.

### Guardrails (in call order)

1. **Crisis detection — input.** Keyword-based detection of high-risk expressions (Indonesian slang-aware: normalization collapses letter repeats like "matiii", maps slang like "gk/nggak", strips clitics). Three matching modes: token-exact, compact ("bunuhdiri" as one token), and typo-tolerant fuzzy matching around anchors. Contextual negation suppresses literal denials ("aku gak mau bunuh diri") while dual-meaning distress phrases ("gak kuat hidup") stay flagged; device contexts neutralize ambiguity ("hp aku mau mati"). Deliberately biased toward safety: false positives are cheaper than false negatives here.
2. **Scope enforcement — chat only.** Requests outside reflection scope (coding help, homework, prompt injection attempts) are rejected *before* any LLM call — saving quota. Moderately tuned: technical words mentioned inside a personal story are not rejected. Crisis detection runs first, so distress always wins over off-topic.
3. **LLM call** with fallback chain.
4. **Crisis detection — output.** Model output is re-scanned before delivery; during streaming an incremental scan runs over a sliding window of the latest text, and a hit discards the partial reply and switches to the standard support message.
5. **Disclaimer layer.** Every user-facing AI response (chat and journal analysis) is forced through `apply_disclaimer()` — e.g. chat answers end with a reminder that this is a reflection companion, not a substitute for a psychologist or psychiatrist.

### Crisis path (Temukan support redirect)

When a crisis signal is detected on input or output, the system **does not** generate a normal AI reply. Instead the user receives a fixed, warm support message pointing to **SEJIWA 119 ext. 8** (Indonesia's Ministry of Health 24-hour free service) and to trusted adults (family, school counselor). The affected session/message/entry is flagged (`crisis_flagged = true`) for auditability.

### Grounding (RAG)

Before LLM calls, the gateway retrieves published encyclopedia topics and library content matching the user's message — lexically by explicit mentions (name/slug/alternative names), and semantically (when `GEMINI_API_KEY` is set) by embedding the query and comparing cosine similarity against stored vectors. Retrieved snippets are added to the system prompt with explicit rules: reference material may enrich understanding but never produce a diagnosis. If embeddings fail or no key is set, retrieval silently degrades to lexical-only.

### Usage metering (`ai_usage_log`)

Every single attempt — success or failure — is recorded as one row: endpoint type, requested/used model, success flag, error type (`rate_limit`, `timeout`, `provider_error`, `auth_error`, `crisis_input_detected`, `crisis_output_detected`, `offtopic_input_detected`), latency, input/output tokens, finish reason, and triggering user (nullable). Logging runs in its **own DB session**, so a logging failure can never disrupt the user flow. One row per *attempt* (not per request) makes per-model rate-limit patterns visible.

### System prompt boundaries

The chatbot's system prompt (`ai/prompts/chat_prompt.py`) fixes its role: warm Indonesian reflection companion for ages 15–23; validates feelings before advising; short conversational answers; **never diagnoses or prescribes**; refuses out-of-scope requests; ignores embedded instruction-override attempts; and switches to urgent-support behavior on danger signs. Journal analysis is one-shot with a fixed three-part format (reflection, two introspective questions, one small step) and the same non-diagnostic rules.

### Explicit limits

- Crisis detection is keyword/heuristic-based, not clinical — it is a safety net, not a risk assessment.
- Free-tier models can rate-limit; the fallback chain mitigates but does not eliminate unavailability (endpoints then return `503` with the user's message already saved).
- Nothing here is medical advice; the product's own disclaimers state this on every AI response.

---

## Privacy & Security

**Implemented (verified in code):**

- **Ownership isolation:** every journal/mood/chat query filters by `user_id`; foreign IDs return `404` (same as nonexistent — anti-enumeration).
- **Passwords:** bcrypt cost 12, hashed directly (no passlib), 72-byte input limit enforced; passwords never returned by any endpoint.
- **Tokens:** JWT HS256, configurable expiry (default 7 days), verified on every protected request; inactive accounts rejected.
- **Explicit consent:** registration records `consent_version` + `consent_accepted_at`.
- **Data rights:** `GET /me/export` downloads everything (profile, journal, mood, chats) as JSON; `DELETE /account` requires the current password and hard-deletes the account with cascading cleanup.
- **Admin control:** admin endpoints gated by an `ADMIN_EMAILS` allowlist; empty list = no admins, always `403`.
- **Login hardening:** identical generic error for wrong email and wrong password.
- **Uploads:** MIME allowlist + real content-type check, 5 MB cap, UUID filenames (no client-provided paths).
- **Data retention:** user-initiated hard delete everywhere; no soft-delete copies of journal/chat content.

**Honest limitations (not yet implemented):**

- The JWT is returned in the login response body and sent via `Authorization` header — **not** stored in an httpOnly cookie by the backend, so token storage depends on the frontend implementation.
- No rate limiting / brute-force protection on auth endpoints yet.
- No token refresh or revocation mechanism; a leaked token is valid until expiry.
- No audit trail for admin content actions beyond basic logging.
- Secrets live in `.env`; no external secrets manager.
- Chat/journal data is stored in plaintext in MySQL (no field-level encryption) — acceptable for the current scope, but worth hardening before wide release.

---

## Deployment

Not deployed yet — development runs locally with `uvicorn --reload`. The intended plan:

| Target | Notes |
|---|---|
| **VPS (primary candidate)** | `uvicorn` behind Nginx reverse proxy; set `ENVIRONMENT=production`, rotate `JWT_SECRET`, restrict `CORS_ORIGINS` to the production domain, enable HTTPS |
| **Railway** | Managed MySQL + containerized FastAPI; `DATABASE_URL` from platform env vars |
| **Vercel** | Hosts the **frontend** repo (Next.js PWA); the FastAPI backend lives on VPS/Railway and is consumed via `CORS_ORIGINS` |

Production checklist derived from the config code:

1. Generate a fresh `JWT_SECRET` (`secrets.token_urlsafe(48)`).
2. Set `ENVIRONMENT=production` (disables SQL echo logging).
3. Point `CORS_ORIGINS` at the deployed frontend origin only.
4. Run `alembic upgrade head` on the production database.
5. Configure `ADMIN_EMAILS` and create the admin account via `scripts/create_admin.py`.
6. Provide `OPENROUTER_API_KEY` (and optionally `GEMINI_API_KEY` for semantic RAG).

<!-- TODO: add actual deployment steps/URLs once the first deployment exists -->

---

## Roadmap

Realistic next steps based on explicit TODOs and staged design in the codebase:

- [ ] First deployment (VPS or Railway) + production hardening checklist above.
- [ ] Prompt versioning: move long prompt texts into separate `.md` files (`prompts/__init__.py` TODO).
- [ ] Continue evaluating and tuning the chat/journal system prompts (marked "early version" in code).
- [ ] Token usage review dashboard built on `ai_usage_log` (data is already collected per attempt).
- [ ] Frontend features in the [separate repo](https://github.com/KokoroShina/Ruang_Kita_FrontEnd): onboarding self-check flow, crisis-path UI.

<!-- TODO: confirm roadmap items with project owner before publishing -->

---

## Contributing & License

This project was built as a product portfolio piece. Contribution guidelines have not been formalized yet — feel free to open an issue for feedback or suggestions.

**License:** none declared yet. `<!-- TODO: add LICENSE file before publishing -->`

---

## Author / Contact

Built and maintained by **Kokoro Shina**.

- GitHub: [@KokoroShina](https://github.com/KokoroShina)
- Email: `<!-- TODO: add contact email -->`
- Portfolio/LinkedIn: `<!-- TODO: add link -->`

---

<div align="center">
<sub>Ruang Kita is a support tool, not a medical service. If you are in crisis, contact a professional or a crisis line such as SEJIWA 119 ext. 8 (Indonesia, free, 24 hours).</sub>
</div>
