---
name: claude-tmux-review-loop
description: tmux 上の Claude Code に issue または明示タスクを割り当て、進捗を監視し、実装完了ごとに diff review を行い、findings があれば同じ pane に修正依頼を返して review clean になるまで繰り返すスキル。仕様不足や判断待ちが出たらユーザーに確認する。「Claude を監督して」「tmux の Claude を見ながらレビューを回して」「review clean になるまで Claude と往復して」などで使用。
allowed-tools: Bash(tmux:*), Bash(git:*), Bash(gh:*), Bash(rg:*), Bash(sed:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*)
---

# Claude tmux Review Loop

## Goal

Claude Code の実装を supervisor として監督し、`implement -> review -> fix` を review clean まで回す。

この skill 自体は task selection や review 手法の source of truth にはならない。既存 skill を組み合わせて使う。

## Related Skills

- `claude-tmux-pm`: GitHub sub-issue の選定、size label gate、worktree 準備、pane 予約、初回 assignment の source of truth
- `agent-workspace`: `main/` と `.worktrees/<issue_number>/` の layout の source of truth
- `tmux-sender`: 単一行 / 複数行 prompt を tmux pane に送る具体手順の source of truth
- `review-diffs`: diff review の推奨フロー。使えるなら優先して使う
- `codex-review`: `tmux capture-pane` の polling / idle 判定パターンの参考
- `github:create-pr` または `github:yeet`: review clean 後に publish したいときだけ使う。この skill の範囲外

## Guardrails

- 同じ issue / task は loop の完了まで同じ pane・同じ branch・同じ worktree で扱う
- current task が clean になる前に次の issue を取りに行かない
- この skill 自体は next issue の選定 source of truth ではない。どの task を start / resume するか曖昧なら推測せずユーザーに聞く
- target が明示されたあとは、routine な phase transition ごとに user confirmation を取り直さない。`watch -> review -> fix -> repeat` は自動で進める
- status 共有や commentary は handoff ではない。brief な進捗共有のあとも loop を継続する
- Claude が「完了」と言っても完了扱いにしない。review clean だけを done とみなす
- commit / push / PR はこの skill では行わない。必要なら clean 後に別 skill へ handoff する
- GitHub issue を Claude に振る場合の gate と worktree 規約は `claude-tmux-pm` と `agent-workspace` に従う
- review は issue contract に対して行う。単なる好みの refactor や style 指摘で loop を伸ばさない
- 初回 handoff が scope / suggested files だけで、`Done when` / `Not done if` / `Hard blockers` を Claude に渡していない場合、そのまま実装を続けさせない。必要なら assignment contract を補強してから進める
- findings を Claude に返すときは、重複と out-of-scope を落とした concrete な修正依頼だけを返す
- 仕様不足、product decision、矛盾した contract、実環境 blocker が出たら推測せずユーザーに聞く
- Claude が real question を出しているときは無理に review に進めず、その質問をユーザーに中継する

## Inputs

次のどれかが必要:

- 親 issue / sub-issue 番号
- repo と issue 番号
- 既存の tmux pane と worktree path
- 明示されたローカル task と作業ディレクトリ

どれもない場合は、どの task を supervise するかユーザーに確認する。

複数の plausible な task がある場合も同様に確認する。特に次は曖昧扱いにする。

- active pane / worktree はあるが、直前の会話で別 issue を next task として合意している
- 既存 task を review したいのか、次の issue を start したいのかが user request から読めない
- parent issue 配下に open issue が複数あり、どれを supervise するか特定できない

`active pane があるからそれを採用する` で進めてはいけない。start / resume target に 10% でも迷いがあるなら短く聞く。

## Procedure

### 1. Establish Loop Context

まず「この skill が扱う target は何か」を固定する。resolve 順序は次。

1. current turn で明示された issue / pane / worktree / task
2. 直前の会話で user と明示合意した specific issue / task
3. 明示された pane / worktree に紐づく single active loop context

2 と 3 が競合する場合、勝手にどちらかを選ばずユーザーに聞く。

「次の sub-issue を始めたい」「親 issue から次を選んで Claude に振りたい」という intent のときは、この skill で選定を始めず `claude-tmux-pm` を先に使う。`claude-tmux-review-loop` は、選定済みの lane を supervise する skill として扱う。

target が確定したら、それは Step 1 から Step 5 までを止まらず実行してよい authorization とみなす。routine な checkpoint ごとに「続けるか」を聞いてはいけない。

GitHub sub-issue を扱う場合は、まず `claude-tmux-pm` のルールで次を固める。

- 対象 issue
- size label gate
- worktree path
- branch `feat/<issue_number>`
- pane / window 予約
- initial implementation prompt

すでに pane / worktree が指定されている場合は、その pane が単一 task に対応していることを確認する。

最低限、次を loop context として固定する。

- task id / issue number
- repo
- worktree path
- branch
- tmux pane
- review range
- review contract

review contract には最低限次を含める。

- change goal
- canonical behavior after the change
- old behavior handling
- in-scope files / layers
- out-of-scope boundary
- done when
- not done if
- required verification
- hard blockers / external prerequisites

contract が曖昧なままなら Claude に投げ切らず、ここでユーザーに確認する。

### 2. Send Or Resume Claude Work

初回 assignment がまだなら `claude-tmux-pm` の template をベースに Claude へ送る。

初回 assignment がすでに送られていても、そこに `Done when` / `Not done if` / `Hard blockers` が無いなら、その lane は contract 不足として扱う。review 前に同じ pane へ補強 prompt を送り、成功条件を固定してから続ける。

修正ループ中なら、新しい task を作らず同じ pane に findings を返す。

送信方法は `tmux-sender` に従う。

- 単一行なら `tmux send-keys`
- 複数行なら `load-buffer -> paste-buffer -> C-m`

### 3. Watch The Pane

`tmux capture-pane -p -t <pane> -S -200` で baseline を取り、その後は 10-20 秒ごとに poll する。

polling は pure exponential backoff にしない。`tmux capture-pane` は比較的 cheap で、ready の検知が遅いほうが loop の体感を悪くしやすいから。

推奨 policy:

- prompt 送信直後は 3 秒ごとに poll する
- 最初の 30-60 秒、または output が変化し続けている間は 3-5 秒を維持する
- output が数回連続で不変になったら 10 秒へ伸ばす
- 最大でも 15-20 秒で cap する
- 新しい output が出たら 3 秒へ戻す
- Claude に follow-up を送った直後も 3 秒へ戻す

Claude がまだ作業中なら polling を続ける。次のどちらかになったら loop を分岐する。

#### Ready For Review

次のどれかを満たしたら review に進む。

- Claude が実装完了または review ready を明示した
- Claude が verification summary を出したあと idle prompt に戻った
- Claude が「ここまでで review してほしい」と言った

#### Needs User

次のどれかを満たしたらユーザー確認に切り替える。

- Claude が仕様質問や product decision を求めた
- Claude が missing credentials / broken environment / unresolved conflict を報告した
- pane が idle でも、最後の要約が blocker 報告で終わっている
- Claude process や pane 自体が死んでいて継続不能

#### User Status Check-In

ユーザーが loop の途中で短い status 確認をしてきた場合（例: 「まだ動いてる?」「止まるの?」「status?」）、それは stop condition ではない。

この場合は:

1. 1-2 文で current state を短く返す
2. その返答を handoff と解釈しない
3. 同じ loop context のまま Step 3 以降を継続する

status check-in のたびに新しい task selection や continuation confirmation を要求してはいけない。明示的な `stop` / `switch` / `retarget` があるときだけ止まる。

### 4. Review The Diff

`review-diffs` が使えるなら優先して使う。使わない場合でも最低限次は確認する。

```bash
git -C <worktree_path> status --short --branch
git -C <worktree_path> diff --stat origin/main...HEAD
git -C <worktree_path> diff --unified=80 origin/main...HEAD
```

review 結果は必ず次の 3 分類のどれかに落とす。

- `clean`
- `fix_required`
- `needs_user_decision`

`clean` 判定は「コード差分がもっともらしい」ではなく、review contract の `Done when` を満たし、`Not done if` のどれにも当たらないことを意味する。特に runtime / native / external-config issue では、docs で未実施の external setup を列挙しただけなら通常 `clean` ではない。

### 5. Branch On Review Result

#### clean

loop は終了。

ユーザーには少なくとも次を返す。

- changed files の要約
- 実行した verification の要約
- 残っている risk / test gap

publish は別 skill に回す。

#### fix_required

real finding だけを短く整理し、同じ pane に返す。

- severity 順
- duplicate を除去
- out-of-scope を除去
- 何を直せば close かを明確化
- contract の `Done when` / `Not done if` と直接結びつける

その後、すぐに Step 3 に戻る。

#### needs_user_decision

ユーザーに判断が必要な点を 1 つずつ明示して停止する。

必要なら Claude の質問を要約せず、そのまま短く転送してよい。

### 6. Feedback Prompt Template

```text
Review findings for the current task:

<ordered findings>

Re-check the original success gates for this task:
- Done when: <...>
- Not done if: <...>
- Hard blockers: <...>

Please fix only the findings above in <worktree_path>.
Keep scope tight to the current issue/task.
Re-run relevant verification after edits.
Do not commit, push, or create a PR.

When ready, stop and summarize:
- files changed in this iteration
- verification commands run
- any remaining uncertainty

If a finding cannot be resolved without a product or spec decision, stop and state the exact question.
```

issue 番号や contract がある場合は、先頭にそれを再掲してよい。ただし prompt を長くしすぎない。

### 7. Ask The User Instead Of Guessing

次の場合は loop を止めてユーザーに聞く。

- どの task を start / resume すべきか曖昧
- user が status を聞いているだけで、stop / switch / retarget を明示していない場合は止めない
- issue 本文と review findings が矛盾している
- fix すると canonical flow 自体が変わる
- 複数の妥当な修正案があり、どれを選ぶかで UX / API / route が変わる
- local secrets / env / external service が足りず再現不能
- 同じファイルにユーザー由来の未整理変更があり、ownership が曖昧

### 8. Stop Conditions

この skill は次のどれかで止まる。

- review clean
- ユーザー回答待ち
- hard blocker
- ユーザーが loop 停止を指示した

## Notes

- GitHub sub-issue を順番に取るルールはこの skill で再定義しない。`claude-tmux-pm` の規約を使う
- `review-loop` の default は「already-selected lane を監督する」であって、「next task を推定して開始する」ではない
- target が明示されたあとは、brief な status 返答をしても loop ownership は user に戻らない。stop condition までは agent 側で継続する
- ad-hoc なローカル task にも使ってよいが、その場合も `watch -> review -> fix -> repeat` の形は崩さない
- `done` は「review clean」の意味であり、「commit 済み」「PR 作成済み」の意味ではない
