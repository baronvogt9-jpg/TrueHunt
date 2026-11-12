"""The honest-vote formula. Every rule is explainable in one sentence and shown next to the vote.

A raw upvote counts 1. An honest upvote counts its weight:

  maker        0.0  the voter claimed the project as its maker on NEAR Hunt (maker/ row)
  insider      0.0  the voter's account name matches the project (name, X handle, GitHub, domain)
  duplicate    0.0  the same person already voted (same root name: foo.near / foo.tg / x.foo.near)
  ring         0.3  a maker of another project, when the two projects are propped up together
                    (its maker votes back, or the same third account upvotes both)
  throwaway    0.3  an auto-generated name (word1234.near) or a bare implicit (64-hex) account
  independent  1.0  none of the above
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .data import Snapshot

WEIGHTS = {"maker": 0.0, "insider": 0.0, "duplicate": 0.0, "ring": 0.3, "throwaway": 0.3, "independent": 1.0}

REASONS = {
    "maker": "claimed this project as its maker",
    "insider": "account name matches the project ({match})",
    "duplicate": "same person already voted as {match}",
    "ring": "maker of {match}; the two projects are upvoted together",
    "throwaway": "auto-generated or bare implicit account",
    "independent": "no link to the project found",
}

# Words too common in hackathon names to prove a link on their own.
STOP = {
    "near", "agent", "agents", "ai", "pay", "protocol", "wallet", "guard", "hack", "hackathon", "the",
    "app", "intents", "intent", "market", "markets", "chain", "onchain", "labs", "lab", "dao", "defi",
    "game", "games", "bot", "bots", "trade", "trading", "copy", "private", "safe", "secure", "money",
    "fund", "swap", "with", "your", "for", "and", "build", "builder", "dev", "team", "official",
    "vercel", "github", "railway", "pages", "netlify", "www", "com", "xyz", "io", "status", "x",
    "twitter", "web", "use", "get", "my", "on", "hq", "net", "org", "page", "site", "demo", "real",
}

GENERATED = re.compile(r"^[a-z]+\d{3,5}\.near$")
IMPLICIT = re.compile(r"^[0-9a-f]{64}$")
ETH_IMPLICIT = re.compile(r"^0x[0-9a-f]{40}$")
MIN_TOKEN = 4


def _clean(word: str) -> str:
    w = word.lower()
    w = re.sub(r"^0x", "", w)
    w = re.sub(r"^\d+", "", w)
    return re.sub(r"[^a-z0-9]", "", w)


def _tokens(text: str) -> set[str]:
    out = set()
    for part in re.split(r"[^A-Za-z0-9]+", text or ""):
        t = _clean(part)
        if len(t) >= MIN_TOKEN and t not in STOP:
            out.add(t)
    return out


def _url_tokens(url: str | None) -> set[str]:
    if not url:
        return set()
    try:
        u = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return set()
    host = (u.hostname or "").lower()
    toks: set[str] = set()
    path = [p for p in u.path.split("/") if p]
    if host.endswith(("x.com", "twitter.com")) and path:
        toks |= _whole(path[0])                     # the X handle
    elif host.endswith("github.com") and path:
        toks |= _whole(path[0])                     # owner
        if len(path) > 1:
            toks |= _whole(path[1]) | _tokens(path[1])
    elif host:
        labels = host.split(".")[:-1]               # drop TLD
        for lab in labels:
            toks |= _whole(lab) | _tokens(lab)
    return toks


def _whole(s: str) -> set[str]:
    t = _clean(s)
    return {t} if len(t) >= MIN_TOKEN and t not in STOP else set()


def project_identity(p: dict) -> set[str]:
    ids = set()
    name = p.get("name") or ""
    ids |= _tokens(name)
    ids |= _whole(name)                              # "Grind District" -> grinddistrict
    for key in ("demo_url", "repository_url", "description_source", "repository_source"):
        ids |= _url_tokens(p.get(key))
    for link in p.get("links") or []:
        if isinstance(link, dict):
            ids |= _url_tokens(link.get("url"))
    return ids


def account_root(account: str) -> str:
    """foo.near, foo.tg, analyst.team.foo.near -> foo."""
    a = account.lower()
    if IMPLICIT.match(a) or ETH_IMPLICIT.match(a):
        return a
    parts = a.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0]


def account_tokens(account: str) -> set[str]:
    a = account.lower()
    if IMPLICIT.match(a) or ETH_IMPLICIT.match(a):
        return set()
    labels = a.split(".")[:-1] or [a]
    toks = set()
    for lab in labels:
        toks |= _whole(lab)
        toks |= _tokens(lab)
    return toks


_STOP_BY_LEN = sorted(STOP, key=len, reverse=True)


def _distinctive(token: str) -> bool:
    """True when something meaningful is left after removing common words: "nearagent" is not."""
    rest = token
    for w in _STOP_BY_LEN:
        if len(w) >= 3:
            rest = rest.replace(w, "")
    return len(re.sub(r"\d", "", rest)) >= MIN_TOKEN


def link_match(account: str, identity: set[str]) -> str | None:
    """Return the token that ties an account to a project, or None."""
    for at in account_tokens(account):
        for pt in identity:
            if not (_distinctive(at) and _distinctive(pt)):
                continue
            if at == pt:
                return pt
            short, long_ = sorted((at, pt), key=len)
            if len(short) >= 5 and short in long_:
                return pt
    return None


def is_throwaway(account: str) -> bool:
    a = account.lower()
    return bool(GENERATED.match(a) or IMPLICIT.match(a))


@dataclass
class ScoredVote:
    voter: str
    kind: str
    weight: float
    reason: str
    block_height: int | None = None


@dataclass
class ScoredProject:
    pid: str
    record: dict
    raw: int = 0
    honest: float = 0.0
    votes: list[ScoredVote] = field(default_factory=list)
    comments: int = 0
    makers: set[str] = field(default_factory=set)

    @property
    def lost(self) -> float:
        return round(self.raw - self.honest, 2)

    @property
    def self_share(self) -> float:
        if not self.raw:
            return 0.0
        return sum(1 for v in self.votes if v.kind in ("maker", "insider", "duplicate")) / self.raw


def score(snap: Snapshot) -> dict[str, ScoredProject]:
    projects = {pid: ScoredProject(pid, rec) for pid, rec in snap.projects.items()}
    identity = {pid: project_identity(rec) for pid, rec in snap.projects.items()}

    # Who is a maker of what: explicit claims plus accounts whose name matches the project.
    makers_of: dict[str, set[str]] = defaultdict(set)
    for m in snap.makers:
        makers_of[m["project_id"]].add(m["account"])
    for v in snap.votes:
        if link_match(v["voter"], identity[v["project_id"]]):
            makers_of[v["project_id"]].add(v["voter"])
    for c in snap.comments:
        if link_match(c["author"], identity[c["project_id"]]):
            makers_of[c["project_id"]].add(c["author"])
    projects_of: dict[str, set[str]] = defaultdict(set)
    for pid, accs in makers_of.items():
        for a in accs:
            projects_of[a].add(pid)
            projects[pid].makers.add(a)

    voted: set[tuple[str, str]] = {(v["voter"], v["project_id"]) for v in snap.votes}
    voters_of: dict[str, set[str]] = defaultdict(set)
    for v in snap.votes:
        voters_of[v["project_id"]].add(v["voter"])

    seen_roots: dict[str, dict[str, str]] = defaultdict(dict)   # pid -> root -> first account
    for v in sorted(snap.votes, key=lambda v: (v.get("block_height") or 0, v["voter"])):
        pid, voter = v["project_id"], v["voter"]
        sp = projects[pid]
        sp.raw += 1
        root = account_root(voter)
        kind, match = "independent", ""

        claimed = {m["account"] for m in snap.makers if m["project_id"] == pid}
        if voter in claimed:
            kind = "maker"
        elif (tok := link_match(voter, identity[pid])):
            kind, match = "insider", tok
        elif root in seen_roots[pid] and not IMPLICIT.match(root):
            kind, match = "duplicate", seen_roots[pid][root]
        else:
            # Ring: the voter makes project q, and q and this project are propped up together,
            # either by this project's maker voting back for q, or by a third account that
            # upvoted both.
            ring_with = [
                q for q in projects_of.get(voter, set())
                if q != pid and (
                    any((m, q) in voted for m in makers_of.get(pid, set()))
                    or any(w != voter and (w, q) in voted for w in voters_of[pid])
                )
            ]
            if ring_with:
                kind, match = "ring", projects[ring_with[0]].record.get("name", ring_with[0])
            elif is_throwaway(voter):
                kind = "throwaway"

        seen_roots[pid].setdefault(root, voter)
        w = WEIGHTS[kind]
        sp.honest += w
        sp.votes.append(ScoredVote(voter, kind, w, REASONS[kind].format(match=match), v.get("block_height")))

    for c in snap.comments:
        projects[c["project_id"]].comments += 1
    for sp in projects.values():
        sp.honest = round(sp.honest, 2)
    return projects


def leaderboard(scored: dict[str, ScoredProject], by: str = "honest") -> list[ScoredProject]:
    if by == "raw":
        key = lambda p: (-p.raw, -p.honest, (p.record.get("name") or "").lower())
    else:
        key = lambda p: (-p.honest, -p.raw, (p.record.get("name") or "").lower())
    return sorted(scored.values(), key=key)


def summary(scored: dict[str, ScoredProject]) -> dict:
    votes = [v for p in scored.values() for v in p.votes]
    by_kind = defaultdict(int)
    for v in votes:
        by_kind[v.kind] += 1
    return {
        "projects": len(scored),
        "with_votes": sum(1 for p in scored.values() if p.raw),
        "raw_votes": len(votes),
        "honest_votes": round(sum(v.weight for v in votes), 2),
        "voters": len({v.voter for v in votes}),
        "by_kind": dict(by_kind),
    }
