---
name: evening-disclosure-script
description: 「きょうの日本株」夕方便と土曜の週間まとめの台本を作る。output/<日付>/data.json を読み、VOICEVOX で読み上げる台本 JSON を output/<日付>/script.json に書き出す。「台本を作って」「<日付>の台本」と言われたとき、または /evening-disclosure-script <日付> で起動されたときに使う。
---

# きょうの日本株 夕方便 台本作成

## 入力
- 引数: 対象日 `YYYY-MM-DD`(なければ output/ 配下の最新日付)
- `output/<日付>/data.json`(EDINET の提出書類の内訳・大量保有報告書・公開買付・臨時報告書、ドル円、国債金利)

## 手順
1. `output/<日付>/data.json` を読む。
2. このスキルの `references/style_guide.md`、`references/ng_words.md`、`references/script_schema.json` を読む。
3. `examples/` の見本を1つ読み、構成と文体を合わせる(数値・社名は見本ではなく data.json から取る)。
4. 台本を作成する。シーン構成は固定:
   01_opening → 02_overview → 03_holdings → 04_events → 05_usdjpy → 06_jgb → 07_ending
5. `output/<日付>/script.json` に書き出す(UTF-8、`script_schema.json` 準拠)。
6. `uv run python .claude/skills/evening-disclosure-script/scripts/validate.py output/<日付>` を実行する。
7. NG があれば指摘箇所だけを直し、6 に戻る(最大3回)。3回で通らなければ、最後の NG 一覧と理由を `output/<日付>/script_error.txt` に書き、script.json は削除せずに終了する。
8. OK になったら「OK」とだけ報告して終了する。

## 週間まとめ (data.json の `edition` が `"weekly"` のとき)
土曜に出す「今週のまとめ」。シーン構成・ルールは夕方便と同じで、対象の期間と言い方だけ変える。
- 対象は `period.start` から `period.end` の1週間(`period.days` が営業日)。件数はすべてこの期間の合計。
- 「きょうの」と言わず「今週の」「この1週間で」と言う。01_opening は「11月16日から11月20日の週間まとめです」のように期間を言う。
- 02_overview: 週の合計に加えて、`filings.daily` から提出の多かった日・少なかった日に触れてよい。
- 03_holdings: `large_holdings.top_issuers`(期間中に2件以上の報告が出た上場会社)があれば、それを中心に話す。なければ `items` から。
- 05_usdjpy / 06_jgb: `change` / `change_pt` は前週末(`prev_date`)からの変化。「前の週末から」「この1週間で」と言い、「前日比」とは言わない。
- title: 「きょうの日本株【週間まとめ】11/16〜11/20 大量保有報告書 180件｜公開買付・臨時報告書」のように、必ず「きょうの日本株【週間まとめ】開始日〜終了日」で始める。
- 07_ending: 「来週もよろしくお願いします」など週末向けの締めにする。

## 絶対ルール
- 数値・社名・日付は data.json にあるものだけを使う。計算・推測・記憶から数字を出さない。
- 投資推奨・価格予想・売買の示唆をしない。「買い」「売り」「おすすめ」「チャンス」「上がりそう」などは禁止(`ng_words.md`)。
- 株価・指数の動きには触れない(data.json にない)。
- 書類を読み上げるだけにしない。各シーンに「その書類は何を意味するか」「なぜ見られているか」の解説を1〜2セリフ入れる(`style_guide.md` の「解説」)。
- 個別の提出について、提出の理由や今後の展開は data.json からはわからない。書くなら「〜とみられます」「〜の可能性があります」と推測であることがわかる言い方にし、断定しない。
- 1セリフ(lines の1要素)は1文、45字以内(目安40字)。
- 免責文(「投資助言ではありません」など)は台本に入れない。エンディング画面と概要欄に自動で表示される。
- data.json の外の情報を調べない(Web検索・Web取得はしない)。src/ などのコードは編集しない。
