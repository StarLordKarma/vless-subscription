#!/bin/bash
set -e

BASE="$HOME/Library/Application Support/V2RayXS-Auto"
LAUNCH="$HOME/Library/LaunchAgents/com.starlordkarma.v2rayxs-auto.plist"
RUNNER="$BASE/run_update.sh"
UPDATER="$BASE/v2rayxs_auto_update.py"
LOG="$BASE/update.log"
ERR="$BASE/update-error.log"
UPDATER_URL="https://starlordkarma.github.io/vless-subscription/mac/v2rayxs_auto_update.py"

mkdir -p "$BASE" "$HOME/Library/LaunchAgents"

cat > "$RUNNER" <<RUNNER
#!/bin/bash
set -e
/usr/bin/curl -fsSL --connect-timeout 10 --max-time 30 "$UPDATER_URL" -o "$UPDATER.new"
/bin/mv "$UPDATER.new" "$UPDATER"
/bin/chmod 700 "$UPDATER"
/usr/bin/python "$UPDATER"
RUNNER
chmod 700 "$RUNNER"

cat > "$LAUNCH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.starlordkarma.v2rayxs-auto</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUNNER</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>3600</integer>
  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR</string>
</dict>
</plist>
PLIST

/bin/launchctl unload "$LAUNCH" >/dev/null 2>&1 || true
/bin/launchctl load "$LAUNCH"

# Run immediately once. Future runs refresh the updater itself first.
/bin/bash "$RUNNER" || true

echo "V2RayXS automatic updates installed."
echo "10 validated servers refresh at login and every hour."
