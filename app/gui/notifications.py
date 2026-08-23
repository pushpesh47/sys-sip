"""Notification system for user feedback."""

from enum import Enum
from typing import Optional
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QColor, QPainter, QFont


class NotificationType(Enum):
    """Notification types."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Notification(QObject):
    """A notification message."""
    
    def __init__(self, message: str, notification_type: NotificationType = NotificationType.INFO, 
                 duration: int = 5000, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.message = message
        self.type = notification_type
        self.duration = duration


class NotificationWidget(QWidget):
    """Widget for displaying a notification."""
    
    closed = Signal()
    
    def __init__(self, notification: Notification, parent=None):
        super().__init__(parent)
        self._notification = notification
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()
        
        # Auto-close timer
        if notification.duration > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.close)
            self._timer.start(notification.duration)
    
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Color based on type
        colors = {
            NotificationType.INFO: ("#2d7ff9", "#e8f0fe"),
            NotificationType.SUCCESS: ("#4caf50", "#e8f5e9"),
            NotificationType.WARNING: ("#ff9800", "#fff3e0"),
            NotificationType.ERROR: ("#f44336", "#ffebee"),
        }
        icon_color, bg_color = colors.get(self._notification.type, colors[NotificationType.INFO])
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {icon_color};
                border-radius: 8px;
            }}
        """)
        
        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icons = {
            NotificationType.INFO: "ℹ",
            NotificationType.SUCCESS: "✓",
            NotificationType.WARNING: "⚠",
            NotificationType.ERROR: "✕",
        }
        icon_label.setText(icons.get(self._notification.type, "ℹ"))
        icon_label.setStyleSheet(f"color: {icon_color}; font-size: 16px; font-weight: bold;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Message
        msg_label = QLabel(self._notification.message)
        msg_label.setStyleSheet(f"color: #1a1a2e; font-size: 13px;")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label, 1)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {icon_color};
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {icon_color};
                color: white;
            }}
        """)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
    
    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class NotificationManager(QObject):
    """Manages notifications display."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_widget = parent
        self._notifications = []
    
    def show(self, message: str, notification_type: NotificationType = NotificationType.INFO, 
             duration: int = 5000) -> NotificationWidget:
        """Show a notification."""
        notification = Notification(message, notification_type, duration)
        widget = NotificationWidget(notification, self._parent_widget)
        
        # Position at top-right of parent
        if self._parent_widget:
            parent_geo = self._parent_widget.geometry()
            widget.move(
                parent_geo.x() + parent_geo.width() - widget.width() - 20,
                parent_geo.y() + 20 + len(self._notifications) * (widget.height() + 10)
            )
        
        widget.closed.connect(lambda: self._on_closed(widget))
        widget.show()
        self._notifications.append(widget)
        return widget
    
    def _on_closed(self, widget: NotificationWidget) -> None:
        """Handle notification closed."""
        if widget in self._notifications:
            self._notifications.remove(widget)
        self._reposition()
    
    def _reposition(self) -> None:
        """Reposition remaining notifications."""
        if not self._parent_widget:
            return
        parent_geo = self._parent_widget.geometry()
        for i, widget in enumerate(self._notifications):
            widget.move(
                parent_geo.x() + parent_geo.width() - widget.width() - 20,
                parent_geo.y() + 20 + i * (widget.height() + 10)
            )
    
    def info(self, message: str, duration: int = 5000) -> NotificationWidget:
        return self.show(message, NotificationType.INFO, duration)
    
    def success(self, message: str, duration: int = 5000) -> NotificationWidget:
        return self.show(message, NotificationType.SUCCESS, duration)
    
    def warning(self, message: str, duration: int = 7000) -> NotificationWidget:
        return self.show(message, NotificationType.WARNING, duration)
    
    def error(self, message: str, duration: int = 10000) -> NotificationWidget:
        return self.show(message, NotificationType.ERROR, duration)


# Global notification manager
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager(parent=None) -> NotificationManager:
    """Get the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(parent)
    elif parent and _notification_manager._parent_widget is None:
        _notification_manager._parent_widget = parent
    return _notification_manager