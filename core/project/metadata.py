"""
Metadata templates and default structure generation for project workspaces.
"""

from typing import Dict, Any, Optional

DEFAULT_NOTES_TEMPLATE_DE = """# CTF Write-Up & Notes: {project_name}

- **Target IP:** `{target_ip}`
- **Attacker IP / LHOST:** `{attacker_ip}`
- **Erstellt am:** {created_at}

---

## 1. Reconnaissance & Port Scans
- **Nmap Initial Scan:**
```bash
# Nmap initial results
```

---

## 2. Initial Access & Exploitation
- **Schwachstelle:**
- **Vorgehensweise:**

---

## 3. Privilege Escalation
- **User Flag:**
- **Root / Admin Escalation:**
- **Root Flag:**

---

## 4. Notizen & Gelerntes
-
"""

DEFAULT_NOTES_TEMPLATE_EN = """# CTF Write-Up & Notes: {project_name}

- **Target IP:** `{target_ip}`
- **Attacker IP / LHOST:** `{attacker_ip}`
- **Created at:** {created_at}

---

## 1. Reconnaissance & Port Scans
- **Nmap Initial Scan:**
```bash
# Nmap initial results
```

---

## 2. Initial Access & Exploitation
- **Vulnerability:**
- **Procedure:**

---

## 3. Privilege Escalation
- **User Flag:**
- **Root / Admin Escalation:**
- **Root Flag:**

---

## 4. Notes & Lessons Learned
-
"""

DEFAULT_NOTES_TEMPLATE = DEFAULT_NOTES_TEMPLATE_DE


def create_initial_notes(
    project_name: str,
    target_ip: str = "TBD",
    attacker_ip: str = "TBD",
    created_at: Optional[str] = None,
    lang: str = "de",
) -> str:
    """Renders initial notes.md markdown text for a new project."""
    from core.validators import format_timestamp

    ts = created_at or format_timestamp()
    tmpl = DEFAULT_NOTES_TEMPLATE_DE if (lang or "").lower().startswith("de") else DEFAULT_NOTES_TEMPLATE_EN
    return tmpl.format(
        project_name=project_name,
        target_ip=target_ip or "TBD",
        attacker_ip=attacker_ip or "TBD",
        created_at=ts,
    )


def create_initial_state(
    project_name: str,
    target_ip: str = "10.10.10.10",
    attacker_ip: str = "10.10.14.5",
    port: str = "4444",
    wordlist: str = "/usr/share/wordlists/dirb/common.txt",
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates initial dictionary structure for project_state.json."""
    from core.validators import format_timestamp

    ts = created_at or format_timestamp()
    return {
        "name": project_name,
        "target_ip": target_ip or "10.10.10.10",
        "attacker_ip": attacker_ip or "10.10.14.5",
        "port": port or "4444",
        "wordlist": wordlist or "/usr/share/wordlists/dirb/common.txt",
        "created_at": ts,
        "updated_at": ts,
        "loot": [],
        "clipboard_history": [],
    }
