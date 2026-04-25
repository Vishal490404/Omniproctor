import sys
import os
import atexit
import ctypes
from typing import List
from urllib.parse import parse_qs, unquote, urlparse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QHBoxLayout, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineSettings, QWebEngineScript
)
from PyQt6.QtCore import QUrl, QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication

from keyblocks import (
    install_emergency_handlers as install_keyblock_emergency_handlers,
    set_target_browser_window,
    start_exam_kiosk_mode,
    stop_exam_kiosk_mode,
)
from log_setup import configure_file_logging
from network.native_firewall_controller import NativeFirewallController, emergency_firewall_cleanup
from protocol_handler import ensure_registered, register, unregister

NO_SYSTEM_LOCKDOWN_FLAG = "--no-system-lockdown"

WDA_EXCLUDEFROMCAPTURE = 0x00000011
WDA_NONE = 0x00000000


# -------------------------
# Background Workers
# -------------------------
class NetworkWorker(QThread):
    """Run NativeFirewallController.enter_exam_mode in a background thread."""
    finished_success = pyqtSignal()
    finished_failure = pyqtSignal(str)

    def __init__(self, browser_exe_path: str, parent=None):
        super().__init__(parent)
        self.browser_exe_path = browser_exe_path
        self.controller: NativeFirewallController | None = None
        self.last_failure: str | None = None

    def run(self):
        try:
            self.controller = NativeFirewallController(self.browser_exe_path)
            success = self.controller.enter_exam_mode()
            if success:
                self.finished_success.emit()
            else:
                # Surface the real underlying error from the backend instead of
                # a generic "returned False" so operators can debug WFP issues.
                backend = getattr(self.controller, "_backend", None)
                detail = getattr(backend, "last_error", None) or "enter_exam_mode returned False"
                self.last_failure = detail
                self.finished_failure.emit(self.last_failure)
        except Exception as e:
            self.last_failure = f"{type(e).__name__}: {e}"
            self.finished_failure.emit(self.last_failure)

    def cleanup(self):
        """Restore firewall state."""
        try:
            if self.controller:
                self.controller.exit_exam_mode()
        except Exception:
            pass


class KioskWorker(QThread):
    """Run start_exam_kiosk_mode in background (it may block)."""
    finished_success = pyqtSignal()
    finished_failure = pyqtSignal(str)

    def __init__(self, hwnd: int, system_lockdown: bool = True, parent=None):
        super().__init__(parent)
        self.hwnd = hwnd
        self.system_lockdown = system_lockdown

    def run(self):
        try:
            ok = start_exam_kiosk_mode(
                self.hwnd, system_lockdown=self.system_lockdown
            )
            if ok:
                self.finished_success.emit()
            else:
                self.finished_failure.emit("start_exam_kiosk_mode returned False")
        except Exception as e:
            self.finished_failure.emit(str(e))


# -------------------------
# WebEngine Page (Popup handling)
# -------------------------
class CustomWebEnginePage(QWebEnginePage):
    """Custom page to handle popups and feature permissions with robust popup lifecycle."""
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.popup_windows: List[QWebEngineView] = []
        self.parent_browser = parent

    def createWindow(self, type):
        try:
            popup_view = QWebEngineView()
            popup_page = CustomWebEnginePage(self.profile(), popup_view)
            popup_view.setPage(popup_page)
            popup_view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            popup_view.setWindowFlag(Qt.WindowType.Window, True)
            popup_view.resize(800, 600)
            popup_view.setWindowTitle("OmniProctor - Secure Browser")

            self.popup_windows.append(popup_view)

            popup_page.windowCloseRequested.connect(lambda pv=popup_view: self._close_popup(pv))

            def on_url_changed(url):
                url_str = url.toString()
                print("Popup urlChanged:", url_str)
                if url_str in ("", "about:blank", "data:,", "data:text/html,", "data:text/html;charset=utf-8,"):
                    QTimer.singleShot(400, lambda pv=popup_view: self._close_popup_if_blank(pv))

            popup_page.urlChanged.connect(on_url_changed)

            def on_load_finished(ok):
                if ok:
                    QTimer.singleShot(300, lambda pv=popup_view: self._close_popup_if_blank(pv))
            popup_page.loadFinished.connect(on_load_finished)

            popup_view.show()

            QTimer.singleShot(3000, lambda pv=popup_view: self._close_popup_if_blank(pv))

            return popup_page
        except Exception as e:
            print("Error creating popup window:", e)
            return super().createWindow(type)

    def _close_popup(self, popup_view):
        try:
            if popup_view in self.popup_windows:
                self.popup_windows.remove(popup_view)
            popup_view.close()
            popup_view.deleteLater()
            print("Popup closed and cleaned up")
        except Exception as e:
            print("Error closing popup:", e)

    def _close_popup_if_blank(self, popup_view):
        try:
            if not popup_view:
                return
            page = popup_view.page()
            if not page:
                self._close_popup(popup_view)
                return
            url = page.url().toString()
            if (not url) or url.startswith("about:blank") or url.startswith("data:") or not url.strip():
                print("Auto-closing blank popup (detected):", url)
                self._close_popup(popup_view)
        except Exception as e:
            print("Error in _close_popup_if_blank:", e)


# -------------------------
# Main Secure Browser Window
# -------------------------
class SecureBrowser(QMainWindow):
    def __init__(
        self,
        url: str,
        browser_exe_path: str | None = None,
        system_lockdown: bool = True,
    ):
        super().__init__()
        self.setWindowTitle("Secure Kiosk Browser")

        self.kiosk_active = False
        self.network_worker: NetworkWorker | None = None
        self.kiosk_worker: KioskWorker | None = None
        self.browser_exe_path = browser_exe_path or sys.executable
        self.target_url = url
        self.network_protection_ready = False
        self._target_url_loaded = False
        self._shutdown_started = False
        self.system_lockdown = system_lockdown

        # UI setup
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Control panel
        control_panel = QWidget()
        control_panel.setFixedHeight(45)
        control_panel.setStyleSheet("background-color: #1a202c; border-bottom: 1px solid #2d3748;")
        control_layout = QHBoxLayout(control_panel)

        self.exit_button = QPushButton("End Session")
        self.exit_button.setFixedSize(110, 32)
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #e53e3e;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-size: 12px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #c53030;
            }
            QPushButton:pressed {
                background-color: #9c2626;
            }
        """)
        self.exit_button.clicked.connect(self.confirm_exit)
        control_layout.addStretch()
        control_layout.addWidget(self.exit_button)
        control_layout.setContentsMargins(10, 5, 10, 5)

        # Browser / profile setup
        self.browser = QWebEngineView()
        default_page = self.browser.page()
        self.profile = default_page.profile() if default_page else None

        if self.profile:
            self.configure_browser_settings()
        else:
            print("Warning: No profile available for browser configuration")

        self.custom_page = CustomWebEnginePage(self.profile, self.browser)
        self.custom_page.featurePermissionRequested.connect(self.handle_permission_request)
        self.custom_page.fullScreenRequested.connect(self.handle_fullscreen_request)

        self.browser.setPage(self.custom_page)

        self.browser.setUrl(QUrl("about:blank"))

        layout.addWidget(control_panel)
        layout.addWidget(self.browser)

        self.setWindowFullScreen()

        QTimer.singleShot(0, self.start_protections_parallel)
        QTimer.singleShot(300, self.check_monitors)

        self.setup_security_monitoring()

        try:
            app = QGuiApplication.instance()
            if app:
                if hasattr(app, 'screenAdded'):
                    getattr(app, 'screenAdded').connect(lambda s: self.inject_screen_info_script())
                if hasattr(app, 'screenRemoved'):
                    getattr(app, 'screenRemoved').connect(lambda s: self.inject_screen_info_script())
                print("Screen change monitoring enabled")
        except (AttributeError, TypeError):
            print("Screen change monitoring not available - using static detection")

    # -------------------------
    # Browser settings & injection
    # -------------------------
    def configure_browser_settings(self):
        try:
            if not self.profile:
                print("Warning: No profile available for configuration")
                return
            settings = self.profile.settings()
            if not settings:
                print("Warning: No settings available for configuration")
                return

            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

            try:
                settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
                settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.TouchIconsEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True)
            except AttributeError:
                pass
            try:
                settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
            except AttributeError:
                pass

            self.inject_screen_info_script()
            print("Browser settings configured for exam mode")
        except Exception as e:
            print(f"Warning: Could not configure some browser settings: {e}")

    def inject_screen_info_script(self):
        if not self.profile:
            return
        try:
            script_collection = self.profile.scripts()
            if not script_collection:
                print("Warning: No script collection available")
                return
            try:
                existing = []
            except AttributeError:
                existing = []
            for s in existing:
                script_collection.remove(s)

            screens = QGuiApplication.screens()
            js_screens = []
            for s in screens:
                geom = s.geometry()
                js_screens.append({
                    "width": geom.width(),
                    "height": geom.height(),
                    "left": geom.left(),
                    "top": geom.top(),
                    "name": s.name()
                })

            js_code = f"""
            (function() {{
                window.__qt_injected_screens = {js_screens};

                if (!navigator.getScreenDetails) {{
                    navigator.getScreenDetails = function() {{
                        const screens = window.__qt_injected_screens.map((screen, index) => ({{
                            availHeight: screen.height,
                            availLeft: screen.left,
                            availTop: screen.top,
                            availWidth: screen.width,
                            colorDepth: 24,
                            height: screen.height,
                            isExtended: index > 0,
                            isInternal: index === 0,
                            isPrimary: index === 0,
                            left: screen.left,
                            orientation: {{ angle: 0, type: 'landscape-primary' }},
                            pixelDepth: 24,
                            top: screen.top,
                            width: screen.width,
                            label: screen.name || `Screen ${{index + 1}}`,
                            devicePixelRatio: window.devicePixelRatio || 1
                        }})));

                        return Promise.resolve({{
                            screens: screens,
                            currentScreen: screens[0] || null
                        }});
                    }};
                }}

                if (window.screen) {{
                    Object.defineProperty(window.screen, 'isExtended', {{
                        value: window.__qt_injected_screens.length > 1,
                        writable: false,
                        enumerable: true
                    }});
                }}

                Object.defineProperty(navigator, 'qtScreenCount', {{
                    value: (window.__qt_injected_screens && window.__qt_injected_screens.length) || 0,
                    writable: false,
                    enumerable: true
                }});

                if (navigator.permissions && navigator.permissions.query) {{
                    const originalQuery = navigator.permissions.query;
                    navigator.permissions.query = function(descriptor) {{
                        if (descriptor && descriptor.name === 'window-management') {{
                            return Promise.resolve({{ state: 'granted' }});
                        }}
                        return originalQuery.call(this, descriptor);
                    }};
                }}

                console.log('Qt Screen Info Injected: ' + window.__qt_injected_screens.length + ' screens detected');
            }})();
            """

            script = QWebEngineScript()
            script.setName("qt_injected_screens")
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            script.setRunsOnSubFrames(True)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script.setSourceCode(js_code)
            try:
                script_collection.insert(script)
            except (AttributeError, TypeError) as e:
                print(f"Could not install script using insert method: {e}")

            print(f"Injected Qt screen info script (screens={len(js_screens)})")
        except Exception as e:
            print(f"Could not inject screen info script: {e}")

    def load_target_url(self):
        if self._target_url_loaded:
            return
        if not self.network_protection_ready:
            print("Skipping URL load until network protection is active")
            return
        print("All protections ready, loading exam URL...")
        self._target_url_loaded = True

        def on_load_finished(success):
            try:
                self.inject_monitoring_scripts(success)
            finally:
                try:
                    self.custom_page.loadFinished.disconnect(on_load_finished)
                except Exception:
                    pass

        self.custom_page.loadFinished.connect(on_load_finished)
        self.browser.setUrl(QUrl(self.target_url))

    def inject_monitoring_scripts(self, success: bool):
        if not success:
            print("Page failed to load")
            return
        print("Page loaded successfully, injecting monitoring scripts...")
        monitor_script = """
        (function() {
            console.log('Exam monitoring script loaded - Multi-monitor support enabled');

            if (window.screen) {
                const screenProps = {
                    availLeft: window.screen.availLeft || 0,
                    availTop: window.screen.availTop || 0,
                    left: window.screen.left || 0,
                    top: window.screen.top || 0,
                    isExtended: (window.__qt_injected_screens && window.__qt_injected_screens.length > 1) || false
                };
                Object.keys(screenProps).forEach(prop => {
                    if (!(prop in window.screen)) {
                        try {
                            Object.defineProperty(window.screen, prop, {
                                value: screenProps[prop],
                                writable: false,
                                enumerable: true
                            });
                        } catch (e) {}
                    }
                });
            }

            if (!window.screen.orientation) {
                try {
                    Object.defineProperty(window.screen, 'orientation', {
                        value: {
                            angle: 0,
                            type: 'landscape-primary',
                            addEventListener: function(){},
                            removeEventListener: function(){}
                        },
                        writable: false,
                        enumerable: true
                    });
                } catch (e) {}
            }

            if (!navigator.getScreenDetails) {
                navigator.getScreenDetails = function() {
                    console.log('getScreenDetails called - providing Qt screen data');
                    if (window.__qt_injected_screens && window.__qt_injected_screens.length > 0) {
                        const screens = window.__qt_injected_screens.map((screen, index) => ({
                            availHeight: screen.height,
                            availLeft: screen.left,
                            availTop: screen.top,
                            availWidth: screen.width,
                            colorDepth: 24,
                            height: screen.height,
                            isExtended: index > 0,
                            isInternal: index === 0,
                            isPrimary: index === 0,
                            left: screen.left,
                            orientation: { angle: 0, type: 'landscape-primary' },
                            pixelDepth: 24,
                            top: screen.top,
                            width: screen.width,
                            label: screen.name || `Display ${index + 1}`,
                            devicePixelRatio: window.devicePixelRatio || 1
                        }));

                        return Promise.resolve({
                            screens: screens,
                            currentScreen: screens[0] || null
                        });
                    } else {
                        const fallbackScreen = {
                            availHeight: window.screen.availHeight,
                            availLeft: window.screen.availLeft || 0,
                            availTop: window.screen.availTop || 0,
                            availWidth: window.screen.availWidth,
                            colorDepth: window.screen.colorDepth || 24,
                            height: window.screen.height,
                            isExtended: false,
                            isInternal: true,
                            isPrimary: true,
                            left: window.screen.left || 0,
                            orientation: window.screen.orientation || { angle: 0, type: 'landscape-primary' },
                            pixelDepth: window.screen.pixelDepth || 24,
                            top: window.screen.top || 0,
                            width: window.screen.width,
                            label: 'Primary Display',
                            devicePixelRatio: window.devicePixelRatio || 1
                        };
                        return Promise.resolve({
                            screens: [fallbackScreen],
                            currentScreen: fallbackScreen
                        });
                    }
                };
            }

            if (navigator.permissions && navigator.permissions.query) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = function(descriptor) {
                    if (descriptor && descriptor.name === 'window-management') {
                        console.log('Window management permission requested - granting');
                        return Promise.resolve({ state: 'granted' });
                    }
                    return originalQuery.call(this, descriptor);
                };
            }

            window.addEventListener('blur', function() {
                console.log('Window lost focus - exam security event');
            });
            window.addEventListener('focus', function() {
                console.log('Window gained focus - exam security event');
            });

            const screenCount = (window.__qt_injected_screens && window.__qt_injected_screens.length) || 1;
            console.log(`Screen detection ready: ${screenCount} screen(s) detected`);

        })();
        """
        self.custom_page.runJavaScript(monitor_script, lambda r: print("Monitoring scripts injected successfully"))

    # -------------------------
    # Permissions / fullscreen
    # -------------------------
    def handle_permission_request(self, origin, feature):
        feature_names = {
            QWebEnginePage.Feature.MediaAudioCapture: "Microphone",
            QWebEnginePage.Feature.MediaVideoCapture: "Camera",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "Camera and Microphone",
            QWebEnginePage.Feature.DesktopVideoCapture: "Screen Sharing",
            QWebEnginePage.Feature.DesktopAudioVideoCapture: "Screen and Audio Sharing",
            QWebEnginePage.Feature.Geolocation: "Location",
            QWebEnginePage.Feature.Notifications: "Notifications"
        }

        feature_name = feature_names.get(feature, f"Unknown Feature ({feature})")
        print(f"Permission requested: {feature_name} from {origin.toString()}")

        self.custom_page.setFeaturePermission(
            origin,
            feature,
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
        )
        print(f"{feature_name} permission granted automatically")

    def handle_fullscreen_request(self, request):
        print(f"Fullscreen request from: {request.origin().toString()}")
        request.accept()
        print("Fullscreen request granted")
        if not self.isFullScreen():
            self.showFullScreen()

    # -------------------------
    # Security / monitoring timers
    # -------------------------
    def setup_security_monitoring(self):
        self.fullscreen_timer = QTimer()
        self.fullscreen_timer.timeout.connect(self.check_fullscreen_mode)
        self.fullscreen_timer.start(2000)

        self.popup_cleanup_timer = QTimer()
        self.popup_cleanup_timer.timeout.connect(self.cleanup_blank_popups)
        self.popup_cleanup_timer.start(5000)

    def check_fullscreen_mode(self):
        if not self.isFullScreen():
            print("Restoring fullscreen mode for exam security")
            self.showFullScreen()

    def cleanup_blank_popups(self):
        if hasattr(self.custom_page, 'popup_windows'):
            popups_to_remove = []
            for popup in list(self.custom_page.popup_windows):
                try:
                    if popup and popup.url().toString() in ["", "about:blank"]:
                        print("Cleaning up blank popup window")
                        popup.close()
                        popups_to_remove.append(popup)
                except Exception:
                    popups_to_remove.append(popup)
            for popup in popups_to_remove:
                if popup in self.custom_page.popup_windows:
                    self.custom_page.popup_windows.remove(popup)

    # -------------------------
    # Monitor check
    # -------------------------
    def check_monitors(self):
        try:
            screens = QGuiApplication.screens()
            print(f"Detected {len(screens)} monitor(s)")
            if len(screens) > 1:
                QMessageBox.warning(
                    self,
                    "Multiple Monitors Detected",
                    f"Multiple monitors detected ({len(screens)} total)!\nFor exam security, please use only one monitor."
                )
                print(f"Multiple monitor check completed: {len(screens)} monitors found")
            else:
                print("Single monitor detected - exam security OK")
        except Exception as e:
            print(f"Error checking monitors: {e}")

    # -------------------------
    # Kiosk / network protection (async)
    # -------------------------
    def start_protections_parallel(self):
        self.start_kiosk_protection_async()
        self.start_network_protection_async()

    def start_kiosk_protection_async(self):
        if self.kiosk_active:
            return
        try:
            hwnd = int(self.winId())
            print(f"Window handle: {hwnd}")
            set_target_browser_window(hwnd)
            self.kiosk_worker = KioskWorker(
                hwnd, system_lockdown=self.system_lockdown
            )
            self.kiosk_worker.finished_success.connect(self._on_kiosk_started)
            self.kiosk_worker.finished_failure.connect(lambda err: print("Kiosk start failed:", err))
            self.kiosk_worker.start()
        except Exception as e:
            print("Error starting kiosk protection async:", e)

    def _on_kiosk_started(self):
        self.kiosk_active = True
        print("Kiosk protection active (keyboard + gesture blocking)")

    def start_network_protection_async(self):
        if self.network_worker:
            return
        try:
            print("Starting network protection (Native Firewall, background)...")
            self.network_worker = NetworkWorker(self.browser_exe_path)
            self.network_worker.finished_success.connect(self._on_network_ready)
            self.network_worker.finished_failure.connect(self._on_network_failed)
            self.network_worker.start()
        except Exception as e:
            print("Error starting network worker:", e)
            self._show_network_failure_dialog(str(e))

    def _on_network_ready(self):
        print("Network protection active (Native Firewall)")
        self.network_protection_ready = True
        self.load_target_url()

    def _on_network_failed(self, reason: str):
        print("Failed to activate network protection:", reason)
        self._show_network_failure_dialog(reason)

    def _show_network_failure_dialog(self, reason: str):
        if self._shutdown_started:
            return
        try:
            from log_setup import get_log_path
            _log_hint = f"\n\nFull log: {get_log_path()}"
        except Exception:
            _log_hint = ""
        QMessageBox.critical(
            self,
            "Network Protection Failed",
            "Secure traffic blocking could not be activated.\n\n"
            "The exam session cannot continue without network protection.\n\n"
            f"Details: {reason}{_log_hint}",
        )
        self.safe_exit()

    # -------------------------
    # Teardown / exit
    # -------------------------
    def confirm_exit(self):
        reply = QMessageBox.question(
            self,
            'Exit Secure Session',
            'Are you sure you want to quit the secure exam session?\n\nThis will end your current session and may affect your exam progress.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.safe_exit()

    def safe_exit(self):
        """Single source of truth for all cleanup.
        Called by confirm_exit, atexit handler, and closeEvent.
        """
        if self._shutdown_started:
            return
        self._shutdown_started = True
        print("Exiting secure browser – restoring system state...")

        # Stop timers
        try:
            if hasattr(self, 'fullscreen_timer') and self.fullscreen_timer:
                self.fullscreen_timer.stop()
            if hasattr(self, 'popup_cleanup_timer') and self.popup_cleanup_timer:
                self.popup_cleanup_timer.stop()
        except Exception:
            pass

        # Close popups
        if hasattr(self, 'custom_page') and hasattr(self.custom_page, 'popup_windows'):
            for popup in list(self.custom_page.popup_windows):
                try:
                    if popup:
                        popup.close()
                except Exception:
                    pass

        # Stop kiosk protection (keyboard hooks + gestures + task manager)
        if self.kiosk_active:
            try:
                stop_exam_kiosk_mode()
            except Exception as e:
                print("Error stopping kiosk mode:", e)
            self.kiosk_active = False
            print("Kiosk protection deactivated")

        # Restore firewall
        if self.network_worker:
            try:
                self.network_worker.cleanup()
                self.network_worker.quit()
                self.network_worker.wait(2000)
            except Exception as e:
                print("Error cleaning up network worker:", e)
            self.network_worker = None

        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(100, app.quit)
        else:
            os._exit(0)

    def closeEvent(self, event):
        """Intercept window close to guarantee cleanup."""
        self.safe_exit()
        event.accept()

    def setWindowFullScreen(self):
        self.showFullScreen()


# -------------------------
# Module-level atexit cleanup
# -------------------------
_active_browser_instance: SecureBrowser | None = None


def _atexit_cleanup():
    """Last-resort cleanup so the user's internet and gestures are restored
    even if the app crashes or is killed."""
    try:
        if _active_browser_instance and _active_browser_instance.network_worker:
            _active_browser_instance.network_worker.cleanup()
    except Exception:
        pass
    try:
        stop_exam_kiosk_mode()
    except Exception:
        pass
    try:
        emergency_firewall_cleanup()
    except Exception:
        pass


atexit.register(_atexit_cleanup)


# -------------------------
# Admin utils and main
# -------------------------
def check_admin_and_show_warning():
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False
    return is_admin


def ensure_run_as_admin():
    is_admin = check_admin_and_show_warning()
    if is_admin:
        return True

    script = os.path.abspath(__file__)
    args = [script] + sys.argv[1:]
    params = " ".join('"%s"' % a for a in args)
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        if int(ret) > 32:
            print("Elevation requested - relaunching as administrator")
            os._exit(0)
        else:
            print(f"Elevation request failed (ShellExecute returned {ret})")
            return False
    except Exception as e:
        print(f"Could not request elevation: {e}")
        return False


def resolve_target_url(argv):
    url_args = [arg for arg in argv[1:] if not arg.startswith('--')]
    if not url_args:
        print("No launch URL provided.")
        return None

    raw_target = url_args[0]
    parsed = urlparse(raw_target)
    if parsed.scheme == 'omniproctor-browser' and parsed.netloc == 'open':
        query = parse_qs(parsed.query)
        encoded_target = query.get('url', [''])[0]
        if encoded_target:
            decoded_target = unquote(encoded_target).strip()
            if decoded_target:
                decoded_parsed = urlparse(decoded_target)
                if decoded_parsed.scheme in {"http", "https"}:
                    print(f"Using protocol launch URL: {decoded_target}")
                    return decoded_target
        print("Protocol launch URI missing a valid http/https url parameter.")
        return None

    if parsed.scheme in {"http", "https"}:
        print(f"Using provided URL: {raw_target}")
        return raw_target

    print("Provided launch URL is not http/https.")
    return None


if __name__ == "__main__":
    # Configure logging before anything else so stdout-less launches
    # (pythonw.exe / protocol handler / frozen exe) still produce a
    # diagnosable log file on disk.
    try:
        _log_path = configure_file_logging()
        print(f"[omniproctor] Log file: {_log_path}")
    except Exception as _exc:
        print(f"[omniproctor] WARNING: file logging setup failed: {_exc}", file=sys.stderr)

    if "--register-protocol" in sys.argv:
        sys.exit(0 if register() else 1)
    if "--unregister-protocol" in sys.argv:
        sys.exit(0 if unregister() else 1)

    if "--firewall-recover" in sys.argv:
        # Admin-only: wipe any orphaned WFP filters/sublayer/provider that a
        # crashed previous run may have left behind. Useful when the network
        # is locked down because exit_exam_mode never ran.
        if not ensure_run_as_admin():
            sys.exit(1)
        try:
            emergency_firewall_cleanup()
            print("Firewall recovery completed.")
            sys.exit(0)
        except Exception as exc:
            print(f"Firewall recovery failed: {exc}")
            sys.exit(1)

    no_system_lockdown = NO_SYSTEM_LOCKDOWN_FLAG in sys.argv

    if not ensure_run_as_admin():
        sys.exit(1)

    try:
        ensure_registered()
    except Exception as exc:
        print(f"Protocol self-registration skipped: {exc}")

    # Install emergency cleanup early (must run on the main thread) so
    # SIGINT / SIGTERM / SIGBREAK and atexit reliably restore Task Manager
    # and gestures even on hard exits.
    try:
        install_keyblock_emergency_handlers()
    except Exception as exc:
        print(f"Could not install keyblock emergency handlers: {exc}")

    enhanced_args = sys.argv + [
        '--enable-features=WindowManagement,WebRTC-Hardware-H264-Encoding,WebRTC-Hardware-H264-Decoding',
        '--enable-experimental-web-platform-features',
        '--enable-blink-features=WindowManagement,GetDisplayMedia,ScreenWakeLock',
        '--disable-web-security',
        '--allow-running-insecure-content',
        '--disable-features=VizDisplayCompositor',
        '--ignore-certificate-errors',
        '--disable-gpu-sandbox',
        '--allow-file-access-from-files',
        '--enable-media-stream',
        '--use-fake-ui-for-media-stream',
        '--auto-accept-camera-and-microphone-capture',
        '--permissions-policy=window-management=*,screen-wake-lock=*,display-capture=*'
    ]

    app = QApplication(enhanced_args)
    app.setQuitOnLastWindowClosed(True)

    target_url = resolve_target_url(sys.argv)
    if not target_url:
        QMessageBox.critical(
            None,
            "Launch Failed",
            "No valid launch URL was provided.\n\n"
            "Open the secure browser from WebClient using the kiosk launch link.",
        )
        sys.exit(1)

    # Dynamic: the exe path for the firewall allow-rule.
    # When bundled as a .exe via PyInstaller, sys.executable IS the .exe.
    browser_exe_path = sys.executable

    window = SecureBrowser(
        target_url,
        browser_exe_path=browser_exe_path,
        system_lockdown=not no_system_lockdown,
    )
    if no_system_lockdown:
        print(
            "Dev mode: --no-system-lockdown set. Task Manager and gesture "
            "policies will NOT be touched on this run."
        )
    _active_browser_instance = window
    window.show()

    exit_code = app.exec()
    sys.exit(exit_code)
