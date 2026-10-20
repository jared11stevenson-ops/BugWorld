# xvfb-run -a godot --rendering-driver opengl3 --path godot --script res://tests/concept_screenshot.gd -- out.png
extends SceneTree


func _init() -> void:
	var out := OS.get_cmdline_user_args()[0]
	var main = load("res://ghost/main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	var arena = main.start_concept(3, 8)
	await process_frame
	var n := 0
	while arena.m["done"] == 0 and n < 3:
		for b in arena.buttons.size():
			if not arena.buttons[b].disabled:
				arena._play((b + n) % arena.buttons.size() if not arena.buttons[(b + n) % arena.buttons.size()].disabled else b)
				break
		n += 1
	for _i in 4:
		await process_frame
	root.get_viewport().get_texture().get_image().save_png(out)
	quit(0)
