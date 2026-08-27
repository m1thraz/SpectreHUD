"""
Menu Action Data Transfer Objects (DTO) for UI-independent controllers.
Allows controllers to define actions, menus, and toolbars without instantiating Qt widgets.
"""
from dataclasses import dataclass
from typing import Optional, Callable, Any


@dataclass
class MenuAction:
    """Represents a generic menu or toolbar action independent of any UI framework."""
    id: str
    text: str = ""
    icon: Optional[str] = None
    enabled: bool = True
    checked: bool = False
    is_separator: bool = False
    is_section_header: bool = False
    shortcut: Optional[str] = None
    tooltip: Optional[str] = None
    callback: Optional[Callable[[], Any]] = None
    data: Any = None

    @classmethod
    def separator(cls, id: str = "separator") -> "MenuAction":
        return cls(id=id, is_separator=True)

    @classmethod
    def section_header(cls, text: str, id: str = "section_header") -> "MenuAction":
        return cls(id=id, text=text, is_section_header=True, enabled=False)
