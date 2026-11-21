#!/bin/zsh
# launchd から平日の夕方に呼ばれる。PATH が最小限なので必要なものを明示する。
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LANG="ja_JP.UTF-8"
mkdir -p logs
LOG="logs/$(date +%F).log"

# VOICEVOX Engine は米国株チャンネル (finance_news_ch) の launchd が常駐させているものを共用する。
# 落ちていたら再起動を頼む (待機は tts ステップで最大60秒)
if ! curl -s -m 3 http://127.0.0.1:50021/version >/dev/null; then
  echo "$(date '+%F %T') VOICEVOX が応答しないため再起動します" >> "$LOG"
  launchctl kickstart -k "gui/$(id -u)/com.fukuchannel.usstock.voicevox" >> "$LOG" 2>&1 || true
fi

# 実行中にスリープしないようにする
exec caffeinate -i uv run python -m src.daily >> "$LOG" 2>&1
