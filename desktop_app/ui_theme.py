"""桌面端暗色兜底样式。"""

from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 12px;
    color: #d7dee8;
}

QMainWindow, QDialog {
    background: #111827;
}

QMenuBar {
    background: #0b1220;
    border-bottom: 1px solid #243244;
    padding: 3px 8px;
}

QMenuBar::item {
    padding: 5px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background: #1f2a3a;
}

QMenu {
    background: #111827;
    border: 1px solid #2f3f55;
}

QMenu::item {
    padding: 7px 28px 7px 18px;
}

QMenu::item:selected {
    background: #1f6feb;
}

QStatusBar {
    background: #0b1220;
    border-top: 1px solid #243244;
}

QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 5px 7px;
    selection-background-color: #2563eb;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #38bdf8;
}

QPushButton {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 5px;
    padding: 7px 12px;
    color: #e5edf7;
}

QPushButton:hover {
    background: #26364f;
}

QPushButton:pressed {
    background: #172033;
}

QPushButton:disabled {
    color: #64748b;
    background: #111827;
    border-color: #243244;
}

QPushButton#PrimaryButton {
    background: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: 700;
}

QPushButton#PrimaryButton:hover {
    background: #1d4ed8;
}

QPushButton#AccentButton {
    background: #0891b2;
    border: 1px solid #22d3ee;
    color: #ffffff;
    font-weight: 700;
}

QGroupBox {
    background: #111827;
    border: 1px solid #2f3f55;
    border-radius: 8px;
    margin-top: 18px;
    padding: 14px 12px 12px 12px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #93c5fd;
}

QTabWidget::pane {
    border: 1px solid #2f3f55;
    border-radius: 8px;
    background: #0f172a;
}

QTabBar::tab {
    background: #111827;
    border: 1px solid #2f3f55;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 8px 14px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #0f172a;
    color: #38bdf8;
    font-weight: 700;
}

QTableWidget {
    background: #0f172a;
    alternate-background-color: #111827;
    gridline-color: #243244;
    border: 1px solid #2f3f55;
    border-radius: 6px;
}

QHeaderView::section {
    background: #111827;
    color: #bfdbfe;
    border: none;
    border-right: 1px solid #243244;
    border-bottom: 1px solid #243244;
    padding: 6px;
    font-weight: 700;
}
"""
