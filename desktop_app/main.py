"""桌面应用入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from desktop_app.app import configure_application, create_main_window


def main() -> int:
    """启动雷达波形性能评估桌面应用。"""
    app = QApplication(sys.argv)
    configure_application()
    window, startup_errors = create_main_window()
    window.show()
    if startup_errors:
        QMessageBox.warning(window, "默认配置加载失败", "\n".join(startup_errors))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
