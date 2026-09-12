"""Centralized Pentesting Phase Taxonomy and Normalization."""

from dataclasses import dataclass
import re
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
    # Recon / Enumeration
    "recon": "recon",
    "reconnaissance": "recon",
    "enumeration": "recon",
    "enum": "recon",
    "aufklärung": "recon",
    "aufklaerung": "recon",
    "aufklärung & enumeration": "recon",
    "aufklaerung & enumeration": "recon",
    "reconnaissance & enumeration": "recon",
    "service enumeration": "recon",
    "directory enumeration": "recon",
    "port scan": "recon",
    "port scanning": "recon",
    "nmap": "recon",
    "discovery": "recon",
    "footprinting": "recon",
    # Initial Access / Exploitation
    "initial": "access",
    "init": "access",
    "initial access": "access",
    "initialer zugriff": "access",
    "initial access & exploitation": "access",
    "initialer zugriff & exploitation": "access",
    "exploitation": "access",
    "exploit": "access",
    "foothold": "access",
    # Privilege Escalation
    "privesc": "privesc",
    "privilege escalation": "privesc",
    "privilege_escalation": "privesc",
    "rechteausweitung": "privesc",
    "rechteausweitung (privesc)": "privesc",
    "local privilege escalation": "privesc",
    "lpe": "privesc",
    # Post-Exploitation / Lateral Movement
    "lateral": "postex",
    "latmove": "postex",
    "lateral movement": "postex",
    "persist": "postex",
    "persistence": "postex",
    "postex": "postex",
    "post_exploitation": "postex",
    "post-exploitation": "postex",
    "post-exploitation & lateral movement": "postex",
    # Custom Scripts / Tools
    "poc": "scripts",
    "pocs": "scripts",
    "script": "scripts",
    "scripts": "scripts",
    "tools": "scripts",
    "custom scripts": "scripts",
    "custom scripts & pocs": "scripts",
    "eigene skripte": "scripts",
    "eigene skripte & pocs": "scripts",
    # Misc / Other
    "general": "misc",
    "other": "misc",
    "others": "misc",
    "weitere": "misc",
    "sonstiges": "misc",
    "verschiedenes": "misc",
    "unassigned": "misc",
    # Numbered prefixes / Legacy titles (EN & DE)
    "1. reconnaissance & enumeration": "recon",
    "1. aufklärung & enumeration": "recon",
    "1. aufklaerung & enumeration": "recon",
    "2. initial access & exploitation": "access",
    "2. initialer zugriff & exploitation": "access",
    "3. privilege escalation": "privesc",
    "3. rechteausweitung": "privesc",
    "4. post-exploitation & lateral movement": "postex",
    "5. custom scripts & pocs": "scripts",
    "5. eigene skripte & pocs": "scripts",
    "6. miscellaneous": "misc",
    "6. sonstiges": "misc",
    "1. recon": "recon",
    "2. access": "access",
    "3. privesc": "privesc",
    "4. postex": "postex",
    "5. scripts": "scripts",
    "6. misc": "misc",
}


def try_normalize_phase_key(val: Optional[str]) -> Optional[str]:
    """
    Attempt to normalize a string (key, alias, short name, long name, or order)
    to a canonical phase key. Returns None if unrecognized or empty.
    """
    if not val:
        return None

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

    # Token-based heuristic resolution for descriptive/compound phrases
    tokens = set(re.findall(r"[a-z0-9äöüß]+", clean))
    if any(t in tokens for t in ("enum", "enumeration", "recon", "reconnaissance", "aufklärung", "aufklaerung")):
        return "recon"
    if any(t in tokens for t in ("privesc", "rechteausweitung", "lpe")) or ("privilege" in tokens and "escalation" in tokens):
        return "privesc"
    if any(t in tokens for t in ("postex", "persistence", "latmove")) or ("lateral" in tokens and "movement" in tokens) or ("post" in tokens and "exploitation" in tokens):
        return "postex"
    if any(t in tokens for t in ("zugriff", "foothold")) or ("initial" in tokens and "access" in tokens) or "exploitation" in tokens:
        return "access"
    if any(t in tokens for t in ("poc", "pocs", "skripte", "skript", "scripts", "script")):
        return "scripts"
    if any(t in tokens for t in ("sonstiges", "verschiedenes", "weitere", "others")):
        return "misc"

    return None


def normalize_phase_key(val: Optional[str]) -> str:
    """Normalize any string (key, alias, or legacy title) to a canonical phase key.
    Falls back to DEFAULT_PHASE_KEY ('misc') if unrecognized or empty.
    """
    norm = try_normalize_phase_key(val)
    return norm if norm is not None else DEFAULT_PHASE_KEY



def get_phase(name_or_key: Optional[str]) -> Phase:
    """Resolve a key, alias, or legacy title into a canonical Phase object."""
    key = normalize_phase_key(name_or_key)
    return PHASES_BY_KEY.get(key, PHASES_BY_KEY[DEFAULT_PHASE_KEY])
