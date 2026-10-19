"""Desktop shell for Flux's local HTML/CSS frontend."""
from pathlib import Path
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from .bridge import Bridge

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "frontend"


class LocalAssetsOnly(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = url.toString() == "qrc:///qtwebchannel/qwebchannel.js"
        if url.isLocalFile():
            path = Path(url.toLocalFile()).resolve()
            allowed = path in {WEB / "index.html", WEB / "style.css", WEB / "motion.css",
                               WEB / "app.js", WEB / "orb.js", WEB / "plasma.js", ROOT / "assets" / "flux-orb.png"}
        info.block(not allowed)


class LocalPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        import logging
        logging.getLogger(__name__).warning("Frontend console at line %s: %s", line, message)

    def acceptNavigationRequest(self, url, navigation_type, main_frame):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == WEB / "index.html"

    def createWindow(self, window_type):
        return None


class Window(QMainWindow):
    def __init__(self, store=None, responder=None):
        super().__init__()
        self.setWindowTitle("Flux — Your personal AI")
        self.setWindowIcon(QIcon(str(ROOT / "assets" / "flux-orb.png")))
        self.resize(1280, 820)
        self.setMinimumSize(760, 580)
        self.web = QWebEngineView(self)
        self.setCentralWidget(self.web)
        self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.profile = QWebEngineProfile(self.web)
        self.interceptor = LocalAssetsOnly(self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        self.browser_page = LocalPage(self.profile, self.web)
        self.browser_page.setBackgroundColor(QColor("#101115"))
        self.web.setPage(self.browser_page)
        settings = self.browser_page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        self.bridge = Bridge(store, responder, self)
        self.channel = QWebChannel(self.browser_page)
        self.channel.registerObject("flux", self.bridge)
        self.browser_page.setWebChannel(self.channel)
        self.web.load(QUrl.fromLocalFile(str(WEB / "index.html")))

    def closeEvent(self, event):
        if self.bridge.shutdown():
            event.accept()
        else:
            event.ignore()
