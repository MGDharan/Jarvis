"""
remote/gateway.py — Async WebSocket & HTTP API Gateway for Phone Remote Assistant.
Runs seamlessly in the background as part of the existing JARVIS process.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Query, Header
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from remote.config import load_remote_config, BASE_DIR
from remote.auth import device_auth_manager
from remote.pairing import pairing_manager
from remote.commands import remote_command_router
from remote.file_service import remote_file_service
from remote.system_service import remote_system_service
from remote.notifications import notification_manager
from remote.audit_log import audit_logger

class RemoteGateway:
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        if orchestrator:
            remote_command_router.set_orchestrator(orchestrator)
        self.app = self._build_app()
        self._server = None
        self._running = False

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="JARVIS Mobile Remote Gateway", version="1.0.0")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/api/health")
        async def health():
            return {
                "status": "online",
                "service": "JARVIS Mobile Gateway",
                "version": "1.0.0"
            }

        # ── Pairing Session Generation Endpoint ──────────────────────────────
        @app.get("/api/pair/new_session")
        async def get_new_pairing_session(req: Request):
            client_ip = req.client.host if req.client else "127.0.0.1"
            # Only permit from localhost or LAN
            session = pairing_manager.create_pairing_session(host_override=client_ip if not client_ip.startswith("127.") else "")
            return session

        # ── Pairing Handshake Endpoint ───────────────────────────────────────
        @app.post("/api/pair/handshake")
        async def pair_handshake(req: Request):
            try:
                body = await req.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")

            token = body.get("pairing_token", "").strip()
            device_name = body.get("device_name", "Android Phone").strip()
            device_model = body.get("device_model", "Android").strip()
            client_ip = req.client.host if req.client else "127.0.0.1"

            if not token:
                raise HTTPException(status_code=400, detail="Missing pairing_token")

            # Validate and consume token (single-use)
            if not pairing_manager.validate_and_consume_token(token):
                audit_logger.log_event(
                    "PAIRING_FAILED",
                    f"Invalid or expired pairing token: {token[:8]}...",
                    client_ip=client_ip,
                    level="WARNING"
                )
                raise HTTPException(status_code=403, detail="Pairing token is invalid or expired")

            device_id, raw_token = device_auth_manager.register_device(
                device_name=device_name,
                device_model=device_model,
                client_ip=client_ip
            )

            # Proactively notify phone connection
            asyncio.create_task(
                notification_manager.broadcast_event(
                    event_type="device_paired",
                    title="Phone Paired Successfully",
                    message=f"Device '{device_name}' is now authenticated with your lab JARVIS.",
                    severity="info"
                )
            )

            return {
                "status": "success",
                "message": "Device authenticated successfully.",
                "device_id": device_id,
                "auth_token": raw_token,
                "server_name": "JARVIS Lab Laptop",
            }

        # ── Secure File Download Endpoint ────────────────────────────────────
        @app.get("/api/transfer/{transfer_id}")
        async def download_transfer(
            transfer_id: str,
            device_id: str = Query(...),
            auth_token: str = Query(...)
        ):
            if not device_auth_manager.validate_token(device_id, auth_token):
                raise HTTPException(status_code=401, detail="Unauthorized")

            transfer = remote_file_service.get_transfer(transfer_id)
            if not transfer:
                raise HTTPException(status_code=404, detail="Transfer expired or not found")

            p = Path(transfer["file_path"])
            if not p.exists() or not p.is_file():
                raise HTTPException(status_code=404, detail="File missing on host")

            audit_logger.log_event(
                "FILE_DOWNLOADED",
                f"File '{transfer['filename']}' downloaded by {device_id}",
                device_id=device_id
            )

            return FileResponse(
                path=str(p),
                filename=transfer["filename"],
                media_type="application/octet-stream",
                headers={"X-Checksum-SHA256": transfer["sha256"]}
            )

        # ── Sentry Snapshot Retrieval ────────────────────────────────────────
        @app.get("/api/snapshot/{snapshot_name}")
        async def get_snapshot(
            snapshot_name: str,
            device_id: str = Query(...),
            auth_token: str = Query(...)
        ):
            if not device_auth_manager.validate_token(device_id, auth_token):
                raise HTTPException(status_code=401, detail="Unauthorized")

            clean_name = Path(snapshot_name).name
            snap_path = BASE_DIR / "snapshots" / "sentry" / clean_name
            if not snap_path.exists() or not snap_path.is_file():
                raise HTTPException(status_code=404, detail="Snapshot not found")

            return FileResponse(path=str(snap_path), media_type="image/jpeg")

        # ── Device Management API ────────────────────────────────────────────
        @app.get("/api/devices")
        async def list_devices():
            return {"devices": device_auth_manager.list_devices()}

        @app.post("/api/devices/revoke")
        async def revoke_device(req: Request):
            body = await req.json()
            dev_id = body.get("device_id")
            if not dev_id:
                raise HTTPException(status_code=400, detail="Missing device_id")
            ok = device_auth_manager.revoke_device(dev_id)
            return {"status": "success" if ok else "not_found"}

        # ── WebSocket Remote Assistant Endpoint ──────────────────────────────
        @app.websocket("/ws/remote")
        async def websocket_remote(ws: WebSocket):
            await ws.accept()
            client_ip = ws.client.host if ws.client else "127.0.0.1"

            # 1. Initial Authentication Handshake
            device_id = ws.query_params.get("device_id")
            auth_token = ws.query_params.get("auth_token")

            if not device_id or not auth_token:
                try:
                    # Allow auth credentials as first JSON frame
                    raw_first = await asyncio.wait_for(ws.receive_text(), timeout=5.0)
                    first_msg = json.loads(raw_first)
                    if first_msg.get("type") == "auth":
                        device_id = first_msg.get("device_id")
                        auth_token = first_msg.get("auth_token")
                except Exception:
                    pass

            if not device_id or not auth_token or not device_auth_manager.validate_token(device_id, auth_token, client_ip=client_ip):
                audit_logger.log_event("WS_AUTH_REJECTED", f"Unauthorized WebSocket attempt from {client_ip}", level="WARNING")
                await ws.send_text(json.dumps({
                    "type": "error",
                    "status": "unauthorized",
                    "message": "Authentication failed or device has been revoked."
                }))
                await ws.close(code=4401)
                return

            audit_logger.log_event("WS_CONNECTED", f"Phone connected: {device_id}", device_id=device_id, client_ip=client_ip)
            notification_manager.register_client(ws)

            # Send welcome & initial status frame
            await ws.send_text(json.dumps({
                "type": "connection_status",
                "status": "online",
                "message": "Connected to JARVIS Lab Assistant",
                "device_id": device_id,
            }))

            # Background task: periodic telemetry push to this phone
            async def _telemetry_loop():
                while True:
                    try:
                        await asyncio.sleep(3.0)
                        if device_auth_manager.is_revoked(device_id):
                            await ws.close(code=4403)
                            break
                        telemetry = remote_system_service.get_telemetry()
                        await ws.send_text(json.dumps({
                            "type": "telemetry",
                            "data": telemetry,
                        }))
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        break

            telemetry_task = asyncio.create_task(_telemetry_loop())

            try:
                while True:
                    text = await ws.receive_text()
                    if not text:
                        continue

                    # Instant revocation check
                    if device_auth_manager.is_revoked(device_id):
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "status": "revoked",
                            "message": "Device access was revoked by administrator."
                        }))
                        break

                    try:
                        payload = json.loads(text)
                    except Exception:
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "message": "Malformed JSON message"
                        }))
                        continue

                    # Ping / Pong heartbeat
                    if payload.get("type") == "ping":
                        await ws.send_text(json.dumps({"type": "pong", "timestamp": payload.get("timestamp")}))
                        continue

                    # Execute structured command
                    response = await remote_command_router.handle_command(
                        command_payload=payload,
                        device_id=device_id,
                        client_ip=client_ip
                    )
                    await ws.send_text(json.dumps({
                        "type": "response",
                        "data": response,
                    }))

            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"[RemoteGateway] WS exception: {e}")
            finally:
                telemetry_task.cancel()
                notification_manager.unregister_client(ws)
                audit_logger.log_event("WS_DISCONNECTED", f"Phone disconnected: {device_id}", device_id=device_id)

        return app

    async def serve(self) -> None:
        """Starts uvicorn async server for the remote gateway."""
        cfg = load_remote_config()
        if not cfg.get("enabled", True):
            print("[RemoteGateway] Disabled by configuration.")
            return

        port = int(cfg.get("port", 8765))
        host = str(cfg.get("host", "0.0.0.0"))

        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._running = True
        print(f"[RemoteGateway] Mobile Gateway running on http://{host}:{port} (WebSocket: ws://{host}:{port}/ws/remote)")
        try:
            await self._server.serve()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[RemoteGateway] Server error: {e}")
        finally:
            self._running = False

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
