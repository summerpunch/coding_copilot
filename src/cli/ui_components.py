"""Rich UI components and helpers for CLI display."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.syntax import Syntax
from rich.markdown import Markdown
from typing import List, Optional
import re

from src.cli.session import ChatSession


class UIComponents:
    """Collection of UI component builders for the CLI."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize UI components.

        Args:
            console: Rich Console instance (creates one if None)
        """
        self.console = console or Console()

    def display_welcome(self):
        """Display welcome screen."""
        self.console.print()

        # Create title
        title = Text()
        title.append("LangGraph Supervisor Agent", style="bold bright_cyan")
        title.append(" — ", style="dim")
        title.append("Coding Copilot CLI", style="bold yellow")

        # Display title panel
        self.console.print(
            Panel.fit(
                Align.center(title),
                title="[bold green]Ready[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )
        self.console.print()

        # Create tips panel
        tips = Text()
        tips.append("Tips for getting started:\n", style="bold bright_white")
        tips.append("  1. Ask questions, edit files, or run commands.\n", style="white")
        tips.append("  2. Be specific for the best results.\n", style="white")
        tips.append("  3. Type ", style="white")
        tips.append("@", style="bold bright_cyan")
        tips.append(" to reference files (autocomplete dropdown).\n", style="white")
        tips.append("  4. Use ", style="white")
        tips.append("@", style="bold bright_cyan")
        tips.append(" multiple times to select multiple files.\n", style="white")
        tips.append("  5. Type ", style="white")
        tips.append("/", style="bold bright_cyan")
        tips.append(" + ", style="white")
        tips.append("Tab", style="bold bright_cyan")
        tips.append(" to see available commands.\n", style="white")
        tips.append("  6. Use ", style="white")
        tips.append("/help", style="bold bright_cyan")
        tips.append(" or ", style="white")
        tips.append("Ctrl+H", style="bold bright_cyan")
        tips.append(" for more information.", style="white")

        self.console.print(
            Panel(
                tips,
                title="[bold bright_yellow]Getting Started[/bold bright_yellow]",
                border_style="bright_yellow",
                padding=(1, 2),
            )
        )
        self.console.print()

    def display_help(self):
        """Display help information."""
        self.console.print()

        # Create commands table
        table = Table(
            title="Available Commands",
            title_style="bold bright_yellow",
            border_style="bright_yellow",
            show_header=True,
            header_style="bold bright_cyan",
        )
        table.add_column("Command", style="bold bright_cyan", no_wrap=True)
        table.add_column("Description", style="white")

        table.add_row("/new [mode]", "Create a new chat session (optional: edit/plan/yolo)")
        table.add_row("/sessions", "List and switch between sessions")
        table.add_row("/history", "View current session history")
        table.add_row("/mode <edit|plan|yolo>", "Switch between modes")
        table.add_row("/clear", "Clear conversation (creates new session)")
        table.add_row("/help", "Show this help message")
        table.add_row("/quit or /exit", "Exit Coding Copilot")

        self.console.print(table)
        self.console.print()

        # Add usage tips
        usage_tips = Text()
        usage_tips.append("Usage Tips:\n", style="bold bright_white")
        usage_tips.append("  • Type ", style="white")
        usage_tips.append("/", style="bold bright_cyan")
        usage_tips.append(" and press ", style="white")
        usage_tips.append("Tab", style="bold bright_cyan")
        usage_tips.append(" to see command suggestions\n", style="white")
        usage_tips.append("  • Type ", style="white")
        usage_tips.append("@", style="bold bright_cyan")
        usage_tips.append(" to see file suggestions (use multiple times for multiple files)\n", style="white")
        usage_tips.append("  • Press ", style="white")
        usage_tips.append("Tab", style="bold bright_cyan")
        usage_tips.append(" or ", style="white")
        usage_tips.append("↓/↑", style="bold bright_cyan")
        usage_tips.append(" to navigate suggestions\n", style="white")
        usage_tips.append("  • Just type your message to chat with the AI assistant\n", style="white")
        usage_tips.append("\nModes:\n", style="bold bright_white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("edit", style="bold bright_green")
        usage_tips.append(" - Full agent workflow (analyze → execute → review)\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("plan", style="bold bright_magenta")
        usage_tips.append(" - Planning mode for complex tasks\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("yolo", style="bold bright_yellow")
        usage_tips.append(" - Auto-approve mode (fast execution)\n", style="white")
        usage_tips.append("\nKeyboard Shortcuts:\n", style="bold bright_white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Enter", style="bold bright_cyan")
        usage_tips.append(" - New line (multi-line input)\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+J", style="bold bright_cyan")
        usage_tips.append(" - Submit message (Ctrl+Enter)\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+C", style="bold bright_cyan")
        usage_tips.append(" - Interrupt current operation\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+D", style="bold bright_cyan")
        usage_tips.append(" or ", style="white")
        usage_tips.append("/quit", style="bold bright_cyan")
        usage_tips.append(" - Exit\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("↑/↓", style="bold bright_cyan")
        usage_tips.append(" - Navigate command history", style="white")

        self.console.print(
            Panel(
                usage_tips,
                title="[bold bright_blue]Help[/bold bright_blue]",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )
        self.console.print()

    def display_session_created(self, session: ChatSession):
        """Display new session creation message.

        Args:
            session: Newly created session
        """
        session_info = Text()
        session_info.append("Session ID: ", style="white")
        session_info.append(session.thread_id, style="bold bright_cyan")  # Full session ID
        session_info.append("\nMode: ", style="white")

        # Mode-specific colors
        if session.mode == "edit":
            mode_style = "bold bright_green"
        elif session.mode == "plan":
            mode_style = "bold bright_magenta"
        elif session.mode == "yolo":
            mode_style = "bold bright_yellow"
        else:
            mode_style = "bold white"

        session_info.append(session.mode, style=mode_style)
        session_info.append("\nCreated: ", style="white")
        session_info.append(session.created_at.strftime("%Y-%m-%d %H:%M:%S"), style="dim")

        self.console.print()
        self.console.print(
            Panel(
                session_info,
                title="[bold green]New Session Created[/bold green]",
                border_style="green",
                padding=(1, 2),  # Add padding for better spacing
            )
        )
        self.console.print()

    def display_sessions_list(self, sessions: List[ChatSession], current_session: Optional[ChatSession]):
        """Display list of sessions.

        Args:
            sessions: List of all sessions
            current_session: Currently active session
        """
        if not sessions:
            self.console.print()
            self.console.print(
                Panel.fit(
                    Text("No sessions yet. Create one with /new", style="dim"),
                    title="[bold yellow]Sessions[/bold yellow]",
                    border_style="yellow",
                )
            )
            self.console.print()
            return

        # Create sessions table
        table = Table(
            title="Chat Sessions",
            title_style="bold bright_yellow",
            border_style="bright_yellow",
            show_header=True,
            header_style="bold bright_cyan",
        )
        table.add_column("", style="bold green", width=2)  # Current marker
        table.add_column("#", style="bold bright_cyan", width=3)
        table.add_column("Session ID", style="bright_cyan", no_wrap=True)
        table.add_column("Mode", style="white", width=6)
        table.add_column("Messages", justify="right", style="white")
        table.add_column("Last Used", style="dim")

        for i, session in enumerate(sessions, 1):
            current_marker = "→" if session.thread_id == (current_session.thread_id if current_session else None) else ""
            session_id = session.thread_id[:8] + "..."
            mode_color = "bright_green" if session.mode == "edit" else "bright_magenta"
            mode_text = Text(session.mode, style=mode_color)
            messages = str(session.message_count)
            last_used = session.last_used.strftime("%m-%d %H:%M")

            table.add_row(current_marker, str(i), session_id, mode_text, messages, last_used)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def display_session_history(self, session: ChatSession):
        """Display current session history.

        Args:
            session: Current session
        """
        session_info = Text()
        session_info.append("Session ID: ", style="white")
        session_info.append(session.thread_id[:8] + "...\n", style="bold bright_cyan")
        session_info.append("Mode: ", style="white")
        mode_color = "bold bright_green" if session.mode == "edit" else "bold bright_magenta"
        session_info.append(f"{session.mode}\n", style=mode_color)
        session_info.append("Messages: ", style="white")
        session_info.append(f"{session.message_count}\n", style="bold green")
        session_info.append("Created: ", style="white")
        session_info.append(session.created_at.strftime("%Y-%m-%d %H:%M:%S"), style="dim")

        self.console.print()
        self.console.print(
            Panel(
                session_info,
                title="[bold bright_cyan]Session History[/bold bright_cyan]",
                border_style="bright_cyan",
                padding=(1, 2),
            )
        )
        self.console.print()

    def display_mode_switched(self, old_mode: str, new_mode: str):
        """Display mode switch confirmation.

        Args:
            old_mode: Previous mode
            new_mode: New mode
        """
        mode_info = Text()
        mode_info.append("Switched from ", style="white")
        mode_info.append(old_mode, style="bold dim")
        mode_info.append(" to ", style="white")
        new_color = "bold bright_green" if new_mode == "edit" else "bold bright_magenta"
        mode_info.append(new_mode, style=new_color)

        self.console.print()
        self.console.print(
            Panel.fit(
                mode_info,
                title="[bold bright_yellow]Mode Changed[/bold bright_yellow]",
                border_style="bright_yellow",
            )
        )
        self.console.print()

    def display_error(self, error_message: str):
        """Display error message.

        Args:
            error_message: Error message to display
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                Text(error_message, style="white"),
                title="[bold red]Error[/bold red]",
                border_style="red",
            )
        )
        self.console.print()

    def display_warning(self, warning_message: str):
        """Display warning message.

        Args:
            warning_message: Warning message to display
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                Text(warning_message, style="yellow"),
                title="[bold yellow]Warning[/bold yellow]",
                border_style="yellow",
            )
        )
        self.console.print()

    def display_info(self, info_message: str):
        """Display info message.

        Args:
            info_message: Info message to display
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                Text(info_message, style="bright_blue"),
                title="[bold bright_blue]Info[/bold bright_blue]",
                border_style="bright_blue",
            )
        )
        self.console.print()

    def display_goodbye(self):
        """Display goodbye message."""
        self.console.print()
        self.console.print(
            Panel.fit(
                Text("Thanks for using Coding Copilot!", style="dim"),
                title="[bold dim]Goodbye[/bold dim]",
                border_style="dim",
            )
        )
        self.console.print()

    def display_user_message(self, message_text: Text):
        """Display user message with better formatting.

        Args:
            message_text: Rich Text object with message content
        """
        self.console.print()

        # Use Panel instead of Panel.fit for better width control
        # Let it expand naturally based on content, but with padding
        self.console.print(
            Panel(
                message_text,
                title="[bold bright_blue]You[/bold bright_blue]",
                border_style="bright_blue",
                padding=(1, 2),  # Better padding
                width=min(self.console.width, max(len(str(message_text)) + 8, 40)),  # Min width 40, max terminal width
            )
        )
        self.console.print()

    def display_assistant_output_with_syntax(self, output: str):
        """Display assistant output with code syntax highlighting.

        Args:
            output: Assistant's output text
        """
        # Detect code blocks with ```language
        code_block_pattern = r'```(\w+)?\n(.*?)```'
        matches = list(re.finditer(code_block_pattern, output, re.DOTALL))

        if not matches:
            # No code blocks, just print normally
            self.console.print(output, end="")
            return

        # Print with syntax highlighting
        last_end = 0
        for match in matches:
            # Print text before code block
            if match.start() > last_end:
                self.console.print(output[last_end:match.start()], end="")

            # Extract language and code
            language = match.group(1) or "python"  # Default to python
            code = match.group(2)

            # Print code with syntax highlighting
            syntax = Syntax(code, language, theme="monokai", line_numbers=True)
            self.console.print()
            self.console.print(syntax)
            self.console.print()

            last_end = match.end()

        # Print remaining text
        if last_end < len(output):
            self.console.print(output[last_end:], end="")

    def display_assistant_header(self):
        """Display assistant message header."""
        self.console.print("[bold bright_green]Assistant:[/bold bright_green]")
        self.console.print()
