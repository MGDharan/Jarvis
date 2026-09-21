"""
remote/test_client.py — Local development test client simulating the Android phone.
Allows full end-to-end testing of phone ↔ laptop communication directly from the terminal.

Usage:
    python -m remote.test_client
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so emoji in print() doesn't crash
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import websockets
    import requests
except ImportError:
    print("Please install test dependencies: pip install websockets requests")
    sys.exit(1)

from remote.config import BASE_DIR

SESSION_CACHE = BASE_DIR / "data" / "test_client_session.json"

def get_or_create_paired_credentials(host="127.0.0.1", port=8765) -> tuple[str, str]:
    if SESSION_CACHE.exists():
        try:
            data = json.loads(SESSION_CACHE.read_text())
            # Quick check if still authorized
            from remote.auth import device_auth_manager
            if device_auth_manager.validate_token(data["device_id"], data["auth_token"]):
                print(f"[TestClient] Reusing cached session for {data['device_id']}")
                return data["device_id"], data["auth_token"]
        except Exception:
            pass

    # Always fetch the pairing token from the RUNNING gateway HTTP API.
    # Do NOT create a token locally — the gateway has its own independent
    # in-memory/file session store, so locally-created tokens will always
    # fail validation on the gateway side.
    base_url = f"http://{host}:{port}"
    try:
        sess_resp = requests.get(f"{base_url}/api/pair/new_session", timeout=5)
        if sess_resp.status_code != 200:
            raise RuntimeError(
                f"Gateway returned {sess_resp.status_code}: {sess_resp.text}"
            )
        token = sess_resp.json().get("pairing_token", "")
        if not token:
            raise RuntimeError("Gateway returned an empty pairing token.")
    except Exception as e:
        raise RuntimeError(
            f"Cannot reach JARVIS Gateway at {base_url}. "
            f"Is JARVIS running? ({e})"
        )

    resp = requests.post(
        f"http://{host}:{port}/api/pair/handshake",
        json={
            "pairing_token": token,
            "device_name": "Terminal Test Phone (CLI)",
            "device_model": "Simulator"
        },
        timeout=5
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Pairing handshake failed: {resp.text}")

    resp_json = resp.json()
    device_id = resp_json["device_id"]
    auth_token = resp_json["auth_token"]

    SESSION_CACHE.write_text(json.dumps({
        "device_id": device_id,
        "auth_token": auth_token
    }))
    print(f"[TestClient] [OK] Paired successfully as {device_id}")
    return device_id, auth_token

async def run_client():
    host = "127.0.0.1"
    port = 8765
    print(f"[TestClient] Connecting to JARVIS Gateway on {host}:{port}...")

    try:
        device_id, auth_token = get_or_create_paired_credentials(host, port)
    except Exception as e:
        print(f"[TestClient] Pairing error (is JARVIS running?): {e}")
        return

    uri = f"ws://{host}:{port}/ws/remote?device_id={device_id}&auth_token={auth_token}"

    try:
        async with websockets.connect(uri) as ws:
            print(f"[TestClient] [CONNECTED] JARVIS Remote Assistant online!")
            print("Type any question or command (e.g. 'cpu', 'find Gaira', 'open chrome', 'shutdown', 'exit'):\n")

            async def receiver():
                async for message in ws:
                    try:
                        parsed = json.loads(message)
                        msg_type = parsed.get("type")
                        if msg_type == "telemetry":
                            data = parsed.get("data", {})
                            cpu = data.get("cpu_percent")
                            ram = data.get("ram_percent")
                            sys.stdout.write(f"\r[Telemetry] CPU: {cpu}% | RAM: {ram}% | (Type command): ")
                            sys.stdout.flush()
                        elif msg_type == "response":
                            resp = parsed.get("data", {})
                            print(f"\n[JARVIS]: {resp.get('message')}")
                            if resp.get("challenge"):
                                print(f"[!] Action requires confirmation! Challenge ID: {resp['challenge']['challenge_id']}")
                                print("To confirm, type: confirm <challenge_id> <action>")
                            sys.stdout.write("\n> ")
                            sys.stdout.flush()
                        elif msg_type == "notification":
                            notif = parsed.get("data", {})
                            print(f"\n[PUSH] {notif.get('title')}: {notif.get('message')}")
                            sys.stdout.write("\n> ")
                            sys.stdout.flush()
                    except Exception as e:
                        print(f"\n[Raw Message]: {message}")

            recv_task = asyncio.create_task(receiver())

            loop = asyncio.get_event_loop()
            while True:
                user_input = await loop.run_in_executor(None, input, "> ")
                cmd = user_input.strip()
                if not cmd:
                    continue
                if cmd.lower() in ("exit", "quit"):
                    break

                if cmd.startswith("confirm "):
                    parts = cmd.split()
                    chal_id = parts[1]
                    act = parts[2] if len(parts) > 2 else "shutdown"
                    payload = {
                        "request_id": f"req_{int(time.time())}",
                        "type": "command",
                        "command": "confirm_action",
                        "arguments": {"challenge_id": chal_id, "action": act}
                    }
                else:
                    payload = {
                        "request_id": f"req_{int(time.time())}",
                        "type": "command",
                        "command": "voice_query",
                        "arguments": {"query": cmd, "include_audio": False}
                    }

                await ws.send(json.dumps(payload))

            recv_task.cancel()
    except Exception as e:
        print(f"[TestClient] Connection closed: {e}")

if __name__ == "__main__":
    asyncio.run(run_client())
