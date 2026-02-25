#!/usr/bin/env python3
"""Quick test to import api module"""

import sys
import os
import pathlib

# Add apps/api to path so imports resolve correctly
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

try:
    print(f"Current working directory: {os.getcwd()}")
    print(f"sys.path (first 3): {sys.path[:3]}")
    print("\nAttempting to import 'app' module...")
    import app
    print("✓ app module imported successfully")
    print(f"  app.__file__: {app.__file__}")
    
    print("\nAttempting to import 'api' module...")
    import api
    print("✓ api module imported successfully")
    print(f"  api.app: {api.app}")
    print(f"  api.app type: {type(api.app)}")
    
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
