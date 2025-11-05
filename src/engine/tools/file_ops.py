"""File operation tools"""
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


# 需要排除的 SDK 和构建目录
EXCLUDED_DIRS = {
    '.venv',
    'venv',
    'env',
    '.env',
    'dist',
    'build',
    '__pycache__',
    '.git',
    '.idea',
    '.vscode',
    'node_modules',
    '.pytest_cache',
    '.mypy_cache',
    '.tox',
    'eggs',
    '.eggs',
    '*.egg-info',
}


def should_exclude_path(path: Path) -> bool:
    """
    检查路径是否应该被排除

    Args:
        path: 要检查的路径

    Returns:
        True 如果应该排除，False 否则
    """
    try:
        # 检查路径的每一部分是否在排除列表中
        for part in path.parts:
            if part in EXCLUDED_DIRS or part.startswith('.'):
                return True
        return False
    except Exception:
        return False


class ReadFileInput(BaseModel):
    """Input for read_file tool"""
    file_path: str = Field(description="Path to the file to read")
    start_line: Optional[int] = Field(default=None, description="Starting line number (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="Ending line number (1-indexed)")


class WriteFileInput(BaseModel):
    """Input for write_file tool"""
    file_path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


class EditFileInput(BaseModel):
    """Input for edit_file tool"""
    file_path: str = Field(description="Path to the file to edit")
    old_string: str = Field(description="String to replace")
    new_string: str = Field(description="Replacement string")
    replace_all: bool = Field(default=False, description="Replace all occurrences")


@tool("read_file", args_schema=ReadFileInput)
def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    Read contents of a file, optionally with line range.

    Args:
        file_path: Path to the file to read
        start_line: Starting line number (1-indexed), optional
        end_line: Ending line number (1-indexed), optional

    Returns:
        File contents or error message
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        if not path.is_file():
            return f"Error: Not a file: {file_path}"

        # Check if this is an SDK/build directory file and warn
        warning = ""
        if should_exclude_path(path):
            warning = "⚠️ Warning: Reading from SDK/build directory. Consider reading project source files instead.\n\n"

        # Use errors='replace' to handle invalid characters
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Apply line range if specified
        if start_line is not None or end_line is not None:
            start = (start_line - 1) if start_line else 0
            end = end_line if end_line else len(lines)
            lines = lines[start:end]

        # Add line numbers
        numbered_lines = [
            f"{i + (start_line or 1):6d}\t{line.rstrip()}"
            for i, line in enumerate(lines)
        ]

        return warning + "\n".join(numbered_lines)

    except UnicodeDecodeError:
        return f"Error: Cannot read file (binary or encoding issue): {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool("write_file", args_schema=WriteFileInput)
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file, creating it if it doesn't exist.

    Args:
        file_path: Path to the file to write
        content: Content to write

    Returns:
        Success or error message
    """
    try:
        path = Path(file_path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Check if overwriting existing file
        existed = path.exists()

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        action = "Updated" if existed else "Created"
        lines = content.count("\n") + 1
        return f"{action} {file_path} ({lines} lines)"

    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool("edit_file", args_schema=EditFileInput)
def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """
    Edit a file by replacing strings.

    Args:
        file_path: Path to the file to edit
        old_string: String to find and replace
        new_string: Replacement string
        replace_all: If True, replace all occurrences; if False, replace only first

    Returns:
        Success or error message
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: String not found in file: '{old_string[:50]}...'"

        # Count occurrences
        count = content.count(old_string)

        if not replace_all and count > 1:
            return (
                f"Error: Found {count} occurrences of the string. "
                f"Please provide more context or use replace_all=True"
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        replaced_count = count if replace_all else 1
        return f"Replaced {replaced_count} occurrence(s) in {file_path}"

    except Exception as e:
        return f"Error editing file: {str(e)}"


# Export all tools
file_tools = [read_file, write_file, edit_file]
