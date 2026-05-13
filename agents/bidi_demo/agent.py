from pathlib import Path
import sys

_PROJECT_DIR = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from app.google_search_agent.agent import agent as root_agent  # noqa: E402

__all__ = ["root_agent"]
