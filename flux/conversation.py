"""Application pipeline shared by the desktop and integration tests."""
from dataclasses import dataclass
import logging
from . import brain
from .memory import MemoryManager

log = logging.getLogger(__name__)


@dataclass
class TurnResult:
    answer: str
    remembered: int = 0
    warning: str = ""


class ConversationManager:
    def __init__(self, store, responder=None):
        self.store = store
        self.memory = MemoryManager(store)
        self.responder = responder or brain.reply

    def context(self, session, question):
        facts = self.memory.retrieve(question)
        return brain.build_context(self.store.messages(session, limit=12), facts, question)

    def send(self, session, question):
        answer = self.responder(self.context(session, question))
        self.store.save_turn(session, question, answer)
        result = TurnResult(answer)
        try:
            result.remembered = len(self.memory.learn(question))
        except Exception:
            log.error("Memory save failed after conversation was saved", exc_info=False)
            result.warning = "Your conversation was saved, but memory could not be updated. Check the Memory page and local log."
        return result
