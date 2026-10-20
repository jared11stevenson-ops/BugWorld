"""Deterministic xorshift32 RNG operating on a state dict {"rng": int}.
Integer-only so the GDScript port (godot/ghost/kernel.gd) is bit-identical."""
M = 0xFFFFFFFF


def seed_state(seed):
    seed &= 0x7FFFFFFF
    x = (seed * 2654435761 + 0x9E3779B9) & M
    if x == 0:
        x = 1
    st = {"rng": x}
    for _ in range(3):
        next_u32(st)
    return st["rng"]


def next_u32(s):
    x = s["rng"]
    x ^= (x << 13) & M
    x ^= x >> 17
    x ^= (x << 5) & M
    s["rng"] = x
    return x


def rand(s, n):
    return next_u32(s) % n


def fnv32_ints(h, vals):
    for v in vals:
        h = ((h ^ (v & M)) * 16777619) & M
    return h


FNV_OFFSET = 2166136261


def fnv32_str(text):
    h = FNV_OFFSET
    for b in text.encode("ascii"):
        h = ((h ^ b) * 16777619) & M
    return h
