"""Timelines: snapshots, deterministic rewind/replay, and branching (alternate realities)."""
import copy
from . import world as W


class Timeline:
    def __init__(self, state, tid="main", parent=None, fork_tick=None, snap_every=50):
        self.s = state
        self.tid = tid
        self.parent = parent
        self.fork_tick = fork_tick
        self.snap_every = snap_every
        self.interventions = []   # {"tick","kind","args","path"?}
        self.applied = set()
        self.snaps = {state["tick"]: copy.deepcopy(state)}
        self.children = 0

    @property
    def tick(self):
        return self.s["tick"]

    def _apply_due(self):
        for idx, iv in enumerate(self.interventions):
            if iv["tick"] == self.s["tick"] and idx not in self.applied:
                W.apply_intervention(self.s, iv)
                self.applied.add(idx)

    def step(self, n=1):
        for _ in range(n):
            self._apply_due()
            W.tick(self.s)
            if self.s["tick"] % self.snap_every == 0:
                self.snaps[self.s["tick"]] = copy.deepcopy(self.s)

    def intervene(self, kind, args=(), path=None):
        iv = {"tick": self.s["tick"], "kind": kind, "args": list(args)}
        if path:
            iv["path"] = path
        self.interventions.append(iv)
        W.apply_intervention(self.s, iv)
        self.applied.add(len(self.interventions) - 1)

    def rewind(self, t):
        """Restore the world to tick t (before interventions scheduled at t). Recorded interventions
        replay automatically on later step() calls, so the original timeline is reproducible."""
        base = max(k for k in self.snaps if k <= t)
        self.s = copy.deepcopy(self.snaps[base])
        self.applied = {i for i, iv in enumerate(self.interventions) if iv["tick"] < base}
        while self.s["tick"] < t:
            self.step(1)
        self.applied = {i for i, iv in enumerate(self.interventions) if iv["tick"] < t}

    def truncate_future(self):
        """Forget recorded interventions at or after the current tick (commit to a new history)."""
        t = self.s["tick"]
        self.interventions = [iv for iv in self.interventions if iv["tick"] < t]
        self.applied = set(range(len(self.interventions)))
        self.snaps = {k: v for k, v in self.snaps.items() if k <= t}

    def fork(self, name=None):
        self.children += 1
        tid = name or f"{self.tid}.{self.children}"
        b = Timeline(copy.deepcopy(self.s), tid, self.tid, self.s["tick"], self.snap_every)
        b.interventions = [copy.deepcopy(iv) for i, iv in enumerate(self.interventions) if i in self.applied]
        b.applied = set(range(len(b.interventions)))
        b.snaps = {k: copy.deepcopy(v) for k, v in self.snaps.items() if k <= self.s["tick"]}
        return b
