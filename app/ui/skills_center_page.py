from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SkillsCenterPage(QFrame):
    """Skills workspace reserved for user-defined workflows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SkillsCenterPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(8)

        eyebrow = QLabel("工作流能力")
        eyebrow.setObjectName("Muted")
        layout.addWidget(eyebrow)

        title = QLabel("技能中心")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel("把重复的任务组织成可复用的工作流程。")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        layout.addSpacing(18)
        empty_card = QFrame()
        empty_card.setObjectName("SkillsEmptyCard")
        empty_layout = QVBoxLayout(empty_card)
        empty_layout.setContentsMargins(28, 28, 28, 28)
        empty_layout.setSpacing(9)

        self.empty_title = QLabel("尚未添加技能")
        self.empty_title.setObjectName("SkillsEmptyTitle")
        empty_layout.addWidget(self.empty_title)

        self.empty_detail = QLabel(
            "技能用于定义 AI 的工作流程；未来可结合工具和知识库执行复杂任务。"
        )
        self.empty_detail.setObjectName("SkillsEmptyDetail")
        self.empty_detail.setWordWrap(True)
        empty_layout.addWidget(self.empty_detail)
        empty_layout.addStretch(1)

        layout.addWidget(empty_card, 1)


class SkillsOverviewPanel(QFrame):
    """Right-side explanation panel for the empty skills center."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SkillsOverviewPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 18, 18)
        layout.setSpacing(10)

        title = QLabel("技能说明")
        title.setObjectName("ContextTitle")
        layout.addWidget(title)

        status = QLabel("○  尚未配置")
        status.setObjectName("Muted")
        layout.addWidget(status)

        detail = QLabel(
            "技能会把意图识别、知识库检索和工具调用组合成一条可复用流程。"
        )
        detail.setObjectName("SkillsEmptyDetail")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addStretch(1)
