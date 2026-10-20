# Drives the real Main scene headlessly: step, rewind, fork, intervene, play a duel to the end and record feedback.
extends SceneTree

const K = preload("res://ghost/kernel.gd")
var fails := 0


func ok(cond: bool, msg: String) -> void:
	if not cond:
		fails += 1
		print("FAIL: ", msg)


func _init() -> void:
	var path := "user://human_feedback.jsonl"
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	var main = load("res://ghost/main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	main.step(60)
	ok(main.T().tick() == 60, "stepped to 60")
	var d60: String = K.digest_hex(main.T().s)
	main.step(40)
	main.rewind(40)
	ok(main.T().tick() == 60, "rewound 100->60")
	ok(K.digest_hex(main.T().s) == d60, "rewind digest matches earlier digest")
	main.fork()
	ok(main.timelines.size() == 2 and main.cur == 1, "forked and switched")
	var before: String = K.digest_hex(main.T().s)
	main.intervene("kill")
	main.step(30)
	var alt: String = K.digest_hex(main.T().s)
	main.switch_timeline(0)
	main.step(30)
	ok(K.digest_hex(main.T().s) != alt, "branch diverged from mainline after intervention")
	ok(main.npc_list.item_count > 0, "npc list populated")
	main.npc_list.select(0)
	main.start_duel()
	await process_frame
	var duel = main.duel
	ok(duel != null, "duel opened")
	var n := 0
	while duel.result == "" and n < 80:
		var heal_ok: bool = duel.player["potions"] > 0 and duel.player["hp"] < 60
		duel._on_action(K.HEAL if heal_ok else (K.POWER if n % 2 == 0 else K.ATTACK))
		n += 1
	ok(duel.result != "", "duel finished: " + duel.result)
	duel._rate(4)
	ok(FileAccess.file_exists(path), "feedback written")
	var line := FileAccess.get_file_as_string(path).strip_edges()
	var rec = JSON.parse_string(line)
	ok(rec != null and rec["rating"] == 4 and rec["ruleset"] == "v1_evolved", "feedback record content " + line)
	print("UI_SMOKE ", JSON.stringify({"fails": fails, "duel_rounds": n, "result": duel.result, "status": main.status.text}))
	quit(1 if fails > 0 else 0)
