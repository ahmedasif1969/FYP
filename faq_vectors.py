"""Index curated Alkhidmat FAQs and retrieve them by local vector similarity."""

import csv
import io
import json
import subprocess
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

EMBEDDING_MODEL = "all-minilm:latest"
FAQ_DIR = Path(__file__).with_name("faq_sources")
PROGRAMMES = ("health-services", "community-services")
MIN_COSINE_SIMILARITY = 0.35


def embed(texts):
    request = Request(
        "http://127.0.0.1:11434/api/embed",
        data=json.dumps({"model": EMBEDDING_MODEL, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with build_opener(ProxyHandler({})).open(request, timeout=12) as response:
        vectors = json.load(response)["embeddings"]
    if len(vectors) != len(texts) or any(len(vector) != 384 for vector in vectors):
        raise ValueError("Unexpected FAQ embedding size")
    return vectors


def query_database(sql, **variables):
    options = [part for name, value in variables.items() for part in ("-v", f"{name}={value}")]
    result = subprocess.run(
        ["psql", "-X", "-w", "-qAt", "-v", "ON_ERROR_STOP=1", *options],
        input=sql, text=True, capture_output=True, timeout=10,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def read_faqs():
    entries = []
    for programme in PROGRAMMES:
        with (FAQ_DIR / f"{programme}.jsonl").open(encoding="utf-8") as source:
            for line in source:
                entry = json.loads(line)
                entry["intent"] = programme.replace("-", "_")
                entries.append(entry)
    return entries


def index_faqs():
    entries = read_faqs()
    vectors = []
    for offset in range(0, len(entries), 12):
        vectors.extend(embed([
            " ".join([entry["question"], *entry["question_variants"], entry["answer"]])
            for entry in entries[offset:offset + 12]
        ]))
    sql = io.StringIO()
    sql.write("BEGIN;\nSET LOCAL search_path TO public;\n")
    sql.write("CREATE TEMP TABLE imported_faqs (LIKE faq_entries INCLUDING ALL) ON COMMIT DROP;\n")
    sql.write("COPY imported_faqs (faq_id, intent, document, embedding) FROM STDIN WITH (FORMAT csv);\n")
    writer = csv.writer(sql, lineterminator="\n")
    for entry, vector in zip(entries, vectors, strict=True):
        writer.writerow([entry["id"], entry["intent"], json.dumps(entry), json.dumps(vector)])
    sql.write("\\.\n")
    sql.write("DELETE FROM faq_entries;\nINSERT INTO faq_entries SELECT * FROM imported_faqs;\nCOMMIT;\n")
    query_database(sql.getvalue())
    return len(entries)


def retrieve_vector_faq(intent, question, allowed_ids=None):
    if allowed_ids == []:
        return None, None
    vector = json.dumps(embed([question])[0], allow_nan=False)
    row = query_database(
        """
        SELECT json_build_object('entry', document, 'distance', embedding <=> :'embedding'::vector)
        FROM public.faq_entries
        WHERE intent = :'intent'
          AND (:'allowed_ids' = '' OR faq_id = ANY(string_to_array(:'allowed_ids', ',')))
        ORDER BY embedding <=> :'embedding'::vector, faq_id
        LIMIT 1;
        """,
        embedding=vector, intent=intent, allowed_ids=",".join(allowed_ids or ()),
    )
    if row:
        result = json.loads(row)
        if allowed_ids or 1 - result["distance"] >= MIN_COSINE_SIMILARITY:
            return result["entry"], result["distance"]
    return None, None


if __name__ == "__main__":
    print(f"Indexed {index_faqs()} FAQ entries with {EMBEDDING_MODEL}.")
