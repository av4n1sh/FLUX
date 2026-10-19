"""Real Qt WebEngine + WebChannel tests using disposable databases."""
import json
import os
from pathlib import Path
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from flux.storage import Store
from flux.ui import Window

APP = QApplication.instance() or QApplication([])


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.db")
        self.window = Window(self.store, lambda _: "Python.\n\n## A useful detail\n- Saved locally\n```python\nprint('hello')\n```")
        self.window.show()
        self.wait(lambda: self.js("document.body.dataset.ready") == "true", 15)

    def tearDown(self):
        self.wait(lambda: self.window.bridge.worker is None)
        self.window.close()
        self.window.browser_page.deleteLater()
        QTest.qWait(100)
        self.window.deleteLater()
        QTest.qWait(100)
        self.tmp.cleanup()

    def wait(self, predicate, timeout=8):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            APP.processEvents()
            if predicate():
                return
            QTest.qWait(25)
        self.fail("Timed out waiting for desktop state")

    def js(self, code):
        result = []
        self.window.browser_page.runJavaScript(code, lambda value: result.append(value))
        until = time.monotonic() + 5
        while not result and time.monotonic() < until:
            APP.processEvents()
            QTest.qWait(5)
        if not result:
            self.fail("JavaScript callback timed out")
        return result[0]

    def click(self, selector):
        self.js(f"document.querySelector({json.dumps(selector)}).click()")
        QTest.qWait(80)

    def fill(self, selector, value):
        self.js(f"document.querySelector({json.dumps(selector)}).value={json.dumps(value)}; document.querySelector({json.dumps(selector)}).dispatchEvent(new Event('input'))")

    def submit_dialog(self):
        self.js("document.querySelector('#modal-form').requestSubmit()")
        QTest.qWait(100)

    def test_connected_chat_memory_rename_delete_and_restart(self):
        self.fill("#input", "My favorite programming language is Python.")
        self.click("#send")
        self.wait(lambda: len(self.store.memories()) == 1 and self.window.bridge.worker is None)
        self.wait(lambda: self.js("document.querySelectorAll('.message').length") == 2)
        session = self.window.bridge.session
        self.assertEqual(len(self.store.messages(session)), 2)
        self.assertEqual(self.js("document.querySelectorAll('.message pre').length"), 1)
        self.click(".session-menu-button")
        self.click("#rename-chat")
        self.fill("#rename-title", "Python preference")
        self.submit_dialog()
        self.assertEqual(self.store.sessions()[0][1], "Python preference")
        self.click("[data-page='memory']")
        self.assertEqual(self.js("document.querySelectorAll('.memory-card').length"), 1)
        self.click(".memory-card button")
        self.fill("#memory-text", "My favorite programming language is Rust.")
        self.submit_dialog()
        self.assertIn("Rust", self.store.memories()[0][1])
        self.click("[data-page='chat']")
        self.click(".session-menu-button")
        self.click("#delete-chat")
        self.wait(lambda: self.js("document.querySelector('#modal').open"))
        self.click("#modal-cancel")
        self.assertEqual(len(self.store.sessions()), 1)
        self.click(".session-menu-button")
        self.click("#delete-chat")
        self.submit_dialog()
        self.assertEqual(Store(self.store.path).sessions(), [])
        self.assertEqual(len(self.store.memories()), 1)
        self.assertEqual(self.window.bridge.session, None)
        self.assertFalse(self.js("document.querySelector('#welcome').hidden"))
        self.click("[data-page='memory']")
        self.click(".memory-card button:last-child")
        self.submit_dialog()
        self.assertEqual(Store(self.store.path).memories(), [])

    def test_layout_orb_settings_and_error_states(self):
        output = Path(__file__).resolve().parents[1] / "data" / "verification"
        output.mkdir(parents=True, exist_ok=True)
        QTest.qWait(300)
        self.assertTrue(self.js("document.querySelector('.orb img').naturalWidth > 0"))
        self.window.grab().save(str(output / "flux-welcome.png"))
        for width, height in [(1280, 820), (760, 580), (1600, 1000)]:
            self.window.resize(width, height)
            QTest.qWait(120)
            self.assertTrue(self.js("document.documentElement.scrollWidth <= innerWidth"))
            self.assertTrue(self.js("document.querySelector('.composer').getBoundingClientRect().bottom <= innerHeight"))
        self.window.resize(1280, 820)
        QTest.qWait(500)
        self.click("[data-page='voice']")
        self.assertFalse(self.js("document.querySelector('#voice-page').hidden"))
        self.assertEqual(self.window.bridge.mode, "voice")
        QTest.qWait(500)
        self.window.grab().save(str(output / "flux-voice.png"))
        self.click("[data-page='settings']")
        self.click("#auto-memory")
        self.assertEqual(self.store.setting("auto_memory"), "false")
        self.click("#reduce-motion")
        self.assertTrue(self.js("document.body.classList.contains('reduced-motion')"))
        with patch.object(self.window.bridge.recorder, "start", side_effect=RuntimeError("Test microphone unavailable")):
            self.click("[data-page='voice']")
            self.click("#voice-record")
            self.assertEqual(self.js("document.body.dataset.state"), "error")
            self.assertFalse(self.window.bridge.recording)
        self.click("[data-page='memory']")
        self.assertLess(self.js("document.querySelector('.empty-memory svg').getBoundingClientRect().height"), 40)
        self.click("#add-memory")
        self.fill("#memory-text", '<img src="file:///C:/secret" onerror="alert(1)">')
        self.submit_dialog()
        self.assertEqual(self.js("document.querySelectorAll('.memory-card img').length"), 0)
        QTest.qWait(500)
        self.window.grab().save(str(output / "flux-memory.png"))

    def test_orb_internal_pixels_and_outline_change_in_both_renderers(self):
        self.wait(lambda: self.js("FluxPlasma.ready && FluxPlasma.frames > 2"))
        sample = """JSON.stringify((()=>{
            const c=document.querySelector('#welcome .orb-plasma'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            const inside=[],edge=[];
            for(let y=4;y<c.height;y+=4)for(let x=4;x<c.width;x+=4){
                const r=Math.hypot(x/c.width-.5,y/c.height-.5),i=(y*c.width+x)*4;
                if(r<.27)inside.push(d[i],d[i+1],d[i+2]);
                if(r>.34 && r<.40)edge.push(d[i+3]);
            }return {inside,edge};})())"""
        reports = []
        for fallback in (False, True):
            if fallback:
                self.js("FluxPlasma.useFallback()")
                QTest.qWait(200)
                self.assertEqual(self.js("FluxPlasma.kind"), "canvas")
            before = json.loads(self.js(sample))
            QTest.qWait(2200)
            after = json.loads(self.js(sample))
            for region in ("inside", "edge"):
                changes = [abs(a-b) for a,b in zip(before[region],after[region])]
                self.assertGreater(sum(changes)/len(changes), .5, region)
                self.assertGreater(max(changes)-min(changes), 5, region)
            reports.append(json.loads(self.js("JSON.stringify(FluxPlasma.diagnostics)")))
        output = Path(__file__).resolve().parents[1] / "data" / "verification"
        output.mkdir(parents=True, exist_ok=True)
        (output / "plasma-renderers.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")

    def test_voice_pipeline_with_injected_audio_services(self):
        bridge = self.window.bridge
        with patch.object(bridge.recorder, "start"), patch.object(bridge.recorder, "stop", return_value=[0]), patch.object(bridge.transcriber, "transcribe", return_value="My favorite food is pasta."), patch("flux.bridge.speak") as speech:
            self.click("#mic")
            self.assertTrue(bridge.recording)
            self.assertEqual(self.js("document.body.dataset.state"), "listening")
            self.click("#voice-record")
            self.wait(lambda: bridge.worker is None)
            self.assertEqual(self.js("document.querySelector('#input').value"), "My favorite food is pasta.")
            self.click("#send")
            self.wait(lambda: speech.called and bridge.worker is None)
            self.assertEqual(len(self.store.memories()), 1)
            self.assertEqual(bridge.state, "idle")

    def test_immediate_send_deduplicates_and_orb_moves_during_work(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        calls = []
        def delayed(context):
            calls.append(context)
            gate.wait(10)
            return "A clear answer."
        self.window.bridge.conversations.responder = delayed
        initial_phase = self.js("FluxOrb.phase")
        initial_transform = self.js("getComputedStyle(document.querySelector('.presence .orb-core')).transform")
        QTest.qWait(650)
        self.assertGreater(self.js("FluxOrb.phase"), initial_phase)
        self.assertNotEqual(self.js("getComputedStyle(document.querySelector('.presence .orb-core')).transform"), initial_transform)
        self.fill("#input", "Explain an idea.")
        self.js("document.querySelector('#input').focus()")
        QTest.keyClick(self.window.web.focusProxy(), Qt.Key.Key_Return)
        self.wait(lambda: len(calls) == 1)
        self.assertEqual(self.js("document.querySelector('#input').value"), "")
        self.assertFalse(self.js("document.querySelector('#input').disabled"))
        self.assertEqual(self.js("document.querySelectorAll('.message.user').length"), 1)
        self.assertEqual(self.js("document.querySelectorAll('.thinking-card .orb-live').length"), 1)
        self.assertEqual(self.js("document.body.dataset.state"), "thinking")
        self.js("window.firstCard=document.querySelector('.message.user');window.thinkingOrb=document.querySelector('.thinking-card .orb-live')")
        phase = self.js("FluxOrb.phase")
        self.fill("#input", "My next draft")
        self.click("#send")
        self.js("document.querySelector('#input').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',repeat:true}))")
        QTest.qWait(650)
        self.assertEqual(len(calls), 1)
        self.assertGreater(self.js("FluxOrb.phase"), phase)
        self.assertEqual(self.js("document.querySelectorAll('.message.user').length"), 1)
        gate.set()
        self.wait(lambda: self.window.bridge.worker is None)
        self.wait(lambda: self.js("document.querySelectorAll('.message.assistant').length") == 1)
        self.assertEqual(self.js("document.querySelector('#input').value"), "My next draft")
        self.assertTrue(self.js("firstCard===document.querySelector('.message.user')"))
        self.assertTrue(self.js("thinkingOrb===document.querySelector('.message.assistant .orb-live')"))
        self.assertTrue(self.js("document.querySelector('.message.assistant').classList.contains('message-enter')"))
        self.assertEqual(len(self.store.messages(self.window.bridge.session)), 2)
        # The same centralized function handles the button, and double clicks cannot duplicate it.
        self.click("#send")
        self.wait(lambda: self.window.bridge.worker is None)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(self.store.messages(self.window.bridge.session)), 4)

    def test_failed_send_keeps_new_draft_and_can_retry(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        def failed(_):
            gate.wait(10)
            raise RuntimeError("Test Ollama disconnected")
        self.window.bridge.conversations.responder = failed
        self.fill("#input", "Please answer this")
        self.click("#send")
        self.assertEqual(self.js("document.querySelector('#input').value"), "")
        self.fill("#input", "Keep this separate draft")
        gate.set()
        self.wait(lambda: self.window.bridge.worker is None)
        self.wait(lambda: self.js("document.querySelectorAll('.message-failure').length") == 1)
        self.assertEqual(self.js("document.querySelector('#input').value"), "Keep this separate draft")
        self.assertEqual(self.store.messages(self.window.bridge.session), [])
        self.window.bridge.conversations.responder = lambda _: "Recovered."
        self.click(".message-failure button")
        self.wait(lambda: self.window.bridge.worker is None)
        self.wait(lambda: len(self.store.messages(self.window.bridge.session)) == 2)
        self.assertEqual(self.js("document.querySelectorAll('.message-failure').length"), 0)
        self.assertEqual(self.js("document.querySelectorAll('.message.user').length"), 1)
        self.assertEqual(self.js("document.querySelector('#input').value"), "Keep this separate draft")

    def test_multiline_long_chat_scroll_resize_and_reduced_motion(self):
        self.fill("#input", "First line")
        self.js("document.querySelector('#input').focus();document.querySelector('#input').setSelectionRange(10,10)")
        QTest.keyClick(self.window.web.focusProxy(), Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.js("document.querySelector('#input').value"), "First line\n")
        self.assertEqual(self.store.sessions(), [])
        a, b = self.store.new_session(), self.store.new_session()
        for i in range(10):
            self.store.save_turn(a, "Question " + str(i), "An earlier answer. " * 20)
        self.window.bridge.dispatch(json.dumps({"action":"load", "id":a}))
        QTest.qWait(200)
        self.window.bridge.conversations.responder = lambda _: "## Long answer\n\n" + "A thoughtful paragraph. " * 500 + "\n\n```python\nprint('safe')\n```"
        self.fill("#input", "A long question. " * 150)
        self.js("window.scrollCalls=[];const originalScroll=document.querySelector('#chat-scroll').scrollTo;document.querySelector('#chat-scroll').scrollTo=function(options){scrollCalls.push(options.behavior);return originalScroll.call(this,options)};window.oldCard=document.querySelector('.message')")
        self.click("#send")
        self.wait(lambda: self.window.bridge.worker is None)
        self.wait(lambda: self.js("document.querySelectorAll('.message').length") == 22)
        self.assertTrue(self.js("scrollCalls.includes('smooth')"))
        self.assertTrue(self.js("oldCard===document.querySelector('.message')"))
        self.assertEqual(self.js("document.querySelectorAll('.message pre').length"), 1)
        for width, height in [(760,580),(1280,820)]:
            self.window.resize(width,height)
            QTest.qWait(200)
            self.assertTrue(self.js("document.documentElement.scrollWidth<=innerWidth"))
        self.window.bridge.dispatch(json.dumps({"action":"load", "id":b}))
        QTest.qWait(120)
        self.assertEqual(self.js("document.querySelectorAll('.message').length"), 0)
        self.click("[data-page='settings']")
        self.click("#reduce-motion")
        phase=self.js("FluxOrb.phase")
        QTest.qWait(350)
        self.assertGreater(self.js("FluxOrb.phase"),phase)


if __name__ == "__main__":
    unittest.main()
