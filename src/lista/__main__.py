"""统一入口：直接重定向到 Typer 版 CLI (lista.cli.app)"""
from .cli.app import main_entry as main

if __name__ == '__main__':
    main()

