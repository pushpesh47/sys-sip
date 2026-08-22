"""OTP input dialog for Jio Fiber provisioning."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QFrame,
)
from PySide6.QtGui import QFont, QIcon

from app.gui.assets import apply_no_maximize_flags


class OtpDialog(QDialog):
    """Dialog for entering OTP during Jio Fiber provisioning."""

    otp_submitted = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None, phone_number: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Jio Fiber SIP Setup")
        self.setModal(True)
        self.setMinimumWidth(420)
        apply_no_maximize_flags(self)
        self._phone_number = phone_number
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main content frame
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(28, 24, 28, 24)

        # Title section
        title = QLabel("Jio Fiber SIP Setup")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: 600;
                color: #1a1a2e;
            }
        """)
        content_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Verify your Jio Fiber account")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #5a5a6e;
            }
        """)
        content_layout.addWidget(subtitle)

        # Description
        if self._phone_number:
            masked_phone = self._mask_phone(self._phone_number)
            desc_text = f"A verification code has been sent to your registered Jio number ending in <b>{masked_phone}</b>."
        else:
            desc_text = "A verification code has been sent to your registered Jio number."
        desc = QLabel(desc_text)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setMinimumHeight(40)
        desc.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #4a4a5e;
                line-height: 1.5;
            }
        """)
        content_layout.addWidget(desc)

        # OTP input section
        otp_container = QFrame()
        otp_container.setStyleSheet("QFrame { background: transparent; }")
        otp_layout = QVBoxLayout(otp_container)
        otp_layout.setSpacing(12)
        otp_layout.setContentsMargins(0, 0, 0, 0)

        # OTP label
        otp_label = QLabel("Verification Code")
        otp_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 500;
                color: #3a3a4e;
            }
        """)
        otp_layout.addWidget(otp_label)

        # OTP input field
        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("Enter OTP")
        self.otp_input.setMaxLength(6)
        self.otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.otp_input.setFixedHeight(52)
        self.otp_input.setFont(QFont("Monospace", 24, QFont.Weight.Medium))
        self.otp_input.setStyleSheet("""
            QLineEdit {
                background-color: #fafafa;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 0 16px;
                color: #1a1a2e;
                letter-spacing: 2px;
            }
            QLineEdit:focus {
                border-color: #2d7ff9;
                background-color: #ffffff;
            }
            QLineEdit:disabled {
                background-color: #f5f5f5;
                color: #9a9aae;
            }
        """)
        self.otp_input.returnPressed.connect(self._on_verify)
        # Only allow digits
        self.otp_input.setInputMask("999999")
        otp_layout.addWidget(self.otp_input)

        content_layout.addWidget(otp_container)

        # Progress bar (indeterminate)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e8e8ee;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #2d7ff9;
                border-radius: 2px;
            }
        """)
        content_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Enter the verification code to continue")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #6a6a7e;
                min-height: 18px;
            }
        """)
        content_layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(40)
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5a5a6e;
                border: 1.5px solid #d0d0d8;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #b0b0bc;
            }
            QPushButton:pressed {
                background-color: #eaeaee;
            }
            QPushButton:disabled {
                color: #b0b0bc;
                border-color: #e0e0e8;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)

        self.verify_button = QPushButton("Verify OTP")
        self.verify_button.setFixedHeight(40)
        self.verify_button.setFixedWidth(130)
        self.verify_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_button.setDefault(True)
        self.verify_button.setEnabled(False)  # Disabled until valid input
        self.verify_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7ff9;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background-color: #1a6de0;
            }
            QPushButton:pressed:enabled {
                background-color: #155ac8;
            }
            QPushButton:disabled {
                background-color: #a8c8f0;
                color: #e0e8f8;
            }
        """)
        self.verify_button.clicked.connect(self._on_verify)
        button_layout.addWidget(self.verify_button)

        content_layout.addLayout(button_layout)

        layout.addWidget(content_frame)

        # Connect input change to validation
        self.otp_input.textChanged.connect(self._on_input_changed)

        # Focus OTP input on show
        self.otp_input.setFocus()

    def _mask_phone(self, phone: str) -> str:
        """Mask phone number showing only last 4 digits."""
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) >= 4:
            return digits[-4:]
        return digits

    def _on_input_changed(self, text: str) -> None:
        """Enable/disable verify button based on input length."""
        # Valid OTP is 4-6 digits
        is_valid = text.isdigit() and 4 <= len(text) <= 6
        self.verify_button.setEnabled(is_valid and not self.verify_button.property("verifying"))

    def _on_verify(self) -> None:
        otp = self.otp_input.text().strip()
        if not otp:
            self.set_status("Please enter the verification code", error=True)
            return

        if not otp.isdigit() or len(otp) < 4 or len(otp) > 6:
            self.set_status("Verification code must be 4-6 digits", error=True)
            return

        # Disable input and buttons during verification
        self.otp_input.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.verify_button.setProperty("verifying", True)
        self.progress_bar.setVisible(True)
        self.set_status("Verifying OTP...")

        self.otp_submitted.emit(otp)

    def _on_cancel(self) -> None:
        self.cancelled.emit()
        self.reject()

    def set_verifying(self, verifying: bool) -> None:
        """Set verifying state."""
        self.verify_button.setProperty("verifying", verifying)
        self.verify_button.setEnabled(not verifying and self._is_input_valid())
        self.cancel_button.setEnabled(not verifying)
        self.otp_input.setEnabled(not verifying)
        self.progress_bar.setVisible(verifying)

    def _is_input_valid(self) -> bool:
        text = self.otp_input.text().strip()
        return text.isdigit() and 4 <= len(text) <= 6

    def set_status(self, message: str, error: bool = False, info: bool = False) -> None:
        """Update status message."""
        self.status_label.setText(message)
        if error:
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #d32f2f;
                    min-height: 18px;
                }
            """)
        elif info:
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #2d7ff9;
                    min-height: 18px;
                }
            """)
        else:
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #6a6a7e;
                    min-height: 18px;
                }
            """)

    def closeEvent(self, event) -> None:
        self.cancelled.emit()
        super().closeEvent(event)