---
name: claude-tmux-pm
description: tmux 上の Claude Code セッションに GitHub の sub-issue を順番に割り当てるスキル。親 Issue 配下の sub-issue を番号順に見て、最初の未対応タスクが `S` ラベルなら `feat/{issue_number}` ブランチの専用 worktree（basename は `<issue_number>`）で Claude Code に実装させる。workspace / worktree の配置規約は `agent-workspace` に従う。Claude は実装と検証まで行い、Codex が diff review してから commit / push / PR を行う。最初の未対応タスクが `M` または `L` の場合は通常は割り当てず、先に対応方針をユーザーと相談する。ただしユーザーが特定 issue について明示的に override した場合は、その issue に限って割り当ててよい。各実行の冒頭では、merge 済み PR に対応する専用 pane / window / worktree を安全に掃除する。「Claude Code に割り当てて」「tmux の Claude に投げて」「agent に issue を振って」などで使用。
allowed-tools: Bash(tmux:*), Bash(gh:*), Bash(git:*)
---

# Claude Code tmux PM Skill

## Guardrails

- workspace / worktree layout は `agent-workspace` の規約に従う
- `S` ラベルの task だけを Claude Code に割り当てる
- `M` / `L` は通常は割り当てない。ユーザーが特定 issue 番号を明示して override した場合だけ例外的に割り当ててよい
- sub-issue は必ず番号の小さい順に扱う
- 先頭の未対応 task が `M` または `L` なら、後ろの `S` を飛ばして割り当ててはいけない
- ブランチ名は必ず `feat/{issue_number}` を使う
- 1 agent につき 1 task だけを担当させる
- Claude Code は必ず `--dangerously-skip-permissions` を付けて起動する
- issue ごとに専用 worktree を使う。既存のユーザー作業中 checkout は使わない
- Claude Code は実装と検証まで行い、commit / push / PR は Codex が review 後に行うのを原則とする
- Claude が「完了」と言っても、そのまま成功扱いにしない。必ず diff review を挟む
- merge 済み PR に対応する専用 pane / window / worktree は、clean であれば回収してよい。識別は `<issue_number>` を共通キーにする
- issue 予約は pane title だけでなく window 名にも残す
- 実装 issue を Claude に渡す前に、sub-issue 側に明示的な implementation contract があることを確認する
- 初回 assignment prompt には scope だけでなく `Done when` / `Not done if` / `Hard blockers` を必ず含める。runtime acceptance や external config が絡む issue を「コードと docs は入った」で完了扱いにさせてはいけない
- issue 本文やコメントで仕様が明確になった場合、Claude に渡す前にその内容を sub-issue に反映する。会話中の口頭合意だけで渡してはいけない
- routing / UX flow / API contract を変える issue は特に厳格に扱う。既存 flow を置き換えるのか、追加するだけなのかが issue に書かれていなければ割り当ててはいけない
- frontend route / island / hydration 変更では、実装後の verification に `build` と bundle 警告確認を含める。test/lint だけで完了扱いにしてはいけない

## Implementation Contract Gate

Claude に実装を振る前に、対象 sub-issue が少なくとも次を持っていることを確認する。

- 何を変える issue なのかを一文で表した目的
- canonical な URL / API / UI flow
- 既存の URL / API / UI flow を残すのか、redirect するのか、404 にするのか
- ユーザーがその flow に入る entrypoint
- 変更対象として想定している既存ファイルやレイヤー
- acceptance criteria または implementation steps
- `done` の定義
- `not done` とみなす条件
- 必須 verification（例: build, simulator, physical device, API call, migration）
- local secrets / external service / dashboard setup が前提なのか、なければ blocker なのか

以下のような change は、上の contract が欠けていると誤実装しやすい。

- routing
- permalink
- button など entrypoint の遷移先変更
- repository / API の責務移動
- 「新規ページ追加」ではなく「既存 flow 置換」に近いもの
- island の hydration 境界や重い client-side 依存を含む frontend page 変更

特に route 系 issue では、次を明文化していない限り割り当てない。

- canonical route は何か
- old route は valid か invalid か
- invalid の場合は 404 / redirect のどちらか
- CTA や導線がどこへ遷移するべきか
- route parameter が必須かどうか

frontend page / island 系 issue では、可能なら次も明文化する。

- どの部分が server-rendered で、どの部分だけ hydrate するか
- 重い dependency を lazy load する必要があるか
- build 時に bundle / chunk size を確認すること

runtime / native / external-config 依存の強い issue では、特に次を曖昧にしない。

- 実値を repo に入れるべきか、ローカル/CI/外部 dashboard 側で持つべきか
- その issue の完了条件に real value / real device / real service verification が含まれるか
- その verification が現 turn で不可能なら `not done` なのか、別 issue に明示的に defer されているのか

issue がこの水準に達していない場合は、Claude に投げる前にユーザーと詰めて sub-issue を更新する。

## Pre-Assignment Summary

Claude に送る前に、Codex は対象 issue の contract を短くまとめてユーザーに返す。最低限、次を 1 度は明示する。

- canonical flow
- old flow の扱い
- in-scope files / components / routes
- out-of-scope の境界
- done when
- not done if
- hard blockers

この summary に対してユーザーが違和感を示したら、assignment を止めて issue を更新してから再開する。

## Procedure

### 1. 親 Issue と sub-issue を確認する

```bash
gh issue view <parent_issue> --repo <owner>/<repo>
gh sub-issue list <parent_issue>
```

sub-issue を番号順に見て、最初の未対応 issue を決める。

未対応かどうかは次で判定する:

- Issue が open のまま
- まだ tmux 上の agent に予約されていない
- まだ PR 完了扱いになっていない

### 1.5 既存の merged issue を掃除する

命名規約:

- branch: `feat/<issue_number>`
- worktree dir basename: `<issue_number>`
- tmux window name: `<issue_number>`
- pane title: `issue-<issue_number>`


各実行の冒頭で、以前の issue 用に作られた専用 pane / window / worktree を確認する。

確認の目安:

```bash
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} #{window_name} #{pane_title} #{pane_current_path}'
git worktree list
gh pr list --repo <owner>/<repo> --search 'head:feat/<issue_number> is:merged' --json number,state,url
```

cleanup 条件:

- 対象が専用 issue window / pane であること
- 対応する `feat/<issue_number>` の PR が merge 済みであること
- 対応する worktree が clean であること
- `main` など通常 checkout ではないこと

cleanup 手順:

```bash
git -C <worktree_path> status --short
tmux kill-window -t <target_window>
git worktree remove <worktree_path>
```

- dirty worktree は消さない
- window / pane と issue の対応が曖昧なものは消さない
- 制約上 worktree ではなく一時 clone を使っている場合だけ、その clone directory を明示的に削除してよい

### 2. サイズラベルを確認する

対象 issue の size label を確認する。

- `S`: 割り当て可
- `M` / `L`: 割り当て禁止。ここで止めてユーザーに相談する
- ただし、ユーザーが「#<issue_number> をそのまま Claude に割り当ててよい」と明示した場合のみ、その issue に限って override 可

このルールは厳守する。先頭 issue が `M` / `L` のとき、後続の `S` に進めてはいけない。override がある場合でも、その指定 issue 以外には適用しない。

### 2.5 実装 contract を確認する

対象 issue の本文、必要なら直近コメントを読み、Implementation Contract Gate を満たしているか確認する。

不足している場合は:

- そのまま Claude に割り当てない
- ユーザーと不足点を詰める
- 合意した内容を sub-issue に反映する
- その後に assignment へ進む

特に route/flow 系の issue では、既存ページや既存 CTA が in scope かどうかを曖昧なままにしない。

### 3. 専用 worktree を用意する

既存の checkout を Claude に触らせない。issue ごとに専用 worktree を作る。
workspace root / `main/` / `.worktrees/<issue_number>/` の構成は `agent-workspace` の規約に従う。

例:

```bash
mkdir -p <workspace_root>/.worktrees
git -C <workspace_root>/main fetch origin
git -C <workspace_root>/main worktree add -b feat/<issue_number> <workspace_root>/.worktrees/<issue_number> origin/main
```

- すでに `feat/<issue_number>` の worktree（basename は `<issue_number>`） があるならそれを再利用してよい
- 既存 branch / remote branch がある場合は、その branch を正しく checkout した worktree を使う

### 4. Claude Code pane を探す

```bash
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index}  #{pane_current_command}  #{pane_title}'
```

優先順位:

1. すでに `issue-<issue_number>` に予約されている pane
2. なければ対象 worktree 用の新規 window（window 名は `<issue_number>`）

原則として、別 issue の会話が残っている既存 pane は再利用しない。

### 5. 必要なら Claude Code を起動する

Claude Code の起動コマンドが `claude` で通る前提なら、必ず `--dangerously-skip-permissions` を付けて起動する。例えば次を使う。

```bash
tmux new-window -n <issue_number> -c <worktree_path> 'claude --dangerously-skip-permissions'
```

起動コマンドが不明、または `claude` が見つからない場合は、ここで止めてユーザーに確認する。勝手に別コマンドを推測しない。

起動後は `tmux capture-pane -p -t <target> -S -80` を数回取り、出力が安定して操作待ちになったことを確認する。

workspace trust prompt が出る場合は、安全な自分の repo/worktree であることを確認した上で通す。

### 6. pane を issue に予約する

同じ issue を二重で振らないため、window 名は `<issue_number>`、pane title は `issue-<issue_number>` にそろえる。

例:

```bash
tmux rename-window -t <target_window> '<issue_number>'
tmux select-pane -t <target> -T 'issue-<issue_number>'
```

### 7. Claude Code に送る

複数行 prompt として送る。最低限、次の情報を含める:

- worktree path
- issue number / title / URL
- ブランチ名 `feat/{issue_number}`
- 親 Issue の番号 / title / URL
- `AGENTS.md` を守ること
- この issue 以外に着手しないこと
- issue に書かれた implementation contract を外さないこと
- `Done when` / `Not done if` / `Hard blockers` を success criteria として扱うこと
- 実装後は commit / push / PR をせず停止し、diff と検証結果を要約すること
- frontend route / island / hydration 変更では `build` 結果と chunk 警告の有無も要約すること
- ブロック時は停止して状況を要約すること

推奨テンプレート:

```text
You are working in <worktree_path>.

Take GitHub issue #<issue_number> in <owner>/<repo>.
Issue URL: <issue_url>
Branch: feat/<issue_number>
Parent issue: #<parent_issue_number>
Parent issue title: <parent_issue_title>
Parent issue URL: <parent_issue_url>

Rules:
- Follow AGENTS.md in the repo.
- Read the parent issue for context before making changes.
- Follow the implementation contract written in the sub-issue exactly.
- Work only on this issue. Do not take on other sub-issues from the parent.
- Inspect the relevant files before editing.
- Run relevant tests or verification.
- Treat the explicit success gates below as binding. Do not declare success just because code and docs were added.
- If the issue changes frontend routes, islands, hydration, or large client-side dependencies, run build and inspect bundle/chunk warnings before stopping.
- Do not commit, push, or create a pull request yet.
- When implementation is ready, stop and summarize:
  - changed files
  - verification commands run
  - any blockers or remaining uncertainty
- For frontend route / island / hydration work, also summarize:
  - whether build passed
  - whether chunk-size warnings appeared
  - the likely cause if a payload regressed
- If blocked, stop and summarize the blocker clearly.

Implementation contract to follow:
- <canonical flow>
- <old flow handling>
- <entrypoint / CTA behavior>
- <in-scope files>
- <out-of-scope boundary>

Done when:
- <explicit acceptance criteria that must be true before this issue is done>

Not done if:
- <conditions that keep the issue open even if code compiles>

Hard blockers:
- <missing secrets / dashboards / device verification / external setup that must be surfaced instead of guessed away>

Suggested start:
cd <worktree_path>
git fetch origin
git switch -c feat/<issue_number> || git switch feat/<issue_number>
gh issue view <parent_issue_number> --repo <owner>/<repo>
gh issue view <issue_number> --repo <owner>/<repo>
```

送信時は `tmux-sender` と同じルールを使う。

- 単一行なら `tmux send-keys`
- 複数行なら `load-buffer` -> `paste-buffer` -> `C-m`

### 8. Claude の実装後に diff review する

Claude が実装完了を報告したら、ここで初めて Codex が review を行う。

最低限:

```bash
git -C <worktree_path> status --short --branch
git -C <worktree_path> diff --stat origin/main...HEAD
git -C <worktree_path> diff --unified=80 origin/main...HEAD
```

- `review-diffs` スキルが使えるなら使う
- findings があれば、その内容を同じ Claude pane に返して修正させる
- 修正後に再 review する
- findings がなくなるまで loop する

### 9. review が clean なら Codex が commit / push / PR を行う

review が clean で、かつ push 権限がある場合は Codex が worktree で次を行ってよい。

```bash
git -C <worktree_path> add <files>
git -C <worktree_path> commit -m "<message>"
git -C <worktree_path> push -u origin feat/<issue_number>
```

必要なら、その後に GitHub PR を作成する。

Claude に commit / push / PR をさせるのは、明示的にその運用を選ぶ場合だけにする。

### 10. 割り当て結果を返す

ユーザーには少なくとも次を返す:

- 割り当てた issue 番号とタイトル
- size label
- 割り当て先 pane
- tmux window 名 `<issue_number>`
- ブランチ名 `feat/{issue_number}`
- worktree path

## If The Next Issue Is M Or L

割り当てず、次のように返す:

- 次に処理すべき issue 番号
- issue title
- size label (`M` or `L`)
- `S` ではないので Claude Code へはまだ渡さないこと

その上で、分割するか、別の進め方にするかをユーザーと相談する。

## Explicit Override For M Or L

ユーザーが特定 issue 番号を明示して override した場合は、その issue に限って割り当ててよい。

その場合の返答と prompt には次を明記する:

- これは通常ルールの例外であること
- override 対象 issue 番号
- review-before-push を通常より厳格に適用すること

Claude への prompt にも次の一文を入れる:

```text
This assignment is an explicit user-approved override for a non-S issue. Keep scope tight and stop for review before any commit/push/PR.
```

## Notes

- Claude の assignment 後も Codex が tmux pane を監視し、review と fix 依頼を繰り返して review clean まで回したい場合は `claude-tmux-review-loop` を使う。この skill はその loop の assignment / setup 側の依存先
- branch 名に `#` は使わない。必ず `feat/{issue_number}` にする
- size label は 1 issue につき 1 つを前提にする
- pane の予約ルールを守り、同じ issue の二重アサインを避ける
- Claude Code を新規起動する場合は、毎回 `claude --dangerously-skip-permissions` を使う
- reuse より isolation を優先する。worktree dir basename と tmux window 名は issue 番号そのものにそろえる
- 「Claude が実装した」ことと「review 済みで merge 可能」なことは別物として扱う
