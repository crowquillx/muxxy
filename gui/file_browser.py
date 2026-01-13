"""
File browser widget for selecting videos and subtitles.
"""
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeView,
    QCheckBox, QLineEdit, QHBoxLayout, QLabel
)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import Qt, pyqtSignal, QDir, QSortFilterProxyModel


class FileFilterProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering files by pattern."""
    
    def __init__(self, file_filter: str = "*"):
        super().__init__()
        self.file_filter = file_filter
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def filterAcceptsRow(self, source_row: int, source_parent):
        """Filter rows based on file pattern."""
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        
        # Always show directories
        if model.isDir(index):
            return True
        
        # Check if file matches filter pattern
        file_name = model.fileName(index).lower()
        patterns = self.file_filter.split()
        
        for pattern in patterns:
            pattern = pattern.strip('*').lower()
            if pattern in file_name:
                return True
        
        return False
    
    def set_filter(self, file_filter: str):
        """Update the file filter."""
        self.file_filter = file_filter
        self.invalidateFilter()


class FileBrowser(QWidget):
    """File browser widget with filtering and selection."""
    
    directory_changed = pyqtSignal(str)
    selection_changed = pyqtSignal()
    
    def __init__(self, file_filter: str = "*", parent=None):
        super().__init__(parent)
        
        self.current_directory = QDir.currentPath()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Search/filter box
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search files...")
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)
        
        # File system model
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.rootPath())
        self.fs_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        
        # Proxy model for filtering
        self.proxy_model = FileFilterProxyModel(file_filter)
        self.proxy_model.setSourceModel(self.fs_model)
        
        # Tree view
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setRootIndex(
            self.proxy_model.mapFromSource(self.fs_model.index(self.current_directory))
        )
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setAlternatingRowColors(True)
        
        # Hide unnecessary columns
        self.tree_view.setColumnHidden(1, True)  # Size
        self.tree_view.setColumnHidden(2, True)  # Type
        self.tree_view.setColumnHidden(3, True)  # Date Modified
        
        # Connect signals
        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.tree_view.doubleClicked.connect(self._on_double_click)
        
        layout.addWidget(self.tree_view)
        
        # Show selected count
        self.count_label = QLabel("0 files selected")
        layout.addWidget(self.count_label)
    
    def set_directory(self, directory: str):
        """Set the root directory for the browser."""
        path = Path(directory)
        if path.exists() and path.is_dir():
            self.current_directory = str(path)
            source_index = self.fs_model.index(self.current_directory)
            proxy_index = self.proxy_model.mapFromSource(source_index)
            self.tree_view.setRootIndex(proxy_index)
            self.tree_view.expandAll()
            self.directory_changed.emit(self.current_directory)
    
    def get_selected_files(self) -> List[Path]:
        """Get list of selected file paths."""
        files = []
        indexes = self.tree_view.selectionModel().selectedIndexes()
        
        # Get only column 0 to avoid duplicates
        seen = set()
        for index in indexes:
            if index.column() == 0:
                source_index = self.proxy_model.mapToSource(index)
                file_path = Path(self.fs_model.filePath(source_index))
                
                # Only include files, not directories
                if file_path.is_file() and str(file_path) not in seen:
                    files.append(file_path)
                    seen.add(str(file_path))
        
        return sorted(files)
    
    def get_all_files(self) -> List[Path]:
        """Get all files in the current directory (matching filter)."""
        files = []
        root_path = Path(self.current_directory)
        
        # Get filter patterns
        patterns = self.proxy_model.file_filter.split()
        
        for pattern in patterns:
            for file_path in root_path.rglob(pattern):
                if file_path.is_file():
                    files.append(file_path)
        
        return sorted(set(files))
    
    def _on_selection_changed(self):
        """Handle selection changes."""
        count = len(self.get_selected_files())
        self.count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
        self.selection_changed.emit()
    
    def _on_double_click(self, index):
        """Handle double-click on items."""
        source_index = self.proxy_model.mapToSource(index)
        file_path = Path(self.fs_model.filePath(source_index))
        
        # If it's a directory, expand/collapse it
        if file_path.is_dir():
            if self.tree_view.isExpanded(index):
                self.tree_view.collapse(index)
            else:
                self.tree_view.expand(index)
    
    def _on_filter_changed(self, text: str):
        """Handle filter text changes."""
        # This could be enhanced to do live filtering by filename
        # For now, it's a placeholder for future enhancement
        pass
