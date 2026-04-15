# PR分割ソリューション: AISecretary と auto-translate-app

このリポジトリには、[mitsu888/cline PR #2](https://github.com/mitsu888/cline/pull/2) で発生した問題の解決策が含まれています。

## 問題

PR #2 「AI秘書 SwiftUI アプリの初期実装」には、2つの独立したプロダクトが混在していました:

1. **AISecretary** - SwiftUI で構築された iOS/macOS アプリ
2. **auto-translate-app** - Python で構築されたデスクトップ翻訳ツール

これにより以下の問題が発生:
- レビューが困難 (異なる技術スタック)
- リリース管理が複雑
- スコープが不明確

## 解決策

このプロジェクトには2つの詳細なドキュメントが含まれています:

### 📋 [PR_SPLIT_PLAN.md](./PR_SPLIT_PLAN.md)
問題の詳細分析と推奨される分割方法:
- ファイル分類 (どのファイルがどのプロジェクトに属するか)
- 分割オプションの比較
- 今後のベストプラクティス
- ブランチ命名規則

### 🛠️ [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)
実装手順の詳細ガイド:
- 3つの異なるシナリオに対応
- 具体的な Git コマンド
- CI/CD 分離の設定例
- PR テンプレートと CODEOWNERS の設定

## クイックスタート

### 推奨アプローチ: 運用ルールで管理を分離

既存の PR は既にマージされているため、履歴の書き換えは推奨されません。代わりに:

1. **PR テンプレートを設定**
   ```bash
   # IMPLEMENTATION_GUIDE.md の「PR テンプレートの作成」セクションを参照
   ```

2. **ブランチ命名規則を採用**
   - AISecretary: `feature/ai-secretary-*`, `bugfix/ai-secretary-*`
   - auto-translate-app: `feature/auto-translate-*`, `bugfix/auto-translate-*`

3. **GitHub ラベルを作成**
   ```bash
   gh label create "project:AISecretary" --color "0075ca"
   gh label create "project:auto-translate-app" --color "d93f0b"
   ```

4. **CODEOWNERS を設定**
   ```bash
   # IMPLEMENTATION_GUIDE.md の「CODEOWNERS ファイルを作成」セクションを参照
   ```

## ファイル構成

```
.
├── README.md                    # このファイル (概要)
├── PR_SPLIT_PLAN.md            # 問題分析と分割計画
└── IMPLEMENTATION_GUIDE.md      # 実装ガイド (詳細手順)
```

## 推奨される実装順序

### 即座に実施すべきこと ✅
1. PR テンプレートの作成
2. GitHub ラベルの設定
3. ブランチ命名規則の文書化
4. チームへの周知

### 1-2週間以内に実施 📅
1. CODEOWNERS の設定
2. CI/CD パイプラインの分離
3. 各プロジェクトの独立した README 作成

### 必要に応じて検討 💡
1. 別リポジトリへの分離
2. Git サブモジュールの使用

## 関連リンク

- 元の PR: https://github.com/mitsu888/cline/pull/2
- Copilot のコメント: https://github.com/mitsu888/cline/pull/2#discussion_r3068620812
- この PR: https://github.com/mitsu888/all/pull/13

## ライセンス

このドキュメントは参考資料として提供されています。実際のプロジェクトのライセンスに従ってください。

---

**作成日**: 2026-04-15
**作成者**: Claude Code Agent
**目的**: PR #2 の構造的な問題を解決し、今後の開発をスムーズにする
