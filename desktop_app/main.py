"""桌面应用入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from desktop_app.windows.main_window import MainWindow


def main() -> int:
    """启动雷达波形性能评估桌面应用。"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("雷达波形性能评估软件 V1.0")
    window.resize(1200, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

