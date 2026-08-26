"""
Snippet Importer: Parst und importiert Cheatsheets im JSON- oder Markdown-Format.

Ermöglicht den flexiblen Massen-Import von Befehlen und Cheatsheets:
1. JSON-Format: Listen von Snippet-Objekten oder strukturierte Kategorien.
2. Markdown-Format (.md): Standard Markdown mit Überschriften (#, ##, ###)
   und Fenced Code Blocks (```bash ... ```).
"""
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Union

from core.logger import get_logger

logger = get_logger("snippet_importer")


def normalize_template_variables(text: str) -> str:
    """
    Wandelt gängige Platzhalter wie $TARGET, $target, $ATTACKER, $LHOST, $PORT
    in die von SpectreHUD verwendeten Template-Variablen ({{TARGET_IP}} etc.) um.
    """
    if not text:
        return ""
    
    # $TARGET / $target / <target> / <TARGET>
    text = re.sub(r'(?i)\$TARGET\b|\bTARGET_IP\b|(?i)<target_ip>|(?i)<target>', '{{TARGET_IP}}', text)
    # $ATTACKER / $LHOST / $attacker / $attackerIP / <attacker>
    text = re.sub(r'(?i)\$ATTACKER(?:_IP|IP)?\b|(?i)\$LHOST\b|(?i)<attacker_ip>|(?i)<lhost>', '{{ATTACKER_IP}}', text)
    # $PORT / $LPORT / <port>
    text = re.sub(r'(?i)\$LPORT\b|\$PORT\b|(?i)<port>|(?i)<lport>', '{{PORT}}', text)
    # $WORDLIST / <wordlist>
    text = re.sub(r'(?i)\$WORDLIST\b|(?i)<wordlist>', '{{WORDLIST}}', text)
    
    return text


def parse_snippets_json(raw_text: str) -> List[Dict[str, Any]]:
    """Parst einen JSON-String und extrahiert standardisierte Snippets."""
    snippets: List[Dict[str, Any]] = []
    try:
        data = json.loads(raw_text)
    except Exception as e:
        logger.error(f"Failed to parse JSON snippets: {e}")
        return []

    # Format 1: Liste von Snippet-Objekten
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and (item.get("template") or item.get("command")):
                tmpl = item.get("template") or item.get("command") or ""
                snippets.append({
                    "id": f"custom_{uuid.uuid4().hex[:8]}",
                    "title": item.get("title") or item.get("name") or "Importierter Befehl",
                    "category": item.get("category") or "Custom Notes & Snippets",
                    "category_id": item.get("category_id") or "custom_snippets",
                    "subcategory": item.get("subcategory") or "Allgemein",
                    "description": item.get("description") or "",
                    "template": normalize_template_variables(tmpl),
                    "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
                    "is_custom": True
                })

    # Format 2: Kategorien-Struktur {"categories": [{"name": ..., "snippets": [...]}]}
    elif isinstance(data, dict):
        if "categories" in data and isinstance(data["categories"], list):
            for cat in data["categories"]:
                if not isinstance(cat, dict):
                    continue
                cat_name = cat.get("name") or "Custom Notes & Snippets"
                cat_id = cat.get("id") or "custom_snippets"
                for snip in cat.get("snippets", []):
                    if not isinstance(snip, dict):
                        continue
                    tmpl = snip.get("template") or snip.get("command") or ""
                    if not tmpl.strip():
                        continue
                    snippets.append({
                        "id": f"custom_{uuid.uuid4().hex[:8]}",
                        "title": snip.get("title") or snip.get("name") or "Importierter Befehl",
                        "category": snip.get("category") or cat_name,
                        "category_id": cat_id,
                        "subcategory": snip.get("subcategory") or "Allgemein",
                        "description": snip.get("description") or "",
                        "template": normalize_template_variables(tmpl),
                        "tags": snip.get("tags") if isinstance(snip.get("tags"), list) else [],
                        "is_custom": True
                    })
        elif "snippets" in data and isinstance(data["snippets"], list):
            return parse_snippets_json(json.dumps(data["snippets"]))

    return snippets


def parse_snippets_markdown(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parst ein Markdown-Cheatsheet und wandelt Abschnitte mit Code-Blöcken in Snippets um.
    
    Erkennt:
    # Hauptkategorie
    ## Unterkategorie
    ### Befehls-Titel / Name
    Optionale Beschreibung oder Notiz
    ```bash
    command ...
    ```
    """
    snippets: List[Dict[str, Any]] = []
    lines = raw_text.splitlines()

    current_category = "Custom Notes & Snippets"
    current_subcategory = "Allgemein"
    current_title = ""
    current_desc_lines: List[str] = []
    in_code_block = False
    current_code_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Fenced code block Start/Ende
        if stripped.startswith("```"):
            if in_code_block:
                # Code Block beendet -> Snippet erstellen!
                code_content = "\n".join(current_code_lines).strip()
                if code_content:
                    title = current_title or (code_content.splitlines()[0][:40] if code_content else "Importierter Befehl")
                    desc = "\n".join(current_desc_lines).strip()
                    
                    snippets.append({
                        "id": f"custom_{uuid.uuid4().hex[:8]}",
                        "title": title,
                        "category": current_category,
                        "category_id": "custom_snippets",
                        "subcategory": current_subcategory,
                        "description": desc,
                        "template": normalize_template_variables(code_content),
                        "tags": [t.lower() for t in re.findall(r'\b[A-Za-z0-9_-]{3,}\b', current_subcategory + " " + title)[:5]],
                        "is_custom": True
                    })
                
                in_code_block = False
                current_code_lines = []
                current_desc_lines = []
                current_title = ""
            else:
                in_code_block = True
                current_code_lines = []
            continue

        if in_code_block:
            current_code_lines.append(line)
            continue

        # Überschriften-Erkennung
        if stripped.startswith("# "):
            current_category = stripped[2:].strip()
            current_subcategory = "Allgemein"
            current_title = ""
            current_desc_lines = []
        elif stripped.startswith("## "):
            current_subcategory = stripped[3:].strip()
            current_title = ""
            current_desc_lines = []
        elif stripped.startswith("### ") or stripped.startswith("#### "):
            header_level = 4 if stripped.startswith("#### ") else 3
            current_title = stripped[header_level + 1:].strip()
            current_desc_lines = []
        else:
            if stripped and not stripped.startswith("---") and not stripped.startswith("{%"):
                current_desc_lines.append(stripped)

    return snippets


def import_snippets_from_file(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Lädt eine Datei (.json oder .md/.txt) und parst alle enthaltenen Snippets."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        logger.error(f"File not found for import: {path}")
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        return []

    if path.suffix.lower() == ".json":
        return parse_snippets_json(content)
    else:
        return parse_snippets_markdown(content)
