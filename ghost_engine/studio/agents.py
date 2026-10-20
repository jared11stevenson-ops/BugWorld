"""The studio's roles. Each role is an executable stage with an acceptance check - not a chat persona. LLM agents can fill a role through the
same contracts (foundry inbox for mechanics; data files for lore), but this cycle's roles are programmatic. Capability gaps are recorded, not hidden."""
ROLES = {
    "inspiration": {"tool": "studio.inspiration.pick", "accept": "3 inspirations from distinct fields", "status": "implemented"},
    "universe_designer": {"tool": "studio.universe.make_universe + explore", "accept": "evolved rules + canon history chosen among explored branches", "status": "implemented"},
    "mechanics_designer": {"tool": "ghost.foundry (discovery loop, agent inbox)", "accept": "viable concepts validated on held-out seeds", "status": "implemented"},
    "programmer": {"tool": "studio.games builders + templates", "accept": "standalone Godot project per game", "status": "implemented"},
    "audio": {"tool": "studio.audio (procedural synthesis)", "accept": "sfx + music loop per game, loaded without import", "status": "implemented (basic synthesis; no composed music)"},
    "balancer_optimizer": {"tool": "studio.tuner + foundry evolution", "accept": "difficulty tuned on held-out seeds", "status": "implemented"},
    "tester": {"tool": "studio.verify", "accept": "self-test, no script errors, twin parity, screenshots", "status": "implemented"},
    "art_2d": {"tool": "shell Emblem + _draw (procedural vector shapes, palette from universe)", "accept": "non-blank screens", "status": "partial (procedural vector art only)"},
    "art_3d": {"tool": "-", "accept": "-", "status": "MISSING: no 3D asset generation exists"},
    "animation": {"tool": "-", "accept": "-", "status": "MISSING: no skeletal/tween animation pipeline"},
    "polish_producer": {"tool": "-", "accept": "-", "status": "MISSING: no human-in-the-loop playtest feedback yet (rating hook exists in Game 1 foundry arena only)"},
}
