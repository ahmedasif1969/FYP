#!/opt/kaavish-demo/venv/bin/python
"""Process one recorded Asterisk call turn."""

import os
import select
import struct
import subprocess
import sys
import time
import wave
from collections import deque
from pathlib import Path

from intent_classifier import IntentClassifier
from test_pipeline import LOCAL_MODELS, generate_reply, select_reply_route, store_call, translate_audio


def capture_speech(audio_fd, recording):
    """Collect a single question from 8 kHz, 16-bit EAGI audio."""
    frame = struct.Struct("<160h")
    preroll = deque(maxlen=15)
    captured = []
    pending = bytearray()
    deadline = time.monotonic() + 8
    loud_frames = quiet_frames = 0
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([audio_fd], [], [], remaining)[0]:
            break
        chunk = os.read(audio_fd, frame.size - len(pending))
        if not chunk:
            break
        pending.extend(chunk)
        if len(pending) < frame.size:
            continue
        audio = bytes(pending)
        pending.clear()
        samples = frame.unpack(audio)
        loud = sum(sample * sample for sample in samples) >= len(samples) * 450 ** 2
        if not captured:
            preroll.append(audio)
            loud_frames = loud_frames + 1 if loud else 0
            if loud_frames >= 3:
                captured.extend(preroll)
                deadline = time.monotonic() + 20
            continue
        captured.append(audio)
        quiet_frames = 0 if loud else quiet_frames + 1
        if quiet_frames >= 75 or len(captured) >= 1000:
            break

    with wave.open(str(recording), "wb") as wav:
        wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        wav.writeframes(b"".join(captured))


def main():
    agi = {}
    for line in sys.stdin:
        if not line.strip():
            break
        name, _, value = line.strip().partition(": ")
        agi[name] = value

    recording = Path(agi["agi_arg_1"])
    reply_wav = Path(agi["agi_arg_2"])
    call_id = agi["agi_uniqueid"]
    os.environ.setdefault("FYP_WHISPER_MODEL_DIR", "/opt/kaavish-demo/models")
    os.environ.setdefault("PGDATABASE", "kaavish_demo")
    model = "medium"
    voice_mode = agi.get("agi_arg_3") == "voice"
    if voice_mode:
        capture_speech(3, recording)
    with wave.open(str(recording), "rb") as audio:
        has_audio = audio.getnframes() > 0
    transcript = translate_audio(recording, model) if has_audio else ""
    intent, score, programme, reply, reply_source, faq_id, faq_distance = generate_reply(
        transcript, reply_wav, awaiting_hospital=agi.get("agi_arg_4") == "hospital",
        llm_model=os.getenv("FYP_LLM_MODEL", LOCAL_MODELS[0]) if voice_mode else None,
        qwen_only=agi.get("agi_arg_5") == "strict",
        use_vector_search=voice_mode,
    )
    try:
        store_call(call_id, transcript, intent, score, programme, reply, model, reply_source, faq_id, faq_distance)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Kaavish call {call_id}: {error}", file=sys.stderr)
    if voice_mode:
        context = "none"
        route, _, _ = select_reply_route(intent, set(IntentClassifier.tokens(transcript)))
        if route == "healthcare_location" and faq_id is None:
            context = "hospital"
        print(f'SET VARIABLE FYP_CONTEXT "{context}"', flush=True)
        sys.stdin.readline()
        print(f'SET VARIABLE FYP_CONTINUE "{int(bool(transcript.strip()))}"', flush=True)
        sys.stdin.readline()


if __name__ == "__main__":
    main()
