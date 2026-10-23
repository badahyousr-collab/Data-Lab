"""Small command line interface with no third-party dependencies."""

import argparse
import json
from pathlib import Path
from .export import export
from .generate import generate
from .pipeline import DataError, load, metrics


def main():
    parser = argparse.ArgumentParser(description="Synthetic retail analytics")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="generate deterministic CSV")
    seed.add_argument("--output", type=Path, default=Path("data/demo"))
    seed.add_argument("--control", action="store_true")
    seed.add_argument("--orders", type=int, default=60)
    for name in ("load", "report", "export"):
        sub = commands.add_parser(name)
        sub.add_argument("--database", type=Path, default=Path("data/sales.db"))
        if name == "load":
            sub.add_argument("--input", type=Path, default=Path("data/demo"))
        if name == "export":
            sub.add_argument("--output", type=Path, default=Path("web/data.json"))
    args = parser.parse_args()
    try:
        if args.command == "seed":
            if args.orders < 1:
                parser.error("--orders must be positive")
            generate(args.output, args.control, args.orders)
            print(f"Synthetic CSV: {args.output}")
        elif args.command == "load":
            print(json.dumps(load(args.input, args.database), ensure_ascii=False))
        elif args.command == "report":
            print(json.dumps(metrics(args.database), ensure_ascii=False))
        elif args.command == "export":
            print(f"Exported {export(args.database, args.output)} item rows to {args.output}")
    except (DataError, FileNotFoundError, OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
