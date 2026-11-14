"""Build tests/fixtures snapshot.json: a small, illustrative slice shaped like the 12 Nov 2026
mainnet data (patterns from the real snapshot, most voter names replaced by placeholders)."""
import json, hashlib, sys

def hexacc(seed): return hashlib.sha256(seed.encode()).hexdigest()

P = {
 "nova": dict(name="NOVA Copy-Trading", tracks=["privacy","security","agents"],
              demo_url="https://x.com/jcarbonnell/status/2118274901693837481",
              repository_url="https://github.com/jcarbonnell/nova-copy-trading",
              links=[{"url":"https://nova-sdk.com/llms.txt"}],
              description="Confidential copy-trading for AI agents, live on NEAR mainnet."),
 "yawrd": dict(name="Yawrd", tracks=["business","agents","social"],
              demo_url="https://x.com/vandigital/status/2120130304233165286",
              repository_url="https://github.com/vandigital/yawrd",
              links=[{"url":"https://yawrd.keelbase.io"}],
              description="A shared project space for people and their AI agents."),
 "portal": dict(name="NEARPORTAL", tracks=["agents","realworld"],
              demo_url="https://x.com/0xunholy/status/2118484384340684976",
              links=[{"url":"https://nearportal.com"}],
              description="Your AI is idle. Someone else's backlog isn't."),
 "nims": dict(name="Nims", tracks=["games"],
              demo_url="https://x.com/marrnueldev/status/2120169484673486926",
              links=[{"url":"https://nims-app.up.railway.app"}],
              description="A market town where every trader is an AI agent with its own wallet."),
 "safe": dict(name="Safe Near", tracks=["security"],
              demo_url="https://x.com/Raphael_Hoang/status/2118583687944269929",
              description="A security gate for AI agents that pay."),
 "crown": dict(name="Crownfall", tracks=["games","memecoins"],
              demo_url="https://x.com/neromtoobad/status/2119855648150339694",
              description="A 3D medieval game where eight houses compete for one throne."),
 "skarbnik": dict(name="Skarbnik", tracks=["privacy","security","agents"],
              demo_url="https://x.com/pgreyy/status/2118237758321795364",
              repository_url="https://github.com/pgreyy/skarbnik",
              description="Private repair bounties for AI agents."),
 "crucible": dict(name="Crucible", tracks=["security","games"],
              demo_url="https://x.com/ofalamin/status/2119482584753418265",
              repository_url="https://github.com/1momoh/crucible",
              description="Can you con an AI guard in 3 messages?"),
 "settle": dict(name="SETTLENEAR", tracks=["defi","agents"],
              demo_url="https://x.com/folarihn/status/2119153070051295422",
              repository_url="https://github.com/folarihn/settle",
              links=[{"url":"https://settlenear.xyz"}],
              description="Escrow, work verification and payment for humans and AI agents."),
 "ballast": dict(name="Ballast", tracks=["defi","agents"],
              demo_url="https://x.com/olliechapman/status/2118541780178334141",
              repository_url="https://github.com/olliechap/near-ballast",
              description="An agent that auto-balances your staked NEAR between AI credits and yield."),
 "heir": dict(name="Heir", tracks=["realworld","open"],
              demo_url="https://x.com/peter_obisi/status/2119013176310427661",
              repository_url="https://github.com/ZSP111/Heir",
              description="A will for your crypto that carries itself out."),
}
ID = {k: f"00000000-0000-4000-8000-{i:012d}" for i, k in enumerate(P, 1)}

V = {
 "nova": ["nova-sdk.near","nova-accountant.near",hexacc("n1"),hexacc("n2"),hexacc("n3"),hexacc("n4"),
          "reviewer-a.near","reviewer-b.near","reviewer-c.near"],
 "yawrd": ["yawrd.near","keelbase.near","vandal.near","reviewer-d.near","reviewer-e.near","reviewer-f.near","reviewer-g.near"],
 "portal": ["038unholy.near","nambk.near","mehdibendo.near",hexacc("p1"),"reviewer-h.near","reviewer-i.near"],
 "nims": ["nims-game.near","fatseal5191.near","simplevilla3287.near","equalward1454.near","quietfox2210.near"],
 "safe": ["poppingbean.near","poppingbean.tg","reviewer-j.near","reviewer-k.near","reviewer-l.near"],
 "crown": ["useparallax.near","analyst.team.useparallax.near","nambk.near"],
 "skarbnik": ["pgreyy.near","client47.near","reviewer-m.near"],
 "crucible": ["ofalamin.near","client47.near"],
 "settle": ["pgreyy.near","ofalamin.near","client47.near"],
 "ballast": ["ollie.near","alejandro.near","reviewer-n.near"],
 "heir": ["alejandro.near"],
}
rows = {"projects": [], "votes": [], "comments": [], "makers": []}
h = 223600000
for k, rec in P.items():
    rows["projects"].append({"predecessor_id":"nearhunt.near","key":f"project/{ID[k]}","block_height":h,
        "value": {"schema":"nearhunt/project/1","id":f"nearhackathon-2026:{ID[k]}",**rec}}); h += 1
for k, voters in V.items():
    for a in voters:
        rows["votes"].append({"predecessor_id":a,"key":f"vote/{ID[k]}","block_height":h,"value":{}}); h += 1
# a withdrawn vote and a spoofed project row, both must be ignored
rows["votes"].append({"predecessor_id":"zahrah.near","key":f"vote/{ID['heir']}","block_height":h,"value":None})
rows["projects"].append({"predecessor_id":"spoofer.near","key":"project/ffffffff-0000-4000-8000-000000000000",
    "block_height":h,"value":{"name":"Fake"}})
rows["makers"].append({"predecessor_id":"ollie.near","key":f"maker/{ID['ballast']}","value":{"code":"0"*32}})
rows["comments"] += [
 {"predecessor_id":"alejandro.near","key":f"comment/{ID['heir']}/1","value":{"text":"Love the dead man's switch idea."}},
 {"predecessor_id":"nims-game.near","key":f"comment/{ID['nims']}/2","value":{"text":"wary is one term of the price formula."}},
]
json.dump(rows, open(sys.argv[1], "w"), separators=(",", ":"))
print(ID)
