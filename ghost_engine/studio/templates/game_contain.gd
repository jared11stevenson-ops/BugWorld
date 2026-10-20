# Game: Cordon. Contain an outbreak on a network of towns: quarantine, treat, or purge (burn a town: costly, capped, and it costs you your conscience).
extends "res://ghost/shell.gd"

const A = preload("res://ghost/contain_core.gd")
const D = preload("res://data/contain.gd")


class MapView extends Control:
	var g

	func _gui_input(ev: InputEvent) -> void:
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			g.pick_at(ev.position, size)

	func _draw() -> void:
		g.draw_map(self)


var s: Dictionary
var params: Dictionary
var sel := -1
var map_view: MapView
var info_lbl: RichTextLabel
var log_lbl: RichTextLabel
var btns: Dictionary = {}
var seed_i := 0
var script_log: Array = []
var flash := 0.0
var t_anim := 0.0
var testing := false


func start() -> void:
	game_id = "cordon"
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	title_screen(U.get("game_title", "Cordon"), "Contain the outbreak. Choose carefully what you are willing to burn.\n" + universe_line(), [["Begin", intro], ["How to play", help]])


func help() -> void:
	text_screen("How to play", "Click a town to select it. Each day you have a few actions:\n- Quarantine (1): seal the town's roads for several days and halve local spread.\n- Treat (1): cure many sick there (limited medicine).\n- Purge (2): burn the town, killing everyone in it and ending its infection forever. You may purge at most %d%% of all people before the world turns on you.\nThen end the day. Survive %d days with at least %d%% of the population alive, or stamp the sickness out entirely." % [int(params["purge_cap"]), int(params["days"]), int(params["win_pct"])], "Back", start)


func intro() -> void:
	text_screen("The first sickness", "\n\n".join(PackedStringArray(U.get("lore", {}).get("prologue", []))), "Take command", func(): begin_game(int(U.get("seed", 1)) * 10 + seed_i))


func begin_game(seed_in: int) -> void:
	seed_i += 1
	s = A.new_game(seed_in, params)
	sel = -1
	script_log = []
	var v := clear()
	info_lbl = RichTextLabel.new()
	info_lbl.bbcode_enabled = true
	info_lbl.custom_minimum_size = Vector2(0, 92)
	v.add_child(info_lbl)
	map_view = MapView.new()
	map_view.g = self
	map_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map_view.custom_minimum_size = Vector2(0, 330)
	v.add_child(map_view)
	var bar := HFlowContainer.new()
	v.add_child(bar)
	btns.clear()
	btns["q"] = button(bar, "Quarantine (1)", func(): act("q"))
	btns["t"] = button(bar, "Treat (1)", func(): act("t"))
	btns["p"] = button(bar, "Purge (%d)" % int(params["purge_ap"]), func(): act("p"))
	btns["end"] = button(bar, "End day", end_day_ui)
	log_lbl = RichTextLabel.new()
	log_lbl.bbcode_enabled = true
	log_lbl.scroll_following = true
	log_lbl.custom_minimum_size = Vector2(0, 120)
	v.add_child(log_lbl)
	log_lbl.append_text("Day 0. Two towns report the sickness.\n")
	refresh()


func tname(i: int) -> String:
	var towns: Array = U["lexicon"]["towns"]
	return towns[i % towns.size()] + ("" if i < towns.size() else " " + str(i / towns.size() + 1))


func refresh() -> void:
	var t := A.totals(s)
	info_lbl.text = "[b]Day %d / %d[/b]   actions %d   medicine %d   alive %d%%   sick %d   purged %d%% (limit %d%%)\n%s" % [s["day"], int(params["days"]), s["ap"], s["meds"], t[0] * 100 / s["total"], t[1], s["purged"] * 100 / s["total"], int(params["purge_cap"]), _sel_text()]
	for k in ["q", "t", "p"]:
		btns[k].disabled = s["over"] != 0 or sel < 0
	btns["end"].disabled = s["over"] != 0
	map_view.queue_redraw()


func _sel_text() -> String:
	if sel < 0:
		return "Select a town on the map."
	return "[b]%s[/b]: population %d   healthy %d   sick %d   recovered %d   dead %d   quarantine %d days%s" % [tname(sel), s["pop"][sel], s["S"][sel], s["I"][sel], s["R"][sel], s["D"][sel], s["Q"][sel], "   [BURNED]" if s["B"][sel] != 0 else ""]


func pos_of(i: int, sz: Vector2) -> Vector2:
	return Vector2(40.0 + float(s["x"][i]) / 1000.0 * (sz.x - 80.0), 30.0 + float(s["y"][i]) / 1000.0 * (sz.y - 60.0))


func pick_at(p: Vector2, sz: Vector2) -> void:
	var best := -1
	var bd := 1e9
	for i in s["pop"].size():
		var d := pos_of(i, sz).distance_to(p)
		if d < bd and d < 36.0:
			bd = d
			best = i
	sel = best
	sfx("click")
	refresh()


func act(kind: String) -> void:
	if sel < 0:
		return
	var ok := A.apply_action(s, [kind, sel])
	if ok:
		script_log.append([kind, sel])
		match kind:
			"q":
				sfx("alarm")
				log_lbl.append_text("%s is sealed for %d days.\n" % [tname(sel), int(params["q_days"])])
			"t":
				sfx("cure")
				log_lbl.append_text("Medicine is carried to %s.\n" % tname(sel))
			"p":
				sfx("burn")
				flash = 1.0
				log_lbl.append_text("[color=#%s]%s is put to the fire. %d perish.[/color]\n" % [pal[2].to_html(false), tname(sel), s["D"][sel]])
		if s["over"] != 0:
			_finish()
	else:
		sfx("hit")
	refresh()


func end_day_ui() -> void:
	end_day_core()


func end_day_core() -> void:
	var before := A.totals(s)
	script_log.append(["end", 0])
	A.end_day(s)
	var after := A.totals(s)
	sfx("infect" if after[1] > before[1] else "step")
	log_lbl.append_text("Day %d: sick %d → %d, alive %d.\n" % [s["day"], before[1], after[1], after[0]])
	if s["over"] != 0:
		_finish()
	refresh()


func _finish() -> void:
	var lore: Dictionary = U.get("lore", {})
	var won: bool = s["won"] != 0
	sfx("win" if won else "lose")
	var t := A.totals(s)
	var why := {"extinguished": "The sickness is stamped out.", "survived": "The season ends and the sickness ebbs.", "collapse": "The towns empty; there is no one left to command.", "conscience": "You burned too much. The survivors no longer follow you.", "too_many_dead": "The sickness is gone, but too few remain."}
	var body: String = "%s\nAlive: %d%% of %d. Purged: %d%%.\n\n%s" % [why.get(s["why"], ""), t[0] * 100 / s["total"], s["total"], s["purged"] * 100 / s["total"], lore.get("epilogue_win" if won else "epilogue_lose", "")]
	if won:
		save["best"] = maxi(int(save.get("best", 0)), t[0])
		write_save()
	var ctx := {"won": won, "why": s["why"], "alive_pct": t[0] * 100 / s["total"], "purged_pct": s["purged"] * 100 / s["total"], "params": params}
	if testing:
		return
	get_tree().create_timer(0.8).timeout.connect(func(): end_screen("Victory" if won else "Defeat", body, ctx, "Back to title", start))


func draw_map(c: Control) -> void:
	var sz := c.size
	t_anim += 0.016
	for e in s["edges"]:
		var a: Vector2 = pos_of(e[0], sz)
		var b: Vector2 = pos_of(e[1], sz)
		var sealed: bool = s["Q"][e[0]] > 0 or s["Q"][e[1]] > 0
		var burned: bool = s["B"][e[0]] != 0 or s["B"][e[1]] != 0
		var col: Color = pal[1].lightened(0.3)
		if sealed or burned:
			col = pal[2].darkened(0.3)
		c.draw_line(a, b, col, 1.5 if not sealed else 3.0)
	for i in s["pop"].size():
		var p := pos_of(i, sz)
		var r := 10.0 + float(s["pop"][i]) / 1200.0 * 18.0
		var inf_ratio := float(s["I"][i]) / maxf(1.0, float(s["pop"][i]))
		if s["B"][i] != 0:
			c.draw_circle(p, r, Color(0.05, 0.03, 0.03))
			c.draw_arc(p, r + 3.0 + sin(t_anim * 6.0 + i) * 1.5, 0, TAU, 20, Color(1.0, 0.45, 0.1), 2.0)
		else:
			c.draw_circle(p, r, pal[3].darkened(0.2))
			if s["I"][i] > 0:
				var pulse := 1.0 + 0.08 * sin(t_anim * 5.0 + i)
				c.draw_circle(p, r * minf(1.0, sqrt(inf_ratio) * 1.6 + 0.12) * pulse, pal[2])
			if s["Q"][i] > 0:
				c.draw_arc(p, r + 6.0, 0, TAU, 24, pal[4], 3.0)
		if i == sel:
			c.draw_arc(p, r + 10.0, 0, TAU, 32, Color.WHITE, 2.0)
		c.draw_string(ThemeDB.fallback_font, p + Vector2(-30, r + 18), tname(i), HORIZONTAL_ALIGNMENT_CENTER, 60, 12, pal[4])
	if flash > 0.0:
		c.draw_rect(Rect2(Vector2.ZERO, sz), Color(1.0, 0.4, 0.1, flash * 0.18))
		flash = maxf(0.0, flash - 0.03)


func _process(_d: float) -> void:
	if map_view != null and is_instance_valid(map_view) and s.has("over"):
		map_view.queue_redraw()


# ---------------------------------------------------------------- headless verification
func selftest() -> Dictionary:
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	testing = true
	var res := {"ok": false}
	var nothing_wins := 0
	for i in 12:
		var g := A.new_game(9000 + i, params)
		while g["over"] == 0:
			A.end_day(g)
		nothing_wins += g["won"]
	res["do_nothing_wins_of_12"] = nothing_wins
	var won_script := []
	var won_seed := -1
	var tries := 0
	for k in 10:
		tries += 1
		begin_game(500 + k)
		await get_tree().process_frame
		while s["over"] == 0:
			for a in A.bot_actions(s, 1):
				sel = a[1]
				act(a[0])
			end_day_core()
		if s["won"] != 0:
			won_script = script_log.duplicate(true)
			won_seed = 500 + k
			break
	res["bot_won"] = won_seed >= 0
	res["bot_tries"] = tries
	res["seed"] = won_seed
	res["script"] = won_script
	res["final_digest"] = A.digest(s)
	res["final_day"] = s["day"]
	res["final_alive"] = A.totals(s)[0]
	# purge cap must end the game (conscience) - test the rule through the real action path
	begin_game(777)
	var guard := 0
	while s["over"] == 0 and guard < 30:
		guard += 1
		sel = guard % int(params["nodes"])
		act("p")
		if s["ap"] < int(params["purge_ap"]):
			end_day_core()
	res["purge_cap_enforced"] = s["over"] != 0 and s["why"] in ["conscience", "collapse"]
	res["audio_loaded"] = sfx_players["burn"].stream.data.size() > 500 and music_player.stream.data.size() > 10000
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	rate_run(4, {"selftest": true})
	res["feedback_written"] = FileAccess.file_exists(FEEDBACK_PATH)
	res["ok"] = res["bot_won"] and nothing_wins <= 3 and res["purge_cap_enforced"] and res["audio_loaded"] and res["save_written"] and res["feedback_written"]
	return res


func shot_prepare() -> void:
	begin_game(501)
	sel = 0
	for i in 4:
		for a in A.bot_actions(s, 1):
			sel = a[1]
			act(a[0])
		end_day_core()
	sel = 0
	refresh()
