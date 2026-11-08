#!/usr/bin/env bash
set -euo pipefail

# Pinned upstream release. Extracting avoids a FUSE requirement in Kaggle containers.
url="https://github.com/zortos293/Lichii/releases/download/build-117/lichii-linux-x86_64-pgo.AppImage"
target="/opt/lichii"
if [ -x "$target/squashfs-root/AppRun" ] && [ "$(cat "$target/build" 2>/dev/null)" = "build-117" ]; then
    echo "Lichii build 117 is already installed."
    exit 0
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
echo "Installing Lichii build 117 (Linux x86_64 PGO)..."
curl --fail --location --retry 3 --output "$work/lichii.AppImage" "$url"
test "$(stat -c%s "$work/lichii.AppImage")" -gt 1000000
chmod +x "$work/lichii.AppImage"
cd "$work"
"$work/lichii.AppImage" --appimage-extract >/dev/null
test -x "$work/squashfs-root/AppRun"
mkdir -p "$target"
cp -a "$work/squashfs-root" "$target/"
echo "build-117" > "$target/build"
echo "Lichii build 117 installed in $target."
