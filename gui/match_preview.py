"""
Match preview widget showing video-subtitle pairings with manual override support.
"""
from pathlib import Path
from typing import List, Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QLabel, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from modules.matcher import MatchResult


class MatchPreview(QWidget):
    """Widget for previewing and manually adjusting video-subtitle matches."""
    
    match_changed = pyqtSignal(Path, object)  # (video_path, subtitle_path or None)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.matches: List[MatchResult] = []
        self.subtitle_files: List[Path] = []
        self.manual_overrides: Dict[Path, Optional[Path]] = {}
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        
        # Info label
        self.info_label = QLabel("No matches to display")
        self.info_label.setStyleSheet("padding: 8px; background-color: #f0f0f0; border-radius: 4px;")
        layout.addWidget(self.info_label)
        
        # Match table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Video", "Subtitle", "Confidence", "Actions"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # Configure columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Enable drag and drop
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        layout.addWidget(self.table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.clear_all_button = QPushButton("Clear All Matches")
        self.clear_all_button.clicked.connect(self.clear_all_matches)
        self.clear_all_button.setEnabled(False)
        
        self.auto_match_button = QPushButton("Auto-Match")
        self.auto_match_button.clicked.connect(self.auto_match_all)
        self.auto_match_button.setEnabled(False)
        
        button_layout.addWidget(self.clear_all_button)
        button_layout.addWidget(self.auto_match_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def set_matches(self, matches: List[MatchResult], subtitle_files: List[Path]):
        """Set the matches to display."""
        self.matches = matches
        self.subtitle_files = subtitle_files
        self.manual_overrides.clear()
        
        self._update_table()
        self._update_info_label()
        
        self.clear_all_button.setEnabled(True)
        self.auto_match_button.setEnabled(True)
    
    def _update_table(self):
        """Update the table with current matches."""
        self.table.setRowCount(len(self.matches))
        
        for row, match in enumerate(self.matches):
            # Video name (column 0)
            video_item = QTableWidgetItem(match.video_path.name)
            video_item.setToolTip(str(match.video_path))
            self.table.setItem(row, 0, video_item)
            
            # Subtitle selector (column 1)
            subtitle_combo = QComboBox()
            subtitle_combo.addItem("(No subtitle)", None)
            
            # Add all subtitle options
            for sub_path in self.subtitle_files:
                subtitle_combo.addItem(sub_path.name, sub_path)
            
            # Set current selection
            current_sub = self.manual_overrides.get(match.video_path, match.subtitle_path)
            if current_sub:
                index = subtitle_combo.findData(current_sub)
                if index >= 0:
                    subtitle_combo.setCurrentIndex(index)
            
            # Connect change signal
            subtitle_combo.currentIndexChanged.connect(
                lambda idx,  row=row: self._on_subtitle_changed(row, idx)
            )
            
            self.table.setCellWidget(row, 1, subtitle_combo)
            
            # Confidence (column 2)
            confidence = match.confidence if current_sub else 0.0
            conf_item = QTableWidgetItem(f"{confidence:.0%}")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Color code by confidence
            if confidence >= 0.9:
                conf_item.setBackground(QBrush(QColor(200, 255, 200)))  # Light green
            elif confidence >= 0.7:
                conf_item.setBackground(QBrush(QColor(255, 255, 200)))  # Light yellow
            elif confidence > 0:
                conf_item.setBackground(QBrush(QColor(255, 230, 200)))  # Light orange
            else:
                conf_item.setBackground(QBrush(QColor(255, 200, 200)))  # Light red
            
            # Tooltip with match info
            tooltip = f"Match Type: {match.match_type}\nReason: {match.reason}"
            if match.video_path in self.manual_overrides:
                tooltip = "MANUAL OVERRIDE\n" + tooltip
            conf_item.setToolTip(tooltip)
            
            self.table.setItem(row, 2, conf_item)
            
            # Actions (column 3)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            clear_button = QPushButton("Clear")
            clear_button.setMaximumWidth(60)
            clear_button.clicked.connect(lambda checked, r=row: self._clear_match(r))
            
            # Show manual indicator if this was manually set
            if match.video_path in self.manual_overrides:
                manual_label = QLabel("✏️")
                manual_label.setToolTip("Manually set")
                actions_layout.addWidget(manual_label)
            
            actions_layout.addWidget(clear_button)
            actions_layout.addStretch()
            
            self.table.setCellWidget(row, 3, actions_widget)
        
        self.table.resizeRowsToContents()
    
    def _update_info_label(self):
        """Update the info label with match statistics."""
        if not self.matches:
            self.info_label.setText("No matches to display")
            return
        
        total = len(self.matches)
        matched = sum(1 for m in self.matches if m.subtitle_path is not None or m.video_path in self.manual_overrides)
        high_conf = sum(1 for m in self.matches if m.confidence >= 0.9 or m.video_path in self.manual_overrides)
        manual = len(self.manual_overrides)
        
        text = f"Total: {total} | Matched: {matched} | High Confidence: {high_conf}"
        if manual > 0:
            text += f" | Manual: {manual}"
        
        self.info_label.setText(text)
    
    def _on_subtitle_changed(self, row: int, index: int):
        """Handle subtitle selection change."""
        if row >= len(self.matches):
            return
        
        match = self.matches[row]
        combo = self.table.cellWidget(row, 1)
        subtitle_path = combo.itemData(index)
        
        # Update manual overrides
        if subtitle_path != match.subtitle_path:
            self.manual_overrides[match.video_path] = subtitle_path
        elif match.video_path in self.manual_overrides:
            del self.manual_overrides[match.video_path]
        
        # Emit change signal
        self.match_changed.emit(match.video_path, subtitle_path)
        
        # Update table display
        self._update_table()
        self._update_info_label()
    
    def _clear_match(self, row: int):
        """Clear the match for a specific row."""
        if row >= len(self.matches):
            return
        
        match = self.matches[row]
        self.manual_overrides[match.video_path] = None
        
        # Update combo box
        combo = self.table.cellWidget(row, 1)
        combo.setCurrentIndex(0)  # Set to "(No subtitle)"
        
        self.match_changed.emit(match.video_path, None)
        self._update_table()
        self._update_info_label()
    
    def clear_all_matches(self):
        """Clear all matches (manual override to no subtitle)."""
        for match in self.matches:
            self.manual_overrides[match.video_path] = None
            self.match_changed.emit(match.video_path, None)
        
        self._update_table()
        self._update_info_label()
    
    def auto_match_all(self):
        """Remove all manual overrides (revert to automatic matching)."""
        self.manual_overrides.clear()
        
        # Notify of changes
        for match in self.matches:
            self.match_changed.emit(match.video_path, match.subtitle_path)
        
        self._update_table()
        self._update_info_label()
    
    def get_matches(self) -> List[MatchResult]:
        """Get the current matches with manual overrides applied."""
        result = []
        for match in self.matches:
            if match.video_path in self.manual_overrides:
                # Create a copy with manual override
                new_match = MatchResult(
                    video_path=match.video_path,
                    subtitle_path=self.manual_overrides[match.video_path],
                    confidence=1.0 if self.manual_overrides[match.video_path] else 0.0,
                    match_type='manual',
                    reason='Manually set by user'
                )
                result.append(new_match)
            else:
                result.append(match)
        return result
