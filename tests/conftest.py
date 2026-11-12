import subprocess
import sys
from pathlib import Path

SNAP = Path(__file__).parent / "snapshot.json"
if not SNAP.exists():
    subprocess.run([sys.executable, str(Path(__file__).parent / "build_fixture.py"), str(SNAP)], check=True)
