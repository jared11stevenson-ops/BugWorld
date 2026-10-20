"""Rulesets are plain int-valued dicts (the 'genome'). Combat is the evolvable mechanic."""
import copy

ACTIONS = ["attack", "guard", "power", "heal"]

BASELINE = {
    "name": "v0_baseline",
    "combat": {
        "crit_pct": 10, "crit_mult_pct": 150,
        "guard_reduce_pct": 20, "guard_counter_pct": 0, "guard_pierce_pct": 100,
        "power_mult_pct": 150, "power_interrupt_pct": 100,
        "potion_heal": 30, "heal_vuln_pct": 0, "start_potions": 3,
        "fatigue_pct": 0, "round_cap": 40,
    },
    "economy": {
        "base_price": 10, "swing_pct": 15, "restock_ticks": 6, "stock_cap": 6,
        "sell_pct": 80, "wage": 2, "tax_pct": 25, "burn": 3, "upkeep": 2, "upkeep_every": 5,
    },
    "world": {
        "aggro_pct": 4, "war_threshold": -40, "kill_rel_penalty": 4, "loot_pct": 50,
        "flee_pct": 50, "respawn_delay": 20, "regen_div": 25,
    },
}

# Evolvable combat parameters: (lo, hi, step)
COMBAT_BOUNDS = {
    "crit_pct": (0, 40, 5), "crit_mult_pct": (120, 250, 10),
    "guard_reduce_pct": (0, 90, 5), "guard_counter_pct": (0, 100, 10), "guard_pierce_pct": (0, 100, 10),
    "power_mult_pct": (100, 300, 10), "power_interrupt_pct": (0, 100, 10),
    "potion_heal": (5, 60, 5), "heal_vuln_pct": (0, 100, 10), "start_potions": (0, 5, 1),
    "fatigue_pct": (0, 30, 5),
}

# Mechanic modules: crossover and ablation operate at this granularity.
MODULES = {
    "crit": ["crit_pct", "crit_mult_pct"],
    "guard": ["guard_reduce_pct", "guard_counter_pct", "guard_pierce_pct"],
    "power": ["power_mult_pct", "power_interrupt_pct"],
    "heal": ["potion_heal", "heal_vuln_pct", "start_potions"],
    "fatigue": ["fatigue_pct"],
}


def clone(rules):
    return copy.deepcopy(rules)


def clamp_combat(c):
    for k, (lo, hi, _st) in COMBAT_BOUNDS.items():
        c[k] = max(lo, min(hi, int(c[k])))
    return c


def validate(rules):
    for sec in ("combat", "economy", "world"):
        for k, v in rules[sec].items():
            if not isinstance(v, int):
                raise ValueError(f"{sec}.{k} must be int, got {v!r}")
    for k, (lo, hi, _st) in COMBAT_BOUNDS.items():
        v = rules["combat"][k]
        if not lo <= v <= hi:
            raise ValueError(f"combat.{k}={v} out of bounds [{lo},{hi}]")
    return True
