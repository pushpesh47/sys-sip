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


class ProviderRowWidget(QWidget):
    """Widget representing a single SIP provider with its status and actions."""

    connect_clicked = Signal(int)
    disconnect_clicked = Signal(int)
    edit_clicked = Signal(int)
    remove_clicked = Signal(int)
    set_active_clicked = Signal(int)

    def __init__(self, config: SipProviderConfig, index: int, is_active: bool, registration_state: RegistrationState, parent=None):
        super().__init__(parent)
        self.config = config
        self.index = index
        self.is_active = is_active
        self.registration_state = registration_state
        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top row: status indicator, name, and registration status
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        # Status indicator (colored dot)
        self.status_indicator = StatusIndicator()
        top_layout.addWidget(self.status_indicator)

        # Provider name with active marker
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        top_layout.addWidget(self.name_label)

        # Registration status label
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        top_layout.addWidget(self.status_label)

        # Active badge
        self.active_badge = QLabel("Active")
        self.active_badge.setFixedHeight(20)
        self.active_badge.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                color: #1976d2;
                border-radius: 10px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        self.active_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_badge.setVisible(False)
        top_layout.addWidget(self.active_badge)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Bottom row: action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setFixedHeight(32)
        self.connect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
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
        self.connect_button.clicked.connect(lambda: self.connect_clicked.emit(self.index))
        button_layout.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setFixedHeight(32)
        self.disconnect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
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
        self.disconnect_button.clicked.connect(lambda: self.disconnect_clicked.emit(self.index))
        button_layout.addWidget(self.disconnect_button)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setFixedHeight(32)
        self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #2d7ff9;
                border: 1.5px solid #2d7ff9;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
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
        self.edit_button.clicked.connect(lambda: self.edit_clicked.emit(self.index))
        button_layout.addWidget(self.edit_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setFixedHeight(32)
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #f44336;
                border: 1.5px solid #f44336;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
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
        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self.index))
        button_layout.addWidget(self.remove_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _update_display(self) -> None:
        # Update name with active indicator
        name_text = self.config.name
        self.name_label.setText(name_text)

        # Update active badge
        self.active_badge.setVisible(self.is_active)

        # Update registration status
        status_colors = {
            RegistrationState.INITIALIZING: "#ff9800",
            RegistrationState.CONNECTING: "#ff9800",
            RegistrationState.REGISTERING: "#2196f3",
            RegistrationState.REGISTERED: "#4caf50",
            RegistrationState.REGISTRATION_FAILED: "#f44336",
            RegistrationState.DISCONNECTED: "#9e9e9e",
            RegistrationState.ERROR: "#f44336",
        }

        status_labels = {
            RegistrationState.INITIALIZING: "Initializing...",
            RegistrationState.CONNECTING: "Connecting...",
            RegistrationState.REGISTERING: "Registering...",
            RegistrationState.REGISTERED: "Registered",
            RegistrationState.REGISTRATION_FAILED: "Failed",
            RegistrationState.DISCONNECTED: "Disconnected",
            RegistrationState.ERROR: "Error",
        }

        color = status_colors.get(self.registration_state, "#9e9e9e")
        label = status_labels.get(self.registration_state, self.registration_state.value)

        self.status_indicator.set_color(color)
        self.status_label.setText(label)

        # Update button states based on registration state
        is_registered = self.registration_state == RegistrationState.REGISTERED
        is_connecting = self.registration_state in (RegistrationState.INITIALIZING, RegistrationState.CONNECTING, RegistrationState.REGISTERING)
        is_failed_or_disconnected = self.registration_state in (RegistrationState.DISCONNECTED, RegistrationState.REGISTRATION_FAILED, RegistrationState.ERROR)

        self.connect_button.setEnabled(is_failed_or_disconnected and not is_connecting)
        self.disconnect_button.setEnabled(is_registered)
        self.edit_button.setEnabled(not is_connecting)
        self.remove_button.setEnabled(not is_connecting)

    def update_state(self, is_active: bool, registration_state: RegistrationState) -> None:
        self.is_active = is_active
        self.registration_state = registration_state
        self._update_display()


class MainWindow(QMainWindow):
    """Main application window - SIP Accounts management."""

    registration_state_changed = Signal(RegistrationState, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SysSIP - SIP Accounts")
        self.setWindowIcon(load_app_icon())
        apply_no_maximize_flags(self)
        self.setFixedSize(550, 650)
        self._service: SipApplicationService = get_service()
        self._otp_dialog: OtpDialog | None = None
        self._provider_rows: dict[int, ProviderRowWidget] = {}
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

        # Header with add buttons
        header_layout = QHBoxLayout()
        title = QLabel("SIP Accounts")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.add_generic_button = QPushButton("+ Add SIP Provider")
        self.add_generic_button.setFixedHeight(36)
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
        header_layout.addWidget(self.add_generic_button)

        self.add_jio_button = QPushButton("+ Add Jio Fiber")
        self.add_jio_button.setFixedHeight(36)
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
        header_layout.addWidget(self.add_jio_button)

        layout.addLayout(header_layout)

        # Provider list (using custom widgets)
        self.provider_list = QListWidget()
        self.provider_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.provider_list.customContextMenuRequested.connect(self._show_provider_menu)
        self.provider_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 0px;
                border: none;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        layout.addWidget(self.provider_list, 1)

        # Status section (for active provider details)
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
        self.details_label = QLabel("Select a provider to see details")
        self.details_label.setStyleSheet("font-size: 12px; color: #666;")
        self.details_label.setWordWrap(True)
        status_layout.addWidget(self.details_label)

        layout.addWidget(status_frame)

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
        self._provider_rows.clear()

        for i, provider_config in enumerate(self._service.settings.providers):
            is_active = (i == self._service.settings.active_provider_index)
            
            # Get registration state for this provider
            reg_state = RegistrationState.DISCONNECTED
            if is_active and self._service.engine:
                reg_state = self._service.engine.registration_state
            
            row_widget = ProviderRowWidget(provider_config, i, is_active, reg_state)
            row_widget.connect_clicked.connect(self._on_connect_provider)
            row_widget.disconnect_clicked.connect(self._on_disconnect_provider)
            row_widget.edit_clicked.connect(self._on_edit_provider)
            row_widget.remove_clicked.connect(self._on_remove_provider)
            
            item = QListWidgetItem()
            item.setSizeHint(row_widget.sizeHint())
            self.provider_list.addItem(item)
            self.provider_list.setItemWidget(item, row_widget)
            self._provider_rows[i] = row_widget

        # Update header button states
        is_provisioning = self._service.is_provisioning
        self.add_generic_button.setEnabled(not is_provisioning)
        self.add_jio_button.setEnabled(not is_provisioning)

    def _on_provider_selected(self, index: int) -> None:
        if index >= 0:
            provider_config = self._service.settings.providers[index]
            self.details_label.setText(
                f"Provider: {provider_config.name}\n"
                f"Username: {provider_config.username}@{provider_config.domain}\n"
                f"Registrar: {provider_config.registrar_host}:{provider_config.registrar_port}\n"
                f"Transport: {provider_config.transport}"
            )
        else:
            self.details_label.setText("Select a provider to see details")

    def _show_provider_menu(self, pos) -> None:
        item = self.provider_list.itemAt(pos)
        if not item:
            return

        # Get the index from the row
        index = self.provider_list.row(item)
        if index < 0:
            return

        menu = QMenu(self)
        set_active_action = QAction("Set as Active", self)
        set_active_action.triggered.connect(lambda: self._service.set_active_provider(index))
        menu.addAction(set_active_action)

        if self._service.settings.providers[index].name == "Jio Fiber" and self._service.active_provider == self._service._providers.get(index):
            provision_action = QAction("Re-provision", self)
            provision_action.triggered.connect(lambda: self._start_reprovisioning(index))
            menu.addAction(provision_action)

        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self._on_edit_provider(index))
        menu.addAction(edit_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._on_remove_provider(index))
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

    def _remove_account(self, index: int) -> None:
        result = self._service.remove_account(index)
        if result.success:
            self._refresh_provider_list()
            QMessageBox.information(self, "Removed", "Account removed successfully.")
        else:
            QMessageBox.critical(self, "Error", result.error or "Failed to remove account.")

    def _on_connect_provider(self, index: int) -> None:
        """Connect a specific provider."""
        # Set as active provider first if not already
        if index != self._service.settings.active_provider_index:
            self._service.set_active_provider(index)
        
        # Start registration
        if self._service.start_registration():
            self._refresh_provider_list()
        else:
            QMessageBox.critical(self, "Connection Failed", "Failed to start SIP engine.")

    def _on_disconnect_provider(self, index: int) -> None:
        """Disconnect a specific provider."""
        if index == self._service.settings.active_provider_index:
            self._service.stop()
            self._refresh_provider_list()
            self._update_status(RegistrationState.DISCONNECTED, "Disconnected")

    def _on_edit_provider(self, index: int) -> None:
        """Edit a specific provider."""
        provider_config = self._service.settings.providers[index]
        
        # Check if it's the active provider and connected
        is_active = (index == self._service.settings.active_provider_index)
        was_connected = is_active and self._service.engine and self._service.engine.is_registered
        
        # If active and connected, disconnect first
        if was_connected:
            self._service.stop()
        
        # Open edit dialog
        dialog = AddProviderDialog(self, "generic")
        # Pre-fill with existing values
        dialog.name_input.setText(provider_config.name)
        dialog.username_input.setText(provider_config.username)
        dialog.password_input.setText(provider_config.password)
        dialog.domain_input.setText(provider_config.domain)
        dialog.registrar_host_input.setText(provider_config.registrar_host)
        dialog.registrar_port_input.setText(str(provider_config.registrar_port))
        dialog.proxy_host_input.setText(provider_config.proxy_host)
        dialog.proxy_port_input.setText(str(provider_config.proxy_port))
        dialog.transport_combo.setCurrentText(provider_config.transport)
        dialog.realm_input.setText(provider_config.realm)
        
        if dialog.exec() == AddProviderDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            if new_config:
                # Update the provider in settings
                self._service.settings.providers[index] = new_config
                self._service.settings._save_providers()
                
                # Update the provider object
                from app.providers import ProviderRegistry
                new_provider = ProviderRegistry.create_provider("generic", new_config)
                self._service._providers[index] = new_provider
                
                # Reinitialize engine if this was the active provider
                if is_active:
                    self._service.initialize_engine()
                
                self._refresh_provider_list()
                self.provider_list.setCurrentRow(index)

    def _on_remove_provider(self, index: int) -> None:
        """Remove a specific provider."""
        provider_config = self._service.settings.providers[index]
        
        reply = QMessageBox.question(
            self,
            "Remove Account",
            f"Remove the {provider_config.name} SIP account?\n\n"
            "This will remove the local credentials and de-authorize the device from the provider.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            result = self._service.remove_account(index)
            if result.success:
                self._refresh_provider_list()
                QMessageBox.information(self, "Removed", "Account removed successfully.")
            else:
                QMessageBox.critical(self, "Error", result.error or "Failed to remove account.")

    @Slot(RegistrationState, str)
    def _on_registration_state_changed(self, state: RegistrationState, reason: str) -> None:
        self._update_status(state, reason)
        # Update the active provider's row widget
        active_index = self._service.settings.active_provider_index
        if active_index in self._provider_rows:
            self._provider_rows[active_index].update_state(True, state)

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

    def closeEvent(self, event) -> None:
        if self._otp_dialog:
            self._otp_dialog.close()
        super().closeEvent(event)