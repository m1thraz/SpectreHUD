import json
from urllib.error import URLError

import pytest

from core.update_checker import UpdateCheckError, check_for_updates


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size):
        return json.dumps(self.payload).encode("utf-8")


def _release(tag="v2.1.4", *, prerelease=False):
    return {
        "tag_name": tag,
        "html_url": "https://github.com/m1thraz/SpectreHUD/releases/tag/v2.1.4",
        "published_at": "2026-09-09T10:30:00Z",
        "draft": False,
        "prerelease": prerelease,
        "assets": [
            {
                "name": "SpectreHUD-2.1.4.exe",
                "browser_download_url": "https://github.com/m1thraz/SpectreHUD/releases/download/v2.1.4/SpectreHUD.exe",
            },
            {
                "name": "spectrehud_2.1.4_amd64.deb",
                "browser_download_url": "https://github.com/m1thraz/SpectreHUD/releases/download/v2.1.4/spectrehud.deb",
            },
        ],
    }


def test_newer_release_and_windows_asset_are_detected():
    result = check_for_updates(
        "2.1.3", platform_name="win32", opener=lambda *_args, **_kwargs: _Response(_release())
    )

    assert result.update_available is True
    assert result.latest_version == "2.1.4"
    assert result.asset_url.endswith("SpectreHUD.exe")


def test_multi_digit_versions_are_compared_semantically():
    result = check_for_updates(
        "2.1.10",
        platform_name="linux",
        opener=lambda *_args, **_kwargs: _Response(_release("v2.1.9")),
    )

    assert result.update_available is False
    assert result.asset_url.endswith("spectrehud.deb")


@pytest.mark.parametrize("payload", [_release(prerelease=True), {"tag_name": "not-a-version"}])
def test_unusable_release_responses_fail_closed(payload):
    with pytest.raises(UpdateCheckError):
        check_for_updates(opener=lambda *_args, **_kwargs: _Response(payload))


def test_network_errors_are_normalized():
    def unavailable(*_args, **_kwargs):
        raise URLError("offline")

    with pytest.raises(UpdateCheckError, match="currently unavailable"):
        check_for_updates(opener=unavailable)
