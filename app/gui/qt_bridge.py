"""Qt Event Bridge - Thread-safe signal bridge for SIP engine callbacks."""

from enum import Enum
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot, Qt


class RegistrationState(Enum):
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    REGISTERING = "registering"
    REGISTERED = "registered"
    REGISTRATION_FAILED = "registration_failed"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class CallState(Enum):
    IDLE = "idle"
    CALLING = "calling"
    RINGING = "ringing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class QtEventBridge(QObject):
    """
    QObject-based signal bridge to marshal SIP engine callbacks to the Qt GUI thread.

    The SIP engine runs on a PJSUA2 event thread (non-GUI thread). This bridge
    allows the engine to emit signals that are delivered via Qt's event queue
    to slots running on the GUI thread.
    """

    registration_state_changed = Signal(RegistrationState, str)
    call_state_changed = Signal(int, CallState, str)
    incoming_call = Signal(int, str)

    _instance: Optional["QtEventBridge"] = None

    def __new__(cls) -> "QtEventBridge":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True

    @classmethod
    def instance(cls) -> "QtEventBridge":
        if cls._instance is None:
            cls._instance = QtEventBridge()
        return cls._instance