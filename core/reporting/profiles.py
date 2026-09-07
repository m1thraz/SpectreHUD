"""Presentation profiles supported by standalone HTML report export."""

from enum import Enum


class ReportExportProfile(str, Enum):
    INTERACTIVE = "interactive"
    PROFESSIONAL_PRINT = "professional_print"
