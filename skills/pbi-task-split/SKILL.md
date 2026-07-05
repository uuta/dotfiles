---
name: pbi-task-split
description: PBI（Product Backlog Item）を agent 実装向けの粗めの実装タスクまたは phase gate に分割する。親 issue の ready 判定、implementation contract、blackbox/runtime acceptance、依存関係、review checkpoint を整理し、方針未決・仕様矛盾・単なる明確化を sub-issue 化しない。UI PBI では approved screenshot/golden が source of truth の場合だけ visual-ui-contract を使い、共通部品・tokens・UI vocabulary が source of truth の場合は vocabulary contract で並列実装可能にする。
---

# PBI Task Split

PBIを agent が実装できる単位へ分割する。目的は細かい作業列挙ではなく、ready な implementation contract と検証可能な phase gate を作ること。

原則:

- issue / sub-issue は **ready になった時点で実装を始められるものだけ** にする
- 方針未決、仕様矛盾、受け入れ条件の破綻、単なる「明確化」は sub-issue にしない
- 実装タスクは以前より粗めでよい。agent が内部で小さく分解できる前提で、契約と acceptance を厚くする
- phase は sub-issue ではなく review / gate checkpoint として扱う。phase ごとに blackbox/runtime verification を定義する
- 目安は 1 PBI あたり 1〜3 実装 issue、最大でも 5。これを超えるなら親 PBI が大きすぎるか contract が弱い

## Procedure

### 1. 要件理解
- タスク定義ファイル（`docs/tasks.md` 等）を読む
- GitHub Issue を `gh issue view <URL>` で取得（コメントは不要なら `--comments=false`）
- PBIの要件を整理し、実装すべき機能を把握

### 1.5 Ready Gate

分割前に親 issue / PBI が ready か確認する。

Ready でない例:

- 本文内で方針が矛盾している
- acceptance criteria が現在のコード・CLI・運用契約では実行不能
- 「どちらを採用するか」「何を対象外にするか」が決まっていない
- 外部サービス、実機、VPS、runtime 値などが完了条件なのに、実施可否や deferral が書かれていない
- 「検討する」「方針を明確化する」「仕様を決める」が主目的になっている

Ready でない場合:

- sub-issue を作らない
- 親 issue の本文修正案、または spec correction コメントを出す
- 決め打ちできる安全な v1 契約がある場合は、それを親 issue に反映してから分割する

### 2. 現状コード調査
- 対象となるエンドポイント・機能の現在の実装を確認
- 関連するファイル（Router, UseCase, Schema, Domain等）を特定
- 参考になる既存実装（類似機能）があれば調査

### 3. boundary / contract の有無を判定
- 以下のいずれかに当てはまる場合、**実装タスクを切る前に boundary / contract を親 issue または実装 issue 本文に固定する**
  - フロントエンド / バックエンドが別リポジトリまたは別レイヤーで進む
  - 複数 agent / 人間が並列で実装する
  - endpoint、イベント、DTO、認証・認可、所有権、エラー shape の認識ズレが起きやすい
  - bootstrap や on-boarding のように、複数画面・複数APIをまたぐ初期フローがある
- boundary / contract の内容例
  - canonical endpoint / route の確定
  - request / response / error shape の固定
  - auth source of truth、identity、ownership の明示
  - sequence diagram や request examples の作成
  - OpenAPI / Swagger / interface / typed client contract の更新
- **重要**: interface が曖昧なまま実装に入らない。ただし「契約を決めるだけ」の sub-issue は原則作らない。
- 例外的に boundary / contract を独立 issue にできるのは、成果物が実装可能な artifact（OpenAPI 更新、typed client 更新、DB migration 契約、UI vocabulary contract / primitive API、visual regression baseline など）として明確で、その issue だけで test / review できる場合に限る。

### 3.5 UI visual source of truth を判定

UI PBI では、先に source of truth を分類する。

#### A. Screenshot-driven / baseline-driven UI

次のいずれかがある場合だけ `visual-ui-contract` を使う。

- approved screenshot / mockup / ideal image が binding reference として明記されている
- golden / screenshot baseline / visual regression test が acceptance の source of truth になっている
- visual fidelity / pixel-level or layout-level reproduction が要求されている

この場合:

- 実装タスクの前に **Visual shell / draft UI component + visual regression gate** を契約に入れる。
- 複数 agent が並列で real flow integration へ進むなら visual shell を独立 issue にしてよい。単独 agent が実装するなら同一 issue 内の phase gate として扱ってよい。
- この先行タスクは mock data で理想UIに近い component composition を作り、golden / screenshot / component-level visual test を追加する。
- component の分割と draft UI を分けると後続 agent が別UIを組み立てられる場合は、同じ先行タスクにまとめる。
- data model、URL builder、action service、provider seam、test helper など visual layout を触らないタスクはこの先行タスクと並列可にしてよい。
- real flow への mount / provider integration は visual shell タスクに依存させる。
- old modal / wrapper / legacy UI の削除は replacement UI が mount され visual gate が通った後の cleanup に置く。
- visual test が fail した場合、agent は baseline / threshold / selector / expectation を変更して通してはいけない。実装を直す。baseline 更新は user approval required と明記する。

#### B. Vocabulary-driven / common-primitives UI

approved screenshot がなく、共通部品・tokens・type roles・color roles・emblem・UI vocabulary が source of truth の場合は `visual-ui-contract` を使わない。`Frozen ref` / golden / screenshot baseline を作らない。

この場合:

- 親 issue または先行 phase gate に **UI vocabulary contract** を固定する。
- vocabulary contract には tokens、required primitives、component APIs、allowed composition、forbidden screen-local styling、information units、state/transition requirements を書く。
- screenshot は review evidence として要求してよいが、source of truth ではないと明記する。
- 並列化したい場合、vocabulary の最小 API / stub / token contract だけを先に固定し、各 screen issue はその vocabulary を参照して並列実装する。
- screen issue は vocabulary 自体を勝手に増やさない。新しい primitive / token / emblem が必要なら parent issue の vocabulary contract 更新として扱う。
- 横断 consistency audit を最後の phase gate に置き、screen-local styling、重複進捗、情報を持たない装飾、world drift を潰す。

### 4. 共通化すべき部品の特定
- 特定機能に配置されているが汎用的なコンポーネントを洗い出し
- 例: Validator, Domain Model, Utility
- 共通モジュールへの移動を計画に含める

### 5. レイヤー別タスク分割

以下の観点でタスクを分割する。レイヤーは観点であり、必ずしも別 issue にしない。

| レイヤー | 内容例 |
|---------|--------|
| **Contract** | OpenAPI、interface、DTO、sequence、ownership、canonical endpoint（原則 issue 本文内） |
| **Domain** | 共通モジュール作成、エラー定義、Model |
| **Infrastructure** | プロンプト作成、外部API連携 |
| **Presentation/Schema** | Request/Response スキーマ |
| **Presentation/Router** | エンドポイント作成・改修 |
| **UseCase** | ビジネスロジック |

**重要**: 1タスク1 implementation contract。複数レイヤーをまたいでも、同じ目的・同じ acceptance・同じ review gate で検証できるなら 1 issue にまとめる。
- 例: CLI 契約変更 + scheduler script + runbook は、blackbox acceptance が一体なら 1 issue + phase gate でよい
- 例: 別々の user-facing behavior、別々の canonical route、別々の rollback boundary を持つものは分ける

### 6. 依存関係・並列可否の整理

```
独立タスク（いつでも着手可能）
  - エラー定義
  - 旧エンドポイント改修（400エラー返却）
  - フロント側タスク（別リポジトリ）

依存チェーン
  Contract fixed in parent issue → Implementation phase 1 → Review gate → Implementation phase 2 → Review gate → Cleanup
```

- **boundary / interface が決まれば並列可能** なタスクを明示
- 独立タスクは「いつでも着手可能」と記載
- 並列化したい場合でも、boundary は親 issue または各実装 issue の contract として固定する
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

## Implementation Contract
- {canonical endpoint / route}
- {request / response / error shape}
- {auth / ownership / identity の前提}
- {in scope / out of scope}
- {UI source of truth: approved visual baseline or UI vocabulary contract, if applicable}
- {done when}
- {not done if}
- {hard blockers / accepted deferrals}

---

## Phase Gates

### Phase N: {phase名}
**目的:** {この phase で成立させる契約}

**Blackbox / runtime acceptance:**
- [ ] `{command}` が {expected result}
- [ ] {UI/API/CLI/runtime の外形確認}

**Review checkpoint:**
- {独立 review agent が見る観点}

---

## 実装 issue 候補

### Issue N: [{Layer}] {タスク名}
**目的:** {一文}

**対象ファイル / レイヤー:**
- `path/to/file.py`

**Contract:**
- Done when: {条件}
- Not done if: {条件}
- Required verification: {unit / integration / blackbox / runtime commands}

**依存:** Task X (依存タスク名)
**備考:** {独立して実施可能 / phase gate を含む / user approval required 等}

---

## 依存関係
{ASCII図で依存関係を表示}

**並列実施可能:**
- {並列可能なタスクの説明}

**Visual UI PBI の場合:**
- screenshot-driven: `Visual shell / draft UI + visual gate` → `Integration` → `Cleanup` を phase gate または必要最小の sub-issue として表す
- vocabulary-driven: `UI vocabulary contract / primitive API` → `Parallel screen implementation` → `Consistency audit` として表す
- vocabulary-driven では screenshot は evidence であり source of truth ではない
- non-visual service/model/action tasks は visual baseline または UI vocabulary を触らない条件で並列可

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

- [ ] boundary / contract を先に固定すべきPBIか判定したか
- [ ] 親 issue が ready でない場合、sub-issue 化せず spec correction に止めたか
- [ ] 方針未決・仕様矛盾・単なる明確化を sub-issue にしていないか
- [ ] 実装 issue は粗めで、1〜3個（最大5個）に収まっているか
- [ ] phase を review / gate checkpoint として定義し、不要に sub-issue 化していないか
- [ ] UI PBI の source of truth が screenshot-driven か vocabulary-driven かを分類したか
- [ ] approved screenshot / ideal UI / visual fidelity が source of truth の場合だけ `visual-ui-contract` を使ったか
- [ ] screenshot-driven の場合、visual shell / draft UI + visual regression gate を integration より前に配置したか
- [ ] screenshot-driven の場合、visual baseline / threshold / selector を agent が勝手に更新しないルールを書いたか
- [ ] vocabulary-driven の場合、UI vocabulary contract、required primitives、forbidden screen-local styling、screen information units を明記したか
- [ ] vocabulary-driven の場合、screen screenshot を source of truth ではなく review evidence として扱ったか
- [ ] 並列実装前の source of truth を明示したか
- [ ] レイヤー観点を確認したが、レイヤーごとの過剰分割をしていないか
- [ ] 1タスク1 implementation contract になっているか
- [ ] acceptance criteria に単体テストだけでなく blackbox / runtime verification が含まれるか
- [ ] 共通化すべき部品を特定したか
- [ ] 独立タスクを明示したか
- [ ] 依存関係を整理したか
- [ ] クリーンアップ計画を含めたか
- [ ] フロント側タスクを分離したか（該当する場合）
- [ ] 検討中・仕様未確定の項目は親 issue の spec correction に戻したか
