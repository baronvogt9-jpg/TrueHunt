from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from . import review as ai
from .data import get_snapshot
from .scoring import REASONS, WEIGHTS, leaderboard, score, summary

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app = FastAPI(title="TrueHunt", description="Honest leaderboard for NEAR Hackathon projects")

KIND_LABEL = {
    "independent": "independent", "maker": "maker", "insider": "insider",
    "duplicate": "duplicate", "ring": "ring", "throwaway": "throwaway",
}


def _scored():
    snap = get_snapshot()
    return snap, score(snap)


def _project_json(p, rank_honest=None, rank_raw=None):
    r = p.record
    return {
        "id": p.pid,
        "name": r.get("name"),
        "tracks": r.get("tracks") or [],
        "raw_votes": p.raw,
        "honest_votes": p.honest,
        "lost": p.lost,
        "self_share": round(p.self_share, 2),
        "rank_honest": rank_honest,
        "rank_raw": rank_raw,
        "comments": p.comments,
        "repository_url": r.get("repository_url"),
        "demo_url": r.get("demo_url"),
        "nearhunt_url": f"https://nearhunt.xyz/p/{p.pid}",
        "votes": [
            {"account": v.voter, "kind": v.kind, "weight": v.weight, "reason": v.reason,
             "block_height": v.block_height}
            for v in p.votes
        ],
    }


def _ranks(scored):
    honest = leaderboard(scored, "honest")
    raw = leaderboard(scored, "raw")
    rh = {p.pid: i + 1 for i, p in enumerate(honest)}
    rr = {p.pid: i + 1 for i, p in enumerate(raw)}
    return honest, raw, rh, rr


@app.get("/", response_class=HTMLResponse)
def index(request: Request, sort: str = "honest", track: str = "", q: str = "", all: int = 0):
    snap, scored = _scored()
    honest, raw, rh, rr = _ranks(scored)
    rows = raw if sort == "raw" else honest
    if track:
        rows = [p for p in rows if track in (p.record.get("tracks") or [])]
    if q:
        ql = q.lower()
        rows = [p for p in rows if ql in (p.record.get("name") or "").lower()
                or ql in (p.record.get("description") or "").lower()]
    if not all and not q:
        rows = [p for p in rows if p.raw] or rows[:50]
    tracks = sorted({t for p in scored.values() for t in (p.record.get("tracks") or [])})
    # Biggest movers: projects whose rank changes most between raw and honest.
    movers = sorted((p for p in scored.values() if p.raw),
                    key=lambda p: -(abs(rh[p.pid] - rr[p.pid]) + p.lost))[:3]
    return templates.TemplateResponse(request, "index.html", {
        "rows": rows, "rh": rh, "rr": rr, "sort": sort, "track": track, "q": q, "all": all,
        "tracks": tracks, "stats": summary(scored), "snap": snap, "movers": movers,
    })


@app.get("/p/{pid}", response_class=HTMLResponse)
def project(request: Request, pid: str):
    snap, scored = _scored()
    if pid not in scored:
        raise HTTPException(404, "No such project")
    honest, raw, rh, rr = _ranks(scored)
    p = scored[pid]
    return templates.TemplateResponse(request, "project.html", {
        "p": p, "r": p.record, "rank_h": rh[pid], "rank_r": rr[pid], "total": len(scored),
        "ai_on": ai.available(), "snap": snap,
    })


@app.get("/method", response_class=HTMLResponse)
def method(request: Request):
    return templates.TemplateResponse(request, "method.html", {"weights": WEIGHTS, "reasons": REASONS})


# ---------- JSON API (read-only, CORS open) ----------

def _cors(data, status=200):
    return JSONResponse(data, status_code=status, headers={"access-control-allow-origin": "*"})


@app.get("/api/leaderboard")
def api_leaderboard(sort: str = "honest", limit: int = 50, track: str = ""):
    if sort not in ("honest", "raw"):
        raise HTTPException(400, "sort must be honest or raw")
    snap, scored = _scored()
    honest, raw, rh, rr = _ranks(scored)
    rows = raw if sort == "raw" else honest
    if track:
        rows = [p for p in rows if track in (p.record.get("tracks") or [])]
    limit = max(1, min(limit, 200))
    return _cors({
        "items": [_project_json(p, rh[p.pid], rr[p.pid]) for p in rows[:limit]],
        "meta": {**summary(scored), "source": snap.source, "fetched_at": snap.fetched_at,
                 "weights": WEIGHTS},
    })


@app.get("/api/projects/{pid}")
def api_project(pid: str):
    snap, scored = _scored()
    if pid not in scored:
        return _cors({"error": "not_found"}, 404)
    _, _, rh, rr = _ranks(scored)
    return _cors(_project_json(scored[pid], rh[pid], rr[pid]))


@app.post("/api/projects/{pid}/review")
def api_review(pid: str):
    snap, scored = _scored()
    if pid not in scored:
        return _cors({"error": "not_found"}, 404)
    return _cors(ai.review(pid, scored[pid].record))


@app.get("/api/stats")
def api_stats():
    snap, scored = _scored()
    return _cors({**summary(scored), "source": snap.source, "fetched_at": snap.fetched_at})


@app.get("/SKILL.md", response_class=PlainTextResponse)
def skill():
    return (BASE / "static" / "SKILL.md").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"ok": True}
