---
name: pbi-sub-issue
description: pbi-task-split で ready と判定された実装タスクだけを GitHub Sub-issue として作成し、親 Issue との関係を設定する。方針未決・仕様矛盾・単なる明確化は sub-issue 化せず、親 issue の spec correction に戻す。粗めの実装 issue と phase gate / blackbox acceptance を優先する。
---

# PBI Sub-issue Creator

タスク分割プランを元に GitHub Sub-issue を作成し、親 Issue との関係を設定する。

Sub-issue は ready な実装単位だけにする。agent が issue を読んでそのまま実装・検証に入れないものは作らない。

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

### 2. Ready Gate

sub-issue 作成前に、親 issue とタスク分割プランが ready か確認する。

作成してはいけない sub-issue:

- 方針決定、仕様確認、単なる「明確化」が主目的
- 親 issue の矛盾や未決事項を子 issue に逃がしている
- acceptance criteria が実行不能、または現在のコード/運用契約と矛盾している
- 成果物が code / test / docs / config / migration / visual baseline などの review 可能な差分として定義されていない
- `Done when` / `Not done if` / 必須 verification が書けない

この場合は sub-issue を作らず、親 issue に spec correction コメントまたは本文修正案を出す。

### 3. タスク分割プランの読み込み
- Obsidian vault または plan file からタスク一覧を取得
- 各タスクの情報を整理:
  - レイヤー名（Domain, Infrastructure, Presentation, UseCase 等）
  - タスク名
  - 対象ファイル
  - 作業内容
  - 依存関係と実行順序
  - implementation contract
  - phase gate / blackbox acceptance

目安:

- 1 PBI につき 1〜3 sub-issue、最大 5
- 複数レイヤーをまたいでも、同じ目的・同じ acceptance・同じ rollback boundary なら 1 sub-issue にまとめる
- phase は原則 sub-issue ではなく、issue 本文内の review checkpoint として書く

visual UI PBI の場合:

- `Visual shell / draft UI + visual regression gate` を integration / cleanup より先の phase gate として扱う。
- 複数 agent が並列で実装する場合だけ、visual shell を独立 sub-issue にしてよい。
- non-visual parallel tasks は依存なしで作成してよいが、body に「visual baseline / threshold / selector を変更しない」と明記する。
- visual shell を独立 sub-issue にした場合だけ、integration task には visual shell task の issue 番号を依存として入れる。
- cleanup を独立 sub-issue にした場合だけ、integration task の issue 番号を依存として入れる。
- golden / screenshot baseline を変更するタスクを作る場合は、user approval required と明記する。

### 4. Sub-issue の作成（各タスクごと）

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
  --body "## 目的
{一文で実装目的を書く}

## 対象ファイル / レイヤー
- \`path/to/file1\`
- \`path/to/file2\`

## Implementation Contract
- In scope:
- Out of scope:
- Done when:
- Not done if:
- Hard blockers / accepted deferrals:

## Phase Gates
- [ ] Phase 1: {blackbox/runtime acceptance}
- [ ] Phase 2: {blackbox/runtime acceptance}

## Required Verification
- [ ] \`unit/integration command\`
- [ ] \`blackbox/runtime command\`

## 依存
- #{依存するIssue番号}

## 参考
- \`path/to/reference/file\`"
```

### 5. Sub-issue 関係の設定

**重要:** 対象リポジトリのローカルディレクトリから実行する必要がある

```bash
cd ~/path/to/repo
gh sub-issue add <親Issue番号> --sub-issue-number <作成したIssue番号>
```

### 6. 作成結果の確認
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
## 目的
{一文で実装目的を書く}

## 対象ファイル / レイヤー
- `path/to/file`

## Implementation Contract
- In scope:
- Out of scope:
- Done when:
- Not done if:
- Hard blockers / accepted deferrals:

## Phase Gates
- [ ] Phase 1: {単体テストだけでなく blackbox/runtime acceptance を書く}
- [ ] Phase 2: {必要なら review checkpoint を書く}

## Required Verification
- [ ] `command`
- [ ] `blackbox/runtime command`

## 依存
- 依存タスクがあれば記載

## 備考
- 独立して実施可能 / phase gate を含む / user approval required 等
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
- 検討中のタスクは作らない。必要なら親 issue の spec correction に戻す
- 独立タスクは備考欄に「独立して実施可能」と記載
