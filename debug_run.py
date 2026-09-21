#!/usr/bin/env python
"""Debug wrapper for JARVIS"""
import sys
import traceback

try:
    sys.path.insert(0, r'f:\jarvis\jarvis')
    
    print("[DEBUG] Python version:", sys.version)
    print("[DEBUG] Loading config...")
    import json
    config = json.load(open(r'f:\jarvis\jarvis\config\api_keys.json'))
    print("[DEBUG] Config loaded OK")
    print("[DEBUG] Xkiro API key:", "✅" if config.get('xkiro_api_key') else "❌")
    
    print("[DEBUG] Importing main...")
    from main import main
    
    print("[DEBUG] Starting JARVIS...")
    main()
    
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    traceback.print_exc()
    with open(r'f:\jarvis\jarvis\error.log', 'w') as f:
        traceback.print_exc(file=f)
    print("[ERROR] Full traceback saved to error.log")
