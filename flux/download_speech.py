"""Explicit, one-time network download. Normal transcription is offline."""
from faster_whisper import WhisperModel
from .config import DATA, WHISPER_MODEL

if __name__ == "__main__":
    print(f"Downloading {WHISPER_MODEL} to {DATA / 'whisper'} ...")
    WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", download_root=str(DATA / "whisper"))
    print("Speech model is ready for offline use.")
