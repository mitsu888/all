"""Tests for the pure-Python helpers in ``subtitle_agent``.

These tests intentionally exercise only logic that has no heavy external
dependencies (no Whisper, no ffmpeg, no network). They can run in any
Python 3.9+ environment with just the standard library.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# Make the module importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subtitle_agent  # noqa: E402
from subtitle_agent import (  # noqa: E402
    Segment,
    SubtitleAgentError,
    _escape_for_subtitles_filter,
    format_timestamp,
    segments_to_srt,
    write_srt,
)


class FormatTimestampTests(unittest.TestCase):
    def test_zero(self) -> None:
        self.assertEqual(format_timestamp(0), "00:00:00,000")

    def test_sub_second(self) -> None:
        self.assertEqual(format_timestamp(0.123), "00:00:00,123")

    def test_seconds_and_minutes(self) -> None:
        self.assertEqual(format_timestamp(65.5), "00:01:05,500")

    def test_hours(self) -> None:
        # 1h 2m 3.004s
        self.assertEqual(format_timestamp(3723.004), "01:02:03,004")

    def test_negative_clamped(self) -> None:
        self.assertEqual(format_timestamp(-1), "00:00:00,000")

    def test_none_treated_as_zero(self) -> None:
        self.assertEqual(format_timestamp(None), "00:00:00,000")  # type: ignore[arg-type]

    def test_rounding(self) -> None:
        # 0.9999 should round to 1000 ms, not 999.
        self.assertEqual(format_timestamp(0.9999), "00:00:01,000")


class SegmentsToSrtTests(unittest.TestCase):
    def test_basic_document(self) -> None:
        segments = [
            Segment(start=0.0, end=1.5, text="こんにちは"),
            Segment(start=1.5, end=3.0, text="世界"),
        ]
        srt = segments_to_srt(segments)
        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:01,500\n"
            "こんにちは\n"
            "\n"
            "2\n"
            "00:00:01,500 --> 00:00:03,000\n"
            "世界\n"
        )
        self.assertEqual(srt, expected)

    def test_empty_text_segments_are_skipped(self) -> None:
        segments = [
            Segment(start=0.0, end=1.0, text="hi"),
            Segment(start=1.0, end=2.0, text="   "),  # blank -> skipped
            Segment(start=2.0, end=3.0, text="there"),
        ]
        srt = segments_to_srt(segments)
        # Two cues, numbered 1 and 2 (not 1 and 3).
        self.assertIn("1\n00:00:00,000 --> 00:00:01,000\nhi\n", srt)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,000\nthere\n", srt)
        self.assertNotIn("   ", srt.strip())

    def test_end_before_start_is_clamped(self) -> None:
        # We should not emit an end < start (would be a malformed SRT).
        segments = [Segment(start=5.0, end=3.0, text="oops")]
        srt = segments_to_srt(segments)
        self.assertIn("00:00:05,000 --> 00:00:05,000", srt)

    def test_empty_input(self) -> None:
        self.assertEqual(segments_to_srt([]), "\n")


class WriteSrtTests(unittest.TestCase):
    def test_writes_utf8(self) -> None:
        import tempfile

        segments = [Segment(start=0.0, end=1.0, text="日本語テスト")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sub" / "test.ja.srt"
            write_srt(segments, out)
            self.assertTrue(out.exists())
            content = out.read_text(encoding="utf-8")
            self.assertIn("日本語テスト", content)


class EscapeSubtitlesFilterTests(unittest.TestCase):
    def test_escapes_colon(self) -> None:
        result = _escape_for_subtitles_filter(Path("C:/videos/movie.srt"))
        self.assertIn("\\:", result)

    def test_escapes_backslash_before_colon(self) -> None:
        # A raw Windows-style path.
        result = _escape_for_subtitles_filter(Path("C:\\videos\\movie.srt"))
        # Backslashes must be doubled, and colons escaped.
        self.assertIn("\\\\", result)
        self.assertIn("\\:", result)

    def test_escapes_single_quote(self) -> None:
        result = _escape_for_subtitles_filter(Path("/tmp/it's.srt"))
        self.assertIn("\\'", result)


class GenerateJapaneseSubtitlesArgumentTests(unittest.TestCase):
    """Argument-validation paths that don't require Whisper / ffmpeg."""

    def test_missing_input_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            subtitle_agent.generate_japanese_subtitles(
                input_video="/nonexistent/does_not_exist.mp4",
            )

    def test_invalid_mode_raises(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"not a real video")
            fake = f.name
        try:
            with self.assertRaises(ValueError):
                subtitle_agent.generate_japanese_subtitles(
                    input_video=fake, mode="invalid"
                )
        finally:
            os.unlink(fake)

    def test_output_same_as_input_raises(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"not a real video")
            fake = f.name
        try:
            with self.assertRaises(ValueError):
                subtitle_agent.generate_japanese_subtitles(
                    input_video=fake,
                    output_video=fake,
                )
        finally:
            os.unlink(fake)


class MissingDependencyTests(unittest.TestCase):
    def test_extract_audio_without_ffmpeg(self) -> None:
        with mock.patch("subtitle_agent.shutil.which", return_value=None):
            with self.assertRaises(subtitle_agent.DependencyMissingError):
                subtitle_agent.extract_audio(Path("in.mp4"), Path("out.wav"))


class TranslatorFactoryTests(unittest.TestCase):
    def test_unknown_backend(self) -> None:
        with self.assertRaises(ValueError):
            subtitle_agent._make_translator("does-not-exist")

    def test_auto_falls_back_to_google_when_argos_missing(self) -> None:
        """If argos isn't installed, ``auto`` should try google."""
        called = {}

        class FakeGoogle:
            def __init__(self, source: str = "en", target: str = "ja") -> None:
                called["init"] = (source, target)

            def translate(self, text: str) -> str:
                return f"[ja]{text}"

        def raise_missing(*_a, **_kw):
            raise subtitle_agent.DependencyMissingError("no argos")

        with mock.patch.object(
            subtitle_agent, "_ArgosTranslator", side_effect=raise_missing
        ), mock.patch.object(
            subtitle_agent, "_DeepTranslator", FakeGoogle
        ):
            translator = subtitle_agent._make_translator("auto")
            self.assertEqual(translator.translate("hi"), "[ja]hi")
            self.assertEqual(called["init"], ("en", "ja"))


class TranslateSegmentsTests(unittest.TestCase):
    def test_uses_original_when_translation_empty(self) -> None:
        segments = [
            Segment(start=0, end=1, text="hello"),
            Segment(start=1, end=2, text="world"),
        ]

        class FakeTranslator:
            def translate(self, text: str) -> str:
                return "" if text == "hello" else "セカイ"

        with mock.patch.object(
            subtitle_agent, "_make_translator", return_value=FakeTranslator()
        ):
            out = subtitle_agent.translate_segments(segments)

        self.assertEqual(out[0].text, "hello")  # fallback to original
        self.assertEqual(out[1].text, "セカイ")

    def test_translation_exception_falls_back(self) -> None:
        segments = [Segment(start=0, end=1, text="boom")]

        class ExplodingTranslator:
            def translate(self, text: str) -> str:
                raise RuntimeError("network down")

        with mock.patch.object(
            subtitle_agent, "_make_translator", return_value=ExplodingTranslator()
        ):
            out = subtitle_agent.translate_segments(segments)

        # We should still get a segment out, with the original text preserved.
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, "boom")


class CliTests(unittest.TestCase):
    """Smoke tests for the argparse layer in ``video_ja_subtitle``."""

    def test_help_runs(self) -> None:
        # We import here to avoid touching the module during collection if
        # any import at module scope failed elsewhere.
        import video_ja_subtitle

        parser = video_ja_subtitle._build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_missing_argument(self) -> None:
        import video_ja_subtitle

        parser = video_ja_subtitle._build_parser()
        # No positional argument -> argparse exits with code 2.
        with self.assertRaises(SystemExit), mock.patch(
            "sys.stderr", new_callable=io.StringIO
        ):
            parser.parse_args([])

    def test_defaults(self) -> None:
        import video_ja_subtitle

        parser = video_ja_subtitle._build_parser()
        args = parser.parse_args(["input.mp4"])
        self.assertEqual(str(args.input), "input.mp4")
        self.assertEqual(args.model, "small")
        self.assertEqual(args.mode, "burn")
        self.assertEqual(args.translator, "auto")
        self.assertEqual(args.source_language, "en")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
