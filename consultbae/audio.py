"""Local audio metadata extraction with WAV support and optional ffprobe support."""
from __future__ import annotations

import audioop
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path


class AudioAnalysisError(ValueError):
    pass


def _wav_metadata(path: Path) -> dict:
    try:
        with wave.open(str(path), "rb") as audio:
            frames, rate, channels, width = audio.getnframes(), audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
            raw = audio.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise AudioAnalysisError(f"Invalid or unsupported WAV file: {exc}") from exc
    if not rate or not width:
        raise AudioAnalysisError("WAV file has invalid sample format")
    rms = audioop.rms(raw, width) if raw else 0
    max_amplitude = float((1 << (8 * width - 1)) - 1)
    loudness = -120.0 if not rms else round(20 * math.log10(rms / max_amplitude), 2)
    return {"duration_seconds": round(frames / rate, 3), "sample_rate_khz": round(rate / 1000, 3),
            "bitrate_kbps": round(rate * width * channels * 8 / 1000, 3), "loudness_dbfs": loudness,
            "format": "wav", "analyzer": "wave"}


def _ffprobe_metadata(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate:stream=sample_rate,bit_rate", "-of", "json", str(path)]
    try:
        output = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        data = json.loads(output)
        stream = next((s for s in data.get("streams", []) if s.get("sample_rate")), {})
        duration = float(data["format"]["duration"])
        sample_rate = int(stream["sample_rate"])
        bitrate = int(data["format"].get("bit_rate") or stream["bit_rate"])
    except (subprocess.SubprocessError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AudioAnalysisError(f"Could not read audio metadata: {exc}") from exc
    return {"duration_seconds": round(duration, 3), "sample_rate_khz": round(sample_rate / 1000, 3),
            "bitrate_kbps": round(bitrate / 1000, 3), "loudness_dbfs": None,
            "format": path.suffix.lstrip(".").casefold(), "analyzer": "ffprobe"}


def analyze_audio(file_path: str | Path) -> dict:
    """Return duration, sample rate, bitrate, and loudness. Raises AudioAnalysisError safely."""
    path = Path(file_path)
    if not path.is_file():
        raise AudioAnalysisError("Audio file does not exist")
    if path.suffix.casefold() == ".wav":
        return _wav_metadata(path)
    if shutil.which("ffprobe"):
        return _ffprobe_metadata(path)
    raise AudioAnalysisError("Only WAV is supported in this environment. Install ffmpeg/ffprobe for other formats.")
