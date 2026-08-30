#!/bin/bash
set -e

BASE="$HOME/Library/Application Support/V2RayXS-Auto"
LAUNCH="$HOME/Library/LaunchAgents/com.starlordkarma.v2rayxs-auto.plist"
UPDATER="$BASE/v2rayxs_auto_update.py"
LOG="$BASE/update.log"
ERR="$BASE/update-error.log"
URL="https://starlordkarma.github.io/vless-subscription/mac/v2rayxs_auto_update.py"

mkdir -p "$BASE" "$HOME/Library/LaunchAgents"

/usr/bin/curl -fsSL --connect-timeout 10 --max-time 30 "$URL" -o "$UPDATER"
chmod 700 "$UPDATER"

cat > "$LAUNCH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.starlordkarma.v2rayxs-auto</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python</string>
    <string>$UPDATER</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>21600</integer>
  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR</string>
</dict>
</plist>
PLIST

/bin/launchctl unload "$LAUNCH" >/dev/null 2>&1 || true
/bin/launchctl load "$LAUNCH"

# Run immediately once; LaunchAgent will then repeat every 6 hours and at login.
/usr/bin/python "$UPDATER" || true

echo "V2RayXS automatic updates installed."
echo "Servers are checked in GitHub and refreshed on this Mac at login and every 6 hours."
