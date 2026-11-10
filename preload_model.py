"""Download the default local model before accepting test calls."""

from faster_whisper import WhisperModel

WhisperModel(
    "medium",
    device="cpu",
    compute_type="int8",
    download_root="/var/cache/asterisk/fyp-whisper",
)
print("MODEL_READY")
