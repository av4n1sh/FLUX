"""Conservative fact learning and bounded lexical retrieval; no generated facts."""
import logging
import re

log = logging.getLogger(__name__)
CATEGORIES = ["Preferences", "Personal", "Projects", "Goals", "Work", "Other"]
STOP = set("i my me you your what which is are do does did can could would should a an the about tell know remember of to for it that please like".split())
SYNONYMS = {"favourite": "favorite", "prefer": "preference", "preferred": "preference", "preferences": "preference", "favorite": "preference", "enjoy": "preference", "likes": "preference", "coding": "programming", "languages": "language", "job": "work", "working": "work", "called": "name"}


def tokens(text):
    return {SYNONYMS.get(w, w) for w in re.findall(r"[\w]+", text.lower()) if w not in STOP}


def extract_facts(text):
    # Only whole declarative first-person sentences. Never scan quoted text, code,
    # questions, hypothetical prompts or credentials for automatic memories.
    if any(mark in text for mark in ('```', '"', '“', '?')):
        return []
    if re.search(r"\b(password|secret|token|api key|credit card|ssn|pretend|imagine|hypothetically)\b", text, re.I):
        return []
    patterns = [
        (r"my favou?rite ([\w ]{2,45}) is (.{1,130})", "Preferences", lambda m: "favorite:" + m[1].lower()),
        (r"i prefer (.{1,150})", "Preferences", lambda m: "prefer:" + m[1].lower()),
        (r"i (?:like|love|enjoy) (.{1,150})", "Preferences", lambda m: "likes:" + m[1].lower()),
        (r"my name is ([\w -]{1,70})", "Personal", lambda m: "name"),
        (r"(?:please )?call me ([\w -]{1,70})", "Personal", lambda m: "name"),
        (r"i (?:am|work as) (?:a|an) (.{1,120})", "Work", lambda m: "occupation"),
        (r"i(?: am|'m) working on (.{1,150})", "Projects", lambda m: "project:" + m[1].lower()),
        (r"my goal is to (.{1,150})", "Goals", lambda m: "goal:" + m[1].lower()),
    ]
    results = []
    for sentence in re.split(r"[.!\n]+", text.strip()):
        sentence = sentence.strip()
        for pattern, category, key in patterns:
            match = re.fullmatch(pattern, sentence, re.I)
            if match:
                results.append((sentence.rstrip("." ) + ".", category, key(match)))
                break
    return results[:3]


class MemoryManager:
    def __init__(self, store):
        self.store = store

    def learn(self, text):
        if self.store.setting("auto_memory", "true") != "true":
            return []
        return [self.store.remember(content, category, key) for content, category, key in extract_facts(text)]

    def add(self, text, category="Other"):
        facts = extract_facts(text)
        key = facts[0][2] if len(facts) == 1 else None
        return self.store.remember(text, category, key)

    def edit(self, identifier, text, category):
        facts = extract_facts(text)
        self.store.edit_memory(identifier, text, category, facts[0][2] if len(facts) == 1 else None)

    def retrieve(self, question, limit=6):
        query = tokens(question)
        broad = bool(re.search(r"(?:what.*(?:know|remember).*me|who am i)", question, re.I))
        ranked = []
        try:
            for fact in self.store.memory_details():
                overlap = query & tokens(fact["content"])
                score = len(overlap)
                if broad:
                    score += 1
                if score:
                    ranked.append((score, fact["updated"], fact["id"], fact["content"]))
            ranked.sort(reverse=True)
            selected = [(identifier, content) for _, _, identifier, content in ranked[:limit]]
            log.info("Memory retrieved; ids=%s", [i for i, _ in selected])
            return selected
        except Exception:
            log.error("Memory retrieval failed", exc_info=False)
            raise
