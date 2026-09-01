import socket
import subprocess
import platform
import re
from typing import Optional
from core.logger import get_logger
from core.platform.network import detect_linux_ipv4_address

logger = get_logger("net_detector")


class NetDetector:
    """Detects active network interfaces and extracts VPN/Attacker IPs (e.g. tun0, tap, 10.x.x.x)."""

    @staticmethod
    def detect_attacker_ip() -> Optional[str]:
        """
        Attempts to automatically detect the user's VPN / CTF IP address (e.g. TryHackMe tun0 / 10.x.x.x).
        Prioritizes VPN subnets (10.x.x.x, 10.10.x.x, 10.14.x.x, 10.11.x.x) and interface names.
        """
        # 1. Try platform-specific interface inspection
        os_type = platform.system().lower()
        if os_type == "windows":
            detected = NetDetector._detect_windows_ip()
            if detected:
                return detected
        elif os_type == "linux":
            detected = NetDetector._detect_linux_ip()
            if detected:
                return detected
        elif os_type == "darwin":
            detected = NetDetector._detect_macos_ip()
            if detected:
                return detected

        # 2. General socket scan across local hostnames / interfaces
        detected = NetDetector._detect_via_sockets()
        if detected:
            return detected

        # 3. Fallback to primary outbound route
        return NetDetector._detect_outbound_ip()

    @staticmethod
    def _detect_windows_ip() -> Optional[str]:
        """Parses ipconfig output on Windows to find VPN / TAP / 10.x.x.x addresses."""
        try:
            output = subprocess.check_output(
                "ipconfig",
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0,
            )

            # Look for 10.x.x.x addresses (typical for THM/HTB OpenVPN connections)
            vpn_ips = re.findall(
                r"IPv4-Adresse[.\s]*:\s*(10\.\d{1,3}\.\d{1,3}\.\d{1,3})", output, re.IGNORECASE
            )
            if not vpn_ips:
                vpn_ips = re.findall(
                    r"IPv4 Address[.\s]*:\s*(10\.\d{1,3}\.\d{1,3}\.\d{1,3})", output, re.IGNORECASE
                )

            if vpn_ips:
                return vpn_ips[0]

            # Next check for other private IPs like 172.16-31.x.x or 192.168.x.x if no 10.x found
            all_ips = re.findall(
                r"(?:IPv4-Adresse|IPv4 Address)[.\s]*:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
                output,
                re.IGNORECASE,
            )
            for ip in all_ips:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    return ip
        except (subprocess.SubprocessError, OSError, UnicodeDecodeError) as e:
            logger.debug(f"Windows IP detection error via ipconfig: {e}")
        return None

    @staticmethod
    def _detect_linux_ip() -> Optional[str]:
        """Use Linux's machine-readable interface output when available."""
        return detect_linux_ipv4_address()

    @staticmethod
    def _detect_macos_ip() -> Optional[str]:
        """macOS has no supported platform command yet; use generic fallbacks."""
        return None

    @staticmethod
    def _detect_via_sockets() -> Optional[str]:
        """Scans socket getaddrinfo for 10.x.x.x addresses."""
        try:
            hostname = socket.gethostname()
            _, _, ip_list = socket.gethostbyname_ex(hostname)
            # Prioritize 10.x.x.x
            for ip in ip_list:
                if ip.startswith("10.") and not ip.startswith("127."):
                    return ip
            # Fallback to any non-loopback
            for ip in ip_list:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    return ip
        except (socket.error, OSError) as e:
            logger.debug(f"Socket IP detection error: {e}")
        return None

    @staticmethod
    def _detect_outbound_ip() -> Optional[str]:
        """Connects a dummy UDP socket to find default routing IP."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except (socket.error, OSError) as e:
            logger.debug(f"Outbound UDP IP detection error: {e}")
        return None
