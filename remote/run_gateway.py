"""
remote/run_gateway.py — Standalone JARVIS Mobile Gateway launcher.

Starts ONLY the HTTP/WebSocket gateway (no JARVIS UI, no audio, no Gemini).
Useful for testing the phone <-> laptop connection before launching full JARVIS.

Usage:
    python -m remote.run_gateway

Keep this running in a terminal, then in another terminal run:
    python -m remote.test_client
"""
from __future__ import annotations

import asyncio
import sys

# Force UTF-8 on Windows consoles
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from remote.config import load_remote_config
from remote.gateway import RemoteGateway


async def main():
    cfg = load_remote_config()
    port = cfg.get("port", 8765)
    host = cfg.get("host", "0.0.0.0")

    print("=" * 60)
    print("  JARVIS Mobile Gateway (standalone mode)")
    print("=" * 60)
    print(f"  Gateway URL : http://{host}:{port}")
    print(f"  WebSocket   : ws://{host}:{port}/ws/remote")
    print(f"  Health      : http://127.0.0.1:{port}/api/health")
    print()
    print("  [!] Running WITHOUT full JARVIS (no AI, no audio).")
    print("  [!] Voice commands will return a stub response.")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    gateway = RemoteGateway(orchestrator=None)
    await gateway.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Gateway] Stopped.")
