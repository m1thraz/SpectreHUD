"""
Button Stylesheets and Interactive Controls for SpectreHUD.
"""

BUTTONS_QSS = """
/* Mode Switcher Tabs */
QPushButton.ModeSwitchBtn {
    background-color: rgba(22, 27, 34, 0.85);
    color: #e6edf3;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ModeSwitchBtn:hover {
    background-color: rgba(56, 139, 253, 0.25);
    color: #ffffff;
    border-color: #58a6ff;
}

QPushButton.ModeSwitchBtnActive {
    background-color: rgba(31, 41, 61, 0.95);
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

/* Project Selector Button */
QPushButton.ProjectSelectBtn {
    background-color: rgba(31, 41, 61, 0.75);
    color: #79c0ff;
    border: 1px solid rgba(56, 139, 253, 0.5);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ProjectSelectBtn:hover {
    background-color: rgba(56, 139, 253, 0.25);
    color: #00e5ff;
    border-color: #00e5ff;
}

/* Screenshot Snip Button */
QPushButton.ScreenshotBtn {
    background-color: rgba(0, 229, 255, 0.15);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.5);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ScreenshotBtn:hover {
    background-color: rgba(0, 229, 255, 0.3);
    border-color: #00e5ff;
}

/* Minimize HUD Button */
QPushButton.MinimizeBtn {
    background-color: rgba(22, 27, 34, 0.85);
    color: #e6edf3;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 13px;
    font-weight: bold;
    min-width: 22px;
}

QPushButton.MinimizeBtn:hover {
    background-color: rgba(56, 139, 253, 0.25);
    color: #00e5ff;
    border-color: #00e5ff;
}

/* Filter Chips / Pills */
QPushButton.FilterPill {
    background-color: rgba(22, 27, 34, 0.8);
    color: #8b949e;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.FilterPill:hover {
    background-color: rgba(33, 38, 45, 0.9);
    color: #f0f6fc;
    border-color: rgba(88, 166, 255, 0.4);
}

QPushButton.FilterPillActive {
    background-color: #1f293d;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* Variable Bar Buttons */
QPushButton.AutoDetectBtn {
    background-color: rgba(31, 41, 61, 0.6);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.3);
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.AutoDetectBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #00e5ff;
    border-color: #00e5ff;
}

QPushButton.MiniPrimaryBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.MiniPrimaryBtn:hover {
    background-color: #2ea043;
}

QPushButton.VarPassToggleBtn {
    background-color: transparent;
    color: #8b949e;
    border: 1px solid rgba(56, 139, 253, 0.3);
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 11px;
}

QPushButton.VarPassToggleBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #00e5ff;
    border-color: #00e5ff;
}

/* Edit & Action Buttons */
QPushButton.EditBtn {
    background-color: rgba(33, 38, 45, 0.7);
    color: #8b949e;
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
}

QPushButton.EditBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #58a6ff;
    border-color: #58a6ff;
}

/* Copy Buttons */
QPushButton.CopyBtn {
    background-color: rgba(31, 41, 61, 0.85);
    color: #79c0ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton.CopyBtn:hover {
    background-color: #388bfd;
    color: #ffffff;
    border-color: #58a6ff;
}

QPushButton.CopyBtnSuccess {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #39d353;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: bold;
    font-size: 12px;
}

/* Danger Buttons */
QPushButton.DangerBtn {
    background-color: transparent;
    color: #f85149;
    border: 1px solid rgba(218, 54, 51, 0.3);
    border-radius: 5px;
    padding: 3px 6px;
    font-size: 10px;
}

QPushButton.DangerBtn:hover {
    background-color: #da3633;
    color: #ffffff;
}

QPushButton.MiniDangerBtn {
    background-color: transparent;
    color: #f85149;
    border: 1px solid rgba(218, 54, 51, 0.35);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniDangerBtn:hover {
    background-color: rgba(218, 54, 51, 0.2);
    border-color: #f85149;
}

/* Favorite Star Buttons */
QPushButton.StarBtn {
    background-color: transparent;
    color: #6e7681;
    border: none;
    font-size: 15px;
    padding: 0px 4px;
    min-width: 20px;
    max-width: 24px;
}

QPushButton.StarBtn:hover {
    color: #e3b341;
    background-color: rgba(227, 179, 65, 0.15);
    border-radius: 4px;
}

QPushButton.StarBtnActive {
    background-color: transparent;
    color: #e3b341;
    border: none;
    font-size: 15px;
    padding: 0px 4px;
    min-width: 20px;
    max-width: 24px;
}

QPushButton.StarBtnActive:hover {
    color: #ffd700;
    background-color: rgba(227, 179, 65, 0.25);
    border-radius: 4px;
}

/* Inline Command Tweaker Buttons */
QPushButton.TweakBtn {
    background-color: rgba(33, 38, 45, 0.85);
    color: #8b949e;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}

QPushButton.TweakBtn:hover {
    background-color: rgba(56, 139, 253, 0.25);
    color: #00e5ff;
    border-color: #00e5ff;
}

QPushButton.TweakBtnActive {
    background-color: rgba(0, 229, 255, 0.2);
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}

/* Primary & Secondary Buttons */
QPushButton.PrimaryBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton.PrimaryBtn:hover {
    background-color: #2ea043;
}

QPushButton.SecondaryBtn {
    background-color: rgba(33, 38, 45, 0.8);
    color: #c9d1d9;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    padding: 5px 12px;
}

QPushButton.SecondaryBtn:hover {
    background-color: rgba(48, 54, 61, 0.9);
    color: #f0f6fc;
}

QPushButton.BrowseBtn {
    background-color: rgba(33, 38, 45, 0.85);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.BrowseBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #00e5ff;
    border-color: #00e5ff;
}

QPushButton.MiniActionBtn {
    background-color: rgba(33, 38, 45, 0.85);
    color: #c9d1d9;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniActionBtn:hover {
    background-color: rgba(48, 54, 61, 0.95);
    color: #00e5ff;
    border-color: rgba(0, 229, 255, 0.4);
}

/* REC Indicator Button */
QPushButton#RecIndicatorBtn {
    background-color: rgba(248, 81, 73, 0.2);
    border: 1px solid rgba(248, 81, 73, 0.7);
    border-radius: 4px;
    color: #ff7b72;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    letter-spacing: 0.5px;
}

QPushButton#RecIndicatorBtn:hover {
    background-color: rgba(248, 81, 73, 0.35);
    border-color: #ff7b72;
}

QPushButton#RecIndicatorBtn[paused="true"] {
    background-color: rgba(110, 118, 129, 0.25);
    border: 1px solid rgba(110, 118, 129, 0.6);
    color: #e6edf3;
    font-weight: 700;
}

QPushButton#RecIndicatorBtn[paused="true"]:hover {
    background-color: rgba(110, 118, 129, 0.4);
    color: #ffffff;
    border-color: #58a6ff;
}

/* Settings Navigation Buttons */
QPushButton.SettingsNavBtn {
    background-color: transparent;
    color: #e6edf3;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.SettingsNavBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #ffffff;
}

QPushButton.SettingsNavBtnActive {
    background-color: rgba(31, 41, 61, 0.95);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.6);
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
}
"""
