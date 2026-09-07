"""Bounded streaming text segmentation for Japanese speech."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BOUNDARIES = frozenset({"。", "\uff01", "\uff1f", "!", "?", "\n"})
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(https?://[^\s)]+\)")
_RAW_URL = re.compile(r"https?://\S+")
_FENCED_CODE = re.compile(r"```.*?```", flags=re.DOTALL)
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_MARKDOWN_MARKS = re.compile(r"[#>*_~`|]+")


@dataclass(frozen=True, slots=True)
class SpeechSegmenterConfig:
    max_segments: int = 2
    segment_max_characters: int = 80
    response_max_characters: int = 160

    def __post_init__(self) -> None:
        if self.max_segments <= 0:
            raise ValueError("maximum speech segments must be positive")
        if self.segment_max_characters <= 0:
            raise ValueError("segment character limit must be positive")
        if self.response_max_characters < self.segment_max_characters:
            raise ValueError("response limit must cover one segment")


class SpeechSegmenter:
    """Collect deltas until a sentence or configured length boundary is ready."""

    def __init__(self, config: SpeechSegmenterConfig) -> None:
        self.config = config
        self._buffer = ""
        self._emitted_segments = 0
        self._emitted_characters = 0

    def feed(self, delta: str) -> list[str]:
        if self._emitted_segments >= self.config.max_segments:
            return []
        remaining = self.config.response_max_characters - self._emitted_characters
        if remaining <= 0:
            return []
        maximum_buffer = min(remaining, self.config.segment_max_characters)
        self._buffer += delta
        output: list[str] = []
        while self._buffer and self._emitted_segments < self.config.max_segments:
            boundary = _first_boundary(self._buffer)
            if boundary is not None and boundary + 1 <= maximum_buffer:
                end = boundary + 1
            elif len(self._buffer) >= maximum_buffer:
                end = _length_split(self._buffer, maximum_buffer)
            else:
                break
            candidate = _normalize_for_speech(self._buffer[:end])
            self._buffer = self._buffer[end:].lstrip()
            if not candidate:
                continue
            candidate = candidate[:remaining]
            output.append(candidate)
            self._emitted_segments += 1
            self._emitted_characters += len(candidate)
            remaining = self.config.response_max_characters - self._emitted_characters
            if remaining <= 0:
                self._buffer = ""
                break
            maximum_buffer = min(remaining, self.config.segment_max_characters)
        if len(self._buffer) > self.config.response_max_characters:
            self._buffer = self._buffer[: self.config.response_max_characters]
        return output

    def finish(self) -> list[str]:
        if not self._buffer or self._emitted_segments >= self.config.max_segments:
            self._buffer = ""
            return []
        remaining = self.config.response_max_characters - self._emitted_characters
        candidate = _normalize_for_speech(self._buffer)[
            : min(remaining, self.config.segment_max_characters)
        ]
        self._buffer = ""
        if not candidate:
            return []
        self._emitted_segments += 1
        self._emitted_characters += len(candidate)
        return [candidate]


def _first_boundary(text: str) -> int | None:
    return next((index for index, character in enumerate(text) if character in _BOUNDARIES), None)


def _length_split(text: str, limit: int) -> int:
    whitespace = max(text.rfind(" ", 0, limit + 1), text.rfind("　", 0, limit + 1))
    return whitespace if whitespace > 0 else limit


def _normalize_for_speech(text: str) -> str:
    normalized = _FENCED_CODE.sub(" コード省略 ", text)
    normalized = _MARKDOWN_LINK.sub(r"\1", normalized)
    normalized = _RAW_URL.sub("リンク", normalized)
    normalized = _EMOJI.sub("", normalized)
    normalized = _MARKDOWN_MARKS.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return re.sub(r"\s+([。、\uff01\uff1f!?])", r"\1", normalized)
