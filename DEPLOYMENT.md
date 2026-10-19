# Deploy Flux on Netlify

The web edition has two components: Netlify serves the interface, and a Python
API handles chat and SQLite history. The API needs a reachable Ollama-compatible
AI server. Netlify does not run the desktop app or Ollama.

This is a personal, single-owner workspace. Anyone with the access key can see
and change all its conversations and memories. It is not a multi-user service.
Use one API worker and one instance. The frontend asks for the server URL and
key on every reload; it never embeds a secret in the published files.

## 1. Publish the frontend

1. Open https://app.netlify.com/start and import `av4n1sh/FLUX` from GitHub.
2. Select `main`. The root `netlify.toml` provides these settings:
   - Base directory: `web`
   - Build command: `node ../scripts/build-web.mjs`
   - Publish directory: `../dist` (relative to the base directory)
3. Deploy and copy the resulting HTTPS site origin, without a trailing slash.

The web base directory avoids installing desktop Python dependencies during
the static-site build. GitHub pushes trigger future deployments once connected.

## 2. Host the API

Use an existing Python server with persistent disk, or import this repository
as a Render Blueprint using `render.yaml`. **The included Render configuration
selects a paid Starter service and persistent disk.** Review current costs before
creating it. No hosting subscription is created by the source code itself.

Build: `pip install -r requirements-web.txt`

Start: `uvicorn flux.web:create_app --factory --host 0.0.0.0 --port $PORT --workers 1`

Configure these variables on the API host:

| Variable | Value |
| --- | --- |
| `FLUX_WEB_TOKEN` | Random secret of at least 32 characters; Render generates one |
| `FLUX_WEB_ORIGINS` | Exact Netlify origin, e.g. `https://your-site.netlify.app`; comma-separate additional origins |
| `FLUX_WEB_DATA` | Persistent directory; the Render blueprint uses `/var/data/flux` |
| `FLUX_OLLAMA_URL` | Full HTTPS Ollama chat endpoint, ending in `/api/chat` |
| `FLUX_OLLAMA_KEY` | Server-side bearer key for the model endpoint, if required |
| `FLUX_MODEL` | Model installed/available on that endpoint; defaults to `qwen3:4b` |

For an API running on the same machine as Ollama, the default model endpoint is
`http://127.0.0.1:11434/api/chat`. A cloud API cannot reach Ollama on your PC through
that address. Use HTTPS when exposing the Flux API, and keep Ollama itself private
or authenticated. Never put either secret in Netlify's static files or GitHub.

`/health` verifies that the API is running, not that the AI model is reachable.
The model provider receives prompts and relevant saved memories. Browser speech
recognition may send audio to the browser vendor's service and is not supported
in every browser. Typed chat remains available.

## 3. Connect and verify

Open your Netlify URL. Enter the API's HTTPS URL and `FLUX_WEB_TOKEN` in the
connection dialog. Send a message, add a memory, reload, reconnect, and verify
the conversation and memory persist. Test voice after granting microphone access.

If connection fails, verify the API is deployed, the access key matches, and
`FLUX_WEB_ORIGINS` exactly matches your frontend origin. Add a custom domain's
origin when changing domains. Keep the persistent disk and back it up separately.

## Local development

```powershell
python -m pip install -r requirements-web.txt
$env:FLUX_WEB_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:FLUX_WEB_ORIGINS = 'http://localhost:8080'
python -m uvicorn flux.web:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal run `node scripts/build-web.mjs`, then
`python -m http.server 8080 --directory dist`. Open `http://localhost:8080` and
connect to `http://127.0.0.1:8000` with the generated key. View the key only in your
own terminal using `$env:FLUX_WEB_TOKEN`. Ollama must be running with the model.
Web data is stored separately in `data/web/flux.db`; desktop data is unchanged.

Tests: install `httpx`, then run
`python -m unittest discover -s tests -p test_web.py -v`.

References: [Netlify configuration](https://docs.netlify.com/build/configure-builds/file-based-configuration/),
[Render persistent disks](https://render.com/docs/disks),
[Render Blueprint configuration](https://render.com/docs/blueprint-spec).
