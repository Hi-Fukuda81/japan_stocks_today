# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# きょうの日本株 / Japan Stocks Today

日本株の開示を読み解く動画を自動生成し、YouTube に投稿するパイプライン。
米国株チャンネル（`../finance_news_ch`、「米国株モーニングデータ」）と同じ構成・運用で、チャンネルとリポジトリは別。

## 現状

- 夕方便（大引け後の開示まとめ）と土曜の週間まとめの fetch → script → tts → visual → video → upload を実装済み。テストは通っている。
- 実データ（2026-11-16〜11-20 の週間まとめ）で fetch → tts → visual → video を動かした（`tmp/real/`）。そのときの台本は手書きで、`claude -p` での台本生成と YouTube への投稿は未実行。夕方便は実データでまだ動かしていない。
- launchd は未登録（`scripts/install_launchd.sh install` を実行していない）。まず手動で1本を最後まで作ってから登録する。
- 未実装: 朝便の自動実行（朝便と夕方便は同じ日付なので、いまの `output/DATE/` のままでは成果物が衝突する。置き場所を分けてから `src/daily.py` と launchd に組み込む。月曜の朝も金曜15時以降の分で出す、とユーザーが決めた）、TDnet・JPX のデータ（決算短信など）、公開買付の価格や期間（届出書の本文の取得が必要）、チャンネルアート、BGM（`assets/bgm.mp3` を置けば自動で使う）。

次のことは勝手に決めず、ユーザーに確認する: YouTube チャンネルと OAuth クライアントの使い方、公開のしかた（予約公開にするか）、VOICEVOX の声の割り当て、新しいデータソースの追加。

## チャンネル概要

- チャンネル名：きょうの日本株（英語名：Japan Stocks Today）。ハンドルは `@JapanStocksToday`（2026-11-22 に作成。米国株モーニングデータと同じ Google アカウントのブランドアカウント）
- YouTube API 用の Google Cloud プロジェクトは `japan-stocks-today`（このチャンネル専用。YouTube Data API v3 を有効化済み）。OAuth クライアント（デスクトップ）を作り、`--auth` 済み（2026-11-22）。チャンネル ID は `UC9MAS5rTzoS5Y-jZIsfiVig`。**OAuth はまだ「テスト中」で、リフレッシュトークンが7日で切れる。** 本番に切り替えるにはブランディングにホームページ・プライバシーポリシー・利用規約の URL が要る（finance_news_ch は Google サイトで用意した）。切り替えたら `--auth` をやり直す
- チャンネルは電話番号の確認がまだなので、カスタムサムネイルを設定できない（投稿は成功し、サムネイルだけ失敗する）。https://www.youtube.com/verify で確認する
- 2026-11-22 に週間まとめ（11/16〜11/20）を非公開で投稿して、upload まで通ることを確認した
- チャンネルアートは `uv run python -m src.branding.channel_art` で `assets/branding/`（banner.png、icon.png）に生成する。米国株モーニングデータと同じ構図で、強調色をオレンジにしてある。チャンネルへの設定はまだ
- 対象：日本株の個人投資家
- 主役は「公的な一次データ（開示・統計）の読み解き」。株価チャートを並べる動画にはしない
- 動画タイトルは `きょうの日本株【夕】11/20 ...`（朝便は `【朝】`）、週間まとめは `きょうの日本株【週間まとめ】11/16〜11/20 ...` で始める。validate.py が検査する
- 東証の休場日（祝日・12/31〜1/3）と日曜は配信しない。土曜は週間まとめだけ

| 便 | 公開時刻（JST） | 内容 | 状態 |
|---|---|---|---|
| 朝便（月〜金） | 8:00ごろ（寄り付き前） | 前営業日の15時以降に EDINET へ提出された書類、直近のドル円・国債金利 | fetch 以降は実装済み（`--edition morning`）。自動実行（`src/daily.py`・launchd）は未対応 |
| 夕方便（月〜金） | 16:00〜17:00（大引け後） | 当日15時より前に EDINET へ提出された公開買付・大量保有報告書（保有割合の動き）・臨時報告書、直近のドル円・国債金利 | 実装済み |
| 週間まとめ（土） | 土曜の朝（launchd は 9:00） | その週（月〜金）の公開買付・大量保有報告書・臨時報告書、ドル円・国債金利の前週末比 | 実装済み |

朝便と夕方便は `config.yaml` の `data.edinet.cutoff`（15:00）で分け、同じ書類を2回取り上げない（`fetch.period_for`）。週間まとめは時刻で絞らない。

セリフと画面では「朝便」「夕方便」と言わず「朝のまとめ」「夕方のまとめ」と言う（VOICEVOX が誤読する。ユーザーの指示）。「大株主」「日本株」の読みは `tts_replacements` で直している。

最後のシーン（`07_ending`）は終了画面で、`video.end_screen_sec`（20秒）以上になるよう最後のセリフの表示を延ばす。画面にはチャンネル登録とおすすめ動画2本の枠を空けてあり、要素そのものは YouTube Studio で置く（API では設定できない）。

## コマンド

```bash
uv sync                                                        # 依存関係 (Python 3.12 以上)
uv run python -m src.main --date 2026-11-20                    # 全ステップ (fetch → script → tts → visual → video → upload)
uv run python -m src.main --step visual --date 2026-11-20      # 1ステップだけ再実行
uv run python -m src.main --date 2026-11-21 --edition weekly   # 土曜の週間まとめ (直近の月〜金)
uv run python -m src.main --date 2026-11-20 --edition morning  # 朝便 (前営業日の15時以降の提出分)
uv run pytest                                                  # 全テスト
uv run pytest tests/test_validate.py::test_ng_word_detected    # 1テストだけ
uv run pytest --cov=src --cov=.claude/skills/evening-disclosure-script/scripts
uv run python .claude/skills/evening-disclosure-script/scripts/validate.py output/2026-11-20   # 台本の検証 (0=OK, 1=NG)
uv run python -m src.upload.youtube --auth                     # YouTube の OAuth 認証 (初回・期限切れ時)
uv run python -m src.daily                                     # 無人実行と同じ処理 (今日の日付。平日は夕方便、土曜は週間まとめ。ロック・休場スキップ・投稿済み判定・通知つき)
scripts/install_launchd.sh install|uninstall|status            # launchd (月〜金 16:00 の夕方便、土曜 9:00 の週間まとめ) の登録
```

- `--date` は動画の日付（JST）。夕方便はその日に EDINET へ提出された書類、週間まとめはその日以前で直近の週（月〜金の営業日）を対象にする。
- `--edition` を使うのは fetch だけ。以降のステップは data.json の `edition` と `period` に従う。
- `script` ステップは実際に `claude -p` を起動する（サブスク枠を消費する）。テストでは必ずモックにする。
- `upload` ステップは実際に YouTube に投稿する。`output/DATE/upload.json` があれば投稿済みとしてスキップする。
- 秘密情報（`.env`、`secrets/client_secret.json`、`secrets/youtube_token.json`）は git に入れない。`.env` に必要な値は `.env.example` を参照。`EDINET_API_KEY` は必須。
- launchd からの `claude -p` は通常ログインだと数日で切れるので、`.env` の `CLAUDE_CODE_OAUTH_TOKEN`（`claude setup-token` で発行）を使う。
- 実行ログは `logs/YYYY-MM-DD.log`。ユーザーに見せる試作は `tmp/`（git 管理外）に置く。
- 読みの確認: tts ステップが `output/DATE/audio/readings.txt` に各セリフの読み（カナ）を出す。誤読は、語の読みが一定なら `config.yaml` の `user_dict`、文脈で読みが変わる語なら `tts_replacements`（字幕は変えず読み上げ文だけ置換）で直す。

### finance_news_ch と共用しているもの

- **VOICEVOX Engine**: `~/apps/voicevox_engine/` を finance_news_ch 側の launchd（`com.fukuchannel.usstock.voicevox`、KeepAlive、`127.0.0.1:50021`）が常駐させている。このリポジトリからは登録しない。手で起動しない（ポートが競合する）。死活確認は `curl http://127.0.0.1:50021/version`。ユーザー辞書も共用なので、`user_dict` に入れた語は米国株側の読みにも効く。
- **コード**: `src/tts/`、`src/video/`、`src/upload/youtube.py`、`src/script/runner.py`、`src/notify.py`、`src/config.py`、`scripts/` は finance_news_ch からのコピー。共通の不具合を直すときは両方を直す。

## アーキテクチャ

### ステップ間はファイルだけで受け渡す

```
fetch  (src/data/fetch.py)        → data.json            (スキーマ: src/data/schema.json)
script (src/script/runner.py)     → script.json          (claude -p でスキルを起動)
tts    (src/tts/synthesize.py)    → audio/SS_LL.wav + audio/manifest.json (各セリフの秒数)
visual (src/visuals/render.py)    → img/<scene_id>.png (+ グラフは img/<scene_id>_anim/) + thumbnail.png
video  (src/video/compose.py)     → timeline.json, frames/, audio/narration.wav, video.mp4, description.txt
upload (src/upload/youtube.py)    → upload.json          (YouTube に非公開で投稿)
```

すべて `output/DATE/` 配下。パスは `src/config.py` の `DayPaths` に集約している。
各ステップは前のステップの成果物ファイルだけを入力にし、メモリ上の状態を共有しない。これにより任意のステップを単独で再実行できる。
`output/DATE/` は再審査請求に備えた制作過程の記録でもある（取得データと台本が残る）。mp4 と json は掃除の対象外。

### データ取得

| 用途 | ソース | モジュール | 備考 |
|---|---|---|---|
| 提出書類の一覧（大量保有・臨時報告書・公開買付など） | EDINET API v2 | `src/data/edinet.py` | 無料。API キーが必要 |
| 大量保有報告書の保有割合・保有目的 | EDINET API v2（書類本文の CSV、`type=5`） | `src/data/edinet.py`、`src/data/holdings.py` | 上場会社についての報告を1件ずつ取得する（週間で約400件、2分ほど） |
| 提出者名・証券コード | EDINET コード一覧（zip） | 同上 | `data/edinet_codes.csv` にキャッシュ（30日で更新、git 管理外） |
| ドル円（東京市場 17時時点） | 日銀 時系列統計データ検索サイト API | `src/data/boj.py` | 系列 `FXERD04` |
| 国債金利 | 財務省 国債金利情報 CSV | `src/data/mof.py` | 今月分で足りなければ全期間の CSV も読む。和暦の日付 |
| 決算短信・業績修正などの適時開示 | TDnet | 未実装 | 自動取得してよいか利用規約を確認してから実装する |
| 空売り比率、信用残、投資部門別売買状況 | JPX 公表データ | 未実装 | 利用条件を確認してから使う |

- `src/data/build.py` は取得した生データから data.json の各節を組み立てる純粋関数だけを置く。通信は各ソースのモジュールに閉じる。
- ドル円と国債金利は公表が遅れるので、夕方の時点では前営業日以前の値になる。data.json の `usdjpy.date`・`jgb.date` と `notes` に実際の日付が入り、台本も図もその日付を言う。
- **主役は「どの会社で何が変わったか」。件数は主役にしない**（ユーザーの指示。件数を並べた試作は「誰も見ない」と却下された）。タイトル画面・サムネイル・台本の書き出しは、保有割合がいちばん大きく動いた会社にする。
- 大量保有・臨時報告書の一覧（`items`）は上場会社に関するものだけ。件数（`count`）は全体。
- 大量保有の `items` は、同じ提出者・発行会社なら最新の1件にしたうえで、新規（保有割合の大きい順）・増加・減少（動いた幅の大きい順）から順番に取る（`holdings.notable`）。保有割合は提出者と共同保有者の合計で、新株予約権などの潜在株式を含む。
- 臨時報告書の `items` は1社1件で、代表取締役・主要株主・親会社の異動などを先に出す（`build.REASON_PRIORITY`）。
- 公開買付は、買付者と対象会社が同じなら自社株の買付（`self_tender`）。
- 社名は `build.short_name` で「株式会社」を外し、全角の英数字を半角にしている。英字の社名を VOICEVOX が1文字ずつ読むときは `tts_replacements` に足す。
- 臨時報告書の提出事由は、開示府令19条2項の号を `build.REPORT_REASONS` で日本語にしている。表にない号の書類は一覧に出さない。対応表は書類の本文とは突き合わせていない。
- `data.reference` は制度上の基準値（大量保有報告書の5%など）。台本で制度を説明するときの数値も照合対象にするために data.json に入れている。
- 営業日判定は `src/data/calendar_jp.py`（`jpholiday` + 年末年始）。

### 週間まとめ

夕方便と同じ data.json の形・シーン構成・validate・図表を使い、対象期間だけが違う（`edition: "weekly"`、`period.days` がその週の営業日）。

- 提出書類は営業日ごとに EDINET を呼んで合算する。`large_holdings.items` はその週で保有割合の動きが大きかったもの、`top_issuers` は期間中2件以上の報告が出た上場会社（夕方便でも同じキーがあるが、中身は1日分）。
- ドル円・国債金利の `change` は、週の初日より前でいちばん新しい値（前週末）との差。図の表記は `theme.change_word` で「前週末比」に切り替わる。
- 日銀・財務省の公表は遅いので、土曜の朝の時点では週の後半の値がまだない。`notes` と図にデータの日付が出る。その週の値が1日分もなければ fetch は失敗する。
- 台本の言い方の違いはスキルの SKILL.md「週間まとめ」にある。

### データに関するルール

- **株価・指数の時系列データは使わない。** 無料で動画に使ってよい入手先がないため。指数は事実を一言触れる程度にとどめ、チャートは描かない（現状の data.json には指数の値がないので、台本でも触れない）。
- **規約で禁止されているサイトはスクレイピングしない**（Yahoo!ファイナンス、株探、まとめサイトなど）。
- 新しいデータソースを追加するときは、先に利用規約（自動取得・商用利用・動画への転載）を確認し、上の表に追記する。`config.yaml` の `channel.data_credits`（概要欄とエンディングに出る出典）にも足す。

### シーン構成は固定

`01_opening → 02_tender（公開買付）→ 03_holdings（大量保有）→ 04_events（臨時報告書）→ 05_usdjpy → 06_jgb → 07_ending`

シーン ID と visual ID（`title` / `tender_offers` / `holdings_table` / `events_list` / `usdjpy_line` / `jgb_yields` / `ending`）は、スキルの `script_schema.json`、`validate.py` の `SCENES`、`src/visuals/render.py` の描画関数の対応、`src/upload/description.py` の目次ラベルが共有している。変えるときは4か所を揃える。

### 決定的な Python と Claude Code の役割分担

- データ取得・音声・図表・動画・投稿は Python で決定的に作る。文章を作るのは台本スキル（`.claude/skills/evening-disclosure-script/`）だけ。
- `src/script/runner.py` は `claude -p "/evening-disclosure-script DATE"` を、読める場所と書ける場所を `output/` とスキルに絞って起動する（Web 取得・検索は禁止）。プロンプトは Python 側に持たない。
- スキルが OK と報告しても、runner が最後に `validate.py` を再実行する（最終ゲート）。
- `validate.py` は標準ライブラリだけで動き、台本の単位付きの数値（件・%・ポイント・円・銭）と日付がすべて data.json にあるか、前日比の向き（上昇/低下、円安/円高）が合っているか、NG ワード（`references/ng_words.md`）がないか、シーン構成・字数・タイトルの書き出しを検査する。単位ごとに照合してよいフィールドは `UNIT_FILTERS` で絞っている。data.json に新しい数値を足すときは、どの単位で照合されるかをここで確認する。

### 映像と音声の同期

`src/video/subtitles.py` の `build_timeline` が manifest の秒数から各セリフの表示区間を決め、同じタイムラインで (1) 無音を挟んだ narration.wav（`src/video/audio.py`）と (2) ffconcat の画像表示時間を作る。ずれが出たらここを見る。
グラフのシーン（`render.ANIMATED`）は progress 0〜1 で途中のコマも描け、`compose.plan_frames` がシーン冒頭のセリフの表示時間の中にコマを差し込む。各セリフの表示時間の合計は変えないので尺は伸びない。
この環境の ffmpeg には libass がないため、字幕は PIL で各フレーム画像に焼き込んでいる。図表は画面下 17%（`theme.SUBTITLE_BAND_RATIO`）を字幕用に空けて描く。

## 台本・動画のコンプライアンス（必須）

スキルの台本だけでなく、概要欄・サムネイル・テンプレ文言を作るときも守る。

- 投資の推奨（「買い」「売り」「今が買い時」など）・価格予想・売買の示唆をしない。事実と、その読み解きに限る。
- 銘柄名・数値は data.json にあるものだけを使う。計算・推測・記憶から数字を出さない。
- 推測は推測とわかる言い方にする（「〜とみられます」など）。
- 免責文は読み上げない。エンディング画面に薄い色で小さく表示し、概要欄にも入れる（どちらも `config.yaml` の `channel.disclaimer` から自動）。
- 概要欄には `VOICEVOX:<キャラ名>` のクレジットとデータ出典が自動で入る。

### 量産型コンテンツと判定されないための方針

YouTube は2025年7月から「非本物コンテンツ（inauthentic content）」として、テンプレート的な量産動画の収益化を厳しくしている。

- 開示を読み上げるだけにしない。毎回「なぜ重要か」「何を意味するか」の解説を入れる（スキルの `style_guide.md`「解説」）。
- **人が台本と動画を確認してから公開する。** そのため `config.yaml` の `upload.privacy` は `private`、`publish_at` は `null`（予約公開しない）にしてある。投稿後の通知を見て、YouTube Studio で確認・修正してから公開する。finance_news_ch は予約公開だが、こちらは変えない。
- 台本の型を複数用意し、動画ごとの構成や言い回しが似すぎないようにする（現状はシーン構成が1種類。型を増やすのは今後の課題）。
- 再審査請求に備えて、制作過程（`output/DATE/` の data.json と script.json、台本の修正履歴）を残しておく。

## VOICEVOX

- 声は曜日ごとの日替わり（`config.yaml` の `voicevox.voices`、`src/tts/voices.py` の `pick_voice` が動画の日付の曜日で選ぶ）。finance_news_ch の割り当てを平日に当てはめた仮の設定で、ユーザーの確認はまだ。入れ替えはユーザーに確認する。
- 使うキャラクターの利用規約を確認する。No.7 は個人の非商用（配信収入は可）、青山龍星は個人なら可（企業が関わる場合は事前確認が必要）。
- キャラクター名をチャンネル名やサムネイルで使う場合は、そのキャラの規約で許されているか確認する。

## macOS / launchd 固有の注意

- 実行環境は自宅の MacBook。launchd はユーザーエージェント（`~/Library/LaunchAgents`）にする。キーチェーンにある Claude Code の認証情報を読むため。LaunchDaemon にはしない。
- launchd 実行時は PATH が最小限になるため、`scripts/run_daily.sh` で `/opt/homebrew/bin` などを明示している。
- スリープしていると動かないので、`pmset repeat wakeorpoweron` で起動時刻の少し前に自動で起こす（finance_news_ch の朝 6:30 と時刻が別なので、設定を上書きしないよう注意する。`pmset repeat` は1つしか持てない）。
- パイプラインは `caffeinate -i` で包む。ロックファイル `output/.lock` で多重起動を防ぐ。
- ffmpeg のエンコードは `h264_videotoolbox`、使えなければ `libx264 -preset veryfast`。1920x1080 / 30fps / AAC。
- YouTube Data API のアップロードは1本あたり1,600ユニット、デフォルト上限は1日10,000ユニット。

## テストの方針

- テストでは Claude Code・VOICEVOX・EDINET・日銀・財務省・YouTube を実際に呼ばない（すべてモック / フェイク）。
- `tests/conftest.py` の `validate_mod` fixture で validate.py をモジュールとして読み込み、`day_dir` fixture でスキルの見本の data/script を置いた日付ディレクトリを作る。見本を変えると多くのテストの期待値に影響する。
- 見本データの提出書類は架空の社名にしてある（公開リポジトリなので、実在の会社について架空の開示を書かない）。
