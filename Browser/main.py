import sys
import requests
import subprocess
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedWidget, QMessageBox, QFrame, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont


class APIClient:
    """Handle API requests to the backend"""
    def __init__(self, base_url="http://localhost:3000"):
        self.base_url = base_url
        self.token = None
        self.user_data = None

    def test_connection(self):
        """Test if the backend server is reachable"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return True, f"Server reachable (Status: {response.status_code})"
        except requests.RequestException as e:
            return False, f"Server unreachable: {str(e)}"

    def login(self, email, password):
        """Login user and store token"""
        try:
            response = requests.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                # Try different possible keys for user data
                self.user_data = (
                    data.get("admin")
                    or data.get("user")
                    or data.get("data")
                    or {}
                )
                if not self.user_data:
                    self.user_data = {"name": data.get("name", "User"), "email": email}
                return True, "Login successful"
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get(
                        "error", error_data.get("message", "Login failed")
                    )
                except Exception:
                    return False, f"Login failed with status {response.status_code}"
        except requests.RequestException as e:
            return False, f"Connection error: {str(e)}"

    def register(self, name, email, password):
        """Register new user"""
        try:
            response = requests.post(
                f"{self.base_url}/auth/signup",
                json={"name": name, "email": email, "password": password}
            )
            if response.status_code in (200, 201):
                data = response.json()
                self.token = data.get("token")
                return True, "Registration successful"
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get(
                        "message", error_data.get("error", "Registration failed")
                    )
                except Exception:
                    return False, f"Registration failed with status {response.status_code}"
        except requests.RequestException as e:
            return False, f"Connection error: {str(e)}"

    def get_active_tests(self):
        """Get all active tests"""
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            response = requests.get(
                f"{self.base_url}/api/tests/activeTests", headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                return True, data
            elif response.status_code == 401:
                return False, "Authentication required. Please login again."
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get(
                        "message",
                        f"HTTP {response.status_code}: Failed to fetch tests"
                    )
                except Exception:
                    error_text = response.text
                    return False, (
                        f"HTTP {response.status_code}: Failed to fetch tests - "
                        f"{error_text[:100]}"
                    )
        except requests.RequestException as e:
            return False, f"Connection error: {str(e)}"


class TestCard(QFrame):
    """Custom widget for displaying test information"""
    def __init__(self, test_data):
        super().__init__()
        self.test_data = test_data
        self.init_ui()

    def init_ui(self):
        self.setObjectName("TestCard")
        self.setFrameStyle(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Test name
        name_label = QLabel(self.test_data.get("name", "Untitled Test"))
        name_label.setObjectName("TestTitle")
        font = QFont("Segoe UI", 12)
        font.setBold(True)
        name_label.setFont(font)

        # Test details
        admin_name = self.test_data.get("admin", {}).get("name", "Unknown Admin")
        admin_label = QLabel(f"Created by: {admin_name}")
        admin_label.setObjectName("TestMeta")

        date_str = self.test_data.get("date", "Unknown Date")
        time_str = self.test_data.get("time", "Unknown Time")
        datetime_label = QLabel(f"{date_str} · {time_str}")
        datetime_label.setObjectName("TestMeta")

        # Editable link field
        edit_link = self.test_data.get("url", "")
        self.edit_link_input = QLineEdit(edit_link)
        self.edit_link_input.setPlaceholderText("Test URL (editable)")
        self.edit_link_input.setObjectName("TestUrlInput")
        self.edit_link_input.setMinimumHeight(24)

        # Launch button
        launch_btn = QPushButton("Launch in Secure Browser")
        launch_btn.setObjectName("LaunchButton")
        launch_btn.clicked.connect(self.launch_test)

        layout.addWidget(name_label)
        layout.addWidget(admin_label)
        layout.addWidget(datetime_label)
        layout.addSpacing(4)
        layout.addWidget(self.edit_link_input)
        layout.addSpacing(6)
        layout.addWidget(launch_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def launch_test(self):
        """Launch the test in secure browser"""
        test_url = self.edit_link_input.text().strip() or self.test_data.get("url")
        if test_url:
            current_file = os.path.abspath(__file__)
            client_dir = os.path.dirname(current_file)
            browser_script = os.path.join(client_dir, "browser", "main.py")

            try:
                if not os.path.exists(browser_script):
                    QMessageBox.warning(
                        self,
                        "Secure Browser Not Found",
                        (
                            "Secure browser script not found at:\n"
                            f"{browser_script}\n\n"
                            "Please make sure the 'browser' folder and main.py exist."
                        ),
                    )
                    return

                subprocess.Popen(
                    [sys.executable, browser_script, test_url],
                    cwd=os.path.dirname(browser_script),
                )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Launch Error",
                    (
                        "Failed to launch secure browser:\n"
                        f"{str(e)}\n\n"
                        f"Path checked: {browser_script}"
                    ),
                )
        else:
            QMessageBox.warning(self, "Missing URL", "Test URL is not available.")


class ConnectionTestWorker(QThread):
    """Worker thread for testing connection asynchronously"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
    
    def run(self):
        success, message = self.api_client.test_connection()
        self.finished.emit(success, message)


class TestsLoaderThread(QThread):
    """Worker thread for loading tests asynchronously"""
    finished = pyqtSignal(bool, object)  # success, data_or_error

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client

    def run(self):
        # This runs in a background thread
        success, data = self.api_client.get_active_tests()
        self.finished.emit(success, data)


class LoginWorker(QThread):
    """Worker thread for login asynchronously"""
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, api_client, email, password):
        super().__init__()
        self.api_client = api_client
        self.email = email
        self.password = password

    def run(self):
        success, message = self.api_client.login(self.email, self.password)
        self.finished.emit(success, message)


class RegisterWorker(QThread):
    """Worker thread for registration asynchronously"""
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, api_client, name, email, password):
        super().__init__()
        self.api_client = api_client
        self.name = name
        self.email = email
        self.password = password

    def run(self):
        success, message = self.api_client.register(self.name, self.email, self.password)
        self.finished.emit(success, message)


class LoginWidget(QWidget):
    """Login/Register interface"""
    login_success = pyqtSignal(dict)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.is_register_mode = False
        self.connection_worker = None
        self.login_worker = None
        self.register_worker = None
        self.init_ui()

    def init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Left branding panel
        branding = QWidget()
        branding.setObjectName("BrandingPanel")
        branding_layout = QVBoxLayout(branding)
        branding_layout.setContentsMargins(40, 40, 40, 40)
        branding_layout.setSpacing(16)

        app_title = QLabel("OmniProctor")
        app_title.setObjectName("BrandingTitle")

        app_tagline = QLabel(
            "Focus on your test, we handle the rest."
        )
        app_tagline.setObjectName("BrandingSubtitle")
        app_tagline.setWordWrap(True)

        # bullet1 = QLabel("• Locked-down secure browser")
        # bullet2 = QLabel("• Network & process monitoring")
        # bullet3 = QLabel("• Multi-platform support")
        # for b in (bullet1, bullet2, bullet3):
        #     b.setObjectName("BrandingBullet")

        branding_layout.addWidget(app_title)
        branding_layout.addWidget(app_tagline)
        branding_layout.addSpacing(12)
        # branding_layout.addWidget(bullet1)
        # branding_layout.addWidget(bullet2)
        # branding_layout.addWidget(bullet3)
        branding_layout.addStretch()

        # Right form container (card)
        form_container = QWidget()
        form_container.setObjectName("FormContainer")
        form_layout_outer = QVBoxLayout(form_container)
        form_layout_outer.setContentsMargins(40, 40, 40, 40)
        form_layout_outer.setSpacing(16)

        title = QLabel("Sign in to continue")
        title.setObjectName("FormTitle")

        subtitle = QLabel("Use your registered email to access available tests.")
        subtitle.setObjectName("FormSubtitle")
        subtitle.setWordWrap(True)

        form_card = QFrame()
        form_card.setObjectName("FormCard")
        inner_layout = QVBoxLayout(form_card)
        inner_layout.setContentsMargins(24, 24, 24, 24)
        inner_layout.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Full name (for registration)")
        self.name_input.setObjectName("TextInput")
        self.name_input.hide()

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        self.email_input.setObjectName("TextInput")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName("TextInput")

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.clicked.connect(self.login)

        self.login_loader = QProgressBar()
        self.login_loader.setObjectName("LoginLoader")
        self.login_loader.setRange(0, 0)
        self.login_loader.setFixedHeight(6)
        self.login_loader.hide()

        self.register_btn = QPushButton("Create Account")
        self.register_btn.setObjectName("AccentButton")
        self.register_btn.clicked.connect(self.register)
        self.register_btn.hide()

        self.toggle_btn = QPushButton("New here? Create an account")
        self.toggle_btn.setObjectName("LinkButton")
        self.toggle_btn.clicked.connect(self.toggle_mode)

        self.test_conn_btn = QPushButton("Test Server Connection")
        self.test_conn_btn.setObjectName("SecondaryButton")
        self.test_conn_btn.clicked.connect(self.test_connection)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.conn_loader = QProgressBar()
        self.conn_loader.setObjectName("ConnLoader")
        self.conn_loader.setRange(0, 0)          # indeterminate/busy mode
        self.conn_loader.setFixedHeight(6)
        self.conn_loader.hide()

        inner_layout.addWidget(self.name_input)
        inner_layout.addWidget(self.email_input)
        inner_layout.addWidget(self.password_input)
        inner_layout.addSpacing(6)
        inner_layout.addWidget(self.login_btn)
        inner_layout.addWidget(self.login_loader)
        inner_layout.addWidget(self.register_btn)
        inner_layout.addSpacing(4)
        inner_layout.addWidget(self.toggle_btn, alignment=Qt.AlignmentFlag.AlignRight)
        inner_layout.addSpacing(8)
        inner_layout.addWidget(self.test_conn_btn)
        inner_layout.addWidget(self.status_label)
        inner_layout.addWidget(self.conn_loader) 

        form_layout_outer.addWidget(title)
        form_layout_outer.addWidget(subtitle)
        form_layout_outer.addWidget(form_card)
        form_layout_outer.addStretch()

        root_layout.addWidget(branding, stretch=3)
        root_layout.addWidget(form_container, stretch=4)

        self.update_ui_mode()

    def toggle_mode(self):
        self.is_register_mode = not self.is_register_mode
        self.update_ui_mode()
        self.status_label.setText("")
        self.status_label.setStyleSheet("")

    def update_ui_mode(self):
        if self.is_register_mode:
            self.name_input.show()
            self.login_btn.hide()
            self.register_btn.show()
            self.toggle_btn.setText("Already registered? Sign in instead")
        else:
            self.name_input.hide()
            self.register_btn.hide()
            self.login_btn.show()
            self.toggle_btn.setText("New here? Create an account")

    def login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()

        if not email or not password:
            self.status_label.setStyleSheet("color: #f97373;")
            self.status_label.setText("Please enter both email and password.")
            return

        self.login_btn.setText("Signing in…")
        self.login_btn.setEnabled(False)
        self.status_label.setText("")
        self.login_loader.show()

        # Start background login
        self.login_worker = LoginWorker(self.api_client, email, password)
        self.login_worker.finished.connect(self.on_login_finished)
        self.login_worker.start()

    def on_login_finished(self, success, message):
        """Handle login results from background thread"""
        self.login_loader.hide()
        
        if success:
            self.status_label.setText("")
            self.login_success.emit(self.api_client.user_data)
        else:
            self.status_label.setStyleSheet("color: #f97373;")
            self.status_label.setText(f"Sign-in failed: {message}")

        self.login_btn.setText("Sign In")
        self.login_btn.setEnabled(True)
        self.login_worker = None

    def register(self):
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()

        if not name or not email or not password:
            self.status_label.setStyleSheet("color: #f97373;")
            self.status_label.setText("Please fill in all fields.")
            return

        self.register_btn.setText("Creating account…")
        self.register_btn.setEnabled(False)
        self.status_label.setText("")
        self.login_loader.show()

        # Start background registration
        self.register_worker = RegisterWorker(self.api_client, name, email, password)
        self.register_worker.finished.connect(self.on_register_finished)
        self.register_worker.start()

    def on_register_finished(self, success, message):
        """Handle registration results from background thread"""
        self.login_loader.hide()
        
        if success:
            self.status_label.setStyleSheet("color: #4ade80;")
            self.status_label.setText("Account created! You can now sign in.")
            self.toggle_mode()
        else:
            self.status_label.setStyleSheet("color: #f97373;")
            self.status_label.setText(f"Registration failed: {message}")

        self.register_btn.setText("Create Account")
        self.register_btn.setEnabled(True)
        self.register_worker = None

    def test_connection(self):
        self.test_conn_btn.setText("Testing…")
        self.test_conn_btn.setEnabled(False)
        self.status_label.setText("")
        self.conn_loader.show()
        
        # Create and start worker thread
        self.connection_worker = ConnectionTestWorker(self.api_client)
        self.connection_worker.finished.connect(self.on_connection_test_finished)
        self.connection_worker.start()
    
    def on_connection_test_finished(self, success, message):
        """Handle connection test results"""
        if success:
            self.status_label.setStyleSheet("color: #4ade80;")
        else:
            self.status_label.setStyleSheet("color: #f97373;")
        self.status_label.setText(message)
        self.conn_loader.hide()
        self.test_conn_btn.setText("Test Server Connection")
        self.test_conn_btn.setEnabled(True)


class TestsWidget(QWidget):
    """Display available tests"""
    logout_requested = pyqtSignal()

    def __init__(self, api_client, user_data):
        super().__init__()
        self.api_client = api_client
        self.user_data = user_data
        self.loader_thread = None
        self.init_ui()
        self.load_tests()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top header bar
        header = QWidget()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(10)

        app_label = QLabel("OmniProctor · Test Dashboard")
        app_label.setObjectName("HeaderTitle")

        user_label = QLabel(self.user_data.get("name", "Candidate"))
        user_label.setObjectName("HeaderUser")

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("HeaderButton")
        refresh_btn.clicked.connect(self.load_tests)

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("HeaderButtonDanger")
        logout_btn.clicked.connect(self.logout)

        header_layout.addWidget(app_label)
        header_layout.addStretch()
        header_layout.addWidget(user_label)
        header_layout.addSpacing(10)
        header_layout.addWidget(refresh_btn)
        header_layout.addWidget(logout_btn)

        # Content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(10)

        title = QLabel("Available Tests")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Select a test below to launch it in the secure exam browser.")
        subtitle.setObjectName("PageSubtitle")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("TestsScrollArea")

        self.tests_widget = QWidget()
        self.tests_widget.setObjectName("TestsViewport")
        self.tests_layout = QVBoxLayout(self.tests_widget)
        self.tests_layout.setContentsMargins(0, 0, 0, 0)
        self.tests_layout.setSpacing(10)
        self.scroll_area.setWidget(self.tests_widget)

        self.status_label = QLabel("Loading tests…")
        self.status_label.setObjectName("StatusInfo")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.status_label.setWordWrap(True)

        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addSpacing(6)
        content_layout.addWidget(self.scroll_area, stretch=1)
        content_layout.addWidget(self.status_label)

        layout.addWidget(header)
        layout.addWidget(content, stretch=1)

    def load_tests(self):
        # If a load is already running, ignore extra clicks
        if self.loader_thread is not None and self.loader_thread.isRunning():
            return

        self.status_label.setText("Loading tests…")
        
        # Scroll to top
        # if self.scroll_area.verticalScrollBar():
        #     self.scroll_area.verticalScrollBar().setValue(0)

        # Clear existing tests from layout
        for i in reversed(range(self.tests_layout.count())):
            item = self.tests_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)

        # Disable refresh button while loading
        for w in self.findChildren(QPushButton):
            if "refresh" in w.text().lower():
                w.setEnabled(False)

        # Start background loader
        self.loader_thread = TestsLoaderThread(self.api_client)
        self.loader_thread.finished.connect(self.on_tests_loaded)
        self.loader_thread.start()

    def on_tests_loaded(self, success: bool, data):
        """Handle test loading results from background thread"""
        # Re-enable refresh button
        for w in self.findChildren(QPushButton):
            if "refresh" in w.text().lower():
                w.setEnabled(True)

        if success:
            tests = data or []
            if tests:
                self.status_label.setText(f"{len(tests)} active test(s) found.")
                for test in tests:
                    card = TestCard(test)
                    self.tests_layout.addWidget(card)
                self.tests_layout.addStretch()
            else:
                self.status_label.setText("No active tests are currently available.")
        else:
            self.status_label.setText(f"Failed to load tests: {data}")

        self.loader_thread = None

    def logout(self):
        self.logout_requested.emit()


class TestLauncherApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.api_client = APIClient()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("OmniProctor Test Launcher")
        self.resize(950, 620)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.login_widget = LoginWidget(self.api_client)
        self.login_widget.login_success.connect(self.show_tests)
        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.setCurrentWidget(self.login_widget)

    def show_tests(self, user_data):
        self.tests_widget = TestsWidget(self.api_client, user_data)
        self.tests_widget.logout_requested.connect(self.show_login)
        self.stacked_widget.addWidget(self.tests_widget)
        self.stacked_widget.setCurrentWidget(self.tests_widget)

    def show_login(self):
        if hasattr(self, "tests_widget"):
            self.stacked_widget.removeWidget(self.tests_widget)
            self.tests_widget.deleteLater()

        self.api_client.token = None
        self.api_client.user_data = None

        self.login_widget.email_input.clear()
        self.login_widget.password_input.clear()
        self.login_widget.name_input.clear()
        self.login_widget.status_label.setText("")
        self.login_widget.status_label.setStyleSheet("")
        self.login_widget.is_register_mode = False
        self.login_widget.update_ui_mode()

        self.stacked_widget.setCurrentWidget(self.login_widget)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("OmniProctor Test Launcher")
    app.setApplicationVersion("1.0")

    # Global stylesheet for a more polished UI
    app.setStyleSheet("""
    QMainWindow {
        background-color: #020617;
    }
    QWidget#BrandingPanel {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 #0f172a, stop:1 #020617);
        color: #e5e7eb;
    }
    QLabel#BrandingTitle {
        font-family: "Segoe UI";
        font-size: 26px;
        font-weight: 700;
        color: #f9fafb;
    }
    QLabel#BrandingSubtitle {
        font-size: 13px;
        color: #cbd5e1;
    }
    QWidget#FormContainer {
        background-color: #020617;
    }
    QLabel#FormTitle {
        color: #e5e7eb;
        font-size: 20px;
        font-weight: 600;
    }
    QLabel#FormSubtitle {
        color: #9ca3af;
        font-size: 12px;
    }
    QFrame#FormCard {
        background-color: #020617;
        border-radius: 14px;
        border: 1px solid #1f2937;
    }
    QLineEdit#TextInput {
        background-color: #020617;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 13px;
        color: #e5e7eb;
    }
    QLineEdit#TextInput:focus {
        border-color: #3b82f6;
    }
    QPushButton#PrimaryButton {
        background-color: #3b82f6;
        color: white;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 13px;
        font-weight: 600;
        border: none;
        outline: none;
    }
    QPushButton#PrimaryButton:hover {
        background-color: #2563eb;
    }
    QPushButton#PrimaryButton:focus {
        outline: none;
    }
    QPushButton#AccentButton {
        background-color: #6366f1;
        color: white;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 13px;
        font-weight: 600;
        border: none;
        outline: none;
    }
    QPushButton#AccentButton:hover {
        background-color: #4f46e5;
    }
    QPushButton#AccentButton:focus {
        outline: none;
    }
    QPushButton#SecondaryButton {
        background-color: #111827;
        color: #e5e7eb;
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 12px;
        border: 1px solid #374151;
        outline: none;
    }
    QPushButton#SecondaryButton:hover {
        background-color: #1f2937;
    }
    QPushButton#SecondaryButton:focus {
        outline: none;
    }
    QPushButton#LinkButton {
        background: none;
        border: none;
        color: #60a5fa;
        font-size: 11px;
        text-decoration: underline;
        outline: none;
    }
    QPushButton#LinkButton:hover {
        color: #93c5fd;
    }
    QPushButton#LinkButton:focus {
        outline: none;
    }
    QLabel#StatusLabel {
        font-size: 11px;
        min-height: 20px;
    }

    /* Dashboard */
    QWidget#HeaderBar {
        background-color: #020617;
        border-bottom: 1px solid #111827;
    }
    QLabel#HeaderTitle {
        color: #e5e7eb;
        font-weight: 600;
        font-size: 14px;
    }
    QLabel#HeaderUser {
        color: #9ca3af;
        font-size: 12px;
    }
    QPushButton#HeaderButton {
        background-color: #111827;
        color: #e5e7eb;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 11px;
        border: 1px solid #374151;
        outline: none;
    }
    QPushButton#HeaderButton:hover {
        background-color: #1f2937;
    }
    QPushButton#HeaderButton:focus {
        outline: none;
    }
    QPushButton#HeaderButtonDanger {
        background-color: #ef4444;
        color: white;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 11px;
        border: none;
        outline: none;
    }
    QPushButton#HeaderButtonDanger:hover {
        background-color: #dc2626;
    }
    QPushButton#HeaderButtonDanger:focus {
        outline: none;
    }
    QLabel#PageTitle {
        color: #e5e7eb;
        font-size: 18px;
        font-weight: 600;
    }
    QLabel#PageSubtitle {
        color: #9ca3af;
        font-size: 12px;
        margin-bottom: 8px;
    }
    QScrollArea#TestsScrollArea {
        background-color: #020617;
        border: 1px solid #111827;
        border-radius: 10px;
    }
    QScrollArea#TestsScrollArea > QWidget {
        background-color: #020617;
    }
    QWidget#TestsViewport {
        background-color: #020617;
    }
    QFrame#TestCard {
        background-color: #020617;
        border-radius: 10px;
        border: 1px solid #111827;
    }
    QFrame#TestCard:hover {
        border-color: #3b82f6;
    }
    QLabel#TestTitle {
        color: #e5e7eb;
    }
    QLabel#TestMeta {
        color: #9ca3af;
        font-size: 11px;
    }
    QLineEdit#TestUrlInput {
        background-color: #020617;
        border-radius: 4px;
        border: 1px dashed #374151;
        padding: 4px 6px;
        font-size: 11px;
        color: #cbd5e1;
    }
    QPushButton#LaunchButton {
        background-color: #22c55e;
        color: #022c22;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 600;
        border: none;
        outline: none;
    }
    QPushButton#LaunchButton:hover {
        background-color: #16a34a;
    }
    QPushButton#LaunchButton:focus {
        outline: none;
    }
    QLabel#StatusInfo {
        color: #9ca3af;
        font-size: 12px;
        padding: 6px;
    }

    QMessageBox {
        background-color: #020617;
    }
    QMessageBox QLabel {
        color: #e5e7eb;
        font-size: 12px;
    }
    QMessageBox QPushButton {
        background-color: #111827;
        color: #e5e7eb;
        border-radius: 4px;
        padding: 4px 10px;
    }
    QProgressBar#ConnLoader {
        border: none;
        background-color: #020617;
        border-radius: 3px;
    }
    QProgressBar#ConnLoader::chunk {
        background-color: #3b82f6;
        border-radius: 3px;
    }
    QProgressBar#LoginLoader {
        border: none;
        background-color: #020617;
        border-radius: 3px;
    }
    QProgressBar#LoginLoader::chunk {
        background-color: #3b82f6;
        border-radius: 3px;
    }
    QMessageBox QPushButton:hover {
        background-color: #1f2937;
    }
    """)

    window = TestLauncherApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
