"""Plain and Pentest-Mode project-state persistence."""

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.atomic_write import atomic_write_bytes, atomic_write_json
from core.crypto_service import KDF_ITERATIONS, create_verifier, decrypt_bytes, derive_key, encrypt_bytes, verify_password
from core.logger import get_logger
from core.project.validator import validate_project_name
from core.project_lock_service import ProjectLockedError, ProjectLockService, ProjectSecurityMetaError
from core.validators import MAX_PROJECT_STATE_FILE_SIZE, is_file_size_valid, validate_project_state

logger = get_logger("projects")


class ProjectStateStore:
    """Reads and writes validated project state, including Pentest-Mode encryption."""

    def __init__(self, project_dir_provider: Callable[[str], Path], lock_service: ProjectLockService):
        self.project_dir_provider = project_dir_provider
        self.lock_service = lock_service

    @staticmethod
    def security_meta_path(project_dir: Path) -> Path:
        return project_dir / "security_meta.json"

    def load_security_meta(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        path = self.security_meta_path(project_dir)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                metadata = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProjectSecurityMetaError(f"Security metadata for '{project_dir.name}' is unreadable.") from exc
        if not isinstance(metadata, dict) or not isinstance(metadata.get("pentest_mode"), bool):
            raise ProjectSecurityMetaError("Security metadata has an invalid pentest_mode field.")
        if metadata["pentest_mode"]:
            self.validate_security_meta(metadata)
        return metadata

    @staticmethod
    def validate_security_meta(metadata: Dict[str, Any]) -> None:
        if not isinstance(metadata, dict) or metadata.get("pentest_mode") is not True:
            raise ProjectSecurityMetaError("Pentest-mode metadata must explicitly enable pentest_mode.")
        salt, iterations, verifier = metadata.get("kdf_salt"), metadata.get("kdf_iterations"), metadata.get("verifier")
        if not isinstance(salt, str) or not isinstance(iterations, int) or not isinstance(verifier, str):
            raise ProjectSecurityMetaError("Security metadata is missing required encryption fields.")
        try:
            decoded_salt = base64.b64decode(salt.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ProjectSecurityMetaError("Security metadata contains an invalid KDF salt.") from exc
        if len(decoded_salt) < 16 or iterations < KDF_ITERATIONS or not verifier:
            raise ProjectSecurityMetaError("Security metadata contains unsafe encryption parameters.")

    def save_security_meta(self, project_dir: Path, metadata: Dict[str, Any]) -> bool:
        self.validate_security_meta(metadata)
        return atomic_write_json(self.security_meta_path(project_dir), metadata, indent=2, ensure_ascii=False)

    @staticmethod
    def serialize(state: Dict[str, Any]) -> bytes:
        return json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")

    def write(self, path: Path, state: Dict[str, Any], key: Optional[bytes]) -> bool:
        serialized = self.serialize(state)
        return atomic_write_bytes(path, encrypt_bytes(key, serialized)) if key is not None else atomic_write_json(path, state, indent=2, ensure_ascii=False)

    def is_pentest_mode(self, name: str) -> bool:
        metadata = self.load_security_meta(self.project_dir_provider(validate_project_name(name)))
        return bool(metadata and metadata.get("pentest_mode"))

    def unlock(self, name: str, password: str) -> bool:
        project_name = validate_project_name(name)
        metadata = self.load_security_meta(self.project_dir_provider(project_name))
        if not metadata or not metadata.get("pentest_mode"):
            return True
        salt = base64.b64decode(metadata["kdf_salt"].encode("ascii"), validate=True)
        key = derive_key(password, salt, metadata["kdf_iterations"])
        if not verify_password(key, metadata["verifier"]):
            return False
        self.lock_service.set_session_key(project_name, key)
        return True

    def enable_pentest_mode(self, name: str, password: str) -> None:
        project_name = validate_project_name(name)
        project_dir = self.project_dir_provider(project_name)
        if self.load_security_meta(project_dir) is not None:
            raise ProjectSecurityMetaError("Pentest mode is already configured for this project.")
        state = self.load(project_name)
        salt = os.urandom(16)
        key = derive_key(password, salt, KDF_ITERATIONS)
        metadata = {
            "pentest_mode": True,
            "kdf_salt": base64.b64encode(salt).decode("ascii"),
            "kdf_iterations": KDF_ITERATIONS,
            "verifier": create_verifier(key),
        }
        self.save_security_meta(project_dir, metadata)
        self.lock_service.set_session_key(project_name, key)
        try:
            self.write(project_dir / "project_state.json", state, key)
        except Exception:
            self.lock_service.clear()
            try:
                self.security_meta_path(project_dir).unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to roll back Pentest-Mode metadata for %s", project_name)
            raise

    def load(self, name: str) -> Dict[str, Any]:
        project_name = validate_project_name(name)
        project_dir = self.project_dir_provider(project_name)
        state_file = project_dir / "project_state.json"
        metadata = self.load_security_meta(project_dir)
        key = None
        if metadata and metadata.get("pentest_mode"):
            key = self.lock_service.get_session_key(project_name)
            if key is None:
                raise ProjectLockedError(f"Project '{project_name}' is locked. Enter its Pentest-Mode password first.")
        if state_file.exists():
            if not is_file_size_valid(state_file, MAX_PROJECT_STATE_FILE_SIZE):
                logger.error("Project state file %s exceeds maximum size limit.", state_file)
                return validate_project_state(None, fallback_name=project_name)
            try:
                if key is not None:
                    raw_data = json.loads(decrypt_bytes(key, state_file.read_bytes()).decode("utf-8"))
                else:
                    with state_file.open("r", encoding="utf-8") as file:
                        raw_data = json.load(file)
                return validate_project_state(raw_data, fallback_name=project_name)
            except (json.JSONDecodeError, RecursionError, OSError, UnicodeDecodeError) as exc:
                logger.error("Error loading project state for %s: %s", project_name, exc)
        return validate_project_state(None, fallback_name=project_name)

    def save(self, name: str, state: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
        project_name = validate_project_name(name)
        project_dir = self.project_dir_provider(project_name)
        if not project_dir.exists() or not project_dir.is_dir():
            logger.error("Refusing to save project '%s': project directory is unavailable at %s.", project_name, project_dir)
            return False
        metadata = self.load_security_meta(project_dir)
        key = None
        if metadata and metadata.get("pentest_mode"):
            key = self.lock_service.get_session_key(project_name)
            if key is None:
                return False
        try:
            final_state = self.load(project_name) or {}
        except ProjectLockedError:
            return False
        if state:
            final_state.update(state)
        final_state.update(kwargs)
        final_state["name"] = project_name
        final_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        valid_state = validate_project_state(final_state, fallback_name=project_name)
        try:
            return self.write(project_dir / "project_state.json", valid_state, key)
        except (OSError, TypeError, ValueError) as exc:
            logger.error("Error saving project state for %s: %s", project_name, exc, exc_info=isinstance(exc, OSError))
            return False
