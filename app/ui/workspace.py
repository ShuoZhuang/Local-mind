from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class WorkspaceShell(QWidget):
    """Stable three-column shell shared by chat and knowledge management."""

    context_visibility_changed = Signal(bool)

    def __init__(self, sidebar: QWidget, main: QWidget, context: QWidget, parent=None):
        super().__init__(parent)
        self.context_is_visible = True
        self._auto_collapsed = False
        self._expanded_context_width = 360
        self.context_container = QFrame()
        self.context_container.setObjectName("ContextRail")
        self.context_container.setMinimumWidth(320)
        self.context_container.setMaximumWidth(360)
        self.context_container.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        self._width_animation = QPropertyAnimation(self.context_container, b"maximumWidth")
        self._width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._width_animation.setDuration(180)
        self._width_animation.finished.connect(self.context_container.hide)

        context_layout = QVBoxLayout(self.context_container)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(12, 10, 12, 8)
        header.addStretch(1)
        self.context_toggle = QPushButton("收起")
        self.context_toggle.setObjectName("QuietButton")
        self.context_toggle.clicked.connect(lambda: self.set_context_visible(not self.context_is_visible))
        self.context_toggle.hide()
        header.addWidget(self.context_toggle)
        context_layout.addLayout(header)
        context_layout.addWidget(context, 1)

        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(sidebar)
        self.splitter.addWidget(main)
        self.splitter.addWidget(self.context_container)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([260, 720, self._expanded_context_width])

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.splitter, 0, 0, 1, 2)

        self.context_expand_button = QPushButton("›")
        self.context_expand_button.setObjectName("ContextEdgeButton")
        self.context_expand_button.setToolTip("收起回答依据")
        self.context_expand_button.setFixedSize(30, 74)
        self.context_expand_button.clicked.connect(self._toggle_context)
        layout.addWidget(
            self.context_expand_button,
            0,
            1,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )

    def set_context_page(self, page: QWidget) -> None:
        layout = self.context_container.layout()
        old = layout.itemAt(1).widget()
        if old is page:
            return
        if old is not None:
            layout.removeWidget(old)
            old.setParent(None)
        layout.addWidget(page, 1)

    def set_context_visible(self, visible: bool, animate: bool = True) -> None:
        if visible == self.context_is_visible:
            return
        self.context_is_visible = visible
        self.context_toggle.setText("收起" if visible else "展开")
        self.context_expand_button.setText("›" if visible else "‹")
        self.context_expand_button.setToolTip("收起回答依据" if visible else "展开回答依据")
        if visible:
            self._width_animation.stop()
            self.context_container.show()
            self.context_container.setMinimumWidth(320)
            self.context_container.setMaximumWidth(self._expanded_context_width)
            self.layout().activate()
            self._apply_splitter_sizes()
        else:
            self._expanded_context_width = max(320, min(360, self.context_container.width() or 340))
            self.context_container.setMinimumWidth(0)
            if animate:
                self._width_animation.stop()
                self._width_animation.setStartValue(self._expanded_context_width)
                self._width_animation.setEndValue(0)
                self._width_animation.start()
            else:
                self.context_container.hide()
            self.context_expand_button.show()
            self.layout().activate()
            self.splitter.setSizes([260, max(1, self.splitter.width() - 260), 0])
        self.context_visibility_changed.emit(visible)

    def _toggle_context(self) -> None:
        self.set_context_visible(not self.context_is_visible)

    def _apply_splitter_sizes(self) -> None:
        available = self.splitter.width()
        if available <= 0:
            return
        context_width = max(320, min(360, self._expanded_context_width))
        sidebar_width = min(280, max(240, int(available * 0.22)))
        main_width = max(1, available - sidebar_width - context_width)
        self.splitter.setSizes([sidebar_width, main_width, context_width])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        narrow = event.size().width() < 980
        if narrow and self.context_is_visible:
            self._auto_collapsed = True
            self.set_context_visible(False, animate=False)
        elif not narrow and self._auto_collapsed:
            self._auto_collapsed = False
            self.set_context_visible(True, animate=False)
        elif self.context_is_visible:
            self._apply_splitter_sizes()
