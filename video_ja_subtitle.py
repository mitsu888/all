#!/usr/bin/env python3
"""動画日本語字幕変換エージェント CLI.

Usage:
    python video_ja_subtitle.py INPUT_VIDEO [options]

Examples:
    # 一番シンプル: 英語動画に日本語字幕を焼き込んで出力
    python video_ja_subtitle.py movie.mp4

    # 出力先を指定
    python video_ja_subtitle.py movie.mp4 -o movie_ja.mp4

    # SRT ファイルだけ生成
    python video_ja_subtitle.py movie.mp4 --mode srt-only

    # 選択可能な字幕トラックとして埋め込む (画質劣化なし)
    python video_ja_subtitle.py movie.mp4 --mode soft

    # 精度重視 (低速)
    python video_ja_subtitle.py movie.mp4 --model medium
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import subtitle_agent
from subtitle_agent import (
    DependencyMissingError,
    SubtitleAgentError,
    generate_japanese_subtitles,
)


WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
MODES = ["burn", "soft", "srt-only"]
TRANSLATOR_BACKENDS = ["auto", "argos", "google"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video_ja_subtitle",
        description=(
            "英語 (など) の動画にワンタッチで日本語字幕をつけるツール / "
            "One-touch tool to add Japanese subtitles to English videos."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="入力動画ファイルのパス")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="出力動画ファイルのパス (デフォルト: <入力名>.ja.<拡張子>)",
    )
    parser.add_argument(
        "--srt",
        type=Path,
        default=None,
        help="SRT 字幕ファイルの出力先 (デフォルト: <入力名>.ja.srt)",
    )
    parser.add_argument(
        "--model",
        choices=WHISPER_MODELS,
        default="small",
        help="Whisper モデルサイズ (小さいほど高速、大きいほど高精度)",
    )
    parser.add_argument(
        "--source-language",
        default="en",
        help="入力音声の言語コード (例: en, fr, zh)。auto を指定すると自動検出",
    )
    parser.add_argument(
        "--translator",
        choices=TRANSLATOR_BACKENDS,
        default="auto",
        help=(
            "翻訳バックエンド。auto は argos-translate (オフライン) を試し、"
            "失敗したら google (オンライン) を使う"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="burn",
        help=(
            "burn: 字幕を映像に焼き込む / soft: 字幕トラックとして埋め込む / "
            "srt-only: SRT ファイルだけ生成"
        ),
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="デバッグ用に抽出音声を残す",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="詳細ログを表示",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="警告以上のログのみ表示",
    )
    return parser


def _configure_logging(verbose: bool, quiet: bool) -> None:
    if verbose and quiet:
        raise SystemExit("--verbose と --quiet は同時に指定できません。")
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose, args.quiet)

    source_language = None if args.source_language.lower() == "auto" else args.source_language

    try:
        result = generate_japanese_subtitles(
            input_video=args.input,
            output_video=args.output,
            srt_output=args.srt,
            model=args.model,
            source_language=source_language,
            translator_backend=args.translator,
            mode=args.mode,
            keep_intermediate=args.keep_intermediate,
        )
    except DependencyMissingError as exc:
        print(f"[依存不足] {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"[ファイルなし] {exc}", file=sys.stderr)
        return 3
    except SubtitleAgentError as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n中断されました。", file=sys.stderr)
        return 130

    print()
    print("=" * 60)
    print("完了しました / Done!")
    print(f"  SRT   : {result.srt_path}")
    if result.video_path is not None:
        print(f"  動画  : {result.video_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
