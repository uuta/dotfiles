---
name: pbi-sub-issue
description: タスク分割プラン（pbi-task-splitで作成）を元に、GitHub の Sub-issue を作成する。親 Issue との関係も自動で設定。visual UI PBI では pbi-task-split の visual shell / visual gate / integration / cleanup の順序と依存関係を崩さず作成する。
---

# PBI Sub-issue Creator

タスク分割プランを元に GitHub Sub-issue を作成し、親 Issue との関係を設定する。

## Prerequisites

### 拡張機能のインストール
```bash
gh extension install agbiotech/gh-sub-issue
```

### 必要な情報
- 親 Issue の URL または番号
- タスク分割プラン（`/pbi-task-split` で作成したもの）
- 対象リポジトリのローカルクローン（sub-issue 関係設定に必要）

## Procedure

### 1. 親 Issue の確認
```bash
gh issue view <親Issue番号> --repo <owner>/<repo>
```

### 2. タスク分割プランの読み込み
- Obsidian vault または plan file からタスク一覧を取得
- 各タスクの情報を整理:
  - レイヤー名（Domain, Infrastructure, Presentation, UseCase 等）
  - タスク名
  - 対象ファイル
  - 作業内容
  - 依存関係と実行順序

visual UI PBI の場合:

- `Visual shell / draft UI + visual regression gate` タスクを integration / cleanup より先に作成する。
- non-visual parallel tasks は依存なしで作成してよいが、body に「visual baseline / threshold / selector を変更しない」と明記する。
- integration task には visual shell task の issue 番号を依存として入れる。
- cleanup task には integration task の issue 番号を依存として入れる。
- golden / screenshot baseline を変更するタスクを作る場合は、user approval required と明記する。

### 3. Sub-issue の作成（各タスクごと）

**Title フォーマット:**
```
[{Layer}] {タスク名}
```

**例:**
- `[Domain] 共通モジュール作成`
- `[Infrastructure] コーディング規約用プロンプト作成`
- `[Presentation/Schema] Request/Response スキーマ`
- `[Presentation/Router] /review 400エラー`
- `[UseCase] V2ReviewUseCase`
- `[Frontend] /v2/review 対応`
- `[Cleanup] 旧ファイル削除`

**コマンド:**
```bash
gh issue create \
  --repo <owner>/<repo> \
  --title "[{Layer}] {タスク名}" \
  --body "## 対象ファイル
- \`path/to/file1\`
- \`path/to/file2\`

## 作業内容
- [ ] 作業項目1
- [ ] 作業項目2
- [ ] 作業項目3

## 依存
- #{依存するIssue番号}

## 参考
- \`path/to/reference/file\`"
```

### 4. Sub-issue 関係の設定

**重要:** 対象リポジトリのローカルディレクトリから実行する必要がある

```bash
cd ~/path/to/repo
gh sub-issue add <親Issue番号> --sub-issue-number <作成したIssue番号>
```

### 5. 作成結果の確認
```bash
cd ~/path/to/repo
gh sub-issue list <親Issue番号>
```

## Full Example

```bash
# 1. Issue 作成
ISSUE_URL=$(gh issue create \
  --repo galirage/mu-copilot-dev \
  --title "[Domain] 共通モジュール作成" \
  --body "## 対象ファイル
- \`src/domain/gitlab_review/models/coding_convention_validator.py\`
- \`src/domain/gitlab_review/models/coding_convention.py\`

## 作業内容
- [ ] \`src/domain/coding_convention/\` ディレクトリを作成
- [ ] CodingConventionValidator を移動
- [ ] import を更新")

# 2. Issue 番号を抽出
ISSUE_NUM=$(echo $ISSUE_URL | grep -oE '[0-9]+$')

# 3. Sub-issue 関係を設定
cd ~/mu-copilot-dev
gh sub-issue add 1324 --sub-issue-number $ISSUE_NUM
```

## Body Template

```markdown
## 対象ファイル
- `path/to/file`

## 作業内容
- [ ] 作業項目

## 依存
- 依存タスクがあれば記載

## 備考
- 独立して実施可能 / 検討中 等
- visual UI task の場合: golden / screenshot baseline、threshold、selector、visual expectation は user approval なしに変更しない

## 参考
- `path/to/reference`
```

## Layer 名一覧

| Layer | 説明 |
|-------|------|
| `Domain` | ドメインモデル、バリデータ、エラー定義 |
| `Infrastructure` | プロンプト、外部API連携、DB |
| `Presentation/Schema` | Request/Response スキーマ |
| `Presentation/Router` | エンドポイント |
| `UseCase` | ビジネスロジック |
| `Frontend` | フロントエンド（別リポジトリ） |
| `Cleanup` | 旧コード削除、クリーンアップ |

## Notes

- Sub-issue 関係の設定は対象リポジトリのローカルクローンから実行が必要
- 検討中のタスクは `【検討中】` をタイトルに含める
- 独立タスクは備考欄に「独立して実施可能」と記載
