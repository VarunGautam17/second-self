"""
Streamlit Community Cloud root entrypoint wrapper for SecondSelf.
Executes secondself/app.py dynamically under Streamlit runtime.
"""
import os
import sys
import runpy
from pathlib import Path

# Locate secondself directory
root_dir = Path(__file__).resolve().parent
secondself_dir = root_dir / "secondself"

# Add secondself directory to sys.path
if str(secondself_dir) not in sys.path:
    sys.path.insert(0, str(secondself_dir))

# Change working directory to secondself for relative paths (static/, data/, wiki/, raw/)
os.chdir(secondself_dir)

# Execute secondself/app.py natively as __main__
target_script = secondself_dir / "app.py"
runpy.run_path(str(target_script), run_name="__main__")
