"""Read NEAR Hunt data straight from NEAR mainnet (FastData KV), never from nearhunt.xyz.

Every row lives in the `nearhunt.near` namespace:
  project/{id}        written by nearhunt.near only (others are spoofs and are dropped)
  vote/{id}           written by the voter; {} = active, null = withdrawn
  comment/{id}/{ms}   written by the commenter; null = deleted
  maker/{id}          written by a project contact after a GitHub check on nearhunt.xyz

Set TRUEHUNT_FIXTURE=path/to/snapshot.json to run offline from a saved snapshot.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import httpx

KV_HOST = os.environ.get("FASTNEAR_KV_HOST", "https://kv.main.fastnear.com")
NAMESPACE = "nearhunt.near"
CACHE_TTL = int(os.environ.get("TRUEHUNT_CACHE_TTL", "120"))


@dataclass
class Snapshot:
    projects: dict[str, dict]                     # submission_id -> record
    votes: list[dict]                             # {voter, project_id, block_height}
    comments: list[dict]                          # {author, project_id, text, block_height}
    makers: list[dict]                            # {account, project_id}
    fetched_at: float = field(default_factory=time.time)
    source: str = "mainnet"


def _read_latest(client: httpx.Client, key_prefix: str, writer: str | None = None) -> list[dict]:
    url = f"{KV_HOST}/v0/latest/{NAMESPACE}" + (f"/{writer}" if writer else "")
    headers = {"content-type": "application/json"}
    if os.environ.get("FASTNEAR_API_KEY"):
        headers["authorization"] = f"Bearer {os.environ['FASTNEAR_API_KEY']}"
    rows: list[dict] = []
    token = None
    while True:
        body = {"key_prefix": key_prefix, "limit": 200}
        if token:
            body["page_token"] = token
        r = client.post(url, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get("entries") or [])
        token = data.get("page_token")
        if not token:
            break
    if writer:
        rows = [e for e in rows if e.get("predecessor_id") == writer]
    return rows


def _id_from_key(key: str, prefix: str) -> str:
    return key[len(prefix):].split("/", 1)[0]


def snapshot_from_rows(project_rows, vote_rows, comment_rows, maker_rows, source="mainnet") -> Snapshot:
    projects = {}
    for e in project_rows:
        if e.get("predecessor_id") != NAMESPACE or not isinstance(e.get("value"), dict):
            continue
        pid = _id_from_key(e["key"], "project/")
        rec = dict(e["value"])
        rec["submission_id"] = pid
        rec["block_height"] = e.get("block_height")
        projects[pid] = rec
    votes = [
        {"voter": e["predecessor_id"], "project_id": _id_from_key(e["key"], "vote/"),
         "block_height": e.get("block_height")}
        for e in vote_rows
        if isinstance(e.get("value"), dict) and _id_from_key(e["key"], "vote/") in projects
    ]
    comments = [
        {"author": e["predecessor_id"], "project_id": _id_from_key(e["key"], "comment/"),
         "text": (e["value"] or {}).get("text", ""), "block_height": e.get("block_height")}
        for e in comment_rows
        if isinstance(e.get("value"), dict) and _id_from_key(e["key"], "comment/") in projects
    ]
    makers = [
        {"account": e["predecessor_id"], "project_id": _id_from_key(e["key"], "maker/")}
        for e in maker_rows
        if isinstance(e.get("value"), dict) and _id_from_key(e["key"], "maker/") in projects
    ]
    return Snapshot(projects, votes, comments, makers, source=source)


def fetch_snapshot() -> Snapshot:
    with httpx.Client(timeout=20) as c:
        return snapshot_from_rows(
            _read_latest(c, "project/", writer=NAMESPACE),
            _read_latest(c, "vote/"),
            _read_latest(c, "comment/"),
            _read_latest(c, "maker/"),
        )


def load_fixture(path: str) -> Snapshot:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return snapshot_from_rows(raw["projects"], raw["votes"], raw.get("comments", []),
                              raw.get("makers", []), source=f"fixture:{os.path.basename(path)}")


_cache: dict = {"snap": None, "at": 0.0}


def get_snapshot() -> Snapshot:
    fixture = os.environ.get("TRUEHUNT_FIXTURE")
    if fixture:
        if _cache["snap"] is None:
            _cache["snap"] = load_fixture(fixture)
        return _cache["snap"]
    if _cache["snap"] is None or time.time() - _cache["at"] > CACHE_TTL:
        try:
            _cache["snap"] = fetch_snapshot()
            _cache["at"] = time.time()
        except Exception:
            if _cache["snap"] is None:
                raise
    return _cache["snap"]
