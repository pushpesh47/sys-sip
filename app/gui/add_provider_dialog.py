"""Dialog for adding a generic SIP provider."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QComboBox,
    QMessageBox,
    QLabel,
)

from app.config.settings import SipProviderConfig
from app.gui.assets import apply_no_maximize_flags


class AddProviderDialog(QDialog):
    """Dialog for adding a new SIP provider."""

    def __init__(self, parent=None, provider_type: str = "generic"):
        super().__init__(parent)
        self.setWindowTitle("Add SIP Provider")
        self.setModal(True)
        self.setFixedSize(450, 400)
        apply_no_maximize_flags(self)
        self._provider_type = provider_type
        self._config: Optional[SipProviderConfig] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("Add SIP Provider")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Form
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My SIP Provider")
        form_layout.addRow("Name:", self.name_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("username@domain.com")
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("SIP password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self.password_input)

        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("sip.example.com")
        form_layout.addRow("Domain:", self.domain_input)

        self.registrar_host_input = QLineEdit()
        self.registrar_host_input.setPlaceholderText("sip.example.com")
        form_layout.addRow("Registrar Host:", self.registrar_host_input)

        self.registrar_port_input = QLineEdit()
        self.registrar_port_input.setText("5060")
        form_layout.addRow("Registrar Port:", self.registrar_port_input)

        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("sip.example.com (optional)")
        form_layout.addRow("Proxy Host:", self.proxy_host_input)

        self.proxy_port_input = QLineEdit()
        self.proxy_port_input.setText("5060")
        form_layout.addRow("Proxy Port:", self.proxy_port_input)

        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["UDP", "TCP", "TLS"])
        self.transport_combo.setCurrentText("UDP")
        form_layout.addRow("Transport:", self.transport_combo)

        self.realm_input = QLineEdit()
        self.realm_input.setPlaceholderText("sip.example.com (optional)")
        form_layout.addRow("Realm:", self.realm_input)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Pre-fill for Jio Fiber if needed
        if self._provider_type == "jio_fiber":
            self.name_input.setText("Jio Fiber")
            self.name_input.setReadOnly(True)

    def _on_accept(self) -> None:
        name = self.name_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        domain = self.domain_input.text().strip()
        registrar_host = self.registrar_host_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing Information", "Please enter a provider name.")
            return

        if not username or not password or not domain or not registrar_host:
            QMessageBox.warning(
                self, "Missing Information",
                "Please fill in all required fields: Username, Password, Domain, Registrar Host."
            )
            return

        try:
            registrar_port = int(self.registrar_port_input.text().strip() or "5060")
            proxy_port = int(self.proxy_port_input.text().strip() or "5060")
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Ports must be valid numbers.")
            return

        self._config = SipProviderConfig(
            name=name,
            username=username,
            password=password,
            domain=domain,
            registrar_host=registrar_host,
            registrar_port=registrar_port,
            proxy_host=self.proxy_host_input.text().strip(),
            proxy_port=proxy_port,
            transport=self.transport_combo.currentText(),
            realm=self.realm_input.text().strip() or domain,
        )
        self.accept()

    def get_config(self) -> Optional[SipProviderConfig]:
        return self._config