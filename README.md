# 動画日本語字幕変換エージェント

**英語 (など) の動画にワンタッチで日本語字幕をつけるツール** です。
音声認識 (OpenAI Whisper) と機械翻訳 (argos-translate / Google) を組み合わせて、
動画から `.srt` 字幕を作り、必要ならそのまま動画に焼き込みます。

> One-touch tool to add Japanese subtitles to English videos.
> Uses Whisper for speech-to-text and argos-translate (offline) or Google
> Translate for translation, then ffmpeg to render the subtitles.

---

## クイックスタート (ワンタッチ)

```bash
./subtitle path/to/movie.mp4
```

初回は仮想環境の作成と依存パッケージのインストール、Whisper モデルのダウンロード
が走るので数分かかります。2 回目以降は数十秒〜数分 (モデルサイズと動画長による)。

完了すると入力動画と同じディレクトリに以下ができます:

- `movie.ja.srt` — 日本語字幕ファイル
- `movie.ja.mp4` — 日本語字幕を焼き込んだ動画

---

## 事前準備

1. **Python 3.9 以上**
2. **ffmpeg** (音声抽出と字幕描画に使います)
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt-get install -y ffmpeg`
   - Windows: <https://ffmpeg.org/download.html>
3. **日本語フォント** (焼き込みモードのみ。既定は `Noto Sans CJK JP`)
   - Ubuntu: `sudo apt-get install -y fonts-noto-cjk`
   - macOS/Windows: 標準でヒラギノ/游ゴシック等が使えます

---

## インストール

### 方法 A: ラッパースクリプト (推奨)

`./subtitle` を実行すれば初回に `.venv` と依存が自動で用意されます。
何も考えなくて大丈夫です。

### 方法 B: 手動セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python video_ja_subtitle.py --help
```

---

## 使い方

### 基本

```bash
./subtitle movie.mp4
```

### よく使うオプション

```bash
# 出力ファイルを指定
./subtitle movie.mp4 -- -o subtitled.mp4

# SRT ファイルだけ生成 (動画は触らない)
./subtitle movie.mp4 -- --mode srt-only

# 字幕トラックとして埋め込む (画質劣化なし。再エンコードなしで一瞬)
./subtitle movie.mp4 -- --mode soft

# 精度重視 (medium は数倍遅いが精度が高い)
./subtitle movie.mp4 -- --model medium

# 入力言語を自動判定
./subtitle movie.mp4 -- --source-language auto

# オンライン翻訳 (Google) を明示的に使う
./subtitle movie.mp4 -- --translator google
```

`./subtitle` を使わず直接 Python から呼ぶ場合は `--` は不要です:

```bash
python video_ja_subtitle.py movie.mp4 --model medium --mode soft
```

### 全オプション

```
positional arguments:
  input                 入力動画ファイルのパス

options:
  -o, --output PATH     出力動画ファイルのパス
                        (デフォルト: <入力名>.ja.<拡張子>)
  --srt PATH            SRT の出力先
                        (デフォルト: <入力名>.ja.srt)
  --model {tiny,base,small,medium,large}
                        Whisper モデルサイズ (デフォルト: small)
  --source-language LANG
                        入力音声の言語コード。auto で自動検出 (デフォルト: en)
  --translator {auto,argos,google}
                        翻訳バックエンド (デフォルト: auto)
  --mode {burn,soft,srt-only}
                        burn: 字幕を焼き込む
                        soft: 字幕トラックとして埋め込む (画質劣化なし)
                        srt-only: SRT ファイルだけ作る
  --keep-intermediate   デバッグ用に抽出音声を残す
  -v, --verbose         詳細ログ
  -q, --quiet           警告以上のログのみ
```

---

## モデルサイズの選び方

| モデル   | サイズ | VRAM 目安 | 相対速度 | 精度 |
|--------|------|---------|------|------|
| tiny   | 39MB | ~1GB    | ~32x | 低   |
| base   | 74MB | ~1GB    | ~16x | ↑    |
| small  | 244MB| ~2GB    | ~6x  | 中 (デフォルト) |
| medium | 769MB| ~5GB    | ~2x  | 高   |
| large  | 1.5GB| ~10GB   | 1x   | 最高 |

CPU でも動きますが `medium` 以上は GPU (CUDA) 推奨です。

---

## プログラムから呼ぶ

`subtitle_agent.py` をライブラリとしても使えます:

```python
from subtitle_agent import generate_japanese_subtitles

result = generate_japanese_subtitles(
    input_video="movie.mp4",
    mode="burn",       # "burn" | "soft" | "srt-only"
    model="small",
)
print(result.srt_path)     # -> movie.ja.srt
print(result.video_path)   # -> movie.ja.mp4
```

---

## トラブルシューティング

### `ffmpeg が見つかりません`
OS のパッケージマネージャで ffmpeg をインストールしてください (上の「事前準備」参照)。

### 焼き込み後、日本語が豆腐 (□) になる
システムに日本語フォントが入っていません。`fonts-noto-cjk` を入れるか、
`--mode soft` (字幕トラックとして埋め込み、再生側のフォントで表示) を使ってください。

### `argos-translate` のモデルダウンロードで失敗する
`--translator google` を指定するとオンラインの Google 翻訳にフォールバックできます。

### 認識精度が低い
- より大きな Whisper モデル (`--model medium` / `--model large`) を試す
- ノイズが多い動画なら事前に音声を整えるとよいです

---

## 仕組み

```
 動画 (mp4/mkv/mov/...)
       │
       ▼   ffmpeg -vn -ar 16000 -ac 1
   16kHz WAV
       │
       ▼   openai-whisper (transcribe)
  英語セグメント + タイムスタンプ
       │
       ▼   argos-translate / Google
  日本語セグメント + タイムスタンプ
       │
       ▼   SRT 書き出し
   .ja.srt
       │
       ▼   ffmpeg (subtitles= フィルタ / mov_text)
  日本語字幕入り動画
```

---

## ライセンスと第三者ソフトウェア

このリポジトリのコード自体は自由に使ってください。実行時に依存する
サードパーティのライブラリ (Whisper / argos-translate / deep-translator /
ffmpeg) はそれぞれのライセンスに従います。
