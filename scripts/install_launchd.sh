#!/bin/zsh
# 使い方: scripts/install_launchd.sh install | uninstall | status
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
# VOICEVOX は finance_news_ch 側の com.fukuchannel.usstock.voicevox を共用するので、ここでは登録しない
LABELS=(com.fukuchannel.jpstock.evening)

case "${1:-}" in
  install)
    mkdir -p "$AGENTS" "$REPO/logs"
    chmod +x "$REPO/scripts/run_daily.sh"
    for label in $LABELS; do
      dest="$AGENTS/$label.plist"
      launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
      # bootout は非同期なので、外れきるまで待ってから bootstrap する (直後だと Input/output error になる)
      for _ in {1..20}; do launchctl print "$DOMAIN/$label" >/dev/null 2>&1 || break; sleep 0.5; done
      sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" "$REPO/scripts/launchd/$label.plist" > "$dest"
      plutil -lint "$dest" >/dev/null
      launchctl bootstrap "$DOMAIN" "$dest"
      echo "installed: $label"
    done
    ;;
  uninstall)
    for label in $LABELS; do
      launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
      rm -f "$AGENTS/$label.plist"
      echo "removed: $label"
    done
    ;;
  status)
    for label in $LABELS; do
      launchctl print "$DOMAIN/$label" 2>/dev/null | grep -E "state =|last exit code" | sed "s/^/$label: /" || echo "$label: not loaded"
    done
    ;;
  *)
    echo "usage: $0 install|uninstall|status" >&2
    exit 2
    ;;
esac
