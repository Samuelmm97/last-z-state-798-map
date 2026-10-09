"""Import a completed native State 798 roster export into atlas power data."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.source.open(encoding="utf-8-sig", newline="")))
    assert rows and all(r["state"] == "798" for r in rows), "Expected State 798 only"
    assert len({r["uid"] for r in rows}) == len(rows), "Duplicate player IDs"
    hqs = json.loads(Path("data/hqs.json").read_text(encoding="utf-8"))
    path = Path("data/power.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    by_uid, by_pair = collections.defaultdict(list), collections.defaultdict(list)
    normalize = lambda s: " ".join(s.casefold().split())
    for h in hqs:
        if h.get("identity_alias_of") is not None:
            continue
        if h.get("playerId"):
            by_uid[str(h["playerId"])].append(h)
        by_pair[(normalize(h["name"]), normalize(h.get("tag", "")))].append(h)
    players = data["players"]
    by_atlas = {p["atlas_id"]: k for k, p in players.items() if p.get("atlas_id") is not None}
    matched = collections.Counter()
    used = set()
    for r in rows:
        candidates = by_uid[r["uid"]]
        method = "player_id"
        if not candidates:
            candidates = [h for h in by_pair[(normalize(r["name"]), normalize(r["allianceTag"]))]
                          if not h.get("playerId") or str(h["playerId"]) == r["uid"]]
            method = "unique_name_and_tag"
        current = [h for h in candidates if h.get("current") is not False]
        if len(current) == 1:
            candidates = current
        h = candidates[0] if len(candidates) == 1 else None
        assert h is None or h["id"] not in used, "Two roster players matched the same HQ"
        key = by_atlas.get(h["id"]) if h else None
        key = key or "native_uid_" + r["uid"]
        p = players.setdefault(key, {})
        p.update(name=r["name"], tag=r["allianceTag"],
                 display=f"[{r['allianceTag']}] {r['name']}", playerId=r["uid"])
        value = int(r["power"])
        assert value >= 0
        previous = p.get("personal_power", {})
        previous_date = previous.get("data_date") or previous.get("captured_date") or data.get("captured_date", "")
        if previous_date <= args.date:
            p["personal_power"] = {"value": value, "rank": None, "source": "alliance_member_roster",
                                   "data_date": args.date, "captured_date": args.date,
                                   "approximate": False, "reading_review": "verified_native_numeric"}
        if h:
            used.add(h["id"])
            p.update(atlas_id=h["id"], atlas={k: h.get(k) for k in ("hq", "name", "x", "y", "zone")},
                     match="native_roster_" + method)
            matched[method] += 1
        else:
            matched["unmatched"] += 1
    # Historical board identities can share an HQ after alliance/name changes.
    # Keep the newest roster identity linked; retain other readings as history.
    groups = collections.defaultdict(list)
    for key, player in players.items():
        if player.get("atlas_id") is not None:
            groups[player["atlas_id"]].append((key, player))
    for entries in groups.values():
        if len(entries) < 2:
            continue
        winner = max(enumerate(entries), key=lambda item: (
            item[1][1].get("personal_power", {}).get("data_date") or
            item[1][1].get("personal_power", {}).get("captured_date") or "", item[0]))[1][0]
        for key, player in entries:
            if key != winner:
                player["historical_atlas_id"] = player.pop("atlas_id")
                player.pop("atlas", None)
                player["match"] = "historical_duplicate_identity"
    report = {"state": "798", "data_date": args.date, "source": "game alliance member roster API",
              "source_file": args.source.name, "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
              "players": len(rows), "alliances": len({r["allianceId"] for r in rows}),
              "matches": dict(matched),
              "scope": "All collected listed alliances; unlisted alliances and unaffiliated players are not covered."}
    alliance_path = args.source.with_name("state-798-alliances.csv")
    if alliance_path.exists():
        alliances = list(csv.DictReader(alliance_path.open(encoding="utf-8-sig", newline="")))
        assert all(r["serverId"] == "798" for r in alliances)
        assert len({r["abbr"] for r in alliances}) == len(alliances), "Ambiguous alliance tags"
        for r in alliances:
            entry = data.setdefault("alliances", {}).setdefault(r["abbr"], {})
            previous = entry.get("alliance_power", {})
            previous_date = previous.get("data_date") or data.get("captured_date", "")
            if previous_date <= args.date:
                entry.update(tag=r["abbr"], display=f"[{r['abbr']}]{r['alliancename']}", allianceId=r["uid"])
                entry["alliance_power"] = {"rank": int(r["rank"]), "value": int(r["fightpower"]),
                                           "data_date": args.date, "source": "game_alliance_power_list"}
        report["alliance_rankings"] = len(alliances)
        report["alliance_source_sha256"] = hashlib.sha256(alliance_path.read_bytes()).hexdigest()
    data["native_roster_import"] = report
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    Path("data/roster-power-import.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
