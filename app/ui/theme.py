APP_STYLE = """
QMainWindow, QWidget {
    background: #10151d;
    color: #eaf1f7;
    font-family: 'Microsoft YaHei UI', 'Microsoft YaHei';
    font-size: 13px;
}
QLabel { background: transparent; }
QPushButton {
    min-height: 34px;
    border: 1px solid #273447;
    border-radius: 10px;
    padding: 6px 12px;
    color: #c9d4e0;
    background: #161d27;
}
QPushButton:hover { border-color: #87dfc3; color: #edfdf7; background: #1c2531; }
QPushButton:pressed { padding-top: 7px; padding-bottom: 5px; }
QPushButton:disabled { color: #66758a; border-color: #202b3a; background: #141a23; }
QPushButton#PrimaryButton { background: #87dfc3; color: #10221e; border: 1px solid #87dfc3; font-weight: 700; }
QPushButton#PrimaryButton:hover { background: #9ce8cf; border-color: #9ce8cf; }
QPushButton#QuietButton { min-height: 26px; padding: 3px 9px; border-color: transparent; background: transparent; color: #91a0b5; }
QPushButton#QuietButton:hover { color: #eaf1f7; background: #1c2531; }
QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox {
    border: 1px solid #273447;
    border-radius: 10px;
    padding: 8px;
    color: #eaf1f7;
    selection-background-color: #285549;
    background: #161d27;
}
QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QSpinBox:hover { border-color: #3c4d64; }
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus { border-color: #87dfc3; }
QListWidget { border: 0; outline: 0; background: transparent; }
QListWidget::item { margin: 2px 0; padding: 9px 10px; border-radius: 10px; color: #aebccd; }
QListWidget::item:hover { background: #1c2531; color: #eaf1f7; }
QListWidget::item:selected { color: #e6fff6; background: #1d3b33; }
QListWidget#ChatMessages, QListWidget#DocumentList { background: transparent; }
QListWidget#ChatMessages::item, QListWidget#DocumentList::item { background: transparent; border: 0; padding: 0; margin: 4px 0; }
QListWidget#ChatMessages::item:hover, QListWidget#ChatMessages::item:selected,
QListWidget#DocumentList::item:hover, QListWidget#DocumentList::item:selected { background: transparent; }
QWidget#MessageRow { background: transparent; }
QLabel#Muted { color: #91a0b5; }
QLabel#Title { color: #f1f6fb; font-size: 20px; font-weight: 700; }
QFrame#Sidebar { background: #111720; border-right: 1px solid #273447; }
QFrame#ContextRail { background: #141b25; border-left: 1px solid #273447; }
QFrame#Card { border: 1px solid #273447; border-radius: 12px; background: #161d27; }
QFrame#UserBubble { border: 1px solid #5aa88e; border-radius: 12px; background: #21483d; margin: 0; }
QFrame#AssistantBubble { border: 1px solid #4b6684; border-radius: 12px; background: #1d2938; margin: 0; }
QFrame#UserBubble:hover { border-color: #87dfc3; background: #285447; }
QFrame#AssistantBubble:hover { border-color: #6f8eaf; background: #223247; }
QWidget#CitationLink { background: transparent; }
QLabel#CitationLabel { color: #8fb9c7; padding: 8px 12px; }
QWidget#CitationLink:hover QLabel#CitationLabel { color: #b9f3e0; }
QLabel#ToolCallLabel { color: #8fb6aa; padding: 9px 10px 9px 18px; border: 0; border-left: 2px solid #4c8f7f; background: transparent; }
QWidget#CitationCard { border: 1px solid #273447; border-radius: 10px; background: #161d27; }
QWidget#CitationCard[selected="true"] { border-color: #87dfc3; background: #1a302c; }
QLabel#CitationTitle { color: #dbe7f4; font-weight: 700; }
QLabel#CitationPreview { color: #aebccd; }
QWidget#DocumentListCard { border: 1px solid #273447; border-radius: 10px; background: #161d27; }
QMenu { border: 1px solid #334258; border-radius: 10px; padding: 5px; background: #1c2531; color: #eaf1f7; }
QMenu::item { padding: 7px 24px 7px 10px; border-radius: 6px; }
QMenu::item:selected { background: #285549; }
QPushButton#ChatOptionsButton { min-width: 34px; max-width: 34px; min-height: 30px; max-height: 30px; padding: 0; border-color: transparent; background: transparent; color: #91a0b5; font-size: 20px; }
QPushButton#ChatOptionsButton:hover { color: #eaf1f7; background: #1c2531; border-color: #334258; }
QScrollBar:vertical { width: 12px; background: #111a24; border-left: 1px solid #2d3b4f; margin: 0; }
QScrollBar::handle:vertical { min-height: 40px; border-radius: 5px; background: #647b96; }
QScrollBar::handle:vertical:hover { background: #87dfc3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
