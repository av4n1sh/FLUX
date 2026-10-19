"""Headless, single-owner controller using the desktop event protocol."""
import json
import logging
import secrets
from .config import MODEL
from .conversation import ConversationManager
from .memory import CATEGORIES

log = logging.getLogger(__name__)


class WebController:
    def __init__(self, store, responder=None):
        self.store = store
        self.conversations = ConversationManager(store, responder)
        sessions = store.sessions()
        self.session = sessions[0][0] if sessions else None
        self.page, self.mode, self.state = "chat", "text", "idle"
        self.status = "Connected to your Flux server."
        self.worker = None
        self.recording = False
        self.confirmation = None
        self.events = []

    def emit(self, event_type, **payload):
        self.events.append(dict(type=event_type, **payload))

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
                pass  # Clipboard is handled by the browser.
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
                raise ValueError("Use browser voice controls.")
                return
            else:
                raise ValueError("Unknown action.")
            self.snapshot()
        except Exception as exc:
            log.error("UI request failed: %s", type(exc).__name__)
            self.error(str(exc))
            if isinstance(locals().get("data"), dict) and data.get("action") == "send":
                self.emit("sendRejected")

    def send(self, question):
        question = question.strip()
        if not question or len(question) > 4000:
            raise ValueError("Write a message between 1 and 4,000 characters.")
        if question.startswith("/"):
            command, _, argument = question.partition(" ")
            if command == "/remember":
                self.conversations.memory.add(argument)
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
        result = self.conversations.send(self.session, question)
        self.emit("turnCompleted")
        self.state, self.status = "idle", result.warning or "Conversation saved."
        self.snapshot()
        if self.mode == "voice":
            self.emit("speak", text=result.answer)
