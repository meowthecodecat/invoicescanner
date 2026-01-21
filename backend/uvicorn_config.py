"""Uvicorn configuration that ensures reload works properly with venv."""
import sys
import os
from pathlib import Path

# Get the backend directory
backend_dir = Path(__file__).parent
root_dir = backend_dir.parent

# Load environment variables from root .env
try:
    from dotenv import load_dotenv
    env_file = root_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

# Ensure the venv site-packages are in sys.path
# This fixes the issue with multiprocessing spawn on Windows
venv_site_packages = Path(sys.prefix) / "Lib" / "site-packages"
if venv_site_packages.exists() and str(venv_site_packages) not in sys.path:
    sys.path.insert(0, str(venv_site_packages))

# Add backend directory to path
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
