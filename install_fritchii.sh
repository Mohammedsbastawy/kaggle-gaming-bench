#!/usr/bin/env bash
set -euo pipefail
url="https://github.com/Frizti/Fritchii/releases/download/fritchii-v5.6/Fritchii-v5.6-Windows-x64.zip"
sha256="3266298fe6b13aa98b72fd3fb05c219475608661fbe7e4b97902e719acb4c699"
target="/opt/fritchii"
if [ -f "$target/app/lichii.exe" ] && [ "$(cat "$target/build" 2>/dev/null)" = "v5.6" ]; then
    echo 'Fritchii v5.6 is already installed.'
    exit 0
fi
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
curl --fail --location --retry 3 --output "$work/fritchii.zip" "$url"
printf '%s  %s\n' "$sha256" "$work/fritchii.zip" | sha256sum --check --status
unzip -q "$work/fritchii.zip" -d "$work/extracted"
exe="$(find "$work/extracted" -type f -name lichii.exe -print -quit)"
test -n "$exe"
mkdir -p "$target/app"
cp -a "$(dirname "$exe")/." "$target/app/"
chmod -R a+rX "$target/app"
printf 'v5.6\n' > "$target/build"
echo 'Fritchii v5.6 installed (Windows x64; launched through Wine).'
