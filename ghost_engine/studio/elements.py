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
    "shell_armor": {"law": "Hardened shells turn blows aside; the patient survive what the bold do not.", "physics": {"armor_factor": 1.6}},
    "longevity": {"law": "The long-lived plan in centuries; haste is a young species' folly.", "physics": {}},
    "siege": {"law": "Fortified places fall to bombardment and patience alike.", "physics": {}},
    "logistics": {"law": "Armies march on fuel and fodder; supply decides wars.", "physics": {}},
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
    "evolved turtles": ["shell_armor", "longevity", "selection", "tide", "team"],
    "sea turtle navigation": ["signal", "drift", "tide", "longevity"],
    "tank warfare": ["projectile_arc", "shell_armor", "siege", "logistics", "team"],
    "the Battle of Kursk": ["projectile_arc", "siege", "logistics", "scarcity"],
    "convergent evolution": ["selection", "feedback"],
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
    "splash": {"genre": "top-down arena action", "unlock": [], "neutral": True,
               "modules": {"barrier": {0: ("open arena", []), 1: ("wall across the arena", ["net", "siege"])},
                           "ret": {0: ("no returns", []), 1: ("bat balloons back", ["rally", "signal", "bounce"])},
                           "win": {0: ("elimination", []), 1: ("hold the fountain", ["tipping", "wells", "pulse", "tide", "soak"])}}},
    "cordon": {"genre": "network strategy", "unlock": ["contagion", "quarantine", "diffusion"], "modules": {"purge": {0: ("no purge", []), 1: ("purge allowed", ["purge"])}}},
    "artillery": {"genre": "turn-based artillery duel", "unlock": [], "neutral": True,       # theme-neutral engine: playable in any universe, skinned by it
                  "modules": {"terrain": {0: ("steady ground", []), 1: ("cratering ground", [])},
                              "ricochet": {0: ("shells burst on contact", []), 1: ("shells ricochet once", [])},
                              "gust": {0: ("steady wind", []), 1: ("gusting wind", [])}}},
    "bastion": {"genre": "wave-defence strategy", "unlock": [], "neutral": True,
                "modules": {"mortar": {0: ("cannons only", []), 1: ("area mortars", [])}, "chill": {0: ("no slowing", []), 1: ("slowing towers", [])},
                            "armored": {0: ("light invaders", []), 1: ("armored heavy invaders", [])}}},
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
    ph = {"gravity_scale": 1.0, "wind": 0.0, "slick": 0, "burst_radius": 1.0, "soak_weight": 0.0, "restitution_scale": 1.0, "armor_factor": 1.0}
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


SKINS = {   # the same engine, dressed by the universe: engines are theme-neutral, universes supply the fiction
    "soak": {"proj": "balloon", "station": "bucket", "verb": "soaking", "hurt": "Soaked!", "hp": "dryness", "champ": "Soak champion", "okay": "Dry enough!", "pick": "Pick up a balloon", "title": "Splash", "fx": [0.3, 0.6, 1.0], "name": "soak"},
    "shell": {"proj": "shell", "station": "depot", "verb": "battering", "hurt": "Knocked out!", "hp": "integrity", "champ": "Skirmish victor", "okay": "Still standing!", "pick": "Load a shell", "title": "Skirmish", "fx": [0.95, 0.6, 0.25], "name": "skirmish"},
}


def skin(elements):
    return SKINS["soak" if "soak" in elements else "shell"]
