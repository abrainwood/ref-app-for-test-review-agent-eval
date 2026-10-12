import argparse
import json
import logging
import re
import sys
from pathlib import Path

ANSWER_KEY = Path(__file__).resolve().parent / "answer_key.json"
SCHEMA = Path(__file__).resolve().parent / "findings.schema.json"


LOGGER = logging.getLogger("grade")
UNRATED = "UNRATED"


class InvalidFindings(ValueError):
    pass


def validate(findings_doc, schema):
    item = schema["properties"]["findings"]["items"]
    findings = findings_doc.get("findings") if isinstance(findings_doc, dict) else None
    if not isinstance(findings, list):
        raise InvalidFindings("top level must be an object with a 'findings' list")
    unexpected_top_level = sorted(findings_doc.keys() - schema["properties"].keys())
    if unexpected_top_level:
        raise InvalidFindings(f"unexpected top-level key {unexpected_top_level[0]!r}")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise InvalidFindings(f"findings[{index}] is not an object")
        extra_keys = sorted(finding.keys() - item["properties"].keys())
        if extra_keys:
            LOGGER.warning("findings[%d] has extra keys %s, ignored", index, extra_keys)
        for field in item["required"]:
            if field not in finding:
                raise InvalidFindings(f"findings[{index}] is missing '{field}'")
        if finding["tier"] not in [*item["properties"]["tier"]["enum"], UNRATED]:
            raise InvalidFindings(f"findings[{index}] has invalid tier {finding['tier']!r}")
        for field in ("file", "category", "summary"):
            if not isinstance(finding[field], str):
                raise InvalidFindings(f"findings[{index}].{field} must be a string")
        if finding["test"] is not None and not isinstance(finding["test"], str):
            raise InvalidFindings(f"findings[{index}].test must be a string or null")


def _as_whole_word(keyword):
    return re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)


def _mentions_any(keywords, finding):
    text = f"{finding['category']} {finding['summary']}"
    return any(_as_whole_word(keyword).search(text) for keyword in keywords)


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


def _placement_match(entry, finding):
    own_file = _nodeids(entry)[0].partition("::")[0]
    placements = entry.get("files", []) + ([own_file] if finding["test"] is None else [])
    on_placement = any(_same_path(finding["file"], path) for path in placements)
    return on_placement and "match_keywords" in entry and _keywords_ok(entry, finding)


def _anchored(entry, finding):
    on_anchor_file = any(_same_path(finding["file"].lower(), anchor.lower()) for anchor in entry["files"])
    return on_anchor_file or any(_as_whole_word(anchor).search(finding["summary"]) for anchor in entry["files"])


def _match_level(entry, finding):
    if _is_repo_wide(entry):
        repo_hit = finding["test"] is None and _anchored(entry, finding) and _mentions_any(entry["match_keywords"], finding)
        return REPO_LEVEL if repo_hit else None
    if "::" in _nodeids(entry)[0]:
        if _test_level_match(entry, finding):
            return TEST_LEVEL
        return FILE_LEVEL if _placement_match(entry, finding) else None
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


def _is_test_level(entry):
    return not _is_repo_wide(entry) and "::" in _nodeids(entry)[0]


def _lands_on(entry, finding):
    if _is_repo_wide(entry):
        return finding["test"] is None and any(
            _same_path(finding["file"].lower(), anchor.lower()) for anchor in entry["files"])
    if _is_test_level(entry):
        names_the_test = any(_same_path(finding["file"], nodeid.partition("::")[0])
                             and finding["test"] == nodeid.partition("::")[2] for nodeid in _nodeids(entry))
        own_file = _nodeids(entry)[0].partition("::")[0]
        on_file = finding["test"] is None and _same_path(finding["file"], own_file)
        return names_the_test or on_file or any(_same_path(finding["file"], f) for f in entry.get("files", []))
    return any(_same_path(finding["file"], path) for path in [entry["test"], *entry.get("files", [])])


def _near_misses(entries, findings, claimed):
    near = []
    for index, finding in enumerate(map(_normalised, findings)):
        candidates = [e["id"] for e in entries if _lands_on(e, finding)]
        if index not in claimed and candidates:
            near.append({"index": index, "finding": findings[index], "candidates": candidates})
    return near


def _tier_accepted(plant, finding, mode):
    conditional = plant.get("conditional_expected")
    return finding["tier"] in plant["expected"][mode] or bool(
        conditional and finding["tier"] in conditional[mode] and _mentions_any(conditional["keywords"], finding))


def _grade_plant(plant, findings, matched, mode):
    seen = [findings[i]["tier"] for i in matched]
    return {
        "hit": bool(matched),
        "tier_ok": any(_tier_accepted(plant, findings[i], mode) for i in matched) if matched
        else "OMITTED" in plant["expected"][mode],
        "tiers_seen": seen,
        "matched": matched,
    }


def _summarise(plants, decoys, unkeyed, near_misses, known_noise_count):
    return {
        "plants_total": len(plants),
        "plants_hit": sum(p["hit"] for p in plants.values()),
        "plants_tier_ok": sum(p["tier_ok"] for p in plants.values()),
        "decoys_total": len(decoys),
        "false_positives": sum(d["false_positive"] for d in decoys.values()),
        "unkeyed": len(unkeyed),
        "near_misses": len(near_misses),
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
    near_misses = _near_misses(plant_entries + decoy_entries, findings, claimed)
    return {
        "mode": mode,
        "plants": plants,
        "decoys": decoys,
        "unkeyed": unkeyed,
        "near_misses": near_misses,
        "known_noise_count": known_noise_count,
        "summary": _summarise(plants, decoys, unkeyed, near_misses, known_noise_count),
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
