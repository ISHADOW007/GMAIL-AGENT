"""CLI module entry point that forwards execution into the main runner."""
from email_agent.main import main


if __name__ == "__main__":
    raise SystemExit(main())

