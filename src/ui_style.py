"""Shared style tokens and helpers for the Qt client UI."""

from __future__ import annotations

ACCENT_DEFAULT_HEX = "#FFD740"
ACCENT_HOVER_HEX = "#FFFF74"
ACCENT_PRESSED_HEX = "#FFC400"
MUTED_DISABLED_HEX = "#4F5B62"
PANEL_BACKGROUND_HEX = "#232629"
SURFACE_BACKGROUND_HEX = "#263238"
SELECTION_BACKGROUND_RGBA: str = "rgba(255, 215, 64, 0.14)"


def primary_accent_button_style(object_name: str | None = None) -> str:
    """Return the filled yellow style used by primary action buttons."""

    selector = _selector("QPushButton", object_name)
    return (
        f"{selector} {{"
        f"background-color: {ACCENT_DEFAULT_HEX};"
        "color: #000000;"
        f"border: 1px solid {ACCENT_DEFAULT_HEX};"
        "border-radius: 4px;"
        "font-weight: 600;"
        "}"
        f"{selector}:hover {{"
        f"background-color: {ACCENT_HOVER_HEX};"
        f"border-color: {ACCENT_HOVER_HEX};"
        "}"
        f"{selector}:pressed {{"
        f"background-color: {ACCENT_PRESSED_HEX};"
        f"border-color: {ACCENT_PRESSED_HEX};"
        "}"
    )


def secondary_accent_button_style(
    object_name: str | None = None,
    include_disabled_state: bool = False,
) -> str:
    """Return the outlined yellow style used by secondary action buttons."""

    selector = _selector("QPushButton", object_name)
    hover_selector = (
        f"{selector}:hover:!disabled" if include_disabled_state else f"{selector}:hover"
    )
    pressed_selector = (
        f"{selector}:pressed:!disabled"
        if include_disabled_state
        else f"{selector}:pressed"
    )

    style = (
        f"{selector} {{"
        "background-color: transparent;"
        f"color: {ACCENT_DEFAULT_HEX};"
        f"border: 1px solid {ACCENT_DEFAULT_HEX};"
        "border-radius: 4px;"
        "font-weight: 600;"
        "}"
        f"{hover_selector} {{"
        "background-color: rgba(255, 215, 64, 0.10);"
        f"color: {ACCENT_HOVER_HEX};"
        f"border-color: {ACCENT_HOVER_HEX};"
        "}"
        f"{pressed_selector} {{"
        "background-color: rgba(255, 196, 0, 0.18);"
        f"color: {ACCENT_PRESSED_HEX};"
        f"border-color: {ACCENT_PRESSED_HEX};"
        "}"
    )

    if include_disabled_state:
        style += (
            f"{selector}:disabled {{"
            f"color: {MUTED_DISABLED_HEX};"
            f"border-color: {MUTED_DISABLED_HEX};"
            "}"
        )

    return style


def progress_bar_style(object_name: str | None = None) -> str:
    """Return the accent style used by application progress bars."""

    selector = _selector("QProgressBar", object_name)
    return (
        f"{selector} {{"
        f"background-color: {SURFACE_BACKGROUND_HEX};"
        f"border: 1px solid {MUTED_DISABLED_HEX};"
        "border-radius: 5px;"
        "text-align: center;"
        "}"
        f"{selector}::chunk {{"
        f"background-color: {ACCENT_DEFAULT_HEX};"
        "border-radius: 4px;"
        "}"
    )


def result_tree_style(object_name: str | None = None) -> str:
    """Return the panel style used by the duplicate result tree."""

    selector = _selector("QTreeWidget", object_name)
    return (
        f"{selector} {{"
        f"background-color: {PANEL_BACKGROUND_HEX};"
        f"alternate-background-color: {SURFACE_BACKGROUND_HEX};"
        f"border: 1px solid {MUTED_DISABLED_HEX};"
        "border-radius: 5px;"
        "}"
        f"{selector} QHeaderView {{"
        f"background-color: {PANEL_BACKGROUND_HEX};"
        "}"
        f"{selector}::item {{"
        "min-height: 22px;"
        "padding: 1px 4px;"
        "}"
        f"{selector}::item:selected {{"
        f"background-color: {SELECTION_BACKGROUND_RGBA};"
        f"color: {ACCENT_DEFAULT_HEX};"
        "}"
    )


def context_menu_style(object_name: str | None = None) -> str:
    """Return the selected-item style used by application context menus."""

    selector = _selector("QMenu", object_name)
    return (
        f"{selector}::item:selected {{"
        f"background-color: {SELECTION_BACKGROUND_RGBA};"
        f"color: {ACCENT_DEFAULT_HEX};"
        "}"
    )


def _selector(base: str, object_name: str | None) -> str:
    if object_name is None:
        return base

    return f"{base}#{object_name}"
