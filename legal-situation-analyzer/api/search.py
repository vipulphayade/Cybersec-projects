from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from bylaw_seed import LAW_NAME
from embeddings import get_embedding_service
from import_service import serialize_embedding
from schemas import DISCLAIMER_TEXT


# --------------------------------------------------
# BYE-LAW NUMBER DETECTION
# --------------------------------------------------

def detect_bye_law_reference(query: str):
    pattern = r"\b(?:bye[-\s]?law|byelaw|section)\s*(\d{1,3})\s*(?:\(?\s*([a-z])\s*\)?)?\b"
    match = re.search(pattern, query.lower())
    if not match:
        match = re.search(r"\b(\d{1,3})\s*\(\s*([a-z])\s*\)", query.lower())

    if match:
        section = match.group(1)
        subsection = match.group(2) if match.group(2) else ""
        return section, subsection

    return None


def no_match_response(confidence: float = 0.0):
    return {
        "law": LAW_NAME,
        "section": None,
        "subsection": None,
        "title": "No reliable exact bye-law match found.",
        "explanation": "Additional facts or documents may be required for reliable interpretation.",
        "citation": "No reliable exact bye-law match found.",
        "example": "",
        "conditions_required": [],
        "possible_challenges": [],
        "related_statutes": [],
        "related_rules": [],
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "disclaimer": DISCLAIMER_TEXT,
        "success": False,
        "message": "No reliable exact bye-law match found.",
        "match_type": "none",
    }


def ensure_query_log_table(db: Session):
    db.execute(text("""
    CREATE TABLE IF NOT EXISTS query_logs (
        id SERIAL PRIMARY KEY,
        query_text TEXT NOT NULL,
        returned_rule TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """))
    db.commit()


# --------------------------------------------------
# STOP WORDS
# --------------------------------------------------

STOP_WORDS = {
    "a","an","and","are","as","at","be","but","by","for","from",
    "had","has","have","he","her","his","if","in","into","is",
    "it","its","may","my","of","on","or","our","she","that",
    "the","their","them","they","this","to","was","we","were",
    "what","when","which","who","will","with","without","you","your"
}


# --------------------------------------------------
# LEGAL SYNONYM GROUPS
# --------------------------------------------------

SYNONYM_GROUPS = {
    "death": {"death","died","deceased","demise"},
    "nominee": {"nominee","nomination","nominated"},
    "transfer": {"transfer","transferred","succession","inherit","inheritance"},
    "member": {"member","members","membership"},
    "parking": {"parking","vehicle","garage","slot"},
    "repair": {"repair","repairs","maintenance","structural"},
    "fund": {"fund","funds","sinking","reserve"},
    "committee": {"committee","managing","management"},
    "meeting": {"meeting","agm","sgm","generalbody","resolution"},
    "complaint": {"complaint","grievance","objection","dispute"},
    "share": {"share","shares","shareholding"},
    "flat": {"flat","apartment","unit"}
}


# --------------------------------------------------
# TOKENIZATION
# --------------------------------------------------

def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", value.lower())


def extract_keywords(value: str) -> set[str]:
    return {
        token
        for token in tokenize(value)
        if len(token) > 2 and token not in STOP_WORDS
    }


# --------------------------------------------------
# KEYWORD EXPANSION
# --------------------------------------------------

def expand_keywords(keywords: set[str]) -> set[str]:

    expanded = set(keywords)

    for keyword in list(keywords):
        for canonical, variants in SYNONYM_GROUPS.items():

            if keyword == canonical or keyword in variants:

                expanded.add(canonical)
                expanded.update(variants)

    return expanded


# --------------------------------------------------
# CHECK KEYWORD COLUMN
# --------------------------------------------------

def has_keywords_column(db: Session) -> bool:

    return bool(
        db.execute(
            text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='bylaws'
                AND column_name='keywords'
            )
            """)
        ).scalar()
    )


# --------------------------------------------------
# KEYWORD FILTER SQL
# --------------------------------------------------

def build_keyword_filter_clause(expanded_keywords:set[str], use_keywords_column:bool):

    if not expanded_keywords:
        return "",{}

    keyword_terms = sorted(expanded_keywords)
    patterns = [f"%{term}%" for term in keyword_terms]

    clauses = [
        "LOWER(title) LIKE ANY(CAST(:keyword_patterns AS text[]))",
        "LOWER(topic) LIKE ANY(CAST(:keyword_patterns AS text[]))",
        "LOWER(content) LIKE ANY(CAST(:keyword_patterns AS text[]))",
        "LOWER(explanation) LIKE ANY(CAST(:keyword_patterns AS text[]))",
        "LOWER(example) LIKE ANY(CAST(:keyword_patterns AS text[]))"
    ]

    if use_keywords_column:

        clauses.append(
            """
            EXISTS (
            SELECT 1 FROM unnest(keywords) kw
            WHERE LOWER(kw)=ANY(CAST(:keyword_terms AS text[]))
            )
            """
        )

    return " AND ("+" OR ".join(clauses)+")",{
        "keyword_terms":keyword_terms,
        "keyword_patterns":patterns
    }


# --------------------------------------------------
# VECTOR SEARCH
# --------------------------------------------------

def fetch_top_candidates(db:Session,description:str,expanded_keywords:set[str],limit:int=5):
    try:
        embedder = get_embedding_service()
        query_vector = serialize_embedding(embedder.encode_one(description))
    except Exception:
        return []

    use_keywords_column = has_keywords_column(db)

    keyword_filter,keyword_params = build_keyword_filter_clause(
        expanded_keywords,use_keywords_column
    )

    base_query = f"""
    SELECT
    id,
    section,
    subsection,
    title,
    topic,
    {("keywords," if use_keywords_column else "ARRAY[]::TEXT[] AS keywords,")}
    content,
    explanation,
    example,
    conditions_required,
    possible_challenges,
    related_statutes,
    embedding <=> CAST(:query_vector AS vector) AS distance
    FROM bylaws
    WHERE embedding IS NOT NULL
    {keyword_filter}
    ORDER BY embedding <=> CAST(:query_vector AS vector)
    LIMIT :limit
    """

    params = {
        "query_vector":query_vector,
        "limit":limit,
        **keyword_params
    }

    result = db.execute(text(base_query),params).all()

    if result:
        return [dict(row._mapping) for row in result]

    fallback_query = """
    SELECT
    id,
    section,
    subsection,
    title,
    topic,
    content,
    explanation,
    example,
    conditions_required,
    possible_challenges,
    related_statutes,
    embedding <=> CAST(:query_vector AS vector) AS distance
    FROM bylaws
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:query_vector AS vector)
    LIMIT :limit
    """

    fallback = db.execute(
        text(fallback_query),
        {"query_vector":query_vector,"limit":limit}
    )

    return [dict(row._mapping) for row in fallback]


def fetch_keyword_candidates(db: Session, expanded_keywords: set[str], limit: int = 5):
    if not expanded_keywords:
        return []

    query = " OR ".join(sorted(expanded_keywords))
    result = db.execute(text("""
    WITH q AS (SELECT websearch_to_tsquery('english', :query) AS query)
    SELECT
        id, section, subsection, title, topic, keywords, content,
        explanation, example, conditions_required, possible_challenges,
        related_statutes,
        ts_rank_cd(
            setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
            setweight(to_tsvector('english', array_to_string(coalesce(keywords, ARRAY[]::text[]), ' ')), 'A') ||
            setweight(to_tsvector('english', coalesce(content,'')), 'B'),
            q.query
        ) AS rank
    FROM bylaws, q
    WHERE (
        setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
        setweight(to_tsvector('english', array_to_string(coalesce(keywords, ARRAY[]::text[]), ' ')), 'A') ||
        setweight(to_tsvector('english', coalesce(content,'')), 'B')
    ) @@ q.query
    ORDER BY rank DESC
    LIMIT :limit
    """), {"query": query, "limit": limit}).all()
    return [dict(row._mapping) for row in result]


# --------------------------------------------------
# TEXT BUILDING
# --------------------------------------------------

def build_candidate_text(candidate:dict[str,Any]):

    values = [
        str(candidate.get("title","")),
        str(candidate.get("topic","")),
        str(candidate.get("content","")),
        str(candidate.get("explanation","")),
        str(candidate.get("example",""))
    ]

    values.extend(candidate.get("keywords",[]) or [])

    return " ".join(v for v in values if v)


# --------------------------------------------------
# KEYWORD OVERLAP
# --------------------------------------------------

def compute_keyword_overlap(query_keywords:set[str],candidate:dict[str,Any]):

    if not query_keywords:
        return 0,0.0

    candidate_tokens = extract_keywords(
        build_candidate_text(candidate)
    )

    overlap_count = len(query_keywords & candidate_tokens)

    ratio = min(1.0,overlap_count/max(1,len(query_keywords)))

    return overlap_count,ratio


# --------------------------------------------------
# SCORING
# --------------------------------------------------

def score_candidate(query_keywords:set[str],candidate:dict[str,Any]):

    semantic = max(0.0,min(1.0,1-float(candidate.get("distance") or 0.0)))

    overlap_count,keyword_overlap = compute_keyword_overlap(
        query_keywords,candidate
    )

    if "rank" in candidate:
        raw_rank = max(0.0, float(candidate.get("rank") or 0.0))
        rank = raw_rank / (raw_rank + 0.1) if raw_rank else 0.0
        final_score = (rank * 0.6) + (keyword_overlap * 0.4)
        return final_score,rank,keyword_overlap,overlap_count

    final_score = (semantic*0.7)+(keyword_overlap*0.3)

    return final_score,semantic,keyword_overlap,overlap_count


# --------------------------------------------------
# RELATED RULES
# --------------------------------------------------

def fetch_related_rules(db:Session,section:str,subsection:str|None):

    result = db.execute(text("""
    SELECT b.section,b.subsection,b.title
    FROM bylaw_relations r
    JOIN bylaws b
    ON b.section=r.target_section
    AND b.subsection=r.target_subsection
    WHERE r.source_section=:section
    AND r.source_subsection=:subsection
    LIMIT 3
    """),{"section":section,"subsection":subsection or ""})

    return [dict(row._mapping) for row in result]


# --------------------------------------------------
# NORMALIZE CONDITIONS
# --------------------------------------------------

def normalize_conditions(raw):

    if isinstance(raw,list):
        return raw

    return []


# --------------------------------------------------
# QUERY LOGGING
# --------------------------------------------------

def log_query(db:Session,description:str,best:dict[str,Any],confidence:float):

    rule = f"{best.get('section')}"

    if best.get("subsection"):
        rule += f"({best['subsection']})"

    if best.get("title"):
        rule += f" - {best['title']}"

    db.execute(text("""
    INSERT INTO query_logs(query_text,returned_rule,confidence)
    VALUES(:q,:r,:c)
    """),{
        "q":description,
        "r":rule,
        "c":confidence
    })

    db.commit()


# --------------------------------------------------
# BUILD RESPONSE
# --------------------------------------------------

def build_response(best,confidence,related_rules):
    explanation = best.get("explanation") or (
        "This clause should be read directly from the official text. "
        "Additional facts or documents may be required for reliable interpretation."
    )

    return {
        "law":LAW_NAME,
        "section":best["section"],
        "subsection":best["subsection"] or None,
        "title":best["title"],
        "explanation":explanation,
        "citation":best["content"],
        "example":best.get("example",""),
        "conditions_required":normalize_conditions(best.get("conditions_required")),
        "possible_challenges":best.get("possible_challenges",[]),
        "related_statutes":best.get("related_statutes",[]),
        "related_rules":[
            {
                "section":r["section"],
                "subsection":r["subsection"] or None,
                "title":r["title"]
            }
            for r in related_rules
        ],
        "confidence":round(confidence,2),
        "disclaimer":DISCLAIMER_TEXT,
        "success": True,
        "message": "",
        "match_type": best.get("match_type", "semantic_match")
    }


# --------------------------------------------------
# MAIN ANALYSIS
# --------------------------------------------------

def analyze_description(description:str,db:Session):
    ensure_query_log_table(db)

    law_ref = detect_bye_law_reference(description)

    if law_ref:

        section,subsection = law_ref

        if subsection:
            result = db.execute(text("""
            SELECT *
            FROM bylaws
            WHERE section=:section AND subsection=:subsection
            LIMIT 1
            """),{"section":section,"subsection":subsection}).first()
        else:
            result = db.execute(text("""
            SELECT *
            FROM bylaws
            WHERE section=:section
            ORDER BY CASE WHEN subsection='' THEN 0 ELSE 1 END, subsection
            LIMIT 1
            """),{"section":section}).first()

        if result:

            best = dict(result._mapping)
            best["match_type"] = "exact_match"

            related = fetch_related_rules(db,section,subsection)

            log_query(db,description,best,1.0)

            return build_response(best,1.0,related)

    query_keywords = extract_keywords(description)

    expanded_keywords = expand_keywords(query_keywords)

    candidates = fetch_keyword_candidates(db, expanded_keywords, limit=5)
    match_type = "keyword_match"

    if not candidates:
        candidates = fetch_top_candidates(db, description, expanded_keywords, limit=5)
        match_type = "semantic_match"

    if not candidates:
        return no_match_response()

    scored = []

    for candidate in candidates:

        score,semantic,keyword_overlap,count = score_candidate(
            expanded_keywords,candidate
        )

        candidate["final_score"] = score

        scored.append(candidate)

    best = max(scored,key=lambda x:x["final_score"])
    best["match_type"] = match_type

    confidence = max(0.0,min(1.0,best["final_score"]))

    if confidence < 0.25 or not best.get("section") or not best.get("content"):
        log_query(db,description,{"section":"none","title":"No reliable exact bye-law match found."},confidence)
        return no_match_response(confidence)

    related = fetch_related_rules(
        db,
        best["section"],
        best.get("subsection")
    )

    log_query(db,description,best,confidence)

    return build_response(best,confidence,related)


def answer_followup(question: str, context: dict[str, Any]):
    citation = context.get("citation") or context.get("content") or ""
    if not context or not context.get("section") or not citation:
        return {
            "section": None,
            "subsection": None,
            "title": None,
            "answer": "No reliable exact bye-law match found.",
            "citation": "No reliable exact bye-law match found.",
            "confidence": 0.0,
            "disclaimer": DISCLAIMER_TEXT,
        }

    question_lower = question.lower()
    section = context.get("section")
    subsection = context.get("subsection")
    title = context.get("title")
    confidence = float(context.get("confidence") or 0.0)

    if any(term in question_lower for term in ["text", "citation", "rule", "clause"]):
        answer = citation
    elif any(term in question_lower for term in ["challenge", "oppose", "object", "argument"]):
        answer = (
            "Possible objections usually depend on facts and documents, such as "
            "whether required forms, approvals, notices, dues, or committee records are complete."
        )
    else:
        answer = (
            f"This follow-up is based only on Bye-law {section}"
            f"{f'({subsection})' if subsection else ''}: {title}. "
            "Please compare your facts with the exact clause text before relying on it."
        )

    return {
        "section": section,
        "subsection": subsection,
        "title": title,
        "answer": answer,
        "citation": citation,
        "confidence": max(0.0, min(1.0, confidence)),
        "disclaimer": DISCLAIMER_TEXT,
    }
