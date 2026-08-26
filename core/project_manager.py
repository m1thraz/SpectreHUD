import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.logger import get_logger

logger = get_logger("projects")

DEFAULT_NOTES_TEMPLATE = """# CTF Write-Up & Notes: {project_name}

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

def get_default_projects_dir() -> Path:
    """Returns the default projects workspace directory, checking SPECTRE_PROJECTS_DIR env var first."""
    env_dir = os.environ.get("SPECTRE_PROJECTS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / "spectre_projects"

class ProjectManager:
    """Manages isolated CTF/Pentest workspaces on the filesystem."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = get_default_projects_dir()
        self.base_dir = Path(base_dir)
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create base projects directory {self.base_dir}: {e}", exc_info=True)
        
        self.active_project = "Default"
        self._ensure_default_project()

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitizes project name to safe folder characters, strictly preventing
        directory traversal (e.g., '.', '..', '../foo').
        """
        if not name:
            return "Default"

        # Replace invalid path characters with underscore
        clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', str(name).strip())

        # Strip leading and trailing dots to prevent hidden/special traversal dirs
        clean = clean.strip(".")

        # Explicitly check against dangerous names or invalid formats
        if not clean or clean in {".", ".."} or not re.match(r'^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$', clean):
            return "Default"

        return clean

    def _ensure_default_project(self) -> None:
        """Ensures a Default project exists."""
        default_dir = self.base_dir / "Default"
        if not default_dir.exists():
            self.create_project("Default", target_ip="10.10.10.10", attacker_ip="10.10.14.5")

    def list_projects(self) -> List[str]:
        """Returns list of all available project directory names."""
        if not self.base_dir.exists():
            return ["Default"]
        projects = []
        try:
            for p in self.base_dir.iterdir():
                if p.is_dir() and not p.name.startswith("."):
                    projects.append(p.name)
        except OSError as e:
            logger.error(f"Failed to list projects from {self.base_dir}: {e}", exc_info=True)
        return sorted(projects) if projects else ["Default"]

    def get_active_project(self) -> str:
        """Returns the name of the currently active project."""
        return self.active_project

    def get_project_dir(self, name: Optional[str] = None) -> Path:
        """
        Returns the filesystem path for a project, enforcing strict workspace boundaries.
        Throws or falls back if a traversal escape attempt is detected.
        """
        pname = self._sanitize_name(name or self.active_project)
        resolved_base = self.base_dir.resolve()
        proj_dir = (self.base_dir / pname).resolve()

        # Second Line of Defense: Verify proj_dir is strictly inside base_dir
        if resolved_base not in proj_dir.parents and proj_dir != resolved_base:
            logger.error(f"Workspace escape attempt detected: {name!r} (resolved to {proj_dir}). Falling back to Default.")
            return self.base_dir / "Default"

        return self.base_dir / pname

    def create_project(self, name: str, target_ip: str = "", attacker_ip: str = "", port: str = "4444") -> Path:
        """
        Creates an isolated project workspace with subfolders (recon, exploit, loot),
        notes.md, and project_state.json.
        """
        clean_name = self._sanitize_name(name)
        proj_dir = self.base_dir / clean_name
        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
            (proj_dir / "recon").mkdir(exist_ok=True)
            (proj_dir / "exploit").mkdir(exist_ok=True)
            (proj_dir / "loot").mkdir(exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create folder structure for project {clean_name}: {e}", exc_info=True)

        # Create notes.md if not exists
        notes_file = proj_dir / "notes.md"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not notes_file.exists():
            notes_content = DEFAULT_NOTES_TEMPLATE.format(
                project_name=clean_name,
                target_ip=target_ip or "TBD",
                attacker_ip=attacker_ip or "TBD",
                created_at=now_str
            )
            try:
                notes_file.write_text(notes_content, encoding="utf-8")
            except OSError as e:
                logger.error(f"Failed to create notes.md for {clean_name}: {e}", exc_info=True)

        # Create project_state.json if not exists
        state_file = proj_dir / "project_state.json"
        if not state_file.exists():
            initial_state = {
                "name": clean_name,
                "target_ip": target_ip or "10.10.10.10",
                "attacker_ip": attacker_ip or "10.10.14.5",
                "port": port or "4444",
                "wordlist": "/usr/share/wordlists/dirb/common.txt",
                "created_at": now_str,
                "updated_at": now_str,
                "loot": [],
                "clipboard_history": []
            }
            try:
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(initial_state, f, indent=2, ensure_ascii=False)
            except (OSError, TypeError, ValueError) as e:
                logger.error(f"Failed to write initial project_state.json for {clean_name}: {e}")

        return proj_dir

    def load_project_state(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Loads and semantically validates state data for a project."""
        from core.validators import validate_project_state
        pname = self._sanitize_name(name or self.active_project)
        state_file = self.get_project_dir(pname) / "project_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    return validate_project_state(raw_data, fallback_name=pname)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted project_state.json for {pname}: {e}")
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error loading state for {pname}: {e}")

        # Return default fallback state
        return validate_project_state(None, fallback_name=pname)

    def save_project_state(self, name: Optional[str] = None, state: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """Persists state data for a project."""
        from core.validators import validate_project_state
        pname = self._sanitize_name(name or self.active_project)
        proj_dir = self.get_project_dir(pname)
        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to ensure project dir {proj_dir}: {e}", exc_info=True)

        from core.atomic_write import atomic_write_json
        state_file = proj_dir / "project_state.json"

        # Merge state from dict and kwargs
        final_state = self.load_project_state(pname) or {}
        if state:
            final_state.update(state)
        if kwargs:
            final_state.update(kwargs)

        final_state["name"] = pname
        final_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        valid_state = validate_project_state(final_state, fallback_name=pname)

        try:
            atomic_write_json(state_file, valid_state, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"OS error saving state for {pname} to {state_file}: {e}", exc_info=True)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error saving state for {pname}: {e}")

    def set_active_project(self, name: str) -> None:
        """Switches the active project context."""
        clean_name = self._sanitize_name(name)
        if clean_name in self.list_projects():
            self.active_project = clean_name
        else:
            self.create_project(clean_name)
            self.active_project = clean_name

    def open_project_folder(self, name: Optional[str] = None) -> bool:
        """Opens the project folder in Windows Explorer or Linux file manager."""
        folder = self.get_project_dir(name)
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create project folder before opening {folder}: {e}")

        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            return True
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"Error opening project folder {folder} in system file manager: {e}", exc_info=True)
            return False
