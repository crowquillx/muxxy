"""
Terminal User Interface for Muxxy.
This module provides an interactive TUI for muxxy operations.
"""
from pathlib import Path
import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static, Input, Select, RadioSet, RadioButton, Checkbox
from textual.containers import Container, VerticalScroll, Horizontal, Grid
from textual import events, on
from textual.widget import Widget
from textual.screen import Screen

from .cli import parse_arguments, main as cli_main
from .constants import DEFAULT_RELEASE_TAG, SUB_EXTS
from .video import find_mkv_files


class MuxxyHeader(Static):
    """Custom header widget for Muxxy TUI."""

    def compose(self) -> ComposeResult:
        yield Static("🎬 Muxxy", id="app-title")
        yield Static("A tool for muxing subtitles, fonts, and attachments into MKV files", id="app-description")


class WelcomeScreen(Screen):
    """Welcome screen with main options."""

    BINDINGS = [
        ("m", "mux", "Mux Subtitles"),
        ("f", "files", "Show Files"),
        ("s", "settings", "Settings"),
        ("q", "quit", "Exit"),
    ]

    def compose(self) -> ComposeResult:
        yield MuxxyHeader()
        
        with Container(id="main-container"):
            yield Static("Welcome to Muxxy", classes="heading")
            yield Static("Select an operation to begin:", classes="sub-heading")
            
            with Container(id="button-container"):
                yield Button("Mux Subtitles", id="btn-mux", variant="primary")
                yield Button("Show Files", id="btn-files", variant="success")
                yield Button("Settings", id="btn-settings")
                yield Button("Exit", id="btn-exit", variant="error")
        
        yield Footer()

    @on(Button.Pressed, "#btn-mux")
    def show_mux_options(self) -> None:
        """Show the mux options screen."""
        self.app.push_screen("mux_options")
        
    def action_mux(self) -> None:
        """Handle 'm' key press to show mux options."""
        self.app.push_screen("mux_options")

    @on(Button.Pressed, "#btn-files")
    def show_files(self) -> None:
        """Show the available files."""
        self.app.push_screen("file_list")
        
    def action_files(self) -> None:
        """Handle 'f' key press to show files."""
        self.app.push_screen("file_list")

    @on(Button.Pressed, "#btn-settings")
    def show_settings(self) -> None:
        """Show the settings screen."""
        self.app.push_screen("settings")
        
    def action_settings(self) -> None:
        """Handle 's' key press to show settings."""
        self.app.push_screen("settings")

    @on(Button.Pressed, "#btn-exit")
    def exit_app(self) -> None:
        """Exit the application."""
        self.app.exit()
        
    def action_quit(self) -> None:
        """Handle 'q' key press to exit the application."""
        self.app.exit()


class FileListScreen(Screen):
    """Screen showing available MKV and subtitle files."""
    
    BINDINGS = [
        ("b", "back", "Back"),
        ("r", "refresh", "Refresh"),
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield MuxxyHeader()
        
        with VerticalScroll(id="file-list-container"):
            yield Static("Available Files", classes="heading")
            yield Static("", id="mkv-list")
            yield Static("", id="subtitle-list")
        
        with Container(id="button-row"):
            yield Button("Back", id="btn-back")
            yield Button("Refresh", id="btn-refresh")
        
        yield Footer()

    def on_mount(self) -> None:
        """Update the file list when the screen is mounted."""
        self.update_file_list()

    def update_file_list(self) -> None:
        """Update the file lists."""
        directory = Path(".")  # Default to current directory
        
        mkv_files = find_mkv_files(directory)
        subtitle_files = []
        for ext in SUB_EXTS:
            subtitle_files.extend(list(directory.glob(f"**/*{ext}")))
        
        mkv_list = self.query_one("#mkv-list")
        sub_list = self.query_one("#subtitle-list")
        
        mkv_content = "## MKV Files\n\n"
        if mkv_files:
            for mkv in mkv_files:
                mkv_content += f"- {mkv.name}\n"
        else:
            mkv_content += "No MKV files found in the current directory.\n"
        
        sub_content = "## Subtitle Files\n\n"
        if subtitle_files:
            for sub in subtitle_files:
                sub_content += f"- {sub.name}\n"
        else:
            sub_content += "No subtitle files found in the current directory.\n"
        
        mkv_list.update(mkv_content)
        sub_list.update(sub_content)

    @on(Button.Pressed, "#btn-back")
    def go_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()
        
    def action_back(self) -> None:
        """Handle 'b' or escape key press to go back."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-refresh")
    def refresh_list(self) -> None:
        """Refresh the file list."""
        self.update_file_list()
        
    def action_refresh(self) -> None:
        """Handle 'r' key press to refresh the file list."""
        self.update_file_list()


class MuxOptionsScreen(Screen):
    """Screen for configuring mux options."""

    BINDINGS = [
        ("b", "back", "Back"),
        ("enter", "start", "Start Muxing"),
        ("escape", "back", "Back"),
        ("tab", "focus_next", "Next Field"),
        ("shift+tab", "focus_previous", "Previous Field"),
    ]

    def compose(self) -> ComposeResult:
        yield MuxxyHeader()
        
        with VerticalScroll(id="options-container"):
            yield Static("Mux Options", classes="heading")
            
            with Container(classes="option-group"):
                yield Static("Directory:", classes="option-label")
                yield Input(placeholder=".", id="input-directory")
            
            with Container(classes="option-group"):
                yield Static("Release Tag:", classes="option-label")
                yield Input(placeholder=f"{DEFAULT_RELEASE_TAG}", id="input-tag")
            
            with Container(classes="option-group"):
                yield Static("Video Track Name:", classes="option-label")
                yield Input(id="input-video-track")
            
            with Container(classes="option-group"):
                yield Static("Subtitle Track Name:", classes="option-label")
                yield Input(id="input-sub-track")
            
            with Container(classes="option-group"):
                yield Static("Subtitle Language:", classes="option-label")
                yield Input(placeholder="eng", id="input-lang")
            
            with Container(classes="option-group"):
                yield Static("Shift Frames:", classes="option-label")
                yield Input(placeholder="0", id="input-shift-frames")
            
            with Container(classes="option-group"):
                yield Static("Output Directory:", classes="option-label")
                yield Input(id="input-output-dir")
            
            with Container(classes="option-group"):
                yield Checkbox("Force all subtitles", id="check-force")
                yield Checkbox("Include all matches", id="check-all-match")
                yield Checkbox("Debug output", id="check-debug")
                yield Checkbox("Strict matching", id="check-strict")
                yield Checkbox("No resample", id="check-no-resample")
                yield Checkbox("Force resample", id="check-force-resample")
        
        with Horizontal(id="button-row"):
            yield Button("Back", id="btn-back")
            yield Button("Start Muxing", id="btn-start", variant="primary")
        
        yield Footer()

    @on(Button.Pressed, "#btn-back")
    def go_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()
        
    def action_back(self) -> None:
        """Handle 'b' or escape key press to go back."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-start")
    def start_muxing(self) -> None:
        """Start the muxing process with the selected options."""
        # Build the arguments
        args = []
        
        directory = self.query_one("#input-directory").value
        if directory and directory != ".":
            args.extend(["--dir", directory])
        
        tag = self.query_one("#input-tag").value
        if tag and tag != DEFAULT_RELEASE_TAG:
            args.extend(["--tag", tag])
        
        video_track = self.query_one("#input-video-track").value
        if video_track:
            args.extend(["--video-track", video_track])
        
        sub_track = self.query_one("#input-sub-track").value
        if sub_track:
            args.extend(["--sub-track", sub_track])
        
        lang = self.query_one("#input-lang").value
        if lang:
            args.extend(["--lang", lang])
        
        shift_frames = self.query_one("#input-shift-frames").value
        if shift_frames and shift_frames != "0":
            args.extend(["--shift-frames", shift_frames])
        
        output_dir = self.query_one("#input-output-dir").value
        if output_dir:
            args.extend(["--output-dir", output_dir])
        
        # Add checkbox options
        if self.query_one("#check-force").value:
            args.append("--force")
        
        if self.query_one("#check-all-match").value:
            args.append("--all-match")
        
        if self.query_one("#check-debug").value:
            args.append("--debug")
        
        if self.query_one("#check-strict").value:
            args.append("--strict")
        
        if self.query_one("#check-no-resample").value:
            args.append("--no-resample")
        
        if self.query_one("#check-force-resample").value:
            args.append("--force-resample")
        
        # Launch the muxing process
        self.app.push_screen(
            ProcessScreen(args=args),
            wait_for_dismiss=False
        )
        
    def action_start(self) -> None:
        """Handle enter key press to start muxing."""
        self.start_muxing()
        
    def action_focus_next(self) -> None:
        """Focus the next input field."""
        self.screen.focus_next()


class ProcessScreen(Screen):
    """Screen showing the muxing process."""
    
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("d", "done", "Done"),
    ]
    
    def __init__(self, args=None):
        super().__init__()
        self.args = args or []

    def compose(self) -> ComposeResult:
        yield MuxxyHeader()
        
        with Container(id="process-container"):
            yield Static("Muxing Process", classes="heading")
            yield Static("Starting muxing process...", id="process-status")
            yield Static("", id="process-log", classes="log")
        
        with Container(id="button-row"):
            yield Button("Cancel", id="btn-cancel", variant="error")
            yield Button("Done", id="btn-done", variant="success", disabled=True)
        
        yield Footer()

    async def on_mount(self) -> None:
        """Start the process when the screen is mounted."""
        # Save original stdout
        original_stdout = sys.stdout
        
        try:
            # Redirect stdout to capture output
            from io import StringIO
            captured_output = StringIO()
            sys.stdout = captured_output
            
            # Set up the arguments
            sys.argv = ["main.py"] + self.args
            
            # Call the CLI main function
            cli_main()
            
            # Update the log with the captured output
            log_widget = self.query_one("#process-log")
            log_widget.update(captured_output.getvalue())
            
            # Update status and enable Done button
            status_widget = self.query_one("#process-status")
            status_widget.update("Muxing completed!")
            
            done_button = self.query_one("#btn-done")
            done_button.disabled = False
        except Exception as e:
            # Handle any errors
            log_widget = self.query_one("#process-log")
            log_widget.update(f"Error during muxing process:\n{str(e)}")
            
            status_widget = self.query_one("#process-status")
            status_widget.update("Muxing failed!")
        finally:
            # Restore original stdout
            sys.stdout = original_stdout

    @on(Button.Pressed, "#btn-cancel")
    def cancel_process(self) -> None:
        """Cancel the process and go back."""
        self.app.pop_screen()
        
    def action_cancel(self) -> None:
        """Handle escape key press to cancel."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-done")
    def finish_process(self) -> None:
        """Finish the process and go back."""
        self.app.pop_screen()
        
    def action_done(self) -> None:
        """Handle 'd' key press to finish."""
        done_button = self.query_one("#btn-done")
        if not done_button.disabled:
            self.app.pop_screen()


class SettingsScreen(Screen):
    """Screen for changing application settings."""
    
    BINDINGS = [
        ("b", "back", "Back"),
        ("s", "save", "Save"),
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield MuxxyHeader()
        
        with Container(id="settings-container"):
            yield Static("Settings", classes="heading")
            # Add settings options here
            yield Static("Application settings will be added here in a future version.", classes="info")
        
        with Container(id="button-row"):
            yield Button("Back", id="btn-back")
            yield Button("Save", id="btn-save", variant="primary")
        
        yield Footer()

    @on(Button.Pressed, "#btn-back")
    def go_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()
        
    def action_back(self) -> None:
        """Handle 'b' or escape key press to go back."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-save")
    def save_settings(self) -> None:
        """Save settings and go back."""
        # Save settings logic would go here
        self.app.pop_screen()
        
    def action_save(self) -> None:
        """Handle 's' key press to save settings."""
        # Save settings logic would go here
        self.app.pop_screen()


class MuxxyTUI(App):
    """Main Muxxy TUI Application."""
    
    TITLE = "Muxxy TUI"
    CSS = """
    #app-title {
        text-align: center;
        color: $accent-lighten-2;
        text-style: bold;
        padding: 1 2;
    }
    
    #app-description {
        text-align: center;
        padding: 0 2 1 2;
        color: $text;
    }
    
    MuxxyHeader {
        width: 100%;
        height: auto;
        background: $boost;
        padding: 1 0;
        dock: top;
    }
    
    .heading {
        text-align: center;
        text-style: bold;
        width: 100%;
        color: $accent;
        padding: 1 0;
        margin: 1 0;
        border-bottom: solid $primary;
    }
    
    .sub-heading {
        text-align: center;
        padding: 1 0;
        margin: 1 0;
    }
    
    .info {
        margin: 1 0;
        text-align: center;
        color: $text-muted;
    }
    
    #main-container {
        padding: 1 2;
        align: center middle;
        height: 100%;
    }
    
    #button-container {
        width: 30;
        layout: grid;
        grid-size: 1;
        grid-gutter: 1 2;
        grid-rows: 4;
        grid-columns: 1fr;
        align: center middle;
        padding: 2 0;
    }
    
    Button {
        width: 100%;
        height: 3;
        margin: 0 1;
    }
    
    #button-row {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1;
    }
    
    #button-row Button {
        margin: 0 1;
        min-width: 16;
    }
    
    #file-list-container, #options-container, #process-container, #settings-container {
        width: 100%;
        height: 1fr;
        padding: 0 2;
    }
    
    #process-log {
        height: auto;
        min-height: 20;
        max-height: 30;
        width: 100%;
        background: $surface-darken-1;
        color: $text;
        border: solid $primary;
        padding: 1;
        overflow-y: scroll;
    }
    
    .option-group {
        width: 100%;
        margin-bottom: 1;
        padding: 0 1;
    }
    
    .option-label {
        padding: 0 1;
        color: $text-muted;
    }
    
    Input {
        margin: 0 1 1 1;
        width: 90%;
    }
    
    Checkbox {
        margin: 0 1;
        padding: 0 1;
        width: 100%;
    }
    """
    
    SCREENS = {
        "welcome": WelcomeScreen,
        "file_list": FileListScreen,
        "mux_options": MuxOptionsScreen,
        "settings": SettingsScreen,
    }
    
    def compose(self) -> ComposeResult:
        """Set up the main app UI."""
        yield Container()  # Placeholder for the current screen

    def on_mount(self) -> None:
        """Start with the welcome screen when the app launches."""
        self.push_screen("welcome")


def run_tui():
    """Run the Muxxy TUI application."""
    app = MuxxyTUI()
    app.run()