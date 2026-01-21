# Backend application package

# This ensures imports work correctly even in uvicorn reload subprocesses
import sys
from pathlib import Path

# Add backend directory to path if not already there
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))