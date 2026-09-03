"""
Button Stylesheets and Interactive Controls for SpectreHUD.
"""

BUTTONS_QSS_TEMPLATE = """
/* Mode Switcher Tabs */
QPushButton.ModeSwitchBtn {
    background-color: {SURFACE_A85};
    color: {TEXT_FORM};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ModeSwitchBtn:hover {
    background-color: {ACTIVE_BLUE_A25};
    color: {TEXT_WHITE};
    border-color: {CYBER_BLUE};
}

QPushButton.ModeSwitchBtnActive {
    background-color: {NAV_A95};
    color: {CYBER_CYAN};
    border: 1px solid {CYBER_CYAN};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

/* Project Selector Button */
QPushButton.ProjectSelectBtn {
    background-color: {NAV_A75};
    color: {CYBER_BLUE_LIGHT};
    border: 1px solid {ACTIVE_BLUE_A50};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ProjectSelectBtn:hover {
    background-color: {ACTIVE_BLUE_A25};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

/* Screenshot Snip Button */
QPushButton.ScreenshotBtn {
    background-color: {CYAN_A15};
    color: {CYBER_CYAN};
    border: 1px solid {CYAN_A50};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ScreenshotBtn:hover {
    background-color: {CYAN_A30};
    border-color: {CYBER_CYAN};
}

/* Minimize HUD Button */
QPushButton.MinimizeBtn {
    background-color: {SURFACE_A85};
    color: {TEXT_FORM};
    border: 1px solid {BORDER_A80};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 13px;
    font-weight: bold;
    min-width: 22px;
}

QPushButton.MinimizeBtn:hover {
    background-color: {ACTIVE_BLUE_A25};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

/* Close HUD Button (quit with save) */
QPushButton.CloseBtn {
    background-color: {SURFACE_A85};
    color: {TEXT_FORM};
    border: 1px solid {BORDER_A80};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 13px;
    font-weight: bold;
    min-width: 22px;
}

QPushButton.CloseBtn:hover {
    background-color: {ERROR_A20};
    color: {STATUS_ERROR};
    border-color: {ERROR_A70};
}

/* Filter Chips / Pills */
QPushButton.FilterPill {
    background-color: {SURFACE_A80};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_A80};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.FilterPill:hover {
    background-color: {CONTROL_A90};
    color: {TEXT_PRIMARY};
    border-color: {BLUE_A40};
}

QPushButton.FilterPillActive {
    background-color: {ACCENT_NAV_ACTIVE};
    color: {CYBER_CYAN};
    border: 1px solid {CYBER_CYAN};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* Variable Bar Buttons */
QPushButton.AutoDetectBtn {
    background-color: {NAV_A60};
    color: {CYBER_BLUE};
    border: 1px solid {ACTIVE_BLUE_A30};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.AutoDetectBtn:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

QPushButton.VarBadgeBtn {
    background-color: {NAV_A60};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_A80};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.VarBadgeBtn:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {TEXT_PRIMARY};
    border-color: {BLUE_A40};
}

QPushButton.VarBadgeBtnActive {
    background-color: {NAV_A60};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_A80};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.VarBadgeBtnActive:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {TEXT_PRIMARY};
    border-color: {BLUE_A40};
}

QPushButton.MiniPrimaryBtn {
    background-color: {STATUS_SUCCESS_BG};
    color: {TEXT_WHITE};
    border: 1px solid {STATUS_SUCCESS_HOVER};
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.MiniPrimaryBtn:hover {
    background-color: {STATUS_SUCCESS_HOVER};
}

QPushButton.VarPassToggleBtn {
    background-color: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {ACTIVE_BLUE_A30};
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 11px;
}

QPushButton.VarPassToggleBtn:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

/* Edit & Action Buttons */
QPushButton.EditBtn {
    background-color: {CONTROL_A70};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_A60};
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
}

QPushButton.EditBtn:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {CYBER_BLUE};
    border-color: {CYBER_BLUE};
}

/* Copy Buttons */
QPushButton.CopyBtn {
    background-color: {NAV_A85};
    color: {CYBER_BLUE_LIGHT};
    border: 1px solid {ACTIVE_BLUE_A40};
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton.CopyBtn:hover {
    background-color: {CYBER_BLUE_ACTIVE};
    color: {TEXT_WHITE};
    border-color: {CYBER_BLUE};
}

QPushButton.CopyBtnSuccess {
    background-color: {STATUS_SUCCESS_BG};
    color: {TEXT_WHITE};
    border: 1px solid {STATUS_SUCCESS};
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: bold;
    font-size: 12px;
}

/* Danger Buttons */
QPushButton.DangerBtn {
    background-color: transparent;
    color: {STATUS_ERROR};
    border: 1px solid {ERROR_BG_A30};
    border-radius: 5px;
    padding: 3px 6px;
    font-size: 10px;
}

QPushButton.DangerBtn:hover {
    background-color: {STATUS_ERROR_BG};
    color: {TEXT_WHITE};
}

QPushButton.MiniDangerBtn {
    background-color: transparent;
    color: {STATUS_ERROR};
    border: 1px solid {ERROR_BG_A35};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniDangerBtn:hover {
    background-color: {ERROR_BG_A20};
    border-color: {STATUS_ERROR};
}

/* Favorite Star Buttons */
QPushButton.StarBtn {
    background-color: transparent;
    color: {TEXT_DIMMED};
    border: none;
    font-size: 15px;
    padding: 0px 4px;
    min-width: 20px;
    max-width: 24px;
}

QPushButton.StarBtn:hover {
    color: {STATUS_WARNING};
    background-color: {STAR_A15};
    border-radius: 4px;
}

QPushButton.StarBtnActive {
    background-color: transparent;
    color: {STATUS_WARNING};
    border: none;
    font-size: 15px;
    padding: 0px 4px;
    min-width: 20px;
    max-width: 24px;
}

QPushButton.StarBtnActive:hover {
    color: {TEXT_FAVORITE};
    background-color: {STAR_A25};
    border-radius: 4px;
}

/* Inline Command Tweaker Buttons */
QPushButton.TweakBtn {
    background-color: {CONTROL_A85};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}

QPushButton.TweakBtn:hover {
    background-color: {ACTIVE_BLUE_A25};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

QPushButton.TweakBtnActive {
    background-color: {CYAN_A20};
    color: {CYBER_CYAN};
    border: 1px solid {CYBER_CYAN};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}

/* Primary & Secondary Buttons */
QPushButton.PrimaryBtn {
    background-color: {STATUS_SUCCESS_BG};
    color: {TEXT_WHITE};
    border: 1px solid {STATUS_SUCCESS_HOVER};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton.PrimaryBtn:hover {
    background-color: {STATUS_SUCCESS_HOVER};
}

QPushButton.SecondaryBtn {
    background-color: {CONTROL_A80};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    padding: 5px 12px;
}

QPushButton.SecondaryBtn:hover {
    background-color: {BORDER_A90};
    color: {TEXT_PRIMARY};
}

QPushButton.FormatToolBtn {
    background-color: {CONTROL_A80};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_A80};
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 11px;
    min-width: 18px;
}

QPushButton.FormatToolBtn:hover {
    background-color: {BORDER_A90};
    color: {TEXT_PRIMARY};
}

QPushButton.BrowseBtn {
    background-color: {CONTROL_A85};
    color: {CYBER_BLUE};
    border: 1px solid {ACTIVE_BLUE_A40};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.BrowseBtn:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

QPushButton.MiniActionBtn {
    background-color: {CONTROL_A85};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniActionBtn:hover {
    background-color: {BORDER_A95};
    color: {CYBER_CYAN};
    border-color: {CYAN_A40};
}

/* REC Indicator Button */
QPushButton#RecIndicatorBtn {
    background-color: {ERROR_A20};
    border: 1px solid {ERROR_A70};
    border-radius: 4px;
    color: {TEXT_REC};
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    letter-spacing: 0.5px;
}

QPushButton#RecIndicatorBtn:hover {
    background-color: {ERROR_A35};
    border-color: {TEXT_REC};
}

QPushButton#RecIndicatorBtn[paused="true"] {
    background-color: {MUTED_A25};
    border: 1px solid {MUTED_A60};
    color: {TEXT_FORM};
    font-weight: 700;
}

QPushButton#RecIndicatorBtn[paused="true"]:hover {
    background-color: {MUTED_A40};
    color: {TEXT_WHITE};
    border-color: {CYBER_BLUE};
}

/* Settings Navigation Buttons */
QPushButton.SettingsNavBtn {
    background-color: transparent;
    color: {TEXT_FORM};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.SettingsNavBtn:hover {
    background-color: {ACTIVE_BLUE_A20};
    color: {TEXT_WHITE};
}

QPushButton.SettingsNavBtnActive {
    background-color: {NAV_A95};
    color: {CYBER_CYAN};
    border: 1px solid {CYAN_A60};
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
}
"""
