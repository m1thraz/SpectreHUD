"""Platform-specific network discovery and pure IPv4 candidate selection."""

import ipaddress
import json
import subprocess
from typing import Iterable, Mapping, Optional


VPN_INTERFACE_PREFIXES = ("tun", "tap", "wg", "tailscale")


def parse_linux_ipv4_interfaces(payload: object) -> list[tuple[str, str]]:
    """Extract ``(interface, address)`` pairs from ``ip -j -4 addr`` data."""
    if not isinstance(payload, list):
        return []

    candidates: list[tuple[str, str]] = []
    for interface in payload:
        if not isinstance(interface, Mapping):
            continue
        name = interface.get("ifname")
        addresses = interface.get("addr_info")
        if not isinstance(name, str) or not isinstance(addresses, list):
            continue
        for address in addresses:
            if not isinstance(address, Mapping) or address.get("family") != "inet":
                continue
            local = address.get("local")
            if isinstance(local, str):
                candidates.append((name, local))
    return candidates


def select_preferred_ipv4(candidates: Iterable[tuple[str, str]]) -> Optional[str]:
    """Choose a usable IPv4 address, preferring CTF/VPN-style interfaces."""
    ranked: list[tuple[tuple[object, ...], str]] = []
    for interface, address in candidates:
        name = str(interface).strip().lower()
        if not name or name == "lo":
            continue
        try:
            parsed = ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError:
            continue
        if (
            parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_unspecified
            or parsed.is_multicast
        ):
            continue

        prefix_rank = next(
            (
                index
                for index, prefix in enumerate(VPN_INTERFACE_PREFIXES)
                if name.startswith(prefix)
            ),
            len(VPN_INTERFACE_PREFIXES),
        )
        rank = (
            prefix_rank == len(VPN_INTERFACE_PREFIXES),
            prefix_rank,
            not address.startswith("10."),
            not parsed.is_private,
            name,
            int(parsed),
        )
        ranked.append((rank, str(parsed)))

    if not ranked:
        return None
    return min(ranked, key=lambda item: item[0])[1]


def detect_linux_ipv4_address() -> Optional[str]:
    """Discover Linux IPv4 interfaces through one machine-readable ``ip`` call."""
    try:
        output = subprocess.check_output(
            ["ip", "-j", "-4", "addr"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        payload = json.loads(output)
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        UnicodeDecodeError,
    ):
        return None
    return select_preferred_ipv4(parse_linux_ipv4_interfaces(payload))
