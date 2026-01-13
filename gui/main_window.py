"""
Main window for Muxxy GUI application.
"""
from pathlib import Path
from typing import List, Optional, Dict
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFileDialog, QMessageBox, QProgressBar,
    QMenuBar, QMenu, QStatusBar, QToolBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QIcon

from core.config import MuxxyConfig
from core.engine import MuxingEngine
from modules.matcher import MatchResult
from gui.file_browser import FileBrowser
from gui.match_preview import MatchPreview
from gui.settings_dialog import SettingsDialog


class MuxWorker(QThread):
    """Worker thread for muxing operations."""
    
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(int, int)  # successes, failures
    error = pyqtSignal(str)
    
    def __init__(self, engine: MuxingEngine, matches: List[MatchResult], mux_options: dict):
        super().__init__()
        self.engine = engine
        self.matches = matches
        self.mux_options = mux_options
        self._cancelled = False
    
    def run(self):
        """Execute muxing in background thread."""
        try:
            successes, failures = self.engine.mux_batch(
                self.matches,
                progress_callback=self.progress.emit,
                **self.mux_options
            )
            self.finished.emit(successes, failures)
        except Exception as e:
            self.error.emit(str(e))
    
    def cancel(self):
        """Cancel the muxing operation."""
        self._cancelled = True
        self.engine.cancel()


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, config: MuxxyConfig):
        super().__init__()
        self.config = config
        self.engine = MuxingEngine(config=config)
        self.mux_worker = None
        self.current_matches: List[MatchResult] = []
        
        self.setWindowTitle("Muxxy - MKV Subtitle Muxer")
        self.resize(config.window_width, config.window_height)
        
        self._create_ui()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        
        # Connect signals
        self._connect_signals()
    
    def _create_ui(self):
        """Create the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Main splitter for three-panel layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Video files
        video_panel = QWidget()
        video_layout = QVBoxLayout(video_panel)
        video_layout.addWidget(QLabel("<b>Video Files</b>"))
        self.video_browser = FileBrowser(file_filter="*.mkv")
        video_layout.addWidget(self.video_browser)
        
        # Center panel: Subtitle files
        subtitle_panel = QWidget()
        subtitle_layout = QVBoxLayout(subtitle_panel)
        subtitle_layout.addWidget(QLabel("<b>Subtitle Files</b>"))
        self.subtitle_browser = FileBrowser(file_filter="*.ass *.srt *.ssa")
        subtitle_layout.addWidget(self.subtitle_browser)
        
        # Right panel: Match preview
        match_panel = QWidget()
        match_layout = QVBoxLayout(match_panel)
        match_layout.addWidget(QLabel("<b>Match Preview</b>"))
        self.match_preview = MatchPreview()
        match_layout.addWidget(self.match_preview)
        
        # Add panels to splitter
        splitter.addWidget(video_panel)
        splitter.addWidget(subtitle_panel)
        splitter.addWidget(match_panel)
        
        # Set initial sizes (30% video, 30% subtitle, 40% preview)
        splitter.setSizes([300, 300, 400])
        
        layout.addWidget(splitter)
        
        # Bottom control panel
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
    
    def _create_control_panel(self) -> QWidget:
        """Create the bottom control panel with action buttons."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        self.match_button = QPushButton("Match Files")
        self.match_button.setToolTip("Automatically match videos to subtitles")
        
        self.preview_button = QPushButton("Preview Output")
        self.preview_button.setToolTip("Preview output filenames")
        self.preview_button.setEnabled(False)
        
        self.mux_button = QPushButton("Start Muxing")
        self.mux_button.setToolTip("Begin muxing matched files")
        self.mux_button.setEnabled(False)
        self.mux_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setToolTip("Cancel ongoing operation")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        
        layout.addWidget(self.match_button)
        layout.addWidget(self.preview_button)
        layout.addStretch()
        layout.addWidget(self.mux_button)
        layout.addWidget(self.cancel_button)
        
        return panel
    
    def _create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open Directory...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        open_dir = QAction("Open Directory", self)
        open_dir.triggered.connect(self.open_directory)
        toolbar.addAction(open_dir)
        
        toolbar.addSeparator()
        
        match_files = QAction("Match Files", self)
        match_files.triggered.connect(self.match_files)
        toolbar.addAction(match_files)
    
    def _create_status_bar(self):
        """Create the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)
        
        self.statusbar.showMessage("Ready")
    
    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.match_button.clicked.connect(self.match_files)
        self.mux_button.clicked.connect(self.start_muxing)
        self.cancel_button.clicked.connect(self.cancel_muxing)
        
        # Connect browser signals
        self.video_browser.directory_changed.connect(self.on_directory_changed)
        
        # Connect match preview signals
        self.match_preview.match_changed.connect(self.on_match_changed)
    
    def open_directory(self):
        """Open a directory dialog and set it for both browsers."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            self.config.last_directory or str(Path.home())
        )
        
        if directory:
            self.video_browser.set_directory(directory)
            self.subtitle_browser.set_directory(directory)
            self.config.last_directory = directory
            self.config.save()
    
    def on_directory_changed(self, directory: str):
        """Handle directory change in browser."""
        # Sync both browsers
        self.subtitle_browser.set_directory(directory)
        self.statusbar.showMessage(f"Directory: {directory}")
    
    def match_files(self):
        """Automatically match video files to subtitles."""
        video_files = self.video_browser.get_selected_files()
        subtitle_files = self.subtitle_browser.get_all_files()  # All subtitles are candidates
        
        if not video_files:
            QMessageBox.warning(self, "No Videos", "Please select at least one video file.")
            return
        
        if not subtitle_files:
            QMessageBox.warning(self, "No Subtitles", "No subtitle files found in the directory.")
            return
        
        self.statusbar.showMessage("Matching files...")
        
        # Perform matching
        self.current_matches = self.engine.matcher.match_batch(
            video_files,
            subtitle_files,
            strict=self.config.strict_matching
        )
        
        # Update match preview
        self.match_preview.set_matches(self.current_matches, subtitle_files)
        
        # Enable buttons
        self.preview_button.setEnabled(True)
        self.mux_button.setEnabled(True)
        
        # Show summary
        matched = sum(1 for m in self.current_matches if m.subtitle_path is not None)
        self.statusbar.showMessage(
            f"Matched {matched} of {len(self.current_matches)} videos"
        )
    
    def on_match_changed(self, video_path: Path, subtitle_path: Optional[Path]):
        """Handle manual match changes from the preview panel."""
        # Update the match in current_matches
        for match in self.current_matches:
            if match.video_path == video_path:
                match.subtitle_path = subtitle_path
                match.match_type = 'manual'
                match.confidence = 1.0 if subtitle_path else 0.0
                match.reason = 'Manually set by user'
                break
    
    def start_muxing(self):
        """Start the muxing process."""
        if not self.current_matches:
            QMessageBox.warning(self, "No Matches", "Please match files first.")
            return
        
        # Filter matches with subtitles
        valid_matches = [m for m in self.current_matches if m.subtitle_path is not None]
        
        if not valid_matches:
            QMessageBox.warning(self, "No Valid Matches", 
                              "No videos have matched subtitles.")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Muxing",
            f"Mux {len(valid_matches)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Prepare mux options from config
        mux_options = {
            'subtitle_lang': self.config.subtitle_lang,
            'shift_frames': self.config.shift_frames,
            'no_resample': self.config.no_resample,
            'force_resample': self.config.force_resample,
            'video_track_name': self.config.video_track_name,
            'sub_track_name': self.config.sub_track_name,
            'release_tag': self.config.release_tag,
            'output_dir': Path(self.config.output_directory) if self.config.output_directory else None,
        }
        
        # Start worker thread
        self.mux_worker = MuxWorker(self.engine, valid_matches, mux_options)
        self.mux_worker.progress.connect(self.on_mux_progress)
        self.mux_worker.finished.connect(self.on_mux_finished)
        self.mux_worker.error.connect(self.on_mux_error)
        
        # Update UI
        self.match_button.setEnabled(False)
        self.mux_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(valid_matches))
        self.progress_bar.setValue(0)
        
        self.statusbar.showMessage("Muxing in progress...")
        self.mux_worker.start()
    
    def cancel_muxing(self):
        """Cancel the ongoing muxing operation."""
        if self.mux_worker and self.mux_worker.isRunning():
            self.mux_worker.cancel()
            self.statusbar.showMessage("Cancelling...")
    
    def on_mux_progress(self, current: int, total: int, filename: str):
        """Update progress bar during muxing."""
        self.progress_bar.setValue(current)
        self.statusbar.showMessage(f"Muxing ({current}/{total}): {filename}")
    
    def on_mux_finished(self, successes: int, failures: int):
        """Handle muxing completion."""
        self.progress_bar.setVisible(False)
        self.match_button.setEnabled(True)
        self.mux_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        
        # Show results
        message = f"Muxing complete!\n\nSuccessful: {successes}\nFailed: {failures}"
        QMessageBox.information(self, "Muxing Complete", message)
        
        self.statusbar.showMessage(f"Complete: {successes} succeeded, {failures} failed")
    
    def on_mux_error(self, error_msg: str):
        """Handle muxing errors."""
        self.progress_bar.setVisible(False)
        self.match_button.setEnabled(True)
        self.mux_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        
        QMessageBox.critical(self, "Muxing Error", f"An error occurred:\n{error_msg}")
        self.statusbar.showMessage("Error occurred")
    
    def show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Settings were saved
            self.statusbar.showMessage("Settings saved")
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Muxxy",
            "<h2>Muxxy</h2>"
            "<p>A tool for muxing subtitles, fonts, and attachments into MKV files.</p>"
            "<p>Version 2.0 - GUI Edition</p>"
            "<p>© 2026</p>"
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Save window size
        self.config.window_width = self.width()
        self.config.window_height = self.height()
        self.config.save()
        
        # Check if muxing is in progress
        if self.mux_worker and self.mux_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Muxing in Progress",
                "Muxing is still in progress. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.mux_worker.cancel()
                self.mux_worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
