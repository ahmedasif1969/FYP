"""Download faster-whisper large-v3 into the local WSL model cache."""

from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="Systran/faster-whisper-large-v3",
    cache_dir="/var/cache/asterisk/fyp-whisper",
)
print(f"MODEL_DOWNLOADED {path}", flush=True)
