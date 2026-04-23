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

    pattern = r'(?:bye\s*law|byelaw|rule|section)?\s*(\d{1,3})\s*\(?([a-z])?\)?'

    match = re.search(pattern, query.lower())

    if match:
        section = match.group(1)
        subsection = match.group(2) if match.group(2) else ""
        return section, subsection

    return None


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

    embedder = get_embedding_service()

    query_vector = serialize_embedding(
        embedder.encode_one(description)
    )

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

    semantic = max(0.0,min(1.0,1-float(candidate["distance"] or 0.0)))

    overlap_count,keyword_overlap = compute_keyword_overlap(
        query_keywords,candidate
    )

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

    return {
        "law":LAW_NAME,
        "section":best["section"],
        "subsection":best["subsection"] or None,
        "title":best["title"],
        "explanation":best["explanation"],
        "citation":best["content"],
        "example":best["example"],
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
        "disclaimer":DISCLAIMER_TEXT
    }


# --------------------------------------------------
# MAIN ANALYSIS
# --------------------------------------------------

def analyze_description(description:str,db:Session):

    law_ref = detect_bye_law_reference(description)

    if law_ref:

        section,subsection = law_ref

        result = db.execute(text("""
        SELECT *
        FROM bylaws
        WHERE section=:section
        AND subsection=:subsection
        LIMIT 1
        """),{"section":section,"subsection":subsection}).first()

        if result:

            best = dict(result._mapping)

            related = fetch_related_rules(db,section,subsection)

            log_query(db,description,best,1.0)

            return build_response(best,1.0,related)

    query_keywords = extract_keywords(description)

    expanded_keywords = expand_keywords(query_keywords)

    candidates = fetch_top_candidates(
        db,
        description,
        expanded_keywords,
        limit=5
    )

    if not candidates:

        return {
            "law":LAW_NAME,
            "section":None,
            "subsection":None,
            "title":None,
            "explanation":"The system could not find a close matching bye-law.",
            "citation":"No clause text available.",
            "example":"Add more details about the society issue.",
            "conditions_required":[],
            "possible_challenges":[],
            "related_statutes":["Maharashtra Co-operative Societies Act, 1960"],
            "related_rules":[],
            "confidence":0.0,
            "disclaimer":DISCLAIMER_TEXT
        }

    scored = []

    for candidate in candidates:

        score,semantic,keyword_overlap,count = score_candidate(
            expanded_keywords,candidate
        )

        candidate["final_score"] = score

        scored.append(candidate)

    best = max(scored,key=lambda x:x["final_score"])

    confidence = max(0.0,min(1.0,best["final_score"]))

    related = fetch_related_rules(
        db,
        best["section"],
        best.get("subsection")
    )

    log_query(db,description,best,confidence)

    return build_response(best,confidence,related)