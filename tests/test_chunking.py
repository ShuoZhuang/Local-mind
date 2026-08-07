from app.models import ChunkingConfig
from app.services.chunking import ExtractedSection, build_chunker
from app.services.documents import extract_sections_from_text


def test_custom_chunker_uses_custom_delimiter():
    config = ChunkingConfig(strategy_id="custom", delimiter="###", max_length=800)

    result = build_chunker(config).split([ExtractedSection(None, "A###B")])

    assert [piece.text for piece in result.pieces] == ["A", "B"]


def test_hierarchical_markdown_preserves_heading_path():
    sections = extract_sections_from_text("# 第一章\n正文\n## 1.1 概念\n细节", suffix=".md")

    result = build_chunker(ChunkingConfig(strategy_id="hierarchical")).split(sections)

    assert result.pieces[-1].heading_path == ("第一章", "1.1 概念")


def test_hierarchical_chunker_falls_back_when_no_heading_exists():
    result = build_chunker(ChunkingConfig(strategy_id="hierarchical")).split(
        [ExtractedSection(None, "只有普通文本。")]
    )

    assert result.fallback_message == "未识别到明确层级，已使用自动分段。"
