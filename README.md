# TrueHunt

**The NEAR Hackathon leaderboard, with self-votes, sock puppets and vote rings weighed out.**

Built for the [NEAR Hackathon](https://nearhackathon.com) (1–14 Nov 2026). Tracks: Open, Social Money.

[NEAR Hunt](https://nearhunt.xyz) puts every hackathon project and every upvote on NEAR mainnet
as open records. That is great, and it makes one problem visible: NEAR accounts are free, so the
top of the leaderboard mostly shows which teams mobilised the most accounts. On 12 Nov 2026 the
#1 project had 9 upvotes, and about 6 of them came from the project's own accounts and bare
implicit accounts.

TrueHunt reads the same on-chain data and gives every vote a weight from 0 to 1, with a
one-line reason printed next to it. Nothing is hidden and nothing is written on chain.

| Kind | Weight | When |
|---|---|---|
| maker | 0 | the voter claimed the project as its maker on NEAR Hunt (`maker/` row) |
| insider | 0 | the voter's account name matches the project: name, X handle, GitHub owner/repo, demo domain |
| duplicate | 0 | the same person already voted: `foo.near`, `foo.tg`, `team.foo.near` |
| ring | 0.3 | the voter makes another project, and the two are upvoted together |
| throwaway | 0.3 | auto-generated name (`quietfox2210.near`) or a bare 64-hex implicit account |
| independent | 1 | none of the above |

Plus an optional **"first five seconds"** review: Gemini reads only the public pitch and says
what a newcomer still doesn't get (clarity 1–5, proof 1–5, what's missing, strongest line).

## Run it (one command)

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000, reads NEAR mainnet live
```

No keys needed. Offline, from the bundled snapshot:

```bash
python tests/build_fixture.py tests/snapshot.json   # builds the sample snapshot
TRUEHUNT_FIXTURE=tests/snapshot.json uvicorn app.main:app
pytest -q                            # 13 passed
```

AI reviews switch on when `GEMINI_API_KEY` is set (see `.env.example`).

## API (read-only, CORS open)

```bash
curl -s "http://127.0.0.1:8000/api/leaderboard?sort=honest&limit=5"
curl -s "http://127.0.0.1:8000/api/projects/{submission_id}"     # every vote with kind, weight, reason
curl -s "http://127.0.0.1:8000/api/stats"
curl -s -X POST "http://127.0.0.1:8000/api/projects/{submission_id}/review"
```

Agents: read [`/SKILL.md`](app/static/SKILL.md).

## How it reads the chain

All data comes from FastData KV on NEAR mainnet, namespace `nearhunt.near`
(`https://kv.main.fastnear.com/v0/latest/nearhunt.near`):

- `project/{id}` — accepted only when written by `nearhunt.near` itself (spoofed rows are dropped)
- `vote/{id}` — the voter is the row's `predecessor_id`; `null` = withdrawn, skipped
- `comment/{id}/{ms}` and `maker/{id}` — same convention

Code: [`app/data.py`](app/data.py) (reading), [`app/scoring.py`](app/scoring.py) (the formula),
[`app/review.py`](app/review.py) (AI review), [`app/main.py`](app/main.py) (pages and API).

## Limits, honestly

- The rules are simple on purpose so anyone can check them. They miss an author whose account
  shares nothing with the project, and they can flag an honest friend with an auto-generated name.
- A low score says the votes look like they come from the team's side. It says nothing about the
  project's quality, and it is not the hackathon's official judging.
- Not affiliated with NEAR Hunt.

## Deploy

Vercel (Python runtime): `vercel.json` routes everything to `api/index.py`. Optional env vars in
`.env.example`.

## License

MIT
