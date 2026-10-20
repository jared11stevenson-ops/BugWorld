"""The studio's roles. Each role is an executable stage with an acceptance check - not a chat persona. LLM agents can fill a role through the
same contracts (foundry inbox for mechanics; data files for lore), but this cycle's roles are programmatic. Capability gaps are recorded, not hidden."""
ROLES = {
    "inspiration": {"tool": "studio.inspiration.pick", "accept": "3 inspirations from distinct fields", "status": "implemented"},
    "universe_designer": {"tool": "studio.universe.make_universe + explore", "accept": "evolved rules + canon history chosen among explored branches", "status": "implemented"},
    "mechanics_designer": {"tool": "ghost.foundry (discovery loop, agent inbox)", "accept": "viable concepts validated on held-out seeds", "status": "implemented"},
    "programmer": {"tool": "studio.games builders + templates", "accept": "standalone Godot project per game", "status": "implemented"},
    "audio": {"tool": "studio.audio (procedural synthesis)", "accept": "12 sfx + layered mood music (drone/pad/bass/heartbeat/hats/arpeggio) + ambient bed per game, loaded without import", "status": "implemented (synthesized; not composed or mixed by an artist)"},
    "balancer_optimizer": {"tool": "studio.tuner + foundry evolution", "accept": "difficulty tuned on held-out seeds", "status": "implemented"},
    "tester": {"tool": "studio.verify", "accept": "self-test, no script errors, twin parity, screenshots", "status": "implemented"},
    "art_2d": {"tool": "shell Emblem + _draw (procedural vector shapes, palette from universe)", "accept": "non-blank screens", "status": "partial (procedural vector art only)"},
    "art_3d": {"tool": "game_arcade3d.gd procedural low-poly meshes (primitives), emissive materials, lighting, fog, skyline", "accept": "3D scene renders (screenshot non-blank) and view matches simulation state", "status": "partial (procedural primitives only; no authored or sculpted assets)"},
    "animation": {"tool": "procedural limb swing/bob, pulsing/spinning props, tweens, particles, camera shake, scene fades", "accept": "no script errors while animating; state sync test", "status": "partial (procedural transforms; no skeletal rigs or authored clips)"},
    "polish_producer": {"tool": "shell.end_screen rating hook in every game + studio.feedback import", "accept": "feedback record written; importer aggregates", "status": "partial (pipeline exists; NO human ratings collected yet)"},
}
