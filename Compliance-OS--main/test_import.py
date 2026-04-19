
import sys
import os
# Add current directory to path
sys.path.append(os.getcwd())

print("Testing import of backend.app...")
try:
    from backend import app
    print("Success!")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
