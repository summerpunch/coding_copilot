"""Main CLI application using typer, rich, and prompt_toolkit."""

import typer
import asyncio
import sys
import os
import re
import logging
from typing import Optional
from pathlib import Path

# Add project root to path if needed
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.text import Text as RichText
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from src.cli.session import ChatSession, SessionDatabase
from src.cli.file_scanner import FileScanner
from src.cli.completers import SmartCompleter
from src.cli.ui_components import UIComponents
from src.engine.chat import run_agent

# Create typer app
app = typer.Typer(
    name="coding-copilot",
    help="Interactive AI coding assistant with supervisor agent architecture",
    add_completion=False,
)

logger = logging.getLogger(__name__)


def disable_all_logging():
    """Disable all logging for production use."""
    logging.root.setLevel(logging.CRITICAL + 1)

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.root.addHandler(logging.NullHandler())

    # Disable specific loggers
    for logger_name in [
        'src', 'httpx', 'httpcore', 'openai', 'anthropic',
        'langchain', 'langchain_core', 'langgraph', 'asyncio',
    ]:
        lg = logging.getLogger(logger_name)
        lg.setLevel(logging.CRITICAL + 1)
        lg.propagate = False
        lg.disabled = True


class CodingCopilotCLI:
    """Main CLI interface for Coding Copilot."""

    def __init__(self, initial_mode: str = "edit", thread_id: Optional[str] = None):
        """Initialize CLI.

        Args:
            initial_mode: Initial mode (edit/plan)
            thread_id: Thread ID to resume (None for new session)
        """
        self.console = Console()
        self.ui = UIComponents(self.console)
        self.session_db = SessionDatabase()
        self.file_scanner = FileScanner()

        # Setup prompt session with completers
        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            completer=SmartCompleter(self.file_scanner),
            complete_while_typing=True,
        )

        # Current session
        self.current_session: Optional[ChatSession] = None

        # Load or create session
        if thread_id:
            self.current_session = self.session_db.get_session(thread_id)
            if not self.current_session:
                self.ui.display_error(f"Session {thread_id} not found. Creating new session.")
                self.create_new_session(initial_mode)
        else:
            self.create_new_session(initial_mode)

    def create_new_session(self, mode: str = "edit"):
        """Create a new chat session.

        Args:
            mode: Mode for the new session (edit/plan)
        """
        self.current_session = ChatSession(mode=mode)
        self.session_db.save_session(self.current_session)
        self.ui.display_session_created(self.current_session)

    async def list_sessions(self):
        """List all sessions and allow switching."""
        sessions = self.session_db.list_sessions()
        self.ui.display_sessions_list(sessions, self.current_session)

        # Ask if user wants to switch
        if len(sessions) > 1:
            self.console.print("[dim]Type a session number to switch, or press Enter to continue[/dim]")
            try:
                choice = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.prompt_session.prompt("Switch to session: ", default=""),
                )
                choice = choice.strip()

                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(sessions):
                        self.current_session = sessions[idx]
                        self.session_db.update_last_used(self.current_session.thread_id)
                        self.console.print(
                            f"[green]Switched to session {self.current_session.thread_id[:8]}... ({self.current_session.mode} mode)[/green]"
                        )
                    else:
                        self.ui.display_error("Invalid session number")
            except (KeyboardInterrupt, EOFError):
                pass

            self.console.print()

    def show_history(self):
        """Show current session history."""
        if not self.current_session:
            self.ui.display_warning("No active session")
            return

        self.ui.display_session_history(self.current_session)

    def switch_mode(self, new_mode: str):
        """Switch the current session's mode.

        Args:
            new_mode: New mode to switch to (edit/plan)
        """
        if not self.current_session:
            self.ui.display_error("No active session")
            return

        if new_mode not in ['edit', 'plan']:
            self.ui.display_error(f"Invalid mode: {new_mode}. Use 'edit' or 'plan'")
            return

        old_mode = self.current_session.mode
        if old_mode == new_mode:
            self.ui.display_info(f"Already in {new_mode} mode")
            return

        self.current_session.mode = new_mode
        self.session_db.update_mode(self.current_session.thread_id, new_mode)
        self.ui.display_mode_switched(old_mode, new_mode)

    async def send_message(self, message: str):
        """Send message to the AI assistant.

        Args:
            message: User's message
        """
        if not self.current_session:
            self.create_new_session()

        # Process file paths: @relative/path -> @absolute/path
        display_text = RichText()
        ai_message_parts = []

        # Split on @ symbols (but preserve them)
        parts = re.split(r'(@[^\s]+)', message)

        for part in parts:
            if part.startswith('@'):
                # This is a file reference
                file_path = part[1:]  # Remove @

                # Resolve to absolute path
                abs_path = self.file_scanner.resolve_path(file_path)

                if abs_path:
                    # Display: clickable link
                    display_text.append(part, style=f"bold bright_cyan link file://{abs_path}")
                    # Send to AI: absolute path
                    ai_message_parts.append(f"@{abs_path}")
                else:
                    # Path not found, but still send it
                    display_text.append(part, style="bold yellow")
                    ai_message_parts.append(part)
            else:
                # Normal text
                display_text.append(part, style="white")
                ai_message_parts.append(part)

        # Construct AI message with absolute paths
        ai_message = "".join(ai_message_parts)

        # Display user message
        self.ui.display_user_message(display_text)

        # Display assistant header
        self.ui.display_assistant_header()

        # Stream output from agent
        last_was_newline = False
        first_output = True

        try:
            async for output in run_agent(
                message=ai_message,
                thread_id=self.current_session.thread_id,
                mode=self.current_session.mode,
            ):
                if output:
                    output_str = str(output)

                    if "\n" in output_str:
                        self.console.print(output_str)
                        last_was_newline = output_str.endswith("\n")
                    else:
                        self.console.print(output_str, end="")
                        sys.stdout.flush()
                        last_was_newline = False

                    first_output = False

            # Add newline if needed
            if not last_was_newline and not first_output:
                self.console.print()

            # Update session stats
            self.session_db.increment_message_count(self.current_session.thread_id)
            self.current_session.message_count += 1

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            self.ui.display_error(str(e))

        self.console.print()

    async def handle_command(self, command: str):
        """Handle slash commands.

        Args:
            command: Command string (including /)
        """
        parts = command.split()
        cmd = parts[0].lower()

        if cmd in ['/quit', '/exit']:
            self.ui.display_goodbye()
            sys.exit(0)

        elif cmd == '/new':
            # Get mode from args or use current
            mode = parts[1] if len(parts) > 1 and parts[1] in ['edit', 'plan'] else self.current_session.mode if self.current_session else 'edit'
            self.create_new_session(mode)

        elif cmd == '/sessions':
            await self.list_sessions()

        elif cmd == '/history':
            self.show_history()

        elif cmd == '/mode':
            if len(parts) < 2:
                self.ui.display_error("Usage: /mode <edit|plan>")
            else:
                self.switch_mode(parts[1])

        elif cmd == '/clear':
            # Create new session (effectively clearing)
            mode = self.current_session.mode if self.current_session else 'edit'
            self.ui.display_info("Creating new session to clear conversation")
            self.create_new_session(mode)

        elif cmd == '/help':
            self.ui.display_help()

        else:
            self.ui.display_warning(f"Unknown command: {command}\nType /help for available commands")

    async def run(self):
        """Main REPL loop."""
        try:
            while True:
                try:
                    # Build prompt
                    if self.current_session:
                        session_id = self.current_session.thread_id[:8]
                        mode = self.current_session.mode
                        mode_color = "green" if mode == "edit" else "magenta"
                        prompt_text = f"[{mode}:{session_id}] > "
                    else:
                        prompt_text = "[no-session] > "

                    # Get user input
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.prompt_session.prompt(prompt_text, multiline=False),
                    )

                    # Strip whitespace
                    user_input = user_input.strip()

                    # Skip empty input
                    if not user_input:
                        continue

                    # Handle commands
                    if user_input.startswith('/'):
                        await self.handle_command(user_input)
                    else:
                        # Send message to agent
                        await self.send_message(user_input)

                except KeyboardInterrupt:
                    self.console.print()
                    self.console.print("[dim]Use /quit to exit[/dim]")
                    self.console.print()
                    continue

                except EOFError:
                    # Ctrl+D to exit
                    self.ui.display_goodbye()
                    break

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            self.ui.display_error(str(e))
        finally:
            self.ui.display_goodbye()


@app.command()
def chat(
    mode: str = typer.Option(
        "edit",
        "--mode",
        "-m",
        help="Initial mode: edit (full workflow) or plan (planning mode)",
    ),
    thread_id: Optional[str] = typer.Option(
        None,
        "--thread-id",
        "-t",
        help="Resume existing session by thread ID",
    ),
    new: bool = typer.Option(
        False,
        "--new",
        "-n",
        help="Force create new session (ignore thread-id)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug logging",
    ),
):
    """Start interactive chat with the coding assistant.

    Examples:
        # Start in edit mode (default)
        $ coding-copilot chat

        # Start in plan mode
        $ coding-copilot chat --mode plan

        # Resume existing session
        $ coding-copilot chat --thread-id abc123

        # Force new session in plan mode
        $ coding-copilot chat --new --mode plan
    """
    # Configure logging
    if debug:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        # Check if frozen (PyInstaller)
        if getattr(sys, 'frozen', False):
            disable_all_logging()

    # Validate mode
    if mode not in ['edit', 'plan']:
        console = Console()
        console.print(f"[red]Error: Invalid mode '{mode}'. Must be 'edit' or 'plan'[/red]")
        sys.exit(1)

    # Handle new flag
    if new:
        thread_id = None

    # Create and run CLI
    cli = CodingCopilotCLI(
        initial_mode=mode,
        thread_id=thread_id,
    )

    # Display welcome screen
    cli.ui.display_welcome()

    # Run main loop
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        cli.ui.display_goodbye()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        cli.ui.display_error(f"Fatal error: {str(e)}")
        sys.exit(1)


@app.command()
def sessions():
    """List all saved sessions."""
    console = Console()
    ui = UIComponents(console)
    session_db = SessionDatabase()

    sessions_list = session_db.list_sessions()
    ui.display_sessions_list(sessions_list, None)


@app.command()
def cleanup(
    days: int = typer.Option(
        30,
        "--days",
        "-d",
        help="Delete sessions not used in this many days",
    ),
    confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
):
    """Clean up old sessions."""
    console = Console()
    session_db = SessionDatabase()

    if not confirm:
        response = typer.confirm(
            f"Delete sessions not used in {days} days?",
            default=False,
        )
        if not response:
            console.print("[yellow]Cancelled[/yellow]")
            return

    deleted = session_db.cleanup_old_sessions(days)
    console.print(f"[green]Deleted {deleted} old session(s)[/green]")


def main():
    """Entry point for CLI."""
    import sys

    # If no command provided, default to 'chat'
    if len(sys.argv) == 1:
        sys.argv.append('chat')

    app()


if __name__ == "__main__":
    main()
