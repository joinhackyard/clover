#!/bin/bash
# Clover by Hackyard — installer. Paste in Terminal:
#   curl -fsSL https://raw.githubusercontent.com/joinhackyard/clover/main/install.sh | bash
# Downloads the source to ~/.clover (Clover updates itself from there), builds the app, opens it.
set -e
DIR="${CLOVER_HOME:-$HOME/.clover}"
G=$'\033[38;2;47;210;122m'; P=$'\033[38;2;255;126;182m'; D=$'\033[2m'; R=$'\033[0m'
printf '\n%s   🍀  Clover%s %sby Hackyard%s\n%s   your whole Mac, one sentence away%s\n\n' "$G" "$R" "$P" "$R" "$D" "$R"
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 26 ] || { echo "Clover needs macOS 26 or later."; exit 1; }
if ! xcode-select -p >/dev/null 2>&1; then
  echo "First, Apple's command line tools. A macOS window will open: click Install."
  echo "When it finishes, paste the install line again."
  xcode-select --install 2>/dev/null || true
  exit 1
fi
if [ -d "$DIR/.git" ]; then
  echo "Updating Clover in $DIR…"
  git -C "$DIR" pull -q --ff-only || { echo "Could not update $DIR. Delete that folder, then paste the install line again."; exit 1; }
else
  echo "Planting Clover in $DIR…"
  git clone -q --depth 1 https://github.com/joinhackyard/clover.git "$DIR"
fi
"$DIR/build.sh"
open "$HOME/Applications/Clover.app"
printf '%sDone.%s The Clover setup window walks you through the rest. Pick Claude Code, or bring your own key\n(Claude API, OpenAI, Azure OpenAI or any endpoint).\n' "$G" "$R"
