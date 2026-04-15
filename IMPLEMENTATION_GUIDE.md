# 実装ガイド: PRを2つのプロジェクトに分割する

このガイドでは、既にマージされたPR #2の内容を将来的に適切に管理するための実装方法を説明します。

## 前提条件

- PR #2 は既に `mitsu888/cline` の `main` ブランチにマージ済み
- リポジトリには2つの独立したプロジェクトが含まれている:
  - `AISecretary/` (SwiftUI iOS/macOSアプリ)
  - `auto-translate-app/` (Python デスクトップツール)

## シナリオ1: 新しいリポジトリに分離する (推奨)

最もクリーンな解決策は、各プロジェクトを独立したリポジトリに分離することです。

### ステップ1: AISecretaryリポジトリを作成

```bash
# 新しいディレクトリを作成
mkdir AISecretary-standalone
cd AISecretary-standalone

# 元のリポジトリから AISecretary のみを含むブランチを作成
git clone https://github.com/mitsu888/cline.git temp
cd temp

# フィルターブランチで AISecretary のみを保持
git filter-branch --subdirectory-filter AISecretary -- --all

# 新しいリモートリポジトリにプッシュ
git remote set-url origin https://github.com/mitsu888/AISecretary.git
git push -u origin main

cd ..
rm -rf temp
```

### ステップ2: auto-translate-appリポジトリを作成

```bash
# 新しいディレクトリを作成
mkdir auto-translate-app-standalone
cd auto-translate-app-standalone

# 元のリポジトリから auto-translate-app のみを含むブランチを作成
git clone https://github.com/mitsu888/cline.git temp
cd temp

# フィルターブランチで auto-translate-app のみを保持
git filter-branch --subdirectory-filter auto-translate-app -- --all

# 新しいリモートリポジトリにプッシュ
git remote set-url origin https://github.com/mitsu888/auto-translate-app.git
git push -u origin main

cd ..
rm -rf temp
```

### ステップ3: 元のリポジトリを更新

元の `cline` リポジトリから両プロジェクトを削除し、submodule として追加:

```bash
cd cline

# 両プロジェクトを削除
git rm -r AISecretary auto-translate-app
git commit -m "Split projects into separate repositories"

# submodule として追加 (オプション)
git submodule add https://github.com/mitsu888/AISecretary.git AISecretary
git submodule add https://github.com/mitsu888/auto-translate-app.git auto-translate-app
git commit -m "Add projects as submodules"
git push origin main
```

## シナリオ2: 同じリポジトリ内で管理を分離する

リポジトリを分けたくない場合、ブランチとPRの運用ルールで管理を分離できます。

### ブランチ保護ルールの設定

GitHub の Settings > Branches で以下を設定:

1. **Branch protection rules for `main`**:
   - Require pull request reviews before merging
   - Require status checks to pass before merging

2. **CODEOWNERS ファイルを作成**:

```bash
# .github/CODEOWNERS を作成
cat > .github/CODEOWNERS << 'EOF'
# AISecretary project
/AISecretary/ @mitsu888 @swift-team

# auto-translate-app project
/auto-translate-app/ @mitsu888 @python-team

# Root files
/*.md @mitsu888
EOF

git add .github/CODEOWNERS
git commit -m "Add CODEOWNERS for project separation"
git push origin main
```

### GitHub Labelsの設定

プロジェクトごとにラベルを作成:

```bash
# GitHub CLI を使用してラベルを作成
gh label create "project:AISecretary" --description "AISecretary SwiftUI App" --color "0075ca"
gh label create "project:auto-translate-app" --description "Auto Translate Desktop Tool" --color "d93f0b"
```

### PR テンプレートの作成

```bash
# .github/PULL_REQUEST_TEMPLATE.md を作成
cat > .github/PULL_REQUEST_TEMPLATE.md << 'EOF'
## プロジェクト

- [ ] AISecretary (SwiftUI App)
- [ ] auto-translate-app (Python Tool)
- [ ] その他

## 変更内容

<!-- 変更内容を簡潔に説明してください -->

## 影響範囲

- [ ] AISecretary のみ
- [ ] auto-translate-app のみ
- [ ] 両プロジェクトに影響
- [ ] ドキュメントのみ

## テスト

<!-- テスト方法を記載してください -->

## チェックリスト

- [ ] 適切なラベルを付与した
- [ ] 該当プロジェクトのREADMEを更新した (必要な場合)
- [ ] テストが通過した
EOF

git add .github/PULL_REQUEST_TEMPLATE.md
git commit -m "Add PR template for project separation"
git push origin main
```

## シナリオ3: 既存のマージ済みコミットを分割する (上級者向け)

⚠️ **警告**: この操作は git 履歴を書き換えます。チーム全体の合意が必要です。

### 前提条件

- チーム全員が作業をコミットしている
- 全員が履歴の書き換えに同意している

### 手順

```bash
# バックアップブランチを作成
git checkout main
git branch backup-before-split

# インタラクティブリベースで分割
git rebase -i <commit-before-PR-merge>

# エディタで、マージコミットを 'edit' に変更
# 保存して閉じる

# 変更を2つのコミットに分割
git reset HEAD~
git add AISecretary/
git commit -m "Add AISecretary SwiftUI App"
git add auto-translate-app/
git commit -m "Add Auto-Translate Desktop Tool"

# リベースを続行
git rebase --continue

# 強制プッシュ (危険!)
git push --force-with-lease origin main
```

### チームメンバーへの通知

```bash
# チーム全員に以下を実行してもらう
git fetch origin
git reset --hard origin/main
```

## 推奨される運用フロー

### 新機能開発時

```bash
# AISecretary の機能追加
git checkout -b feature/ai-secretary-habit-tracker
# 変更を加える
git add AISecretary/
git commit -m "[AISecretary] Add habit tracker feature"
git push origin feature/ai-secretary-habit-tracker
# PR作成: タイトル "[AISecretary] Add habit tracker feature"

# auto-translate-app の機能追加
git checkout -b feature/auto-translate-clipboard-monitor
# 変更を加える
git add auto-translate-app/
git commit -m "[auto-translate-app] Improve clipboard monitoring"
git push origin feature/auto-translate-clipboard-monitor
# PR作成: タイトル "[auto-translate-app] Improve clipboard monitoring"
```

### バグ修正時

```bash
# AISecretary のバグ修正
git checkout -b bugfix/ai-secretary-schedule-sync
git add AISecretary/
git commit -m "[AISecretary] Fix schedule sync issue"
git push origin bugfix/ai-secretary-schedule-sync

# auto-translate-app のバグ修正
git checkout -b bugfix/auto-translate-api-error
git add auto-translate-app/
git commit -m "[auto-translate-app] Fix API error handling"
git push origin bugfix/auto-translate-api-error
```

## CI/CD の分離

### GitHub Actions ワークフロー例

```yaml
# .github/workflows/ai-secretary.yml
name: AISecretary CI

on:
  pull_request:
    paths:
      - 'AISecretary/**'
  push:
    branches: [main]
    paths:
      - 'AISecretary/**'

jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build and Test
        run: |
          cd AISecretary
          xcodebuild test -scheme AISecretary
```

```yaml
# .github/workflows/auto-translate-app.yml
name: Auto-Translate-App CI

on:
  pull_request:
    paths:
      - 'auto-translate-app/**'
  push:
    branches: [main]
    paths:
      - 'auto-translate-app/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd auto-translate-app
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd auto-translate-app
          pytest
```

## まとめ

推奨される順序:

1. **短期的 (今すぐ)**:
   - PR テンプレートの作成
   - ラベルの設定
   - CODEOWNERS の設定
   - ブランチ命名規則の統一

2. **中期的 (1-2週間以内)**:
   - CI/CD の分離
   - 各プロジェクトの独立したREADME作成
   - ドキュメントの整理

3. **長期的 (必要に応じて)**:
   - 別リポジトリへの分離を検討
   - Git 履歴のクリーンアップ (チーム合意が得られた場合のみ)

最も重要なのは、**今後のPRで混在を避けること**です。過去の履歴を書き換えるよりも、今後の運用ルールを確立することに注力してください。
