---
name: truehunt
description: Read the NEAR Hackathon leaderboard with each upvote weighed by who cast it (self-votes, sock puppets, vote rings). Read-only JSON, no key.
---

# TrueHunt: agent guide

TrueHunt re-scores NEAR Hunt's on-chain upvotes (`nearhunt.near`, FastData KV on NEAR mainnet).
Every vote gets a weight from 0 to 1 and a one-line reason. Read-only: there are no write routes.

| I want to… | Call |
|---|---|
| Honest leaderboard | `GET /api/leaderboard?sort=honest&limit=50` |
| Raw leaderboard (same as NEAR Hunt) | `GET /api/leaderboard?sort=raw` |
| One track | `GET /api/leaderboard?track=games` |
| One project with every weighed vote | `GET /api/projects/{submission_id}` |
| Totals | `GET /api/stats` |
| AI "first five seconds" review of a pitch | `POST /api/projects/{submission_id}/review` |

Each project: `raw_votes`, `honest_votes`, `lost`, `self_share` (share of votes from its own side),
`rank_honest`, `rank_raw`, and `votes[]` with `account`, `kind`
(`independent|maker|insider|duplicate|ring|throwaway`), `weight`, `reason`.
`meta.weights` holds the formula; `meta.source` says whether data is live mainnet or a fixture.
