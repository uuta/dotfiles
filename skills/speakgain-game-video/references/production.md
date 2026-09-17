# Skyrim × SpeakGain 動画制作手順

最終更新：2026-09-09。次回の制作はこのファイルから開始する。手順の正本はdotfiles内のこのファイル、メディアの保存先はGoogle Drive。

## 保存先とパスの解決

- 手順書：`/Users/yutaaoki/dotfiles/skills/speakgain-game-video/references/production.md`
- Google DriveのContentルート：`/Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content`
- 既存のSkyrim素材ルート（以下「素材ルート」）：`/Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim`
- 本文中の `clips/20260908/...` は、この素材ルートからの相対パス。手順書の置き場所から解決しない。
- 今回は参照切れを避けるため、既存61ファイルを階層ごと移したコピーを素材庫にした。過去の完成版もこの一式に残している。次回以降の投稿成果物は `Content/projects/<投稿ID>/` に保存し、素材庫の部品を参照する。
- 現在の投稿成果物：`Content/projects/2026-09-09-skyrim-01/final.mp4`（Contentルート基準）。
- 別MacではDriveのマウント先が変わり得る。ユーザー指定のContentルートで相対パスを解決し直す。下のクリック用リンクはこのMac向け。
- 編集時は必要な素材がローカルで読み取れることを確認する。一時ファイルは同期対象外の作業フォルダで扱い、検証済み成果物だけ保存先へコピーする。
- 旧 `/Users/yutaaoki/Movies/Hub/Projects/skyrim` は削除せず移行時点の控えとして保持。以後の正本として編集しない。
- `/Users/yutaaoki/SpeakGain/downloads/` 内の元動画、元の `0903.mov` は今回のコピー対象外。切り抜き・導入音声は素材庫にあるが、元動画からの再抽出には旧ソースも必要。manifestのsource絶対パスは出典履歴として残し、取得可能と決めつけない。
- コピー直後に61ファイル（61,541,149 bytes）全てのSHA-256一致と投稿用finalの一致を確認。Drive内の案内文はその後更新した。クラウドへのアップロード完了は未検証。控えを消す判断は別途行う。


## 確定した方針

- ゲーム切り抜き、SpeakGainスクショ、読み上げ音声、導入画像・音楽を独立した部品として保存し、再利用する。
- 基本は3フレーズ。5フレーズなども実験できる。完成動画の秒数を先に固定しない。
- 構成は「導入 → ゲーム1 → SpeakGain1 → ゲーム2 → SpeakGain2 → …」。ゲームの元音声は残す。
- SpeakGain画面に付ける声は採用済みの **Weathered Warrior**。新しいフレーズだけ生成する。既存の承認済み音声を再生成しない。
- 今回変更したのは動画の音声。SpeakGainアプリのTTSは未変更。アプリ移行は別件の [Issue #233](https://github.com/uuta/SpeakGain/issues/233)。この動画で使った声が現行アプリに実装済みとは案内しない。
- 新しい元動画、20時間版などは素材元の追加として扱う。既存の部品や声を作り直す必要はない。

## 現在の完成版と承認状況

- [完成動画 v6](</Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim/clips/20260908/skyrim-speakgain-v6-weathered-warrior.mp4>)：37.866667秒、1080×1920、30fps。
- 2026-09-09にユーザーがVoice Design候補3を採用。3フレーズへの利用、結合版を承認済み。
- Dropbox納品済み：`/Users/yutaaoki/Library/CloudStorage/Dropbox/20260909/skyrim-speakgain-v6-weathered-warrior.mp4`
- ローカル版・Dropbox版のSHA-256：`17139c893502a32c9117f38f8f2138f3552b5f0e9c36a13686baaf08205cfada`
- 制作上の成功例であり、投稿後の成果を検証済みという意味ではない。

## 1. 元動画から候補を探す

まずダウンロード済み素材を調べ、同じファイルを再ダウンロードしない。

採用基準：

- 短くても、難しい単語・聞き慣れない言い回し・実際に口にしたくなる表現がある。
- Skyrimの有名なmeme台詞も優先候補。知名度が不明なら確認し、推測を確定扱いしない。
- 基本3本は、人物・場所・場面がそれぞれ違うものを選ぶ。
- 台詞が単独でも成立する。実況の被り、聞き取れない箇所、前後の文脈依存を確認する。
- 台詞全体と字幕が収まる範囲を選ぶ。短くするために語尾を切らない。

字幕・文字起こしは候補探しに使えるが、誤認識があるため最終的に元映像・発話と照合する。原文、採用理由、人物・場面、元動画ID、開始・終了位置を残す。5本に増やすときも同じ基準を使う。

### 20時間版などを追加する場合

- URL、映像品質、実況の有無、字幕の有無を確認する。
- ダウンロード前に、選択フォーマットの容量を取得できれば提示する。不明なら推定と明記する。20時間という長さだけで容量を断定しない。
- テザリング中は、容量と実行タイミングについてユーザー確認を取る。長尺動画を無断でダウンロードしない。
- 字幕・チャプターなどで候補位置を絞り、必要に応じてその周辺を確認する。
- 入手・加工できることと投稿への利用許諾は別。元動画・音楽の利用条件を確認する。今回の第三者動画の再利用許諾と導入曲の曲名・権利は未確認。

## 2. ゲーム切り抜きを独立保存する

- 元動画を変更せず、採用シーンごとに1ファイル書き出す。
- 最初に元画角の切り抜きを保存する。その後、投稿用の拡大版を別ファイルにする。
- 字幕の出始め、全文表示、消える直前、シーン境界を確認する。素材に余白がない場合は記録する。
- 出典、原文、元動画上の開始・終了秒、切り抜きファイル名をmanifestに残す。
- 完成動画だけから素材を取り直さず、以後も独立部品を正本として使う。

今回の出典と位置は [manifest-meme-batch.json](</Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim/clips/20260908/manifest-meme-batch.json>) に記録済み。

## 3. 同じ英文をSpeakGainに登録し、スクショを保存する

- 使用する端末・シミュレーターとログイン状態を画面で確認する。別の端末を見て未ログインと判断しない。
- 登録済みカードがあれば再利用する。新規登録では、採用原文と同じフレーズを登録する。
- カード生成・説明生成が完了してからKnowledge画面を開く。
- 原文、意味、説明が正しいカードであること、全文が画面内にあることを確認してPNGで保存する。
- スクショはTTSと別部品にする。音声の変更だけで画面を撮り直さない。
- 動きが必要な場合だけ別途録画する。今回の画面は実機能のスクショを静止表示したもので、再生ボタンのアニメーションなどは含まない。
- 最終画面の文字を、投稿時の表示サイズで読めるか確認する。

## 4. Weathered Warriorで必要な音声だけ生成する

| 項目 | 採用設定 |
| --- | --- |
| 声の名前 | Weathered Warrior |
| Voice ID | `pvYicZWcwdDCz5V4NMDA` |
| TTSモデル | `eleven_v3` |
| voice_settings | `{"stability": 0.5}`（他の項目は未指定） |
| 出力 | `mp3_44100_128` |
| 生成文 | 採用した台詞の原文のみ |
| 音声タグ | 今回は使用なし |
| 認証ファイル | `/Users/yutaaoki/.config/elevenlabs/.env` の `ELEVENLABS_API_KEY` |

実際に成功したリクエスト形：

```text
POST https://api.elevenlabs.io/v1/text-to-speech/pvYicZWcwdDCz5V4NMDA?output_format=mp3_44100_128
Headers: xi-api-key（ローカル環境から読み込む）, Content-Type: application/json
Body: {"text":"採用原文","model_id":"eleven_v3","voice_settings":{"stability":0.5}}
```

運用上の注意：

- まず同じ原文・声・モデル・設定で承認済みのMP3がないか探す。あればそれを使う。
- 初回生成はフレーズごとに1回。失敗時は状態を記録し、タイムアウトなど結果不明の場合に盲目的に再送しない。
- キーを文書・コマンド引数・ログ・チャットに書かない。認証情報をGoogle Drive・Dropboxにコピーしない。
- 権限・残高不足時に勝手な入金、プラン変更、別サービスへの切り替えをしない。
- HTTP成功を確認してから音声を保存し、モデル・設定・原文・リクエストIDを記録する。
- character-costヘッダーをドル料金と解釈しない。費用が必要なら当日の料金と実際の利用明細を別途確認する。
- 同じ設定で生成し直しても、演技・長さまで同一とは限らない。承認済みMP3が正本。
- 試聴で台本外発話、欠け、声質を確認する。人間の耳で確認していなければ、確認したとは記録しない。
- Voice Designを毎回実行しない。声を変える必要があるときだけ、新候補を試聴・選択して保存する。

今回の3本の設定・リクエスト記録：[warrior-phrases-v1.md](</Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim/clips/20260908/elevenlabs/warrior-phrases-v1.md>)。声そのものの設計履歴：[warrior-design-v1.md](</Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim/clips/20260908/elevenlabs/warrior-design-v1.md>)。

## 5. 投稿に使う部品と順番を決める

1フレーズを以下の組として扱う：

```text
フレーズID
├── 原文・出典・採用理由
├── ゲーム切り抜き（元画角）
├── 投稿用の拡大版
├── SpeakGainスクショ
└── 承認済みWeathered Warrior音声
```

投稿ごとに、使用するフレーズIDの順序、導入部品、出力先を記録する。3本か5本かで完成尺が変わるだけで、別の編集方式にはしない。

### 今回の再利用可能な部品

以下は `clips/20260908/` を基準とした相対パス。

| ID | 元画角ゲーム | 拡大版ゲーム | SpeakGainスクショ | 採用音声 |
| --- | --- | --- | --- | --- |
| 04-nazeem | `04-nazeem-cloud-district.mp4` | `game-zoom/04-nazeem-cloud-district-vertical.mp4` | `speakgain/raw/04-nazeem-knowledge.png` | `elevenlabs/04-nazeem-warrior-v1.mp3` |
| 05-ulfberth | `05-ulfberth-deal-some-damage.mp4` | `game-zoom/05-ulfberth-deal-some-damage-vertical.mp4` | `speakgain/raw/05-ulfberth-knowledge.png` | `elevenlabs/05-ulfberth-warrior-v1.mp3` |
| 06-isran | `06-isran-sleep-is-for-the-weak.mp4` | `game-zoom/06-isran-sleep-is-for-the-weak-vertical.mp4` | `speakgain/raw/06-isran-knowledge.png` | `elevenlabs/06-isran-warrior-v1.mp3` |

導入画像：`intro/skyrim-title-v1.png`。導入音声：`intro/reference-opening-5s.wav`。合成済み導入：`intro/skyrim-intro-5s-audio.mp4`。

旧 `speakgain/*-speakgain.mp4` にはAzure音声が入っている。Weathered Warrior採用版としてそのまま使わない。

## 6. 長さを素材から決めて結合する

### 基準

- 出力：1080×1920、30fps、H.264、yuv420p、AAC、48kHzステレオ、faststart。
- 今回の圧縮設定：libx264、CRF 18、preset fast、AAC 192 kbps。
- 導入は今回承認された5秒版を使う。2秒版は短すぎたため不採用。新しい導入は別の実験として扱う。
- ゲームは可能な限り大きく表示するが、台詞の字幕全文が切れない画角を優先する。全シーン一律のクロップにはしない。
- スクショはアスペクト比を維持し、文字やUIを切らずに1080×1920へ収める。今回の1080×2400画面なら864×1920に縮小し左右余白108pxずつが基準。
- ゲームの元音声とBGMは保持。SpeakGain側だけ採用音声を使い、旧Azure音声を混ぜない。

### 尺の計算

```text
FPS = 30
SpeakGain表示フレーム数 = ceil((音声の長さ + 0.35秒 + 0.50秒) × FPS)
SpeakGain表示秒数 = 表示フレーム数 ÷ FPS
完成尺 = 導入尺 + Σ(各ゲーム切り抜き尺 + 各SpeakGain表示尺)
```

音声はffprobeなどで実測し、長さを手で推測しない。画面を出して0.35秒後に発話を開始し、語尾の後に約0.5秒以上の余白を残す。音声を目標尺に押し込むための速度変更・途中カットはしない。

今回の新しい声は全て-3dBで使用。ゲームとの音量差を確認し、次回も無条件に同じ減衰が最適とは判断しない。生成された声へのピッチ変更や追加の演技加工は今回していない。

ゲーム素材ごとの拡大値：[game-zoom/README.md](</Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim/clips/20260908/game-zoom/README.md>)。今回のタイムライン・検証：[video-v6.md](</Users/yutaaoki/Library/CloudStorage/GoogleDrive-nightrage.metal66@gmail.com/My Drive/SpeakGain/Content/library/skyrim/clips/20260908/elevenlabs/video-v6.md>)。

### 再構築と自動化の現状

- **上記は次回制作の手順。部品一覧だけで動く汎用結合スクリプトはまだ未実装。**
- 今回のv6は、既存v5の画面・ゲーム音声を再利用して音声を差し替えた。`assemble-v6.fffilter` の固定フレーム数を、新しい投稿へそのまま流用しない。
- 次回以降は、独立した部品から新しい順序と尺を計算する。v5への依存は今回の再構築用に限定する。
- 編集だけのやり直しでTTS APIやVoice Designを呼ばない。

## 7. 検証して書き出す

- [ ] 3組または選択した組数が、指定した順序で入っている。
- [ ] ゲーム台詞、スクショ原文、生成音声が同じフレーズである。
- [ ] ゲーム字幕とスクショの原文が切れずに見える。
- [ ] 導入音楽や台詞が不自然な位置で切れていない。
- [ ] 語頭・語尾が欠けず、旧Azure音声や二重音声が混ざっていない。
- [ ] 音声が長い場合に画面が先に切り替わらない。短い場合に無駄な長い静止時間が残っていない。
- [ ] ffprobeでサイズ、fps、音声仕様、音声と映像の長さを確認する。
- [ ] 全編デコードが通る。各場面の開始・中間・終了付近を視覚確認する。
- [ ] ユーザーが完成版を試聴確認する。波形一致・デコード確認を聴感確認の代わりにしない。
- [ ] 承認済み素材と完成動画を上書きせず、新バージョン名で保存する。
- [ ] 指定された納品先へ完成動画をコピーし、ハッシュでコピー一致を確認する。Google Drive・Dropboxのクラウド同期完了は別事項。

## 8. 投稿文と実験記録

今回承認されたdescription：

```text
Skyrim dialogue hits different when you actually say it out loud. 🗣️⚔️
Which line lives rent-free in your head?

Practicing with SpeakGain.

#Skyrim #SkyrimMemes #GamingEnglish #LearnEnglish #SpeakGain
```

TikTok上でタイトルを冒頭に表示する編集も行っているため、動画内の導入との重複を投稿画面で確認する。尺、フレーズ数、順序、導入、descriptionを記録し、3本版と5本版などの比較条件を残す。再生数だけでなく取得できる視聴維持・プロフィール遷移なども見る。投稿や自動投稿は別途ユーザーの指示があるときに行う。

## 次回の依頼例

> この手順でSkyrim動画を1本作って。既存素材から別場面を3つ選び、声はWeathered Warrior。音声が既にあるフレーズは再生成しない。新しい元動画のダウンロードはまだしない。完成したら試聴させて。

## 過去ログの読み方

`clips/20260908/` 内のREADMEや各attempt記録はその時点の作業履歴。旧資料の「未実施」「試聴待ち」は現在の全体状況を表さない。現在の採用方針と承認状況は本書を入口とし、個別の技術値はリンク先の記録で確認する。
