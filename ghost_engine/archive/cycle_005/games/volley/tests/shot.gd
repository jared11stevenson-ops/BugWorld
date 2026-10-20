# Screenshots + non-blank check. xvfb-run godot --rendering-driver opengl3 --path . --script res://tests/shot.gd -- out_dir
extends SceneTree


func colors(img: Image) -> int:
	var seen := {}
	for x in range(0, img.get_width(), 7):
		for y in range(0, img.get_height(), 7):
			seen[img.get_pixel(x, y).to_html()] = true
	return seen.size()


func _init() -> void:
	var out := OS.get_cmdline_user_args()[0]
	DirAccess.make_dir_recursive_absolute(out)
	var main = load("res://main.tscn").instantiate()
	root.add_child(main)
	for i in 4:
		await process_frame
	var a := root.get_viewport().get_texture().get_image()
	a.save_png(out + "/title.png")
	main.shot_prepare()
	for i in 6:
		await process_frame
	var b := root.get_viewport().get_texture().get_image()
	b.save_png(out + "/play.png")
	var f := FileAccess.open(out + "/shots.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"title_colors": colors(a), "play_colors": colors(b), "w": a.get_width(), "h": a.get_height()}))
	f.close()
	quit(0)
