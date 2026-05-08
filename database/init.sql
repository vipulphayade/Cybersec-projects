CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS bylaws (
    id SERIAL PRIMARY KEY,
    section TEXT NOT NULL,
    subsection TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    keywords TEXT[] NOT NULL,
    content TEXT NOT NULL,
    explanation TEXT NOT NULL,
    example TEXT NOT NULL,
    conditions_required JSONB NOT NULL DEFAULT '[]'::jsonb,
    possible_challenges TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    related_statutes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    embedding VECTOR(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (section, subsection, title)
);

CREATE TABLE IF NOT EXISTS bylaw_relations (
    id SERIAL PRIMARY KEY,
    source_section TEXT NOT NULL,
    source_subsection TEXT NOT NULL DEFAULT '',
    target_section TEXT NOT NULL,
    target_subsection TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS bylaws_embedding_idx
    ON bylaws USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_bylaws_section_subsection
    ON bylaws (section, subsection);

CREATE INDEX IF NOT EXISTS idx_bylaws_topic
    ON bylaws (topic);

CREATE INDEX IF NOT EXISTS idx_bylaw_relations_source
    ON bylaw_relations (source_section, source_subsection);
