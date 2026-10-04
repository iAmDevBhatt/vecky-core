"""
Minimal Kokoro TTS HTTP wrapper.

Wraps the local kokoro-venv's KPipeline behind a tiny FastAPI service so a
remote client (no torch/transformers install needed there) can POST text
and get back WAV audio bytes.

Run:
    /home/dj/kokoro-venv/bin/uvicorn tts_server:app --host 0.0.0.0 --port 8001
"""
import io
import threading

import numpy as np
import soundfile as sf
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

_pipeline = None
_lock = threading.Lock()
_lang_codes = {
    "a": "a", "b": "b", "j": "j", "z": "z", "s": "s",
    "f": "f", "h": "h", "i": "i", "p": "p", "r": "r", "e": "e",
}


def _get_pipeline(voice: str):
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        lang = _lang_codes.get(voice[0].lower(), "a") if voice else "a"
        print(f"[TTS-server] Loading Kokoro pipeline (lang={lang})...")
        _pipeline = KPipeline(lang_code=lang)
        # warmup
        for _ in _pipeline("hello", voice="af_heart"):
            pass
        print("[TTS-server] Ready.")
    return _pipeline


class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0


@app.get("/health")
def health():
    return {"status": "ok", "loaded": _pipeline is not None}


@app.post("/tts")
def tts(req: TTSRequest):
    if not req.text.strip():
        return JSONResponse({"error": "empty text"}, status_code=400)

    with _lock:
        pipeline = _get_pipeline(req.voice)
        chunks = []
        for _, _, audio in pipeline(req.text, voice=req.voice, speed=req.speed):
            if audio is not None:
                arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio, dtype=np.float32)
                chunks.append(arr)

    if not chunks:
        return JSONResponse({"error": "no audio generated"}, status_code=500)

    full = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, full, 24000, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return Response(content=buf.read(), media_type="audio/wav")
