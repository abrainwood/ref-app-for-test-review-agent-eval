"""Command-line interface for the calculator."""

import sys

from calculator import add, divide, multiply, subtract

OPS = {
    "add": add,
    "sub": subtract,
    "mul": multiply,
    "div": divide,
}

USAGE = "usage: cli.py {add|sub|mul|div} A B"


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if len(argv) != 4 or argv[1] not in OPS:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        a = float(argv[2])
        b = float(argv[3])
    except ValueError:
        print("error: A and B must be numbers", file=sys.stderr)
        return 2
    try:
        result = OPS[argv[1]](a, b)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
