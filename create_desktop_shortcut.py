import os
import sys
import subprocess
from pathlib import Path

def create_shortcut():
    project_dir = Path(__file__).parent.resolve()
    main_script = project_dir / "main.py"
    
    # Get python executable (prefer pythonw to launch silently in background without console)
    python_dir = Path(sys.executable).parent
    pythonw_exe = python_dir / "pythonw.exe"
    if not pythonw_exe.exists():
        python_exe = sys.executable
    else:
        python_exe = str(pythonw_exe)

    # User Desktop Directory
    desktop_dir = Path.home() / "Desktop"
    if not desktop_dir.exists():
        # Fallback to OneDrive Desktop if synced
        onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
        if onedrive_desktop.exists():
            desktop_dir = onedrive_desktop

    icon_path = project_dir / "data" / "icon.ico"
    icon_line = f'$Shortcut.IconLocation = "{icon_path}"' if icon_path.exists() else ""

    # PowerShell command to create WScript.Shell shortcut
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
        print(f"[-] Fehler beim Erstellen des Shortcuts: {e}")
        return False, str(e)

if __name__ == "__main__":
    success, path = create_shortcut()
    if success:
        print(f"SpectreHUD Shortcut liegt auf deinem Desktop: {path}")
    else:
        print(f"Fehler: {path}")
