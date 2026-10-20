# Game 1: concept campaign. Three trials, each with its own discovered rule set; best of 3 matches vs an escalating rival.
extends "res://ghost/shell.gd"

const C = preload("res://ghost/concept.gd")
const CAM = preload("res://data/campaign.gd")
const RIVALS := {7: "Wanderer (random)", 9: "Mimic (counters your last move)", 8: "Strategist (adaptive)"}

var chapter := 0
var attempt := 0
var match_no := 0
var wins := 0
var spec: Dictionary
var m: Dictionary
var h_opp: Dictionary
var opp_pid := 7
var human_actions: Array = []
var records: Array = []
var btns: Array = []
var state_lbl: RichTextLabel
var log_lbl: RichTextLabel
var next_btn: Button
var seed_base := 1


func start() -> void:
	game_id = "concept_campaign"
	var entries := [["New campaign", func(): chapter = 0; save["chapter"] = 0; show_intro()]]
	if int(save.get("chapter", 0)) > 0 and int(save["chapter"]) < CAM.CAMPAIGN["chapters"].size():
		entries.append(["Continue (trial %d)" % (int(save["chapter"]) + 1), func(): chapter = int(save["chapter"]); show_intro()])
	entries.append(["How to play", show_help])
	title_screen(U.get("game_title", "Trials"), CAM.CAMPAIGN["tagline"] + "\n" + universe_line(), entries)


func show_help() -> void:
	text_screen("How to play", "Each turn you and your rival choose an action at the same time. Hover an action to read exactly what it does; the rules list on each trial screen is complete.\nWin the trial's end condition before your rival does. Win 2 of 3 duels to clear a trial. The rival grows smarter each duel.", "Back", start)


func show_intro() -> void:
	var ch: Dictionary = CAM.CAMPAIGN["chapters"][chapter]
	spec = ch["spec"]
	attempt += 1
	match_no = 0
	wins = 0
	text_screen("Trial %d of %d: %s" % [chapter + 1, CAM.CAMPAIGN["chapters"].size(), ch["title"]], ch["blurb"] + "\n\n" + ch["text"], "Begin", begin_match)


func begin_match() -> void:
	var ch: Dictionary = CAM.CAMPAIGN["chapters"][chapter]
	opp_pid = ch["ladder"][match_no]
	seed_base = int(U.get("seed", 1)) * 1000 + chapter * 100 + attempt * 10 + match_no
	m = C.new_match(spec, seed_base)
	h_opp = C.new_hist(spec["actions"].size())
	human_actions = []
	btns = []
	var v := clear()
	label(v, "%s — duel %d of 3 vs %s    (wins %d)" % [spec["name"], match_no + 1, RIVALS[opp_pid], wins], 22, 2)
	state_lbl = RichTextLabel.new()
	state_lbl.bbcode_enabled = true
	state_lbl.custom_minimum_size = Vector2(0, 60)
	v.add_child(state_lbl)
	var bar := HFlowContainer.new()
	v.add_child(bar)
	for i in spec["actions"].size():
		var b := button(bar, spec["actions"][i]["name"], func(): act(i))
		b.tooltip_text = C.action_tooltip(spec, i)
		btns.append(b)
	log_lbl = RichTextLabel.new()
	log_lbl.size_flags_vertical = Control.SIZE_EXPAND_FILL
	log_lbl.scroll_following = true
	log_lbl.bbcode_enabled = true
	v.add_child(log_lbl)
	next_btn = button(v, "Continue", after_match)
	next_btn.visible = false
	refresh()


func vars_line(who: int) -> String:
	var parts := []
	for vd in spec["vars"]:
		parts.append("%s %d" % [vd[0], m["p"][who][vd[0]]])
	return ", ".join(parts)


func refresh() -> void:
	state_lbl.text = "[color=#%s]You: %s[/color]\n[color=#%s]Rival: %s[/color]    round %d" % [pal[3].to_html(false), vars_line(0), pal[2].to_html(false), vars_line(1), m["round"]]
	for i in btns.size():
		btns[i].disabled = m["done"] != 0 or not C.is_legal(spec, m, 0, i)


func act(i: int) -> void:
	if m["done"] != 0:
		return
	var a1 := C.choose(spec, opp_pid, m, 1, h_opp)
	var s := C.step(spec, m, i, a1)
	C.observe(h_opp, s[0])
	human_actions.append(s[0])
	log_lbl.append_text("Round %d: you [b]%s[/b], rival [b]%s[/b]\n" % [m["round"], spec["actions"][s[0]]["name"], spec["actions"][s[1]]["name"]])
	if m["done"] != 0:
		var won: bool = m["winner"] == 0
		if won:
			wins += 1
		sfx("win" if won else "lose")
		log_lbl.append_text("\n[b]%s[/b] after %d rounds%s\n" % ["YOU WIN" if won else ("DRAW" if m["winner"] == -1 else "YOU LOSE"), m["round"], " (time limit)" if m["timeout"] != 0 else ""])
		records.append({"concept": spec["id"], "seed": seed_base, "opp": opp_pid, "actions": human_actions.duplicate(), "winner": m["winner"], "rounds": m["round"], "digest": C.match_digest(spec, m)})
		next_btn.visible = true
	else:
		sfx("click")
	refresh()


func after_match() -> void:
	match_no += 1
	if match_no < 3:
		begin_match()
		return
	if wins >= 2:
		chapter += 1
		save["chapter"] = chapter
		save["best"] = int(save.get("best", 0)) + wins
		write_save()
		if chapter >= CAM.CAMPAIGN["chapters"].size():
			text_screen("The %s is yours" % U.get("name", "world"), "You mastered every trial.\n\n" + U.get("law_text", "") + "\n\nInspired by: " + ", ".join(U.get("inspirations", [])), "Back to title", start)
		else:
			text_screen("Trial cleared", "You won %d of 3 duels. The next trial changes the rules entirely." % wins, "Next trial", show_intro)
	else:
		text_screen("Trial failed", "You won %d of 3 duels. Study the rules and try again." % wins, "Retry trial", show_intro)


# ---------------------------------------------------------------- headless verification: a bot plays the real campaign UI path
func selftest() -> Dictionary:
	save["chapter"] = 0
	chapter = 0
	attempt = 0
	var n_ch: int = CAM.CAMPAIGN["chapters"].size()
	var res := {"ok": false, "chapters_cleared": 0, "attempts": 0, "matches": 0}
	var guard := 0
	show_intro()
	begin_match()
	while chapter < n_ch and guard < 80:
		guard += 1
		while m["done"] == 0:
			act(_bot_action())
		after_match()                    # the real game path: next duel, trial result, ending
		await get_tree().process_frame
		if match_no < 3:
			continue
		res["attempts"] += 1
		if chapter >= n_ch:
			break
		show_intro()
		begin_match()
	res["chapters_cleared"] = chapter
	res["matches"] = records.size()
	res["records"] = records
	res["audio_loaded"] = sfx_players["win"].stream.data.size() > 1000 and music_player.stream.data.size() > 10000
	res["universe_loaded"] = U.has("name") and pal.size() == 5
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	res["ok"] = chapter >= n_ch and res["audio_loaded"] and res["universe_loaded"] and res["save_written"]
	return res


# Verification bot: simulates each of its options against an exact copy of the rival's decision (1-ply lookahead). It proves a
# trial is winnable by a clever player; it says nothing about how hard it is for humans.
func _bot_action() -> int:
	var best := 0
	var bv := -1000000000
	for a in spec["actions"].size():
		if not C.is_legal(spec, m, 0, a):
			continue
		var mm := m.duplicate(true)
		var hh := h_opp.duplicate(true)
		var a1 := C.choose(spec, opp_pid, mm, 1, hh)
		C.step(spec, mm, a, a1)
		var v := C.value(spec, mm, 0)
		if mm["done"] != 0:
			v += 100000 if mm["winner"] == 0 else (-100000 if mm["winner"] == 1 else 0)
		if v > bv:
			bv = v
			best = a
	return best


func shot_prepare() -> void:
	show_intro()
	begin_match()
	act(0)
