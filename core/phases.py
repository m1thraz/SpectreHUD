"""Centralized Pentesting Phase Taxonomy and Normalization."""

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple


@dataclass(frozen=True)
class Phase:
    """Represents a standardized pentest phase."""

    key: str
    short: str  # Short badge label, e.g. "RECON", "ACCESS"
    long: str  # Detailed description / tooltip, e.g. "Reconnaissance & Enumeration"
    order: int
    icon: str = ""


PHASES: Tuple[Phase, ...] = (
    Phase(
        key="recon",
        short="RECON",
        long="Reconnaissance & Enumeration",
        order=1,
    ),
    Phase(
        key="access",
        short="ACCESS",
        long="Initial Access & Exploitation",
        order=2,
    ),
    Phase(
        key="privesc",
        short="PRIVESC",
        long="Privilege Escalation",
        order=3,
    ),
    Phase(
        key="postex",
        short="POSTEX",
        long="Post-Exploitation & Lateral Movement",
        order=4,
    ),
    Phase(
        key="scripts",
        short="SCRIPTS",
        long="Custom Scripts & PoCs",
        order=5,
    ),
    Phase(
        key="misc",
        short="MISC",
        long="Miscellaneous",
        order=6,
    ),
)

PHASES_BY_KEY: Dict[str, Phase] = {p.key: p for p in PHASES}
VALID_PHASE_KEYS: Set[str] = set(PHASES_BY_KEY.keys())
DEFAULT_PHASE_KEY: str = "misc"

PHASE_ALIASES: Dict[str, str] = {
    # Synonyms & shorthand
    "initial": "access",
    "init": "access",
    "lateral": "postex",
    "latmove": "postex",
    "poc": "scripts",
    "pocs": "scripts",
    "script": "scripts",
    "tools": "scripts",
    "persist": "postex",
    "persistence": "postex",
    "enumeration": "recon",
    "enum": "recon",
    "privilege_escalation": "privesc",
    "post_exploitation": "postex",
    "general": "misc",
    "other": "misc",
    # Numbered prefixes / Legacy titles
    "1. reconnaissance & enumeration": "recon",
    "2. initial access & exploitation": "access",
    "3. privilege escalation": "privesc",
    "4. post-exploitation & lateral movement": "postex",
    "5. custom scripts & pocs": "scripts",
    "6. miscellaneous": "misc",
    "1. recon": "recon",
    "2. access": "access",
    "3. privesc": "privesc",
    "4. postex": "postex",
    "5. scripts": "scripts",
    "6. misc": "misc",
}


def normalize_phase_key(val: Optional[str]) -> str:
    """Normalize any string (key, alias, or legacy title) to a canonical phase key."""
    if not val:
        return DEFAULT_PHASE_KEY

    clean = str(val).strip().lower()
    if clean in PHASES_BY_KEY:
        return clean

    if clean in PHASE_ALIASES:
        return PHASE_ALIASES[clean]

    # Check by short name match (e.g. "RECON", "ACCESS")
    for phase in PHASES:
        if clean == phase.short.lower():
            return phase.key

    # Check by long title match (e.g. "Reconnaissance & Enumeration")
    for phase in PHASES:
        if clean == phase.long.lower():
            return phase.key

    # Check order digit match (e.g. "1", "2")
    if clean.isdigit():
        num = int(clean)
        for phase in PHASES:
            if phase.order == num:
                return phase.key

    # Check if starts with e.g. "1." or "2."
    if len(clean) >= 2 and clean[0].isdigit() and clean[1] == ".":
        num = int(clean[0])
        for phase in PHASES:
            if phase.order == num:
                return phase.key

    return DEFAULT_PHASE_KEY


def get_phase(name_or_key: Optional[str]) -> Phase:
    """Resolve a key, alias, or legacy title into a canonical Phase object."""
    key = normalize_phase_key(name_or_key)
    return PHASES_BY_KEY.get(key, PHASES_BY_KEY[DEFAULT_PHASE_KEY])
