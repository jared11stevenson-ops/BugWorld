# Port of ghost/kernel/timeline.py: snapshots, deterministic rewind, branching.
extends RefCounted

const K = preload("res://ghost/kernel.gd")

var s: Dictionary
var tid: String
var parent: String
var fork_tick: int
var snap_every: int
var interventions: Array = []
var applied: Dictionary = {}
var snaps: Dictionary = {}
var children: int = 0


func _init(state: Dictionary, id := "main", parent_id := "", ftick := -1, every := 50) -> void:
	s = state
	tid = id
	parent = parent_id
	fork_tick = ftick
	snap_every = every
	snaps = {int(state["tick"]): state.duplicate(true)}


func tick() -> int:
	return s["tick"]


func _apply_due() -> void:
	for idx in interventions.size():
		var iv: Dictionary = interventions[idx]
		if iv["tick"] == s["tick"] and not applied.has(idx):
			K.apply_intervention(s, iv)
			applied[idx] = true


func step(n := 1) -> void:
	for _i in n:
		_apply_due()
		K.tick(s)
		if s["tick"] % snap_every == 0:
			snaps[int(s["tick"])] = s.duplicate(true)


func intervene(kind: String, args := [], path := "") -> void:
	var iv := {"tick": s["tick"], "kind": kind, "args": args.duplicate()}
	if path != "":
		iv["path"] = path
	interventions.append(iv)
	K.apply_intervention(s, iv)
	applied[interventions.size() - 1] = true


func _applied_before(t: int) -> Dictionary:
	var d := {}
	for i in interventions.size():
		if interventions[i]["tick"] < t:
			d[i] = true
	return d


func rewind(t: int) -> void:
	var base := -1
	for k in snaps.keys():
		if k <= t and k > base:
			base = k
	s = snaps[base].duplicate(true)
	applied = _applied_before(base)
	while s["tick"] < t:
		step(1)
	applied = _applied_before(t)


func truncate_future() -> void:
	var t: int = s["tick"]
	var keep := []
	for iv in interventions:
		if iv["tick"] < t:
			keep.append(iv)
	interventions = keep
	applied = {}
	for i in keep.size():
		applied[i] = true
	var ns := {}
	for k in snaps.keys():
		if k <= t:
			ns[k] = snaps[k]
	snaps = ns


func fork(name := "") -> RefCounted:
	children += 1
	var id := name if name != "" else "%s.%d" % [tid, children]
	var b = get_script().new(s.duplicate(true), id, tid, s["tick"], snap_every)
	b.interventions = []
	for i in interventions.size():
		if applied.has(i):
			b.interventions.append(interventions[i].duplicate(true))
	b.applied = {}
	for i in b.interventions.size():
		b.applied[i] = true
	b.snaps = {}
	for k in snaps.keys():
		if k <= s["tick"]:
			b.snaps[k] = snaps[k].duplicate(true)
	return b
