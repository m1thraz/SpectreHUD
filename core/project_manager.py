import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_NOTES_TEMPLATE = """# 🎯 CTF Write-Up & Notes: {project_name}

- **Target IP:** `{target_ip}`
- **Attacker IP / LHOST:** `{attacker_ip}`
- **Erstellt am:** {created_at}

---

## 🔍 1. Reconnaissance & Port Scans
- **Nmap Initial Scan:**
```bash
# Nmap initial results
```

---

## ⚡ 2. Initial Access & Exploitation
- **Schwachstelle:** 
- **Vorgehensweise:** 

---

## 🛡️ 3. Privilege Escalation
- **User Flag:** 
- **Root / Admin Escalation:** 
- **Root Flag:** 

---

## 📝 4. Notizen & Gelerntes
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
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_project = "Default"
        self._ensure_default_project()

    def _sanitize_name(self, name: str) -> str:
        """Sanitizes project name to safe folder characters."""
        clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name.strip())
        return clean or "Default"

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
        for p in self.base_dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                projects.append(p.name)
        return sorted(projects) if projects else ["Default"]

    def get_active_project(self) -> str:
        """Returns the name of the currently active project."""
        return self.active_project

    def get_project_dir(self, name: Optional[str] = None) -> Path:
        """Returns the filesystem path for a project."""
        pname = self._sanitize_name(name or self.active_project)
        return self.base_dir / pname

    def create_project(self, name: str, target_ip: str = "", attacker_ip: str = "", port: str = "4444") -> Path:
        """
        Creates an isolated project workspace with subfolders (recon, exploit, loot),
        notes.md, and project_state.json.
        """
        clean_name = self._sanitize_name(name)
        proj_dir = self.base_dir / clean_name
        proj_dir.mkdir(parents=True, exist_ok=True)

        # Create subfolders
        (proj_dir / "recon").mkdir(exist_ok=True)
        (proj_dir / "exploit").mkdir(exist_ok=True)
        (proj_dir / "loot").mkdir(exist_ok=True)

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
            notes_file.write_text(notes_content, encoding="utf-8")

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
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(initial_state, f, indent=2, ensure_ascii=False)

        return proj_dir

    def load_project_state(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Loads state data for a project."""
        pname = self._sanitize_name(name or self.active_project)
        state_file = self.get_project_dir(pname) / "project_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ProjectManager] Error loading state for {pname}: {e}")

        # Return default fallback state
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "name": pname,
            "target_ip": "10.10.10.10",
            "attacker_ip": "10.10.14.5",
            "port": "4444",
            "wordlist": "/usr/share/wordlists/dirb/common.txt",
            "created_at": now_str,
            "updated_at": now_str,
            "loot": [],
            "clipboard_history": []
        }

    def save_project_state(self, name: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> None:
        """Persists state data for a project."""
        pname = self._sanitize_name(name or self.active_project)
        proj_dir = self.get_project_dir(pname)
        proj_dir.mkdir(parents=True, exist_ok=True)
        state_file = proj_dir / "project_state.json"

        if state is None:
            return

        state["name"] = pname
        state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ProjectManager] Error saving state for {pname}: {e}")

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
            folder.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            return True
        except Exception as e:
            print(f"[ProjectManager] Error opening folder: {e}")
            return False
