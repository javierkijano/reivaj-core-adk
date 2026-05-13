from pathlib import Path
import sys

_SERVER_DIR = Path(__file__).resolve().parent / "server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

for _module_name in list(sys.modules):
    if _module_name == "example_agent" or _module_name.startswith("example_agent."):
        del sys.modules[_module_name]

from example_agent.agent import root_agent  # noqa: E402

__all__ = ["root_agent"]
