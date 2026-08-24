import socket
import subprocess
import platform
import re
from typing import Optional, List

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
        elif os_type in ["linux", "darwin"]:
            detected = NetDetector._detect_unix_ip()
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
            output = subprocess.check_output("ipconfig", text=True, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            
            # Look for 10.x.x.x addresses (typical for THM/HTB OpenVPN connections)
            vpn_ips = re.findall(r"IPv4-Adresse[.\s]*:\s*(10\.\d{1,3}\.\d{1,3}\.\d{1,3})", output, re.IGNORECASE)
            if not vpn_ips:
                vpn_ips = re.findall(r"IPv4 Address[.\s]*:\s*(10\.\d{1,3}\.\d{1,3}\.\d{1,3})", output, re.IGNORECASE)

            if vpn_ips:
                # Return the first 10.x.x.x IP (usually the VPN)
                return vpn_ips[0]

            # Next check for other private IPs like 172.16-31.x.x or 192.168.x.x if no 10.x found
            all_ips = re.findall(r"(?:IPv4-Adresse|IPv4 Address)[.\s]*:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output, re.IGNORECASE)
            for ip in all_ips:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    return ip
        except Exception as e:
            print(f"[NetDetector] Windows detection error: {e}")
        return None

    @staticmethod
    def _detect_unix_ip() -> Optional[str]:
        """Checks tun0, wg0, tap0 or ip route on Linux/macOS."""
        # Check tun0 or wg0 directly via ip addr
        for iface in ["tun0", "wg0", "tap0"]:
            try:
                output = subprocess.check_output(["ip", "-4", "addr", "show", iface], text=True, stderr=subprocess.DEVNULL)
                match = re.search(r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output)
                if match:
                    return match.group(1)
            except Exception:
                pass
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
        except Exception:
            pass
        return None

    @staticmethod
    def _detect_outbound_ip() -> Optional[str]:
        """Connects a dummy UDP socket to find default routing IP."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            # Doesn't actually send packets
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass
        return None
