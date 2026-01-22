"""Simple test to verify OpenAI is working correctly."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
backend_dir = Path(__file__).parent
env_path = backend_dir.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded .env from: {env_path}")
else:
    print(f"[WARN] No .env file found")

# Check environment
print(f"\n[INFO] OPENAI_MODEL: {os.getenv('OPENAI_MODEL', 'NOT SET (will use gpt-4o)')}")
print(f"[INFO] OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'MISSING'}")

# Test import
sys.path.insert(0, str(backend_dir))
try:
    from app.services.ai import AIService
    service = AIService()
    print(f"\n[OK] Service initialized")
    print(f"[INFO] Actual model being used: {service.model}")
except Exception as e:
    print(f"\n[ERROR] Failed to initialize: {e}")
    import traceback
    traceback.print_exc()
