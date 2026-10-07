import json
import sys
from pathlib import Path


def _rate(flags):
    return sum(flags) / len(flags)


def _count_stats(counts):
    return {"per_run": counts, "mean": sum(counts) / len(counts)}


class InvalidReports(ValueError):
    pass


def _single_mode(reports):
    if not reports:
        raise InvalidReports("no reports given")
    modes = {r["mode"] for r in reports}
    if len(modes) > 1:
        raise InvalidReports(f"mixed modes: {sorted(modes)}")
    return modes.pop()


def summarise(reports):
    mode = _single_mode(reports)
    plant_ids = reports[0]["plants"]
    decoy_ids = reports[0]["decoys"]
    return {
        "mode": mode,
        "runs": len(reports),
        "plants": {
            pid: {
                "hit_rate": _rate([r["plants"][pid]["hit"] for r in reports]),
                "tier_ok_rate": _rate([r["plants"][pid]["tier_ok"] for r in reports]),
            }
            for pid in plant_ids
        },
        "decoys": {
            did: {"false_positive_rate": _rate([r["decoys"][did]["false_positive"] for r in reports])}
            for did in decoy_ids
        },
        "unkeyed": _count_stats([len(r["unkeyed"]) for r in reports]),
        "near_misses": _count_stats([len(r["near_misses"]) for r in reports]),
        "known_noise": _count_stats([r["known_noise_count"] for r in reports]),
    }


def main(paths):
    reports = [json.loads(Path(p).read_text()) for p in paths]
    try:
        summary = summarise(reports)
    except InvalidReports as error:
        print(f"cannot summarise: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
