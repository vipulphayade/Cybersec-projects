from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from bylaw_seed import build_dataset, build_relations
from embeddings import get_embedding_service


ROOT_DIR = Path(os.getenv("APP_ROOT", Path(__file__).resolve().parent))
if not (ROOT_DIR / "dataset").exists():
    ROOT_DIR = ROOT_DIR.parent
DEFAULT_DATASET_PATH = ROOT_DIR / "dataset" / "bylaws_dataset.json"


def serialize_embedding(vector: list[float]) -> str:
    rounded = [f"{value:.8f}" for value in vector]
    return "[" + ",".join(rounded) + "]"


def build_search_text(entry: dict[str, Any]) -> str:
    sections = [
        entry["law_name"],
        f"Section {entry['section']}",
        f"Subsection {entry['subsection']}" if entry.get("subsection") else "",
        entry["title"],
        entry["topic"],
        " ".join(entry.get("keywords", [])),
        entry["content"],
        entry["explanation"],
        entry["example"],
        " ".join(
            item["requirement"] + " " + item["plain_explanation"]
            for item in entry.get("conditions_required", [])
        ),
        " ".join(entry.get("possible_challenges", [])),
        " ".join(entry.get("related_statutes", [])),
    ]
    return " ".join(part for part in sections if part)


def _split_pipe_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item.strip() for item in value if item and item.strip()]
    return [item.strip() for item in value.split("|") if item.strip()]


def _split_condition_items(value: str | list[dict] | None) -> list[dict[str, str]]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    items = []
    for raw_item in value.split("|"):
        parts = [part.strip() for part in raw_item.split("::", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            items.append({"requirement": parts[0], "plain_explanation": parts[1]})
    return items


def load_dataset(dataset_path: str | None = None) -> list[dict[str, Any]]:
    path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if path.exists():
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if path.suffix.lower() == ".csv":
            rows: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    rows.append(
                        {
                            "law_name": row["law_name"],
                            "section": row["section"],
                            "subsection": row.get("subsection", ""),
                            "title": row["title"],
                            "topic": row["topic"],
                            "keywords": _split_pipe_list(row.get("keywords")),
                            "content": row["content"],
                            "explanation": row["explanation"],
                            "example": row["example"],
                            "conditions_required": _split_condition_items(
                                row.get("conditions_required")
                            ),
                            "possible_challenges": _split_pipe_list(
                                row.get("possible_challenges")
                            ),
                            "related_statutes": _split_pipe_list(
                                row.get("related_statutes")
                            ),
                        }
                    )
            return rows
    return build_dataset()


def ensure_vector_extension(db: Session) -> None:
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.commit()


def import_dataset(
    db: Session,
    dataset_path: str | None = None,
    replace_existing: bool = False,
) -> int:
    ensure_vector_extension(db)
    dataset = load_dataset(dataset_path)
    relations = build_relations(dataset)
    embedder = get_embedding_service()

    if replace_existing:
        db.execute(text("TRUNCATE TABLE bylaw_relations, bylaws RESTART IDENTITY CASCADE"))
        db.commit()

    search_texts = [build_search_text(entry) for entry in dataset]
    embeddings = embedder.encode(search_texts)

    for entry, search_text, embedding_vector in zip(dataset, search_texts, embeddings):
        embedding = serialize_embedding(embedding_vector)
        db.execute(
            text(
                """
                INSERT INTO bylaws (
                    section,
                    subsection,
                    title,
                    topic,
                    keywords,
                    content,
                    explanation,
                    example,
                    conditions_required,
                    possible_challenges,
                    related_statutes,
                    embedding
                ) VALUES (
                    :section,
                    :subsection,
                    :title,
                    :topic,
                    :keywords,
                    :content,
                    :explanation,
                    :example,
                    CAST(:conditions_required AS jsonb),
                    :possible_challenges,
                    :related_statutes,
                    CAST(:embedding AS vector)
                )
                ON CONFLICT (section, subsection, title)
                DO UPDATE SET
                    topic = EXCLUDED.topic,
                    keywords = EXCLUDED.keywords,
                    content = EXCLUDED.content,
                    explanation = EXCLUDED.explanation,
                    example = EXCLUDED.example,
                    conditions_required = EXCLUDED.conditions_required,
                    possible_challenges = EXCLUDED.possible_challenges,
                    related_statutes = EXCLUDED.related_statutes,
                    embedding = EXCLUDED.embedding
                """
            ),
            {
                "section": entry["section"],
                "subsection": entry.get("subsection", ""),
                "title": entry["title"],
                "topic": entry["topic"],
                "keywords": entry["keywords"],
                "content": entry["content"],
                "explanation": entry["explanation"],
                "example": entry["example"],
                "conditions_required": json.dumps(entry.get("conditions_required", [])),
                "possible_challenges": entry.get("possible_challenges", []),
                "related_statutes": entry.get("related_statutes", []),
                "embedding": embedding,
            },
        )

    db.execute(text("TRUNCATE TABLE bylaw_relations RESTART IDENTITY"))
    for relation in relations:
        db.execute(
            text(
                """
                INSERT INTO bylaw_relations (
                    source_section,
                    source_subsection,
                    target_section,
                    target_subsection
                ) VALUES (
                    :source_section,
                    :source_subsection,
                    :target_section,
                    :target_subsection
                )
                """
            ),
            relation,
        )

    db.commit()
    db.execute(text("ANALYZE bylaws"))
    db.commit()
    return len(dataset)


def ensure_seed_data(db: Session) -> int:
    dataset_size = len(load_dataset(os.getenv("DATASET_PATH")))
    minimum_expected = int(os.getenv("MINIMUM_DATASET_SIZE", str(dataset_size)))
    count = db.execute(text("SELECT COUNT(*) FROM bylaws")).scalar_one()
    missing_embeddings = db.execute(
        text("SELECT COUNT(*) FROM bylaws WHERE embedding IS NULL")
    ).scalar_one()

    if count < minimum_expected or missing_embeddings > 0:
        return import_dataset(db, replace_existing=(count == 0))
    return count
