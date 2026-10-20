"""Lore from simulation: faction personalities and town descriptions are derived from the canon history's measured statistics;
the prologue weaves the real-world facts into the universe's law. Templated language, real data."""
import random
from ghost.kernel import world as W
from . import universe as U

ADJ = {"ruthless": "have taken more lives than any rival", "beleaguered": "have buried the most of their own", "prosperous": "hold the fattest purses",
       "watchful": "have spilled the least blood and kept their counsel", "restless": "cannot stay out of other people's quarrels", "steadfast": "hold their ground whatever comes"}
TONE = {"contagion": ("sickness", "ward", "cure"), "purge": ("fire", "cleansing", "ash"), "pulse": ("rhythm", "beat", "tide"),
        "wells": ("weight", "pull", "orbit"), "drift": ("current", "drift", "wandering")}


def make_lore(uni):
    rnd = random.Random(uni["seed"] * 3 + 11)
    tl = U.canon_world(uni)
    s = tl.s
    lex = uni["lexicon"]
    nf = s["n_fac"]
    kills, deaths, wealth, alive = [0] * nf, [0] * nf, [0] * nf, [0] * nf
    for e in s["events"]:
        if e[2] == W.EV_KILL:
            deaths[s["npcs"][e[4]]["faction"]] += 1
            if e[3] >= 0:
                kills[s["npcs"][e[3]]["faction"]] += 1
    for n in s["npcs"]:
        if n["alive"]:
            wealth[n["faction"]] += n["gold"]; alive[n["faction"]] += 1
    wars = {}
    for e in s["events"]:
        if e[2] == W.EV_WAR:
            for f in (e[3], e[4]):
                wars[f] = wars.get(f, 0) + 1
    traits = {}
    order = lambda arr: sorted(range(nf), key=lambda i: -arr[i])
    traits[order(kills)[0]] = "ruthless"
    for f in order(deaths):
        if f not in traits:
            traits[f] = "beleaguered"; break
    for f in order(wealth):
        if f not in traits:
            traits[f] = "prosperous"; break
    for f in range(nf):
        traits.setdefault(f, "restless" if wars.get(f, 0) else "watchful")
    towns_pop = [sum(1 for n in s["npcs"] if n["alive"] and n["loc"] == i) for i in range(len(lex["towns"]))]
    facts = list(uni["facts"].items())
    noun, motion, remedy = TONE[uni["law"]]
    prologue = [
        f"{uni['name']} was not made; it was assembled from remembered truths. " + " ".join(f"\"{f}\"" for _, f in facts[:2]),
        f"Then came the third truth: \"{facts[2][1]}\" From the meeting of these three the law of {uni['name']} was born. {uni['law_text']}",
        (uni["chronicle"][0] if uni["chronicle"] else "The first days are unrecorded.") + f" That was how the {motion} first showed itself to the living.",
    ]
    factions = {}
    for f in range(nf):
        a = traits[f]
        factions[lex["factions"][f]] = {"trait": a, "blurb": f"{lex['factions'][f]} are {a}: they {ADJ[a]}. In the canon history they slew {kills[f]}, lost {deaths[f]}, and still field {alive[f]} souls with {wealth[f]} {lex['currency']}."}
    towns = {}
    for i, tn in enumerate(lex["towns"]):
        m1, m2 = rnd.sample(lex["motifs"], 2)
        towns[tn] = f"{tn}: {towns_pop[i]} souls live where {m1.replace('-', ' ')} meets {m2.replace('-', ' ')}; the {noun} is felt here first."
    ep_win = f"The {noun} of {uni['name']} did not end, but it learned your name. Those who survive will tell it as a story of {remedy}."
    ep_lose = f"The {noun} of {uni['name']} closes over the place where you stood. Perhaps the next keeper will remember what you could not."
    return {"prologue": prologue, "factions": factions, "towns": towns, "epilogue_win": ep_win, "epilogue_lose": ep_lose, "traits": traits}
