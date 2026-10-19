# Flux redesign validation — 2026-09-19

## Internal plasma upgrade

- 19 automated tests passed, including seven native Qt WebEngine integration tests.
- At fixed canvas coordinates, internal RGB pixels and edge alpha changed over 2.2
  seconds in both WebGL and the forced Canvas fallback. Nonuniform pixel changes
  verify internal animation independently of the element's CSS position or scale.
- The original pink image remains unmodified; the shader uses it as a displaced texture.
  A native Windows welcome screenshot was visually inspected for the new plasma appearance.
- One shared rendering surface, bounded resolution, a 30 Hz update cap, and visibility
  culling limit rendering work. Recorded render times measure CPU submission only,
  not GPU completion; these checks are not a sustained hardware FPS benchmark.
- Reports: `data/verification/plasma-tests.log` and `plasma-renderers.json`.
- A real `qwen3:4b` recall request verified changing internal canvas pixels while
  the Ollama worker was still running. It correctly recalled Python from the separate
  test database. See `data/verification/live-recall.json` and `plasma-live.log`.

## Orb and chat upgrade

- 18 automated tests passed, including the existing memory, history, deletion, and voice checks.
- Real Enter and Shift+Enter events were exercised in Qt WebEngine. Sending clears the
  editor before the model completes, shows exactly one user message, and preserves a
  newer draft when the reply arrives. Repeated input during a request does not duplicate it.
- A delayed worker verified that the JavaScript animation clock continues advancing while
  the GUI remains interactive. An actual `qwen3:4b` request additionally verified changing
  visible orb transforms during inference; the reply still recalled the saved Python preference.
- The pending user element survives completion, and the same thinking orb moves into the
  assistant response header. Earlier message elements are retained rather than reanimated.
- Failed requests, retry, preservation of a separate draft, long Markdown responses,
  smooth scrolling, window resizing, and conversation switching passed desktop checks.
- Reduced motion keeps the gentlest orb glow alive while suppressing message transitions.
  The animation loop skips hidden/offscreen orbs. No sustained hardware FPS benchmark was run.
- The Ollama client, storage, and voice services were not rewritten for this upgrade.
  Responses remain non-streamed; their entrance is animated after the full reply arrives.

## Confirmed

- 15 automated tests passed: six core/model-client tests, six memory/conversation tests,
  and three desktop integration tests using actual Qt WebEngine and WebChannel.
- Desktop tests exercise HTML controls for send, history, rename, cancel deletion,
  confirm deletion, memory editing/deletion, settings, voice states, and error handling.
- Layout checks passed at 760×580, 1280×820, and 1600×1000.
- Native Windows screenshots were inspected for welcome, voice, and memory views.
  An oversized empty-state icon and a deletion event naming collision were found and fixed.
- A fresh test database was used for two separate desktop processes with real
  `qwen3:4b` through Ollama. First process learned the Python preference; second opened
  a new chat, retrieved and injected the saved fact, and answered correctly.
  Result: “Your favorite programming language is Python.”
- The installed Qwen3 template forced an open thinking block. A request-only empty
  assistant thinking prefix resolved the observed reasoning-only responses.
- Windows SAPI generated “My favorite programming language is Python.” into a test
  audio file. Offline faster-whisper transcribed that sentence successfully.
- The user's actual database migration retained 4 conversations, 14 messages, and
  zero pre-existing long-term memories. A legacy backup was created before migration.

## Limits

- Automated voice UI tests inject audio services; they are not a human microphone test.
  The physical microphone is detected, but room noise and human recognition accuracy
  have not been validated.
- Speaking animation indicates TTS state, not the exact waveform. Listening animation
  uses microphone amplitude.
- Automatic memory extraction is limited to documented English patterns. Retrieval
  is bounded lexical matching with a small synonym map, not semantic search.
- Responses are not streamed and there is no cancel/stop-speaking button yet.
- Headless Chromium emitted GPU warnings and initially produced stale captures after
  resizing. Final visual checks used native Windows rendering with background occlusion
  disabled. Normal app launch does not disable the GPU or Chromium sandbox.

Reproduction commands and storage/backup details are in README.md. Diagnostic logs,
test-only databases, synthetic audio, JSON live-test reports, and screenshots are under
`data/verification/`, outside version control and separate from personal history.
# Web edition validation

- Netlify build passed: `node scripts/build-web.mjs`, including execution from the `web` base directory.
- Generated frontend JavaScript passed `node --check`.
- 16 tests passed across `test_web.py`, `test_core.py`, and `test_memory_conversations.py`.
- Web tests cover authentication, request limits, CORS, chat persistence, memory preservation, deletion confirmation, and failed model requests. AI responses are mocked.
- Desktop UI tests were not runnable in the deployment-preparation environment because PySide6 was absent. Desktop source files were not changed.
- Live Netlify hosting, hosted AI responses, browser rendering, and browser microphone/speech still require deployment verification. No authenticated hosting connection was available during preparation.

