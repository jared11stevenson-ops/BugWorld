"""Human feedback intake. The games write user://feedback.jsonl (one JSON record per rating). Import it into the studio's knowledge store:
  python3 -m studio feedback import path/to/feedback.jsonl
Self-test records are ignored. Only per-game aggregates are stored (universe-independent)."""
import json


def load_records(path):
    out = []
    for line in open(path):
        line = line.strip()
        if line:
            r = json.loads(line)
            if not r.get("ctx", {}).get("selftest"):
                out.append(r)
    return out


def aggregate(know, records):
    fb = know.setdefault("human_feedback", {})
    for r in records:
        g = fb.setdefault(r["game"], {"n": 0, "sum": 0, "by_rating": {str(i): 0 for i in range(1, 6)}})
        g["n"] += 1
        g["sum"] += int(r["rating"])
        g["by_rating"][str(int(r["rating"]))] += 1
    return {k: {"n": v["n"], "mean": round(v["sum"] / v["n"], 2)} for k, v in fb.items()}
