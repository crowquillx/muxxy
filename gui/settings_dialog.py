"""
Settings dialog for Muxxy configuration.
"""
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QPushButton, QCheckBox, QSpinBox, QDialogButtonBox,
    QFileDialog, QTabWidget, QWidget, QDoubleSpinBox
)
from PyQt6.QtCore import Qt

from core.config import MuxxyConfig


class SettingsDialog(QDialog):
    """Dialog for editing application settings."""
    
    def __init__(self, config: MuxxyConfig, parent=None):
        super().__init__(parent)
        
        self.config = config
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(600, 500)
        
        self._create_ui()
        self._load_settings()
    
    def _create_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        
        # Tab widget for different setting categories
        tabs = QTabWidget()
        
        # General settings tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Matching settings tab
        matching_tab = self._create_matching_tab()
        tabs.addTab(matching_tab, "Matching")
        
        # Processing settings tab
        processing_tab = self._create_processing_tab()
        tabs.addTab(processing_tab, "Processing")
        
        layout.addWidget(tabs)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Output settings group
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout()
        
        self.release_tag_edit = QLineEdit()
        output_layout.addRow("Release Tag:", self.release_tag_edit)
        
        # Output directory with browse button
        output_dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("(same as input)")
        output_dir_button = QPushButton("Browse...")
        output_dir_button.clicked.connect(self._browse_output_dir)
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(output_dir_button)
        output_layout.addRow("Output Directory:", output_dir_layout)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Track naming group
        track_group = QGroupBox("Track Naming")
        track_layout = QFormLayout()
        
        self.video_track_edit = QLineEdit()
        self.video_track_edit.setPlaceholderText("(auto-detect from filename)")
        track_layout.addRow("Video Track Name:", self.video_track_edit)
        
        self.sub_track_edit = QLineEdit()
        self.sub_track_edit.setPlaceholderText("(auto-detect from filename)")
        track_layout.addRow("Subtitle Track Name:", self.sub_track_edit)
        
        self.sub_lang_edit = QLineEdit()
        self.sub_lang_edit.setPlaceholderText("(auto-detect from filename)")
        track_layout.addRow("Subtitle Language:", self.sub_lang_edit)
        
        track_group.setLayout(track_layout)
        layout.addWidget(track_group)
        
        layout.addStretch()
        return widget
    
    def _create_matching_tab(self) -> QWidget:
        """Create the matching settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Matching options group
        matching_group = QGroupBox("Matching Options")
        matching_layout = QFormLayout()
        
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setSuffix(" (0-1)")
        matching_layout.addRow("Confidence Threshold:", self.confidence_spin)
        
        self.strict_check = QCheckBox("Only accept high-confidence matches")
        matching_layout.addRow("Strict Matching:", self.strict_check)
        
        matching_group.setLayout(matching_layout)
        layout.addWidget(matching_group)
        
        # Info group
        info_group = QGroupBox("About Matching")
        info_layout = QVBoxLayout(info_group)
        
        from PyQt6.QtWidgets import QLabel
        info_labels = [
            "The matcher uses episode/season numbers to find subtitle matches.",
            "Confidence threshold determines the minimum score for auto-matching.",
            "Lower values = more matches, but less accurate.",
            "Higher values = fewer matches, but more accurate.",
            "You can always manually override matches in the GUI."
        ]
        for text in info_labels:
            label = QLabel(text)
            label.setWordWrap(True)
            info_layout.addWidget(label)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        return widget
    
    def _create_processing_tab(self) -> QWidget:
        """Create the processing settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Subtitle processing group
        subtitle_group = QGroupBox("Subtitle Processing")
        subtitle_layout = QFormLayout()
        
        self.shift_frames_spin = QSpinBox()
        self.shift_frames_spin.setRange(-1000, 1000)
        self.shift_frames_spin.setSuffix(" frames")
        subtitle_layout.addRow("Shift Frames:", self.shift_frames_spin)
        
        self.no_resample_check = QCheckBox("Skip subtitle resampling")
        subtitle_layout.addRow("", self.no_resample_check)
        
        self.force_resample_check = QCheckBox("Force resample even if resolution matches")
        subtitle_layout.addRow("", self.force_resample_check)
        
        subtitle_group.setLayout(subtitle_layout)
        layout.addWidget(subtitle_group)
        
        layout.addStretch()
        return widget
    
    def _browse_output_dir(self):
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir_edit.text() or str(Path.home())
        )
        if directory:
            self.output_dir_edit.setText(directory)
    
    def _load_settings(self):
        """Load settings from config into UI."""
        self.release_tag_edit.setText(self.config.release_tag)
        self.output_dir_edit.setText(self.config.output_directory or "")
        self.video_track_edit.setText(self.config.video_track_name or "")
        self.sub_track_edit.setText(self.config.sub_track_name or "")
        self.sub_lang_edit.setText(self.config.subtitle_lang or "")
        
        self.confidence_spin.setValue(self.config.confidence_threshold)
        self.strict_check.setChecked(self.config.strict_matching)
        
        self.shift_frames_spin.setValue(self.config.shift_frames)
        self.no_resample_check.setChecked(self.config.no_resample)
        self.force_resample_check.setChecked(self.config.force_resample)
    
    def accept(self):
        """Save settings and close dialog."""
        # Update config
        self.config.release_tag = self.release_tag_edit.text() or "MySubs"
        self.config.output_directory = self.output_dir_edit.text() or None
        self.config.video_track_name = self.video_track_edit.text() or None
        self.config.sub_track_name = self.sub_track_edit.text() or None
        self.config.subtitle_lang = self.sub_lang_edit.text() or None
        
        self.config.confidence_threshold = self.confidence_spin.value()
        self.config.strict_matching = self.strict_check.isChecked()
        
        self.config.shift_frames = self.shift_frames_spin.value()
        self.config.no_resample = self.no_resample_check.isChecked()
        self.config.force_resample = self.force_resample_check.isChecked()
        
        # Save to file
        self.config.save()
        
        super().accept()
