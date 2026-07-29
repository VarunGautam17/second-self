"""
Streamlit Community Cloud root entrypoint wrapper for SecondSelf.
Delegates to secondself/app.py while ensuring sys.path and working directory are correctly aligned.
"""
import os
import sys
from pathlib import Path

# Locate secondself directory
root_dir = Path(__file__).resolve().parent
secondself_dir = root_dir / "secondself"

# Add secondself directory to sys.path
if str(secondself_dir) not in sys.path:
    sys.path.insert(0, str(secondself_dir))

# Change working directory to secondself for relative paths (static/, data/, wiki/, raw/)
os.chdir(secondself_dir)

# Run secondself app
import app  # noqa: E402
