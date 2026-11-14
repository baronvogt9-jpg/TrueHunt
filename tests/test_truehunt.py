import os
from pathlib import Path

import pytest

FIXTURE = str(Path(__file__).parent / "snapshot.json")
os.environ["TRUEHUNT_FIXTURE"] = FIXTURE
os.environ.pop("GEMINI_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.data import load_fixture  # noqa: E402
from app.main import app  # noqa: E402
from app.scoring import account_root, is_throwaway, link_match, project_identity, score  # noqa: E402

ID = {k: f"00000000-0000-4000-8000-{i:012d}" for i, k in enumerate(
    ["nova", "yawrd", "portal", "nims", "safe", "crown", "skarbnik", "crucible", "settle",
     "ballast", "heir"], 1)}


@pytest.fixture(scope="module")
def scored():
    return score(load_fixture(FIXTURE))


def kinds(scored, key):
    return {v.voter: v.kind for v in scored[ID[key]].votes}


def test_spoofed_project_and_withdrawn_vote_are_ignored(scored):
    assert "ffffffff-0000-4000-8000-000000000000" not in scored
    assert "zahrah.near" not in kinds(scored, "heir")


def test_project_accounts_are_insiders(scored):
    k = kinds(scored, "nova")
    assert k["nova-sdk.near"] == "insider" and k["nova-accountant.near"] == "insider"
    assert kinds(scored, "yawrd")["keelbase.near"] == "insider"          # the demo's domain
    assert kinds(scored, "nims")["nims-game.near"] == "insider"


def test_x_handle_with_0x_prefix_matches(scored):
    assert kinds(scored, "portal")["038unholy.near"] == "insider"        # X handle 0xunholy


def test_claimed_maker(scored):
    assert kinds(scored, "ballast")["ollie.near"] == "maker"


def test_same_person_twice_is_duplicate(scored):
    assert kinds(scored, "safe")["poppingbean.tg"] == "duplicate"
    assert kinds(scored, "crown")["analyst.team.useparallax.near"] == "duplicate"


def test_generated_and_implicit_are_throwaway(scored):
    k = kinds(scored, "nims")
    assert k["fatseal5191.near"] == "throwaway"
    assert sum(1 for v in k.values() if v == "throwaway") == 4
    assert is_throwaway("a" * 64) and not is_throwaway("alejandro.near")


def test_vote_ring(scored):
    k = kinds(scored, "settle")
    assert k["pgreyy.near"] == "ring" and k["ofalamin.near"] == "ring"
    assert k["client47.near"] == "independent"


def test_independent_reviewer_counts_fully(scored):
    assert kinds(scored, "heir")["alejandro.near"] == "independent"
    assert scored[ID["heir"]].honest == 1.0


def test_common_words_never_link():
    ident = project_identity({"name": "NEAR Agent Pay", "demo_url": "https://x.com/someone/status/1"})
    assert link_match("near-agent.near", ident) is None
    assert link_match("pay.near", ident) is None


def test_account_root():
    assert account_root("analyst.team.useparallax.near") == "useparallax"
    assert account_root("poppingbean.tg") == "poppingbean"


def test_honest_reorders_the_top(scored):
    nova, nims = scored[ID["nova"]], scored[ID["nims"]]
    assert nova.raw == 9 and nova.honest < 5
    assert nims.self_share == pytest.approx(0.2)
    assert nims.honest < 2


client = TestClient(app)


def test_pages_render():
    r = client.get("/")
    assert r.status_code == 200 and "worth counting" in r.text and "NOVA Copy-Trading" in r.text
    assert client.get("/?sort=raw&track=games").status_code == 200
    assert client.get("/?all=1&q=heir").status_code == 200
    r = client.get(f"/p/{ID['nova']}")
    assert r.status_code == 200 and "nova-sdk.near" in r.text and "insider" in r.text
    assert client.get("/method").status_code == 200
    assert client.get("/p/nope").status_code == 404


def test_api():
    j = client.get("/api/leaderboard?limit=3").json()
    assert len(j["items"]) == 3 and j["meta"]["source"].startswith("fixture")
    assert j["items"][0]["honest_votes"] >= j["items"][1]["honest_votes"]
    p = client.get(f"/api/projects/{ID['settle']}").json()
    assert {v["kind"] for v in p["votes"]} == {"ring", "independent"}
    assert client.get("/api/leaderboard?sort=bad").status_code == 400
    assert client.post(f"/api/projects/{ID['heir']}/review").json()["error"].startswith("AI reviews are off")
    assert "truehunt" in client.get("/SKILL.md").text
