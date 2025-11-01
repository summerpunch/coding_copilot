"""Shell execution tools"""
import subprocess
import shlex
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class BashInput(BaseModel):
    """Input for bash tool"""
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(default=30, description="Timeout in seconds")
    working_dir: Optional[str] = Field(default=None, description="Working directory")


@tool("bash", args_schema=BashInput)
def bash_execute(command: str, timeout: int = 30, working_dir: Optional[str] = None) -> str:
    """
    Execute a bash command and return the output.

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds (default: 30)
        working_dir: Working directory for command execution

    Returns:
        Command output (stdout and stderr) or error message
    """
    try:
        # Security: Check for dangerous commands
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            "dd if=/dev",
            "> /dev/sd",
            "fork bomb",
            ":(){ :|:& };:",
        ]

        cmd_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in cmd_lower:
                return f"Error: Dangerous command blocked: {pattern}"

        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
        )

        # Build output
        output_parts = []

        if result.stdout:
            output_parts.append("STDOUT:")
            output_parts.append(result.stdout)

        if result.stderr:
            output_parts.append("STDERR:")
            output_parts.append(result.stderr)

        if result.returncode != 0:
            output_parts.append(f"\nReturn code: {result.returncode}")

        if not output_parts:
            return "Command executed successfully (no output)"

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# Export shell tools
shell_tools = [bash_execute]
