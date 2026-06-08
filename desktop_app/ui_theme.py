"""桌面端统一视觉样式。"""

from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 12px;
    color: #1f2933;
}

QMainWindow, QDialog {
    background: #eef2f5;
}

QMenuBar {
    background: #f8fafc;
    border-bottom: 1px solid #d7dee6;
    padding: 3px 8px;
}

QMenuBar::item {
    padding: 5px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background: #e8eef4;
}

QMenu {
    background: #ffffff;
    border: 1px solid #cfd8e3;
    padding: 4px;
}

QMenu::item {
    padding: 6px 28px 6px 18px;
}

QMenu::item:selected {
    background: #e8f3f1;
    color: #0f766e;
}

QStatusBar {
    background: #f8fafc;
    border-top: 1px solid #d7dee6;
}

QFrame#AppSidebar {
    background: #f8fafc;
    border-right: 1px solid #d7dee6;
}

QLabel#AppTitle {
    font-size: 17px;
    font-weight: 700;
    color: #102a43;
}

QLabel#AppSubtitle {
    color: #62748a;
}

QLabel#PageTitle {
    font-size: 18px;
    font-weight: 700;
    color: #102a43;
}

QLabel#PageSubtitle {
    color: #62748a;
}

QLabel#SectionTitle {
    font-size: 13px;
    font-weight: 700;
    color: #243b53;
}

QFrame#PageSurface {
    background: #ffffff;
    border: 1px solid #d7dee6;
    border-radius: 8px;
}

QFrame#Panel {
    background: #ffffff;
    border: 1px solid #d7dee6;
    border-radius: 8px;
}

QFrame#SoftPanel {
    background: #f8fafc;
    border: 1px solid #dce3eb;
    border-radius: 8px;
}

QListWidget#NavigationList {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget#NavigationList::item {
    min-height: 36px;
    padding: 8px 12px;
    margin: 2px 10px;
    border-radius: 6px;
    color: #334e68;
}

QListWidget#NavigationList::item:selected {
    background: #d9f0ed;
    color: #0f766e;
    font-weight: 700;
}

QListWidget#NavigationList::item:hover {
    background: #edf7f5;
}

QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 5px;
    padding: 5px 7px;
    selection-background-color: #99d6ce;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #2f9e8f;
}

QPushButton {
    background: #ffffff;
    border: 1px solid #b8c5d2;
    border-radius: 5px;
    padding: 7px 12px;
    color: #1f2933;
}

QPushButton:hover {
    background: #f1f5f9;
}

QPushButton:pressed {
    background: #e2e8f0;
}

QPushButton:disabled {
    color: #9aa8b7;
    background: #eef2f5;
    border-color: #d7dee6;
}

QPushButton#PrimaryButton {
    background: #0f766e;
    border: 1px solid #0f766e;
    color: #ffffff;
    font-weight: 700;
}

QPushButton#PrimaryButton:hover {
    background: #0b8a80;
}

QPushButton#DangerButton {
    background: #ffffff;
    border: 1px solid #d97777;
    color: #9f1239;
}

QGroupBox {
    background: #ffffff;
    border: 1px solid #d7dee6;
    border-radius: 8px;
    margin-top: 18px;
    padding: 14px 12px 12px 12px;
    font-weight: 700;
    color: #243b53;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}

QTabWidget::pane {
    border: 1px solid #d7dee6;
    border-radius: 8px;
    background: #ffffff;
}

QTabBar::tab {
    background: #eef2f5;
    border: 1px solid #d7dee6;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 7px 12px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #0f766e;
    font-weight: 700;
}

QTableWidget {
    background: #ffffff;
    alternate-background-color: #f8fafc;
    gridline-color: #e2e8f0;
    border: 1px solid #d7dee6;
    border-radius: 6px;
}

QHeaderView::section {
    background: #eef2f5;
    color: #334e68;
    border: none;
    border-right: 1px solid #d7dee6;
    border-bottom: 1px solid #d7dee6;
    padding: 6px;
    font-weight: 700;
}

QProgressBar {
    border: 1px solid #cfd8e3;
    border-radius: 5px;
    background: #eef2f5;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: #2f9e8f;
    border-radius: 5px;
}
"""

