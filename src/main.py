"""Application entrypoint for Duplicate Size Scanner."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

APPLICATION_ID = "DuplicateSizeScanner"
APPLICATION_NAME = "Duplicate Size Scanner"
ORGANIZATION_NAME = "DuplicateSizeScanner"

LOGGER = logging.getLogger(__name__)

# Enables support for direct script execution
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    """Run the Duplicate Size Scanner Qt application."""

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication
    from qt_material import apply_stylesheet

    from src.ui import DuplicateSizeScannerWindow

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APPLICATION_ID)

    app = QApplication(sys.argv)
    app.setApplicationDisplayName(APPLICATION_NAME)
    try:
        apply_stylesheet(app, theme="dark_amber.xml")
    except (OSError, ValueError) as err:
        LOGGER.warning("Could not apply qt-material theme: %s", err)

    window = DuplicateSizeScannerWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
