import argparse
import json
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
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise InvalidFindings(f"findings[{index}] is not an object")
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


def _matches_test(entry_test, finding):
    path, _, name = entry_test.partition("::")
    return finding["file"] == path and finding.get("test") in (name, entry_test)


def _matches_file(entry, finding):
    if finding["file"] != entry["test"]:
        return False
    return "match_keywords" not in entry or _mentions_any(entry["match_keywords"], finding)


def _matches_anywhere(entry, finding):
    return _mentions_any(entry["match_keywords"], finding)


def _is_repo_wide(entry):
    return entry["test"] == "repo" or entry["test"].startswith("git:")


def _matches(entry, finding):
    if _is_repo_wide(entry):
        return _matches_anywhere(entry, finding)
    if "::" in entry["test"]:
        return _matches_test(entry["test"], finding)
    return _matches_file(entry, finding)


def _grade_plant(plant, findings, mode):
    seen = [f["tier"] for f in findings if _matches(plant, f)]
    accepted = plant["expected"][mode]
    return {
        "hit": bool(seen),
        "tier_ok": any(t in accepted for t in seen) if seen else "OMITTED" in accepted,
        "tiers_seen": seen,
    }


def _matches_any(entries, finding):
    return any(_matches(entry, finding) for entry in entries)


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
    plants = {p["id"]: _grade_plant(p, findings, mode) for p in key["plants"]}
    decoys = {d["id"]: {"false_positive": any(_matches(d, f) for f in findings)} for d in key["decoys"]}
    known_noise = key.get("known_noise", [])
    known_noise_count = sum(_matches_any(known_noise, f) for f in findings)
    keyed = key["plants"] + key["decoys"] + known_noise
    unkeyed = [f for f in findings if not _matches_any(keyed, f)]
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
