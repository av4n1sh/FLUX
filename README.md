# Flux

## Web edition / Netlify

Flux now includes a Netlify-ready frontend and a separate authenticated Python
API. See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment and local web setup.
Hosting the frontend alone shows a connection screen; a working API and
Ollama-compatible model server are required for chat. The desktop version below
continues to work independently.

A modular Windows desktop personal assistant. The interface is **HTML, CSS, and JavaScript**
inside a PySide6 Qt WebEngine desktop window. Python handles Ollama, SQLite history,
long-term memory, Whisper speech recognition, and Windows speech output.

## Launch the redesigned app

If you already installed Flux, close the old window and run:

```powershell
Set-Location 'C:\Users\avani\Documents\ChatGPT\FLUX'
.\.venv\Scripts\python.exe -m flux
```

No Node.js, web server, or new dependency is required. Qt WebEngine and WebChannel are
included in the installed PySide6 package. Open the application through Python, not by
double-clicking the HTML file: the Python bridge provides its real data and actions.

The sidebar contains previous chats, Memory, Voice, and Settings. Use a conversation's
**•••** menu to rename or delete it. Deletion requires confirmation and removes its messages
from the database; independent long-term memories remain. New Chat opens a draft; a database
conversation is created when you first send a message. Deleting all chats returns to the orb.

The original pink orb is bundled in `flux/assets/flux-orb.png`. A shared JavaScript clock
blends idle, listening, thinking, speaking, and error states without restarting the motion.
The WebGL renderer combines that original texture with evolving plasma, displaced internal
detail, traveling highlights, depth shading, and a subtly rippling silhouette. Systems
without WebGL use an animated Canvas renderer that also changes the internal pixels.
One shared surface serves all visible orbs, capped at 30 updates per second (20 when
render submission is expensive), at 320 pixels for WebGL or 160 for the CPU fallback.
A small persistent orb stays in the header during chat. Listening reacts to
microphone amplitude; speaking is a state animation, not a synthesized-audio waveform.
Reduce motion softens the orb to a gentle living glow and disables message transitions.
Offscreen or hidden surfaces skip drawing to conserve resources.

Enter and the Send button use the same guarded send function. A submitted message appears
and the input clears immediately; you can draft your next message while Flux works.
Sending that next draft remains disabled until the current request completes. Replies
do not erase the next draft. Failed requests show Retry and restore the submitted text
when the editor is empty. Existing messages retain their DOM elements, so only new messages
animate. New messages scroll smoothly; scrolling up keeps your reading position, with a
Latest message button to return. Long answers reveal their beginning instead of skipping
straight to their end. Shift + Enter inserts a new line.

## What changed in memory

The earlier version persisted `/remember` facts correctly, but **ordinary messages never
created memories**. The inspected database contained 4 conversations, 14 messages, and
zero saved facts. This was a missing learning step, not a lost-database or prompt-injection issue.

Flux now learns a limited set of clear first-person statements after a successful response,
such as `My favorite programming language is Python.`, `My name is Avani.`,
`I'm working on Flux.`, and `My goal is to learn Python.` It does not scan old conversations.
Automatic learning can be switched off in Settings. The Memory page supports adding,
editing, deleting, and clearing real saved facts. Manual `/remember` still works.

Learning uses conservative English patterns, not a general-purpose extraction model.
It skips questions, quoted text, code blocks, and common credential terms. It does not
understand every phrasing or detect every sensitive fact; review saved memories yourself.
Repeated favorite-topic statements update that preference rather than add a conflicting fact.

Retrieval ranks lexical matches with basic synonyms and injects at most six relevant facts
into the model context. It is not semantic/vector search. Ask explicit questions about a fact's
topic; arbitrary paraphrases may need better retrieval in a future version.

The existing SQLite tables and IDs are retained and upgraded in place. Before upgrading a
legacy database, Flux creates `data/flux.before-v2.db`. **That backup contains the old history**;
deletion in the active database does not erase the backup. Keep or remove it according to your
own retention needs. No existing conversations are intentionally deleted during upgrade.

Pipeline logging goes to `data/flux.log`, rotated at 500 KB with two backups. It records
saved/retrieved/injected memory IDs and failures, not conversation or memory text.

The installed Qwen3 template was also forcing an open thinking block despite `think: false`.
Flux supplies an empty closed thinking block as a request-only assistant prefix for Qwen3,
then displays only the final answer. Neither the model files nor stored user messages are
modified. Responses that hit the output limit before finishing produce a retryable error.

## 1. Install Python and Ollama

Open **PowerShell** from the Windows Start menu. Run these commands one at a time:

```powershell
winget install --exact --id Python.Python.3.12 --source winget
winget install --exact --id Ollama.Ollama --source winget
```

Follow installer prompts. If winget is unavailable, use the official installers:
[Python 3.12.10 Windows installer](https://www.python.org/downloads/release/python-31210/)
(choose Windows installer 64-bit and enable **Add python.exe to PATH**) and
[Ollama for Windows](https://ollama.com/download/windows).
Python 3.12 is a conservative compatibility choice for this starter's speech packages.

Close PowerShell and open a fresh window so it sees the installed commands:

```powershell
py -3.12 --version
ollama --version
```

Launch **Ollama** from Start. It runs in the background. Download the initial brain:

```powershell
ollama pull qwen3:4b
ollama run qwen3:4b
```

Type a greeting to verify the model, then type `/bye` to exit its terminal chat.
The model download is about 2.5 GB; runtime memory requirements are higher.
Performance depends on your PC. If it runs too slowly, try the smaller model:

```powershell
ollama pull qwen3:1.7b
$env:FLUX_MODEL = "qwen3:1.7b"
```

Set that environment variable in the same PowerShell window you use to launch Flux.
The model selection resets when you close that PowerShell window.

## 2. Set up and launch text chat first

All project files are already in `C:\Users\avani\Documents\ChatGPT\FLUX`.
A virtual environment keeps Flux's packages separate from other Python projects.
Run:

```powershell
Set-Location 'C:\Users\avani\Documents\ChatGPT\FLUX'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flux
```

You do not need to activate the environment or change PowerShell execution policy.
`requirements.txt` installs PySide6, including the Qt libraries needed for the window.
Keep Ollama running. Flux connects only to `127.0.0.1:11434`.

Type `Hello, introduce yourself.` and press **Send**. The first answer can take longer
while Ollama loads the model. The starter displays the completed answer, not streamed tokens.

## 3. Verify history and memory

1. Send `My favorite programming language is Python.` and wait for the response.
2. Open **Memory** and confirm the preference is present.
3. Close Flux, reopen it, and click **New chat**.
4. Ask `What programming language do I like?`.
5. Select your earlier chat in the sidebar. Rename it through **••• → Rename**.
6. Choose **••• → Delete**, first cancel, then repeat and confirm. Reopen Flux to verify deletion.
7. Check that the preference is still on the Memory page. Delete it there separately.

Long-term memory is a bounded fact list shared across conversations (300 facts,
300 characters each). Supported personal statements can become memories automatically.
Temporary context consists of up to six recent complete turns from the selected chat,
within a 12,000-character history budget. New conversations start with no earlier chat
context. Reopening an old conversation reconstructs its recent context from history.
This is deliberately simple memory, not semantic search or automatic summarization.

Only successfully completed question/answer pairs are saved. Failed requests remain visible
with Retry. Their text is restored to an empty input box; a newer draft is preserved.

## 4. Add voice

Close Flux, then run these commands in the project folder:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.\.venv\Scripts\python.exe -m flux.download_speech
.\.venv\Scripts\python.exe -m flux
```

This installs faster-whisper, microphone capture, and Windows speech synthesis.
The download command fetches the `base.en` Whisper model once. Subsequent transcription
uses that cached model offline. Model downloads require internet access; recordings
are not uploaded. Audio is held in memory and not saved to disk by Flux.

Select **Voice**, click **Start listening**, speak, then click **Stop recording**.
Recording automatically stops after 30 seconds. Review/edit the transcript and click
**Send**. Flux displays the reply and speaks up to its first 1,500 characters using an
installed Windows voice. The composer microphone also enters Voice mode. Returning to
**Chats** selects Text mode. There is no wake word or background listening.
Typing is also available in Voice mode.

For languages other than English, download the multilingual model and launch with:

```powershell
$env:FLUX_WHISPER_MODEL = "base"
.\.venv\Scripts\python.exe -m flux.download_speech
.\.venv\Scripts\python.exe -m flux
```

## Files and responsibilities

```text
FLUX/
  requirements.txt          Desktop dependencies
  requirements-voice.txt    Optional speech dependencies
  flux/
    __init__.py             Python package marker
    __main__.py             Application entry point
    config.py               Model, local paths, assistant instructions
    brain.py                Bounded context and loopback-only Ollama requests
    storage.py              SQLite migrations, conversations, facts, settings
    memory.py               Fact learning, editing, bounded relevant retrieval
    conversation.py         Context → Ollama → history → memory pipeline
    bridge.py               Validated JavaScript/Python actions and workers
    logging_setup.py        Local rotating pipeline log
    speech.py               Recording, local transcription, Windows TTS
    download_speech.py      Explicit one-time Whisper model download
    ui.py                   Desktop WebEngine shell and local asset restrictions
    frontend/
      index.html            Interface structure and local resources
      style.css             Responsive design and orb animations
      app.js                DOM rendering, dialogs, WebChannel interactions
      orb.js                Shared continuous animation clock and state blending
      plasma.js             WebGL plasma shader and animated Canvas fallback
      motion.css            Orb layers, chat bubbles, send/reply transitions
    assets/
      flux-orb.png          User-provided pink orb, unmodified original
  tests/
    test_core.py            Storage, context, and mocked Ollama checks
    test_memory_conversations.py   Persistence, migration, retrieval, deletion
    test_desktop.py         Actual WebEngine/WebChannel UI integration tests
    live_ollama.py          Explicit real-model tests across app processes
  data/                     Created on first use; excluded from Git
    flux.db                 Conversation history, saved facts, settings
    flux.log                Diagnostic events without private message text
    whisper/                Downloaded speech model
```

## Privacy and current limits

- Conversations and facts are stored as unencrypted SQLite data in `data/flux.db`.
  Windows account/file permissions protect access; Flux does not provide authentication yet.
- `/forget` removes the saved fact, not mentions of it in existing conversation history.
  The model may still see it in the selected chat's recent context.
- The embedded browser loads only bundled UI files and Qt's WebChannel script. It cannot
  navigate to websites or fetch remote images. No shell execution, computer control,
  camera, vision, or self-editing tools are connected. Model output uses safe DOM text
  rendering with basic Markdown (headings, lists, fenced code, bold, inline code) and Copy.
  Raw HTML and executable links are not rendered. Full Markdown tables are not implemented.
- Chat and speech run in background threads. To avoid abruptly terminating these threads,
  closing is deferred during an operation: wait for completion, then close again.
  Ollama requests have a 180-second network timeout. There is no Cancel/Stop-speaking button yet.
- The model can make mistakes. Instructions alone do not enforce security; any future
  tools must enforce permissions in application code.
- Model output is still returned as a complete response, not streamed tokens.
- Dependency ranges allow compatible updates; a tested exact-version lock can be captured
  after successful setup on your PC.

## Troubleshooting

**Python opens the Microsoft Store:** use `py -3.12` after installing real Python,
and reopen PowerShell. If `py` is missing, rerun the Python installer with launcher support.

**Cannot reach Ollama:** open Ollama from Start. Check `ollama list`. If it is not running,
run `ollama serve` in a separate PowerShell window. An address-in-use message usually means
Ollama is already running. Do not expose its port to the internet.

**Model not found:** run `ollama pull qwen3:4b` (or the model selected by `FLUX_MODEL`).

**Microphone unavailable:** install the voice requirements; enable microphone access
and desktop app microphone access under Windows Settings > Privacy & security > Microphone.
Choose a working default input device under Settings > System > Sound.

**Speech model missing:** run `.\.venv\Scripts\python.exe -m flux.download_speech` with
internet access and the same `FLUX_WHISPER_MODEL` value used to launch the app.

**No spoken sound:** check the default Windows output device and volume, and installed
Windows speech voices. A speech error does not remove the displayed/saved answer.

**Install fails:** copy the complete error and the command that produced it. Diagnose it
before changing the application. CPU transcription avoids requiring a CUDA installation.

## Development and roadmap

Run automated tests without requiring an LLM server or microphone (desktop tests use
the real WebEngine bridge with injected model/audio services and disposable databases):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Explicit live Ollama tests use a separate database under `data/verification`. Run these
as two commands; the second process verifies cross-chat recall after the first closes:

```powershell
.\.venv\Scripts\python.exe tests\live_ollama.py learn
.\.venv\Scripts\python.exe tests\live_ollama.py recall
```

If an offscreen Qt test produces GPU warnings or stale screenshots, run native Windows tests:

```powershell
$env:QT_QPA_PLATFORM = "windows"
$env:QTWEBENGINE_CHROMIUM_FLAGS = "--disable-backgrounding-occluded-windows --disable-renderer-backgrounding"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The live microphone still needs a human speech check for room noise, volume, and device
quality. Automated voice state tests are not evidence of human microphone recognition accuracy.

Build and validate in this order:

1. Local text chat and helpful connection errors.
2. Saved history and explicit memory, including restart behavior.
3. Desktop GUI and status orb.
4. Optional voice input/output and mode switching.
5. Better memory: editing, deletion/export controls, summaries, relevance retrieval.
6. Better GUI: streaming, cancellation, settings, audio visualization, installer.
7. Web access and a typed tool registry with explicit permissions and audit records.
8. Computer control, authentication, narrowly scoped file access, and confirmations for risky actions.
9. Portability and explicit internal state/personality settings.
10. Image generation/editing, screen vision, and opt-in camera access.
11. Self-coding only in isolated working copies, with tests, readable diffs, manual approval,
    and rollback. Never let generated code silently replace the running assistant.

## Official references

- [Ollama on Windows](https://docs.ollama.com/windows)
- [Qwen3 4B](https://ollama.com/library/qwen3:4b)
- [Qt for Python / PySide6](https://doc.qt.io/qtforpython-6/)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Offline Windows TTS through pyttsx3](https://github.com/nateshmbhat/pyttsx3)
- [Edge TTS](https://github.com/rany2/edge-tts) is an optional future online alternative.
