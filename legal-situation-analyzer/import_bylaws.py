from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "api"))

from database import SessionLocal  # noqa: E402
from import_service import DEFAULT_DATASET_PATH, import_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Maharashtra housing society bye-laws into PostgreSQL."
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Path to JSON or CSV dataset file. Defaults to the bundled JSON dataset.",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Truncate and fully reload existing laws before import.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = SessionLocal()
    try:
        imported = import_dataset(
            session,
            dataset_path=args.dataset,
            replace_existing=args.replace_existing,
        )
        print(f"Imported {imported} bye-law entries from {args.dataset}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
