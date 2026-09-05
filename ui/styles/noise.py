"""Small, shared grain texture; created lazily on the GUI thread."""

from functools import lru_cache
from random import Random

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, qRgb


@lru_cache(maxsize=1)
def generate_noise_pixmap() -> QPixmap:
    """Return one deterministic tile, shared by every glass surface."""
    rng = Random(0)
    image = QImage(128, 128, QImage.Format.Format_RGB32)
    for y in range(128):
        for x in range(128):
            value = rng.randrange(256)
            image.setPixel(x, y, qRgb(value, value, value))
    return QPixmap.fromImage(image)


@lru_cache(maxsize=1)
def generate_coarse_noise_pixmap() -> QPixmap:
    """Smooth a periodic coarse field once, avoiding seams between tiled edges."""
    rng = Random(17)
    values = [[rng.randrange(256) for _ in range(32)] for _ in range(32)]
    image = QImage(96, 96, QImage.Format.Format_RGB32)
    for y in range(96):
        for x in range(96):
            value = values[y % 32][x % 32]
            image.setPixel(x, y, qRgb(value, value, value))
    enlarged = image.scaled(
        768, 768, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    return QPixmap.fromImage(enlarged.copy(256, 256, 256, 256))
