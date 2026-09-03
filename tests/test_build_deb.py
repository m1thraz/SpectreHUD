"""
Unit tests for the Debian package (.deb) builder script.
"""

from pathlib import Path
from unittest.mock import patch
from scripts.build_deb import (
    generate_control_file,
    generate_launcher_wrapper,
    generate_postinst_script,
    generate_postrm_script,
    prepare_deb_staging_tree,
    build_deb_package,
    get_project_version,
)


def test_generate_control_file():
    content = generate_control_file("2.0.6", arch="amd64")
    assert "Package: spectrehud" in content
    assert "Version: 2.0.6" in content
    assert "Architecture: amd64" in content
    assert "Depends: libgl1" in content
    assert content.endswith("\n")


def test_generate_scripts():
    postinst = generate_postinst_script()
    assert "#!/bin/sh" in postinst
    assert "update-desktop-database" in postinst

    postrm = generate_postrm_script()
    assert "#!/bin/sh" in postrm
    assert "gtk-update-icon-cache" in postrm

    launcher = generate_launcher_wrapper()
    assert "exec /opt/spectrehud/spectrehud" in launcher


def test_prepare_deb_staging_tree(tmp_path):
    project_dir = Path(__file__).resolve().parent.parent
    staging_dir = tmp_path / "deb_staging"

    prepare_deb_staging_tree(project_dir, staging_dir, "2.0.6")

    # Assert standard Debian structure
    assert (staging_dir / "DEBIAN" / "control").exists()
    assert (staging_dir / "DEBIAN" / "postinst").exists()
    assert (staging_dir / "DEBIAN" / "postrm").exists()
    assert (staging_dir / "usr" / "bin" / "spectrehud").exists()
    assert (staging_dir / "usr" / "share" / "applications" / "spectrehud.desktop").exists()
    assert (staging_dir / "opt" / "spectrehud").exists()


def test_build_deb_package_mocked(tmp_path):
    project_dir = Path(__file__).resolve().parent.parent

    with patch("shutil.which", return_value=None):
        deb_path = build_deb_package(project_dir=project_dir, skip_pyinstaller=True)
        version = get_project_version(project_dir)
        assert deb_path.name == f"spectrehud_{version}_amd64.deb"
