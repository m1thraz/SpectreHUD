"""Plain and Pentest-Mode project-state persistence."""

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.atomic_write import atomic_write_bytes, atomic_write_json
from core.crypto_service import (
    DecryptionError,
    KDF_ITERATIONS,
    create_verifier,
    decrypt_bytes,
    derive_key,
    encrypt_bytes,
    verify_password,
)
from core.logger import get_logger
from core.project.validator import validate_project_name
from core.project.lock_service import (
    ProjectLockedError,
    ProjectLockService,
    ProjectSecurityMetaError,
)
from core.project.persistence import (
    PersistFailureReason,
    PersistResult,
    classify_persistence_error,
)
from core.validators import MAX_PROJECT_STATE_FILE_SIZE, is_file_size_valid, validate_project_state

logger = get_logger("projects")
PROJECT_STATE_SCHEMA_VERSION = 1
SECURITY_META_SCHEMA_VERSION = 1
LEGACY_SCHEMA_BACKUP_SUFFIX = ".pre-schema-v1.bak"


class ProjectStateLoadError(Exception):
    """A persisted project snapshot cannot safely become live runtime state."""

    def __init__(self, message: str, failure_reason: PersistFailureReason):
        super().__init__(message)
        self.failure_reason = failure_reason


class ProjectStateCorruptedError(ProjectStateLoadError):
    def __init__(
        self,
        message: str,
        failure_reason: PersistFailureReason = PersistFailureReason.VALIDATION_FAILED,
    ):
        super().__init__(message, failure_reason)


class ProjectSchemaMismatchError(ProjectStateLoadError):
    def __init__(self, message: str):
        super().__init__(message, PersistFailureReason.SCHEMA_MISMATCH)


class ProjectStateStore:
    """Reads and writes validated project state, including Pentest-Mode encryption."""

    def __init__(
        self, project_dir_provider: Callable[[str], Path], lock_service: ProjectLockService
    ):
        self.project_dir_provider = project_dir_provider
        self.lock_service = lock_service

    @staticmethod
    def security_meta_path(project_dir: Path) -> Path:
        return project_dir / "security_meta.json"

    @staticmethod
    def _backup_legacy_file(path: Path) -> Path:
        """Preserve the exact pre-migration bytes before adding schema metadata."""
        backup_path = path.with_name(f"{path.name}{LEGACY_SCHEMA_BACKUP_SUFFIX}")
        if not backup_path.exists():
            atomic_write_bytes(backup_path, path.read_bytes())
        return backup_path

    def load_security_meta(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        path = self.security_meta_path(project_dir)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                metadata = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProjectSecurityMetaError(
                f"Security metadata for '{project_dir.name}' is unreadable."
            ) from exc
        if not isinstance(metadata, dict):
            raise ProjectSchemaMismatchError(
                f"Security metadata for '{project_dir.name}' uses an unsupported schema version."
            )
        if "schema_version" not in metadata:
            migrated_metadata = dict(metadata)
            migrated_metadata["schema_version"] = SECURITY_META_SCHEMA_VERSION
            if not isinstance(migrated_metadata.get("pentest_mode"), bool):
                raise ProjectSecurityMetaError(
                    "Security metadata has an invalid pentest_mode field."
                )
            if migrated_metadata["pentest_mode"]:
                self.validate_security_meta(migrated_metadata)
            try:
                self._backup_legacy_file(path)
                atomic_write_json(path, migrated_metadata, indent=2, ensure_ascii=False)
            except OSError as exc:
                raise ProjectSecurityMetaError(
                    f"Security metadata for '{project_dir.name}' could not be migrated safely."
                ) from exc
            metadata = migrated_metadata
            logger.info("Migrated legacy security metadata for '%s' to schema 1.", project_dir.name)
        elif metadata.get("schema_version") != SECURITY_META_SCHEMA_VERSION:
            raise ProjectSchemaMismatchError(
                f"Security metadata for '{project_dir.name}' uses an unsupported schema version."
            )
        if not isinstance(metadata.get("pentest_mode"), bool):
            raise ProjectSecurityMetaError(
                "Security metadata has an invalid pentest_mode field."
            )
        if metadata["pentest_mode"]:
            self.validate_security_meta(metadata)
        return metadata

    @staticmethod
    def validate_security_meta(metadata: Dict[str, Any]) -> None:
        if (
            not isinstance(metadata, dict)
            or metadata.get("schema_version") != SECURITY_META_SCHEMA_VERSION
            or metadata.get("pentest_mode") is not True
        ):
            raise ProjectSecurityMetaError(
                "Pentest-mode metadata must use the current schema and explicitly enable pentest_mode."
            )
        salt, iterations, verifier = (
            metadata.get("kdf_salt"),
            metadata.get("kdf_iterations"),
            metadata.get("verifier"),
        )
        if (
            not isinstance(salt, str)
            or not isinstance(iterations, int)
            or not isinstance(verifier, str)
        ):
            raise ProjectSecurityMetaError(
                "Security metadata is missing required encryption fields."
            )
        try:
            decoded_salt = base64.b64decode(salt.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ProjectSecurityMetaError(
                "Security metadata contains an invalid KDF salt."
            ) from exc
        if len(decoded_salt) < 16 or iterations < KDF_ITERATIONS or not verifier:
            raise ProjectSecurityMetaError(
                "Security metadata contains unsafe encryption parameters."
            )

    def save_security_meta(
        self, project_dir: Path, metadata: Dict[str, Any]
    ) -> PersistResult[None]:
        try:
            self.validate_security_meta(metadata)
            written = atomic_write_json(
                self.security_meta_path(project_dir), metadata, indent=2, ensure_ascii=False
            )
            return (
                PersistResult.ok()
                if written
                else PersistResult.failed(PersistFailureReason.IO_ERROR)
            )
        except ProjectSecurityMetaError:
            return PersistResult.failed(PersistFailureReason.VALIDATION_FAILED)
        except (OSError, TypeError, ValueError) as exc:
            return PersistResult.failed(classify_persistence_error(exc))

    @staticmethod
    def serialize(state: Dict[str, Any]) -> bytes:
        return json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")

    def write(
        self, path: Path, state: Dict[str, Any], key: Optional[bytes]
    ) -> PersistResult[None]:
        try:
            serialized = self.serialize(state)
            written = (
                atomic_write_bytes(path, encrypt_bytes(key, serialized))
                if key is not None
                else atomic_write_json(path, state, indent=2, ensure_ascii=False)
            )
            return (
                PersistResult.ok()
                if written
                else PersistResult.failed(PersistFailureReason.IO_ERROR)
            )
        except (OSError, TypeError, ValueError) as exc:
            return PersistResult.failed(classify_persistence_error(exc))

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

    def enable_pentest_mode(self, name: str, password: str) -> PersistResult[None]:
        try:
            project_name = validate_project_name(name)
            project_dir = self.project_dir_provider(project_name)
            if self.load_security_meta(project_dir) is not None:
                return PersistResult.failed(PersistFailureReason.VALIDATION_FAILED)
            state = self.load(project_name)
            salt = os.urandom(16)
            key = derive_key(password, salt, KDF_ITERATIONS)
            metadata = {
                "schema_version": SECURITY_META_SCHEMA_VERSION,
                "pentest_mode": True,
                "kdf_salt": base64.b64encode(salt).decode("ascii"),
                "kdf_iterations": KDF_ITERATIONS,
                "verifier": create_verifier(key),
            }
        except ProjectStateLoadError as exc:
            return PersistResult.failed(exc.failure_reason)
        except ProjectSecurityMetaError:
            return PersistResult.failed(PersistFailureReason.VALIDATION_FAILED)
        except (OSError, TypeError, ValueError) as exc:
            return PersistResult.failed(classify_persistence_error(exc))

        metadata_result = self.save_security_meta(project_dir, metadata)
        if not metadata_result.success:
            return metadata_result

        self.lock_service.set_session_key(project_name, key)
        state_result = self.write(project_dir / "project_state.json", state, key)
        if state_result.success:
            return state_result

        self.lock_service.clear()
        rollback_performed = False
        try:
            self.security_meta_path(project_dir).unlink(missing_ok=True)
            rollback_performed = True
        except OSError:
            logger.exception("Failed to roll back Pentest-Mode metadata for %s", project_name)
        return PersistResult.failed(
            state_result.failure_reason or PersistFailureReason.UNKNOWN,
            rollback_performed=rollback_performed,
        )

    def load(self, name: str) -> Dict[str, Any]:
        project_name = validate_project_name(name)
        project_dir = self.project_dir_provider(project_name)
        state_file = project_dir / "project_state.json"
        metadata = self.load_security_meta(project_dir)
        key = None
        if metadata and metadata.get("pentest_mode"):
            key = self.lock_service.get_session_key(project_name)
            if key is None:
                raise ProjectLockedError(
                    f"Project '{project_name}' is locked. Enter its Pentest-Mode password first."
                )
        if state_file.exists():
            if not is_file_size_valid(state_file, MAX_PROJECT_STATE_FILE_SIZE):
                raise ProjectStateCorruptedError(
                    f"Project state for '{project_name}' exceeds the maximum supported size."
                )
            try:
                if key is not None:
                    raw_data = json.loads(
                        decrypt_bytes(key, state_file.read_bytes()).decode("utf-8")
                    )
                else:
                    with state_file.open("r", encoding="utf-8") as file:
                        raw_data = json.load(file)
                if not isinstance(raw_data, dict):
                    raise ProjectSchemaMismatchError(
                        f"Project state for '{project_name}' uses an unsupported schema version."
                    )
                if "schema_version" not in raw_data:
                    migrated_state = validate_project_state(
                        raw_data, fallback_name=project_name
                    )
                    self._backup_legacy_file(state_file)
                    migration_result = self.write(state_file, migrated_state, key)
                    if not migration_result.success:
                        raise ProjectStateCorruptedError(
                            f"Project state for '{project_name}' could not be migrated safely.",
                            migration_result.failure_reason or PersistFailureReason.UNKNOWN,
                        )
                    raw_data = migrated_state
                    logger.info("Migrated legacy project state for '%s' to schema 1.", project_name)
                elif raw_data.get("schema_version") != PROJECT_STATE_SCHEMA_VERSION:
                    raise ProjectSchemaMismatchError(
                        f"Project state for '{project_name}' uses an unsupported schema version."
                    )
                return validate_project_state(raw_data, fallback_name=project_name)
            except ProjectSchemaMismatchError:
                raise
            except (
                DecryptionError,
                json.JSONDecodeError,
                RecursionError,
                OSError,
                UnicodeDecodeError,
            ) as exc:
                raise ProjectStateCorruptedError(
                    f"Project state for '{project_name}' is unreadable or corrupted.",
                    (
                        PersistFailureReason.VALIDATION_FAILED
                        if isinstance(exc, DecryptionError)
                        else classify_persistence_error(exc)
                    ),
                ) from exc
        return validate_project_state(None, fallback_name=project_name)

    def save(
        self, name: str, state: Optional[Dict[str, Any]] = None, **kwargs
    ) -> PersistResult[None]:
        try:
            project_name = validate_project_name(name)
            project_dir = self.project_dir_provider(project_name)
        except (OSError, TypeError, ValueError) as exc:
            return PersistResult.failed(classify_persistence_error(exc))
        if not project_dir.exists() or not project_dir.is_dir():
            logger.error(
                "Refusing to save project '%s': project directory is unavailable at %s.",
                project_name,
                project_dir,
            )
            return PersistResult.failed(PersistFailureReason.IO_ERROR)
        try:
            metadata = self.load_security_meta(project_dir)
        except ProjectStateLoadError as exc:
            return PersistResult.failed(exc.failure_reason)
        except ProjectSecurityMetaError:
            return PersistResult.failed(PersistFailureReason.VALIDATION_FAILED)
        key = None
        if metadata and metadata.get("pentest_mode"):
            key = self.lock_service.get_session_key(project_name)
            if key is None:
                return PersistResult.failed(PersistFailureReason.PROJECT_LOCKED)
        try:
            final_state = self.load(project_name) or {}
        except ProjectLockedError:
            return PersistResult.failed(PersistFailureReason.PROJECT_LOCKED)
        except ProjectStateLoadError as exc:
            return PersistResult.failed(exc.failure_reason)
        if state:
            final_state.update(state)
        final_state.update(kwargs)
        final_state["name"] = project_name
        final_state["schema_version"] = PROJECT_STATE_SCHEMA_VERSION
        final_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            valid_state = validate_project_state(final_state, fallback_name=project_name)
        except (OSError, TypeError, ValueError) as exc:
            logger.error(
                "Error saving project state for %s: %s",
                project_name,
                exc,
                exc_info=isinstance(exc, OSError),
            )
            return PersistResult.failed(classify_persistence_error(exc))
        return self.write(project_dir / "project_state.json", valid_state, key)
