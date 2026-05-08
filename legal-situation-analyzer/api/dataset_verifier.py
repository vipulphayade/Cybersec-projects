from __future__ import annotations

import logging
import string

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def _normalize_subsection(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    return cleaned.strip("()")


def verify_sections(db: Session) -> list[int]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT CAST(section AS INTEGER) AS section_number
            FROM bylaws
            WHERE section ~ '^[0-9]+$'
            ORDER BY section_number
            """
        )
    ).scalars().all()

    if not rows:
        logger.warning("Dataset sanity check: no numeric sections found in bylaws table.")
        return []

    max_section = max(rows)
    existing = set(rows)
    missing = [number for number in range(1, max_section + 1) if number not in existing]
    if missing:
        logger.warning("Dataset sanity check: missing section numbers detected: %s", missing)
    return missing


def verify_subsections(db: Session) -> list[dict[str, object]]:
    rows = db.execute(
        text(
            """
            SELECT section, subsection
            FROM bylaws
            WHERE subsection IS NOT NULL AND subsection <> ''
            ORDER BY
                CASE WHEN section ~ '^[0-9]+$' THEN CAST(section AS INTEGER) END NULLS LAST,
                section,
                subsection
            """
        )
    ).all()

    grouped: dict[str, list[str]] = {}
    for row in rows:
        section = row.section
        subsection = _normalize_subsection(row.subsection)
        if len(subsection) == 1 and subsection in string.ascii_lowercase:
            grouped.setdefault(section, []).append(subsection)

    gaps: list[dict[str, object]] = []
    for section, subsections in grouped.items():
        ordered = sorted(set(subsections))
        if not ordered:
            continue
        start = ord("a")
        end = ord(ordered[-1])
        missing = [chr(code) for code in range(start, end + 1) if chr(code) not in ordered]
        if missing:
            gap = {"section": section, "missing_subsections": missing}
            gaps.append(gap)
            logger.warning(
                "Dataset sanity check: section %s has missing subsection letters: %s",
                section,
                missing,
            )
    return gaps


def verify_duplicates(db: Session) -> list[dict[str, object]]:
    rows = db.execute(
        text(
            """
            SELECT section, subsection, COUNT(*) AS duplicate_count
            FROM bylaws
            GROUP BY section, subsection
            HAVING COUNT(*) > 1
            ORDER BY section, subsection
            """
        )
    ).all()

    duplicates = [
        {
            "section": row.section,
            "subsection": row.subsection or None,
            "count": row.duplicate_count,
        }
        for row in rows
    ]
    if duplicates:
        logger.warning("Dataset sanity check: duplicate section/subsection pairs found: %s", duplicates)
    return duplicates


def verify_missing_text(db: Session) -> list[dict[str, object]]:
    rows = db.execute(
        text(
            """
            SELECT section, subsection
            FROM bylaws
            WHERE content IS NULL
               OR LENGTH(TRIM(content)) < 40
            ORDER BY section, subsection
            """
        )
    ).all()

    missing = [
        {"section": row.section, "subsection": row.subsection or None}
        for row in rows
    ]
    if missing:
        logger.warning("Dataset sanity check: missing or too-short bye-law text found: %s", missing)
    return missing


def verify_embeddings(db: Session) -> list[dict[str, object]]:
    rows = db.execute(
        text(
            """
            SELECT section, subsection
            FROM bylaws
            WHERE embedding IS NULL
            ORDER BY section, subsection
            """
        )
    ).all()

    missing = [
        {"section": row.section, "subsection": row.subsection or None}
        for row in rows
    ]
    if missing:
        logger.warning("Dataset sanity check: missing embeddings found: %s", missing)
    return missing


def run_dataset_sanity_check(db: Session) -> dict[str, object]:
    results: dict[str, object] = {}
    checks = {
        "missing_sections": verify_sections,
        "subsection_gaps": verify_subsections,
        "duplicates": verify_duplicates,
        "missing_text": verify_missing_text,
        "missing_embeddings": verify_embeddings,
    }

    for name, check in checks.items():
        try:
            results[name] = check(db)
        except Exception as exc:  # pragma: no cover - defensive startup logging
            logger.warning("Dataset sanity check failed during %s: %s", name, exc)
            results[name] = []

    logger.info("Dataset sanity check completed.")
    return results
