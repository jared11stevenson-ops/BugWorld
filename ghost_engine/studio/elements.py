"""Universe elements: the abstract physical/social/ludic building blocks that inspirations are decomposed into. A universe is the FUSION of its
inspirations' elements; game ideas may only use what the universe contains. Each element carries physics (constants that every game of the universe
must honour), a one-line law for the shared codex, and the modules of each game family that it unlocks."""

# element -> {"law": text for the codex, "physics": {constant: value}}
ELEMENTS = {
    "projectile_arc": {"law": "Anything thrown flies in an arc and lands where gravity decides, not where it was aimed.", "physics": {"gravity_scale": 1.0}},
    "burst": {"law": "Soft things burst on impact and release everything they hold over an area.", "physics": {"burst_radius": 1.0}},
    "soak": {"law": "Water clings. Whatever is soaked grows heavy and slow, and dries only with time.", "physics": {"soak_weight": 1.0}},
    "refill": {"law": "Ammunition is never free: it must be fetched from a source and carried.", "physics": {}},
    "friendly_fire": {"law": "Splash does not know friend from foe.", "physics": {}},
    "team": {"law": "Bands of allies act together; their rivals are other bands.", "physics": {}},
    "net": {"law": "A net divides the world in two: bodies cannot cross it, but flying things can go over.", "physics": {}},
    "rally": {"law": "A shared object passes back and forth until someone fails to return it.", "physics": {}},
    "touch_limit": {"law": "Each side may handle the shared object only a few times before it must cross.", "physics": {}},
    "serve": {"law": "Every exchange begins with a deliberate launch by one side.", "physics": {}},
    "bounce": {"law": "Hard surfaces return what strikes them, a little livelier than it came.", "physics": {"restitution_scale": 1.0}},
    "wind": {"law": "The air has moods: gusts push light things off their course.", "physics": {"wind": 0.03}},
    "slick": {"law": "Wet ground is a rumor of footing; momentum is the only honest thing.", "physics": {"slick": 1}},
    "tide": {"law": "The edge of the world rises and falls, taking and giving back ground.", "physics": {}},
    "pulse": {"law": "Everything beats with a rhythm; periodic waves sweep the land.", "physics": {}},
    "wells": {"law": "Heavy places pull wanderers toward them.", "physics": {}},
    "drift": {"law": "A restless current moves all things; standing still has a price.", "physics": {"wind": 0.02}},
    "contagion": {"law": "A state can spread from one body to its neighbours, faster where they gather.", "physics": {}},
    "quarantine": {"law": "Barriers slow spreading, but nothing seals perfectly.", "physics": {}},
    "purge": {"law": "A cleansing line sweeps the world; it destroys the guilty and the innocent alike.", "physics": {}},
    "fog": {"law": "News arrives late; you act on what was true two days ago.", "physics": {}},
    "signal": {"law": "Messages cross distance faster than bodies can.", "physics": {}},
    "network": {"law": "Places are joined by roads; what happens in one place travels along them.", "physics": {}},
    "tipping": {"law": "Slow pressures build until a threshold flips everything at once.", "physics": {}},
    "diffusion": {"law": "Concentrations flatten out; nothing stays where it was put.", "physics": {}},
    "erosion": {"law": "Surfaces wear away; what is held today is thinner tomorrow.", "physics": {}},
    "scarcity": {"law": "There is never quite enough, and the shortage chooses who thrives.", "physics": {}},
    "symbiosis": {"law": "Unlike things can feed each other, and are worse off alone.", "physics": {}},
    "selection": {"law": "Variants compete; what survives is what the world rewards.", "physics": {}},
    "feedback": {"law": "Effects feed their own causes; small pushes grow or die.", "physics": {}},
    "entropy": {"law": "Order decays; effort is what holds it together.", "physics": {}},
    "predation": {"law": "Some live by taking from others, and the others adapt.", "physics": {}},
}

TAG_ELEMENTS = {"projectile": ["projectile_arc"], "splash": ["burst", "soak"], "rally": ["rally", "touch_limit"], "team": ["team"], "oscillation": ["pulse"],
                "resonance": ["pulse"], "contagion": ["contagion", "network"], "quarantine": ["quarantine"], "purge": ["purge"], "signal": ["signal"], "network": ["network"],
                "tipping": ["tipping"], "diffusion": ["diffusion"], "erosion": ["erosion"], "scarcity": ["scarcity"], "migration": ["drift"], "symbiosis": ["symbiosis"],
                "selection": ["selection"], "feedback": ["feedback"], "entropy": ["entropy"], "predation": ["predation"]}
ENTRY_ELEMENTS = {   # explicit decompositions, richer than the tags
    "water balloon fights": ["projectile_arc", "burst", "soak", "refill", "friendly_fire", "team"],
    "volleyball": ["net", "rally", "touch_limit", "serve", "bounce", "team"],
    "rally scoring": ["rally", "serve"],
    "projectile motion": ["projectile_arc", "bounce"],
    "wave interference": ["pulse", "soak"],
    "beach dune formation": ["drift", "erosion", "wind"],
    "the water cycle": ["soak", "tide"],
    "tidal pools": ["tide", "scarcity", "soak"],
    "tidal locking": ["tide", "pulse"],
    "surface tension": ["soak", "burst"],
    "quarantine": ["quarantine", "network", "fog"],
    "John Snow's cholera map": ["contagion", "signal", "network"],
}


def entry_elements(entry):
    if entry[0] in ENTRY_ELEMENTS:
        return list(ENTRY_ELEMENTS[entry[0]])
    out = []
    for t in entry[2]:
        for e in TAG_ELEMENTS.get(t, []):
            if e not in out:
                out.append(e)
    return out


# ---------------------------------------------------------------- game families and their idea modules
# module values are small ints so they travel through Godot data files unchanged
FAMILIES = {
    "volley": {"genre": "3D sport", "unlock": ["net", "rally"],               # any of these unlocks the family
               "modules": {"ball": {0: ("rubber", []), 1: ("water balloon", ["burst", "soak"])},
                           "net": {0: ("solid net", []), 1: ("porous net", ["wind", "drift", "diffusion", "slick"])},
                           "score": {0: ("rally scoring", ["rally"]), 1: ("soak scoring", ["soak"])}}},
    "splash": {"genre": "top-down arena action", "unlock": ["projectile_arc", "burst"],
               "modules": {"barrier": {0: ("open arena", []), 1: ("net across the arena", ["net"])},
                           "ret": {0: ("no returns", []), 1: ("bat balloons back", ["rally", "signal", "bounce"])},
                           "win": {0: ("elimination", []), 1: ("hold the fountain", ["tipping", "wells", "pulse", "tide", "soak"])}}},
    "cordon": {"genre": "network strategy", "unlock": ["contagion", "quarantine", "diffusion"], "modules": {"purge": {0: ("no purge", []), 1: ("purge allowed", ["purge"])}}},
    "arcade3d": {"genre": "3D action", "unlock": [], "modules": {"law": {0: ("law of the universe", [])}}},
    "concept": {"genre": "strategy duel", "unlock": [], "modules": {}},
    "steward": {"genre": "world simulation", "unlock": [], "modules": {}},
}


def family_available(family, elements):
    u = FAMILIES[family]["unlock"]
    return not u or any(e in elements for e in u)


def module_available(family, mod, val, elements):
    needs = FAMILIES[family]["modules"][mod][val][1]
    return not needs or any(e in elements for e in needs)


def universe_physics(elements):
    """Fuse element physics into the shared constants every game of the universe must honour."""
    ph = {"gravity_scale": 1.0, "wind": 0.0, "slick": 0, "burst_radius": 1.0, "soak_weight": 0.0, "restitution_scale": 1.0}
    for e in elements:
        for k, v in ELEMENTS[e]["physics"].items():
            if k == "wind":
                ph["wind"] = max(ph["wind"], v)
            elif k == "slick":
                ph["slick"] = 1
            else:
                ph[k] = max(ph.get(k, 0), v)
    return ph


def laws_text(elements):
    return [ELEMENTS[e]["law"] for e in elements]
