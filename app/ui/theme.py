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
QPushButton#SidebarNav { text-align: left; min-height: 34px; border-color: transparent; background: transparent; color: #aebccd; }
QPushButton#SidebarNav:hover { border-color: #334c5d; background: #182633; color: #eaf1f7; }
QPushButton#SidebarNav[active="true"] { border-color: #376a69; background: #193b3b; color: #dffff5; }
QPushButton#SidebarCreateAction { min-height: 30px; padding: 5px 6px; font-size: 12px; color: #c9d9e5; background: #172231; border-color: #2c4055; }
QPushButton#SidebarCreateAction:hover { color: #eafff8; background: #1f3b42; border-color: #73d9c1; }
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
QFrame#ToolCenterPage { background: #101822; }
QScrollArea#ToolCardsScrollArea, QWidget#ToolCardsContent { background: #101822; border: none; }
QScrollArea#ToolDetailsScrollArea, QWidget#ToolDetailsContent { background: #121d2a; border: none; }
QFrame#SkillsCenterPage { background: #101822; }
QFrame#SkillsEmptyCard { border: 1px solid #2b3d50; border-radius: 16px; background: #172333; }
QLabel#SkillsEmptyTitle { color: #eff9ff; font-size: 22px; font-weight: 700; }
QLabel#SkillsEmptyDetail { color: #a9bacb; line-height: 1.45; }
QFrame#SkillsOverviewPanel { background: #121d2a; border: 1px solid #2b3d50; border-radius: 14px; }
QFrame#ToolCard { border: 1px solid #2b3d50; border-radius: 14px; background: #172333; }
QFrame#ToolCard:hover { border-color: #537b8e; background: #1a2b3a; }
QFrame#ToolCard[selected="true"] { border: 2px solid #73d9c1; background: #183542; }
QLabel#ToolIcon { color: #9fd2e4; border: 1px solid #3b6a80; border-radius: 22px; background: #172c3e; font-size: 22px; }
QLabel#ToolCardTitle { color: #eff9ff; font-size: 16px; font-weight: 700; }
QLabel#ToolCardDescription { color: #a9bacb; line-height: 1.35; }
QLabel#ToolEnabledStatus { color: #67e39a; font-weight: 700; }
QLabel#ToolDisabledStatus { color: #8898a9; }
QLabel#ToolCapabilityStatus { color: #8fb9c7; }
QPushButton#ToolFilterButton { min-height: 28px; padding: 4px 13px; border-radius: 14px; color: #9cacbd; background: #172333; }
QPushButton#ToolFilterButton:checked { color: #eafff8; border-color: #73d9c1; background: #1b4b49; }
QFrame#ToolDetailsPanel { background: #121d2a; border: 1px solid #2b3d50; border-radius: 14px; }
QLabel#ToolDetailsTitle { color: #f1f7fb; font-size: 21px; font-weight: 700; }
QLabel#ToolDetailsStatus { color: #67e39a; font-weight: 700; }
QLabel#ToolDetailsDescription { color: #b6c4d2; line-height: 1.45; }
QLabel#ToolCapabilities { color: #c9e7df; padding: 8px 10px; border: 1px solid #2d5b5c; border-radius: 9px; background: #152e35; }
QLabel#ToolExample { color: #c9f4e6; padding: 10px; border: 1px solid #2b4d5f; border-radius: 9px; background: #142331; font-family: 'Cascadia Mono', 'Consolas'; }
QLabel#ToolSectionTitle { color: #eff7fb; font-size: 14px; font-weight: 700; }
QLabel#ToolRecentCalls { color: #aebdca; padding: 10px; border: 1px solid #273a4c; border-radius: 9px; background: #14202d; }
QLabel#ToolTestResult { color: #87dfc3; padding: 9px 10px; border: 1px solid #2d5b5c; border-radius: 9px; background: #152e35; }
QLabel#ToolTestResult[success="false"] { color: #ffadad; border-color: #754c55; background: #321e27; }
QLabel#ContextTitle { color: #f1f6fb; font-size: 19px; font-weight: 700; }
QScrollBar:horizontal { height: 0; }
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
QPushButton#ContextEdgeButton { min-width: 30px; max-width: 30px; min-height: 74px; max-height: 74px; padding: 0; border: 1px solid #33485b; border-right: 0; border-radius: 10px 0 0 10px; background: #172332; color: #a8c4d2; font-size: 24px; }
QPushButton#ContextEdgeButton:hover { background: #1e3842; border-color: #73d9c1; color: #dffff5; }
QScrollBar:vertical { width: 12px; background: #111a24; border-left: 1px solid #2d3b4f; margin: 0; }
QScrollBar::handle:vertical { min-height: 40px; border-radius: 5px; background: #647b96; }
QScrollBar::handle:vertical:hover { background: #87dfc3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
