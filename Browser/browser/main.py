import sys
import os
import atexit
import ctypes
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QVBoxLayout, QWidget,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineScript
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

from web_profile import build_kiosk_profile
from win11_compat import harden_kiosk_window, remove_capture_protection
from ui import KioskSplash, KioskTopBar, OmniProctorMessageBox, apply_theme

NO_SYSTEM_LOCKDOWN_FLAG = "--no-system-lockdown"


def _is_dev_mode() -> bool:
    return os.getenv("OMNIPROCTOR_DEV", "").strip() in {"1", "true", "True"}


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
                backend = getattr(self.controller, "_backend", None)
                detail = getattr(backend, "last_error", None) or "enter_exam_mode returned False"
                self.last_failure = detail
                self.finished_failure.emit(self.last_failure)
        except Exception as e:
            self.last_failure = f"{type(e).__name__}: {e}"
            self.finished_failure.emit(self.last_failure)

    def cleanup(self):
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

    def javaScriptConsoleMessage(self, level, message, line, source_id):
        """Forward page console logs into our Python log so we can see them
        without devtools (kiosk has devtools disabled)."""
        try:
            level_name = {0: "INFO", 1: "WARN", 2: "ERROR"}.get(int(level), "LOG")
            print(f"[page-console:{level_name}] {message} ({source_id}:{line})")
        except Exception:
            pass

    def createWindow(self, type):
        """Open child popups (e.g. Google OAuth, payment frames) inside the
        kiosk in a controlled, hardened window.

        Critical for Google / Microsoft / Auth0 sign-in: the page calls
        ``window.open('https://accounts.google.com/...', '_blank')`` and
        then communicates with the popup via ``window.opener``. The
        popup must:

        * Open with the SAME ``QWebEngineProfile`` so cookies and the
          shared session are visible.
        * Not be closed prematurely while the user is typing credentials.
          We previously auto-closed any popup whose URL stayed at
          ``about:blank`` for >300 ms, which is enough to nuke a slow
          OAuth window before it even navigates.
        * Honour ``window.close()`` from the OAuth page so it disappears
          after sign-in (handled via ``windowCloseRequested``).
        * Be excluded from screen capture, just like the main window.
        """
        try:
            owner = self.parent_browser
            owner_window = owner.window() if owner else None

            popup_view = QWebEngineView(owner_window)
            popup_view.setWindowFlag(Qt.WindowType.Window, True)
            try:
                popup_view.setWindowModality(Qt.WindowModality.NonModal)
            except Exception:
                pass

            popup_page = CustomWebEnginePage(self.profile(), popup_view)
            popup_view.setPage(popup_page)
            popup_view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            popup_view.resize(900, 680)
            popup_view.setWindowTitle("OmniProctor - Sign in")

            try:
                popup_view.setWindowIcon(KioskTopBar.make_window_icon())
            except Exception:
                pass

            self.popup_windows.append(popup_view)
            popup_page.featurePermissionRequested.connect(
                lambda origin, feature, page=popup_page: self._popup_grant_legacy(page, origin, feature)
            )
            try:
                popup_page.permissionRequested.connect(self._popup_grant_modern)
            except (AttributeError, TypeError):
                pass

            popup_page.windowCloseRequested.connect(lambda pv=popup_view: self._close_popup(pv))

            popup_state = {
                "ever_navigated": False,
                "popup_view": popup_view,
            }

            def on_url_changed(url):
                url_str = url.toString()
                print("Popup urlChanged:", url_str)
                if url_str and not (
                    url_str.startswith("about:blank")
                    or url_str.startswith("data:,")
                    or url_str.startswith("data:text/html,")
                    or url_str.startswith("data:text/html;charset=utf-8,")
                ):
                    popup_state["ever_navigated"] = True

            popup_page.urlChanged.connect(on_url_changed)

            def on_load_finished(ok):
                # Only treat the popup as stillborn if it has never left
                # about:blank AFTER a real load attempt completed. OAuth
                # popups frequently hold at about:blank for a beat before
                # the JS opener does ``popup.location = '...'``.
                if not ok and not popup_state["ever_navigated"]:
                    QTimer.singleShot(500, lambda pv=popup_view: self._close_popup_if_blank(pv))

            popup_page.loadFinished.connect(on_load_finished)

            popup_view.show()
            popup_view.raise_()
            popup_view.activateWindow()

            # Apply screen-capture protection + DWM hardening once the
            # native HWND exists. Some OAuth pages wait for window focus
            # before redirecting, so this also helps focus latency.
            def _harden_popup():
                try:
                    hwnd = int(popup_view.winId())
                    if hwnd:
                        harden_kiosk_window(hwnd)
                except Exception as exc:
                    print(f"WARN: popup harden failed: {exc}")

            QTimer.singleShot(150, _harden_popup)

            # Long stale-popup safety net: if after 30 s the popup still
            # has not navigated anywhere real, assume it's a leak and
            # close it. 30 s is generous enough for the slowest OAuth
            # provider on a flaky link, but short enough that a
            # silently-broken popup doesn't sit around forever.
            def _timeout_check(pv=popup_view):
                try:
                    if popup_state["ever_navigated"]:
                        return
                    if pv in self.popup_windows:
                        print("Auto-closing popup that never navigated within 30 s")
                        self._close_popup(pv)
                except Exception as exc:
                    print(f"Error in popup timeout check: {exc}")

            QTimer.singleShot(30000, _timeout_check)

            return popup_page
        except Exception as e:
            print("Error creating popup window:", e)
            return super().createWindow(type)

    def _popup_grant_legacy(self, page, origin, feature):
        """Auto-grant legacy-API permissions on a popup page (camera/mic
        rarely needed there, but generic for completeness)."""
        try:
            page.setFeaturePermission(
                origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
            )
            print(f"Popup permission granted: feature={int(feature)} origin={origin.toString()}")
        except Exception as exc:
            print(f"WARN: popup setFeaturePermission failed: {exc}")

    def _popup_grant_modern(self, permission):
        """Auto-grant new-API permissions on a popup page."""
        try:
            permission.grant()
            try:
                ptype_name = getattr(permission.permissionType(), "name", "?")
            except Exception:
                ptype_name = "?"
            print(f"Popup modern permission granted: {ptype_name}")
        except Exception as exc:
            print(f"WARN: popup permission.grant failed: {exc}")

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
        splash: Optional[KioskSplash] = None,
    ):
        super().__init__()
        self.setWindowTitle("OmniProctor Secure Kiosk")
        self.setWindowIcon(KioskTopBar.make_window_icon())

        self.kiosk_active = False
        self.network_worker: NetworkWorker | None = None
        self.kiosk_worker: KioskWorker | None = None
        self.browser_exe_path = browser_exe_path or sys.executable
        self.target_url = url
        self.network_protection_ready = False
        self._target_url_loaded = False
        self._shutdown_started = False
        self.system_lockdown = system_lockdown
        self._splash = splash
        self._granted_permission_origins = set()

        # ---- UI setup -----------------------------------------------------
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top_bar = KioskTopBar(
            test_title="OmniProctor Secure Session",
            assignee=os.environ.get("USERNAME", "Candidate"),
            parent=main_widget,
        )
        self.top_bar.exit_requested.connect(self.confirm_exit)

        # ---- Persistent Web Engine profile (perf-profile) -----------------
        self.profile = build_kiosk_profile(parent=self)

        # ---- Browser view --------------------------------------------------
        self.browser = QWebEngineView()
        self.custom_page = CustomWebEnginePage(self.profile, self.browser)
        self.custom_page.featurePermissionRequested.connect(self.handle_permission_request)
        self.custom_page.fullScreenRequested.connect(self.handle_fullscreen_request)
        try:
            self.custom_page.renderProcessTerminated.connect(self._on_render_process_terminated)
        except Exception as exc:
            print(f"WARN: could not bind renderProcessTerminated: {exc}")

        # Qt 6.8+ exposes the new QWebEnginePermission API via the
        # ``permissionRequested`` signal. The ONLY place modern permission
        # types (Window Management, Clipboard Read/Write, Local Fonts, …)
        # are surfaced - the legacy ``featurePermissionRequested`` signal
        # does not include them. The signal lives on QWebEnginePage in
        # PyQt6 6.8+ (and on QWebEngineProfile in some builds), so try
        # both to maximise compatibility.
        bound_modern = False
        for owner_name, owner in (("page", self.custom_page), ("profile", self.profile)):
            try:
                owner.permissionRequested.connect(self.handle_modern_permission_request)
                print(f"Modern permissionRequested signal bound on {owner_name}")
                bound_modern = True
            except (AttributeError, TypeError):
                pass
        if not bound_modern:
            print("INFO: modern permissionRequested signal not available on this Qt build")

        self.browser.setPage(self.custom_page)
        self.browser.setUrl(QUrl("about:blank"))

        # Inject screen-info script via this profile's script collection.
        self.inject_screen_info_script()

        layout.addWidget(self.top_bar)
        layout.addWidget(self.browser)

        self.setWindowFullScreen()

        QTimer.singleShot(0, self.start_protections_parallel)

        # Strict single-monitor enforcement (monitor-enforce)
        QTimer.singleShot(300, self.enforce_single_monitor)
        self._monitor_poll = QTimer(self)
        self._monitor_poll.setInterval(5000)
        self._monitor_poll.timeout.connect(self.enforce_single_monitor)
        self._monitor_poll.start()

        self.setup_security_monitoring()

        try:
            app = QGuiApplication.instance()
            if app:
                if hasattr(app, 'screenAdded'):
                    getattr(app, 'screenAdded').connect(lambda _s: self.enforce_single_monitor())
                if hasattr(app, 'screenRemoved'):
                    getattr(app, 'screenRemoved').connect(lambda _s: self.enforce_single_monitor())
                print("Screen change monitoring enabled")
        except (AttributeError, TypeError):
            print("Screen change monitoring not available - using static detection")

    # -------------------------
    # Screen-info JS injection
    # -------------------------
    def inject_screen_info_script(self):
        if not self.profile:
            return
        try:
            script_collection = self.profile.scripts()
            if not script_collection:
                print("Warning: No script collection available")
                return

            # Remove any previous version of our injected script.
            try:
                existing = list(script_collection.find("qt_injected_screens"))
            except (AttributeError, TypeError):
                existing = []
            for s in existing:
                try:
                    script_collection.remove(s)
                except Exception:
                    pass

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

                function __qt_buildScreenDetailsResult() {{
                    const screens = window.__qt_injected_screens.map((screen, index) => ({{
                        availHeight: screen.height,
                        availLeft: screen.left,
                        availTop: screen.top,
                        availWidth: screen.width,
                        colorDepth: 24,
                        height: screen.height,
                        isExtended: false,
                        isInternal: index === 0,
                        isPrimary: index === 0,
                        left: screen.left,
                        orientation: {{ angle: 0, type: 'landscape-primary' }},
                        pixelDepth: 24,
                        top: screen.top,
                        width: screen.width,
                        label: screen.name || `Screen ${{index + 1}}`,
                        devicePixelRatio: window.devicePixelRatio || 1
                    }}));
                    const evtTarget = {{
                        addEventListener: function() {{}},
                        removeEventListener: function() {{}},
                        dispatchEvent: function() {{ return true; }}
                    }};
                    return Object.assign({{}}, evtTarget, {{
                        screens: screens,
                        currentScreen: screens[0] || null,
                        oncurrentscreenchange: null,
                        onscreenschange: null
                    }});
                }}

                // The Window Management API spec puts getScreenDetails on
                // Window, NOT on Navigator. Many sites call it as
                // ``window.getScreenDetails()`` or just ``getScreenDetails()``.
                // We previously only patched ``navigator.getScreenDetails``,
                // which is a non-standard alias — so HackerRank never saw
                // our shim and went down the rejected-permission path.
                function __qt_screenDetailsShim() {{
                    console.log('[OmniProctor] getScreenDetails() called -> serving '
                        + window.__qt_injected_screens.length + ' screen(s) from Qt');
                    return Promise.resolve(__qt_buildScreenDetailsResult());
                }}

                try {{ window.getScreenDetails = __qt_screenDetailsShim; }} catch (e) {{}}
                try {{ navigator.getScreenDetails = __qt_screenDetailsShim; }} catch (e) {{}}
                if (window.Window && window.Window.prototype) {{
                    try {{
                        Object.defineProperty(window.Window.prototype, 'getScreenDetails', {{
                            value: __qt_screenDetailsShim,
                            writable: true,
                            configurable: true
                        }});
                    }} catch (e) {{}}
                }}

                if (window.screen) {{
                    // Always report isExtended=false: even if multiple
                    // monitors are physically attached, the kiosk's strict
                    // single-monitor enforcement will tear down the session,
                    // so for the page's pre-flight we can safely tell it
                    // there is one screen.
                    try {{
                        Object.defineProperty(window.screen, 'isExtended', {{
                            value: false,
                            configurable: true,
                            enumerable: true
                        }});
                    }} catch (e) {{}}
                }}

                Object.defineProperty(navigator, 'qtScreenCount', {{
                    value: (window.__qt_injected_screens && window.__qt_injected_screens.length) || 0,
                    writable: false,
                    enumerable: true
                }});

                if (navigator.permissions && navigator.permissions.query) {{
                    const FORCE_GRANTED = new Set([
                        'window-management',
                        'window-placement',  // legacy alias used by older sites
                        'camera',
                        'microphone',
                        'clipboard-read',
                        'clipboard-write',
                        'notifications',
                        'fullscreen',
                        'display-capture',
                        'screen-wake-lock'
                    ]);
                    function __qt_makeStatus(name) {{
                        return {{
                            state: 'granted',
                            status: 'granted',
                            name: name,
                            onchange: null,
                            addEventListener: function() {{}},
                            removeEventListener: function() {{}},
                            dispatchEvent: function() {{ return true; }}
                        }};
                    }}
                    const originalQuery = navigator.permissions.query.bind(navigator.permissions);
                    function __qt_permissionsQuery(descriptor) {{
                        if (descriptor && FORCE_GRANTED.has(descriptor.name)) {{
                            console.log('[OmniProctor] permissions.query(' + descriptor.name + ') -> granted (shim)');
                            return Promise.resolve(__qt_makeStatus(descriptor.name));
                        }}
                        return originalQuery(descriptor);
                    }}
                    // Patch both the instance and (defensively) the prototype
                    // so callers that grab Permissions.prototype.query still
                    // hit our shim.
                    try {{ navigator.permissions.query = __qt_permissionsQuery; }} catch (e) {{}}
                    try {{
                        if (window.Permissions && window.Permissions.prototype) {{
                            Object.defineProperty(window.Permissions.prototype, 'query', {{
                                value: __qt_permissionsQuery,
                                writable: true,
                                configurable: true
                            }});
                        }}
                    }} catch (e) {{}}
                }}

                window.__qt_kiosk_shim_loaded = true;
                console.log('[OmniProctor] kiosk shim loaded; screens=' + window.__qt_injected_screens.length
                    + ', getScreenDetails=' + typeof window.getScreenDetails
                    + ', perms.query.patched=' + (navigator.permissions && navigator.permissions.query.toString().includes('FORCE_GRANTED')));
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

    # -------------------------
    # Page-load lifecycle
    # -------------------------
    def load_target_url(self):
        if self._target_url_loaded:
            return
        if not self.network_protection_ready:
            print("Skipping URL load until network protection is active")
            return
        print("All protections ready, loading exam URL...")
        self._target_url_loaded = True

        if self._splash:
            try:
                self._splash.close()
            except Exception:
                pass
            self._splash = None

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
                        return Promise.resolve({ screens: screens, currentScreen: screens[0] || null });
                    }
                    return Promise.resolve({ screens: [], currentScreen: null });
                };
            }

            if (navigator.permissions && navigator.permissions.query) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = function(descriptor) {
                    if (descriptor && descriptor.name === 'window-management') {
                        return Promise.resolve({ state: 'granted' });
                    }
                    return originalQuery.call(this, descriptor);
                };
            }
        })();
        """
        self.custom_page.runJavaScript(monitor_script, lambda r: print("Monitoring scripts injected successfully"))

    # -------------------------
    # Permissions / fullscreen
    # -------------------------
    def _on_render_process_terminated(self, status, exit_code):
        """Survive a renderer/GPU crash without taking the kiosk down.

        The most common trigger is a media-stack fault when the camera or
        microphone first initialises. We log it, surface it on the top bar,
        and try to reload the page so the candidate can keep going.
        """
        try:
            print(f"WARN: render process terminated (status={status}, exit_code={exit_code})")
        except Exception:
            pass
        try:
            self.top_bar.set_camera_status("warn", "Renderer recovered")
        except Exception:
            pass
        try:
            QTimer.singleShot(750, lambda: self.browser.reload())
        except Exception:
            pass

    def handle_modern_permission_request(self, permission):
        """Auto-grant modern QWebEnginePermission requests (Qt 6.8+).

        This is what HackerRank's "Window Access permission" prompt and
        similar new W3C permissions (Clipboard, Local Fonts, etc.) flow
        through. The legacy ``featurePermissionRequested`` slot does not
        receive these.
        """
        try:
            try:
                origin_str = permission.origin().toString()
            except Exception:
                origin_str = "<unknown origin>"
            try:
                ptype = permission.permissionType()
                ptype_name = getattr(ptype, "name", str(ptype))
            except Exception:
                ptype_name = "<unknown type>"
            print(f"Modern permission requested: {ptype_name} from {origin_str}")
            try:
                permission.grant()
                print(f"  -> granted ({ptype_name})")
            except Exception as exc:
                print(f"  -> grant() failed for {ptype_name}: {exc}")

            try:
                # Surface camera grants on the top bar even when they come in
                # via the new API instead of the legacy signal.
                from PyQt6.QtWebEngineCore import QWebEnginePermission as _QP
                pt = _QP.PermissionType
                if ptype in (
                    getattr(pt, "MediaVideoCapture", None),
                    getattr(pt, "MediaAudioVideoCapture", None),
                ):
                    self.top_bar.set_camera_status("ok", "Camera ON")
                elif ptype == getattr(pt, "MediaAudioCapture", None):
                    self.top_bar.set_camera_status("ok", "Microphone ON")
            except Exception:
                pass
        except Exception as exc:
            print(f"WARN: handle_modern_permission_request failed: {exc}")

    def handle_permission_request(self, origin, feature):
        # Wrap the entire grant path in try/except: any uncaught exception
        # raised on a Qt slot leaves Qt's C++ stack in an indeterminate state
        # and can hard-crash the kiosk (taking the firewall + kiosk-mode
        # registry state down with it because atexit handlers never run).
        feature_names = {
            QWebEnginePage.Feature.MediaAudioCapture: "Microphone",
            QWebEnginePage.Feature.MediaVideoCapture: "Camera",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "Camera and Microphone",
            QWebEnginePage.Feature.DesktopVideoCapture: "Screen Sharing",
            QWebEnginePage.Feature.DesktopAudioVideoCapture: "Screen and Audio Sharing",
            QWebEnginePage.Feature.Geolocation: "Location",
            QWebEnginePage.Feature.Notifications: "Notifications",
        }
        feature_name = feature_names.get(feature, f"Unknown Feature ({feature})")
        origin_str = ""
        try:
            origin_str = origin.toString()
        except Exception:
            origin_str = "<unknown origin>"
        print(f"Permission requested: {feature_name} from {origin_str}")

        try:
            self.custom_page.setFeaturePermission(
                origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
            )
            self._granted_permission_origins.add((origin_str, int(feature)))
            print(f"{feature_name} permission granted automatically")
        except Exception as exc:
            print(f"WARN: setFeaturePermission failed for {feature_name}: {exc}")

        try:
            if feature in (
                QWebEnginePage.Feature.MediaVideoCapture,
                QWebEnginePage.Feature.MediaAudioVideoCapture,
            ):
                self.top_bar.set_camera_status("ok", "Camera ON")
            elif feature == QWebEnginePage.Feature.MediaAudioCapture:
                self.top_bar.set_camera_status("ok", "Microphone ON")
        except Exception as exc:
            print(f"WARN: top bar camera status update failed: {exc}")

    def handle_fullscreen_request(self, request):
        print(f"Fullscreen request from: {request.origin().toString()}")
        request.accept()
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
    # Strict single-monitor enforcement
    # -------------------------
    def enforce_single_monitor(self):
        if self._shutdown_started:
            return
        try:
            screens = QGuiApplication.screens()
        except Exception as exc:
            print(f"Error reading screen list: {exc}")
            return
        count = len(screens)
        self.top_bar.set_monitor_status(count)
        if count <= 1:
            return

        # If we've already warned once, just keep counting and wait for the
        # grace period to expire.
        if not getattr(self, "_monitor_grace_running", False):
            self._monitor_grace_running = True
            print(f"Multiple monitors detected ({count}) - showing blocking modal")
            QTimer.singleShot(0, lambda: self._show_monitor_violation_dialog(count))
            QTimer.singleShot(10_000, self._monitor_grace_expired)

    def _show_monitor_violation_dialog(self, count: int):
        try:
            OmniProctorMessageBox.critical(
                self,
                "External Display Detected",
                (
                    f"{count} displays are connected to this device.\n\n"
                    "Disconnect all external monitors within 10 seconds or the "
                    "secure session will be terminated."
                ),
            )
        except Exception as exc:
            print(f"Could not show monitor violation dialog: {exc}")

    def _monitor_grace_expired(self):
        if self._shutdown_started:
            return
        screens = QGuiApplication.screens()
        if len(screens) <= 1:
            print("External display(s) disconnected within grace period - continuing session")
            self._monitor_grace_running = False
            return
        print("Grace period expired with multiple monitors still connected - terminating session")
        self.safe_exit()

    # -------------------------
    # Kiosk / network protection (async)
    # -------------------------
    def start_protections_parallel(self):
        if self._splash:
            self._splash.set_status("Activating kiosk hooks…")
        self.start_kiosk_protection_async()
        if self._splash:
            self._splash.set_status("Enabling secure network filter…")
        self.start_network_protection_async()

    def start_kiosk_protection_async(self):
        if self.kiosk_active:
            return
        try:
            hwnd = int(self.winId())
            print(f"Window handle: {hwnd}")
            set_target_browser_window(hwnd)
            harden_kiosk_window(hwnd)  # WDA_EXCLUDEFROMCAPTURE + DWM hardening
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
        self.top_bar.set_network_status(True, "Network OK")
        self.top_bar.set_firewall_status(True, "Firewall ON")
        if self._splash:
            self._splash.set_status("Loading exam…")
        self.load_target_url()

    def _on_network_failed(self, reason: str):
        print("Failed to activate network protection:", reason)
        self.top_bar.set_network_status(False, "Network blocked")
        self.top_bar.set_firewall_status(False, "Firewall failed")
        self._show_network_failure_dialog(reason)

    def _show_network_failure_dialog(self, reason: str):
        if self._shutdown_started:
            return
        try:
            from log_setup import get_log_path
            _log_hint = f"\n\nFull log: {get_log_path()}"
        except Exception:
            _log_hint = ""
        OmniProctorMessageBox.critical(
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
        reply = OmniProctorMessageBox.question(
            self,
            "Exit Secure Session",
            "Are you sure you want to quit the secure exam session?\n\n"
            "This will end your current session and may affect your exam progress.",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            default_button=QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.safe_exit()

    def safe_exit(self):
        if self._shutdown_started:
            return
        self._shutdown_started = True
        print("Exiting secure browser – restoring system state...")

        try:
            if hasattr(self, 'fullscreen_timer') and self.fullscreen_timer:
                self.fullscreen_timer.stop()
            if hasattr(self, 'popup_cleanup_timer') and self.popup_cleanup_timer:
                self.popup_cleanup_timer.stop()
            if hasattr(self, '_monitor_poll') and self._monitor_poll:
                self._monitor_poll.stop()
        except Exception:
            pass

        if hasattr(self, 'custom_page') and hasattr(self.custom_page, 'popup_windows'):
            for popup in list(self.custom_page.popup_windows):
                try:
                    if popup:
                        popup.close()
                except Exception:
                    pass

        try:
            remove_capture_protection(int(self.winId()))
        except Exception:
            pass

        if self.kiosk_active:
            try:
                stop_exam_kiosk_mode()
            except Exception as e:
                print("Error stopping kiosk mode:", e)
            self.kiosk_active = False
            print("Kiosk protection deactivated")

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


def _emergency_excepthook(exc_type, exc_value, exc_tb):
    """Catch unhandled exceptions, run cleanup, then re-raise.

    Without this, an uncaught exception on a Qt slot can leave the WFP
    filters and Task Manager registry policy in their locked-down state.
    """
    try:
        import traceback
        sys.stderr.write("=== UNHANDLED KIOSK EXCEPTION ===\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
    except Exception:
        pass
    try:
        _atexit_cleanup()
    except Exception:
        pass
    # Defer to the previous hook so the process still exits non-zero.
    try:
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    except Exception:
        pass


sys.excepthook = _emergency_excepthook


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


def _build_chromium_flags() -> list[str]:
    """Curated Chromium flag set for fast, secure media-capable kiosk."""
    flags = [
        '--enable-features=WindowManagement,WebRTC-Hardware-H264-Encoding,WebRTC-Hardware-H264-Decoding,CanvasOopRasterization,UseSkiaRenderer',
        '--enable-experimental-web-platform-features',
        '--enable-blink-features=WindowManagement,GetDisplayMedia,ScreenWakeLock',
        # Performance --------------------------------------------------------
        '--enable-gpu-rasterization',
        '--enable-zero-copy',
        '--num-raster-threads=4',
        '--enable-accelerated-2d-canvas',
        # Media auto-grant (we also auto-accept in Python). Note: dropped
        # --use-fake-ui-for-media-stream so the real device picker logic runs.
        '--auto-accept-camera-and-microphone-capture',
        '--enable-media-stream',
        # Misc ---------------------------------------------------------------
        '--allow-file-access-from-files',
        '--disable-gpu-sandbox',
        '--permissions-policy=window-management=*,screen-wake-lock=*,display-capture=*',
    ]
    if _is_dev_mode():
        # Dev-only relaxations
        flags.extend([
            '--disable-web-security',
            '--ignore-certificate-errors',
            '--allow-running-insecure-content',
        ])
    return flags


def _apply_hidpi_policy():
    """Keep fractional scaling sharp on Win11 instead of forcing 2x rounding."""
    try:
        from PyQt6.QtGui import QGuiApplication as _QGuiApp
        _QGuiApp.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except (AttributeError, TypeError) as exc:
        print(f"HiDPI policy not applied: {exc}")
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    except (AttributeError, TypeError):
        pass
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except (AttributeError, TypeError):
        pass


if __name__ == "__main__":
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

    try:
        install_keyblock_emergency_handlers()
    except Exception as exc:
        print(f"Could not install keyblock emergency handlers: {exc}")

    # HiDPI must be set before QApplication is constructed.
    _apply_hidpi_policy()

    enhanced_args = sys.argv + _build_chromium_flags()
    app = QApplication(enhanced_args)
    app.setQuitOnLastWindowClosed(True)
    app.setApplicationName("OmniProctor Kiosk")
    app.setOrganizationName("OmniProctor")
    app.setWindowIcon(KioskTopBar.make_window_icon())
    apply_theme(app)

    # Splash while WFP and kiosk hooks come up.
    splash: Optional[KioskSplash] = None
    try:
        splash = KioskSplash()
        splash.set_status("Starting OmniProctor secure browser…")
        splash.show()
        app.processEvents()
    except Exception as exc:
        print(f"Splash unavailable: {exc}")
        splash = None

    target_url = resolve_target_url(sys.argv)
    if not target_url:
        if splash:
            splash.close()
        OmniProctorMessageBox.critical(
            None,
            "Launch Failed",
            "No valid launch URL was provided.\n\n"
            "Open the secure browser from WebClient using the kiosk launch link.",
        )
        sys.exit(1)

    browser_exe_path = sys.executable

    window = SecureBrowser(
        target_url,
        browser_exe_path=browser_exe_path,
        system_lockdown=not no_system_lockdown,
        splash=splash,
    )
    if no_system_lockdown:
        print(
            "Dev mode: --no-system-lockdown set. Task Manager and gesture "
            "policies will NOT be touched on this run."
        )
    _active_browser_instance = window
    window.show()
    if splash:
        try:
            splash.finish(window)
        except Exception:
            pass

    exit_code = app.exec()
    sys.exit(exit_code)
