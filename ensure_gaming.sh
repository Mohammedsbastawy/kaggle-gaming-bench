#!/usr/bin/env bash
# First-game setup. Intentionally absent from the desktop cold-boot path.
set -euo pipefail
bench=/tmp/kaggle-game-dev-bench
ready=/opt/7bz-gaming.ready
mkdir -p /opt /home/gamer/logs "$bench/logs"
exec 9>/opt/7bz-gaming.lock
flock 9
if [[ -f "$ready" ]]; then exit 0; fi
started=$SECONDS
export DEBIAN_FRONTEND=noninteractive
echo 'Installing Wine and NVIDIA game compatibility on first use...'

dpkg --add-architecture i386
apt-get update -qq

wine_dir=/home/gamer/.config/heroic/tools/wine
wine_archive=/tmp/wine-lutris-GE-Proton8-26-x86_64.tar.xz
vgl64=/tmp/virtualgl_3.1.5_amd64.deb
vgl32=/tmp/virtualgl32_3.1.5_amd64.deb
redist_dir=/tmp/vc_redist
mkdir -p "$wine_dir" "$redist_dir"

download() { curl -fLsS --retry 2 --connect-timeout 15 "$1" -o "$2"; }
download 'https://github.com/GloriousEggroll/wine-ge-custom/releases/download/GE-Proton8-26/wine-lutris-GE-Proton8-26-x86_64.tar.xz' "$wine_archive" & wine_pid=$!
download 'https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl_3.1.5_amd64.deb' "$vgl64" & vgl64_pid=$!
download 'https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl32_3.1.5_amd64.deb' "$vgl32" & vgl32_pid=$!
download 'https://aka.ms/vs/17/release/vc_redist.x64.exe' "$redist_dir/vc_redist.x64.exe" & vc64_pid=$!
download 'https://aka.ms/vs/17/release/vc_redist.x86.exe' "$redist_dir/vc_redist.x86.exe" & vc32_pid=$!
if [[ -c /dev/nvidia0 && -c /dev/nvidiactl ]]; then
    bash "$bench/probe_nvidia_userspace.sh" > "$bench/logs/nvidia-userspace.log" 2>&1 & nvidia_pid=$!
fi

# APT is serialized with other APT callers by flock, but independent HTTP
# transfers above can progress while dpkg installs the 32-bit runtime.
apt-get install -y -qq --no-install-recommends \
    wine wine64 wine32:i386 winbind winetricks cabextract p7zip-full vulkan-tools \
    libgl1:i386 libglx0:i386 libx11-6:i386 libxext6:i386 libxi6:i386 \
    libxfixes3:i386 libxcomposite1:i386 libxrandr2:i386 \
    libpulse0:i386 libgnutls30:i386 libvulkan1:i386 \
    > "$bench/logs/apt-gaming.log" 2>&1

wait "$vgl64_pid"; wait "$vgl32_pid"
printf '%s  %s\n' \
    df3f7788ce41b182a47c0d298e5cd6d2d63579522cb41825970b7726e825485e "$vgl64" \
    7dc63ecb47d7ab9cb486bb21a9a968dee853380da760cc7f36f616d09ec62b9e "$vgl32" \
    | sha256sum -c -
apt-get install -y -qq --no-install-recommends "$vgl64" "$vgl32" \
    >> "$bench/logs/apt-gaming.log" 2>&1

wait "$wine_pid"
xz -t "$wine_archive"
tar -xf "$wine_archive" -C "$wine_dir"
runner=$(find "$wine_dir" -mindepth 2 -maxdepth 3 -path '*/bin/wine' -print -quit)
test -n "$runner"
test -x "$runner"
ln -sfn "$(dirname "$(dirname "$runner")")" "$wine_dir/Wine-GE-Proton8-26"
chown -R gamer:gamer "$wine_dir"

if [[ -n "${nvidia_pid:-}" ]]; then wait "$nvidia_pid" || true; fi
if [[ -f "$bench/nvidia-userspace-probe/env.sh" ]]; then
    # shellcheck disable=SC1091
    source "$bench/nvidia-userspace-probe/env.sh"
fi

prefix=/home/gamer/.wine
runuser -u gamer -- env HOME=/home/gamer DISPLAY=:0 WINEPREFIX="$prefix" WINEARCH=win64 \
    WINEDLLOVERRIDES=mscoree,mshtml=d "$(dirname "$runner")/wineboot" --init \
    > "$bench/logs/wineboot.log" 2>&1 || true
wait "$vc64_pid"; wait "$vc32_pid"
for arch in x64 x86; do
    runuser -u gamer -- env HOME=/home/gamer DISPLAY=:0 WINEPREFIX="$prefix" WINEARCH=win64 \
        WINEDLLOVERRIDES=mscoree,mshtml=d "$runner" \
        "$redist_dir/vc_redist.$arch.exe" /install /quiet /norestart \
        >> "$bench/logs/vcredist.log" 2>&1 || true
done
runuser -u gamer -- env HOME=/home/gamer DISPLAY=:0 WINEPREFIX="$prefix" "$runner" \
    regedit /S "$bench/config/wine/mouse.reg" \
    >> "$bench/logs/wine-registry.log" 2>&1 || true

python3 "$bench/fix_heroic_config.py" >> "$bench/logs/heroic-config.log" 2>&1 || true
touch "$ready"
echo "GAMING_PREP_SECONDS=$((SECONDS-started))"
