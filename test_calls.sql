CREATE TABLE IF NOT EXISTS test_calls (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id text NOT NULL,
    logged_at timestamptz NOT NULL DEFAULT now(),
    transcript text NOT NULL,
    intent text NOT NULL,
    score double precision NOT NULL CHECK (score BETWEEN 0 AND 1),
    programme text,
    reply text NOT NULL,
    whisper_model text
);

CREATE INDEX IF NOT EXISTS test_calls_call_id_idx ON test_calls (call_id);

ALTER TABLE test_calls ADD COLUMN IF NOT EXISTS reply_source text;
