"""Validated WebChannel API; persistent state and voice remain in Python."""
import json
import logging
import secrets
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication
from .config import MODEL
from .conversation import ConversationManager
from .memory import CATEGORIES
from .speech import Recorder, Transcriber, speak
from .storage import Store

log = logging.getLogger(__name__)


class Worker(QThread):
    def __init__(self, operation):
        super().__init__()
        self.operation, self.result, self.error = operation, None, None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as exc:
            self.error = str(exc)
            log.error("Background operation failed: %s", type(exc).__name__)


class Bridge(QObject):
    event = Signal(str)

    def __init__(self, store=None, responder=None, parent=None):
        super().__init__(parent)
        self.store = store or Store()
        self.conversations = ConversationManager(self.store, responder)
        sessions = self.store.sessions()
        self.session = sessions[0][0] if sessions else None
        self.page, self.mode, self.state = "chat", "text", "idle"
        self.status = "Ready when you are."
        self.worker = None
        self.recording = False
        self.recorder, self.transcriber = Recorder(), Transcriber()
        self.confirmation = None
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self.stop_recording)
        self.level_timer = QTimer(self)
        self.level_timer.timeout.connect(lambda: self.emit("level", value=self.recorder.level))

    def emit(self, event_type, **payload):
        self.event.emit(json.dumps(dict(type=event_type, **payload), ensure_ascii=False))

    def snapshot(self):
        self.emit("snapshot", sessions=self.store.session_details(), session=self.session,
                  messages=self.store.messages(self.session) if self.session else [],
                  memories=self.store.memory_details(), page=self.page, mode=self.mode,
                  state=self.state, status=self.status, busy=self.worker is not None,
                  recording=self.recording, model=MODEL,
                  autoMemory=self.store.setting("auto_memory", "true") == "true",
                  reducedMotion=self.store.setting("reduced_motion", "false") == "true")

    def error(self, message):
        self.state, self.status = "error", message
        self.emit("status", state=self.state, status=self.status, busy=self.worker is not None, recording=self.recording)

    @Slot(str)
    def dispatch(self, raw):
        try:
            if len(raw) > 150000:
                raise ValueError("Request is too large.")
            data = json.loads(raw)
            action = data.get("action")
            if action == "ready":
                self.snapshot()
                return
            if action == "copy":
                QApplication.clipboard().setText(str(data.get("text", ""))[:100000])
                return
            if self.worker:
                raise ValueError("Wait for Flux to finish the current operation.")
            if self.recording and action != "record":
                raise ValueError("Stop recording before changing pages or conversations.")
            if action == "new":
                self.session, self.page, self.state = None, "chat", "idle"
                self.status = "A fresh conversation. Your saved memories come with you."
                self.emit("clearInput")
            elif action == "load":
                identifier = str(data["id"])
                if identifier not in {i for i, _ in self.store.sessions()}:
                    raise ValueError("Conversation no longer exists.")
                self.session, self.page, self.state = identifier, "chat", "idle"
                self.status = "Conversation loaded."
                self.emit("clearInput")
            elif action == "page":
                if data["page"] not in ("chat", "memory", "voice", "settings"):
                    raise ValueError("Unknown page.")
                self.page = data["page"]
                if self.page in ("chat", "voice"):
                    self.mode = "voice" if self.page == "voice" else "text"
            elif action == "mode":
                if data["mode"] not in ("text", "voice"):
                    raise ValueError("Unknown mode.")
                self.mode = data["mode"]
                self.page = "voice" if self.mode == "voice" else "chat"
            elif action == "rename":
                self.store.rename_session(str(data["id"]), str(data["title"]))
                self.status = "Conversation renamed."
            elif action == "requestDelete":
                kind = data["kind"]
                if kind not in ("conversation", "memory", "allMemories"):
                    raise ValueError("Unknown deletion request.")
                token = secrets.token_urlsafe(24)
                self.confirmation = (token, kind, data.get("id"))
                self.emit("confirmDelete", token=token, kind=kind)
                return
            elif action == "cancelDelete":
                self.confirmation = None
                return
            elif action == "confirmDelete":
                if not self.confirmation or data.get("token") != self.confirmation[0]:
                    raise ValueError("Deletion confirmation expired. Try again.")
                _, kind, identifier = self.confirmation
                self.confirmation = None
                if kind == "conversation":
                    self.store.delete_session(str(identifier))
                    if self.session == identifier:
                        self.session, self.page = None, "chat"
                        self.emit("clearInput")
                    self.status = "Conversation deleted. Long-term memories were kept."
                elif kind == "memory":
                    self.store.forget(int(identifier))
                    self.status = "Memory deleted. Mentions in chat history remain."
                else:
                    self.store.clear_memories()
                    self.status = "Long-term memories cleared. Chat history was kept."
            elif action == "saveMemory":
                text, category = str(data["text"]), data["category"]
                if category not in CATEGORIES:
                    raise ValueError("Unknown memory category.")
                if data.get("id") is None:
                    self.conversations.memory.add(text, category)
                else:
                    self.conversations.memory.edit(int(data["id"]), text, category)
                self.status = "Memory saved."
            elif action == "setting":
                if data["key"] not in ("auto_memory", "reduced_motion") or not isinstance(data["value"], bool):
                    raise ValueError("Invalid setting.")
                self.store.set_setting(data["key"], "true" if data["value"] else "false")
                self.status = "Setting saved."
            elif action == "send":
                self.send(str(data["text"]))
                return
            elif action == "record":
                self.stop_recording() if self.recording else self.start_recording()
                return
            else:
                raise ValueError("Unknown action.")
            self.snapshot()
        except Exception as exc:
            log.error("UI request failed: %s", type(exc).__name__)
            self.error(str(exc))
            if isinstance(locals().get("data"), dict) and data.get("action") == "send":
                self.emit("sendRejected")

    def run_operation(self, operation, callback, state, status):
        self.callback = callback
        self.worker = Worker(operation)
        self.worker.finished.connect(self.complete)
        self.state, self.status = state, status
        self.snapshot()
        self.worker.start()

    @Slot()
    def complete(self):
        worker, callback = self.worker, self.callback
        self.worker = None
        worker.deleteLater()
        if worker.error:
            self.error(worker.error)
            self.emit("requestFailed")
            self.snapshot()
            return
        try:
            callback(worker.result)
        except Exception as exc:
            self.error(str(exc))
            self.snapshot()

    def send(self, question):
        question = question.strip()
        if not question or len(question) > 4000:
            raise ValueError("Write a message between 1 and 4,000 characters.")
        if question.startswith("/"):
            command, _, argument = question.partition(" ")
            if command == "/remember":
                self.conversations.memory.add(argument)
                self.status = "Saved to long-term memory."
            elif command == "/memories":
                self.page = "memory"
            elif command == "/forget":
                self.dispatch(json.dumps(dict(action="requestDelete", kind="memory", id=int(argument))))
            else:
                raise ValueError("Commands: /remember FACT, /memories, /forget ID")
            self.emit("clearInput")
            self.snapshot()
            return
        if self.session is None:
            self.session = self.store.new_session()
        session, voice = self.session, self.mode == "voice"
        self.emit("pending", text=question)

        def answered(result):
            # The browser already cleared the submitted text. Leave its next draft alone.
            self.emit("turnCompleted")
            self.state = "idle"
            self.status = result.warning or (f"Saved {result.remembered} memory. You can edit it in Memory." if result.remembered else "Conversation saved.")
            self.snapshot()
            if voice:
                def spoken(_):
                    self.state = "idle"
                    self.status = result.warning or "Ready when you are."
                    self.snapshot()
                self.run_operation(lambda: speak(result.answer), spoken, "speaking", "Speaking · Windows voice")

        self.run_operation(lambda: self.conversations.send(session, question), answered,
                           "thinking", "Thinking locally… The first response may take a few minutes.")

    def start_recording(self):
        try:
            self.recorder.start()
        except Exception as exc:
            raise RuntimeError(f"Microphone unavailable: {exc}. Check Windows microphone permissions and voice packages.") from exc
        self.recording = True
        self.mode, self.page, self.state = "voice", "voice", "listening"
        self.status = "Listening… Stop when you’re finished. Maximum 30 seconds."
        self.record_timer.start(30000)
        self.level_timer.start(80)
        self.snapshot()

    @Slot()
    def stop_recording(self):
        if not self.recording:
            return
        self.record_timer.stop()
        self.level_timer.stop()
        self.recording = False
        try:
            audio = self.recorder.stop()
            def transcribed(text):
                self.state = "idle"
                self.status = "Review your transcript, then Send."
                self.emit("transcript", text=text[:4000])
                self.snapshot()
            self.run_operation(lambda: self.transcriber.transcribe(audio), transcribed,
                               "thinking", "Transcribing on your PC…")
        except Exception as exc:
            self.error(str(exc))
            self.snapshot()

    def shutdown(self):
        if self.worker is not None:
            self.error("Wait for the current operation to finish, then close Flux again.")
            return False
        if self.recording:
            self.record_timer.stop()
            self.level_timer.stop()
            self.recording = False
            try:
                self.recorder.stop()
            except Exception:
                pass
        return True
