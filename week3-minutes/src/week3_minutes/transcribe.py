"""Optional: audio -> text with an open Whisper model running locally (Hugging Face
transformers). Not installed by default because torch is a multi-gigabyte download;
run it with:

    uv run --with "transformers[torch]" python -m week3_minutes --audio meeting.mp3

Decoding mp3/m4a needs ffmpeg on your PATH (macOS: `brew install ffmpeg`).
This path is not covered by the offline tests.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_WHISPER = "openai/whisper-small"


class TranscriptionUnavailable(RuntimeError):
    pass


def transcribe(audio: str | Path, model_id: str = DEFAULT_WHISPER) -> str:
    try:
        from transformers import pipeline  # imported here so the rest works without it
    except ImportError as exc:
        raise TranscriptionUnavailable(
            'Audio needs the transformers library: uv run --with "transformers[torch]" ...'
        ) from exc
    asr = pipeline("automatic-speech-recognition", model=model_id, return_timestamps=True)
    result = asr(str(audio))  # chunks long audio internally when return_timestamps=True
    return str(result["text"]).strip()
