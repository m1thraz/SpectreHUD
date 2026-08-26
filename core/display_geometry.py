from dataclasses import dataclass
from typing import Sequence, Tuple, Union


@dataclass(frozen=True)
class ScreenGeometry:
    """
    Representation of a single display screen in virtual desktop coordinates.
    Completely independent of Qt for pure Python unit testing.
    """
    x: int
    y: int
    width: int
    height: int
    device_pixel_ratio: float = 1.0

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class VirtualDesktopBoundingBox:
    """
    Bounding box enclosing all active display screens in virtual desktop space.
    Correctly supports negative offsets (e.g. monitors placed to the left or above primary).
    """
    min_x: int
    min_y: int
    width: int
    height: int

    @property
    def max_x(self) -> int:
        return self.min_x + self.width

    @property
    def max_y(self) -> int:
        return self.min_y + self.height

    def to_tuple(self) -> Tuple[int, int, int, int]:
        return (self.min_x, self.min_y, self.width, self.height)


ScreenInput = Union[ScreenGeometry, Tuple[int, int, int, int]]
OriginInput = Union[VirtualDesktopBoundingBox, Tuple[int, int]]


def _to_screen_geom(screen: ScreenInput) -> ScreenGeometry:
    if isinstance(screen, ScreenGeometry):
        return screen
    if isinstance(screen, (tuple, list)) and len(screen) >= 4:
        dpr = float(screen[4]) if len(screen) > 4 else 1.0
        return ScreenGeometry(int(screen[0]), int(screen[1]), int(screen[2]), int(screen[3]), dpr)
    raise TypeError(f"Invalid screen geometry format: {screen}")


def compute_virtual_desktop_bounding_box(
    screens: Sequence[ScreenInput]
) -> VirtualDesktopBoundingBox:
    """
    Computes the overarching bounding box for a collection of screens.
    Handles negative offsets and irregular screen arrangements.

    If screens list is empty, returns (0, 0, 0, 0).
    """
    if not screens:
        return VirtualDesktopBoundingBox(min_x=0, min_y=0, width=0, height=0)

    geoms = [_to_screen_geom(s) for s in screens]

    min_x = min(g.x for g in geoms)
    min_y = min(g.y for g in geoms)
    max_x = max(g.right for g in geoms)
    max_y = max(g.bottom for g in geoms)

    total_width = max(0, max_x - min_x)
    total_height = max(0, max_y - min_y)

    return VirtualDesktopBoundingBox(
        min_x=min_x,
        min_y=min_y,
        width=total_width,
        height=total_height
    )


def compute_screen_paint_offset(
    screen: ScreenInput,
    virtual_origin: OriginInput
) -> Tuple[int, int]:
    """
    Computes the (offset_x, offset_y) top-left paint coordinate for a screen
    relative to the virtual desktop bounding box origin (min_x, min_y).
    """
    geom = _to_screen_geom(screen)

    if isinstance(virtual_origin, VirtualDesktopBoundingBox):
        orig_x, orig_y = virtual_origin.min_x, virtual_origin.min_y
    elif isinstance(virtual_origin, (tuple, list)) and len(virtual_origin) >= 2:
        orig_x, orig_y = int(virtual_origin[0]), int(virtual_origin[1])
    else:
        raise TypeError(f"Invalid virtual origin format: {virtual_origin}")

    offset_x = geom.x - orig_x
    offset_y = geom.y - orig_y

    return (offset_x, offset_y)