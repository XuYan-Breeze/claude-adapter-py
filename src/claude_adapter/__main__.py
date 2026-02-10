"""Main entry point for running as a module
作为模块运行的主入口点

Allows running: python -m claude_adapter
允许运行：python -m claude_adapter
"""

from .cli import cli_main

if __name__ == "__main__":
    cli_main()
