"""Autocomplete providers for commands and files."""

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from typing import Iterable, Optional
import time

from src.cli.file_scanner import FileScanner


class CommandCompleter(Completer):
    """Completer for slash commands."""

    COMMANDS = [
        '/new',
        '/sessions',
        '/history',
        '/mode',
        '/clear',
        '/help',
        '/quit',
        '/exit',
    ]

    COMMAND_DESCRIPTIONS = {
        '/new': 'Create a new chat session',
        '/sessions': 'List and switch between sessions',
        '/history': 'View current session history',
        '/mode': 'Switch mode (edit/plan)',
        '/clear': 'Clear conversation (create new session)',
        '/help': 'Show help message',
        '/quit': 'Exit Coding Copilot',
        '/exit': 'Exit Coding Copilot',
    }

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        """Get command completions.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects for matching commands
        """
        text = document.text_before_cursor

        # Only complete if text starts with /
        if not text.startswith('/'):
            return

        # Get the command part (before any space)
        cmd_part = text.split()[0] if text.split() else text

        # Find matching commands
        for cmd in self.COMMANDS:
            if cmd.startswith(cmd_part):
                # Calculate how much to replace
                start_position = -len(cmd_part)

                yield Completion(
                    text=cmd,
                    start_position=start_position,
                    display=cmd,
                    display_meta=self.COMMAND_DESCRIPTIONS.get(cmd, ''),
                )


class FileCompleter(Completer):
    """Completer for file paths triggered by @ symbol."""

    def __init__(self, file_scanner: Optional[FileScanner] = None):
        """Initialize file completer.

        Args:
            file_scanner: FileScanner instance (creates one if None)
        """
        self.file_scanner = file_scanner or FileScanner()
        self._cache_time = 0
        self._cache = None

    def _get_files(self):
        """Get file list with 5-second cache."""
        current_time = time.time()

        # Use cache if less than 5 seconds old
        if self._cache is not None and (current_time - self._cache_time) < 5:
            return self._cache

        # Refresh cache
        self._cache = self.file_scanner.scan(use_cache=True)
        self._cache_time = current_time

        return self._cache

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        """Get file path completions.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects for matching files
        """
        text = document.text_before_cursor

        # Find the last @ symbol
        last_at = text.rfind('@')

        # If no @ or @ is not the trigger for this completion, skip
        if last_at == -1:
            return

        # Get text after the last @
        after_at = text[last_at + 1:]

        # If there's a space after @, don't complete
        if ' ' in after_at:
            return

        # Get file list
        files = self._get_files()

        # Filter and yield matching files
        for rel_path, abs_path, is_dir in files:
            # Check if this file matches the partial input
            if after_at.lower() in rel_path.lower():
                # Icon for display
                icon = '📁' if is_dir else '📄'
                display_text = f'{icon} {rel_path}'

                # Calculate replacement position
                start_position = -len(after_at)

                yield Completion(
                    text=rel_path,
                    start_position=start_position,
                    display=display_text,
                    display_meta=abs_path,
                )


class ModeCompleter(Completer):
    """Completer for mode command arguments."""

    MODES = ['edit', 'plan']

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        """Get mode completions.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects for modes
        """
        text = document.text_before_cursor

        # Only complete if line starts with /mode
        if not text.startswith('/mode'):
            return

        # Get the part after /mode
        parts = text.split()
        if len(parts) == 1:
            # No mode entered yet, show all
            for mode in self.MODES:
                yield Completion(
                    text=mode,
                    start_position=0,
                    display=mode,
                    display_meta=f'{mode} mode',
                )
        elif len(parts) == 2:
            # Partial mode entered
            partial = parts[1]
            for mode in self.MODES:
                if mode.startswith(partial):
                    start_position = -len(partial)
                    yield Completion(
                        text=mode,
                        start_position=start_position,
                        display=mode,
                        display_meta=f'{mode} mode',
                    )


class SmartCompleter(Completer):
    """Combined completer that dispatches to appropriate sub-completer."""

    def __init__(self, file_scanner: Optional[FileScanner] = None):
        """Initialize smart completer.

        Args:
            file_scanner: FileScanner instance for file completion
        """
        self.command_completer = CommandCompleter()
        self.file_completer = FileCompleter(file_scanner)
        self.mode_completer = ModeCompleter()

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        """Get appropriate completions based on context.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects from appropriate completer
        """
        text = document.text_before_cursor

        # Mode argument completion
        if text.startswith('/mode'):
            yield from self.mode_completer.get_completions(document, complete_event)
        # Command completion
        elif text.startswith('/'):
            yield from self.command_completer.get_completions(document, complete_event)
        # File completion (if @ is present)
        elif '@' in text:
            yield from self.file_completer.get_completions(document, complete_event)
