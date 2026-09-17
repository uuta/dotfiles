---
name: tmux-sender
description: tmux の別ペインにコマンドを送信する。「ペインで実行して」「tmuxで送信」などのリクエストで使用。
allowed-tools: Bash(tmux:*)
---

# tmux コマンド送信

送信対象と操作の依頼が明示されている場合に使う。対象 pane のプロセスと割り当てを確認し、正確な `%pane_id` に送る。window 名や番号だけで対象を決めない。

## Agent への prompt

改行の有無にかかわらず、prompt を一意な一時ファイルに保存し、専用の名前付き buffer で配送する。並行実行間で共有される `/tmp/tmux_send.txt` やデフォルト buffer を使わない。

以下の `prompt_file` は今回作成したファイル、`target_pane` は確認済み pane。シェルの quoted heredoc またはファイル書き込み API で prompt を保存し、本文をシェルコードへ展開しない。

```bash
rtk proxy tmux load-buffer -b "$prompt_buffer" "$prompt_file"
rtk proxy tmux paste-buffer -b "$prompt_buffer" -t "$target_pane" -d
rtk proxy sleep 0.5
rtk proxy tmux send-keys -t "$target_pane" C-m
rtk proxy tmux capture-pane -p -t "$target_pane" -S -80
```

`prompt_buffer` は一時ファイルの basename など、今回の送信で一意な名前にする。capture で入力が提出され、処理が始まったことを確認する。未提出が確認できた場合だけ入力終端や Enter を補正し、再確認する。処理中の prompt を丸ごと再送しない。完了・中止後は自分が作った一時ファイルと残存 buffer を片付ける。

## Shell pane へのコマンド

対話 agent ではなく shell prompt と確認できた pane に短いコマンドを送る場合は、`send-keys -l` で本文、続けて `C-m` を送ってよい。複数行は上の buffer 手順を使う。送信後は同じ pane の出力を確認する。
