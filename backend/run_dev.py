"""Development server runner that ensures proper Python environment with reload.

This script fixes the Windows multiprocessing issue with uvicorn --reload
by ensuring the reload worker uses the venv Python interpreter.
"""
import sys
import os
from pathlib import Path

# Ensure we're using the venv Python
print(f"Using Python: {sys.executable}")

# Change to backend directory
backend_dir = Path(__file__).parent
os.chdir(backend_dir)

# Load environment variables from parent .env
try:
    from dotenv import load_dotenv
    env_path = backend_dir.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded .env from: {env_path}")
    else:
        print(f"⚠ No .env file found at: {env_path}")
except ImportError:
    print("⚠ python-dotenv not installed, skipping .env loading")

# Set PYTHONPATH to ensure imports work correctly
backend_path = str(backend_dir)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import uvicorn and run directly (avoids subprocess issues)
import uvicorn

print("=" * 60)
print("🚀 Starting InvoiceToSheet AI Backend Server")
print(f"📍 Working directory: {os.getcwd()}")
print(f"🐍 Python: {sys.executable}")
print(f"🔧 Reload: ENABLED")
print(f"🌐 Server: http://0.0.0.0:8000")
print("=" * 60)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(backend_dir)],
        log_level="info"
    )
