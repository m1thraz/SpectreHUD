"""
Screenshot domain package for SpectreHUD.

Provides project-scoped screenshot capture, persistence,
and transaction coordination.
"""

from core.screenshots.manager import ScreenshotManager, ScreenshotSaveError
from core.screenshots.transaction_service import (
    ScreenshotTransactionResult,
    ScreenshotTransactionService,
)

__all__ = [
    "ScreenshotManager",
    "ScreenshotSaveError",
    "ScreenshotTransactionResult",
    "ScreenshotTransactionService",
]
