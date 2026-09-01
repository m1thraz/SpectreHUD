"""Deterministic Linux network discovery tests using synthetic ``ip -j`` data."""

import json
import subprocess
from unittest.mock import patch

import pytest

from core.net_detector import NetDetector
from core.platform.network import detect_linux_ipv4_address, select_preferred_ipv4


def _interface(name: str, *addresses: str) -> dict:
    return {
        "ifname": name,
        "addr_info": [
            {"family": "inet", "local": address, "prefixlen": 24}
            for address in addresses
        ],
    }


@pytest.mark.parametrize(
    ("interfaces", "expected"),
    [
        ([_interface("tun0", "10.10.14.2")], "10.10.14.2"),
        ([_interface("tun1", "10.10.15.2")], "10.10.15.2"),
        ([_interface("wg0", "10.20.0.2")], "10.20.0.2"),
        ([_interface("tailscale0", "100.64.0.2")], "100.64.0.2"),
        ([_interface("eth0", "192.168.1.20")], "192.168.1.20"),
        ([_interface("eth0", "192.168.1.20"), _interface("tun0", "10.10.14.3")], "10.10.14.3"),
        ([_interface("lo", "127.0.0.1")], None),
        (
            [
                _interface("wg0", "10.20.0.2"),
                _interface("tun1", "10.10.15.2"),
                _interface("tun0", "10.10.14.2"),
            ],
            "10.10.14.2",
        ),
    ],
)
def test_linux_interface_selection(interfaces, expected):
    candidates = [
        (interface["ifname"], address["local"])
        for interface in interfaces
        for address in interface["addr_info"]
    ]
    assert select_preferred_ipv4(candidates) == expected


def test_linux_detection_invokes_ip_once_and_parses_json():
    output = json.dumps(
        [
            _interface("lo", "127.0.0.1"),
            _interface("eth0", "192.168.1.20"),
            _interface("tun0", "10.10.14.4"),
        ]
    )
    with patch("core.platform.network.subprocess.check_output", return_value=output) as command:
        assert detect_linux_ipv4_address() == "10.10.14.4"

    command.assert_called_once_with(
        ["ip", "-j", "-4", "addr"],
        text=True,
        stderr=subprocess.DEVNULL,
    )


@pytest.mark.parametrize(
    "result",
    ["", "not-json", "{}", "[]"],
)
def test_linux_detection_handles_empty_broken_or_missing_candidates(result):
    with patch("core.platform.network.subprocess.check_output", return_value=result):
        assert detect_linux_ipv4_address() is None


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("ip not installed"),
        subprocess.CalledProcessError(1, ["ip"]),
        UnicodeDecodeError("utf-8", b"x", 0, 1, "invalid"),
    ],
)
def test_linux_detection_contains_command_failures(failure):
    with patch("core.platform.network.subprocess.check_output", side_effect=failure):
        assert detect_linux_ipv4_address() is None


def test_macos_does_not_invoke_linux_ip_command():
    with (
        patch("core.net_detector.platform.system", return_value="Darwin"),
        patch("core.net_detector.detect_linux_ipv4_address") as linux_detector,
        patch.object(NetDetector, "_detect_via_sockets", return_value=None),
        patch.object(NetDetector, "_detect_outbound_ip", return_value=None),
    ):
        assert NetDetector.detect_attacker_ip() is None

    linux_detector.assert_not_called()


def test_linux_uses_platform_detector_before_generic_fallbacks():
    with (
        patch("core.net_detector.platform.system", return_value="Linux"),
        patch(
            "core.net_detector.detect_linux_ipv4_address",
            return_value="10.10.14.9",
        ) as linux_detector,
        patch.object(NetDetector, "_detect_via_sockets") as socket_detector,
        patch.object(NetDetector, "_detect_outbound_ip") as outbound_detector,
    ):
        assert NetDetector.detect_attacker_ip() == "10.10.14.9"

    linux_detector.assert_called_once_with()
    socket_detector.assert_not_called()
    outbound_detector.assert_not_called()
