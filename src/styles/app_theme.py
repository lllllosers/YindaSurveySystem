from __future__ import annotations


APP_QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 14px;
    color: #263238;
}

QMainWindow {
    background: #f3f6f9;
}

QToolTip {
    background: #263746;
    color: white;
    border: none;
    padding: 6px 8px;
}

QFrame#sidebar {
    background: #1f3244;
    border: none;
}

QLabel#appTitle {
    color: white;
    font-size: 21px;
    font-weight: 700;
}

QLabel#appSubtitle {
    color: #c5d2dd;
    font-size: 13px;
}

QPushButton#navButton {
    min-height: 40px;
    padding: 0 12px;
    border: none;
    border-radius: 7px;
    background: transparent;
    color: #e8eef3;
    text-align: left;
    font-size: 15px;
    font-weight: 500;
}

QPushButton#navButton:hover {
    background: #2d475f;
    color: white;
}

QPushButton#navButton:pressed {
    background: #35566f;
}

QLabel#navSectionLabel {
    margin-top: 8px;
    padding: 5px 10px 2px 10px;
    color: #8fa6b8;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#navButton[navLevel="child"] {
    padding-left: 24px;
}

QLabel#versionLabel {
    color: #92a7b8;
    font-size: 12px;
}

QFrame#topBar,
QFrame#contentCard {
    background: white;
    border: 1px solid #dfe5eb;
    border-radius: 9px;
}

QLabel#pageTitle {
    color: #1e3447;
    font-size: 23px;
    font-weight: 700;
}

QLabel#contentLabel {
    color: #607080;
    font-size: 15px;
}

QLabel#pageDescription {
    color: #607080;
    font-size: 13px;
}

QLabel[title="true"] {
    color: #1f4e79;
    font-size: 18px;
    font-weight: 700;
}

QFrame[card="true"] {
    background: white;
    border: 1px solid #dfe5eb;
    border-radius: 9px;
}

QPushButton {
    min-height: 34px;
    padding: 0 14px;
    border: 1px solid #cbd5df;
    border-radius: 6px;
    background: white;
    color: #29404f;
    font-weight: 500;
}

QPushButton:hover {
    background: #edf5fb;
    border-color: #9ebed6;
}

QPushButton:pressed {
    background: #dcebf6;
}

QPushButton:disabled {
    color: #9aa7b2;
    background: #f4f6f8;
    border-color: #e1e5e9;
}

QPushButton[role="primary"] {
    color: white;
    background: #2f6f9f;
    border-color: #2f6f9f;
}

QPushButton[role="primary"]:hover {
    background: #285f89;
    border-color: #285f89;
}

QPushButton[role="danger"] {
    color: #a82a2a;
    background: #fffafa;
    border-color: #e3b7b7;
}

QPushButton[role="danger"]:hover {
    color: white;
    background: #ba3d3d;
    border-color: #ba3d3d;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QDateEdit {
    min-height: 32px;
    padding: 0 8px;
    border: 1px solid #cbd5df;
    border-radius: 5px;
    background: white;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus {
    border-color: #5f95bd;
}

QPlainTextEdit,
QTextEdit {
    padding: 7px 8px;
    border: 1px solid #cbd5df;
    border-radius: 5px;
    background: white;
}

QGroupBox {
    margin-top: 12px;
    padding-top: 12px;
    border: 1px solid #dfe5eb;
    border-radius: 7px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #36566f;
}

QTableWidget,
QTableView,
QTreeWidget,
QListWidget {
    background: white;
    alternate-background-color: #f8fafc;
    border: 1px solid #dfe5eb;
    border-radius: 6px;
    gridline-color: #e7ebef;
}

QTableWidget::item,
QTableView::item,
QTreeWidget::item,
QListWidget::item {
    min-height: 28px;
    padding: 4px 6px;
}

QTableWidget::item:selected,
QTableView::item:selected,
QTreeWidget::item:selected,
QListWidget::item:selected {
    background: #dcecf7;
    color: #173b57;
}

QHeaderView::section {
    min-height: 30px;
    padding: 5px 8px;
    background: #edf3f7;
    color: #314c60;
    border: none;
    border-right: 1px solid #dfe5eb;
    border-bottom: 1px solid #d7dee5;
    font-weight: 700;
}

QTabWidget::pane {
    border: 1px solid #dfe5eb;
    border-radius: 7px;
    background: white;
    top: -1px;
}

QTabBar::tab {
    min-width: 110px;
    min-height: 34px;
    padding: 0 14px;
    margin-right: 3px;
    border: 1px solid #dfe5eb;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    background: #edf2f6;
    color: #536776;
}

QTabBar::tab:selected {
    background: white;
    color: #1f4e79;
    font-weight: 700;
}

QScrollBar:vertical {
    width: 11px;
    margin: 0;
    background: #f2f4f6;
}

QScrollBar::handle:vertical {
    min-height: 30px;
    border-radius: 5px;
    background: #b8c4ce;
}

QScrollBar:horizontal {
    height: 11px;
    margin: 0;
    background: #f2f4f6;
}

QScrollBar::handle:horizontal {
    min-width: 30px;
    border-radius: 5px;
    background: #b8c4ce;
}

QProgressBar {
    min-height: 18px;
    border: 1px solid #d4dce3;
    border-radius: 6px;
    background: #eef2f5;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 5px;
    background: #4f86ad;
}
"""

# 二级导航补充样式。独立追加，避免依赖 APP_QSS 的具体引号写法。
APP_QSS += '\nQPushButton#navGroupButton {\n    min-height: 40px;\n    padding: 0 12px;\n    border: none;\n    border-radius: 7px;\n    background: transparent;\n    color: #e8eef3;\n    text-align: left;\n    font-size: 15px;\n    font-weight: 600;\n}\n\nQPushButton#navGroupButton:hover {\n    background: #2d475f;\n    color: white;\n}\n\nQPushButton#navGroupButton:checked {\n    background: #263f54;\n    color: white;\n}\n\nQWidget#navChildContainer {\n    background: transparent;\n}\n\nQPushButton#navButton[navLevel="child"] {\n    min-height: 36px;\n    padding-left: 20px;\n    font-size: 14px;\n}\n'

# Shared engineering survey/list UI refinement.
# Kept separate from APP_QSS core so this stage remains easy to audit.
SHARED_ENGINEERING_UI_QSS = r"""
#sectionPageTitle {
    font-size: 21px;
    font-weight: 700;
    padding: 2px 0 0 0;
}

#pageDescription {
    font-size: 14px;
    padding: 0 0 4px 0;
}

#summaryLabel {
    font-size: 14px;
    font-weight: 600;
    padding: 2px 0 2px 0;
}

#statusHint,
#shortcutHint {
    font-size: 13px;
}

QPushButton[uiRole="primary"] {
    min-height: 34px;
    padding: 5px 16px;
    font-weight: 600;
}

QPushButton[uiRole="secondary"] {
    min-height: 34px;
    padding: 5px 14px;
}

QPushButton[uiRole="danger"] {
    min-height: 34px;
    padding: 5px 14px;
    font-weight: 600;
}

#dataTable {
    padding: 0;
}
"""

APP_QSS += SHARED_ENGINEERING_UI_QSS

# NATIVE_COMBO_ARROW: use Qt/Windows native down-chevron instead of a CSS triangle.
# Visual polish pass 1:
# compact survey entry + cleaner combo-box affordance.
VISUAL_POLISH_PASS_QSS = r"""
QComboBox {
    min-height: 34px;
    padding: 4px 10px;
}

#surveyEntrySectionTitle {
    font-size: 19px;
    font-weight: 700;
    padding: 0 0 2px 0;
}

#surveyEntryLead {
    font-size: 14px;
    color: #5f6f82;
    padding: 0 0 6px 0;
}

#surveyEntryHintTitle {
    font-size: 14px;
    font-weight: 700;
    padding: 8px 0 2px 0;
}

#surveyEntryHintText {
    font-size: 13px;
    color: #5f6f82;
    padding: 0 0 4px 0;
}

QPushButton#surveyEntryPrimary,
QPushButton#surveyEntrySecondary {
    min-height: 42px;
    padding: 7px 14px;
    text-align: center;
}

QPushButton#surveyEntryPrimary {
    font-weight: 700;
}

QPushButton#surveyEntrySecondary {
    font-weight: 500;
}
"""

APP_QSS += VISUAL_POLISH_PASS_QSS

# Filter/statistics layout refinement shared by engineering list/query pages.
FILTER_STATISTICS_POLISH_QSS = r"""
#filterCard {
    background: #f8fafc;
    border: 1px solid #d9e3ec;
    border-radius: 8px;
}

#filterTitle {
    font-size: 14px;
    font-weight: 700;
    color: #263b4f;
    padding: 0 0 2px 0;
}

#filterRowLabel {
    font-size: 13px;
    font-weight: 700;
    color: #5a6a7a;
}

#filterCard QLabel {
    color: #405266;
}

#filterCard QLineEdit,
#filterCard QComboBox {
    min-height: 34px;
}

#filterCard QPushButton {
    min-height: 34px;
}

#summaryLabel {
    background: #eef5fb;
    border: 1px solid #d6e5f1;
    border-left: 4px solid #4a82ad;
    border-radius: 7px;
    padding: 9px 12px;
    font-size: 14px;
    font-weight: 600;
    color: #29465f;
}

QComboBox QAbstractItemView {
    padding: 4px;
}
"""

APP_QSS += FILTER_STATISTICS_POLISH_QSS

# Central control-width contract.
# Filters use one compact width; ordinary form inputs use one standard width.
CONTROL_WIDTH_SYSTEM_QSS = r"""
QLineEdit[uiWidthRole="filter"],
QComboBox[uiWidthRole="filter"] {
    min-width: 200px;
    max-width: 200px;
}

QLineEdit[uiWidthRole="form"],
QComboBox[uiWidthRole="form"] {
    min-width: 280px;
    max-width: 280px;
}
"""

APP_QSS += CONTROL_WIDTH_SYSTEM_QSS

# Shared visual language for task/result workflows.
WORKFLOW_UI_POLISH_QSS = r"""
QGroupBox[workflowCard="true"] {
    background: #fbfcfd;
    border: 1px solid #dce4eb;
    border-radius: 8px;
    margin-top: 10px;
    padding: 14px 12px 12px 12px;
}

QGroupBox[workflowCard="true"]::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #2d4256;
    font-weight: 700;
    font-size: 16px;
    background: #ffffff;
}

QLabel#workflowLead {
    color: #5d6f81;
    font-size: 14px;
    padding: 0 0 4px 0;
}

QLabel#workflowSummary {
    background: #f7f9fb;
    border: 1px solid #e0e7ee;
    border-radius: 6px;
    padding: 8px 10px;
    color: #405467;
}

QLabel#workflowStatus {
    background: #eef5fb;
    border: 1px solid #d7e6f2;
    border-left: 4px solid #4b82ad;
    border-radius: 6px;
    padding: 8px 10px;
    color: #29465f;
    font-weight: 600;
}

QPlainTextEdit#workflowDetails {
    background: #fbfcfd;
    border: 1px solid #dce4eb;
    border-radius: 6px;
    padding: 8px;
}
"""

APP_QSS += WORKFLOW_UI_POLISH_QSS

