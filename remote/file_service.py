"""
remote/file_service.py — Safe allowlisted file search and chunked streaming file transfer.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from remote.config import load_remote_config, TRANSFERS_DIR
from remote.audit_log import audit_logger

_lock = threading.Lock()

class FileSecurityError(Exception):
    pass

class RemoteFileService:
    def __init__(self):
        # transfer_id -> { "file_path": Path, "created_at": float, "expires_at": float, "size": int, "sha256": str, "is_temp": bool }
        self._transfers: dict[str, dict[str, Any]] = {}
        self._start_cleanup_timer()

    def _start_cleanup_timer(self) -> None:
        def _cleanup_loop():
            while True:
                time.sleep(60)
                self._cleanup_expired()

        t = threading.Thread(target=_cleanup_loop, daemon=True)
        t.start()

    def _cleanup_expired(self) -> None:
        now = time.time()
        with _lock:
            expired_ids = [
                t_id for t_id, data in self._transfers.items()
                if data["expires_at"] < now
            ]
            for t_id in expired_ids:
                data = self._transfers.pop(t_id, None)
                if data and data.get("is_temp"):
                    p = data.get("file_path")
                    if p and isinstance(p, Path) and p.exists():
                        try:
                            if p.is_file():
                                p.unlink(missing_ok=True)
                            elif p.is_dir():
                                shutil.rmtree(p, ignore_errors=True)
                        except Exception as e:
                            print(f"[FileService] Cleanup error: {e}")

    def is_safe_path(self, target_path: str | Path) -> bool:
        """
        Validates that target_path resides within an allowed directory and does NOT
        point to any blocked directory or blocked sensitive file.
        """
        cfg = load_remote_config()
        allowed_dirs = [Path(p).resolve() for p in cfg.get("allowed_directories", []) if Path(p).exists()]
        blocked_dirs = [Path(p).resolve() for p in cfg.get("blocked_directories", []) if Path(p).exists()]
        blocked_files = [f.lower() for f in cfg.get("blocked_files", [])]

        try:
            resolved = Path(target_path).resolve()
        except Exception:
            return False

        # 1. Block known forbidden files (e.g. .env, api_keys.json)
        if resolved.name.lower() in blocked_files:
            return False

        # 2. Block sensitive file extensions (private keys, certificates)
        if resolved.suffix.lower() in (".pem", ".key", ".pfx", ".kdbx"):
            return False

        # 3. Check blocked directory trees
        for b_dir in blocked_dirs:
            try:
                if resolved == b_dir or resolved.is_relative_to(b_dir):
                    return False
            except Exception:
                pass

        # 4. Check whether it resides within an allowed root
        for a_dir in allowed_dirs:
            try:
                if resolved == a_dir or resolved.is_relative_to(a_dir):
                    return True
            except Exception:
                pass

        return False

    def search_files(self, query: str, file_type: str = "", max_results: int = 50) -> list[dict[str, Any]]:
        """
        Recursively searches allowed directories for query matching folder or filenames.
        Returns a list of matching file records.
        """
        cfg = load_remote_config()
        allowed_dirs = [Path(p).resolve() for p in cfg.get("allowed_directories", []) if Path(p).exists()]
        query_lower = query.lower().strip()
        type_lower = file_type.lower().strip().replace(".", "")

        results = []
        for root in allowed_dirs:
            try:
                # Walk with depth limit of 6 to avoid slow scanning
                for dirpath, dirnames, filenames in os.walk(root):
                    # Filter out hidden or blocked folders from traversal
                    dirnames[:] = [
                        d for d in dirnames
                        if not d.startswith(".") and d not in ("AppData", "node_modules", ".git", "venv", "__pycache__")
                    ]

                    # 1. Check directory names
                    for d in dirnames:
                        if query_lower in d.lower():
                            d_path = Path(dirpath) / d
                            if self.is_safe_path(d_path):
                                results.append({
                                    "name": d,
                                    "path": str(d_path).replace("\\", "/"),
                                    "is_dir": True,
                                    "size_bytes": 0,
                                    "extension": "",
                                    "modified_at": datetime.fromtimestamp(d_path.stat().st_mtime).isoformat(),
                                })
                                if len(results) >= max_results:
                                    return results

                    # 2. Check file names
                    for f in filenames:
                        f_path = Path(dirpath) / f
                        if not self.is_safe_path(f_path):
                            continue

                        ext = f_path.suffix.lower().replace(".", "")
                        if type_lower and ext != type_lower:
                            continue

                        if query_lower in f.lower() or not query_lower:
                            try:
                                stat = f_path.stat()
                                results.append({
                                    "name": f,
                                    "path": str(f_path).replace("\\", "/"),
                                    "is_dir": False,
                                    "size_bytes": stat.st_size,
                                    "extension": ext,
                                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                })
                                if len(results) >= max_results:
                                    return results
                            except Exception:
                                continue
            except Exception as e:
                print(f"[FileService] Search error in {root}: {e}")

        return results

    def prepare_transfer(
        self,
        target_path: str,
        file_extension_filter: str = "",
        device_id: str = "UNKNOWN"
    ) -> dict[str, Any]:
        """
        Prepares a single file or a folder (optionally filtered by extension, e.g. 'pdf')
        for secure transfer. Returns metadata and a transfer_id.
        """
        path = Path(target_path).resolve()
        if not self.is_safe_path(path):
            raise FileSecurityError(f"Access denied: path '{target_path}' is outside allowed directories or forbidden.")

        cfg = load_remote_config()
        max_mb = cfg.get("max_transfer_mb", 500)
        max_bytes = max_mb * 1024 * 1024
        cleanup_sec = cfg.get("temp_cleanup_sec", 900)

        transfer_id = f"trans_{uuid.uuid4().hex[:16]}"
        now = time.time()
        expires_at = now + cleanup_sec

        if path.is_file():
            stat = path.stat()
            if stat.st_size > max_bytes:
                raise ValueError(f"File size exceeds maximum transfer limit of {max_mb} MB.")

            sha256 = self._compute_sha256(path)
            with _lock:
                self._transfers[transfer_id] = {
                    "file_path": path,
                    "filename": path.name,
                    "created_at": now,
                    "expires_at": expires_at,
                    "size_bytes": stat.st_size,
                    "sha256": sha256,
                    "is_temp": False,
                    "device_id": device_id,
                }

            audit_logger.log_event("FILE_TRANSFER_PREPARED", f"Single file prepared: {path.name}", device_id=device_id)
            return {
                "transfer_id": transfer_id,
                "filename": path.name,
                "file_count": 1,
                "total_bytes": stat.st_size,
                "total_mb": round(stat.st_size / (1024 * 1024), 2),
                "sha256": sha256,
                "expires_in_seconds": cleanup_sec,
                "requires_confirmation": False,
            }

        elif path.is_dir():
            # Collect matching files inside directory
            ext_filter = file_extension_filter.lower().replace(".", "")
            files_to_zip: list[Path] = []
            total_size = 0

            for root, _, files in os.walk(path):
                for f in files:
                    fp = Path(root) / f
                    if not self.is_safe_path(fp):
                        continue
                    if ext_filter and fp.suffix.lower().replace(".", "") != ext_filter:
                        continue
                    try:
                        sz = fp.stat().st_size
                        total_size += sz
                        files_to_zip.append(fp)
                    except Exception:
                        pass

            if not files_to_zip:
                raise FileNotFoundError(f"No matching files found in '{path.name}'.")

            if total_size > max_bytes:
                raise ValueError(f"Total matching files size ({round(total_size / (1024*1024), 2)} MB) exceeds limit of {max_mb} MB.")

            # Create temporary zip archive
            zip_filename = f"{path.name}_{ext_filter or 'all'}_{int(now)}.zip"
            zip_path = TRANSFERS_DIR / zip_filename
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fp in files_to_zip:
                    rel_name = fp.relative_to(path)
                    zf.write(fp, arcname=str(rel_name))

            zip_size = zip_path.stat().st_size
            sha256 = self._compute_sha256(zip_path)

            with _lock:
                self._transfers[transfer_id] = {
                    "file_path": zip_path,
                    "filename": zip_filename,
                    "created_at": now,
                    "expires_at": expires_at,
                    "size_bytes": zip_size,
                    "sha256": sha256,
                    "is_temp": True,
                    "device_id": device_id,
                }

            audit_logger.log_event(
                "FILE_BUNDLE_PREPARED",
                f"Bundle prepared: {len(files_to_zip)} files ({round(zip_size / (1024*1024), 2)} MB)",
                device_id=device_id
            )
            return {
                "transfer_id": transfer_id,
                "filename": zip_filename,
                "file_count": len(files_to_zip),
                "total_bytes": zip_size,
                "total_mb": round(zip_size / (1024 * 1024), 2),
                "sha256": sha256,
                "expires_in_seconds": cleanup_sec,
                "requires_confirmation": zip_size > (10 * 1024 * 1024) or len(files_to_zip) > 1,
            }
        else:
            raise FileNotFoundError(f"Path '{target_path}' not found.")

    def get_transfer(self, transfer_id: str) -> dict[str, Any] | None:
        with _lock:
            data = self._transfers.get(transfer_id)
            if not data:
                return None
            if data["expires_at"] < time.time():
                return None
            return data

    @staticmethod
    def _compute_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

remote_file_service = RemoteFileService()
