"""Executable evidence for the red-team report. Run from anywhere: python3 foundry_agents/rt_prove.py"""
import json, os
from rt_lib import *
from ghost.foundry import agents as A, dsl
H = os.path.dirname(os.path.abspath(__file__))
L = lambda n: json.load(open(os.path.join(H, n)))

def play_script(spec, script0, p1, seed):
    """script0: list of actions for seat 0 (then 0), p1: policy id"""
    n = len(spec["actions"]); m = dsl.new_match(spec, seed); h = [A.new_hist(n), A.new_hist(n)]
    while not m["done"]:
        a0 = script0[m["round"]] if m["round"] < len(script0) else 0
        a1 = A.choose(spec, p1, m, 1, h[1])
        s0, s1 = dsl.step(spec, m, a0, a1); A.observe(h[0], s1); A.observe(h[1], s0)
    return m

print("== SEAT BIAS (redteam_seat.json): adapter vs adapter, 300 seeds")
s = L("redteam_seat.json"); w = [0, 0, 0]
for k in range(300):
    m = A.play(s, A.ADAPTER, A.ADAPTER, 5000 + k); w[m["winner"]] += 1
print(" seat0 wins=%d seat1 wins=%d draws=%d" % (w[0], w[1], w[-1]))
w = [0, 0, 0]
for k in range(300):
    m = A.play(s, 1, 1, 5000 + k); w[m["winner"]] += 1   # raid mirror
print(" always-raid mirror: seat0=%d seat1=%d draws=%d" % (w[0], w[1], w[-1]))

print("== COMBO (redteam_combo.json): scripted 'charge, finisher' bot in seat 0 vs all 12 pipeline policies, 20 seeds each")
s = L("redteam_combo.json"); tot = [0, 0, 0]
for p in range(12):
    r = [0, 0, 0]
    for k in range(20):
        r[play_script(s, [3, 1], p, 100 + k)["winner"]] += 1
    print("  vs %-9s win=%d loss=%d draw=%d" % (A.NAMES[p], r[0], r[1], r[-1]))

print("== DICE (redteam_dice.json): adapter(seat0) vs random win/loss over 400 seeds; and result vs sum of own dice")
s = L("redteam_dice.json"); w = [0, 0, 0]
for k in range(400): w[A.play(s, A.ADAPTER, A.RANDOM, 9000 + k)["winner"]] += 1
print(" adapter wins=%d random wins=%d draws=%d  (choice worth only ~%.0f%% edge)" % (w[0], w[1], w[-1], 100*(w[0]-w[1])/400))
w = [0, 0, 0]
for k in range(400): w[A.play(s, 3, 0, 9000 + k)["winner"]] += 1
print(" best fixed (roll_safe) vs plain roll: wins=%d losses=%d draws=%d" % (w[0], w[1], w[-1]))

print("== DECOY: how many adapter moves are the cosmetic action?")
s = L("redteam_decoy.json"); usage = [0]*5
for k in range(50): A.play(s, A.ADAPTER, 0, 300 + k, usage)
print(" adapter usage (bank,raid,guard,flourish,showboat):", usage)
# win rate after removing the cosmetic actions' effect: flourish does nothing to pts, so each flourish = lost tempo
for pid in (0, 2):
    r = [0, 0, 0]
    for k in range(100): r[A.play(s, 3, pid, 700 + k)["winner"]] += 1
    print(" always-flourish (never touches pts) vs always-%s: wins=%d losses=%d draws=%d" % (s["actions"][pid]["name"], r[0], r[1], r[-1]))
