# Game 2: Steward. Guide one faction of the shared universe through 10 epochs using limited influence.
# Runs the persistent world kernel; previews are forked timelines, rewinds are limited. Target = do-nothing timeline * margin.
extends "res://ghost/shell.gd"

const K = preload("res://ghost/kernel.gd")
const TL = preload("res://ghost/timeline.gd")
const D = preload("res://data/steward.gd")

class MapView extends Control:
	var g

	func _draw() -> void:
		var s: Dictionary = g.tl.s
		var nt: int = s["towns"].size()
		var c := size / 2.0
		var rx := size.x * 0.40
		var ry := size.y * 0.36
		var pos := []
		for i in nt:
			var a := TAU * i / nt - PI / 2
			pos.append(c + Vector2(cos(a) * rx, sin(a) * ry))
		for i in nt:
			for j in s["adj"][i]:
				if j > i:
					draw_line(pos[i], pos[j], g.pal[1].lightened(0.25), 2.0)
		var fcol := [g.pal[3], g.pal[2], g.pal[4], g.pal[1].lightened(0.6)]
		for i in nt:
			draw_circle(pos[i], 30.0, g.pal[1])
			draw_arc(pos[i], 30.0, 0, TAU, 32, g.pal[2], 2.0)
			draw_string(ThemeDB.fallback_font, pos[i] + Vector2(-34, 50), g.tname(i), HORIZONTAL_ALIGNMENT_CENTER, 70, 14, g.pal[4])
			var k := 0
			for n in s["npcs"]:
				if n["alive"] and n["loc"] == i:
					var ang := k * 0.9
					var rr := 6.0 + 4.0 * floorf(k / 7.0)
					var p: Vector2 = pos[i] + Vector2(cos(ang), sin(ang)) * rr
					draw_circle(p, 4.0, fcol[n["faction"] % 4])
					if n["faction"] == g.f:
						draw_arc(p, 6.0, 0, TAU, 12, g.pal[4], 1.0)
					k += 1


var tl
var map_view: MapView
var f := 0
var epoch := 0
var ip := 0
var score := 0
var rewinds := 2
var epoch_start_tick := 0
var epoch_start_ip := 0
var epoch_start_score := 0
var target := 0
var over := false
var status_lbl: RichTextLabel
var log_lbl: RichTextLabel
var btns: Dictionary = {}
var script_log: Array = []
var shown := 0


func start() -> void:
	game_id = "steward"
	title_screen(U.get("game_title", "Steward"), "Guide %s through ten epochs.\n%s" % [fname(D.DATA["player_faction"]), universe_line()],
		[["Begin", intro], ["How to play", help]])


func help() -> void:
	text_screen("How to play", "You steward a faction in a living world that keeps running whether or not you act. Each epoch you gain influence (IP) and may spend it:\n- Bless (2): +300 to your poorest member.\n- Sue for peace (3): reset relations with your worst enemy.\n- Edict of calm (4): lower aggression for everyone.\n- Foresee (1): preview the next epoch on a forked timeline.\n- Rewind (free, 2 uses): undo this epoch.\nEnd the epoch to let time pass. Keep your people alive and prosperous: reach the target score by epoch 10. The target is 'what happens if you do nothing' plus a margin.", "Back", start)


func fname(i: int) -> String:
	return U["lexicon"]["factions"][i]


func tname(i: int) -> String:
	return U["lexicon"]["towns"][i]


func intro() -> void:
	var lore: Dictionary = U.get("lore", {})
	var fb: String = lore.get("factions", {}).get(fname(D.DATA["player_faction"]), {}).get("blurb", "")
	text_screen("The charge", "%s\n\nYou are the steward of %s. %s\n\n(World rules were found by an evolutionary search over %d candidate worlds.)" % ["\n\n".join(PackedStringArray(lore.get("prologue", []))), fname(D.DATA["player_faction"]), fb, int(D.DATA.get("evaluations", 0))], "Take the charge", begin_game)


func metric(s: Dictionary) -> Array:
	var pop := 0
	var wealth := 0
	for n in s["npcs"]:
		if n["alive"] and n["faction"] == f:
			pop += 1
			wealth += n["gold"]
	return [pop, wealth, pop * 10 + wealth / 50]


func begin_game() -> void:
	f = D.DATA["player_faction"]
	tl = TL.new(K.new_world(D.DATA["seed"], D.DATA["rules"]))
	tl.step(D.DATA["start_tick"])
	epoch = 0
	score = 0
	rewinds = 2
	ip = D.DATA["ip_start"] - D.DATA["ip_gain"]
	over = false
	script_log = []
	var ghost = tl.fork("baseline")
	var base := 0
	for e in D.DATA["epochs"]:
		ghost.step(D.DATA["epoch_ticks"])
		base += metric(ghost.s)[2]
	target = base * D.DATA["target_pct"] / 100
	new_epoch()


func new_epoch() -> void:
	ip += D.DATA["ip_gain"]
	epoch += 1
	epoch_start_tick = tl.tick()
	epoch_start_ip = ip
	epoch_start_score = score
	shown = tl.s["events"].size()
	build_ui()
	say("[b]Epoch %d begins.[/b] You have %d influence." % [epoch, ip])
	refresh()


func build_ui() -> void:
	var v := clear()
	status_lbl = RichTextLabel.new()
	status_lbl.bbcode_enabled = true
	status_lbl.custom_minimum_size = Vector2(0, 100)
	v.add_child(status_lbl)
	map_view = MapView.new()
	map_view.g = self
	map_view.custom_minimum_size = Vector2(0, 250)
	v.add_child(map_view)
	var bar := HFlowContainer.new()
	v.add_child(bar)
	btns.clear()
	for e in [["bless", "Bless (2)", bless], ["peace", "Sue for peace (3)", peace], ["calm", "Edict of calm (4)", calm], ["foresee", "Foresee (1)", foresee], ["rewind", "Rewind", rewind_epoch], ["end", "End epoch", end_epoch]]:
		btns[e[0]] = button(bar, e[1], e[2])
	log_lbl = RichTextLabel.new()
	log_lbl.bbcode_enabled = true
	log_lbl.scroll_following = true
	log_lbl.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(log_lbl)


func say(t: String) -> void:
	log_lbl.append_text(t + "\n")


func refresh() -> void:
	if map_view != null:
		map_view.queue_redraw()
	var mt := metric(tl.s)
	var war := []
	for g in tl.s["n_fac"]:
		if g != f and tl.s["war"][f][g] != 0:
			war.append(fname(g))
	status_lbl.text = "[b]%s[/b] — epoch %d/%d   influence %d   rewinds %d\nPeople %d   wealth %d %s   score %d / target %d   (this epoch %d)\nAt war with: %s    aggression %d" % [fname(f), epoch, D.DATA["epochs"], ip, rewinds, mt[0], mt[1], U["lexicon"]["currency"], score, target, score - epoch_start_score, ", ".join(war) if war.size() > 0 else "no one", tl.s["rules"]["world"]["aggro_pct"]]
	btns["bless"].disabled = ip < 2 or over
	btns["peace"].disabled = ip < 3 or over or _worst_enemy() < 0
	btns["calm"].disabled = ip < 4 or over or tl.s["rules"]["world"]["aggro_pct"] <= 1
	btns["foresee"].disabled = ip < 1 or over
	btns["rewind"].disabled = rewinds <= 0 or over or tl.tick() == epoch_start_tick and ip == epoch_start_ip
	btns["end"].disabled = over


func _poorest() -> int:
	var best := -1
	for n in tl.s["npcs"]:
		if n["alive"] and n["faction"] == f and (best < 0 or n["gold"] < tl.s["npcs"][best]["gold"]):
			best = n["id"]
	return best


func _worst_enemy() -> int:
	var best := -1
	for g in tl.s["n_fac"]:
		if g != f and tl.s["rel"][f][g] < 0 and (best < 0 or tl.s["rel"][f][g] < tl.s["rel"][f][best]):
			best = g
	return best


func bless() -> bool:
	var p := _poorest()
	if ip < 2 or p < 0:
		return false
	ip -= 2
	tl.intervene("give_gold", [p, 300])
	script_log.append(["bless"])
	sfx("pickup")
	say("You bless %s#%d with 300 %s." % [K.npc_name(tl.s["npcs"][p]), p, U["lexicon"]["currency"]])
	refresh()
	return true


func peace() -> bool:
	var g := _worst_enemy()
	if ip < 3 or g < 0:
		return false
	ip -= 3
	tl.intervene("set_rel", [f, g, 0])
	script_log.append(["peace"])
	sfx("pickup")
	say("Envoys reset relations between %s and %s." % [fname(f), fname(g)])
	refresh()
	return true


func calm() -> bool:
	var cur: int = tl.s["rules"]["world"]["aggro_pct"]
	if ip < 4 or cur <= 1:
		return false
	ip -= 4
	tl.intervene("set_rule", [maxi(1, cur - 2)], "world.aggro_pct")
	script_log.append(["calm"])
	sfx("pulse")
	say("An edict of calm lowers aggression across the world to %d." % maxi(1, cur - 2))
	refresh()
	return true


func foresee() -> Dictionary:
	if ip < 1:
		return {}
	ip -= 1
	var fk = tl.fork("foresight")
	var before := metric(tl.s)
	fk.step(D.DATA["epoch_ticks"])
	var after := metric(fk.s)
	script_log.append(["foresee"])
	say("[color=#%s]Foresight (forked timeline): people %d → %d, wealth %d → %d if you end the epoch now.[/color]" % [pal[3].to_html(false), before[0], after[0], before[1], after[1]])
	sfx("click")
	refresh()
	return {"people": after[0], "wealth": after[1]}


func rewind_epoch() -> bool:
	if rewinds <= 0:
		return false
	rewinds -= 1
	tl.rewind(epoch_start_tick)
	tl.truncate_future()
	ip = epoch_start_ip
	score = epoch_start_score
	script_log.append(["rewind"])
	shown = tl.s["events"].size()
	say("[color=yellow]Time folds back to the start of the epoch.[/color]")
	refresh()
	return true


func end_epoch() -> void:
	if over:
		return
	var s0: Dictionary = tl.s
	tl.step(D.DATA["epoch_ticks"])
	var mt := metric(tl.s)
	score += mt[2]
	script_log.append(["end"])
	var evs: Array = tl.s["events"]
	var n_kill := 0
	for i in range(shown, evs.size()):
		var ev: Array = evs[i]
		if ev[2] == K.EV_KILL:
			n_kill += 1
			if tl.s["npcs"][ev[4]]["faction"] == f:
				say("[color=salmon]%s of your people was slain in %s.[/color]" % [K.npc_name(tl.s["npcs"][ev[4]]), tname(ev[5])])
		elif ev[2] == K.EV_WAR:
			say("[color=salmon]WAR: %s and %s.[/color]" % [fname(ev[3]), fname(ev[4])])
		elif ev[2] == K.EV_PEACE:
			say("[color=lightgreen]PEACE: %s and %s.[/color]" % [fname(ev[3]), fname(ev[4])])
	shown = evs.size()
	say("The epoch passes. %d deaths across the world. Your people: %d." % [n_kill, mt[0]])
	sfx("hit" if n_kill > 3 else "click")
	if mt[0] < 3:
		finish(false, "Collapse: your people dwindled below three.")
	elif epoch >= D.DATA["epochs"]:
		finish(score >= target, "")
	else:
		new_epoch()
		return
	refresh()


func finish(won: bool, why: String) -> void:
	over = true
	sfx("win" if won else "lose")
	if won:
		save["best"] = maxi(int(save.get("best", 0)), score)
		write_save()
	var lore: Dictionary = U.get("lore", {})
	var body := "%s\nFinal score %d against a target of %d.\n\n%s" % ["The charge is fulfilled." if won else ("The charge fails. " + why), score, target, lore.get("epilogue_win" if won else "epilogue_lose", U.get("law_text", ""))]
	end_screen("Victory" if won else "Defeat", body, {"won": won, "score": score, "target": target, "epochs": epoch}, "Back to title", start)


# ---------------------------------------------------------------- headless verification
func bot_turn() -> void:
	if _worst_enemy() >= 0 and tl.s["war"][f][_worst_enemy()] != 0 and ip >= 3:
		peace()
	if tl.s["rules"]["world"]["aggro_pct"] > 2 and ip >= 4:
		calm()
	while ip >= 2:
		bless()
	end_epoch()


func selftest() -> Dictionary:
	var res := {"ok": false}
	# 1) do-nothing must lose (target is its score * margin)
	begin_game()
	while not over:
		end_epoch()
		await get_tree().process_frame
	res["do_nothing_score"] = score
	res["target"] = target
	var nothing_loses: bool = score < target
	# 2) rewind/foresight semantics
	begin_game()
	var d0 := K.digest_hex(tl.s)
	bless()
	foresee()
	var before_rw := K.digest_hex(tl.s)
	rewind_epoch()
	var rw_ok := K.digest_hex(tl.s) == d0 and ip == epoch_start_ip
	res["rewind_restores_epoch_start"] = rw_ok
	# 3) a competent bot must be able to win; record its script for the Python twin
	begin_game()
	var guard := 0
	while not over and guard < 30:
		guard += 1
		bot_turn()
		await get_tree().process_frame
	res["bot_score"] = score
	res["bot_won"] = score >= target and epoch >= D.DATA["epochs"]
	res["script"] = script_log
	res["final_digest"] = K.digest_hex(tl.s)
	res["final_tick"] = tl.tick()
	res["audio_loaded"] = sfx_players["win"].stream.data.size() > 1000 and music_player.stream.data.size() > 10000
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	rate_run(4, {"selftest": true})
	res["feedback_written"] = FileAccess.file_exists(FEEDBACK_PATH)
	res["ok"] = res["feedback_written"] and nothing_loses and rw_ok and res["bot_won"] and res["audio_loaded"] and res["save_written"]
	return res


func shot_prepare() -> void:
	begin_game()
	bless()
	foresee()
	end_epoch()
