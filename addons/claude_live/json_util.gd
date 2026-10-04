@tool
extends RefCounted
## JSON.stringify leaves raw control characters (e.g. ESC from colored logs) unescaped, which strict
## clients reject. Everything that leaves the plugin as JSON goes through here.

static func stringify(v: Variant, indent: String = "") -> String:
	var s := JSON.stringify(v, indent)
	var re := RegEx.create_from_string("[\\x00-\\x1f]")
	var ms := re.search_all(s)
	for i in range(ms.size() - 1, -1, -1):
		var m := ms[i]
		var c := m.get_string().unicode_at(0)
		if indent != "" and (c == 10 or c == 13 or c == 9):
			continue  # whitespace emitted by pretty-printing is legal between tokens
		s = s.substr(0, m.get_start()) + "\\u%04x" % c + s.substr(m.get_end())
	return s
