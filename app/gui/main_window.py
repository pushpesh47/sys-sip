"""Main application window - SIP Accounts management."""

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMenu,
    QFrame,
    QSizePolicy,
)
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont

from app.config.settings import SipProviderConfig
from app.gui.otp_dialog import OtpDialog
from app.gui.add_provider_dialog import AddProviderDialog
from app.sip.service import get_service, SipApplicationService
from app.sip.engine import RegistrationState
from app.providers.base import ProvisioningResult, ProvisioningState
from app.gui.assets import load_app_icon, apply_no_maximize_flags


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


class ProviderListItem(QListWidgetItem):
    """List item for a SIP provider."""

    def __init__(self, config: SipProviderConfig, index: int, is_active: bool = False):
        super().__init__()
        self.config = config
        self.index = index
        self.is_active = is_active
        self._update_display()

    def _update_display(self) -> None:
        status = " ● Active" if self.is_active else ""
        self.setText(f"{self.config.name}{status}")
        self.setToolTip(
            f"Provider: {self.config.name}\n"
            f"Username: {self.config.username}\n"
            f"Domain: {self.config.domain}\n"
            f"Registrar: {self.config.registrar_host}:{self.config.registrar_port}"
        )

    def set_active(self, active: bool) -> None:
        self.is_active = active
        self._update_display()


class MainWindow(QMainWindow):
    """Main application window - SIP Accounts management."""

    registration_state_changed = Signal(RegistrationState, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SysSIP - SIP Accounts")
        self.setWindowIcon(load_app_icon())
        apply_no_maximize_flags(self)
        self.resize(500, 600)
        self._service: SipApplicationService = get_service()
        self._otp_dialog: OtpDialog | None = None
        self._setup_ui()
        self._connect_signals()
        self._refresh_provider_list()
        self._check_initial_state()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("SIP Accounts")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Provider list
        self.provider_list = QListWidget()
        self.provider_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.provider_list.customContextMenuRequested.connect(self._show_provider_menu)
        self.provider_list.currentRowChanged.connect(self._on_provider_selected)
        self.provider_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1a1a2e;
            }
            QListWidget::item:hover:!selected {
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.provider_list)

        # Status section
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_frame.setStyleSheet("background-color: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px;")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 16, 16, 16)

        # Current status
        self.status_layout = QHBoxLayout()
        self.status_indicator = StatusIndicator()
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        self.status_layout.addWidget(self.status_indicator)
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()
        status_layout.addLayout(self.status_layout)

        # Provider details
        self.details_label = QLabel("No provider selected")
        self.details_label.setStyleSheet("font-size: 12px; color: #666;")
        self.details_label.setWordWrap(True)
        status_layout.addWidget(self.details_label)

        layout.addWidget(status_frame)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.add_jio_button = QPushButton("Add Jio Fiber")
        self.add_jio_button.setFixedHeight(40)
        self.add_jio_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_jio_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7ff9;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
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
        self.add_jio_button.clicked.connect(self._on_add_jio_fiber)
        button_layout.addWidget(self.add_jio_button)

        self.add_generic_button = QPushButton("Add SIP Provider")
        self.add_generic_button.setFixedHeight(40)
        self.add_generic_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_generic_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #2d7ff9;
                border: 1.5px solid #2d7ff9;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover:enabled {
                background-color: #e8f0fe;
            }
            QPushButton:pressed:enabled {
                background-color: #d0e0fc;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #a8c8f0;
                border-color: #a8c8f0;
            }
        """)
        self.add_generic_button.clicked.connect(self._on_add_generic)
        button_layout.addWidget(self.add_generic_button)

        self.remove_button = QPushButton("Remove Account")
        self.remove_button.setFixedHeight(40)
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.setEnabled(False)
        self.remove_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #f44336;
                border: 1.5px solid #f44336;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover:enabled {
                background-color: #fdeaea;
            }
            QPushButton:pressed:enabled {
                background-color: #fcdada;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #ef9a9a;
                border-color: #ef9a9a;
            }
        """)
        self.remove_button.clicked.connect(self._on_remove_account)
        button_layout.addWidget(self.remove_button)

        button_layout.addStretch()

        self.connect_button = QPushButton("Connect")
        self.connect_button.setFixedHeight(40)
        self.connect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_button.setEnabled(False)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 24px;
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
        self.connect_button.clicked.connect(self._on_connect)
        button_layout.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setFixedHeight(40)
        self.disconnect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
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
        self.disconnect_button.clicked.connect(self._on_disconnect)
        button_layout.addWidget(self.disconnect_button)

        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        # Wrap callback to ensure it runs on Qt main thread
        self.registration_state_changed.connect(self._on_registration_state_changed)
        self._service.add_state_callback(self._on_registration_state_changed_threadsafe)

    def _check_initial_state(self) -> None:
        """Check if we need to provision on startup."""
        active_provider = self._service.active_provider
        if active_provider and active_provider.provider_name == "Jio Fiber":
            config = active_provider.get_config()
            if not config.password:
                # No credentials, start provisioning
                QTimer.singleShot(500, self._start_jio_provisioning)
            else:
                # Has credentials, initialize engine
                QTimer.singleShot(500, self._service.initialize_engine)

    def _refresh_provider_list(self) -> None:
        self.provider_list.clear()
        for i, provider in enumerate(self._service.settings.providers):
            is_active = (i == self._service.settings.active_provider_index)
            item = ProviderListItem(provider, i, is_active)
            self.provider_list.addItem(item)

        # Update button states
        has_active = self._service.active_provider is not None
        is_provisioning = self._service.is_provisioning
        
        self.add_jio_button.setEnabled(not is_provisioning)
        self.remove_button.setEnabled(has_active and not is_provisioning)
        self.connect_button.setEnabled(has_active and not self._service.engine and not is_provisioning)
        self.disconnect_button.setEnabled(has_active and self._service.engine is not None and not is_provisioning)

    def _on_provider_selected(self, index: int) -> None:
        if index >= 0:
            provider = self._service._providers.get(index)
            if provider:
                config = provider.get_config()
                self.details_label.setText(
                    f"Provider: {config.name}\n"
                    f"Username: {config.username}@{config.domain}\n"
                    f"Registrar: {config.registrar_host}:{config.registrar_port}\n"
                    f"Transport: {config.transport}"
                )
        else:
            self.details_label.setText("No provider selected")

    def _show_provider_menu(self, pos) -> None:
        item = self.provider_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        set_active_action = QAction("Set as Active", self)
        set_active_action.triggered.connect(lambda: self._service.set_active_provider(item.index))
        menu.addAction(set_active_action)

        if item.config.name == "Jio Fiber" and self._service.active_provider == self._service._providers.get(item.index):
            provision_action = QAction("Re-provision", self)
            provision_action.triggered.connect(lambda: self._start_reprovisioning(item.index))
            menu.addAction(provision_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._confirm_remove_account(item.index))
        menu.addAction(remove_action)

        menu.exec(self.provider_list.mapToGlobal(pos))

    def _on_add_jio_fiber(self) -> None:
        # Check if Jio Fiber already exists
        for i, provider in enumerate(self._service.settings.providers):
            if provider.name == "Jio Fiber":
                self.provider_list.setCurrentRow(i)
                return

        self._start_jio_provisioning()

    def _on_add_generic(self) -> None:
        dialog = AddProviderDialog(self, "generic")
        if dialog.exec() == AddProviderDialog.DialogCode.Accepted:
            config = dialog.get_config()
            if config:
                index = self._service.add_provider("generic", config)
                self._refresh_provider_list()
                self.provider_list.setCurrentRow(index)

    def _start_jio_provisioning(self) -> None:
        """Start Jio Fiber provisioning without adding to provider list yet."""
        index, result = self._service.start_jio_provisioning()

        if result.state == ProvisioningState.WAITING_OTP:
            phone = result.otp_sent_to or "your Jio number"
            self._otp_dialog = OtpDialog(self, phone)
            self._otp_dialog.otp_submitted.connect(self._on_otp_submitted)
            self._otp_dialog.cancelled.connect(self._on_otp_cancelled)
            self._otp_dialog.show()
            self._refresh_provider_list()  # Update button states (disable Add Jio Fiber during provisioning)
        elif result.success:
            # Should not happen on first attempt, but handle anyway
            self._service.commit_jio_provisioning(index, result)
            self._refresh_provider_list()
            QMessageBox.information(self, "Success", "Provisioning completed successfully!")
        else:
            # Failed to even start provisioning
            self._service.cancel_jio_provisioning()
            QMessageBox.critical(self, "Provisioning Failed", result.error or "Unknown error")

    def _start_reprovisioning(self, index: int) -> None:
        """Re-provision an existing Jio Fiber account."""
        provider = self._service._providers.get(index)
        if not provider or not provider.supports_provisioning:
            return

        # Stop engine if this is the active provider
        if index == self._service.settings.active_provider_index:
            self._service.stop()

        result = self._service.provision_provider(index)

        if result.state == ProvisioningState.WAITING_OTP:
            phone = result.otp_sent_to or "your Jio number"
            self._otp_dialog = OtpDialog(self, phone)
            self._otp_dialog.otp_submitted.connect(self._on_otp_submitted)
            self._otp_dialog.cancelled.connect(self._on_otp_cancelled)
            self._otp_dialog.show()
            self._refresh_provider_list()
        elif result.success:
            self._refresh_provider_list()
            QMessageBox.information(self, "Success", "Re-provisioning completed successfully!")
        else:
            QMessageBox.critical(self, "Re-provisioning Failed", result.error or "Unknown error")

    def _on_otp_submitted(self, otp: str) -> None:
        if self._otp_dialog:
            self._otp_dialog.set_verifying(True)
            self._otp_dialog.set_status("Verifying OTP...")

        self._service.submit_jio_otp(otp)

        # Poll for result
        self._poll_provisioning_result()

    def _on_otp_cancelled(self) -> None:
        self._service.cancel_jio_provisioning()
        self._refresh_provider_list()
        self._otp_dialog = None

    def _poll_provisioning_result(self) -> None:
        """Poll for provisioning result."""
        result = self._service.get_jio_provisioning_status()

        if result is None:
            # Still in progress, poll again
            QTimer.singleShot(1000, self._poll_provisioning_result)
            return

        if self._otp_dialog:
            if result.state == ProvisioningState.WAITING_OTP:
                # Still waiting for user to enter OTP (initial state or after invalid OTP)
                if result.requires_otp and result.error and "Invalid OTP" in result.error:
                    # Invalid OTP - show error and allow retry
                    self._otp_dialog.set_verifying(False)
                    self._otp_dialog.set_status(result.error, error=True)
                    self._otp_dialog.otp_input.clear()
                    self._otp_dialog.otp_input.setFocus()
                # else: still in initial "Waiting for OTP..." state, just keep polling
                QTimer.singleShot(1000, self._poll_provisioning_result)
            elif result.state == ProvisioningState.VERIFYING_OTP:
                # OTP submitted, verification in progress
                self._otp_dialog.set_verifying(True)
                self._otp_dialog.set_status("Verifying OTP...")
                QTimer.singleShot(1000, self._poll_provisioning_result)
            elif result.state == ProvisioningState.SUCCESS:
                self._otp_dialog.accept()
                self._otp_dialog = None
                
                # Commit the successful provisioning
                index = self._service._provisioning_index
                if self._service.commit_jio_provisioning(index, result):
                    self._refresh_provider_list()
                    QMessageBox.information(self, "Success", "Provisioning completed successfully!")
                else:
                    QMessageBox.critical(self, "Error", "Failed to save provisioning result")
            else:  # FAILED
                self._otp_dialog.set_verifying(False)
                self._otp_dialog.set_status(result.error or "Provisioning failed", error=True)

        self._refresh_provider_list()

    def _confirm_remove_account(self, index: int) -> None:
        provider = self._service._providers.get(index)
        if not provider:
            return

        config = provider.get_config()
        reply = QMessageBox.question(
            self,
            "Remove Account",
            f"Remove the {config.name} SIP account?\n\n"
            "This will remove the local credentials and de-authorize the device from the provider.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._remove_account(index)

    def _on_remove_account(self) -> None:
        index = self.provider_list.currentRow()
        if index >= 0:
            self._confirm_remove_account(index)

    def _remove_account(self, index: int) -> None:
        result = self._service.remove_account(index)
        if result.success:
            self._refresh_provider_list()
            QMessageBox.information(self, "Removed", "Account removed successfully.")
        else:
            QMessageBox.critical(self, "Error", result.error or "Failed to remove account.")

    def _on_connect(self) -> None:
        if self._service.start_registration():
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
        else:
            QMessageBox.critical(self, "Connection Failed", "Failed to start SIP engine.")

    def _on_disconnect(self) -> None:
        self._service.stop()
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self._update_status(RegistrationState.DISCONNECTED, "Disconnected")

    @Slot(RegistrationState, str)
    def _on_registration_state_changed(self, state: RegistrationState, reason: str) -> None:
        self._update_status(state, reason)

    def _on_registration_state_changed_threadsafe(self, state: RegistrationState, reason: str) -> None:
        self.registration_state_changed.emit(state, reason)

    def _update_status(self, state: RegistrationState, reason: str) -> None:
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

        self.status_indicator.set_color(colors.get(state, "#9e9e9e"))
        self.status_label.setText(labels.get(state, state.value))

        if reason and state in (RegistrationState.REGISTRATION_FAILED, RegistrationState.ERROR):
            self.status_label.setToolTip(reason)

        # Update button states
        if state == RegistrationState.REGISTERED:
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
        elif state in (RegistrationState.DISCONNECTED, RegistrationState.REGISTRATION_FAILED, RegistrationState.ERROR):
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self._otp_dialog:
            self._otp_dialog.close()
        super().closeEvent(event)