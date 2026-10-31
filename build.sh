#!/bin/bash
# Clover by Hackyard: builds Clover.app, starts it at login, and (re)starts it now. Run it again after any change.
# CLOVER_PACKAGE=<folder> ./build.sh only builds a signed-ad-hoc Clover.app into that folder (CI releases): no install, no restart.
set -e; cd "$(dirname "$0")"
VERSION=$(tr -d '\n' < VERSION)
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid VERSION: $VERSION"; exit 1; }
IFS=. read -r VERSION_MAJOR VERSION_MINOR VERSION_PATCH <<< "$VERSION"
(( VERSION_MINOR < 1000 && VERSION_PATCH < 1000 )) || { echo "VERSION components must be below 1000"; exit 1; }
BUILD=$((VERSION_MAJOR * 1000000 + VERSION_MINOR * 1000 + VERSION_PATCH))
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo unknown)
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 26 ] || { echo "Clover needs macOS 26 or later (it uses Apple's new on-device speech)."; exit 1; }
xcode-select -p >/dev/null 2>&1 || { echo "Needs Apple's command line tools. Run: xcode-select --install   then run ./build.sh again."; exit 1; }
command -v python3 >/dev/null || { echo "Clover needs Python 3. Install it, then run ./build.sh again."; exit 1; }
command -v claude >/dev/null || [ -x ~/.local/bin/claude ] || echo "Note: Claude Code is not installed yet. That is fine: Clover can use your Antigravity plan or your own API key (Claude, OpenAI, Gemini, Azure and more) instead."
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
# A compiler error must leave the installed app and its resources alone.
swiftc -O -target "$(uname -m)-apple-macos26.0" Clover.swift -o "$STAGE/Clover"
APP=${CLOVER_PACKAGE:+$CLOVER_PACKAGE/Clover.app}; APP=${APP:-~/Applications/Clover.app}   # in Applications so System Settings can list it for permissions
APP=${APP/#\~/$HOME}
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/ui" "$APP/Contents/Resources/sounds"
cp clover.py clover_engine.py "$APP/Contents/Resources/"
cp ui/*.html ui/*.js "$APP/Contents/Resources/ui/"
cp ui/sounds/*.wav "$APP/Contents/Resources/sounds/"   # Clover's own sound pack
cp ui/sounds/Bloom.wav "$APP/Contents/Resources/"   # notification banners look for their sound here
cp ui/AppIcon.icns "$APP/Contents/Resources/"
cat > "$APP/Contents/Info.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>org.hackyard.clover</string>
<key>CFBundleName</key><string>Clover</string>
<key>CFBundleExecutable</key><string>Clover</string>
<key>CFBundleVersion</key><string>$BUILD</string>
<key>CFBundleShortVersionString</key><string>$VERSION</string>
<key>CloverCommit</key><string>$COMMIT</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>CloverSource</key><string>$(pwd)</string>
<key>LSUIElement</key><true/>
<key>NSMicrophoneUsageDescription</key><string>Clover listens when you use its shortcut or microphone button.</string>
<key>NSAppleEventsUsageDescription</key><string>Clover controls apps like Finder, Chrome and Music when you ask it to.</string>
<key>NSCalendarsFullAccessUsageDescription</key><string>Clover reads your calendar, adds events you request, and asks before moving or deleting existing events. Calendar details are sent to your chosen AI model.</string>
<key>NSSpeechRecognitionUsageDescription</key><string>Clover turns your words into text on this Mac.</string>
</dict></plist>
P
mv "$STAGE/Clover" "$APP/Contents/MacOS/Clover"
# With a code-signing identity named "Clover Local Signing" in the keychain, macOS keeps permissions across
# rebuilds and auto-updates; ad hoc signing would ask for every permission again after each one. So make it once.
if [ -n "$CLOVER_PACKAGE" ]; then codesign -s - --force "$APP"; echo "Packaged $APP"; exit 0; fi   # CI: ad hoc, nothing installed
ID=$(security find-identity -p codesigning | awk '/Clover Local Signing/{print $2; exit}')
if [ -z "$ID" ]; then
  K=$(mktemp -d)
  /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 7300 -subj "/CN=Clover Local Signing" -addext "extendedKeyUsage=critical,codeSigning" \
    -addext "keyUsage=critical,digitalSignature" -keyout "$K/k.pem" -out "$K/c.pem" 2>/dev/null &&
  /usr/bin/openssl pkcs12 -export -inkey "$K/k.pem" -in "$K/c.pem" -out "$K/a.p12" -passout pass:clover 2>/dev/null &&
  security import "$K/a.p12" -P clover -T /usr/bin/codesign >/dev/null 2>&1 || true   # fails quietly: ad hoc still works
  rm -rf "$K"
  ID=$(security find-identity -p codesigning | awk '/Clover Local Signing/{print $2; exit}')
fi
codesign -s "${ID:--}" --force "$APP"
# register with macOS, or System Settings can't list it for permissions
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
AGENT=~/Library/LaunchAgents/org.hackyard.clover.plist   # starts at login, restarts if it crashes (Quit stays quit)
mkdir -p ~/Library/LaunchAgents ~/.config/clover
cat > "$AGENT" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>org.hackyard.clover</string>
<key>ProgramArguments</key><array><string>$APP/Contents/MacOS/Clover</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>StandardErrorPath</key><string>$HOME/.config/clover/app.err</string>
</dict></plist>
P
[ -n "$CLOVER_NO_RESTART" ] && exit 0   # the app's own updater restarts it when idle
# Reload the job so launchd refreshes its executable signing requirement after a rebuild.
launchctl bootout gui/$(id -u)/org.hackyard.clover 2>/dev/null || true
pkill -f "$APP/Contents/MacOS/Clover$" 2>/dev/null && sleep 1   # stop a copy opened by hand too
# bootout can return before the job has finished unloading.
launchctl bootstrap gui/$(id -u) "$AGENT" 2>/dev/null || { sleep 1; launchctl bootstrap gui/$(id -u) "$AGENT" 2>/dev/null || {
  echo "Could not add Clover to Login Items; opening it directly instead."
  open "$APP"
}; }
echo "🍀 Clover is running. Hold Control+Option+Space and talk, or turn on the wake word and say \"Clover\"."
