import sys, runpy
from pathlib import Path

# camera_software root (…/bm_camera/camera_software)
ROOT = Path(__file__).resolve().parents[2]

# Make sure plain 'bm_agent' (run_agent.py, handlers, etc.) is importable
sys.path.insert(0, str(ROOT))              # adds camera_software to sys.path
sys.path.insert(0, str(ROOT / "bm_agent")) # safe belt & suspenders

# Execute the existing agent entrypoint
runpy.run_path(str(ROOT / "bm_agent" / "run_agent.py"), run_name="__main__")
