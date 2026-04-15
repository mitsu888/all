# PR分割計画: AI秘書とAuto-Translate-Appの分離

## 問題の概要

mitsu888/cline のPR #2「AI秘書 SwiftUI アプリの初期実装」には、以下の2つの独立したプロダクトが含まれています:

1. **AISecretary** - iOS/macOS向けSwiftUIアプリ (AI秘書機能)
2. **auto-translate-app** - Pythonデスクトップ翻訳ツール

これらは異なる技術スタック、異なる目的を持つ別々のプロダクトであるため、レビューやリリース管理の観点から別々のPRに分割することが推奨されます。

## ファイル分類

### AISecretary プロジェクト (SwiftUI)
以下のディレクトリ/ファイルが含まれます:
- `AISecretary/` - 全ディレクトリ
  - `AISecretary/AISecretary/` - アプリケーションコード
  - `AISecretary/AISecretary/Models/` - データモデル
  - `AISecretary/AISecretary/Services/` - サービス層
  - `AISecretary/AISecretary/Views/` - UI層
  - `AISecretary/AISecretary/AppIntents/` - Siriショートカット
  - `AISecretary/AISecretary/Utilities/` - ユーティリティ
  - 設定ファイル (.entitlements, Info.plist等)

**技術スタック**: Swift, SwiftUI, SwiftData, EventKit, MapKit, Claude API

**主な機能**:
- チャット機能 (Claude API連携)
- 音声入力・ボイスメモ
- スケジュール管理 (カレンダー同期)
- タスク管理
- 習慣トラッカー
- 日次報告機能
- プロアクティブ通知

### auto-translate-app プロジェクト (Python)
以下のディレクトリ/ファイルが含まれます:
- `auto-translate-app/` - 全ディレクトリ
  - `auto-translate-app/main.py` - メインアプリケーション
  - `auto-translate-app/requirements.txt` - Python依存関係
  - `auto-translate-app/README.md` - プロジェクトドキュメント
  - その他Pythonソースファイル

**技術スタック**: Python, PyQt/Tkinter (GUI), Claude API

**主な機能**:
- デスクトップ翻訳ツール
- クリップボード監視
- 自動翻訳

## 推奨される分割方法

### オプション1: 既存PRが未マージの場合

1. **現在のPRをクローズ**
   - PR #2をクローズまたは下書きに戻す

2. **AISecretaryブランチを作成**
   ```bash
   # 元のブランチから開始
   git checkout claude/auto-translate-app-ozIEb

   # 新しいブランチを作成
   git checkout -b feature/ai-secretary-app

   # auto-translate-app/ ディレクトリを削除
   git rm -r auto-translate-app/
   git commit -m "Remove auto-translate-app (will be in separate PR)"

   # プッシュ
   git push origin feature/ai-secretary-app
   ```

3. **auto-translate-appブランチを作成**
   ```bash
   # 元のブランチから開始
   git checkout claude/auto-translate-app-ozIEb

   # 新しいブランチを作成
   git checkout -b feature/auto-translate-app

   # AISecretary/ ディレクトリを削除
   git rm -r AISecretary/
   git commit -m "Remove AISecretary (will be in separate PR)"

   # プッシュ
   git push origin feature/auto-translate-app
   ```

4. **2つの新しいPRを作成**
   - PR 1: "Add AISecretary SwiftUI App"
   - PR 2: "Add Auto-Translate Desktop Tool"

### オプション2: 既存PRが既にマージされている場合 (現在の状況)

PR #2は既にマージされているため、以下のアプローチを推奨します:

1. **今後の開発では別々のブランチ/PRを使用**
   - AISecretaryの機能追加 → `feature/ai-secretary-*` ブランチ
   - auto-translate-appの機能追加 → `feature/auto-translate-*` ブランチ

2. **プロジェクト構造の整理**
   ```
   repository/
   ├── AISecretary/          # iOS/macOS アプリ
   │   ├── AISecretary.xcodeproj
   │   └── AISecretary/
   │       ├── Models/
   │       ├── Views/
   │       └── Services/
   ├── auto-translate-app/   # Python デスクトップツール
   │   ├── main.py
   │   ├── requirements.txt
   │   └── README.md
   └── README.md             # ルートREADME (両プロジェクトを説明)
   ```

3. **各プロジェクトの独立したREADMEを作成**
   - `AISecretary/README.md` - SwiftUIアプリの説明
   - `auto-translate-app/README.md` - 翻訳ツールの説明

## 今後のベストプラクティス

### PR作成時のガイドライン

1. **1 PR = 1プロジェクト**
   - AISecretaryの変更はAISecretary専用のPR
   - auto-translate-appの変更はauto-translate-app専用のPR

2. **明確なPRタイトル**
   - ✅ 良い例: "[AISecretary] Add habit tracker feature"
   - ✅ 良い例: "[auto-translate-app] Fix clipboard monitoring"
   - ❌ 悪い例: "Add new features" (どちらのプロジェクトか不明)

3. **PRの説明に含めるべき内容**
   - 対象プロジェクト名
   - 変更の概要
   - 影響範囲
   - テスト方法

4. **レビュアーの割り当て**
   - SwiftUIの専門家 → AISecretary PR
   - Pythonの専門家 → auto-translate-app PR

### ブランチ命名規則

```
feature/ai-secretary-<feature-name>    # AISecretary用
feature/auto-translate-<feature-name>  # auto-translate-app用
bugfix/ai-secretary-<bug-description>  # AISecretaryバグ修正
bugfix/auto-translate-<bug-description> # auto-translate-appバグ修正
```

## まとめ

このPRはすでにマージされているため、履歴の書き換えは推奨されません。代わりに:

1. **今後は各プロジェクトを独立したPRで管理**
2. **明確なブランチ命名規則を使用**
3. **PRタイトル/説明でプロジェクトを明示**
4. **各プロジェクトの独立したドキュメントを維持**

これにより、レビューが容易になり、リリース管理も明確になります。

## 参考リンク

- 元のPR: https://github.com/mitsu888/cline/pull/2
- Copilotのコメント: https://github.com/mitsu888/cline/pull/2#discussion_r3068620812
