"""動画日本語字幕変換エージェント / Video Japanese Subtitle Agent.

Core library for turning an English (or any-language) video into a video with
Japanese subtitles. The pipeline is:

    1. Extract audio from the input video with ffmpeg.
    2. Transcribe the audio to text with Whisper (word/segment timestamps).
    3. Translate each segment to Japanese.
       - Whisper's built-in ``translate`` task only produces English, so we
         run a separate translation step. By default we use the offline
         ``argos-translate`` package; if that is unavailable we fall back to
         the ``deep-translator`` (Google) HTTP backend.
    4. Write an SRT subtitle file.
    5. Optionally burn the subtitles into the video (hard subs) or mux them
       as a soft subtitle track using ffmpeg.

The module is designed to be usable both programmatically and from the
command line (see ``video_ja_subtitle.py``).
"""

from __future__ import annotations

import dataclasses
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

logger = logging.getLogger("subtitle_agent")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Segment:
    """A single subtitle segment with timing (seconds) and text."""

    start: float
    end: float
    text: str

    def with_text(self, new_text: str) -> "Segment":
        return dataclasses.replace(self, text=new_text)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SubtitleAgentError(RuntimeError):
    """Base error for the subtitle agent."""


class DependencyMissingError(SubtitleAgentError):
    """Raised when a required external dependency is missing."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_ffmpeg() -> str:
    """Return the path to ffmpeg or raise DependencyMissingError."""
    path = shutil.which("ffmpeg")
    if not path:
        raise DependencyMissingError(
            "ffmpeg が見つかりません。 / ffmpeg is not installed.\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt-get install -y ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )
    return path


def format_timestamp(seconds: float) -> str:
    """Format a duration in seconds as an SRT timestamp ``HH:MM:SS,mmm``.

    Negative values are clamped to zero to keep the SRT well-formed.
    """
    if seconds is None:
        seconds = 0.0
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments: Sequence[Segment]) -> str:
    """Render segments as an SRT document.

    Blank cues are skipped and the remaining cues are renumbered
    sequentially starting from 1.
    """
    lines: List[str] = []
    index = 0
    for seg in segments:
        text = (seg.text or "").strip()
        # SRT does not allow blank cues; skip empty ones defensively.
        if not text:
            continue
        index += 1
        start = format_timestamp(seg.start)
        end = format_timestamp(max(seg.end, seg.start))
        lines.append(str(index))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    """Extract mono 16 kHz WAV audio suitable for Whisper."""
    _check_ffmpeg()
    video_path = Path(video_path)
    audio_path = Path(audio_path)
    if not video_path.exists():
        raise FileNotFoundError(f"入力動画が見つかりません: {video_path}")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(audio_path),
    ]
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SubtitleAgentError(
            f"ffmpeg で音声抽出に失敗しました:\n{result.stderr.strip()}"
        )
    return audio_path


# ---------------------------------------------------------------------------
# Transcription (Whisper)
# ---------------------------------------------------------------------------


def transcribe(
    audio_path: Path,
    model_name: str = "small",
    source_language: Optional[str] = "en",
) -> List[Segment]:
    """Transcribe audio using OpenAI Whisper.

    Parameters
    ----------
    audio_path:
        Path to a WAV/MP3/etc. file supported by Whisper.
    model_name:
        One of ``tiny``, ``base``, ``small``, ``medium``, ``large``.
        Smaller models are faster but less accurate.
    source_language:
        Two-letter language code, or ``None`` to let Whisper auto-detect.
    """
    try:
        import whisper  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on runtime env
        raise DependencyMissingError(
            "openai-whisper がインストールされていません。\n"
            "  pip install -U openai-whisper\n"
            "(初回起動時にモデルが自動でダウンロードされます)"
        ) from exc

    logger.info("Whisper モデル '%s' を読み込み中...", model_name)
    model = whisper.load_model(model_name)
    logger.info("音声認識を実行中...")
    result = model.transcribe(
        str(audio_path),
        language=source_language,
        task="transcribe",
        verbose=False,
    )
    segments = [
        Segment(
            start=float(seg["start"]),
            end=float(seg["end"]),
            text=str(seg["text"]).strip(),
        )
        for seg in result.get("segments", [])
    ]
    logger.info("%d 個のセグメントを認識しました。", len(segments))
    return segments


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


class _Translator:
    """Small adapter so we can swap translation backends easily."""

    def translate(self, text: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError


class _ArgosTranslator(_Translator):
    """Offline translator using argos-translate.

    Model packages are downloaded lazily on first use.
    """

    def __init__(self, source: str = "en", target: str = "ja") -> None:
        try:
            import argostranslate.package as pkg  # type: ignore
            import argostranslate.translate as translate  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise DependencyMissingError(
                "argostranslate が見つかりません。\n"
                "  pip install argostranslate"
            ) from exc

        self._source = source
        self._target = target
        self._pkg = pkg
        self._translate = translate
        self._ensure_language_package()

    def _ensure_language_package(self) -> None:
        installed = {
            (lang.code, tlang.code)
            for lang in self._translate.get_installed_languages()
            for tlang in lang.translations_from + lang.translations_to
        }
        if any(
            src == self._source and dst == self._target for src, dst in installed
        ):
            return
        logger.info("argos-translate 言語パッケージをダウンロード中...")
        self._pkg.update_package_index()
        available = self._pkg.get_available_packages()
        candidate = next(
            (
                p
                for p in available
                if p.from_code == self._source and p.to_code == self._target
            ),
            None,
        )
        if candidate is None:
            raise SubtitleAgentError(
                f"argos-translate で {self._source}->{self._target} の"
                " パッケージが見つかりません。"
            )
        download_path = candidate.download()
        self._pkg.install_from_path(download_path)

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
        return self._translate.translate(text, self._source, self._target)


class _DeepTranslator(_Translator):
    """Fallback translator using deep-translator (Google backend)."""

    def __init__(self, source: str = "en", target: str = "ja") -> None:
        try:
            from deep_translator import GoogleTranslator  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise DependencyMissingError(
                "deep-translator が見つかりません。\n"
                "  pip install deep-translator"
            ) from exc

        self._impl = GoogleTranslator(source=source, target=target)

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
        return self._impl.translate(text)


def _make_translator(
    backend: str, source: str = "en", target: str = "ja"
) -> _Translator:
    backend = backend.lower()
    if backend == "argos":
        return _ArgosTranslator(source=source, target=target)
    if backend == "google":
        return _DeepTranslator(source=source, target=target)
    if backend == "auto":
        try:
            return _ArgosTranslator(source=source, target=target)
        except DependencyMissingError:
            logger.info("argos-translate が使えないため google に切替します。")
            return _DeepTranslator(source=source, target=target)
    raise ValueError(f"未知の翻訳バックエンド: {backend}")


def translate_segments(
    segments: Sequence[Segment],
    backend: str = "auto",
    source_language: str = "en",
    target_language: str = "ja",
) -> List[Segment]:
    """Translate the text of each segment.

    Empty translations fall back to the original English text so a subtitle
    is always shown for that time window.
    """
    translator = _make_translator(backend, source_language, target_language)
    translated: List[Segment] = []
    for i, seg in enumerate(segments, start=1):
        try:
            ja = translator.translate(seg.text).strip()
        except Exception as exc:  # noqa: BLE001 - want to keep going
            logger.warning("翻訳失敗 (segment %d): %s", i, exc)
            ja = ""
        if not ja:
            ja = seg.text
        translated.append(seg.with_text(ja))
        if i % 25 == 0:
            logger.info("翻訳進捗: %d / %d", i, len(segments))
    return translated


# ---------------------------------------------------------------------------
# Subtitle rendering
# ---------------------------------------------------------------------------


def write_srt(segments: Sequence[Segment], srt_path: Path) -> Path:
    srt_path = Path(srt_path)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(segments_to_srt(segments), encoding="utf-8")
    return srt_path


def _escape_for_subtitles_filter(path: Path) -> str:
    """Escape a path for use inside ffmpeg's ``subtitles=`` filter argument.

    The subtitles filter parses its argument with ffmpeg's option parser, so
    ``:``, ``\\`` and ``'`` are special. This is important on Windows where
    ``C:\\...`` would otherwise be misread.
    """
    text = str(path)
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    return text


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    font_name: str = "Noto Sans CJK JP",
    font_size: int = 24,
) -> Path:
    """Burn (hard-code) the subtitles into the video."""
    _check_ffmpeg()
    video_path = Path(video_path)
    srt_path = Path(srt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    style = (
        f"FontName={font_name},FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
        "BorderStyle=3,Outline=1,Shadow=0,MarginV=30"
    )
    subtitles_arg = (
        f"subtitles='{_escape_for_subtitles_filter(srt_path)}'"
        f":force_style='{style}'"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        subtitles_arg,
        "-c:a",
        "copy",
        str(output_path),
    ]
    logger.info("字幕を動画に焼き込み中...")
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SubtitleAgentError(
            f"ffmpeg で字幕焼き込みに失敗しました:\n{result.stderr.strip()}"
        )
    return output_path


def mux_soft_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    language_tag: str = "jpn",
) -> Path:
    """Add subtitles as a selectable track (soft subs). Preserves quality."""
    _check_ffmpeg()
    video_path = Path(video_path)
    srt_path = Path(srt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # For .mp4 output we need mov_text; for .mkv we can use srt directly.
    suffix = output_path.suffix.lower()
    sub_codec = "mov_text" if suffix in {".mp4", ".m4v", ".mov"} else "srt"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(srt_path),
        "-map",
        "0",
        "-map",
        "1",
        "-c",
        "copy",
        "-c:s",
        sub_codec,
        "-metadata:s:s:0",
        f"language={language_tag}",
        str(output_path),
    ]
    logger.info("字幕を動画に埋め込み中 (soft-subs)...")
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SubtitleAgentError(
            f"ffmpeg で字幕埋め込みに失敗しました:\n{result.stderr.strip()}"
        )
    return output_path


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SubtitleResult:
    """Return value of :func:`generate_japanese_subtitles`."""

    srt_path: Path
    video_path: Optional[Path]  # None if the user only wanted an SRT


def generate_japanese_subtitles(
    input_video: Path,
    output_video: Optional[Path] = None,
    srt_output: Optional[Path] = None,
    model: str = "small",
    source_language: Optional[str] = "en",
    translator_backend: str = "auto",
    mode: str = "burn",
    keep_intermediate: bool = False,
) -> SubtitleResult:
    """End-to-end: video in → video with Japanese subtitles out.

    Parameters
    ----------
    input_video:
        Path to the English (or any-language) source video.
    output_video:
        Where to write the subtitled video. If ``None`` and ``mode`` is not
        ``"srt-only"``, defaults to ``<input>.ja.<ext>``.
    srt_output:
        Where to write the SRT file. Defaults to ``<input>.ja.srt``.
    model:
        Whisper model size.
    source_language:
        Language code for Whisper. ``None`` enables auto-detect.
    translator_backend:
        ``"auto"`` (default), ``"argos"`` (offline) or ``"google"``.
    mode:
        ``"burn"`` — hard subs baked into video (works everywhere).
        ``"soft"`` — soft subs muxed as a selectable track (better quality).
        ``"srt-only"`` — only produce the .srt file, do not touch the video.
    keep_intermediate:
        If True, keep the extracted audio WAV next to the SRT for debugging.
    """
    input_video = Path(input_video).expanduser().resolve()
    if not input_video.exists():
        raise FileNotFoundError(f"入力動画が見つかりません: {input_video}")

    if mode not in {"burn", "soft", "srt-only"}:
        raise ValueError(f"未知の mode: {mode}")

    stem = input_video.stem
    parent = input_video.parent
    if srt_output is None:
        srt_output = parent / f"{stem}.ja.srt"
    else:
        srt_output = Path(srt_output).expanduser().resolve()

    if mode != "srt-only":
        if output_video is None:
            output_video = parent / f"{stem}.ja{input_video.suffix}"
        else:
            output_video = Path(output_video).expanduser().resolve()
        if output_video.resolve() == input_video.resolve():
            raise ValueError(
                "出力ファイルが入力ファイルと同じです。別のパスを指定してください。"
            )

    with tempfile.TemporaryDirectory(prefix="subtitle_agent_") as tmpdir:
        tmp_root = Path(tmpdir)
        audio_path = tmp_root / "audio.wav"
        extract_audio(input_video, audio_path)

        segments = transcribe(
            audio_path, model_name=model, source_language=source_language
        )
        if not segments:
            raise SubtitleAgentError(
                "音声からセグメントが得られませんでした。動画に音声が含まれているか確認してください。"
            )

        translated = translate_segments(
            segments,
            backend=translator_backend,
            source_language=source_language or "en",
            target_language="ja",
        )
        write_srt(translated, srt_output)
        logger.info("SRT を書き出しました: %s", srt_output)

        if keep_intermediate:
            kept = srt_output.with_suffix(".wav")
            shutil.copy(audio_path, kept)
            logger.info("中間音声ファイルを保存: %s", kept)

        if mode == "srt-only":
            return SubtitleResult(srt_path=srt_output, video_path=None)

        assert output_video is not None
        if mode == "burn":
            burn_subtitles(input_video, srt_output, output_video)
        else:  # soft
            mux_soft_subtitles(input_video, srt_output, output_video)
        logger.info("完成した動画: %s", output_video)
        return SubtitleResult(srt_path=srt_output, video_path=output_video)
