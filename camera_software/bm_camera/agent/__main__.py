# Allows: python -m bm_camera.agent
import sys, runpy
from pathlib import Path

# Locate camera_software root and make it importable
ROOT = Path(__file__).resolve().parents[2]  # .../camera_software
sys.path.insert(0, str(ROOT))

# Execute the existing agent script as __main__
runpy.run_path(str(ROOT / "bm_agent" / "run_agent.py"), run_name="__main__")
