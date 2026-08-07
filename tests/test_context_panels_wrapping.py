import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.context_panels import CitationPanel


def test_citation_panel_wraps_long_sources_without_horizontal_scroll():
    application = QApplication.instance() or QApplication([])
    panel = CitationPanel()
    panel.resize(360, 600)
    panel.set_citations(
        [
            {
                "file_name": "source_" + "x" * 120 + ".pdf",
                "score": 0.81,
                "text": "snippet_" + "y" * 240,
            }
        ]
    )
    panel.show()
    application.processEvents()

    item = panel.source_list.item(0)
    item_rect = panel.source_list.visualItemRect(item)

    assert panel.source_list.horizontalScrollBar().maximum() == 0
    assert item_rect.width() <= panel.source_list.viewport().width()
    assert item_rect.height() > 48

    panel.close()
    application.processEvents()
