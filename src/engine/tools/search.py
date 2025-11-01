"""Search tools for code exploration"""
from pathlib import Path
from typing import Optional
import re
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GlobInput(BaseModel):
    """Input for glob tool"""
    pattern: str = Field(description="Glob pattern to match files (e.g., '**/*.py', 'src/**/*test*.ts')")
    base_path: Optional[str] = Field(default=".", description="Base directory to search from")


class GrepInput(BaseModel):
    """Input for grep tool"""
    pattern: str = Field(description="Regex pattern to search for")
    path: Optional[str] = Field(default=".", description="File or directory to search in")
    file_pattern: Optional[str] = Field(default=None, description="File pattern to filter (e.g., '*.py')")
    case_insensitive: bool = Field(default=False, description="Case insensitive search")
    context_lines: int = Field(default=0, description="Number of context lines to show")
    max_results: int = Field(default=100, description="Maximum number of results")


@tool("glob", args_schema=GlobInput)
def glob_search(pattern: str, base_path: str = ".") -> str:
    """
    Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., '**/*.py', 'src/**/*test*.ts')
        base_path: Base directory to search from

    Returns:
        List of matching file paths
    """
    try:
        base = Path(base_path)
        if not base.exists():
            return f"Error: Base path not found: {base_path}"

        # Use glob to find matching files
        matches = list(base.glob(pattern))

        # Filter out directories
        files = [str(m.relative_to(base)) for m in matches if m.is_file()]

        if not files:
            return f"No files found matching pattern: {pattern}"

        # Sort by modification time (most recent first)
        files.sort(key=lambda f: Path(base / f).stat().st_mtime, reverse=True)

        result = f"Found {len(files)} file(s) matching '{pattern}':\n\n"
        result += "\n".join(f"  {f}" for f in files[:50])

        if len(files) > 50:
            result += f"\n\n... and {len(files) - 50} more files"

        return result

    except Exception as e:
        return f"Error in glob search: {str(e)}"


@tool("grep", args_schema=GrepInput)
def grep_search(
    pattern: str,
    path: str = ".",
    file_pattern: Optional[str] = None,
    case_insensitive: bool = False,
    context_lines: int = 0,
    max_results: int = 100
) -> str:
    """
    Search for pattern in files (like grep/ripgrep).

    Args:
        pattern: Regex pattern to search for
        path: File or directory to search in
        file_pattern: File pattern to filter (e.g., '*.py')
        case_insensitive: Case insensitive search
        context_lines: Number of context lines to show
        max_results: Maximum number of results

    Returns:
        Matching lines with file and line numbers
    """
    try:
        search_path = Path(path)
        if not search_path.exists():
            return f"Error: Path not found: {path}"

        # Compile regex
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)

        # Determine files to search
        if search_path.is_file():
            files = [search_path]
        else:
            # Search directory
            if file_pattern:
                files = list(search_path.glob(f"**/{file_pattern}"))
            else:
                files = list(search_path.glob("**/*"))

            # Filter to only files
            files = [f for f in files if f.is_file()]

        results = []
        total_matches = 0

        for file in files:
            try:
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        total_matches += 1
                        if total_matches <= max_results:
                            # Build result with context
                            result_lines = []

                            # Context before
                            for j in range(max(0, i - context_lines - 1), i - 1):
                                result_lines.append(f"  {j + 1:6d}  {lines[j].rstrip()}")

                            # Matching line
                            result_lines.append(f"→ {i:6d}  {line.rstrip()}")

                            # Context after
                            for j in range(i, min(len(lines), i + context_lines)):
                                result_lines.append(f"  {j + 1:6d}  {lines[j].rstrip()}")

                            results.append(
                                f"{file.relative_to(Path.cwd()) if search_path.is_dir() else file.name}:\n"
                                + "\n".join(result_lines)
                            )

            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

        if not results:
            return f"No matches found for pattern: {pattern}"

        header = f"Found {total_matches} match(es) for '{pattern}'"
        if total_matches > max_results:
            header += f" (showing first {max_results})"
        header += ":\n\n"

        return header + "\n\n".join(results)

    except re.error as e:
        return f"Error: Invalid regex pattern: {str(e)}"
    except Exception as e:
        return f"Error in grep search: {str(e)}"


# Export all search tools
search_tools = [glob_search, grep_search]
