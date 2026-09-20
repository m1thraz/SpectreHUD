"""Canonical project-scoped variables shared by persistence and snippet interpolation."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final, Mapping, TypedDict, cast

from core.validators import MAX_TARGET_IP_LENGTH


PROJECT_VARIABLE_DEFAULTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "target_ip": "10.10.10.10",
        "attacker_ip": "10.10.14.5",
        "port": "4444",
        "username": "",
        "password": "",
        "domain": "",
        "ntlm_hash": "",
        "hash": "",
        "hash_file": "",
        "wordlist": "/usr/share/wordlists/dirb/common.txt",
        "url": "",
        "subnet": "",
        "dns_server": "",
        "dns": "",
    }
)
PROJECT_VARIABLE_KEYS: Final[tuple[str, ...]] = tuple(PROJECT_VARIABLE_DEFAULTS)

_PROJECT_VARIABLE_MAX_LENGTHS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "target_ip": MAX_TARGET_IP_LENGTH,
        "attacker_ip": MAX_TARGET_IP_LENGTH,
        "port": 32,
        "username": 1024,
        "password": 1024,
        "domain": 1024,
        "ntlm_hash": 1024,
        "hash": 1024,
        "hash_file": 1024,
        "wordlist": 1024,
        "url": 2048,
        "subnet": 1024,
        "dns_server": 1024,
        "dns": 1024,
    }
)


class ProjectVariables(TypedDict):
    target_ip: str
    attacker_ip: str
    port: str
    username: str
    password: str
    domain: str
    ntlm_hash: str
    hash: str
    hash_file: str
    wordlist: str
    url: str
    subnet: str
    dns_server: str
    dns: str


def normalize_project_variables(data: Mapping[str, Any] | None) -> ProjectVariables:
    """Return the complete bounded project-variable set with stable defaults."""
    source = data or {}
    normalized = {
        key: str(source.get(key) or default)[:_PROJECT_VARIABLE_MAX_LENGTHS[key]]
        for key, default in PROJECT_VARIABLE_DEFAULTS.items()
    }
    return cast(ProjectVariables, normalized)
