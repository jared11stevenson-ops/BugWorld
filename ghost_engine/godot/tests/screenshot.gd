# Renders the playable viewer (and a duel) to PNGs. Needs a display: xvfb-run -a godot --rendering-driver opengl3 --path godot --script res://tests/screenshot.gd -- out_dir
extends SceneTree

const K = preload("res://ghost/kernel.gd")


func _init() -> void:
	var out := OS.get_cmdline_user_args()[0]
	DirAccess.make_dir_recursive_absolute(out)
	var main = load("res://ghost/main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	main.step(120)
	main.fork()
	main.intervene("set_rel")
	main.step(60)
	main.npc_list.select(2)
	main._show_history()
	for _i in 4:
		await process_frame
	root.get_viewport().get_texture().get_image().save_png(out + "/viewer.png")
	main.start_duel()
	await process_frame
	var duel = main.duel
	for a in [K.POWER, K.ATTACK, K.GUARD]:
		if duel.result == "":
			duel._on_action(a)
	for _i in 4:
		await process_frame
	root.get_viewport().get_texture().get_image().save_png(out + "/duel.png")
	quit(0)
