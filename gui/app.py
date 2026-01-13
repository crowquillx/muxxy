"""
GUI application entry point for Muxxy.
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from core.config import MuxxyConfig
from gui.main_window import MainWindow


def run_gui():
    """Run the Muxxy GUI application."""
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Muxxy")
    app.setOrganizationName("Muxxy")
    
    # Set application-wide style
    app.setStyle("Fusion")  # Modern cross-platform style
    
    # Load configuration
    config = MuxxyConfig.load()
    
    # Create and show main window
    try:
        window = MainWindow(config)
        window.show()
        
        # Run the application
        sys.exit(app.exec())
        
    except Exception as e:
        QMessageBox.critical(
            None,
            "Error",
            f"Failed to start Muxxy:\n{str(e)}"
        )
        sys.exit(1)


if __name__ == "__main__":
    run_gui()
