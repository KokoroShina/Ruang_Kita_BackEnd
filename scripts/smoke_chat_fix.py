"""Smoke test perbaikan chatbot: krisis input -> balasan dukungan tanpa AI.

Jalankan saat server dev hidup (default http://localhost:8001).
- Kirim "aku pingin mati" (streaming) -> harus dapat balasan dukungan SEJIWA,
  TANPA event "model" (artinya AI tidak dipanggil).
- Kirim "aku bahagia" (streaming) -> alur normal: model -> delta... -> done.
"""

import json
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"


def read_sse(resp: httpx.Response):
    """Parse SSE sederhana: yield (event, data_dict)."""
    event = None
    for line in resp.iter_lines():
        line = line.strip()
        if not line:
            event = None
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event:
            raw = line[5:].strip()
            try:
                yield event, json.loads(raw)
            except ValueError:
                yield event, {"raw": raw}


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=120)
    email = f"smoke_{uuid.uuid4().hex[:10]}@example.com"
    password = "SmokeTest#2026!"

    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Smoke Tester"},
    )
    r.raise_for_status()

    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ---- Kasus 1: kata krisis ------------------------------------------------
    r = client.post("/api/v1/chat/sessions", headers=headers, json={})
    r.raise_for_status()
    sid = r.json()["id"]

    print("=" * 60)
    print('KASUS 1: "aku pingin mati" (harus balasan dukungan, TANPA AI)')
    print("=" * 60)
    events1 = []
    with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/messages/stream",
        headers=headers,
        json={"content": "aku pingin mati"},
    ) as resp:
        for ev, data in read_sse(resp):
            events1.append((ev, data))
            if ev == "delta":
                print(f"[delta] {data['text'][:80]}", end="")
            else:
                print(f"\n[{ev}] {json.dumps(data, ensure_ascii=False)[:200]}")

    ok_crisis = (
        any(e == "done" and d.get("crisis_detected") for e, d in events1)
        and not any(e == "model" for e, _ in events1)
        and any("119" in d.get("text", "") for e, d in events1 if e == "delta")
    )
    print(f"\n>>> HASIL KRISIS: {'LULUS ✅' if ok_crisis else 'GAGAL ❌'}")

    # ---- Kasus 2: pesan positif ---------------------------------------------
    r = client.post("/api/v1/chat/sessions", headers=headers, json={})
    r.raise_for_status()
    sid2 = r.json()["id"]

    print()
    print("=" * 60)
    print('"aku bahagia" (harus alur normal dengan AI)')
    print("=" * 60)
    events2 = []
    with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid2}/messages/stream",
        headers=headers,
        json={"content": "aku bahagia"},
    ) as resp:
        for ev, data in read_sse(resp):
            events2.append((ev, data))
            if ev == "delta":
                print(f"[delta] {data['text'][:60]}", end="")
            elif ev == "model":
                print(f"[model] {data}")
            else:
                print(f"\n[{ev}] {json.dumps(data, ensure_ascii=False)[:200]}")

    has_model = any(ev == "model" for ev, _ in events2)
    done_ok = any(
        ev == "done" and d.get("crisis_detected") is False and d.get("assistant_message_id")
        for _, d in events2
    )
    print(f"\n\n>>> HASIL NORMAL: {'LULUS ✅' if (has_model and done_ok) else 'GAGAL ❌'}")

    return 0 if (ok_crisis and has_model and done_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
