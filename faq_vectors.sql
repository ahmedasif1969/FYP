CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.faq_entries (
    faq_id text PRIMARY KEY,
    intent text NOT NULL,
    document jsonb NOT NULL,
    embedding vector(384) NOT NULL
);

GRANT SELECT ON public.faq_entries TO asterisk;
