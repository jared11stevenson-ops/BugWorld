"""Hand-written seed concepts from three different genres. They are the baseline for novelty and comparison."""

def V(w, n): return ["v", w, n]
def inc(w, n, e): return ["+=", w, n, e]
def when_opp(a, yes, no=0): return ["?", ["==", ["act", "opp"], a], yes, no]


def slugfest():
    return {"id": "seed_slugfest", "name": "Slugfest",
            "vars": [["hp", 40, 0, 40], ["energy", 2, 0, 5]],
            "actions": [
                {"name": "strike", "cond": 0, "fx": [inc("opp", "hp", -6), inc("me", "energy", 1)]},
                {"name": "guard", "cond": 0, "fx": [inc("me", "hp", when_opp(0, 4)), inc("opp", "hp", when_opp(0, -2))]},
                {"name": "bomb", "cond": [">=", V("me", "energy"), 2],
                 "fx": [inc("opp", "hp", when_opp(1, -3, -12)), inc("me", "energy", -2)]},
                {"name": "rest", "cond": 0, "fx": [inc("me", "hp", 3), inc("me", "energy", 1)]}],
            "passive": [], "end": [[["<=", V("opp", "hp"), 0], 1], [["<=", V("me", "hp"), 0], -1]],
            "tiebreak": "hp", "max_rounds": 20, "value": [["hp", 1]]}


def sprint():
    return {"id": "seed_sprint", "name": "Sprint",
            "vars": [["pos", 0, 0, 12], ["fuel", 3, 0, 6]],
            "actions": [
                {"name": "jog", "cond": 0, "fx": [inc("me", "pos", 1), inc("me", "fuel", 1)]},
                {"name": "dash", "cond": [">=", V("me", "fuel"), 2], "fx": [inc("me", "pos", 3), inc("me", "fuel", -2)]},
                {"name": "trip", "cond": 0, "fx": [inc("opp", "pos", -1)]},
                {"name": "block", "cond": 0, "fx": [inc("opp", "pos", when_opp(1, -3)), inc("me", "pos", 1)]}],
            "passive": [], "end": [[[">=", V("me", "pos"), 12], 1]],
            "tiebreak": "pos", "max_rounds": 25, "value": [["pos", 1]]}


def heist():
    return {"id": "seed_heist", "name": "Heist",
            "vars": [["loot", 0, 0, 30], ["heat", 0, 0, 10]],
            "actions": [
                {"name": "sneak", "cond": 0, "fx": [inc("me", "loot", 1)]},
                {"name": "grab", "cond": 0, "fx": [inc("me", "loot", 4), inc("me", "heat", 3)]},
                {"name": "frame", "cond": 0, "fx": [inc("opp", "heat", 2)]},
                {"name": "lay_low", "cond": 0, "fx": [inc("me", "heat", -3)]}],
            "passive": [], "end": [[[">=", V("me", "heat"), 10], -1], [[">=", V("me", "loot"), 15], 1]],
            "tiebreak": "loot", "max_rounds": 25, "value": [["loot", 1], ["heat", -1]]}


def all_seeds():
    return [slugfest(), sprint(), heist()]
