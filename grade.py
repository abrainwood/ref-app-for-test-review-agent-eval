import argparse
import json
import re
import sys
from pathlib import Path

ANSWER_KEY = Path(__file__).resolve().parent / "answer_key.json"
SCHEMA = Path(__file__).resolve().parent / "findings.schema.json"


class InvalidFindings(ValueError):
    pass


def validate(findings_doc, schema):
    item = schema["properties"]["findings"]["items"]
    findings = findings_doc.get("findings") if isinstance(findings_doc, dict) else None
    if not isinstance(findings, list):
        raise InvalidFindings("top level must be an object with a 'findings' list")
    for key in findings_doc.keys() - schema["properties"].keys():
        raise InvalidFindings(f"unexpected top-level key {key!r}")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise InvalidFindings(f"findings[{index}] is not an object")
        for key in finding.keys() - item["properties"].keys():
            raise InvalidFindings(f"findings[{index}] has unexpected key {key!r}")
        for field in item["required"]:
            if field not in finding:
                raise InvalidFindings(f"findings[{index}] is missing '{field}'")
        if finding["tier"] not in item["properties"]["tier"]["enum"]:
            raise InvalidFindings(f"findings[{index}] has invalid tier {finding['tier']!r}")
        for field in ("file", "category", "summary"):
            if not isinstance(finding[field], str):
                raise InvalidFindings(f"findings[{index}].{field} must be a string")
        if finding["test"] is not None and not isinstance(finding["test"], str):
            raise InvalidFindings(f"findings[{index}].test must be a string or null")


def _mentions_any(keywords, finding):
    text = f"{finding['category']} {finding['summary']}".lower()
    return any(keyword.lower() in text for keyword in keywords)


def _keywords_ok(entry, finding):
    return "match_keywords" not in entry or _mentions_any(entry["match_keywords"], finding)


LINE_SUFFIX = re.compile(r":\d+(:\d+)?$")
PARAM_SUFFIX = re.compile(r"\[.*\]$")


def _normalise_file(raw):
    path, _, name = raw.strip().replace("\\", "/").partition("::")
    path = LINE_SUFFIX.sub("", path)
    while path.startswith("./"):
        path = path[2:]
    return path, name


def _normalise_test(raw):
    name = PARAM_SUFFIX.sub("", raw.strip()).removesuffix("()")
    return name.split("::")[-1] or None


def _normalised(finding):
    path, name_in_file = _normalise_file(finding["file"])
    raw_test = finding.get("test") or name_in_file
    test = _normalise_test(raw_test) if raw_test else None
    return {**finding, "file": path, "test": test}


def _same_path(found, wanted):
    return found == wanted or found.endswith("/" + wanted)


def _nodeids(entry):
    return entry.get("tests") or [entry["test"]]


def _is_repo_wide(entry):
    return entry["test"] == "repo" or entry["test"].startswith("git:")


TEST_LEVEL, FILE_LEVEL, REPO_LEVEL = 0, 1, 2


def _test_level_match(entry, finding):
    for nodeid in _nodeids(entry):
        path, _, name = nodeid.partition("::")
        if _same_path(finding["file"], path) and finding["test"] == name:
            return _keywords_ok(entry, finding)
    return False


def _file_level_match(entry, finding):
    paths = [entry["test"], *entry.get("files", [])]
    return any(_same_path(finding["file"], path) for path in paths) and _keywords_ok(entry, finding)


def _match_level(entry, finding):
    if _is_repo_wide(entry):
        repo_hit = finding["test"] is None and _mentions_any(entry["match_keywords"], finding)
        return REPO_LEVEL if repo_hit else None
    if "::" in _nodeids(entry)[0]:
        if _test_level_match(entry, finding):
            return TEST_LEVEL
        extra = any(_same_path(finding["file"], path) for path in entry.get("files", []))
        return FILE_LEVEL if extra and _keywords_ok(entry, finding) else None
    return FILE_LEVEL if _file_level_match(entry, finding) else None


def _claims(entries, finding):
    levels = [(_match_level(e, finding), position) for position, e in enumerate(entries)]
    matching = [(level, position) for level, position in levels if level is not None]
    if not matching:
        return set()
    best = min(level for level, _ in matching)
    return {position for level, position in matching if level == best}


def _matched_by_entry(entries, findings):
    matched = {position: [] for position in range(len(entries))}
    for index, finding in enumerate(map(_normalised, findings)):
        for position in _claims(entries, finding):
            matched[position].append(index)
    return matched


def _grade_plant(plant, findings, matched, mode):
    seen = [findings[i]["tier"] for i in matched]
    accepted = plant["expected"][mode]
    return {
        "hit": bool(matched),
        "tier_ok": any(t in accepted for t in seen) if seen else "OMITTED" in accepted,
        "tiers_seen": seen,
        "matched": matched,
    }


def _summarise(plants, decoys, unkeyed, known_noise_count):
    return {
        "plants_total": len(plants),
        "plants_hit": sum(p["hit"] for p in plants.values()),
        "plants_tier_ok": sum(p["tier_ok"] for p in plants.values()),
        "decoys_total": len(decoys),
        "false_positives": sum(d["false_positive"] for d in decoys.values()),
        "unkeyed": len(unkeyed),
        "known_noise": known_noise_count,
    }


def grade(findings_doc, key, mode):
    findings = findings_doc["findings"]
    plant_entries, decoy_entries = key["plants"], key["decoys"]
    noise_entries = key.get("known_noise", [])
    entries = plant_entries + decoy_entries + noise_entries
    matched = _matched_by_entry(entries, findings)
    decoy_offset = len(plant_entries)
    noise_offset = decoy_offset + len(decoy_entries)
    plants = {p["id"]: _grade_plant(p, findings, matched[i], mode) for i, p in enumerate(plant_entries)}
    decoys = {d["id"]: {"false_positive": bool(matched[decoy_offset + i]), "matched": matched[decoy_offset + i]}
              for i, d in enumerate(decoy_entries)}
    claimed = {index for indexes in matched.values() for index in indexes}
    known_noise_count = len({i for position in range(noise_offset, len(entries)) for i in matched[position]})
    unkeyed = [f for index, f in enumerate(findings) if index not in claimed]
    return {
        "mode": mode,
        "plants": plants,
        "decoys": decoys,
        "unkeyed": unkeyed,
        "known_noise_count": known_noise_count,
        "summary": _summarise(plants, decoys, unkeyed, known_noise_count),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grade a findings JSON against the answer key")
    parser.add_argument("findings")
    parser.add_argument("--mode", required=True, choices=["slice", "whole_suite"])
    args = parser.parse_args(argv)
    try:
        doc = json.loads(Path(args.findings).read_text())
        validate(doc, json.loads(SCHEMA.read_text()))
    except (OSError, ValueError) as error:
        print(f"invalid findings file {args.findings}: {error}", file=sys.stderr)
        return 2
    key = json.loads(ANSWER_KEY.read_text())
    print(json.dumps(grade(doc, key, args.mode), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
