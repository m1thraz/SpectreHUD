import re
from typing import Dict, Any, List, Set

# Known global variable aliases that are supplied by the top VariableBar
GLOBAL_PARAM_KEYS: Set[str] = {
    "TARGET_IP",
    "TARGET",
    "RHOST",
    "RHOSTS",
    "IP",
    "ATTACKER_IP",
    "LHOST",
    "HOST",
    "MY_IP",
    "PORT",
    "LPORT",
    "RPORT",
    "USERNAME",
    "USER",
    "PASSWORD",
    "PASS",
    "URL",
}

# Standard defaults/presets for common CTF parameters
SMART_PRESETS: Dict[str, str] = {
    "DOMAIN": "example.local",
    "DNS_SERVER": "10.10.10.10",
    "WORDLIST": "/usr/share/wordlists/dirb/common.txt",
    "HASH_FILE": "hashes.txt",
    "TABLE_NAME": "users",
    "DATABASE_NAME": "app_db",
    "FILE_PATH": "/etc/passwd",
    "FILE_NAME": "id_rsa",
    "ENDPOINT": "/api/v1/login",
    "SERVICE_NAME": "ssh",
    "SUBNET": "192.168.1.0/24",
    "PORT_SEQUENCE": "7000,8000,9000",
    "LOCAL_HOST": "127.0.0.1",
    "LOCAL_PORT": "8080",
    "REQUEST_FILE": "request.txt",
    "PARAMETER": "page",
    "PARAM": "id",
    "EIP_VALUE": "0x41414141",
    "PATTERN": "Aa0Aa1Aa2Aa3Aa4Aa5Aa6Aa7Aa8Aa9",
    "SSH_PUBLIC_KEY": "id_rsa.pub",
    "ZIP_FILE": "archive.zip",
    "SOURCE_FILE": "exploit.c",
    "OUTPUT_FILE": "output.bin",
    "OBJECT_FILE": "module.o",
    "USER_FIELD": "username",
    "PASS_FIELD": "password",
    "FAIL_MESSAGE": "Invalid credentials",
    "LOG_PATH": "/var/log/auth.log",
    "PATH": "/var/www/html",
    "DIR": "/",
    "FILE": "passwd",
    "USER": "admin",
    "USERNAME": "root",
    "PASSWORD": "password",
    "PASS": "password",
    "INTERFACE": "tun0",
    "PAYLOAD": "bash",
    "EXTENSIONS": "php,txt,html,js",
    "HASH": "hash.txt",
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
        Returns placeholder names that require user input (i.e. not handled by global target_ip/attacker_ip/port/user/pass,
        and not already provided with a non-empty value in variables).
        """
        all_placeholders = TemplateEngine.extract_all_placeholders(template)
        unresolved = []
        for p in all_placeholders:
            if p not in GLOBAL_PARAM_KEYS:
                p_lower = p.lower()
                val = variables.get(p_lower) or variables.get(p)
                if p in ("HASH", "HASH_FILE", "NTLM_HASH") and not val:
                    val = (
                        variables.get("ntlm_hash")
                        or variables.get("hash_file")
                        or variables.get("hash")
                    )
                elif p in ("DNS", "DNS_SERVER") and not val:
                    val = variables.get("dns_server") or variables.get("dns")
                elif p == "ENDPOINT" and not val:
                    val = variables.get("url") or variables.get("endpoint")

                if not val or not str(val).strip():
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
        username = str(variables.get("username", "")).strip()
        password = str(variables.get("password", "")).strip()
        domain = str(variables.get("domain", "")).strip()
        hash_val = str(
            variables.get("ntlm_hash", "")
            or variables.get("hash_file", "")
            or variables.get("hash", "")
        ).strip()
        wordlist = str(variables.get("wordlist", "")).strip() or SMART_PRESETS.get("WORDLIST", "")
        url = str(variables.get("url", "")).strip()
        subnet = str(variables.get("subnet", "")).strip()
        dns_server = str(variables.get("dns_server", "") or variables.get("dns", "")).strip()

        default_url = (
            url
            if url
            else (f"http://{target_ip}:{port}" if port and port != "80" else f"http://{target_ip}")
        )

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
            "USERNAME": username if username else "{{USERNAME}}",
            "USER": username if username else "{{USER}}",
            "PASSWORD": password if password else "{{PASSWORD}}",
            "PASS": password if password else "{{PASS}}",
            "DOMAIN": domain if domain else "{{DOMAIN}}",
            "HASH": hash_val if hash_val else "{{HASH}}",
            "NTLM_HASH": hash_val if hash_val else "{{NTLM_HASH}}",
            "HASH_FILE": hash_val if hash_val else "{{HASH_FILE}}",
            "WORDLIST": wordlist,
            "URL": default_url,
            "ENDPOINT": url if url else "{{ENDPOINT}}",
            "SUBNET": subnet if subnet else "{{SUBNET}}",
            "DNS_SERVER": dns_server if dns_server else "{{DNS_SERVER}}",
            "DNS": dns_server if dns_server else "{{DNS}}",
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
    def render_with_custom(
        template: str, variables: Dict[str, Any], custom_params: Dict[str, str]
    ) -> str:
        """Fully renders template resolving both globals and custom inline parameters."""
        merged_vars = dict(variables)
        merged_vars.update(custom_params)
        return TemplateEngine.render(template, merged_vars)


# Backward-compatible and domain-specific alias
SnippetInterpolator = TemplateEngine
