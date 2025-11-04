"""
Entry point for the Coding Copilot CLI.

This module imports and runs the main CLI application.
"""

from src.cli.cli_app import main

# Re-export for direct execution
__all__ = ['main']

if __name__ == "__main__":
    main()
