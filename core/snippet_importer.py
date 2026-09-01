"""
Snippet Importer & Parser for SpectreHUD.
Allows importing custom snippets from JSON and Markdown files with automatic variable normalization.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Union

from core.logger import get_logger

logger = get_logger("snippet_importer")


def normalize_template_variables(text: str) -> str:
    """
    Normalizes common CTF / Pentesting variable placeholders to standard SpectreHUD placeholders:
    - $TARGET, $TARGET_IP, <target_ip>, <target>, {{TARGET}} -> {{TARGET_IP}}
    - $ATTACKER, $ATTACKER_IP, $LHOST, <attacker_ip>, <lhost>, {{ATTACKER}} -> {{ATTACKER_IP}}
    - $PORT, $LPORT, <port>, <lport> -> {{PORT}}
    - $WORDLIST, <wordlist> -> {{WORDLIST}}
    """
    if not text:
        return ""

    # Target IP
    text = re.sub(
        r"\$(?:TARGET_IP|TARGET)\b|\bTARGET_IP\b|<(?:target_ip|target)>|\{\{TARGET\}\}",
        "{{TARGET_IP}}",
        text,
        flags=re.IGNORECASE,
    )
    # Attacker / LHOST IP
    text = re.sub(
        r"\$(?:ATTACKER(?:_IP|IP)?|LHOST)\b|<(?:attacker_ip|lhost|attacker)>|\{\{ATTACKER\}\}|\{\{LHOST\}\}",
        "{{ATTACKER_IP}}",
        text,
        flags=re.IGNORECASE,
    )
    # Port / LPORT
    text = re.sub(
        r"\$(?:LPORT|PORT)\b|<(?:lport|port)>|\{\{LPORT\}\}", "{{PORT}}", text, flags=re.IGNORECASE
    )
    # Wordlist
    text = re.sub(r"\$WORDLIST\b|<wordlist>", "{{WORDLIST}}", text, flags=re.IGNORECASE)

    return text


def parse_snippets_json(content: str) -> List[Dict[str, Any]]:
    """Parses snippet definitions from JSON string (array or object)."""
    snippets: List[Dict[str, Any]] = []
    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to parse snippets JSON: {e}")
        return []

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if "snippets" in data and isinstance(data["snippets"], list):
            items = data["snippets"]
        elif "categories" in data and isinstance(data["categories"], list):
            for cat in data["categories"]:
                if (
                    isinstance(cat, dict)
                    and "snippets" in cat
                    and isinstance(cat["snippets"], list)
                ):
                    cat_name = cat.get("name", "Custom")
                    for s in cat["snippets"]:
                        if isinstance(s, dict):
                            s.setdefault("category", cat_name)
                            items.append(s)
        else:
            items = [data]

    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title", item.get("name", "Custom Snippet"))
        template = item.get("template", item.get("command", item.get("code", "")))
        if not template:
            continue
        category = item.get("category", "Custom Notes & Snippets")
        tags = item.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        snippets.append(
            {
                "title": str(title),
                "template": normalize_template_variables(str(template).strip()),
                "category": str(category),
                "tags": tags if isinstance(tags, list) else [],
            }
        )

    return snippets


def parse_snippets_markdown(content: str) -> List[Dict[str, Any]]:
    """
    Parses snippets from Markdown text.
    Headings (#, ##, ###) define category / section / title.
    Code blocks (```...```) define the command template.
    """
    snippets: List[Dict[str, Any]] = []
    lines = content.splitlines()

    current_h1 = "Custom"
    current_h2 = ""
    current_title = ""
    in_code_block = False
    code_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lines = []
            else:
                in_code_block = False
                template = "\n".join(code_lines).strip()
                if template:
                    title = current_title or (
                        f"{current_h2} - Command" if current_h2 else f"{current_h1} - Command"
                    )
                    category = current_h1
                    snippets.append(
                        {
                            "title": title,
                            "template": normalize_template_variables(template),
                            "category": category,
                            "tags": [t for t in [current_h1, current_h2] if t],
                        }
                    )
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if stripped.startswith("# "):
            current_h1 = stripped[2:].strip()
            current_h2 = ""
            current_title = ""
        elif stripped.startswith("## "):
            current_h2 = stripped[3:].strip()
            current_title = current_h2
        elif stripped.startswith("### "):
            current_title = stripped[4:].strip()
        elif stripped.startswith("#### "):
            current_title = stripped[5:].strip()

    return snippets


def import_snippets_from_file(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Reads a JSON or Markdown file and parses snippets with size limit checks."""
    from core.validators import is_file_size_valid, MAX_CONFIG_FILE_SIZE

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        logger.error(f"Import file does not exist: {path}")
        return []

    if not is_file_size_valid(path, MAX_CONFIG_FILE_SIZE):
        logger.error(
            f"Import file exceeds maximum allowed size ({path.stat().st_size} > {MAX_CONFIG_FILE_SIZE} bytes): {path}"
        )
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        return []

    suffix = path.suffix.lower()
    if suffix in (".json", ".js"):
        return parse_snippets_json(content)
    elif suffix in (".md", ".markdown", ".txt"):
        return parse_snippets_markdown(content)
    else:
        res = parse_snippets_json(content)
        if res:
            return res
        return parse_snippets_markdown(content)
