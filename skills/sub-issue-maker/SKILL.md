---
name: sub-issue-maker
description: Provide the task granularity for cutting subissues.
---

## Conditions

### もし何かを実装する必要があるなら

DDDをプロジェクトに採用しているため、下記の観点でSub-issueに切れないか検討してください。

まず、以下に当てはまる場合は **Boundary / Contract 用の sub-issue** を先に切ることを検討してください。

- Frontend / Backend が別々に進む
- 複数 agent や複数人が並列で進める
- endpoint、DTO、認証、ownership、error shape のズレが起きやすい
- bootstrap / onboarding のように、複数画面・複数APIをまたぐフローがある

Boundary / Contract issue の内容例:

- canonical endpoint / route の確定
- request / response / error shape の固定
- auth source of truth と ownership の明示
- OpenAPI / Swagger / interface の更新
- sequence diagram や request examples の記述

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
- interface が未確定なら、実装 sub-issue より先に boundary sub-issue を切る
- 並列実装したい場合、boundary issue を依存元として明示する
- 「実装」と「契約定義」を同じ sub-issue に詰め込みすぎない

### 他の要件に関して

要件に応じて適切なサイズでtaskを切ってください
