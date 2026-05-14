import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

for _module_name in list(sys.modules):
    if _module_name == "app" or _module_name.startswith("app."):
        del sys.modules[_module_name]

from app.agent import root_agent  # noqa: E402

__all__ = ["root_agent"]
