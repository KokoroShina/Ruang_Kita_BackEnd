"""Test mood tracker: CRUD, validasi, statistik akurat, ownership."""

from datetime import datetime, timedelta, timezone


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _seed_week(client, headers, now):
    """7 log: D-5..D-1 backfill + 2 log hari ini. Return list id."""
    plan = [(5, 2, "cemas"), (4, 3, None), (3, 2, "cemas"), (2, 1, "sedih"), (1, 4, "senang")]
    ids = []
    for days_ago, score, label in plan:
        r = await client.post(
            "/api/v1/mood/logs",
            headers=headers,
            json={
                "mood_score": score,
                **({"mood_label": label} if label else {}),
                "logged_at": _iso(now - timedelta(days=days_ago)),
            },
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])
    r = await client.post(
        "/api/v1/mood/logs", headers=headers, json={"mood_score": 4, "mood_label": "senang"}
    )
    ids.append(r.json()["id"])
    r = await client.post(
        "/api/v1/mood/logs", headers=headers, json={"mood_score": 3, "mood_label": "cemas"}
    )
    ids.append(r.json()["id"])
    return ids


async def test_create_log_defaults(client, make_user):
    headers = await make_user("mood1@test.id")
    r = await client.post(
        "/api/v1/mood/logs", headers=headers, json={"mood_score": 3, "mood_label": "biasa aja"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["source"] == "manual"
    assert body["mood_score"] == 3
    assert body["logged_at"]  # terisi otomatis (UTC)


async def test_create_log_validation(client, make_user):
    headers = await make_user("mood2@test.id")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    r = await client.post("/api/v1/mood/logs", headers=headers, json={"mood_score": 0})
    assert r.status_code == 422
    r = await client.post("/api/v1/mood/logs", headers=headers, json={"mood_score": 6})
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/mood/logs",
        headers=headers,
        json={"mood_score": 3, "logged_at": _iso(now + timedelta(days=1))},
    )
    assert r.status_code == 422  # masa depan ditolak


async def test_list_order_limit_and_days_filter(client, make_user):
    headers = await make_user("mood3@test.id")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await _seed_week(client, headers, now)

    r = await client.get("/api/v1/mood/logs", headers=headers)
    logs = r.json()
    assert len(logs) == 7
    logged = [l["logged_at"] for l in logs]
    assert logged == sorted(logged, reverse=True)  # terbaru dulu

    r = await client.get("/api/v1/mood/logs", params={"limit": 2}, headers=headers)
    assert len(r.json()) == 2

    r = await client.get("/api/v1/mood/logs", params={"days": 3}, headers=headers)
    cutoff_date = (now - timedelta(days=3)).date().isoformat()
    assert all(l["logged_at"][:10] >= cutoff_date for l in r.json())


async def test_stats_accurate(client, make_user):
    headers = await make_user("mood4@test.id")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date().isoformat()
    await _seed_week(client, headers, now)

    r = await client.get("/api/v1/mood/stats", params={"days": 30}, headers=headers)
    s = r.json()
    assert s["total_logs"] == 7
    assert abs(s["avg_score"] - round((2 + 3 + 2 + 1 + 4 + 4 + 3) / 7, 2)) < 0.01
    assert s["score_distribution"] == {"1": 1, "2": 2, "3": 2, "4": 2}
    assert s["current_streak_days"] == 6
    assert s["top_labels"][0] == {"label": "cemas", "count": 3}

    trend_days = [p["date"] for p in s["daily_trend"]]
    for i in range(6):
        assert (now.date() - timedelta(days=i)).isoformat() in trend_days
    today_point = next(p for p in s["daily_trend"] if p["date"] == today)
    assert today_point["count"] == 2 and abs(today_point["avg_score"] - 3.5) < 0.01


async def test_stats_empty_user_zero_safe(client, make_user):
    headers = await make_user("mood5@test.id")
    r = await client.get("/api/v1/mood/stats", headers=headers)
    s = r.json()
    assert s["total_logs"] == 0
    assert s["avg_score"] is None
    assert s["current_streak_days"] == 0
    assert s["daily_trend"] == []


async def test_patch_own_log(client, make_user):
    headers = await make_user("mood6@test.id")
    lid = (
        await client.post("/api/v1/mood/logs", headers=headers, json={"mood_score": 2})
    ).json()["id"]

    r = await client.patch(
        f"/api/v1/mood/logs/{lid}", headers=headers, json={"mood_score": 5, "note": "edit"}
    )
    assert r.status_code == 200 and r.json()["mood_score"] == 5

    # patch kosong -> 422
    r = await client.patch(f"/api/v1/mood/logs/{lid}", headers=headers, json={})
    assert r.status_code == 422


async def test_mood_ownership_isolation(client, make_user):
    hA = await make_user("owner@test.id")
    hB = await make_user("lain@test.id")
    lid = (
        await client.post("/api/v1/mood/logs", headers=hA, json={"mood_score": 3})
    ).json()["id"]

    r = await client.patch(f"/api/v1/mood/logs/{lid}", headers=hB, json={"mood_score": 1})
    assert r.status_code == 404
    r = await client.delete(f"/api/v1/mood/logs/{lid}", headers=hB)
    assert r.status_code == 404

    # owner bisa hapus
    r = await client.delete(f"/api/v1/mood/logs/{lid}", headers=hA)
    assert r.status_code == 204
