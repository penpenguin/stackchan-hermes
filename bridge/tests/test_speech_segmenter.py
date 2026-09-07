from __future__ import annotations

from stackchan_bridge.hermes.segmenter import SpeechSegmenter, SpeechSegmenterConfig


def test_segmenter_emits_complete_japanese_sentences_without_character_streaming() -> None:
    segmenter = SpeechSegmenter(
        SpeechSegmenterConfig(
            max_segments=2,
            segment_max_characters=80,
            response_max_characters=160,
        )
    )

    assert segmenter.feed("今日は") == []
    assert segmenter.feed("いい天気です") == []
    assert segmenter.feed("。次も") == ["今日はいい天気です。"]
    assert segmenter.feed("話します\uff01三つ目") == ["次も話します\uff01"]
    assert segmenter.feed("は発話しません。") == []
    assert segmenter.finish() == []


def test_segmenter_splits_a_sentence_at_the_per_segment_character_limit() -> None:
    segmenter = SpeechSegmenter(
        SpeechSegmenterConfig(
            max_segments=2,
            segment_max_characters=10,
            response_max_characters=20,
        )
    )

    first = segmenter.feed("12345 78901 34567。")
    remaining = segmenter.finish()

    assert first == ["12345", "78901"]
    assert remaining == []
    assert all(len(segment) <= 10 for segment in first + remaining)


def test_segmenter_normalizes_markdown_urls_and_emoji_for_speech() -> None:
    segmenter = SpeechSegmenter(
        SpeechSegmenterConfig(
            max_segments=2,
            segment_max_characters=80,
            response_max_characters=160,
        )
    )

    segments = segmenter.feed(
        "# **重要**です。詳しくは [資料](https://example.com/doc) を見てください 😊。"
    )

    assert segments == ["重要です。", "詳しくは 資料 を見てください。"]
    assert "http" not in "".join(segments)
    assert "*" not in "".join(segments)
