#!/opt/fyp-stt-venv/bin/python3
"""Asterisk EAGI: translate incoming 8 kHz speech turns into English."""

import audioop
from collections import deque
import json
import os
import queue
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from io import BytesIO

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

RATE = 8000
FRAME_BYTES = 320  # 20 ms of 16-bit mono PCM
SILENCE_FRAMES = 60  # 1.2 seconds; keep more context around pauses
MIN_FRAMES = 25  # 500 ms
MAX_FRAMES = 1000  # 20 seconds
PREROLL_FRAMES = 15  # retain 300 ms before speech detection
SPEECH_RMS = int(os.getenv("FYP_SPEECH_RMS", "450"))
MODEL_NAME = os.getenv("FYP_WHISPER_MODEL", "medium")
MODEL_DIR = os.getenv("FYP_WHISPER_MODEL_DIR", "/var/cache/asterisk/fyp-whisper")
TRANSCRIPT_PATH = os.getenv(
    "FYP_TRANSCRIPT_PATH", "/var/log/asterisk/fyp_transcripts.jsonl"
)


def read_agi_environment():
    values = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            break
        key, _, value = line.partition(": ")
        values[key] = value
    return values


def wav_bytes(pcm):
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    output.seek(0)
    return output


def transcribe_worker(items, call_id):
    model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", download_root=MODEL_DIR)
    while True:
        item = items.get()
        if item is None:
            return
        try:
            audio = decode_audio(wav_bytes(item), sampling_rate=16000)
            detected_language, detected_probability, language_probs = model.detect_language(audio=audio)
            allowed_probs = {
                candidate: probability
                for candidate, probability in language_probs
                if candidate in ("ur", "en")
            }
            # Short Urdu phrases are sometimes detected as Hindi or another language.
            # Prefer Urdu in that case so the translation uses the likely source language.
            language = detected_language if detected_language in ("ur", "en") else "ur"
            segments, _ = model.transcribe(
                audio, language=language, task="translate", vad_filter=False
            )
            translation = " ".join(segment.text.strip() for segment in segments).strip()
            if translation:
                record = {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "call_id": call_id,
                    "task": "translate",
                    "language": language,
                    "detected_language": detected_language,
                    "detected_probability": round(detected_probability, 3),
                    "urdu_probability": round(allowed_probs.get("ur", 0), 3),
                    "english_probability": round(allowed_probs.get("en", 0), 3),
                    "text": translation,
                }
                with open(TRANSCRIPT_PATH, "a", encoding="utf-8") as out:
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(json.dumps(record, ensure_ascii=False), file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"Translation error: {exc}", file=sys.stderr, flush=True)


def main():
    env = read_agi_environment()
    call_id = env.get("agi_uniqueid", str(int(time.time())))
    items = queue.Queue(maxsize=8)
    worker = threading.Thread(target=transcribe_worker, args=(items, call_id), daemon=True)
    worker.start()
    frame_buffer = bytearray()
    preroll = deque(maxlen=PREROLL_FRAMES)
    input_buffer = bytearray()
    speech_frames = 0
    quiet_frames = 0
    try:
        while True:
            chunk = os.read(3, FRAME_BYTES)
            if not chunk:
                break
            input_buffer.extend(chunk)
            while len(input_buffer) >= FRAME_BYTES:
                frame = bytes(input_buffer[:FRAME_BYTES])
                del input_buffer[:FRAME_BYTES]
                rms = audioop.rms(frame, 2)
                if not speech_frames and rms >= SPEECH_RMS:
                    frame_buffer.extend(b"".join(preroll))
                    preroll.clear()
                if rms >= SPEECH_RMS:
                    speech_frames += 1
                    quiet_frames = 0
                elif speech_frames:
                    quiet_frames += 1
                if speech_frames:
                    frame_buffer.extend(frame)
                else:
                    preroll.append(frame)
                if speech_frames and (quiet_frames >= SILENCE_FRAMES or len(frame_buffer) >= MAX_FRAMES * FRAME_BYTES):
                    if len(frame_buffer) >= MIN_FRAMES * FRAME_BYTES:
                        items.put(bytes(frame_buffer))
                    frame_buffer.clear()
                    speech_frames = 0
                    quiet_frames = 0
    finally:
        if len(frame_buffer) >= MIN_FRAMES * FRAME_BYTES:
            items.put(bytes(frame_buffer))
        items.put(None)
        worker.join(timeout=30)


if __name__ == "__main__":
    main()

