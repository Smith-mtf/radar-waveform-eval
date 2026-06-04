"""主窗口定义。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """雷达波形性能评估软件的最小主窗口。"""

    def __init__(self) -> None:
        """初始化主窗口布局。"""
        super().__init__()
        self.setWindowTitle("雷达波形性能评估软件 V1.0")
        self.resize(1200, 800)
        self.setCentralWidget(self._build_central_widget())

    def _build_central_widget(self) -> QWidget:
        """构建包含左侧导航和右侧占位内容的中心区域。"""
        splitter = QSplitter()

        navigation = QListWidget()
        navigation.addItems(
            [
                "波形配置",
                "场景配置",
                "评估执行",
                "结果可视化",
                "方案对比",
                "报告导出",
            ],
        )
        navigation.setFixedWidth(220)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        title_label = QLabel("雷达波形性能评估软件 V1.0")
        title_label.setObjectName("mainTitleLabel")
        content_layout.addWidget(title_label)
        content_layout.addStretch(1)

        splitter.addWidget(navigation)
        splitter.addWidget(content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        return splitter

