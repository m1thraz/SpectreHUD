"""Plain and Pentest-Mode project-state persistence."""

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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


@dataclass(frozen=True)
class ProjectState:
    schema_version: int
    name: str
    target_ip: str
    attacker_ip: str
    port: str
    username: str
    password: str
    wordlist: str
    created_at: str
    updated_at: str
    loot: List[Dict[str, Any]]
    clipboard_history: List[Dict[str, Any]]
    quick_notes: List[Dict[str, Any]]
    active_phase: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "target_ip": self.target_ip,
            "attacker_ip": self.attacker_ip,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "wordlist": self.wordlist,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "loot": list(self.loot),
            "clipboard_history": list(self.clipboard_history),
            "quick_notes": list(self.quick_notes),
            "active_phase": self.active_phase,
        }


@dataclass(frozen=True)
class SecurityMeta:
    schema_version: int
    pentest_mode: bool
    kdf_salt: Optional[str] = None
    kdf_iterations: Optional[int] = None
    verifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "pentest_mode": self.pentest_mode,
        }
        if self.kdf_salt is not None:
            data["kdf_salt"] = self.kdf_salt
        if self.kdf_iterations is not None:
            data["kdf_iterations"] = self.kdf_iterations
        if self.verifier is not None:
            data["verifier"] = self.verifier
        return data


def validate_and_parse_project_state(
    raw: Dict[str, Any], fallback_name: str = "Default"
) -> ProjectState:
    if not isinstance(raw, dict):
        raise ProjectStateCorruptedError("Project state must be a JSON object.")
    if (
        type(raw.get("schema_version")) is not int
        or raw["schema_version"] != PROJECT_STATE_SCHEMA_VERSION
    ):
        raise ProjectSchemaMismatchError("Project state uses an unsupported schema version.")

    text_fields = (
        "name",
        "target_ip",
        "attacker_ip",
        "port",
        "username",
        "password",
        "wordlist",
        "created_at",
        "updated_at",
    )
    list_fields = ("loot", "clipboard_history", "quick_notes")
    if any(field in raw and not isinstance(raw[field], str) for field in text_fields):
        raise ProjectStateCorruptedError("Project state contains an invalid text field.")
    if any(field in raw and not isinstance(raw[field], list) for field in list_fields):
        raise ProjectStateCorruptedError("Project state contains an invalid collection field.")
    if "active_phase" in raw and raw["active_phase"] is not None and not isinstance(
        raw["active_phase"], str
    ):
        raise ProjectStateCorruptedError("Project state contains an invalid active phase.")

    normalized = validate_project_state(raw, fallback_name=fallback_name)
    for field in list_fields:
        if len(normalized[field]) != len(raw.get(field, [])):
            raise ProjectStateCorruptedError(
                f"Project state contains an invalid entry in '{field}'."
            )
    return ProjectState(**normalized)


def validate_and_parse_security_meta(raw: Dict[str, Any]) -> SecurityMeta:
    if not isinstance(raw, dict):
        raise ProjectSecurityMetaError("Security metadata must be a JSON object.")
    if (
        type(raw.get("schema_version")) is not int
        or raw["schema_version"] != SECURITY_META_SCHEMA_VERSION
    ):
        raise ProjectSchemaMismatchError("Security metadata uses an unsupported schema version.")
    if not isinstance(raw.get("pentest_mode"), bool):
        raise ProjectSecurityMetaError("Security metadata has an invalid pentest_mode field.")

    metadata = SecurityMeta(
        schema_version=raw["schema_version"],
        pentest_mode=raw["pentest_mode"],
        kdf_salt=raw.get("kdf_salt"),
        kdf_iterations=raw.get("kdf_iterations"),
        verifier=raw.get("verifier"),
    )
    if metadata.pentest_mode:
        ProjectStateStore.validate_security_meta(metadata)
    return metadata


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

    def load_security_meta(self, project_dir: Path) -> Optional[SecurityMeta]:
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
            validate_and_parse_security_meta(migrated_metadata)
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
        return validate_and_parse_security_meta(metadata)

    @staticmethod
    def validate_security_meta(metadata: SecurityMeta) -> None:
        if (
            metadata.schema_version != SECURITY_META_SCHEMA_VERSION
            or metadata.pentest_mode is not True
        ):
            raise ProjectSecurityMetaError(
                "Pentest-mode metadata must use the current schema and explicitly enable pentest_mode."
            )
        salt, iterations, verifier = (
            metadata.kdf_salt,
            metadata.kdf_iterations,
            metadata.verifier,
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
        self, project_dir: Path, metadata: SecurityMeta
    ) -> PersistResult[None]:
        try:
            self.validate_security_meta(metadata)
            written = atomic_write_json(
                self.security_meta_path(project_dir),
                metadata.to_dict(),
                indent=2,
                ensure_ascii=False,
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
    def serialize(state: ProjectState) -> bytes:
        return json.dumps(state.to_dict(), indent=2, ensure_ascii=False).encode("utf-8")

    def write(
        self, path: Path, state: ProjectState, key: Optional[bytes]
    ) -> PersistResult[None]:
        try:
            serialized = self.serialize(state)
            written = (
                atomic_write_bytes(path, encrypt_bytes(key, serialized))
                if key is not None
                else atomic_write_json(path, state.to_dict(), indent=2, ensure_ascii=False)
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
        return bool(metadata and metadata.pentest_mode)

    def unlock(self, name: str, password: str) -> bool:
        project_name = validate_project_name(name)
        metadata = self.load_security_meta(self.project_dir_provider(project_name))
        if not metadata or not metadata.pentest_mode:
            return True
        assert metadata.kdf_salt is not None
        assert metadata.kdf_iterations is not None
        assert metadata.verifier is not None
        salt = base64.b64decode(metadata.kdf_salt.encode("ascii"), validate=True)
        key = derive_key(password, salt, metadata.kdf_iterations)
        if not verify_password(key, metadata.verifier):
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
            metadata = SecurityMeta(
                schema_version=SECURITY_META_SCHEMA_VERSION,
                pentest_mode=True,
                kdf_salt=base64.b64encode(salt).decode("ascii"),
                kdf_iterations=KDF_ITERATIONS,
                verifier=create_verifier(key),
            )
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

    def load(self, name: str) -> ProjectState:
        project_name = validate_project_name(name)
        project_dir = self.project_dir_provider(project_name)
        state_file = project_dir / "project_state.json"
        metadata = self.load_security_meta(project_dir)
        key = None
        if metadata and metadata.pentest_mode:
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
                    migrated_state = validate_and_parse_project_state(
                        validate_project_state(raw_data, fallback_name=project_name),
                        fallback_name=project_name,
                    )
                    self._backup_legacy_file(state_file)
                    migration_result = self.write(state_file, migrated_state, key)
                    if not migration_result.success:
                        raise ProjectStateCorruptedError(
                            f"Project state for '{project_name}' could not be migrated safely.",
                            migration_result.failure_reason or PersistFailureReason.UNKNOWN,
                        )
                    raw_data = migrated_state.to_dict()
                    logger.info("Migrated legacy project state for '%s' to schema 1.", project_name)
                elif raw_data.get("schema_version") != PROJECT_STATE_SCHEMA_VERSION:
                    raise ProjectSchemaMismatchError(
                        f"Project state for '{project_name}' uses an unsupported schema version."
                    )
                return validate_and_parse_project_state(raw_data, fallback_name=project_name)
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
        return validate_and_parse_project_state(
            validate_project_state(None, fallback_name=project_name),
            fallback_name=project_name,
        )

    def save(
        self, name: str, state: Optional[ProjectState] = None, **kwargs: Any
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
        if metadata and metadata.pentest_mode:
            key = self.lock_service.get_session_key(project_name)
            if key is None:
                return PersistResult.failed(PersistFailureReason.PROJECT_LOCKED)
        try:
            final_state = self.load(project_name)
        except ProjectLockedError:
            return PersistResult.failed(PersistFailureReason.PROJECT_LOCKED)
        except ProjectStateLoadError as exc:
            return PersistResult.failed(exc.failure_reason)
        if state is not None:
            final_state = state
        final_data = final_state.to_dict()
        final_data.update(kwargs)
        final_data["name"] = project_name
        final_data["schema_version"] = PROJECT_STATE_SCHEMA_VERSION
        final_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            valid_state = validate_and_parse_project_state(
                final_data, fallback_name=project_name
            )
        except ProjectStateLoadError as exc:
            return PersistResult.failed(exc.failure_reason)
        except (OSError, TypeError, ValueError) as exc:
            logger.error(
                "Error saving project state for %s: %s",
                project_name,
                exc,
                exc_info=isinstance(exc, OSError),
            )
            return PersistResult.failed(classify_persistence_error(exc))
        return self.write(project_dir / "project_state.json", valid_state, key)
