---
name: pbi-task-split
description: PBI（Product Backlog Item）をレイヤー別に分割し、並列実施可能なタスクを特定する。boundary / contract タスク、共通化すべき部品の洗い出し、依存関係の整理、クリーンアップ計画まで含む。
---

# PBI Task Split

PBIを実装可能なタスクに分割する。レイヤー別分割、boundary / contract の明示、共通化、並列可否を考慮した計画を作成する。

## Procedure

### 1. 要件理解
- タスク定義ファイル（`docs/tasks.md` 等）を読む
- GitHub Issue を `gh issue view <URL>` で取得（コメントは不要なら `--comments=false`）
- PBIの要件を整理し、実装すべき機能を把握

### 2. 現状コード調査
- 対象となるエンドポイント・機能の現在の実装を確認
- 関連するファイル（Router, UseCase, Schema, Domain等）を特定
- 参考になる既存実装（類似機能）があれば調査

### 3. boundary / contract の有無を判定
- 以下のいずれかに当てはまる場合、**実装タスクの前に boundary / contract タスクを切る**
  - フロントエンド / バックエンドが別リポジトリまたは別レイヤーで進む
  - 複数 agent / 人間が並列で実装する
  - endpoint、イベント、DTO、認証・認可、所有権、エラー shape の認識ズレが起きやすい
  - bootstrap や on-boarding のように、複数画面・複数APIをまたぐ初期フローがある
- boundary / contract タスクの内容例
  - canonical endpoint / route の確定
  - request / response / error shape の固定
  - auth source of truth、identity、ownership の明示
  - sequence diagram や request examples の作成
  - OpenAPI / Swagger / interface / typed client contract の更新
- **重要**: interface が曖昧なまま並列実装に入らない。ズレや再実装コストが高い場合、boundary タスクを独立 issue にする。

### 4. 共通化すべき部品の特定
- 特定機能に配置されているが汎用的なコンポーネントを洗い出し
- 例: Validator, Domain Model, Utility
- 共通モジュールへの移動を計画に含める

### 5. レイヤー別タスク分割

以下の観点でタスクを分割する：

| レイヤー | 内容例 |
|---------|--------|
| **Boundary / Contract** | OpenAPI、interface、DTO、sequence、ownership、canonical endpoint |
| **Domain** | 共通モジュール作成、エラー定義、Model |
| **Infrastructure** | プロンプト作成、外部API連携 |
| **Presentation/Schema** | Request/Response スキーマ |
| **Presentation/Router** | エンドポイント作成・改修 |
| **UseCase** | ビジネスロジック |

**重要**: 1タスク1機能の原則。1タスクに複数機能を入れない。
- 例: `/review` 400エラーと `/v2/review` 新規作成は別タスク
- 例: `POST /user` bootstrap contract の確定 と、その handler 実装は別タスクにできる

### 6. 依存関係・並列可否の整理

```
独立タスク（いつでも着手可能）
  - エラー定義
  - 旧エンドポイント改修（400エラー返却）
  - フロント側タスク（別リポジトリ）

依存チェーン
  Boundary / Contract → Domain → Infrastructure → Schema → UseCase → Router
```

- **boundary / interface が決まれば並列可能** なタスクを明示
- 独立タスクは「いつでも着手可能」と記載
- 並列化したい場合、boundary タスクを完了条件付きの先行タスクとして書く
- frontend / backend で契約を共有する場合、どの artifact が source of truth かを書く

### 7. クリーンアップ計画
- 削除対象ファイルを洗い出し
- 旧コード、旧テスト、不要なimportを特定
- **最後に実施するタスク** として配置

### 8. フロント側タスク（該当する場合）
- 別リポジトリの作業を明示
- バックエンドと独立して実施可能であることを記載
- エンドポイント差し替え、バリデーション追加等
- backend との境界がある場合、先に boundary / contract タスクを切る
- frontend は boundary の consumer として何を実装するのかを明示する

### 9. 出力フォーマット

```markdown
# {機能名} 実装タスク分割

## 概要
{GitHub Issue URL} に基づき、{機能概要}を実装する。

## 方針
- {エンドポイント構成等}
- {boundary / contract の source of truth}

## Boundary / Contract
- {canonical endpoint / route}
- {request / response / error shape}
- {auth / ownership / identity の前提}
- {未確定事項があればここに明記}

---

## タスク一覧（レイヤー別）

### Task N: {レイヤー}層 - {タスク名}
**対象ファイル:**
- `path/to/file.py`

**作業内容:**
- [ ] 作業項目1
- [ ] 作業項目2

**依存:** Task X (依存タスク名)
**備考:** {独立して実施可能 / 検討中 等}

---

## 依存関係
{ASCII図で依存関係を表示}

**並列実施可能:**
- {並列可能なタスクの説明}

---

## 参考ファイルパス
| カテゴリ | ファイル |
|---------|---------|
| 現行xxx | `path/to/file` |
| 参考実装 | `path/to/reference` |
| 契約定義 | `path/to/openapi-or-interface` |
```

### 10. Obsidian vault に保存
- `/plan-on-md` を使用して保存
- パス: `~/uuta/Projects/{project}/{branch}/{file}.md`

## 観点チェックリスト

- [ ] boundary / contract を先に切るべきPBIか判定したか
- [ ] 並列実装前の source of truth を明示したか
- [ ] レイヤー別に分割されているか
- [ ] 1タスク1機能になっているか
- [ ] 共通化すべき部品を特定したか
- [ ] 独立タスクを明示したか
- [ ] 依存関係を整理したか
- [ ] クリーンアップ計画を含めたか
- [ ] フロント側タスクを分離したか（該当する場合）
- [ ] 検討中・仕様未確定の項目を明示したか
