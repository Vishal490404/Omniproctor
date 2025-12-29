import sys
import os
import ctypes
from typing import List

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

from keyblocks import start_exam_kiosk_mode, stop_exam_kiosk_mode, set_target_browser_window
from network.simplewall_controller import SimpleWallController

# Constants for display affinity (unused but kept for completeness)
WDA_EXCLUDEFROMCAPTURE = 0x00000011
WDA_NONE = 0x00000000


# -------------------------
# Background Workers
# -------------------------
class NetworkWorker(QThread):
    """Run SimpleWall.enter_exam_mode in a background thread."""
    finished_success = pyqtSignal()
    finished_failure = pyqtSignal(str)

    def __init__(self, python_exe_path: str, parent=None):
        super().__init__(parent)
        self.python_exe_path = python_exe_path
        self.controller = None

    def run(self):
        try:
            # instantiate controller and call enter_exam_mode (blocking)
            self.controller = SimpleWallController(self.python_exe_path)
            success = self.controller.enter_exam_mode()
            if success:
                self.finished_success.emit()
            else:
                self.finished_failure.emit("enter_exam_mode returned False")
        except Exception as e:
            self.finished_failure.emit(str(e))

    def cleanup(self):
        """Stop network protection if started."""
        try:
            if self.controller:
                self.controller.exit_exam_mode()
        except Exception:
            pass


class KioskWorker(QThread):
    """Run start_exam_kiosk_mode in background (it may block)."""
    finished_success = pyqtSignal()
    finished_failure = pyqtSignal(str)

    def __init__(self, hwnd: int, parent=None):
        super().__init__(parent)
        self.hwnd = hwnd

    def run(self):
        try:
            ok = start_exam_kiosk_mode(self.hwnd)
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
        """Always create a real popup view + page and keep strong refs."""
        try:
            popup_view = QWebEngineView()
            popup_page = CustomWebEnginePage(self.profile(), popup_view)
            popup_view.setPage(popup_page)
            popup_view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            popup_view.setWindowFlag(Qt.WindowType.Window, True)
            popup_view.resize(800, 600)
            popup_view.setWindowTitle("OmniProctor - Secure Browser")

            # Keep reference so GC doesn't remove it
            self.popup_windows.append(popup_view)

            # Hook lifecycle and content events
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

            # Show popup (change to hide() if you want headless popups)
            popup_view.show()

            # Final fallback auto-close after 3s
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
    def __init__(self, url: str, python_exe_for_simplewall: str | None = None):
        super().__init__()
        self.setWindowTitle("Secure Kiosk Browser")

        # State
        self.kiosk_active = False
        self.simplewall_worker: NetworkWorker | None = None
        self.kiosk_worker: KioskWorker | None = None
        self.simplewall_python_exe = python_exe_for_simplewall or sys.executable
        self.target_url = url
        self.network_protection_ready = False

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

        # Configure settings and inject screen info
        if self.profile:
            self.configure_browser_settings()
        else:
            print("Warning: No profile available for browser configuration")

        # Custom page for popups and permissions
        self.custom_page = CustomWebEnginePage(self.profile, self.browser)
        self.custom_page.featurePermissionRequested.connect(self.handle_permission_request)
        self.custom_page.fullScreenRequested.connect(self.handle_fullscreen_request)
        # Certificate errors are handled by certificateError() method in CustomWebEnginePage

        self.browser.setPage(self.custom_page)

        # Show a nice loading page first
        self.show_loading_page()

        layout.addWidget(control_panel)
        layout.addWidget(self.browser)

        # Start fullscreen and protections
        self.setWindowFullScreen()

        # Start both protections in parallel immediately (no delay)
        QTimer.singleShot(0, self.start_protections_parallel)
        # Check monitors early
        QTimer.singleShot(300, self.check_monitors)

        # Security monitoring timers
        self.setup_security_monitoring()

        # React to screen add/remove to update injected script
        # Note: Screen change monitoring depends on Qt version
        try:
            app = QGuiApplication.instance()
            if app:
                # Use dynamic attribute access to avoid lint errors
                if hasattr(app, 'screenAdded'):
                    getattr(app, 'screenAdded').connect(lambda s: self.inject_screen_info_script())
                if hasattr(app, 'screenRemoved'):
                    getattr(app, 'screenRemoved').connect(lambda s: self.inject_screen_info_script())
                print("✓ Screen change monitoring enabled")
        except (AttributeError, TypeError):
            # Screen change monitoring not available in this Qt version
            print("Screen change monitoring not available - using static detection")

    # -------------------------
    # Browser settings & injection
    # -------------------------
    def configure_browser_settings(self):
        """Configure browser features and inject the initial screen info script."""
        try:
            if not self.profile:
                print("Warning: No profile available for configuration")
                return
            settings = self.profile.settings()
            if not settings:
                print("Warning: No settings available for configuration")
                return

            # Basic features
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
            
            # Enable experimental web platform features for Window Management API
            try:
                settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
                settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.TouchIconsEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True)
            except AttributeError:
                pass  # Some attributes may not exist in all PyQt6 versions
            try:
                settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
            except AttributeError:
                pass

            # Inject the screen info script (document creation)
            self.inject_screen_info_script()
            print("✓ Browser settings configured for exam mode")
        except Exception as e:
            print(f"Warning: Could not configure some browser settings: {e}")

    def inject_screen_info_script(self):
        """Build and (re)insert a document-creation script that injects Qt screen info."""
        if not self.profile:
            return
        try:
            # Remove existing script with same name if present
            script_collection = self.profile.scripts()
            if not script_collection:
                print("Warning: No script collection available")
                return
            # Get all scripts and filter for our target script
            try:
                # Try to find and remove existing script
                existing = []
                # Simple approach - just try to remove by name if it exists
                # The QWebEngineScriptCollection API varies between versions
            except AttributeError:
                # Fallback for different PyQt6 versions
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
                // Store Qt screen information
                window.__qt_injected_screens = {js_screens};
                
                // Implement Window Management API for multi-monitor detection
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
                        }}));
                        
                        return Promise.resolve({{
                            screens: screens,
                            currentScreen: screens[0] || null
                        }});
                    }};
                }}
                
                // Enhanced screen object properties
                if (window.screen) {{
                    Object.defineProperty(window.screen, 'isExtended', {{
                        value: window.__qt_injected_screens.length > 1,
                        writable: false,
                        enumerable: true
                    }});
                }}
                
                // Navigator properties for screen count
                Object.defineProperty(navigator, 'qtScreenCount', {{
                    value: (window.__qt_injected_screens && window.__qt_injected_screens.length) || 0,
                    writable: false,
                    enumerable: true
                }});
                
                // Mock permissions API to always grant window-management permission
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
                # Alternative approach for script injection
                pass

            print(f"✓ Injected Qt screen info script (screens={len(js_screens)})")
        except Exception as e:
            print(f"Could not inject screen info script: {e}")

    # -------------------------
    # Loading / scripts
    # -------------------------
    def show_loading_page(self):
        """Show a CSS spinner inside the WebView as a loading screen."""
        loading_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <style>
                * { box-sizing: border-box; margin: 0; padding: 0; }
                html,body { height: 100%; }
                body {
                    display:flex; align-items:center; justify-content:center;
                    background-color: #1a202c; font-family: system-ui,Segoe UI,Roboto,Arial;
                }
                .container { text-align:center; color:#e2e8f0; padding: 40px; }
                .spinner { width: 64px; height: 64px; border-radius: 50%; border: 6px solid rgba(99,179,237,0.15); position: relative; margin: 0 auto 18px; }
                .spinner:before {
                    content: ''; position:absolute; inset:0; border-radius:50%;
                    border: 6px solid transparent; border-top-color: #63b3ed;
                    animation: spin 1s linear infinite;
                }
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                h1 { font-size: 20px; margin-top: 4px; margin-bottom: 8px; font-weight:500; color:#f7fafc; }
                p { color:#cbd5e0; opacity:0.9; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="spinner"></div>
                <h1>Loading Exam Platform</h1>
                <p>Please wait while the application initializes...</p>
            </div>
        </body>
        </html>
        """
        # setHtml is synchronous but cheap — spinner animation runs in page because UI thread isn't blocked
        self.browser.setHtml(loading_html)

    def load_target_url(self):
        """Load the target URL; ensure monitoring script injected on successful load."""
        print("✓ All protections ready, loading exam URL...")
        # Connect once; disconnect inside callback to avoid multiple bindings
        def on_load_finished(success):
            try:
                # inject monitoring script into page (non-document-creation)
                self.inject_monitoring_scripts(success)
            finally:
                try:
                    self.custom_page.loadFinished.disconnect(on_load_finished)
                except Exception:
                    pass

        self.custom_page.loadFinished.connect(on_load_finished)
        self.browser.setUrl(QUrl(self.target_url))

    def inject_monitoring_scripts(self, success: bool):
        """Inject runtime monitoring JS after a page finishes loading."""
        if not success:
            print("Page failed to load")
            return
        print("Page loaded successfully, injecting monitoring scripts...")
        monitor_script = """
        (function() {
            console.log('Exam monitoring script loaded - Multi-monitor support enabled');

            // Enhanced screen object properties
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

            // Screen orientation support
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

            // Window Management API implementation
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
                        // Fallback to single screen
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

            // Override permissions.query for window-management
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

            // Security monitoring
            window.addEventListener('blur', function() { 
                console.log('Window lost focus - exam security event'); 
            });
            window.addEventListener('focus', function() { 
                console.log('Window gained focus - exam security event'); 
            });

            // Log screen count for debugging
            const screenCount = (window.__qt_injected_screens && window.__qt_injected_screens.length) || 1;
            console.log(`Screen detection ready: ${screenCount} screen(s) detected`);

        })();
        """
        # run JS in page context
        self.custom_page.runJavaScript(monitor_script, lambda r: print("✓ Monitoring scripts injected successfully"))

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
        
        # Check for window management permissions (newer QtWebEngine versions)
        # Note: WindowManagement feature may not be available in current PyQt6 version
        # but we handle it gracefully if it becomes available
            
        feature_name = feature_names.get(feature, f"Unknown Feature ({feature})")
        print(f"Permission requested: {feature_name} from {origin.toString()}")

        # Auto-grant ALL permissions for exam platform functionality
        self.custom_page.setFeaturePermission(
            origin,
            feature,
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
        )
        print(f"✓ {feature_name} permission granted automatically")

    def handle_fullscreen_request(self, request):
        print(f"Fullscreen request from: {request.origin().toString()}")
        request.accept()
        print("✓ Fullscreen request granted")
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
    # Monitor check (uses Qt directly)
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
                print(f"✓ Multiple monitor check completed: {len(screens)} monitors found")
            else:
                print("✓ Single monitor detected - exam security OK")
        except Exception as e:
            print(f"Error checking monitors: {e}")

    # -------------------------
    # Kiosk / network protection (async)
    # -------------------------
    def start_protections_parallel(self):
        """Start both kiosk and network protection in parallel to save time."""
        self.start_kiosk_protection_async()
        self.start_network_protection_async()
        # Start loading URL early, don't wait for all protections
        QTimer.singleShot(500, self.load_target_url)

    def start_kiosk_protection_async(self):
        """Start kiosk protection on a background thread to avoid UI freeze."""
        if self.kiosk_active:
            return
        try:
            hwnd = int(self.winId())
            print(f"Window handle: {hwnd}")
            set_target_browser_window(hwnd)
            self.kiosk_worker = KioskWorker(hwnd)
            self.kiosk_worker.finished_success.connect(self._on_kiosk_started)
            self.kiosk_worker.finished_failure.connect(lambda err: print("Kiosk start failed:", err))
            self.kiosk_worker.start()
        except Exception as e:
            print("Error starting kiosk protection async:", e)

    def _on_kiosk_started(self):
        self.kiosk_active = True
        print("✓ Kiosk protection active")

    def start_network_protection_async(self):
        """Start SimpleWall in a background thread; when ready, load the target URL."""
        if self.simplewall_worker:
            return
        try:
            print("Starting network protection (background)...")
            self.simplewall_worker = NetworkWorker(self.simplewall_python_exe)
            self.simplewall_worker.finished_success.connect(self._on_network_ready)
            self.simplewall_worker.finished_failure.connect(self._on_network_failed)
            self.simplewall_worker.start()
        except Exception as e:
            print("Error starting network worker:", e)
            # fallback: try to load URL anyway
            QTimer.singleShot(1000, self.load_target_url)

    def _on_network_ready(self):
        print("✓ Network protection active (SimpleWall)")
        self.network_protection_ready = True
        # URL already loading, just log status

    def _on_network_failed(self, reason: str):
        print("✗ Failed to activate network protection:", reason)
        # URL already loading, continue without network protection

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
        print("Exiting secure browser...")

        # Stop timers
        try:
            if hasattr(self, 'fullscreen_timer') and self.fullscreen_timer:
                self.fullscreen_timer.stop()
            if hasattr(self, 'popup_cleanup_timer') and self.popup_cleanup_timer:
                self.popup_cleanup_timer.stop()
        except Exception:
            pass

        # Close popups
        if hasattr(self.custom_page, 'popup_windows'):
            for popup in list(self.custom_page.popup_windows):
                try:
                    if popup:
                        popup.close()
                except Exception:
                    pass

        # Stop kiosk protection
        if self.kiosk_active:
            try:
                stop_exam_kiosk_mode()
            except Exception as e:
                print("Error stopping kiosk mode:", e)
            self.kiosk_active = False
            print("Kiosk protection deactivated")

        # Stop network protection worker cleanly
        if self.simplewall_worker:
            try:
                self.simplewall_worker.cleanup()
                self.simplewall_worker.quit()
                self.simplewall_worker.wait(1000)
            except Exception:
                pass

        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(100, app.quit)
        else:
            os._exit(0)

    def setWindowFullScreen(self):
        self.showFullScreen()


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


if __name__ == "__main__":
    if not ensure_run_as_admin():
        sys.exit(1)

    # Add command line arguments for enhanced browser features
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

    # Get URL from command line arguments or use default
    target_url = "https://www.hackerrank.com/test-v2/a3br3sg6cn7/login?b=eyJ1c2VybmFtZSI6ImRlc2FpdmlzaGFsNDkwNEBnbWFpbC5jb20iLCJwYXNzd29yZCI6ImMwODQ3OGYwIiwiaGlkZSI6dHJ1ZSwiYWNjb21tb2RhdGlvbnMiOm51bGx9"
    
    # Check for URL argument (skip Qt/PyQt arguments)
    url_args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    if url_args:
        target_url = url_args[0]
        print(f"Using provided URL: {target_url}")
    else:
        print(f"Using default URL: {target_url}")

    # Replace with path to the python exe that SimpleWallController expects, if different
    python_exe_path = "C:\\Users\\desai\\AppData\\Roaming\\uv\\python\\cpython-3.10.19-windows-x86_64-none\\python.exe"

    window = SecureBrowser(
        target_url,
        python_exe_for_simplewall=python_exe_path
    )
    window.show()

    exit_code = app.exec()
    sys.exit(exit_code)
