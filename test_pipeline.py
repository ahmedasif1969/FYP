"""Run the FYP demo from typed text or a local recording."""

import argparse
import csv
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

from faq_search import LOCAL_MODELS, choose_faq, search_faqs


def translate_audio(audio, model_name):
    from faster_whisper import WhisperModel

    cache = os.environ.get(
        "FYP_WHISPER_MODEL_DIR", str(Path(__file__).parent / "tmp" / "whisper-models")
    )
    model = WhisperModel(model_name, device="cpu", compute_type="int8",
                         download_root=cache, local_files_only=True)
    segments, _ = model.transcribe(str(audio), task="translate", vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments)


def store_call(call_id, transcript, intent, score, programme, reply, model, reply_source):
    payload = io.StringIO()
    payload.write(
        "COPY test_calls (call_id, transcript, intent, score, programme, reply, whisper_model, reply_source) "
        "FROM STDIN WITH (FORMAT csv, FORCE_NOT_NULL (transcript, reply));\n"
    )
    call_id = " ".join(call_id.splitlines())
    transcript = " ".join(transcript.splitlines())
    csv.writer(payload, lineterminator="\r\n").writerow(
        [call_id, transcript, intent, score, programme, reply, model, reply_source]
    )
    # Match the CSV row's line ending so PostgreSQL accepts the COPY marker.
    payload.write("\\.\r\n")
    subprocess.run(["psql", "-X", "-w", "-q", "-v", "ON_ERROR_STOP=1"],
                   input=payload.getvalue(), text=True, check=True, timeout=10)


def generate_reply(transcript, reply_wav, llm_model=LOCAL_MODELS[0], qwen_only=False):
    intent, score = "other", 0.0
    programme = None
    reply = "I don't have an answer to that question. Please speak with a human operator for help."
    reply_source = "no_match"
    if not transcript.strip():
        reply = "I did not hear any speech. Please check your microphone."
        reply_source = "no_speech"
    else:
        candidates = search_faqs(transcript)
        if candidates:
            row, model_available = choose_faq(llm_model, transcript, candidates) if llm_model else (None, False)
            if row:
                reply_source = f"{llm_model}:{row['id']}"
            elif not model_available:
                if qwen_only:
                    return intent, score, None, "", "qwen_failed"
                best_score, best_row = candidates[0]
                runner_up = candidates[1][0] if len(candidates) > 1 else 0
                if best_score >= 0.80 and best_score - runner_up >= 0.15:
                    row = best_row
                    reply_source = f"faq_fallback:{row['id']}"
            if row:
                intent = row["intent"]
                programme = row["program"]
                reply = row["answer"].strip()
                score = next(match_score for match_score, match in candidates if match is row)
    reply_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "reply.txt").write_text(reply, encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
             "-f", "lavfi", "-i", "flite=textfile=reply.txt",
             "-ar", "8000", "-ac", "1", "-c:a", "pcm_s16le", str(reply_wav.absolute())],
            cwd=directory, check=True,
        )
    return intent, score, programme, reply, reply_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--audio", type=Path)
    parser.add_argument("--model", default="medium", choices=["medium", "large-v3"])
    parser.add_argument("--llm", choices=LOCAL_MODELS, default=LOCAL_MODELS[0],
                        help="Select FAQ replies with local Ollama")
    parser.add_argument("--qwen-only", action="store_true", help="Disable FAQ fallback when Ollama is unavailable")
    parser.add_argument("--reply-wav", required=True, type=Path)
    parser.add_argument("--store-call", metavar="CALL_ID",
                        help="Store the result in PostgreSQL using standard libpq settings")
    args = parser.parse_args()

    transcript = args.text
    if args.audio:
        transcript = translate_audio(args.audio, args.model)

    intent, score, programme, reply, reply_source = generate_reply(
        transcript, args.reply_wav, llm_model=args.llm, qwen_only=args.qwen_only
    )
    if args.store_call:
        store_call(args.store_call, transcript, intent, score, programme, reply,
                   args.model if args.audio else None, reply_source)
    print(json.dumps({"transcript": transcript, "intent": intent, "score": round(score, 3),
                      "programme": programme, "reply": reply, "reply_source": reply_source},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
