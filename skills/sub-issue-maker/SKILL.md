---
name: sub-issue-maker
description: Provide coarse, agent-ready task granularity for cutting GitHub sub-issues. Use implementation contracts and blackbox acceptance, avoid creating sub-issues for policy clarification, unresolved decisions, or specification contradictions.
---

## Conditions

### もし何かを実装する必要があるなら

sub-issue は ready な実装単位だけに切る。agent が issue を読んでそのまま実装・検証に入れないものは作らない。

まず、親 issue が ready か確認してください。

sub-issue にしてはいけないもの:

- 方針決定、仕様確認、単なる「明確化」
- 親 issue の矛盾や未決事項を子 issue に逃がしているもの
- acceptance criteria が現在のコード・運用契約で実行不能なもの
- 成果物が code / test / docs / config / migration / visual baseline などの review 可能な差分として定義できないもの

この場合は sub-issue を作らず、親 issue に spec correction コメントまたは本文修正案を出してください。

以下に当てはまる場合は **Boundary / Contract を先に固定** してください。ただし、原則として contract は親 issue または実装 sub-issue 本文に書き、単なる contract 明確化だけの sub-issue は作らないでください。

- Frontend / Backend が別々に進む
- 複数 agent や複数人が並列で進める
- endpoint、DTO、認証、ownership、error shape のズレが起きやすい
- bootstrap / onboarding のように、複数画面・複数APIをまたぐフローがある

Boundary / Contract の内容例:

- canonical endpoint / route の確定
- request / response / error shape の固定
- auth source of truth と ownership の明示
- OpenAPI / Swagger / interface の更新
- sequence diagram や request examples の記述

Boundary / Contract を独立 sub-issue にできるのは、OpenAPI 更新、typed client 更新、DB migration 契約、visual regression baseline など、成果物が実装可能で test / review できる場合に限ります。

task 粒度の目安:

- 1 PBI につき 1〜3 sub-issue、最大 5
- 複数レイヤーをまたいでも、同じ目的・同じ acceptance・同じ rollback boundary なら 1 sub-issue にまとめる
- phase は原則 sub-issue ではなく、issue 本文内の review / gate checkpoint として扱う
- 各 sub-issue に `Done when` / `Not done if` / `Required verification` を書く
- verification は単体テストだけでなく blackbox / runtime acceptance を含める

- Frontend
  - boundary / contract の consumer 実装
  - constantsの修正
  - domainの修正
  - infrastructureの修正（APIを定義・修正したりする場合のみ）
- Backend
  - boundary / contract の provider 実装
  - controllerの修正
  - domainの修正
  - use caseの修正
  - infrastructureの修正（外部APIを新たに定義・修正したり、table schemaを新たに定義・修正したりする必要がある場合のみ）

要件を読んで、他に必要そうなタスクがあれば適宜切ってください（Dockerfileの修正等）

**重要**:
- interface が未確定なら、実装 sub-issue を切らず親 issue の contract を直す
- 並列実装したい場合、contract の source of truth を親 issue または artifact として明示する
- 「実装」と「契約」は分離しすぎない。agent-ready な 1 issue に目的、scope、phase gate、verification をまとめる

### 他の要件に関して

要件に応じて適切なサイズでtaskを切ってください。細分化より、ready な契約と検証可能な acceptance を優先してください。
