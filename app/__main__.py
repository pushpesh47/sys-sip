"""Main application entry point."""

import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.gui.dialer_window import DialerWindow
from app.gui.assets import load_app_icon


def main() -> int:
    """Application entry point."""
    # Add project root to path for imports
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("SysSIP")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SysSIP")
    app.setApplicationDisplayName("SysSIP - SIP/VoIP Dialer")
    app.setDesktopFileName("syssip")
    
    # Set application style
    app.setStyle("Fusion")

    # Set the application icon - this is inherited by windows
    app_icon = load_app_icon()
    # Debug: verify icon
    if not app_icon.isNull():
        sizes = app_icon.availableSizes()
        if sizes:
            print(f"App icon loaded successfully. Available sizes: {sizes}")
        else:
            print("Warning: App icon has no available sizes")
    else:
        print("Warning: App icon is null")
    app.setWindowIcon(app_icon)

    # Create and show main window
    window = DialerWindow()
    # Ensure main window has the icon explicitly set
    window.setWindowIcon(app_icon)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())