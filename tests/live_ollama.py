"""Explicit live desktop test: run learn, then recall in separate processes."""
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from flux import brain
from flux.storage import Store
from flux.ui import Window

app = QApplication([])
output = ROOT / "data" / "verification"
output.mkdir(parents=True, exist_ok=True)
phase = sys.argv[1]
assert phase in ("learn", "recall")
captured = []


def responder(context):
    captured.append(context)
    return brain.reply(context)


marker = output / "live-database.txt"
if phase == "learn":
    database_name = "live-" + uuid4().hex + ".db"
    marker.write_text(database_name, encoding="utf-8")
else:
    database_name = marker.read_text(encoding="utf-8").strip()
    assert Path(database_name).name == database_name
store = Store(output / database_name)
if phase == "learn":
    assert not store.memories()
window = Window(store, responder)
window.show()


def js(code):
    result = []
    window.browser_page.runJavaScript(code, lambda value: result.append(value))
    until = time.monotonic() + 5
    while not result and time.monotonic() < until:
        app.processEvents()
        QTest.qWait(10)
    return result[0] if result else None


def wait(predicate, timeout):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(30)
    raise RuntimeError("Live desktop verification timed out")


wait(lambda: js("document.body.dataset.ready") == "true", 20)
idle_transform = js("document.querySelector('.presence .orb-core').style.transform")
QTest.qWait(650)
assert js("document.querySelector('.presence .orb-core').style.transform") != idle_transform
js("document.querySelector('#new-chat').click()")
QTest.qWait(150)
question = "My favorite programming language is Python." if phase == "learn" else "What programming language do I like?"
js("document.querySelector('#input').value=" + json.dumps(question) + ";document.querySelector('#input').dispatchEvent(new Event('input'));document.querySelector('#send').click()")
assert js("document.querySelector('#input').value") == ""
assert js("document.querySelectorAll('.message.user').length") == 1
wait(lambda: bool(captured), 10)
pixel_sample = """JSON.stringify((()=>{const c=document.querySelector('.presence .orb-plasma');
    return Array.from(c.getContext('2d').getImageData(20,20,40,40).data);})())"""
working_pixels = js(pixel_sample)
was_working = window.bridge.worker is not None
QTest.qWait(650)
animated_during_llm = was_working and window.bridge.worker is not None and js(pixel_sample) != working_pixels
assert animated_during_llm, "Internal orb pixels did not change while the LLM worker was running"
window.grab().save(str(output / "orb-thinking.png"))
wait(lambda: window.bridge.worker is None, 200)
assert window.bridge.state != "error", window.bridge.status
messages = window.bridge.store.messages(window.bridge.session)
assert len(messages) == 2, messages
assert window.bridge.store.memories()
if phase == "recall":
    assert "Python" in captured[0][0]["content"]
    assert "python" in messages[-1]["content"].lower()
    assert "</think>" not in messages[-1]["content"]
QTest.qWait(250)
window.grab().save(str(output / ("live-" + phase + ".png")))
report = {"phase": phase, "passed": True, "model": brain.MODEL, "answer": messages[-1]["content"], "animated_during_llm": animated_during_llm,
          "internal_pixels_animated_during_llm": animated_during_llm,
          "renderer": json.loads(js("JSON.stringify(FluxPlasma.diagnostics)")),
          "memory_count": len(window.bridge.store.memories()), "memory_injected": "Python" in captured[0][0]["content"]}
(output / ("live-" + phase + ".json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=True), flush=True)
window.close()
window.browser_page.deleteLater()
QTest.qWait(100)
window.deleteLater()
QTest.qWait(100)
