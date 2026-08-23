"""Dialer main window for voice calling - Phase 3 Enhanced."""

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
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTextEdit,
    QScrollArea,
    QToolButton,
)
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap, QPainter, QColor, QKeySequence

from app.config.settings import SipProviderConfig
from app.gui.main_window import MainWindow as SipAccountsWindow
from app.sip.service import get_service, SipApplicationService
from app.sip.engine import RegistrationState, CallState
from app.gui.assets import load_app_icon, load_logo_pixmap, apply_no_maximize_flags
from app.gui.qt_bridge import QtEventBridge
from app.gui import get_notification_manager, NotificationType
from app.data import get_data_store, CallRecord, Contact, CallDirection, CallStatus, PhoneSettings
from datetime import datetime


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
    """Main dialer window for voice calling - Phase 3 Enhanced."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SysSIP - SIP/VoIP Dialer")
        self.setWindowIcon(load_app_icon())
        apply_no_maximize_flags(self)
        self.resize(1000, 650)
        self._service: SipApplicationService = get_service()
        self._data_store = get_data_store()
        self._sip_accounts_window: SipAccountsWindow | None = None
        self._incoming_call_dialog = None
        self._call_history_dialog = None
        self._contacts_dialog = None
        self._settings_dialog = None
        self._call_duration_timer = QTimer()
        self._call_duration_timer.setInterval(1000)
        self._call_duration_timer.timeout.connect(self._update_call_duration)
        self._call_start_time = QTime(0, 0)
        self._current_call_id = -1
        self._mic_muted = False
        self._current_call_number = ""
        self._current_call_contact_name = ""
        self._notifications = get_notification_manager(self)
        
        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._check_initial_state()
        self._load_recent_calls()

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
        """Create the left account/SIP status panel with account selector."""
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

        # Account Selector
        selector_layout = QHBoxLayout()
        account_title = QLabel("Active Account")
        account_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a2e; background: transparent; border: none;")
        selector_layout.addWidget(account_title)
        selector_layout.addStretch()
        
        self.account_selector = QComboBox()
        self.account_selector.setFixedHeight(32)
        self.account_selector.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #2d7ff9;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                selection-background-color: #e3f2fd;
            }
        """)
        self.account_selector.currentIndexChanged.connect(self._on_account_selected)
        selector_layout.addWidget(self.account_selector)
        layout.addLayout(selector_layout)

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
        """Create the right dialer panel with recent calls and contacts access."""
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
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header with navigation buttons
        header_layout = QHBoxLayout()
        
        # DIALER heading
        dialer_title = QLabel("DIALER")
        dialer_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1a1a2e; letter-spacing: 1px; background: transparent; border: none;")
        header_layout.addWidget(dialer_title)
        
        header_layout.addStretch()
        
        # Navigation buttons
        self.recent_btn = QToolButton()
        self.recent_btn.setText("📞 Recent")
        self.recent_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.recent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recent_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #2d7ff9;
                border: 1px solid #2d7ff9;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QToolButton:hover {
                background-color: #e8f0fe;
            }
            QToolButton:pressed {
                background-color: #d0e0fc;
            }
        """)
        self.recent_btn.clicked.connect(self._show_call_history)
        header_layout.addWidget(self.recent_btn)
        
        self.contacts_btn = QToolButton()
        self.contacts_btn.setText("👥 Contacts")
        self.contacts_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.contacts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.contacts_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #2d7ff9;
                border: 1px solid #2d7ff9;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QToolButton:hover {
                background-color: #e8f0fe;
            }
            QToolButton:pressed {
                background-color: #d0e0fc;
            }
        """)
        self.contacts_btn.clicked.connect(self._show_contacts)
        header_layout.addWidget(self.contacts_btn)
        
        layout.addLayout(header_layout)

        # Destination Number input
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
        self.number_input.textChanged.connect(self._on_number_changed)
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

        # Call info (contact name + number)
        call_info_layout = QVBoxLayout()
        call_info_layout.setSpacing(4)
        
        self.active_call_name_label = QLabel("")
        self.active_call_name_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #1a1a2e;")
        self.active_call_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        call_info_layout.addWidget(self.active_call_name_label)
        
        self.active_call_number_label = QLabel("")
        self.active_call_number_label.setStyleSheet("font-size: 13px; color: #666; font-family: monospace;")
        self.active_call_number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        call_info_layout.addWidget(self.active_call_number_label)
        
        self.active_call_account_label = QLabel("")
        self.active_call_account_label.setStyleSheet("font-size: 11px; color: #999;")
        self.active_call_account_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        call_info_layout.addWidget(self.active_call_account_label)
        
        active_call_layout.addLayout(call_info_layout, 1)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #e0e0e0;")
        active_call_layout.addWidget(separator)

        # Call duration
        self.call_duration_label = QLabel("00:00")
        self.call_duration_label.setStyleSheet("font-size: 24px; font-weight: bold; font-family: monospace; color: #2d7ff9;")
        self.call_duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        active_call_layout.addWidget(self.call_duration_label, 1)

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        separator2.setStyleSheet("color: #e0e0e0;")
        active_call_layout.addWidget(separator2)

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

        # Recent calls quick access (initially hidden, shown when there are recent calls)
        self.recent_calls_frame = QFrame()
        self.recent_calls_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e8e8e8;
                border-radius: 8px;
            }
        """)
        self.recent_calls_frame.setVisible(False)
        recent_calls_layout = QVBoxLayout(self.recent_calls_frame)
        recent_calls_layout.setSpacing(8)
        recent_calls_layout.setContentsMargins(16, 12, 16, 12)
        
        recent_header = QHBoxLayout()
        recent_title = QLabel("Recent Calls")
        recent_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a1a2e;")
        recent_header.addWidget(recent_title)
        recent_header.addStretch()
        recent_calls_layout.addLayout(recent_header)
        
        self.recent_calls_list = QListWidget()
        self.recent_calls_list.setMaximumHeight(120)
        self.recent_calls_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.recent_calls_list.itemDoubleClicked.connect(self._on_recent_call_double_clicked)
        recent_calls_layout.addWidget(self.recent_calls_list)
        
        layout.addWidget(self.recent_calls_frame)
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

    def _on_number_changed(self, text: str) -> None:
        """Handle number input change - update recent calls filter if needed."""
        pass  # Could add auto-complete from contacts/history here

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
        
        call_history_action = QAction("Call History", self)
        call_history_action.setShortcut(QKeySequence("Ctrl+H"))
        call_history_action.triggered.connect(self._show_call_history)
        file_menu.addAction(call_history_action)
        
        contacts_action = QAction("Contacts", self)
        contacts_action.setShortcut(QKeySequence("Ctrl+T"))
        contacts_action.triggered.connect(self._show_contacts)
        file_menu.addAction(contacts_action)
        
        file_menu.addSeparator()
        
        settings_action = QAction("Settings", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
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
        self._update_account_selector()

    def _update_account_selector(self) -> None:
        """Update the account selector dropdown."""
        self.account_selector.blockSignals(True)
        self.account_selector.clear()
        
        for i, config in enumerate(self._service.settings.providers):
            self.account_selector.addItem(config.name, i)
            if i == self._service.settings.active_provider_index:
                self.account_selector.setCurrentIndex(self.account_selector.count() - 1)
        
        self.account_selector.blockSignals(False)

    def _on_account_selected(self, index: int) -> None:
        """Handle account selection change."""
        if index >= 0:
            provider_index = self.account_selector.itemData(index)
            if provider_index is not None:
                self._service.set_active_provider(provider_index)

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
            provider_name = self._service.active_provider.get_config().name if self._service.active_provider else 'Jio Fiber'
            self.status_reg_label.setText(f"{label} ({provider_name})")
            self.status_message_label.setText(label if state != RegistrationState.REGISTERED else "Ready")

        if reason and state in (RegistrationState.REGISTRATION_FAILED, RegistrationState.ERROR):
            self.reg_status_label.setToolTip(reason)
            
        self._update_account_selector()

    @Slot(object, str)
    def _on_registration_state_changed(self, state: object, reason: str) -> None:
        """Handle registration state changes from SIP engine."""
        prev_state = self._service.registration_state
        self._update_registration_status(state, reason)
        
        # Update account info if newly registered
        if state == RegistrationState.REGISTERED:
            provider = self._service.active_provider
            if provider:
                self._update_account_info(provider.get_config())
                if prev_state != RegistrationState.REGISTERED:
                    self._notifications.success(f"Registered with {provider.get_config().name}")
        elif state == RegistrationState.REGISTRATION_FAILED:
            if prev_state != RegistrationState.REGISTRATION_FAILED:
                self._notifications.error(f"Registration failed: {reason}")
        elif state == RegistrationState.DISCONNECTED:
            if prev_state == RegistrationState.REGISTERED:
                self._notifications.warning("Disconnected from SIP server")

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

        # Update call status in left panel
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
                self.status_message_label.setText("Idle")
            elif state == CallState.CALLING:
                self.status_message_label.setText(f"Calling {reason}...")
            elif state == CallState.RINGING:
                self.status_message_label.setText("Ringing...")
            elif state == CallState.CONNECTING:
                self.status_message_label.setText(f"Connecting {reason}...")
            elif state == CallState.CONNECTED:
                self.status_message_label.setText(f"Connected to {reason}")
            elif state == CallState.DISCONNECTING:
                self.status_message_label.setText("Disconnecting...")
            elif state == CallState.DISCONNECTED:
                self.status_message_label.setText("Idle")
            elif state == CallState.FAILED:
                self.status_message_label.setText("Idle")

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
            
            # Update active call info with contact resolution
            self._update_active_call_info()
            
            # Mark call as answered in history
            if hasattr(self, '_current_call_record_id') and self._current_call_record_id:
                record = self._data_store.find_call_record(self._current_call_record_id)
                if record and not record.answered_at:
                    record.answered_at = datetime.now()
                    self._data_store.update_call_record(record)
            
            self._notifications.success(f"Connected to {self._current_call_number}")
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
            
            # Finalize call record automatically based on answered state
            self._finalize_call_record_auto()
            self._notifications.info("Call ended")
        elif state == CallState.FAILED:
            if hasattr(self, '_incoming_call_dialog') and self._incoming_call_dialog:
                self._incoming_call_dialog.close()
                self._incoming_call_dialog = None
            self.call_button.setEnabled(True)
            self.hangup_button.setEnabled(False)
            self.number_input.setEnabled(True)
            self.active_call_frame.setVisible(False)
            self._call_duration_timer.stop()
            
            # Finalize call record
            self._finalize_call_record(CallStatus.FAILED)
            self._notifications.error(f"Call failed: {reason}")

    def _update_active_call_info(self) -> None:
        """Update the active call info display with contact name resolution."""
        # Get contact name for current call number
        contact = self._data_store.find_contact_by_number(self._current_call_number)
        if contact:
            self.active_call_name_label.setText(contact.name)
            self.active_call_number_label.setText(self._current_call_number)
        else:
            self.active_call_name_label.setText(self._current_call_number)
            self.active_call_number_label.setText("")
        
        # Show current SIP account
        provider = self._service.active_provider
        if provider:
            self.active_call_account_label.setText(f"Via: {provider.get_config().name}")
        else:
            self.active_call_account_label.setText("")

    def _update_call_duration(self) -> None:
        """Update call duration display."""
        elapsed = self._call_start_time.secsTo(QTime.currentTime())
        minutes = elapsed // 60
        seconds = elapsed % 60
        self.call_duration_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_mic_toggle(self) -> None:
        """Toggle microphone mute state."""
        if self._current_call_id < 0:
            return

        muted = not self._mic_muted

        if not self._service.engine.set_microphone_muted(self._current_call_id, muted):
            return

        self._mic_muted = muted

        if self._mic_muted:
            self.mic_button.setText("🔇 MIC OFF")
            self.mic_button.setStyleSheet("""
                QPushButton {
                    background-color: #ffebee;
                    color: #c62828;
                    border: 1px solid #ef9a9a;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 0 20px;
                }
                QPushButton:hover {
                    background-color: #ffcdd2;
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

    def _on_call_clicked(self) -> None:
        """Handle CALL button click."""
        number = self.number_input.text().strip()
        if not number:
            QMessageBox.warning(self, "Invalid Number", "Please enter a destination number.")
            return

        if not self._service.engine or not self._service.engine.is_registered:
            QMessageBox.warning(self, "Not Registered", "No registered SIP account. Please check SIP Accounts.")
            return

        # Store the number for call tracking
        self._current_call_number = number
        
        # Make the call through SIP engine
        success = self._service.engine.make_call(number)
        if not success:
            QMessageBox.critical(self, "Call Failed", "Unable to start call.")
            self._notifications.error("Call Failed", "Unable to start call. Check your connection.")
        else:
            # Create outgoing call record
            provider = self._service.active_provider
            account_name = provider.get_config().name if provider else "Unknown"
            
            record = CallRecord(
                number=number,
                direction=CallDirection.OUTGOING,
                status=CallStatus.CALLING,
                started_at=datetime.now(),
                sip_account=account_name,
            )
            self._data_store.add_call_record(record)
            self._current_call_record_id = record.id
            self._load_recent_calls()
            self._notifications.info(f"Calling {number}...")

    def _on_hangup_clicked(self) -> None:
        """Handle HANG UP button click."""
        if self._current_call_id >= 0:
            self._service.engine.hangup_call(self._current_call_id)
            # UI will be updated via the engine's call-state callback

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
        """Show incoming call dialog with contact resolution."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
        from datetime import datetime
        
        if self._incoming_call_dialog:
            self._incoming_call_dialog.close()
        
        # Resolve contact name
        contact = self._data_store.find_contact_by_number(remote_uri)
        display_name = contact.name if contact else remote_uri
        
        self._current_call_number = remote_uri
        self._current_call_contact_name = display_name
        
        # Create incoming call record (non‑blocking, best‑effort)
        try:
            provider = self._service.active_provider
            account_name = provider.get_config().name if provider else "Unknown"
            record = CallRecord(
                number=remote_uri,
                direction=CallDirection.INCOMING,
                status=CallStatus.CALLING,  # ringing
                started_at=datetime.now(),
                sip_account=account_name,
            )
            self._data_store.add_call_record(record)
            self._current_call_record_id = record.id
            self._load_recent_calls()
        except Exception:
            # If persistence fails we still want the UI to appear
            self._current_call_record_id = None
        
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
        
        # Contact name
        name_label = QLabel(display_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 22px; font-weight: 500; color: #1a1a2e;")
        layout.addWidget(name_label)
        
        # Number
        number_label = QLabel(remote_uri)
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setStyleSheet("font-size: 14px; color: #666; font-family: monospace;")
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
        
        # Update call record to answered
        self._update_call_record_on_answer()
        
        self._service.engine.answer_call(call_id)

    def _reject_incoming_call(self, call_id: int) -> None:
        """Reject incoming call."""
        if self._incoming_call_dialog:
            # Disable buttons immediately to prevent double-reject
            self._incoming_call_dialog.setEnabled(False)
            self._incoming_call_dialog.reject()
            self._incoming_call_dialog = None
        
        # Update call record to rejected
        self._update_call_record_on_reject()        
        self._service.engine.hangup_call(call_id)

    def _update_call_record_on_answer(self) -> None:
        """Update call record when call is answered."""
        # Find the most recent call record for this number
        history = self._data_store.get_call_history(limit=1)
        if history:
            record = history[0]
            if record.number == self._current_call_number and record.status == CallStatus.CALLING:
                record.status = CallStatus.ANSWERED
                record.answered_at = datetime.now()
                self._data_store.update_call_record(record)

    def _update_call_record_on_reject(self) -> None:
        """Update call record when call is rejected."""
        history = self._data_store.get_call_history(limit=1)
        if history:
            record = history[0]
            if record.number == self._current_call_number and record.status == CallStatus.CALLING:
                record.status = CallStatus.REJECTED
                record.ended_at = datetime.now()
                self._data_store.update_call_record(record)
                self._load_recent_calls()

    def _finalize_call_record(self, status: CallStatus) -> None:
        """Finalize call record when call ends with explicit status."""
        if hasattr(self, '_current_call_record_id') and self._current_call_record_id:
            record = self._data_store.find_call_record(self._current_call_record_id)
            if record:
                record.status = status
                record.ended_at = datetime.now()
                if record.answered_at:
                    record.duration = int((record.ended_at - record.answered_at).total_seconds())
                self._data_store.update_call_record(record)
                self._load_recent_calls()
                return
        # fallback to latest
        history = self._data_store.get_call_history(limit=1)
        if history:
            record = history[0]
            if record.number == self._current_call_number:
                record.status = status
                record.ended_at = datetime.now()
                if record.answered_at:
                    record.duration = int((record.ended_at - record.answered_at).total_seconds())
                self._data_store.update_call_record(record)
                self._load_recent_calls()

    def _finalize_call_record_auto(self) -> None:
        """Finalize call record inferring status from answered_at and direction."""
        if not hasattr(self, '_current_call_record_id') or not self._current_call_record_id:
            return
        record = self._data_store.find_call_record(self._current_call_record_id)
        if not record:
            return
        # Don't override explicit terminal statuses (e.g., REJECTED from user action)
        if record.status in (CallStatus.REJECTED, CallStatus.ANSWERED, CallStatus.FAILED, CallStatus.CANCELLED):
            return
        record.ended_at = datetime.now()
        if record.answered_at:
            record.status = CallStatus.ANSWERED
            record.duration = int((record.ended_at - record.answered_at).total_seconds())
        else:
            # Not answered
            if record.direction == CallDirection.INCOMING:
                record.status = CallStatus.MISSED
            else:
                record.status = CallStatus.CANCELLED
        self._data_store.update_call_record(record)
        self._load_recent_calls()

    def _load_recent_calls(self) -> None:
        """Load recent calls into the quick access list."""
        recent = self._data_store.get_recent_calls(limit=5)
        self.recent_calls_list.clear()
        
        if recent:
            self.recent_calls_frame.setVisible(True)
            for record in recent:
                item = QListWidgetItem()
                contact = self._data_store.find_contact_by_number(record.number)
                display_name = contact.name if contact else record.number
                
                direction_icon = "📤" if record.direction == CallDirection.OUTGOING else "📥"
                status_icon = ""
                if record.status == CallStatus.ANSWERED:
                    status_icon = "✓"
                elif record.status == CallStatus.MISSED:
                    status_icon = "⚠"
                elif record.status == CallStatus.REJECTED:
                    status_icon = "✗"
                elif record.status == CallStatus.FAILED:
                    status_icon = "✗"
                
                time_str = record.started_at.strftime("%H:%M")
                date_str = record.started_at.strftime("%b %d")
                if record.started_at.date() == datetime.now().date():
                    date_str = "Today"
                elif record.started_at.date() == (datetime.now().date() - __import__('datetime').timedelta(days=1)):
                    date_str = "Yesterday"
                
                duration_str = f" · {record.formatted_duration}" if record.is_answered else ""
                
                item.setText(f"{direction_icon} {display_name}\n   {record.direction.value.capitalize()} · {date_str} {time_str}{duration_str}")
                item.setData(Qt.ItemDataRole.UserRole, record.id)
                self.recent_calls_list.addItem(item)
        else:
            self.recent_calls_frame.setVisible(False)

    def _on_recent_call_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on recent call - redial."""
        record_id = item.data(Qt.ItemDataRole.UserRole)
        record = self._data_store.find_call_record(record_id)
        if record:
            self.number_input.setText(record.number)
            self._on_call_clicked()

    def _show_call_history(self) -> None:
        """Show call history dialog."""
        if self._call_history_dialog is None:
            self._call_history_dialog = CallHistoryDialog(self, self._data_store)
            self._call_history_dialog.destroyed.connect(self._on_call_history_closed)
            self._call_history_dialog.call_selected.connect(self._on_history_call_selected)
        self._call_history_dialog.refresh()
        self._call_history_dialog.show()
        self._call_history_dialog.raise_()
        self._call_history_dialog.activateWindow()

    def _on_call_history_closed(self) -> None:
        """Handle call history dialog closed."""
        self._call_history_dialog = None

    def _on_history_call_selected(self, record: CallRecord) -> None:
        """Handle call selected from history."""
        self.number_input.setText(record.number)
        self._on_call_clicked()

    def _show_contacts(self) -> None:
        """Show contacts dialog."""
        if self._contacts_dialog is None:
            self._contacts_dialog = ContactsDialog(self, self._data_store)
            self._contacts_dialog.destroyed.connect(self._on_contacts_closed)
            self._contacts_dialog.contact_selected.connect(self._on_contact_selected)
        self._contacts_dialog.refresh()
        self._contacts_dialog.show()
        self._contacts_dialog.raise_()
        self._contacts_dialog.activateWindow()

    def _on_contacts_closed(self) -> None:
        """Handle contacts dialog closed."""
        self._contacts_dialog = None

    def _on_contact_selected(self, contact: Contact) -> None:
        """Handle contact selected."""
        self.number_input.setText(contact.number)
        self._on_call_clicked()

    def _show_settings(self) -> None:
        """Show settings dialog."""
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self, self._data_store, self._service)
            self._settings_dialog.destroyed.connect(self._on_settings_closed)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _on_settings_closed(self) -> None:
        """Handle settings dialog closed."""
        self._settings_dialog = None

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


class CallHistoryDialog(QDialog):
    """Call history dialog."""
    
    call_selected = Signal(CallRecord)
    
    def __init__(self, parent, data_store):
        super().__init__(parent)
        self._data_store = data_store
        self.setWindowTitle("Call History")
        self.setModal(True)
        self.resize(600, 500)
        apply_no_maximize_flags(self)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Call History")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1a1a2e;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        clear_btn = QPushButton("Clear History")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
        """)
        clear_btn.clicked.connect(self._clear_history)
        header_layout.addWidget(clear_btn)
        
        layout.addLayout(header_layout)
        
        # Call history list
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.history_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.history_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def refresh(self) -> None:
        """Refresh the call history list."""
        self.history_list.clear()
        records = self._data_store.get_call_history()
        
        for record in records:
            item = QListWidgetItem()
            contact = self._data_store.find_contact_by_number(record.number)
            display_name = contact.name if contact else record.number
            
            direction_icon = "📤" if record.direction == CallDirection.OUTGOING else "📥"
            status_text = record.status.value.capitalize()
            
            if record.status == CallStatus.ANSWERED:
                status_color = "#4caf50"
            elif record.status == CallStatus.MISSED:
                status_color = "#ff9800"
            elif record.status in (CallStatus.REJECTED, CallStatus.FAILED):
                status_color = "#f44336"
            else:
                status_color = "#9e9e9e"
            
            time_str = record.started_at.strftime("%H:%M:%S")
            date_str = record.started_at.strftime("%b %d, %Y")
            if record.started_at.date() == datetime.now().date():
                date_str = "Today"
            elif record.started_at.date() == (datetime.now().date() - __import__('datetime').timedelta(days=1)):
                date_str = "Yesterday"
            
            duration_str = f" · Duration: {record.formatted_duration}" if record.is_answered else ""
            
            item.setText(f"{direction_icon} {display_name}\n   {record.number} · {date_str} {time_str} · {status_text}{duration_str} · Via: {record.sip_account}")
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            self.history_list.addItem(item)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on history item."""
        record_id = item.data(Qt.ItemDataRole.UserRole)
        record = self._data_store.find_call_record(record_id)
        if record:
            self.call_selected.emit(record)
            self.accept()
    
    def _clear_history(self) -> None:
        """Clear call history."""
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all call history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._data_store.clear_call_history()
            self.refresh()
            # Also refresh main window recent calls
            parent = self.parent()
            if hasattr(parent, '_load_recent_calls'):
                parent._load_recent_calls()


class ContactsDialog(QDialog):
    """Contacts management dialog."""
    
    contact_selected = Signal(Contact)
    
    def __init__(self, parent, data_store):
        super().__init__(parent)
        self._data_store = data_store
        self.setWindowTitle("Contacts")
        self.setModal(True)
        self.resize(500, 600)
        apply_no_maximize_flags(self)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header with search
        header_layout = QHBoxLayout()
        title = QLabel("Contacts")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1a1a2e;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search contacts...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #2d7ff9;
            }
        """)
        self.search_input.textChanged.connect(self._on_search)
        header_layout.addWidget(self.search_input)
        
        add_btn = QPushButton("Add Contact")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d7ff9;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1a6de0;
            }
        """)
        add_btn.clicked.connect(self._add_contact)
        header_layout.addWidget(add_btn)
        
        layout.addLayout(header_layout)
        
        # Contacts list
        self.contacts_list = QListWidget()
        self.contacts_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.contacts_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.contacts_list.customContextMenuRequested.connect(self._show_context_menu)
        self.contacts_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.contacts_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def refresh(self) -> None:
        """Refresh the contacts list."""
        self.contacts_list.clear()
        contacts = self._data_store.get_contacts()
        
        query = self.search_input.text().strip().lower() if hasattr(self, 'search_input') else ""
        
        for contact in contacts:
            if query and query not in contact.name.lower() and query not in contact.number.lower():
                continue
            
            item = QListWidgetItem()
            item.setText(f"{contact.name}\n   {contact.number}")
            item.setData(Qt.ItemDataRole.UserRole, contact.id)
            self.contacts_list.addItem(item)
    
    def _on_search(self, text: str) -> None:
        """Handle search text change."""
        self.refresh()
    
    def _add_contact(self) -> None:
        """Add a new contact."""
        dialog = ContactEditDialog(self, self._data_store)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            contact = dialog.get_contact()
            if contact:
                self._data_store.add_contact(contact)
                self.refresh()
                # Also refresh main window
                parent = self.parent()
                if hasattr(parent, '_load_recent_calls'):
                    parent._load_recent_calls()
    
    def _show_context_menu(self, pos) -> None:
        """Show context menu for contact item."""
        item = self.contacts_list.itemAt(pos)
        if not item:
            return
        
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self._edit_contact(item))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_contact(item))
        
        call_action = menu.addAction("Call")
        call_action.triggered.connect(lambda: self._call_contact(item))
        
        menu.exec(self.contacts_list.mapToGlobal(pos))
    
    def _edit_contact(self, item: QListWidgetItem) -> None:
        """Edit a contact."""
        contact_id = item.data(Qt.ItemDataRole.UserRole)
        contact = self._data_store.get_contact(contact_id)
        if contact:
            dialog = ContactEditDialog(self, self._data_store, contact)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated = dialog.get_contact()
                if updated:
                    self._data_store.update_contact(updated)
                    self.refresh()
    
    def _delete_contact(self, item: QListWidgetItem) -> None:
        """Delete a contact."""
        contact_id = item.data(Qt.ItemDataRole.UserRole)
        contact = self._data_store.get_contact(contact_id)
        if contact:
            reply = QMessageBox.question(
                self, "Delete Contact",
                f"Delete contact '{contact.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._data_store.delete_contact(contact_id)
                self.refresh()
    
    def _call_contact(self, item: QListWidgetItem) -> None:
        """Call a contact."""
        contact_id = item.data(Qt.ItemDataRole.UserRole)
        contact = self._data_store.get_contact(contact_id)
        if contact:
            self.contact_selected.emit(contact)
            self.accept()
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on contact."""
        self._call_contact(item)


class ContactEditDialog(QDialog):
    """Dialog for adding/editing a contact."""
    
    def __init__(self, parent, data_store, contact: Contact = None):
        super().__init__(parent)
        self._data_store = data_store
        self._contact = contact
        self._is_editing = contact is not None
        self.setWindowTitle("Edit Contact" if self._is_editing else "Add Contact")
        self.setModal(True)
        self.setFixedSize(400, 350)
        apply_no_maximize_flags(self)
        self._setup_ui()
        
        if self._is_editing:
            self._populate_fields()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Form
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Contact name")
        form_layout.addRow("Name:", self.name_input)
        
        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("Phone number or SIP URI")
        form_layout.addRow("Number:", self.number_input)
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Notes (optional)")
        self.notes_input.setMaximumHeight(80)
        form_layout.addRow("Notes:", self.notes_input)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _populate_fields(self) -> None:
        """Populate fields with existing contact data."""
        if self._contact:
            self.name_input.setText(self._contact.name)
            self.number_input.setText(self._contact.number)
            self.notes_input.setPlainText(self._contact.notes)
    
    def _on_accept(self) -> None:
        """Validate and accept."""
        name = self.name_input.text().strip()
        number = self.number_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Missing Information", "Please enter a contact name.")
            return
        
        if not number:
            QMessageBox.warning(self, "Missing Information", "Please enter a phone number or SIP URI.")
            return
        
        if self._is_editing:
            self._contact.name = name
            self._contact.number = number
            self._contact.notes = self.notes_input.toPlainText().strip()
        else:
            self._contact = Contact(
                name=name,
                number=number,
                notes=self.notes_input.toPlainText().strip(),
            )
        
        self.accept()
    
    def get_contact(self) -> Contact:
        """Get the contact."""
        return self._contact


class SettingsDialog(QDialog):
    """Settings dialog for phone application."""
    
    def __init__(self, parent, data_store, service):
        super().__init__(parent)
        self._data_store = data_store
        self._service = service
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedSize(500, 450)
        apply_no_maximize_flags(self)
        self._settings = data_store.get_settings()
        self._setup_ui()
        self._populate_fields()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1a1a2e;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
            }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # SIP Account section
        sip_group = self._create_section("SIP Account")
        sip_layout = QFormLayout()
        sip_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        sip_layout.setSpacing(12)
        
        self.default_account_combo = QComboBox()
        self.default_account_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #2d7ff9;
            }
        """)
        sip_layout.addRow("Default Account:", self.default_account_combo)
        sip_group.setLayout(sip_layout)
        content_layout.addWidget(sip_group)
        
        # Audio section
        audio_group = self._create_section("Audio")
        audio_layout = QFormLayout()
        audio_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        audio_layout.setSpacing(12)
        
        self.input_device_combo = QComboBox()
        self.input_device_combo.addItem("Default", "")
        self.input_device_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
        """)
        audio_layout.addRow("Input Device:", self.input_device_combo)
        
        self.output_device_combo = QComboBox()
        self.output_device_combo.addItem("Default", "")
        self.output_device_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
        """)
        audio_layout.addRow("Output Device:", self.output_device_combo)
        
        audio_group.setLayout(audio_layout)
        content_layout.addWidget(audio_group)
        
        # Dialer section
        dialer_group = self._create_section("Dialer")
        dialer_layout = QFormLayout()
        dialer_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        dialer_layout.setSpacing(12)
        
        self.show_duration_check = QPushButton()
        self.show_duration_check.setCheckable(True)
        self.show_duration_check.setText("Show call duration during calls")
        dialer_layout.addRow("", self.show_duration_check)
        
        dialer_group.setLayout(dialer_layout)
        content_layout.addWidget(dialer_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_section(self, title: str) -> QFrame:
        """Create a settings section frame."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a2e; margin-bottom: 8px;")
        layout.addWidget(title_label)
        
        return frame
    
    def _populate_fields(self) -> None:
        """Populate fields with current settings."""
        # Populate account combo
        self.default_account_combo.clear()
        self.default_account_combo.addItem("System Default (First Registered)", "")
        for i, provider in enumerate(self._service.settings.providers):
            self.default_account_combo.addItem(provider.get_config().name, str(i))
        
        # Set current default
        if self._settings.default_sip_account:
            for i in range(self.default_account_combo.count()):
                if self.default_account_combo.itemData(i) == self._settings.default_sip_account:
                    self.default_account_combo.setCurrentIndex(i)
                    break
        
        # Audio devices - placeholder for now
        # In Phase 4, we can enumerate actual audio devices
        
        # Dialer settings
        self.show_duration_check.setChecked(self._settings.show_call_duration)
    
    def _on_accept(self) -> None:
        """Save settings."""
        # Get selected default account
        account_data = self.default_account_combo.currentData()
        if account_data:
            self._settings.default_sip_account = account_data
        
        self._settings.show_call_duration = self.show_duration_check.isChecked()
        
        # Audio devices - save when implemented
        
        self._data_store.update_settings(self._settings)
        
        # Notify parent window
        parent = self.parent()
        if hasattr(parent, '_notifications'):
            parent._notifications.success("Settings saved")
        
        self.accept()