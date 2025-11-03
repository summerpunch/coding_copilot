import asyncio
import logging
import uuid
import sys
from typing import Optional
from datetime import datetime
from rich.panel import Panel
from rich.markdown import Markdown
from rich.console import Console

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from src.engine.chat import run_agent

logger = logging.getLogger(__name__)

# 初始化 Rich Console
console = Console()

class ChatSession:
    """管理单个聊天会话"""

    def __init__(self, thread_id: Optional[str] = None):
        self.thread_id = thread_id or str(uuid.uuid4())
        self.created_at = datetime.now()
        self.message_count = 0

    def __str__(self):
        return f"Session {self.thread_id[:8]}..."


class CodingCopilotCLI:
    """交互式命令行界面主类"""

    def __init__(self):
        self.current_session: Optional[ChatSession] = None
        self.sessions = []
        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
        )

    def display_welcome(self):
        """显示欢迎界面"""
        console.print()
        console.print("[bold bright_cyan]Coding Copilot[/bold bright_cyan]")
        console.print()
        console.print("Tips for getting started:")
        console.print("  1. Ask questions, edit files, or run commands.")
        console.print("  2. Be specific for the best results.")
        console.print("  3. [bold bright_cyan]/help[/bold bright_cyan] for more information.")
        console.print()

        md = Markdown(
            ":sparkles: [bold cyan]**LangGraph**[/bold cyan] — [yellow]**Claude Code Clone**[/yellow]"
        )

        console.print(
            Panel.fit(
                Markdown("**LangGraph Coding Agent** — Claude Code Clone"),
                title="[bold green] Ready [/bold green]",
                border_style="green",
            )
        )

    def display_help(self):
        """显示帮助信息"""
        console.print()
        console.print("[bold bright_yellow]Available Commands:[/bold bright_yellow]")
        console.print()
        console.print("  [bold bright_cyan]/new[/bold bright_cyan]      - Create a new chat session")
        console.print("  [bold bright_cyan]/sessions[/bold bright_cyan] - List all chat sessions")
        console.print("  [bold bright_cyan]/help[/bold bright_cyan]     - Show this help message")
        console.print("  [bold bright_cyan]/quit[/bold bright_cyan]     - Exit Coding Copilot")
        console.print()
        console.print("Just type your message to start chatting with the AI assistant.")
        console.print()

    def create_new_session(self):
        """创建新的会话"""
        self.current_session = ChatSession()
        self.sessions.append(self.current_session)
        console.print()
        console.print(
            f"[dim]Created new session: {self.current_session.thread_id[:8]}...[/dim]"
        )
        console.print()

    def list_sessions(self):
        """列出所有会话"""
        if not self.sessions:
            console.print()
            console.print("[dim]No sessions yet.[/dim]")
            console.print()
            return

        console.print()
        console.print("[bold bright_yellow]Chat Sessions:[/bold bright_yellow]")
        console.print()
        for i, session in enumerate(self.sessions, 1):
            current_marker = "→" if session == self.current_session else " "
            session_info = f"Session {session.thread_id[:8]}..."
            message_info = f"{session.message_count} messages"
            time_info = session.created_at.strftime("%H:%M:%S")
            console.print(
                f"  {current_marker} [bright_cyan]{i}.[/bright_cyan] {session_info} "
                f"[dim]({message_info}, {time_info})[/dim]"
            )
        console.print()

    async def send_message(self, message: str):
        """发送消息到 AI 助手"""
        if not self.current_session:
            self.create_new_session()

        # 显示用户消息
        console.print()
        console.print(f"[bold bright_blue]You:[/bold bright_blue]")
        console.print(message)
        console.print()

        # 流式输出处理
        first_output = True
        last_was_newline = False

        try:
            async for output in run_agent(
                message=message, thread_id=self.current_session.thread_id
            ):
                # 第一次输出时显示 Assistant 标题
                if first_output:
                    console.print("[bold bright_green]Assistant:[/bold bright_green]")
                    first_output = False
                    last_was_newline = True

                if output:
                    output_str = str(output)

                    # 如果输出包含换行符，使用 print（会自动换行）
                    if "\n" in output_str:
                        # 如果上一次不是以换行结束，先打印当前内容
                        console.print(output_str)
                        last_was_newline = output_str.endswith("\n")
                    else:
                        # 流式文本块，不换行
                        console.print(output_str, end="")
                        sys.stdout.flush()
                        last_was_newline = False

            # 如果最后一次输出没有换行，添加一个换行
            if not last_was_newline and not first_output:
                console.print()

            # 增加消息计数
            self.current_session.message_count += 1

        except Exception as e:
            logger.error(f"发送消息时出错: {e}", exc_info=True)
            console.print()
            console.print(f"[bold red]Error:[/bold red] {str(e)}")

        console.print()  # 添加空行分隔

    async def run(self):
        """运行主循环"""
        self.display_welcome()

        # 创建第一个会话
        self.create_new_session()

        try:
            while True:
                try:
                    # 显示提示符
                    session_id = (
                        self.current_session.thread_id[:8]
                        if self.current_session
                        else "no-session"
                    )
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.prompt_session.prompt(
                            f"[{session_id}] > ",
                            multiline=False,
                        ),
                    )

                    # 去除前后空白
                    user_input = user_input.strip()

                    # 空输入
                    if not user_input:
                        continue

                    # 处理命令
                    if user_input.startswith("/"):
                        await self.handle_command(user_input)
                    else:
                        # 发送消息
                        await self.send_message(user_input)

                except KeyboardInterrupt:
                    console.print()
                    console.print("[dim]Use /quit to exit[/dim]")
                    console.print()
                    continue
                except EOFError:
                    break

        except Exception as e:
            logger.error(f"运行 CLI 时出错: {e}", exc_info=True)
            console.print()
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print()
        finally:
            console.print()
            console.print("[dim]Goodbye![/dim]")
            console.print()

    async def handle_command(self, command: str):
        """处理用户命令"""
        cmd = command.lower().split()[0]

        if cmd in ["/quit", "/exit"]:
            console.print()
            console.print("[dim]Goodbye![/dim]")
            console.print()
            exit(0)
        elif cmd == "/new":
            self.create_new_session()
        elif cmd == "/sessions":
            self.list_sessions()
        elif cmd == "/help":
            self.display_help()
        else:
            console.print()
            console.print(f"[yellow]Unknown command:[/yellow] {command}")
            console.print("[dim]Type /help for available commands[/dim]")
            console.print()


def main():
    """CLI 入口点"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 创建并运行 CLI
    cli = CodingCopilotCLI()
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        console.print()
        console.print("[dim]Goodbye![/dim]")
        console.print()
    except Exception as e:
        logger.error(f"启动 CLI 时出错: {e}", exc_info=True)
        console.print()
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        console.print()
        exit(1)


if __name__ == "__main__":
    main()
