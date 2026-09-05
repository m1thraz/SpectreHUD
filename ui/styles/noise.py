"""Small, shared grain texture; created lazily on the GUI thread."""

from functools import lru_cache
from random import Random

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
