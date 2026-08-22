"""Asset loading utilities for SysSIP application."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow, QDialog


def get_project_root() -> Path:
    """Find project root by looking for .env file or known structure."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".env").exists() or (current / "run.py").exists():
            return current
        current = current.parent
    # Fallback: assume we're in app/gui/ and project root is 3 levels up
    return Path(__file__).resolve().parent.parent.parent


def get_asset_path(asset_name: str) -> Path:
    """Get absolute path to an asset file."""
    project_root = get_project_root()
    return project_root / "app" / "assets" / asset_name


def load_app_icon() -> QIcon:
    """Load the application icon (sys-sip-small.png)."""
    icon_path = get_asset_path("logo/sys-sip-small.png")
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        # Verify icon has valid pixmaps
        if not icon.availableSizes():
            # Try loading as pixmap first to verify
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon = QIcon(pixmap)
        return icon
    return QIcon()


def load_logo_pixmap(large: bool = True) -> QPixmap:
    """Load the SysSIP logo pixmap.
    
    Args:
        large: If True, load sys-sip.png; if False, load sys-sip-small.png
    
    Returns:
        QPixmap of the logo, or empty pixmap if not found.
    """
    asset_name = "logo/sys-sip.png" if large else "logo/sys-sip-small.png"
    logo_path = get_asset_path(asset_name)
    if logo_path.exists():
        return QPixmap(str(logo_path))
    return QPixmap()


def get_window_flags_no_maximize() -> Qt.WindowType:
    """Get window flags for top-level windows without maximize button.
    
    Returns explicit flags preserving:
    - Window (top-level window)
    - WindowTitleHint (title bar)
    - WindowSystemMenuHint (system menu)
    - WindowMinimizeButtonHint (minimize button)
    - WindowCloseButtonHint (close button)
    
    While explicitly EXCLUDING:
    - WindowMaximizeButtonHint (maximize button)
    """
    return (
        Qt.WindowType.Window
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinimizeButtonHint
        | Qt.WindowType.WindowCloseButtonHint
    )


def apply_no_maximize_flags(window: QMainWindow | QDialog) -> None:
    """Apply no-maximize window flags to a top-level window or dialog.
    
    This uses explicit flag construction to ensure the maximize button
    is reliably removed on all platforms, particularly Linux.
    """
    window.setWindowFlags(get_window_flags_no_maximize())