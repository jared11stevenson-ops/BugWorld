# Generic runner: instantiates res://main.tscn, awaits the game's selftest(), prints GAME_SELFTEST {json}, exits non-zero on failure.
extends SceneTree


func _init() -> void:
	var main = load("res://main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	await process_frame
	var res: Dictionary = await main.selftest()
	print("GAME_SELFTEST ", JSON.stringify(res))
	quit(0 if res.get("ok", false) else 1)
