# Plays every compiled concept to the end through the real arena UI and dumps replayable session records for the Python twin.
# Run: godot --headless --path godot --script res://tests/concept_ui_smoke.gd -- out.json
extends SceneTree

const CS = preload("res://generated/concepts.gd")
var fails := 0


func _init() -> void:
	var out := OS.get_cmdline_user_args()[0]
	var main = load("res://ghost/main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	main.open_concepts()
	await process_frame
	var recs := []
	var opps := [8, 7, 6, 9]
	for i in CS.CONCEPTS.size():
		for k in 3:
			var arena = main.start_concept(i, opps[(i + k) % 4])
			await process_frame
			var n := 0
			while arena.m["done"] == 0 and n < 80:
				var legal := []
				for b in arena.buttons.size():
					if not arena.buttons[b].disabled:
						legal.append(b)
				arena._play(legal[(n * 7 + k) % legal.size()])
				n += 1
			if arena.m["done"] == 0:
				fails += 1
				print("FAIL: match did not finish ", i)
			arena.rate(3)
			recs.append(arena.last_record)
			await process_frame
	var f := FileAccess.open(out, FileAccess.WRITE)
	f.store_string(JSON.stringify(recs))
	f.close()
	print("CONCEPT_UI ", JSON.stringify({"fails": fails, "sessions": recs.size()}))
	quit(1 if fails > 0 else 0)
