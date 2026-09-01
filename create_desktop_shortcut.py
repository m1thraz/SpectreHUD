import os
import sys
import subprocess
from pathlib import Path
from typing import Tuple


def _create_windows_shortcut(project_dir: Path, main_script: Path) -> Tuple[bool, str]:
    python_dir = Path(sys.executable).parent
    pythonw_exe = python_dir / "pythonw.exe"
    if not pythonw_exe.exists():
        python_exe = sys.executable
    else:
        python_exe = str(pythonw_exe)

    desktop_dir = Path.home() / "Desktop"
    if not desktop_dir.exists():
        onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
        if onedrive_desktop.exists():
            desktop_dir = onedrive_desktop
        else:
            desktop_dir.mkdir(parents=True, exist_ok=True)

    shortcut_path = desktop_dir / "SpectreHUD.lnk"
    icon_path = project_dir / "data" / "icon.ico"
    icon_line = f'$Shortcut.IconLocation = "{icon_path}"' if icon_path.exists() else ""

    ps_script = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{python_exe}"
    $Shortcut.Arguments = '"{main_script}"'
    $Shortcut.WorkingDirectory = "{project_dir}"
    $Shortcut.Description = "SpectreHUD - CTF Cheatsheet & Loot Overlay"
    {icon_line}
    $Shortcut.WindowStyle = 1
    $Shortcut.Save()
    """

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
        print(f"[+] Desktop Shortcut erfolgreich erstellt: {shortcut_path}")
        return True, str(shortcut_path)
    except (subprocess.SubprocessError, OSError) as e:
        print(f"[-] Fehler beim Erstellen des Windows-Shortcuts: {e}")
        return False, str(e)


def _create_linux_shortcut(project_dir: Path, main_script: Path) -> Tuple[bool, str]:
    desktop_dir = Path.home() / "Desktop"
    if not desktop_dir.exists():
        desktop_dir = Path.home() / ".local" / "share" / "applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)

    shortcut_path = desktop_dir / "spectrehud.desktop"

    icon_path = (
        project_dir
        / "resources"
        / "linux"
        / "icons"
        / "hicolor"
        / "scalable"
        / "apps"
        / "spectrehud.svg"
    )
    if not icon_path.exists():
        icon_path = project_dir / "data" / "icon.svg"

    desktop_content = f"""[Desktop Entry]
Type=Application
Name=SpectreHUD
Comment=CTF & Pentesting HUD Cheatsheet
Exec="{sys.executable}" "{main_script}"
Icon={icon_path if icon_path.exists() else "spectrehud"}
Categories=Utility;Security;Development;
Terminal=false
StartupWMClass=spectrehud
"""

    try:
        shortcut_path.write_text(desktop_content, encoding="utf-8")
        try:
            os.chmod(shortcut_path, 0o755)
        except OSError:
            pass
        print(f"[+] Linux Desktop Entry erfolgreich erstellt: {shortcut_path}")
        return True, str(shortcut_path)
    except OSError as e:
        print(f"[-] Fehler beim Erstellen des Linux Desktop Entry: {e}")
        return False, str(e)


def create_shortcut() -> Tuple[bool, str]:
    project_dir = Path(__file__).parent.resolve()
    main_script = project_dir / "main.py"

    if sys.platform.startswith("win"):
        return _create_windows_shortcut(project_dir, main_script)
    elif sys.platform.startswith("linux"):
        return _create_linux_shortcut(project_dir, main_script)
    else:
        err = f"Unsupported platform for desktop shortcut: {sys.platform}"
        print(f"[-] {err}")
        return False, err


if __name__ == "__main__":
    success, path = create_shortcut()
    if success:
        print(f"SpectreHUD Shortcut liegt auf deinem Desktop: {path}")
    else:
        print(f"Fehler: {path}")
