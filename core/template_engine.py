import re
from typing import Dict, Any, List, Set

# Known global variable aliases that are supplied by the top VariableBar
GLOBAL_PARAM_KEYS: Set[str] = {
    "TARGET_IP", "TARGET", "RHOST", "RHOSTS", "IP",
    "ATTACKER_IP", "LHOST", "HOST", "MY_IP",
    "PORT", "LPORT", "RPORT",
    "URL"
}

# Standard defaults/presets for common CTF parameters
SMART_PRESETS: Dict[str, str] = {
    "WORDLIST": "/usr/share/wordlists/dirb/common.txt",
    "PARAM": "id",
    "PARAMETER": "page",
    "PATH": "/var/www/html",
    "DIR": "/",
    "FILE": "passwd",
    "USER": "admin",
    "USERNAME": "root",
    "PASSWORD": "password",
    "INTERFACE": "tun0",
    "PAYLOAD": "bash",
    "EXTENSIONS": "php,txt,html,js",
    "HASH": "hash.txt"
}

class TemplateEngine:
    """Interpolates variables, identifies placeholders, and handles interactive inline parameter substitution."""

    @staticmethod
    def extract_all_placeholders(template: str) -> List[str]:
        """Extracts all unique placeholder names inside {{...}} from template."""
        if not template:
            return []
        matches = re.findall(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}", template)
        # Keep unique preserving order
        seen = set()
        unique = []
        for m in matches:
            m_upper = m.strip().upper()
            if m_upper not in seen:
                seen.add(m_upper)
                unique.append(m_upper)
        return unique

    @staticmethod
    def extract_unresolved_placeholders(template: str, variables: Dict[str, Any]) -> List[str]:
        """
        Returns placeholder names that require user input (i.e. not handled by global target_ip/attacker_ip/port).
        """
        all_placeholders = TemplateEngine.extract_all_placeholders(template)
        unresolved = []
        for p in all_placeholders:
            if p not in GLOBAL_PARAM_KEYS:
                unresolved.append(p)
        return unresolved

    @staticmethod
    def render(template: str, variables: Dict[str, Any]) -> str:
        """
        Renders template with standard global variables.
        Unresolved custom parameters remain as {{PARAM}} for visual clarity until copied.
        """
        if not template:
            return ""

        target_ip = str(variables.get("target_ip", "")).strip() or "10.10.10.10"
        attacker_ip = str(variables.get("attacker_ip", "")).strip() or "10.10.14.5"
        port = str(variables.get("port", "")).strip() or "4444"
        wordlist = str(variables.get("wordlist", "")).strip() or SMART_PRESETS.get("WORDLIST", "")

        aliases = {
            "TARGET_IP": target_ip,
            "TARGET": target_ip,
            "RHOST": target_ip,
            "RHOSTS": target_ip,
            "IP": target_ip,
            "ATTACKER_IP": attacker_ip,
            "LHOST": attacker_ip,
            "HOST": attacker_ip,
            "MY_IP": attacker_ip,
            "PORT": port,
            "LPORT": port,
            "RPORT": port,
            "WORDLIST": wordlist,
            "URL": f"http://{target_ip}:{port}" if port and port != "80" else f"http://{target_ip}"
        }

        # Include custom variables if provided
        for k, v in variables.items():
            aliases[k.upper()] = str(v)

        result = template
        for key, val in aliases.items():
            pattern = re.compile(rf"\{{\{{\s*{re.escape(key)}\s*\}}\}}", re.IGNORECASE)
            result = pattern.sub(lambda m, v=val: v, result)

        return result

    @staticmethod
    def render_with_custom(template: str, variables: Dict[str, Any], custom_params: Dict[str, str]) -> str:
        """Fully renders template resolving both globals and custom inline parameters."""
        merged_vars = dict(variables)
        merged_vars.update(custom_params)
        return TemplateEngine.render(template, merged_vars)
