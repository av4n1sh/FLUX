"""Optional speech dependencies load only when used. Audio stays in RAM."""
from .config import DATA, WHISPER_MODEL


class Recorder:
    def __init__(self):
        self.stream = None
        self.frames = []
        self.overflow = False
        self.level = 0.0

    def start(self):
        import sounddevice as sd
        import numpy as np
        self.frames = []
        self.overflow = False

        def capture(data, frames, time, status):
            self.overflow |= bool(status)
            self.level = min(1.0, float(np.sqrt(np.mean(data * data))) * 12)
            self.frames.append(data.copy())

        self.stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=capture)
        try:
            self.stream.start()
        except Exception:
            self.stream.close()
            self.stream = None
            raise

    def stop(self):
        import numpy as np
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        frames, self.frames = self.frames, []
        self.level = 0.0
        if self.overflow:
            raise RuntimeError("Microphone audio dropped frames. Try recording again.")
        if not frames:
            raise RuntimeError("No microphone audio was captured.")
        return np.concatenate(frames).flatten()


class Transcriber:
    def __init__(self):
        self.model = None

    def transcribe(self, audio):
        from faster_whisper import WhisperModel
        if self.model is None:
            self.model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8",
                                      download_root=str(DATA / "whisper"), local_files_only=True)
        segments, _ = self.model.transcribe(audio, beam_size=1, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise RuntimeError("No speech detected. Try speaking closer to the microphone.")
        return text


def speak(text):
    import pythoncom
    import pyttsx3
    pythoncom.CoInitialize()
    engine = None
    try:
        engine = pyttsx3.init("sapi5")
        engine.setProperty("rate", 180)
        engine.say(text[:1500])
        engine.runAndWait()
    finally:
        if engine is not None:
            engine.stop()
        pythoncom.CoUninitialize()
