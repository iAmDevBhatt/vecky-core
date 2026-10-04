# remote/

Code that runs *off* this machine, on your homelab Ollama/Kokoro box, in
support of `VeckyLocal`'s local assistant mode (see `AI.md`). Kept here so
it's version-controlled alongside the client code that calls it — the
live copy only exists on the server until you redeploy it.

## `tts_server.py`

A ~70-line FastAPI wrapper around the `kokoro` Python package (which is a
library, not a server) so `main.py` can get spoken audio back over HTTP
instead of needing `torch`/`transformers`/Kokoro installed locally.

- **Runs on**: `192.168.50.100` (hostname `vecky`), inside the existing
  `/home/dj/kokoro-venv` virtualenv — that venv already has `kokoro`,
  `torch` (CPU-only, no GPU on that box), and `soundfile` installed.
- **Listens on**: `0.0.0.0:8001`
- **Endpoints**:
  - `GET /health` → `{"status": "ok", "loaded": bool}`
  - `POST /tts` → body `{"text": str, "voice"?: str, "speed"?: float}`,
    returns `audio/wav` bytes (mono, 24kHz, 16-bit PCM — deliberately
    plain PCM so the client can decode it with Python's built-in `wave`
    module, no extra dependency needed).
- **Client**: `VeckyLocal._speak()` in `main.py` POSTs here, then plays
  the returned WAV locally via `sounddevice`. The URL is read from
  `config/api_keys.json`'s `tts_api_url` field.

### Deploying / redeploying

```bash
scp -i <path-to-key> -P 22 remote/tts_server.py dj@192.168.50.100:/home/dj/tts_server.py

ssh -i <path-to-key> -p 22 dj@192.168.50.100 \
  "pkill -f 'uvicorn tts_server'; \
   cd /home/dj && setsid nohup /home/dj/kokoro-venv/bin/uvicorn tts_server:app \
     --host 0.0.0.0 --port 8001 > /home/dj/tts_server.log 2>&1 < /dev/null &"
```

`setsid` matters — plain `nohup ... & disown` can fail to detach in a
non-interactive SSH session and the process dies when the SSH connection
closes.

Logs land in `/home/dj/tts_server.log` on the server. First request after
a (re)start is slow (~seconds) since it lazy-loads and warms up the Kokoro
pipeline; every request after that is fast.

### Not yet done

- Doesn't survive a server reboot — no systemd unit yet. Worth adding if
  this becomes more than a demo.
- No auth — anything on the LAN that can reach port 8001 can make it talk.
  Fine for a homelab, not fine to expose publicly.
