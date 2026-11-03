#!/bin/bash
# Installs or updates Grabzy.CC on macOS from Grabzy-CC's releases.
#
#   bash grabzy-update.sh              install or update now
#   bash grabzy-update.sh --schedule   also check at login and every 6 hours
#   bash grabzy-update.sh --unschedule
#
# The disk image is checked against the SHA-256 GitHub records for it. While
# the browser is open nothing is replaced; the next check installs it.

set -euo pipefail

REPO="Grabzy-CC/grabzy-chromium-macos"
APP="/Applications/Chromium.app"   # the bundle keeps Chromium's name, see README
HOME_DIR="$HOME/Library/Application Support/Grabzy.CC"
STAMP="$HOME_DIR/installed-release.txt"
LABEL="cc.grabzy.update"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME_DIR"

log() { printf '%s %s\n' "$(date -u '+%F %TZ')" "$*" | tee -a "$HOME_DIR/update.log"; }

case "${1:-}" in
  --unschedule)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    log "scheduled check removed"
    exit 0 ;;
  --schedule)
    self="$HOME_DIR/grabzy-update.sh"
    [ "$0" = "$self" ] || cp "$0" "$self"
    chmod +x "$self"
    mkdir -p "$(dirname "$PLIST")"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$self</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>21600</integer>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    log "scheduled check installed" ;;
esac

case "$(uname -m)" in
  arm64) arch=arm64 ;;
  *) arch=x86_64 ;;
esac

json=$(curl -fsSL -H "User-Agent: grabzy-update" "https://api.github.com/repos/$REPO/releases/latest")
# JavaScript for Automation ships with macOS; python3 may not be installed.
field() { osascript -l JavaScript -e "function run(a) { const r = JSON.parse(a[0]); $1 }" "$json"; }
tag=$(field 'return r.tag_name')
current=$(cat "$STAMP" 2>/dev/null || true)
if [ "$tag" = "$current" ] && [ -d "$APP" ]; then
  log "up to date ($current)"
  exit 0
fi
if pgrep -xq Chromium; then
  log "$tag is ready; it installs on the next check after the browser is closed"
  exit 0
fi

asset=$(field "const a = r.assets.find(a => a.name.startsWith('grabzy-chromium_') && a.name.endsWith('_$arch-macos.dmg'));
  return a ? [a.name, a.browser_download_url, a.digest || '-'].join(' ') : ''")
[ -n "$asset" ] || { log "release $tag has no $arch disk image"; exit 1; }
read -r name url digest <<<"$asset"

tmp=$(mktemp -d)
trap 'hdiutil detach -quiet "$tmp/mnt" 2>/dev/null || true; rm -rf "$tmp"' EXIT
log "downloading $name"
curl -fsSL -o "$tmp/$name" "$url"
if [ "$digest" != "-" ]; then
  [ "sha256:$(shasum -a 256 "$tmp/$name" | cut -d' ' -f1)" = "$digest" ] || { log "checksum mismatch for $name, not installing"; exit 1; }
else
  log "warning: GitHub gave no checksum for this file"
fi

hdiutil attach -quiet -nobrowse -readonly -mountpoint "$tmp/mnt" "$tmp/$name"
log "installing $tag"
rm -rf "$APP.new"
ditto "$tmp/mnt/Chromium.app" "$APP.new"
# Signed ad hoc, not notarized: clear the quarantine flag so Gatekeeper lets it open.
xattr -cr "$APP.new"
rm -rf "$APP"
mv "$APP.new" "$APP"
echo "$tag" > "$STAMP"
log "installed $tag"
