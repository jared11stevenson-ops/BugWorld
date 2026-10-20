"""Genre pool and selection. A cycle picks three games of different families, scored by how well each genre expresses the universe's dynamics,
with a novelty bonus for genres the studio has not shipped recently (read from persistent knowledge)."""
import random
from . import games as G, tuner

POOL = {
    "concept_campaign": {"family": "strategy", "label": "strategy duel campaign", "affinity": {"signal": 2, "selection": 2, "feedback": 2, "predation": 1, "network": 1, "tipping": 1}},
    "steward": {"family": "simulation", "label": "world-sim stewardship", "affinity": {"network": 2, "symbiosis": 2, "scarcity": 2, "migration": 1, "contagion": 2, "quarantine": 1}},
    "cordon": {"family": "containment", "label": "network containment strategy", "affinity": {"contagion": 4, "quarantine": 4, "purge": 2, "network": 1, "tipping": 1}},
    "volley": {"family": "sport", "label": "3D sports tournament", "affinity": {"rally": 4, "team": 2, "oscillation": 1, "projectile": 1, "resonance": 1}},
    "splash": {"family": "arena", "label": "top-down water-balloon battle", "affinity": {"projectile": 4, "splash": 4, "team": 3, "diffusion": 1, "tipping": 1}},
    "arcade": {"family": "action", "label": "real-time 2D action", "affinity": {"oscillation": 2, "resonance": 2, "erosion": 1, "diffusion": 1, "entropy": 1}},
    "arcade3d": {"family": "action", "label": "real-time 3D action", "affinity": {"purge": 2, "contagion": 1, "tipping": 1, "predation": 1, "migration": 1, "signal": 1}},
}


def choose(uni, know, rnd_seed):
    rnd = random.Random(rnd_seed)
    recent = [g for c in know.get("cycles", [])[-2:] for g in c.get("genres", [])]
    scored = []
    for gid, g in POOL.items():
        s = sum(uni["tags"].get(t, 0) * w for t, w in g["affinity"].items())
        s += 2.0 if gid not in recent else 0.0          # novelty: prefer genres not shipped in the last two cycles
        s += rnd.random() * 0.5
        scored.append((s, gid))
    scored.sort(reverse=True)
    chosen, families = [], set()
    for s, gid in scored:
        if POOL[gid]["family"] not in families and len(chosen) < 3:
            chosen.append(gid); families.add(POOL[gid]["family"])
    return chosen, {gid: round(s, 2) for s, gid in scored}
