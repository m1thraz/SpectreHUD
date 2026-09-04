"""Generates a proper multi-resolution Windows ICO file containing
16x16, 24x24, 32x32, 48x48, 64x64, 128x128, and 256x256 resolutions.
"""
import struct
from pathlib import Path
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer


def create_multires_ico(svg_path: Path, output_ico_path: Path) -> None:
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load SVG from {svg_path}")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images_png_bytes = []

    for s in sizes:
        img = QImage(s, s, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        images_png_bytes.append(bytes(buf.data()))

    # ICONDIR: 3 WORDs: reserved=0, type=1 (icon), count=len(sizes)
    count = len(sizes)
    header = struct.pack("<HHH", 0, 1, count)

    # Calculate offsets
    entries = []
    offset = 6 + 16 * count
    for s, png_data in zip(sizes, images_png_bytes):
        w = 0 if s == 256 else s
        h = 0 if s == 256 else s
        entries.append(
            struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png_data), offset)
        )
        offset += len(png_data)

    ico_bytes = header + b"".join(entries) + b"".join(images_png_bytes)
    output_ico_path.write_bytes(ico_bytes)
    print(f"[+] Multi-resolution ICO successfully written to {output_ico_path} ({len(ico_bytes)} bytes, {count} sizes: {sizes})")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    svg_file = base_dir / "data" / "icon.svg"
    ico_file = base_dir / "data" / "icon.ico"
    create_multires_ico(svg_file, ico_file)
