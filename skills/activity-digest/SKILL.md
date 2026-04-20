---
name: activity-digest
description: その日の作業ログを横断して activity digest を作る。ユーザーが「activity digest」「今日何をしたかログから見たい」「作業ログをまとめたい」「証跡ベースで振り返りたい」などを求めたときに使う。特定プロジェクト名に依存せず、その日に触った作業対象を git、GitHub、Codex、Claude、tmux、shell snapshot から復元する。
---

# Activity Digest

その日の作業を、記憶ではなく証跡ベースでまとめる skill。

## When to use

- 「activity digest がほしい」
- 「今日何をしたかログから見たい」
- 「作業ログをまとめたい」
- 「証跡ベースで振り返りたい」
- 日次 / 週次レビューの前に、事実ベースの材料を集めたい

## Goal

以下を短時間で1枚にまとめる。

- その日にどの作業対象を触ったか
- どの repo / worktree / 非 git directory が主軸だったか
- どの issue / PR / GitHub activity があったか
- Codex / Claude / tmux で何を進めていたか
- shell レベルでどれくらい動いていたか

## Principles

- 特定 repo 名を前提にしない
- 記憶ではなく証跡を優先する
- まず広く集めて、必要なら個別ログに潜る
- digest は観測結果であり、解釈は `daily-review` 側で行う
- 「観測された活動」と「本人の記憶」のズレも情報として扱う

## Procedure

### 1. まず digest を生成する

以下の script を使う。

```bash
python3 /Users/yutaaoki/dotfiles/skills/activity-digest/scripts/activity_digest.py --date YYYY-MM-DD
```

必要なら repo を追加する。

```bash
python3 /Users/yutaaoki/dotfiles/skills/activity-digest/scripts/activity_digest.py \
  --date YYYY-MM-DD \
  --repo /path/to/repo1 \
  --repo /path/to/repo2
```

### 2. 出力を読む

digest では主に以下を見る。

- `Observed Targets`
  - 今日触ったと推定される directory
  - agent / tmux / explicit repo のどこから観測されたか
  - git repo / worktree か、非 git directory か
- `Repositories`
  - branch
  - 今日の commit
  - working tree の変化
  - reflog
  - GitHub issue / PR activity
  - observed paths
- `Codex activity`
  - どの cwd で何セッション動いていたか
  - どんな依頼が投げられていたか
- `Claude activity`
  - どの cwd でどんなタスクが走っていたか
- `Tmux activity`
  - どの pane が開いていたか
  - pane の cwd / command / title
- `Shell snapshots`
  - shell ベースの活動量

### 3. 次の用途につなげる

activity digest は最終成果物ではなく、次の材料として使う。

- 日次振り返り
- 週次レビュー
- 「今日は何が進んだか」の要約
- skill / checklist / automation の抽出

必要なら `daily-review` skill と組み合わせる。

### 4. 薄い digest のときの扱い

digest が薄いときは、「何もしていない」と断定しない。

- Codex / Claude の個別ログを深掘る
- 対象 repo の `git reflog` を見る
- 必要なら tmux や shell の追加証跡を手で取りにいく
- 先に観測結果を要約し、そのあとユーザーに抜けを聞く

## Notes

- 毎回すべてを深掘りしない
- digest はまず広く、必要なら個別ログに潜る
- `git` と `GitHub` を優先して読み、不明点がある日にだけ agent log を詳しく見る
- script が現在自動で見るのは `git / GitHub / Codex / Claude / tmux / shell snapshots`
- tmux は current state を使うので、基本的には `今日` の digest で使う
- 過去日付の digest では tmux は source of truth にしない
- browser、calendar などは将来候補であり、必要なら手で補う
