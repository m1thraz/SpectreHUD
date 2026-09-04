"""Small mode-renderer contract used by the application orchestrator."""

from dataclasses import dataclass
from typing import Callable, List, Protocol

from PyQt6.QtWidgets import QWidget


@dataclass(frozen=True)
class RenderResult:
    """Widgets and presentation metadata produced by a mode renderer."""

    cards: List[QWidget]
    footer_text: str
    refresh_geometry: bool = True


class ContentRenderer(Protocol):
    """Builds filter controls and visible content for one application mode."""

    def build_pills(self) -> None: ...

    def render(self) -> RenderResult: ...


class CallbackContentRenderer:
    """Typed adapter for existing specialized controllers."""

    def __init__(
        self,
        build_pills: Callable[[], None],
        render: Callable[[], RenderResult],
    ) -> None:
        self._build_pills = build_pills
        self._render = render

    def build_pills(self) -> None:
        self._build_pills()

    def render(self) -> RenderResult:
        return self._render()
