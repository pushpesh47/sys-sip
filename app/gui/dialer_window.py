"""Dialer main window for voice calling."""

from app import APP_VERSION, APP_DESCRIPTION, APP_DEVELOPER, APP_DEVELOPER_NUMBER, APP_DEVELOPER_GIT

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QTime
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QMenuBar,
    QMenu,
    QFrame,
    QSizePolicy,
    QGridLayout,
    QStatusBar,
)
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap, QPainter, QColor

from app.config.settings import SipProviderConfig
from app.gui.main_window import MainWindow as SipAccountsWindow
from app.sip.service import get_service, SipApplicationService
from app.sip.engine import RegistrationState, CallState
from app.gui.assets import load_app_icon, load_logo_pixmap, apply_no_maximize_flags
from app.gui.qt_bridge import QtEventBridge


class StatusIndicator(QWidget):
    """Colored status indicator widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor("#9e9e9e")  # Gray

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 12, 12)


class DialerWindow(QMainWindow):
    """Main dialer window for voice calling."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SysSIP - SIP/VoIP Dialer")
        self.setWindowIcon(load_app_icon())
        apply_no_maximize_flags(self)
        self.resize(950, 600)
        self._service: SipApplicationService = get_service()
        self._sip_accounts_window: SipAccountsWindow | None = None
        self._incoming_call_dialog = None
        self._call_duration_timer = QTimer()
        self._call_duration_timer.setInterval(1000)
        self._call_duration_timer.timeout.connect(self._update_call_duration)
        self._call_start_time = QTime(0, 0)
        self._current_call_id = -1
        self._mic_muted = False
        
        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._check_initial_state()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Left panel - Account / SIP Status
        left_panel = self._create_account_status_panel()
        main_layout.addWidget(left_panel, 1)

        # Right panel - Dialer
        right_panel = self._create_dialer_panel()
        main_layout.addWidget(right_panel, 2)

        # Bottom status bar
        self._setup_status_bar()

    def _create_account_status_panel(self) -> QWidget:
        """Create the left account/SIP status panel."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(320)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Active Account section
        account_title = QLabel("Active Account")
        account_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a2e; background: transparent; border: none;")
        layout.addWidget(account_title)

        # Account info frame
        account_frame = QFrame()
        account_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e8e8e8;
                border-radius: 6px;
            }
        """)
        account_layout = QVBoxLayout(account_frame)
        account_layout.setSpacing(8)
        account_layout.setContentsMargins(16, 16, 16, 16)

        # Provider name with status indicator
        provider_layout = QHBoxLayout()
        self.account_indicator = StatusIndicator()
        self.account_name_label = QLabel("Jio Fiber")
        self.account_name_label.setStyleSheet("font-size: 16px; font-weight: 500; color: #1a1a2e; background: transparent; border: none;")
        provider_layout.addWidget(self.account_indicator)
        provider_layout.addWidget(self.account_name_label)
        provider_layout.addStretch()
        account_layout.addLayout(provider_layout)

        # Registration status
        self.account_reg_label = QLabel("Registered")
        self.account_reg_label.setStyleSheet("font-size: 12px; color: #4caf50; font-weight: 500; background: transparent; border: none;")
        account_layout.addWidget(self.account_reg_label)

        # SIP URI
        self.account_uri_label = QLabel("916546317451@br.wln.lms.jio.com")
        self.account_uri_label.setStyleSheet("font-size: 11px; color: #666; font-family: monospace; background: transparent; border: none;")
        self.account_uri_label.setWordWrap(True)
        account_layout.addWidget(self.account_uri_label)

        layout.addWidget(account_frame)

        # SIP Provider section
        provider_title = QLabel("SIP Provider")
        provider_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a2e; margin-top: 8px; background: transparent; border: none;")
        layout.addWidget(provider_title)

        provider_info_frame = QFrame()
        provider_info_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e8e8e8;
                border-radius: 6px;
            }
        """)
        provider_info_layout = QVBoxLayout(provider_info_frame)
        provider_info_layout.setSpacing(10)
        provider_info_layout.setContentsMargins(16, 16, 16, 16)

        # Provider name
        self.provider_name_label = QLabel("Jio Fiber")
        self.provider_name_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #1a1a2e; background: transparent; border: none;")
        provider_info_layout.addWidget(self.provider_name_label)

        # Registration status
        reg_status_layout = QHBoxLayout()
        self.reg_status_indicator = StatusIndicator()
        self.reg_status_indicator.set_color("#4caf50")
        self.reg_status_label = QLabel("Registered")
        self.reg_status_label.setStyleSheet("font-size: 13px; color: #333; background: transparent; border: none;")
        reg_status_layout.addWidget(self.reg_status_indicator)
        reg_status_layout.addWidget(self.reg_status_label)
        reg_status_layout.addStretch()
        provider_info_layout.addLayout(reg_status_layout)

        # SIP Server
        self.server_label = QLabel("jiofiber.local.html:5068")
        self.server_label.setStyleSheet("font-size: 12px; color: #666; font-family: monospace; background: transparent; border: none;")
        provider_info_layout.addWidget(self.server_label)

        # Transport
        self.transport_label = QLabel("TLS")
        self.transport_label.setStyleSheet("font-size: 12px; color: #666; background: transparent; border: none;")
        provider_info_layout.addWidget(self.transport_label)

        layout.addWidget(provider_info_frame)

        # Call Status section
        call_status_title = QLabel("Call Status")
        call_status_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a2e; margin-top: 8px; background: transparent; border: none;")
        layout.addWidget(call_status_title)

        call_status_frame = QFrame()
        call_status_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e8e8e8;
                border-radius: 6px;
            }
        """)
        call_status_layout = QVBoxLayout(call_status_frame)
        call_status_layout.setSpacing(8)
        call_status_layout.setContentsMargins(16, 16, 16, 16)

        self.call_status_indicator = StatusIndicator()
        self.call_status_indicator.set_color("#9e9e9e")
        self.call_status_label = QLabel("Idle")
        self.call_status_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #1a1a2e; background: transparent; border: none;")
        call_status_layout.addWidget(self.call_status_indicator)
        call_status_layout.addWidget(self.call_status_label)

        layout.addWidget(call_status_frame)
        layout.addStretch()

        return panel

    def _create_dialer_panel(self) -> QWidget:
        """Create the right dialer panel."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # DIALER heading
        dialer_title = QLabel("DIALER")
        dialer_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1a1a2e; letter-spacing: 1px; background: transparent; border: none;")
        layout.addWidget(dialer_title)

        # Destination Number input
        number_label = QLabel("")
        number_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #3a3a4e; background: transparent; border: none;")
        layout.addWidget(number_label)

        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("Enter number or SIP URI")
        self.number_input.setFixedHeight(56)
        self.number_input.setFont(QFont("Monospace", 20))
        self.number_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 0 16px;
                color: #1a1a2e;
                letter-spacing: 1px;
            }
            QLineEdit:focus {
                border-color: #2d7ff9;
            }
        """)
        self.number_input.returnPressed.connect(self._on_call_clicked)
        layout.addWidget(self.number_input)

        # Dial Pad
        dialpad_frame = QFrame()
        dialpad_frame.setStyleSheet("background: transparent;")
        dialpad_layout = QGridLayout(dialpad_frame)
        dialpad_layout.setSpacing(12)
        dialpad_layout.setContentsMargins(0, 0, 0, 0)

        keys = [
            ("1", ""), ("2", "ABC"), ("3", "DEF"),
            ("4", "GHI"), ("5", "JKL"), ("6", "MNO"),
            ("7", "PQRS"), ("8", "TUV"), ("9", "WXYZ"),
            ("*", ""), ("0", "+"), ("#", ""),
        ]

        for idx, (digit, letters) in enumerate(keys):
            row = idx // 3
            col = idx % 3
            btn = self._create_dialpad_button(digit, letters)
            dialpad_layout.addWidget(btn, row, col)

        layout.addWidget(dialpad_frame)

        # Call Controls
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)

        self.call_button = QPushButton("CALL")
        self.call_button.setFixedHeight(56)
        self.call_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.call_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                min-width: 140px;
            }
            QPushButton:hover:enabled {
                background-color: #43a047;
            }
            QPushButton:pressed:enabled {
                background-color: #388e3c;
            }
            QPushButton:disabled {
                background-color: #a5d6a7;
                color: #e8f5e9;
            }
        """)
        self.call_button.clicked.connect(self._on_call_clicked)
        button_layout.addWidget(self.call_button)

        self.hangup_button = QPushButton("HANG UP")
        self.hangup_button.setFixedHeight(56)
        self.hangup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hangup_button.setEnabled(False)
        self.hangup_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                min-width: 140px;
            }
            QPushButton:hover:enabled {
                background-color: #e53935;
            }
            QPushButton:pressed:enabled {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #ef9a9a;
                color: #fde0e0;
            }
        """)
        self.hangup_button.clicked.connect(self._on_hangup_clicked)
        button_layout.addWidget(self.hangup_button)

        layout.addLayout(button_layout)

        # Active Call Controls (shown only during connected call)
        self.active_call_frame = QFrame()
        self.active_call_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e8e8e8;
                border-radius: 8px;
            }
        """)
        self.active_call_frame.setVisible(False)
        active_call_layout = QHBoxLayout(self.active_call_frame)
        active_call_layout.setSpacing(20)
        active_call_layout.setContentsMargins(20, 16, 20, 16)

        # Call duration
        self.call_duration_label = QLabel("00:00")
        self.call_duration_label.setStyleSheet("font-size: 24px; font-weight: bold; font-family: monospace; color: #2d7ff9;")
        self.call_duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        active_call_layout.addWidget(self.call_duration_label, 1)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #e0e0e0;")
        active_call_layout.addWidget(separator)

        # Microphone mute/unmute button
        self.mic_button = QPushButton("🎤 MIC ON")
        self.mic_button.setFixedHeight(44)
        self.mic_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #a5d6a7;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #c8e6c9;
                border-color: #81c784;
            }
            QPushButton:pressed {
                background-color: #a5d6a7;
            }
        """)
        self.mic_button.clicked.connect(self._on_mic_toggle)
        active_call_layout.addWidget(self.mic_button)

        layout.addWidget(self.active_call_frame)
        layout.addStretch()

        return panel

    def _create_dialpad_button(self, digit: str, letters: str) -> QPushButton:
        """Create a dial pad button."""
        btn = QPushButton()
        btn.setFixedSize(72, 72)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if letters:
            btn.setText(f"{digit}\n{letters}")
        else:
            btn.setText(digit)
        
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 36px;
                font-size: 24px;
                font-weight: 500;
                color: #1a1a2e;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #e8e8e8;
            }
        """)
        
        # For multi-line text, we need to adjust
        if letters:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 36px;
                    font-size: 18px;
                    font-weight: 500;
                    color: #1a1a2e;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                    border-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #e8e8e8;
                }
            """)
        
        btn.clicked.connect(lambda: self._on_dialpad_clicked(digit))
        return btn

    def _on_dialpad_clicked(self, digit: str) -> None:
        """Handle dial pad button click."""
        current_text = self.number_input.text()
        self.number_input.setText(current_text + digit)
        self.number_input.setFocus()

    def _setup_status_bar(self) -> None:
        """Setup bottom status bar."""
        status_bar = QStatusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #f5f5f5;
                border-top: 1px solid #e0e0e0;
                color: #333;
                font-size: 12px;
            }
        """)
        
        # Left side - Status message
        self.status_message_label = QLabel("Ready")
        status_bar.addWidget(self.status_message_label)
        
        # Right side - Registration status and transport
        status_bar.addPermanentWidget(QLabel("  "))
        
        self.status_reg_indicator = StatusIndicator()
        self.status_reg_indicator.set_color("#4caf50")
        status_bar.addPermanentWidget(self.status_reg_indicator)
        
        self.status_reg_label = QLabel("Registered (Jio Fiber)")
        self.status_reg_label.setStyleSheet("font-weight: 500;")
        status_bar.addPermanentWidget(self.status_reg_label)
        
        status_bar.addPermanentWidget(QLabel("  "))
        
        self.status_transport_label = QLabel("TLS")
        self.status_transport_label.setStyleSheet("font-weight: 500; color: #2d7ff9;")
        status_bar.addPermanentWidget(self.status_transport_label)
        
        self.setStatusBar(status_bar)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #fafafa;
                border-bottom: 1px solid #e0e0e0;
                font-size: 13px;
                padding: 4px 8px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #e8e8e8;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #e8e8e8;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # SIP menu
        sip_menu = menubar.addMenu("SIP")
        accounts_action = QAction("SIP Accounts", self)
        accounts_action.triggered.connect(self._show_sip_accounts)
        sip_menu.addAction(accounts_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About SysSIP", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _connect_signals(self) -> None:
        # Connect Qt event bridge signals with queued connection for thread safety
        bridge = QtEventBridge.instance()
        bridge.registration_state_changed.connect(
            self._on_registration_state_changed, Qt.ConnectionType.QueuedConnection
        )
        bridge.call_state_changed.connect(
            self._on_call_state_changed, Qt.ConnectionType.QueuedConnection
        )
        bridge.incoming_call.connect(
            self._on_incoming_call, Qt.ConnectionType.QueuedConnection
        )

        # Ensure engine is initialized if we have a registered provider
        self._check_initial_state()

    def _check_initial_state(self) -> None:
        """Check initial SIP state and initialize engine if needed."""
        active_provider = self._service.active_provider
        if active_provider:
            self._update_account_info(active_provider.get_config())
            if not self._service.engine:
                # Auto-initialize engine if we have an active provider with credentials
                config = active_provider.get_config()
                if config.password:
                    self._service.initialize_engine()
        self._update_registration_status(self._service.registration_state, "")

    def _update_account_info(self, config: SipProviderConfig) -> None:
        """Update displayed account information."""
        self.account_name_label.setText(config.name)
        self.account_reg_label.setText("Registered" if self._service.registration_state == RegistrationState.REGISTERED else "Not Registered")
        self.account_uri_label.setText(f"{config.username}@{config.domain}")
        self.provider_name_label.setText(config.name)
        self.server_label.setText(f"{config.registrar_host}:{config.registrar_port}")
        self.transport_label.setText(config.transport)

    def _update_registration_status(self, state: RegistrationState, reason: str) -> None:
        """Update registration status display."""
        colors = {
            RegistrationState.INITIALIZING: "#ff9800",
            RegistrationState.CONNECTING: "#ff9800",
            RegistrationState.REGISTERING: "#2196f3",
            RegistrationState.REGISTERED: "#4caf50",
            RegistrationState.REGISTRATION_FAILED: "#f44336",
            RegistrationState.DISCONNECTED: "#9e9e9e",
            RegistrationState.ERROR: "#f44336",
        }

        labels = {
            RegistrationState.INITIALIZING: "Initializing...",
            RegistrationState.CONNECTING: "Connecting...",
            RegistrationState.REGISTERING: "Registering...",
            RegistrationState.REGISTERED: "Registered",
            RegistrationState.REGISTRATION_FAILED: "Registration Failed",
            RegistrationState.DISCONNECTED: "Disconnected",
            RegistrationState.ERROR: "Error",
        }

        color = colors.get(state, "#9e9e9e")
        label = labels.get(state, state.value)

        # Update left panel indicators
        self.account_indicator.set_color(color)
        self.account_reg_label.setText(label)
        self.account_reg_label.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 500; background: transparent; border: none;")
        
        self.reg_status_indicator.set_color(color)
        self.reg_status_label.setText(label)
        
        # Update call status indicator
        if state == RegistrationState.REGISTERED:
            self.call_status_indicator.set_color("#4caf50")
            self.call_status_label.setText("Idle")
        else:
            self.call_status_indicator.set_color("#9e9e9e")
            self.call_status_label.setText("Offline")

        # Update bottom status bar
        if hasattr(self, 'status_reg_indicator'):
            self.status_reg_indicator.set_color(color)
            self.status_reg_label.setText(f"{label} ({self._service.active_provider.get_config().name if self._service.active_provider else 'Jio Fiber'})")
            self.status_message_label.setText(label if state != RegistrationState.REGISTERED else "Ready")

        if reason and state in (RegistrationState.REGISTRATION_FAILED, RegistrationState.ERROR):
            self.reg_status_label.setToolTip(reason)

    @Slot(object, str)
    def _on_registration_state_changed(self, state: object, reason: str) -> None:
        """Handle registration state changes from SIP engine."""
        self._update_registration_status(state, reason)
        
        # Update account info if newly registered
        if state == RegistrationState.REGISTERED:
            provider = self._service.active_provider
            if provider:
                self._update_account_info(provider.get_config())

    @Slot(int, object, str)
    def _on_call_state_changed(self, call_id: int, state: object, reason: str) -> None:
        """Handle call state changes from SIP engine."""
        self._current_call_id = call_id
        self._update_call_ui(state, reason)

    @Slot(int, str)
    def _on_incoming_call(self, call_id: int, remote_uri: str) -> None:
        """Handle incoming call from SIP engine."""
        self._show_incoming_call_dialog(call_id, remote_uri)

    def _update_call_ui(self, state: CallState, reason: str) -> None:
        """Update call UI based on call state."""
        state_labels = {
            CallState.IDLE: "Idle",
            CallState.CALLING: "Calling...",
            CallState.RINGING: "Ringing...",
            CallState.CONNECTING: "Connecting...",
            CallState.CONNECTED: "Connected",
            CallState.DISCONNECTING: "Disconnecting...",
            CallState.DISCONNECTED: "Call Ended",
            CallState.FAILED: "Call Failed",
        }

        # Update call status in left panel ONLY
        if state == CallState.IDLE:
            self.call_status_indicator.set_color("#4caf50" if self._service.registration_state == RegistrationState.REGISTERED else "#9e9e9e")
            self.call_status_label.setText("Idle" if self._service.registration_state == RegistrationState.REGISTERED else "Offline")
        elif state in (CallState.CALLING, CallState.RINGING, CallState.CONNECTING):
            self.call_status_indicator.set_color("#2196f3")
            self.call_status_label.setText(state_labels.get(state, state.value))
        elif state == CallState.CONNECTED:
            self.call_status_indicator.set_color("#4caf50")
            self.call_status_label.setText("Connected")
        elif state == CallState.DISCONNECTING:
            self.call_status_indicator.set_color("#ff9800")
            self.call_status_label.setText("Disconnecting...")
        elif state == CallState.DISCONNECTED:
            self.call_status_indicator.set_color("#9e9e9e")
            self.call_status_label.setText("Idle")
        elif state == CallState.FAILED:
            self.call_status_indicator.set_color("#9e9e9e")
            self.call_status_label.setText("Idle")

        # Update bottom status bar
        if hasattr(self, 'status_message_label'):
            if state == CallState.IDLE:
                self.status_message_label.setText("Ready")
            elif state == CallState.CALLING:
                self.status_message_label.setText(f"Calling {reason}...")
            elif state == CallState.RINGING:
                self.status_message_label.setText(f"Ringing {reason}...")
            elif state == CallState.CONNECTING:
                self.status_message_label.setText(f"Connecting {reason}...")
            elif state == CallState.CONNECTED:
                self.status_message_label.setText(f"Connected to {reason}")
            elif state == CallState.DISCONNECTING:
                self.status_message_label.setText("Disconnecting...")
            elif state == CallState.DISCONNECTED:
                self.status_message_label.setText("Call Ended")
            elif state == CallState.FAILED:
                self.status_message_label.setText(f"Call Failed: {reason}")

        # Manage button states and call duration
        if state == CallState.IDLE:
            self.call_button.setEnabled(True)
            self.hangup_button.setEnabled(False)
            self.number_input.setEnabled(True)
            self.active_call_frame.setVisible(False)
            self._call_duration_timer.stop()
            self._call_start_time = QTime(0, 0)
            self.call_duration_label.setText("00:00")
            self._mic_muted = False
            self.mic_button.setText("🎤 MIC ON")
            self.mic_button.setStyleSheet("""
                QPushButton {
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    border: 1px solid #a5d6a7;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 0 20px;
                }
                QPushButton:hover {
                    background-color: #c8e6c9;
                    border-color: #81c784;
                }
                QPushButton:pressed {
                    background-color: #a5d6a7;
                }
            """)
        elif state in (CallState.CALLING, CallState.RINGING, CallState.CONNECTING):
            self.call_button.setEnabled(False)
            self.hangup_button.setEnabled(True)
            self.number_input.setEnabled(False)
            self.active_call_frame.setVisible(False)
        elif state == CallState.CONNECTED:
            self.call_button.setEnabled(False)
            self.hangup_button.setEnabled(True)
            self.number_input.setEnabled(False)
            self.active_call_frame.setVisible(True)
            self._call_start_time = QTime.currentTime()
            self._call_duration_timer.start()
        elif state == CallState.DISCONNECTING:
            self.call_button.setEnabled(False)
            self.hangup_button.setEnabled(False)
            self.number_input.setEnabled(False)
            self.active_call_frame.setVisible(True)
        elif state == CallState.DISCONNECTED:
            self.call_button.setEnabled(True)
            self.hangup_button.setEnabled(False)
            self.number_input.setEnabled(True)
            self.active_call_frame.setVisible(False)
            self._call_duration_timer.stop()
            self._call_start_time = QTime(0, 0)
            self.call_duration_label.setText("00:00")
        elif state == CallState.FAILED:
            self.call_button.setEnabled(True)
            self.hangup_button.setEnabled(False)
            self.number_input.setEnabled(True)
            self.active_call_frame.setVisible(False)
            self._call_duration_timer.stop()
            if state == CallState.FAILED:
                QMessageBox.warning(self, "Call Failed", reason or "Call failed")

    def _update_call_duration(self) -> None:
        """Update call duration display."""
        elapsed = self._call_start_time.secsTo(QTime.currentTime())
        minutes = elapsed // 60
        seconds = elapsed % 60
        self.call_duration_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_mic_toggle(self) -> None:
        """Handle microphone mute/unmute toggle."""
        self._mic_muted = not self._mic_muted
        if self._mic_muted:
            self.mic_button.setText("🎤 MIC OFF")
            self.mic_button.setStyleSheet("""
                QPushButton {
                    background-color: #fdeaea;
                    color: #c62828;
                    border: 1px solid #ef9a9a;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 0 20px;
                }
                QPushButton:hover {
                    background-color: #fcdada;
                    border-color: #e57373;
                }
                QPushButton:pressed {
                    background-color: #ef9a9a;
                }
            """)
        else:
            self.mic_button.setText("🎤 MIC ON")
            self.mic_button.setStyleSheet("""
                QPushButton {
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    border: 1px solid #a5d6a7;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 0 20px;
                }
                QPushButton:hover {
                    background-color: #c8e6c9;
                    border-color: #81c784;
                }
                QPushButton:pressed {
                    background-color: #a5d6a7;
                }
            """)
        # TODO: Connect to actual audio mute when media architecture supports it
        # For now, this is a UI-only toggle

    def _on_call_clicked(self) -> None:
        """Handle CALL button click."""
        number = self.number_input.text().strip()
        if not number:
            QMessageBox.warning(self, "Invalid Number", "Please enter a destination number.")
            return

        if not self._service.engine or not self._service.engine.is_registered:
            QMessageBox.warning(self, "Not Registered", "No registered SIP account. Please check SIP Accounts.")
            return

        # Make the call through SIP engine
        success = self._service.engine.make_call(number)
        if not success:
            QMessageBox.critical(self, "Call Failed", "Unable to start call.")

    def _on_hangup_clicked(self) -> None:
        """Handle HANG UP button click."""
        if self._current_call_id >= 0:
            success = self._service.engine.hangup_call(self._current_call_id)
            if success:
                self._update_call_ui(CallState.DISCONNECTED, "Call Ended")

    def _show_sip_accounts(self) -> None:
        """Show SIP Accounts management window."""
        if self._sip_accounts_window is None:
            self._sip_accounts_window = SipAccountsWindow()
            self._sip_accounts_window.destroyed.connect(self._on_sip_accounts_closed)
        self._sip_accounts_window.show()
        self._sip_accounts_window.raise_()
        self._sip_accounts_window.activateWindow()

    def _on_sip_accounts_closed(self) -> None:
        """Handle SIP Accounts window closed."""
        self._sip_accounts_window = None

    def _show_incoming_call_dialog(self, call_id: int, remote_uri: str) -> None:
        """Show incoming call dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
        from PySide6.QtCore import Qt
        
        if self._incoming_call_dialog:
            self._incoming_call_dialog.close()
        
        self._incoming_call_dialog = QDialog(self)
        self._incoming_call_dialog.setWindowTitle("Incoming Call")
        self._incoming_call_dialog.setModal(True)
        self._incoming_call_dialog.setMinimumWidth(350)
        apply_no_maximize_flags(self._incoming_call_dialog)
        self._incoming_call_dialog.setStyleSheet("""
            QDialog {
                background-color: #fafafa;
            }
        """)
        
        layout = QVBoxLayout(self._incoming_call_dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Incoming call label
        label = QLabel("Incoming Call")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 20px; font-weight: bold; color: #1a1a2e;")
        layout.addWidget(label)
        
        # Remote number
        number_label = QLabel(remote_uri)
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setStyleSheet("font-size: 18px; color: #3a3a4e;")
        layout.addWidget(number_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        
        answer_button = QPushButton("ANSWER")
        answer_button.setFixedHeight(56)
        answer_button.setCursor(Qt.CursorShape.PointingHandCursor)
        answer_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #43a047;
            }
            QPushButton:pressed {
                background-color: #388e3c;
            }
        """)
        answer_button.clicked.connect(lambda: self._answer_incoming_call(call_id))
        button_layout.addWidget(answer_button)
        
        reject_button = QPushButton("REJECT")
        reject_button.setFixedHeight(56)
        reject_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reject_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        reject_button.clicked.connect(lambda: self._reject_incoming_call(call_id))
        button_layout.addWidget(reject_button)
        
        layout.addLayout(button_layout)
        
        self._incoming_call_dialog.show()

    def _answer_incoming_call(self, call_id: int) -> None:
        """Answer incoming call."""
        if self._incoming_call_dialog:
            self._incoming_call_dialog.accept()
            self._incoming_call_dialog = None
        self._service.engine.answer_call(call_id)

    def _reject_incoming_call(self, call_id: int) -> None:
        """Reject incoming call."""
        if self._incoming_call_dialog:
            self._incoming_call_dialog.reject()
            self._incoming_call_dialog = None
        self._service.engine.reject_call(call_id)

    def _show_about(self) -> None:
        """Show about dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("About SysSIP")
        dialog.setModal(True)
        dialog.setFixedSize(480, 320)
        apply_no_maximize_flags(dialog)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #fafafa;
            }
        """)
        
        layout = QHBoxLayout(dialog)
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Left side - Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = load_logo_pixmap(large=True)
        if not logo_pixmap.isNull():
            # Scale proportionally to fit
            scaled_pixmap = logo_pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("SysSIP")
            logo_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #2d7ff9;")
        layout.addWidget(logo_label)
        
        # Right side - Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        title = QLabel("SysSIP")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #1a1a2e;")
        info_layout.addWidget(title)
        
        subtitle = QLabel("SIP / VoIP Client")
        subtitle.setStyleSheet("font-size: 14px; color: #2d7ff9; font-weight: 500;")
        info_layout.addWidget(subtitle)
        
        desc = QLabel(APP_DESCRIPTION)
        desc.setStyleSheet("font-size: 13px; color: #4a4a5e; line-height: 1.5;")
        desc.setWordWrap(True)
        info_layout.addWidget(desc)

        author = QLabel(f"Developed by: {APP_DEVELOPER}\nNumber: {APP_DEVELOPER_NUMBER}\nGIT: {APP_DEVELOPER_GIT}")
        author.setStyleSheet("font-size: 13px; color: #4a4a5e; line-height: 1.5;")
        author.setWordWrap(True)
        info_layout.addWidget(author)
        
        info_layout.addStretch()
        
        version = QLabel(f"Version {APP_VERSION}")
        version.setStyleSheet("font-size: 12px; color: #888;")
        version.setAlignment(Qt.AlignmentFlag.AlignRight)
        info_layout.addWidget(version)
        
        layout.addLayout(info_layout)
        
        # OK button
        ok_button = QPushButton("OK")
        ok_button.setFixedSize(80, 36)
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7ff9;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1a6de0;
            }
            QPushButton:pressed {
                background-color: #155ac8;
            }
        """)
        ok_button.clicked.connect(dialog.accept)
        
        # Add OK button at bottom right
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        info_layout.addLayout(button_layout)
        
        dialog.exec()

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Clean up any active call
        if self._current_call_id >= 0:
            self._service.engine.hangup_call(self._current_call_id)
        
        # Close SIP accounts window if open
        if self._sip_accounts_window:
            self._sip_accounts_window.close()
        
        # Close incoming call dialog if open
        if self._incoming_call_dialog:
            self._incoming_call_dialog.close()
        
        # Stop SIP engine
        self._service.stop()
        
        super().closeEvent(event)