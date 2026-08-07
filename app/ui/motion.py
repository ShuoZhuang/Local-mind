from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def reveal(widget: QWidget, duration: int = 180, delay: int = 0) -> None:
    """Reveal a new row without changing layout geometry.

    This is the Qt equivalent of a small GSAP opacity timeline: it keeps the
    row's width/height stable and only animates paint opacity, preventing the
    chat list from jumping while messages arrive.
    """
    if duration <= 0:
        widget.setVisible(True)
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    widget._localmind_reveal_animation = animation

    def start() -> None:
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    QTimer.singleShot(max(0, delay), start)
