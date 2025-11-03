import asyncio
import logging
import uuid
import sys
from typing import Optional
from datetime import datetime
from rich.panel import Panel
from rich.markdown import Markdown
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.align import Align

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import radiolist_dialog, checkboxlist_dialog
from prompt_toolkit.completion import Completer, Completion, WordCompleter, merge_completers
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
import os
from pathlib import Path
import threading

from src.engine.chat import run_agent

logger = logging.getLogger(__name__)


def scan_directory_files(base_path=".", max_depth=5, ignore_patterns=None):
    """扫描目录下的所有文件

    Args:
        base_path: 基础路径
        max_depth: 最大扫描深度
        ignore_patterns: 忽略的模式列表

    Returns:
        文件列表 [(相对路径, 绝对路径, 是否目录)]
    """
    if ignore_patterns is None:
        ignore_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            '.idea', '.vscode', 'build', '*.pyc',
            '*.egg-info', '.pytest_cache', '.mypy_cache', '*.sqlite',
            '*.sqlite-shm', '*.sqlite-wal'
        ]

    base_path = Path(base_path).resolve()
    files = []

    def should_ignore(path):
        """检查路径是否应该被忽略"""
        name = path.name

        # 忽略隐藏文件（以 . 开头），但保留 .env
        if name.startswith('.') and name not in ['.env', '.gitignore']:
            return True

        # 忽略打包后的可执行文件本身
        if name in ['coding_copilot']:
            return True

        for pattern in ignore_patterns:
            if '*' in pattern:
                # 通配符匹配
                if pattern.startswith('*.'):
                    ext = pattern[1:]
                    if name.endswith(ext):
                        return True
            else:
                # 精确匹配目录/文件名
                if name == pattern:
                    return True
        return False

    def scan_dir(current_path, depth=0):
        """递归扫描目录"""
        if depth > max_depth:
            return

        try:
            for item in sorted(current_path.iterdir()):
                if should_ignore(item):
                    continue

                rel_path = item.relative_to(base_path)

                if item.is_dir():
                    files.append((str(rel_path) + "/", str(item), True))
                    scan_dir(item, depth + 1)
                else:
                    files.append((str(rel_path), str(item), False))
        except PermissionError:
            pass

    scan_dir(base_path)
    return files


def read_file_content(file_path, max_lines=500):
    """读取文件内容

    Args:
        file_path: 文件路径
        max_lines: 最大读取行数

    Returns:
        文件内容字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) > max_lines:
                content = ''.join(lines[:max_lines])
                content += f"\n... (文件太大，只显示前 {max_lines} 行)"
            else:
                content = ''.join(lines)
            return content
    except UnicodeDecodeError:
        return f"[二进制文件，无法读取]"
    except Exception as e:
        return f"[读取失败: {str(e)}]"


def format_file_context(file_paths):
    """格式化文件上下文信息

    Args:
        file_paths: 文件路径列表

    Returns:
        格式化的文件内容字符串
    """
    context_parts = []

    for file_path in file_paths:
        path = Path(file_path)

        if path.is_dir():
            # 目录：列出直接子项
            context_parts.append(f"\n--- Directory: {file_path} ---")
            try:
                items = list(path.iterdir())
                if items:
                    context_parts.append("Contents:")
                    for item in sorted(items)[:20]:  # 最多显示20个
                        item_type = "📁" if item.is_dir() else "📄"
                        context_parts.append(f"  {item_type} {item.name}")
                    if len(items) > 20:
                        context_parts.append(f"  ... and {len(items) - 20} more items")
                else:
                    context_parts.append("(空目录)")
            except Exception as e:
                context_parts.append(f"(无法读取: {str(e)})")
        else:
            # 文件：读取内容
            context_parts.append(f"\n--- File: {file_path} ---")
            content = read_file_content(file_path)
            context_parts.append(content)

    return "\n".join(context_parts)


class FileCompleter(Completer):
    """文件路径补全器，当输入 @ 时触发"""

    def __init__(self):
        self.cached_files = None
        self.cache_time = None

    def get_files(self):
        """获取文件列表（带缓存）"""
        import time
        current_time = time.time()

        # 缓存 5 秒
        if self.cached_files is None or (current_time - (self.cache_time or 0)) > 5:
            self.cached_files = scan_directory_files()
            self.cache_time = current_time

        return self.cached_files

    def get_completions(self, document, complete_event):
        """获取补全建议"""
        text = document.text_before_cursor

        # 找到最后一个 @ 的位置
        last_at = text.rfind('@')

        # 如果没有 @ 或者 @ 后面有空格，不补全
        if last_at == -1:
            return

        # 获取 @ 后面的文本
        after_at = text[last_at + 1:]

        # 如果 @ 后面有空格，不补全
        if ' ' in after_at:
            return

        # 获取文件列表
        files = self.get_files()

        # 过滤匹配的文件
        for rel_path, abs_path, is_dir in files:
            # 检查是否匹配
            if after_at.lower() in rel_path.lower():
                # 计算要显示的文本
                display_text = f"{'📁' if is_dir else '📄'} {rel_path}"

                # 计算要插入的文本（相对路径）
                completion_text = rel_path

                # 计算要删除的字符数（@ 后面已输入的部分）
                start_position = -len(after_at)

                yield Completion(
                    text=completion_text,
                    start_position=start_position,
                    display=display_text,
                    display_meta=abs_path,
                )


def disable_all_logging():
    """完全禁用所有日志输出（用于打包后的生产环境）"""
    # 设置根 logger 为最高级别
    logging.root.setLevel(logging.CRITICAL + 1)

    # 移除所有现有的 handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # 添加 NullHandler
    logging.root.addHandler(logging.NullHandler())

    # 禁用所有已知的 logger
    loggers_to_disable = [
        # 项目模块
        'src', 'src.engine', 'src.engine.chat', 'src.engine.agents',
        'src.engine.agents.llm_factory', 'src.engine.agents.supervisor',
        'src.engine.prompts', 'src.engine.prompts.template',
        'src.cli', 'src.cli.main',

        # HTTP 库
        'httpx', 'httpcore', 'urllib3', 'requests',

        # AI 库
        'openai', 'anthropic',
        'langchain', 'langchain_core', 'langchain_openai',
        'langchain_anthropic', 'langgraph',

        # 其他常见库
        'asyncio', 'aiosqlite', 'sqlite3',
    ]

    for logger_name in loggers_to_disable:
        lg = logging.getLogger(logger_name)
        lg.setLevel(logging.CRITICAL + 1)
        lg.propagate = False
        lg.disabled = True


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
        self.console = Console()

        # 定义所有可用命令
        self.available_commands = [
            '/new',
            '/sessions',
            '/history',
            '/clear',
            '/help',
            '/menu',
            '/quit',
            '/exit',
        ]

        # 创建命令补全器
        command_completer = WordCompleter(
            self.available_commands,
            ignore_case=True,
            sentence=True,
        )

        # 创建文件补全器
        file_completer = FileCompleter()

        # 合并补全器
        merged_completer = merge_completers([command_completer, file_completer])

        # 设置键盘绑定
        kb = KeyBindings()

        @kb.add('c-h')  # Ctrl+H 显示帮助
        def show_help(event):
            """快捷键显示帮助"""
            event.app.exit(result='/help')

        @kb.add('c-n')  # Ctrl+N 新建会话
        def new_session(event):
            """快捷键新建会话"""
            event.app.exit(result='/new')

        @kb.add('c-l')  # Ctrl+L 列出会话
        def list_sessions(event):
            """快捷键列出会话"""
            event.app.exit(result='/sessions')

        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=kb,
            completer=merged_completer,  # 使用合并后的补全器
            complete_while_typing=True,  # 输入时自动补全
        )

        # 存储待插入的文件内容
        self.pending_file_context = None

    def display_welcome(self):
        """显示欢迎界面"""
        self.console.print()

        # 创建标题
        title = Text()
        title.append("LangGraph Coding Agent", style="bold bright_cyan")
        title.append(" — ", style="dim")
        title.append("Claude Code Clone", style="bold yellow")

        # 使用 Panel 显示主标题
        self.console.print(
            Panel.fit(
                Align.center(title),
                title="[bold green]Ready[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )
        self.console.print()

        # 创建提示信息面板
        tips = Text()
        tips.append("Tips for getting started:\n", style="bold bright_white")
        tips.append("  1. Ask questions, edit files, or run commands.\n", style="white")
        tips.append("  2. Be specific for the best results.\n", style="white")
        tips.append("  3. Type ", style="white")
        tips.append("@", style="bold bright_cyan")
        tips.append(" to reference files (shows dropdown suggestions).\n", style="white")
        tips.append("  4. You can use ", style="white")
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
        """显示帮助信息"""
        self.console.print()

        # 创建命令表格
        table = Table(
            title="Available Commands",
            title_style="bold bright_yellow",
            border_style="bright_yellow",
            show_header=True,
            header_style="bold bright_cyan",
        )
        table.add_column("Command", style="bold bright_cyan", no_wrap=True)
        table.add_column("Description", style="white")

        table.add_row("/new", "Create a new chat session")
        table.add_row("/sessions", "List and switch between chat sessions")
        table.add_row("/history", "View current session history")
        table.add_row("/clear", "Clear current conversation")
        table.add_row("/help", "Show this help message")
        table.add_row("/quit", "Exit Coding Copilot")

        self.console.print(table)
        self.console.print()

        # 添加使用提示
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
        usage_tips.append(" to navigate file suggestions\n", style="white")
        usage_tips.append("  • Just type your message to chat with the AI assistant\n", style="white")
        usage_tips.append("\nKeyboard Shortcuts:\n", style="bold bright_white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+H", style="bold bright_cyan")
        usage_tips.append(" - Show help\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+N", style="bold bright_cyan")
        usage_tips.append(" - New session\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+L", style="bold bright_cyan")
        usage_tips.append(" - List sessions\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+C", style="bold bright_cyan")
        usage_tips.append(" - Interrupt (won't exit)\n", style="white")
        usage_tips.append("  • ", style="white")
        usage_tips.append("Ctrl+D", style="bold bright_cyan")
        usage_tips.append(" or ", style="white")
        usage_tips.append("/quit", style="bold bright_cyan")
        usage_tips.append(" - Exit", style="white")

        self.console.print(
            Panel(
                usage_tips,
                title="[bold bright_blue]Help[/bold bright_blue]",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )
        self.console.print()

    async def select_files(self):
        """显示文件选择对话框"""
        self.console.print()
        self.console.print("[bold bright_cyan]Scanning files...[/bold bright_cyan]")

        # 显示当前工作目录
        current_dir = os.getcwd()
        self.console.print(f"[dim]Current directory: {current_dir}[/dim]")

        # 扫描当前目录
        try:
            files = scan_directory_files()
            self.console.print(f"[dim]Found {len(files)} files/folders[/dim]")

            # 如果没有文件，列出目录内容进行调试
            if len(files) == 0:
                self.console.print(f"[yellow]Debug: Listing directory contents...[/yellow]")
                try:
                    items = list(Path(current_dir).iterdir())
                    self.console.print(f"[yellow]Total items in directory: {len(items)}[/yellow]")
                    for item in items[:10]:  # 只显示前10个
                        self.console.print(f"[yellow]  - {item.name}[/yellow]")
                except Exception as e:
                    self.console.print(f"[red]Error listing directory: {str(e)}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error scanning files: {str(e)}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            self.console.print()
            return []

        if not files:
            self.console.print("[yellow]No files found in current directory[/yellow]")
            self.console.print()
            return []

        # 准备选项列表 (value, label)
        file_options = []
        for rel_path, abs_path, is_dir in files:
            label = f"📁 {rel_path}" if is_dir else f"📄 {rel_path}"
            file_options.append((abs_path, label))

        # 限制显示数量（避免列表太长）
        if len(file_options) > 100:
            self.console.print(f"[yellow]Found {len(file_options)} files, showing first 100[/yellow]")
            file_options = file_options[:100]

        self.console.print("[dim]Opening file selector...[/dim]")

        # 显示文件选择对话框
        try:
            selected = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: checkboxlist_dialog(
                    title="Select Files/Folders",
                    text="Use Space to select, Enter to confirm:",
                    values=file_options,
                ).run(),
            )

            if selected:
                self.console.print()
                self.console.print(f"[green]Selected {len(selected)} item(s)[/green]")
                for item in selected:
                    item_type = "📁" if Path(item).is_dir() else "📄"
                    self.console.print(f"  {item_type} {Path(item).relative_to(os.getcwd())}")
                self.console.print()

            return selected if selected else []

        except Exception as e:
            self.console.print(f"[red]Error selecting files: {str(e)}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            self.console.print()
            return []

    async def show_command_menu(self):
        """显示交互式命令菜单"""
        commands = [
            ("new", "Create a new chat session"),
            ("sessions", "List and switch between sessions"),
            ("history", "View current session history"),
            ("clear", "Clear current conversation"),
            ("help", "Show help message"),
            ("quit", "Exit Coding Copilot"),
        ]

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: radiolist_dialog(
                title="Commands",
                text="Select a command to execute:",
                values=commands,
            ).run(),
        )

        if result:
            await self.handle_command(f"/{result}")

    def create_new_session(self):
        """创建新的会话"""
        self.current_session = ChatSession()
        self.sessions.append(self.current_session)

        # 使用 Panel 显示新会话信息
        session_info = Text()
        session_info.append("Session ID: ", style="white")
        session_info.append(self.current_session.thread_id[:8] + "...", style="bold bright_cyan")
        session_info.append("\nCreated: ", style="white")
        session_info.append(self.current_session.created_at.strftime("%Y-%m-%d %H:%M:%S"), style="dim")

        self.console.print()
        self.console.print(
            Panel.fit(
                session_info,
                title="[bold green]New Session Created[/bold green]",
                border_style="green",
            )
        )
        self.console.print()

    async def list_sessions(self):
        """列出所有会话并支持切换"""
        if not self.sessions:
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

        # 创建会话表格
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
        table.add_column("Messages", justify="right", style="white")
        table.add_column("Created", style="dim")

        for i, session in enumerate(self.sessions, 1):
            current_marker = "→" if session == self.current_session else ""
            session_id = session.thread_id[:8] + "..."
            messages = str(session.message_count)
            created = session.created_at.strftime("%H:%M:%S")

            table.add_row(current_marker, str(i), session_id, messages, created)

        self.console.print()
        self.console.print(table)
        self.console.print()

        # 询问是否要切换会话
        if len(self.sessions) > 1:
            self.console.print("[dim]Type a session number to switch, or press Enter to continue[/dim]")
            try:
                choice = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.prompt_session.prompt("Switch to session: ", default=""),
                )
                choice = choice.strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.sessions):
                        self.current_session = self.sessions[idx]
                        self.console.print(
                            f"[green]Switched to session {self.current_session.thread_id[:8]}...[/green]"
                        )
                    else:
                        self.console.print("[yellow]Invalid session number[/yellow]")
            except (KeyboardInterrupt, EOFError):
                pass
            self.console.print()

    async def send_message(self, message: str):
        """发送消息到 AI 助手"""
        if not self.current_session:
            self.create_new_session()

        # 显示用户消息
        self.console.print()

        # 处理消息中的文件路径，将其转换为链接和完整路径
        from rich.text import Text as RichText
        import re

        display_text = RichText()

        # 查找所有 @文件路径 模式（支持更多字符）
        parts = re.split(r'(@[^\s]+)', message)

        # 用于存储转换后的消息（发送给 AI）
        ai_message_parts = []

        for part in parts:
            if part.startswith('@'):
                # 这是文件路径，移除 @ 前缀
                file_path = part[1:]

                # 获取完整的绝对路径
                abs_path = os.path.abspath(file_path)

                # 显示：带链接的相对路径
                display_text.append(part, style="bold bright_cyan link file://" + abs_path)

                # 发送给 AI：完整的绝对路径
                ai_message_parts.append(f"@{abs_path}")
            else:
                # 普通文本
                display_text.append(part, style="white")
                ai_message_parts.append(part)

        # 构造发送给 AI 的消息（包含完整路径）
        ai_message = "".join(ai_message_parts)

        user_panel = Panel.fit(
            display_text,
            title="[bold bright_blue]You[/bold bright_blue]",
            border_style="bright_blue",
        )
        self.console.print(user_panel)
        self.console.print()

        # 流式输出处理
        first_output = True
        last_was_newline = False

        try:
            # 显示 Assistant 标题
            self.console.print("[bold bright_green]Assistant:[/bold bright_green]")
            self.console.print()

            # 使用转换后的消息（包含完整路径）
            async for output in run_agent(
                    message=ai_message, thread_id=self.current_session.thread_id
            ):
                if output:
                    output_str = str(output)

                    # 如果输出包含换行符，使用 print（会自动换行）
                    if "\n" in output_str:
                        # 如果上一次不是以换行结束，先打印当前内容
                        self.console.print(output_str)
                        last_was_newline = output_str.endswith("\n")
                    else:
                        # 流式文本块，不换行
                        self.console.print(output_str, end="")
                        sys.stdout.flush()
                        last_was_newline = False

                    first_output = False

            # 如果最后一次输出没有换行，添加一个换行
            if not last_was_newline and not first_output:
                self.console.print()

            # 增加消息计数
            self.current_session.message_count += 1

        except Exception as e:
            logger.error(f"发送消息时出错: {e}", exc_info=True)
            self.console.print()
            error_panel = Panel.fit(
                Text(str(e), style="white"),
                title="[bold red]Error[/bold red]",
                border_style="red",
            )
            self.console.print(error_panel)

        self.console.print()  # 添加空行分隔

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
                        # 普通消息，直接发送
                        await self.send_message(user_input)

                except KeyboardInterrupt:
                    self.console.print()
                    self.console.print("[dim]Use /quit to exit[/dim]")
                    self.console.print()
                    continue
                except EOFError:
                    # Ctrl+D 退出
                    self.console.print()
                    self.console.print(
                        Panel.fit(
                            Text("Thanks for using Coding Copilot!", style="dim"),
                            title="[bold dim]Goodbye[/bold dim]",
                            border_style="dim",
                        )
                    )
                    self.console.print()
                    break

        except Exception as e:
            logger.error(f"运行 CLI 时出错: {e}", exc_info=True)
            self.console.print()
            error_panel = Panel.fit(
                Text(str(e), style="white"),
                title="[bold red]Error[/bold red]",
                border_style="red",
            )
            self.console.print(error_panel)
            self.console.print()
        finally:
            self.console.print()
            self.console.print(
                Panel.fit(
                    Text("Thanks for using Coding Copilot!", style="dim"),
                    title="[bold dim]Goodbye[/bold dim]",
                    border_style="dim",
                )
            )
            self.console.print()

    async def handle_command(self, command: str):
        """处理用户命令"""
        cmd = command.lower().split()[0]

        if cmd in ["/quit", "/exit"]:
            self.console.print()
            self.console.print(
                Panel.fit(
                    Text("Thanks for using Coding Copilot!", style="dim"),
                    title="[bold dim]Goodbye[/bold dim]",
                    border_style="dim",
                )
            )
            self.console.print()
            exit(0)
        elif cmd == "/new":
            self.create_new_session()
        elif cmd == "/sessions":
            await self.list_sessions()
        elif cmd == "/help":
            self.display_help()
        elif cmd == "/menu":
            await self.show_command_menu()
        elif cmd == "/history":
            self.show_history()
        elif cmd == "/clear":
            self.clear_conversation()
        else:
            self.console.print()
            warning_panel = Panel.fit(
                Text(f"Unknown command: {command}\nType /help for available commands", style="yellow"),
                title="[bold yellow]Warning[/bold yellow]",
                border_style="yellow",
            )
            self.console.print(warning_panel)
            self.console.print()

    def show_history(self):
        """显示当前会话历史"""
        if not self.current_session:
            self.console.print()
            self.console.print(
                Panel.fit(
                    Text("No active session", style="dim"),
                    title="[bold yellow]History[/bold yellow]",
                    border_style="yellow",
                )
            )
            self.console.print()
            return

        session_info = Text()
        session_info.append("Session ID: ", style="white")
        session_info.append(self.current_session.thread_id[:8] + "...\n", style="bold bright_cyan")
        session_info.append("Messages: ", style="white")
        session_info.append(f"{self.current_session.message_count}\n", style="bold green")
        session_info.append("Created: ", style="white")
        session_info.append(self.current_session.created_at.strftime("%Y-%m-%d %H:%M:%S"), style="dim")

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

    def clear_conversation(self):
        """清除当前会话"""
        if self.current_session:
            self.console.print()
            self.console.print(
                Panel.fit(
                    Text(f"To clear conversation, create a new session with /new", style="yellow"),
                    title="[bold yellow]Clear Conversation[/bold yellow]",
                    border_style="yellow",
                )
            )
            self.console.print()
        else:
            self.console.print()
            self.console.print(
                Panel.fit(
                    Text("No active session", style="dim"),
                    title="[bold yellow]Clear[/bold yellow]",
                    border_style="yellow",
                )
            )
            self.console.print()


def main():
    """CLI 入口点"""
    # 检查是否在 PyInstaller 打包环境中运行
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        # 打包后：完全禁用所有日志输出
        disable_all_logging()
    else:
        # 开发模式：显示日志
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    # 创建并运行 CLI
    cli = CodingCopilotCLI()
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        cli.console.print()
        cli.console.print(
            Panel.fit(
                Text("Thanks for using Coding Copilot!", style="dim"),
                title="[bold dim]Goodbye[/bold dim]",
                border_style="dim",
            )
        )
        cli.console.print()
    except Exception as e:
        logger.error(f"启动 CLI 时出错: {e}", exc_info=True)
        cli.console.print()
        error_panel = Panel.fit(
            Text(str(e), style="white"),
            title="[bold red]Error[/bold red]",
            border_style="red",
        )
        cli.console.print(error_panel)
        cli.console.print()
        exit(1)


if __name__ == "__main__":
    main()
