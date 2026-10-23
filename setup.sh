#!/bin/bash
set -e

BENCH="/tmp/kaggle-game-dev-bench"
LOGS="/home/gamer/logs"
BUILDS="/tmp/game-builds"
mkdir -p "$BENCH/logs" "$BUILDS" /tmp/ea-store

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"

echo "=========================================================="
echo "    KAGGLE GAMING & GAME-DEV BENCH BOOTSTRAPPER           "
echo "=========================================================="

# 1. Kill stale apt/dpkg locks if running in dirty interactive session
echo "▶ Checking and clearing stale apt locks..."
fuser -k /var/lib/dpkg/lock-frontend 2>/dev/null || true
fuser -k /var/lib/dpkg/lock 2>/dev/null || true
fuser -k /var/lib/apt/lists/lock 2>/dev/null || true
fuser -k /var/cache/apt/archives/lock 2>/dev/null || true
rm -f /var/lib/dpkg/lock* /var/lib/apt/lists/lock* /var/cache/apt/archives/lock* 2>/dev/null || true
dpkg --configure -a 2>/dev/null || true

# Helper function for resilient apt install with timeout and retries
apt_install() {
    local label="$1"
    shift
    echo "▶ Installing $label..."
    local attempts=0
    while [ $attempts -lt 3 ]; do
        attempts=$((attempts + 1))
        if apt-get install -y --no-install-recommends \
            -o DPkg::Lock::Timeout=120 \
            -o APT::Get::Assume-Yes=true \
            "$@"; then
            return 0
        fi
        echo "Notice: apt install for $label failed (attempt $attempts/3). Retrying in 4s..."
        sleep 4
        fuser -k /var/lib/dpkg/lock-frontend 2>/dev/null || true
        rm -f /var/lib/dpkg/lock* 2>/dev/null || true
        dpkg --configure -a 2>/dev/null || true
    done
    echo "Warning: Could not install some packages for $label, continuing..."
    return 0
}

# 2. Multiarch & repositories setup
dpkg --add-architecture i386 || true
if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
    sed -i 's/Components: main universe/Components: main universe multiverse/g' /etc/apt/sources.list.d/ubuntu.sources || true
fi

# Resilient apt update
apt-get update -o DPkg::Lock::Timeout=120 -qq || true

# 3. Core desktop, X11, and audio utilities
apt_install "core desktop" \
    xvfb openbox tint2 xterm pulseaudio pulseaudio-utils xauth dbus-x11 \
    libgl1-mesa-dri libgbm1 libpixman-1-0 libxkbcommon0 mesa-utils x11-utils vulkan-tools \
    xdotool wmctrl wget curl cabextract p7zip-full

# Build tools (isolated so multilib issues don't block core)
apt_install "build tools" git make gcc
apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=120 gcc-multilib 2>/dev/null || true

# 4. Wine and complete 32-bit/64-bit graphics runtime
apt_install "wine runtime" wine wine64 winbind
apt_install "32-bit graphics runtime" \
    wine32:i386 libgl1:i386 libglx0:i386 libglx-mesa0:i386 libgl1-mesa-dri:i386 \
    mesa-vulkan-drivers:i386 libx11-6:i386 libxext6:i386 libxfixes3:i386 \
    libxcomposite1:i386 libxrandr2:i386 libxinerama1:i386 libxi6:i386 libasound2:i386 \
    libpulse0:i386 libgnutls30:i386 libvulkan1:i386

# GPU graphics/display components must be mounted by the host when the container
# is created. Never install a second NVIDIA kernel driver or fabricate an ICD.
# VirtualGL supplies both 64- and 32-bit OpenGL interposers on capable hosts.
if [ -c /dev/nvidiactl ] && [ -c /dev/nvidia0 ]; then
    if ! [ -x /opt/VirtualGL/bin/vglrun ]; then
        VGL64=/tmp/virtualgl_3.1.5_amd64.deb
        VGL32=/tmp/virtualgl32_3.1.5_amd64.deb
        wget -q https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl_3.1.5_amd64.deb -O "$VGL64" || true
        wget -q https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl32_3.1.5_amd64.deb -O "$VGL32" || true
        if echo 'df3f7788ce41b182a47c0d298e5cd6d2d63579522cb41825970b7726e825485e  /tmp/virtualgl_3.1.5_amd64.deb' | sha256sum -c - && \
           echo '7dc63ecb47d7ab9cb486bb21a9a968dee853380da760cc7f36f616d09ec62b9e  /tmp/virtualgl32_3.1.5_amd64.deb' | sha256sum -c -; then
            apt-get install -y --no-install-recommends "$VGL64" "$VGL32" || true
        else
            echo 'VirtualGL download or checksum failed; GPU GL bridge unavailable.'
        fi
    fi
else
    echo 'NVIDIA GPU devices unavailable; GPU 3D cannot be enabled inside this container.'
fi
if [ -c /dev/nvidia-modeset ] && [ -c /dev/nvidia0 ]; then
    apt_install "NVIDIA Xorg server support" xserver-xorg-core
fi

if [ -c /dev/nvidiactl ] && { [ -f /etc/vulkan/icd.d/nvidia_icd.json ] || [ -f /usr/share/vulkan/icd.d/nvidia_icd.json ]; }; then
    DXVK_TAR=/tmp/dxvk-2.6.2.tar.gz
    wget -q https://github.com/doitsujin/dxvk/releases/download/v2.6.2/dxvk-2.6.2.tar.gz -O "$DXVK_TAR" || true
    if echo '17761876556afd55736cb895d184f5a1c55d43350f1b1e3b129f8d28706d7992  /tmp/dxvk-2.6.2.tar.gz' | sha256sum -c -; then
        mkdir -p /opt/gamelab-dxvk
        tar -xzf "$DXVK_TAR" -C /opt/gamelab-dxvk
    else
        echo 'DXVK download or checksum failed; DXVK unavailable.'
    fi
fi

# 5. Extra libraries for Lutris and Wine Gecko
apt_install "extra libraries" python3-tk python3.12 python3-dbus python3-gi python3-yaml python3-lxml python3-requests python3-pil
apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=120 wine-gecko 2>/dev/null || true

# 6. Python streaming, interface and gaming packages
python3 -m pip install --no-cache-dir \
    'selkies[jupyter]==2.1.0' 'pygame==2.6.1' 'psutil' 'legendary-gl'

# 7. Steam installation (Valve official deb)
STEAM_DEB="/tmp/steam_latest.deb"
if [ ! -f "$STEAM_DEB" ] || [ $(stat -c%s "$STEAM_DEB" 2>/dev/null || echo 0) -lt 1000000 ]; then
    wget -q https://repo.steampowered.com/steam/archive/stable/steam_latest.deb -O "$STEAM_DEB" || true
fi
if [ -f "$STEAM_DEB" ] && [ $(stat -c%s "$STEAM_DEB") -gt 1000000 ]; then
    apt_install "steam deb" "$STEAM_DEB"
else
    apt_install "steam apt" steam
fi

# 8. Heroic Games Launcher
HEROIC_DEB="/tmp/heroic.deb"
if [ ! -f "$HEROIC_DEB" ] || [ $(stat -c%s "$HEROIC_DEB" 2>/dev/null || echo 0) -lt 10000000 ]; then
    wget -q https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/releases/download/v2.22.4/Heroic-2.22.4-linux-amd64.deb -O "$HEROIC_DEB" || true
fi
if [ -f "$HEROIC_DEB" ] && [ $(stat -c%s "$HEROIC_DEB") -gt 10000000 ]; then
    dpkg -i "$HEROIC_DEB" || apt-get install -f -y -o DPkg::Lock::Timeout=120 || true
fi

# 9. Lutris & Minigalaxy
apt_install "lutris" lutris
apt_install "minigalaxy" minigalaxy

# 10. EA App installer download
EA_EXE="/tmp/ea-store/EAappInstaller.exe"
if [ ! -f "$EA_EXE" ] || [ $(stat -c%s "$EA_EXE" 2>/dev/null || echo 0) -lt 1000000 ]; then
    wget -q https://origin-a.akamaihd.net/EA-Desktop-Client-Download/installer-releases/EAappInstaller.exe -O "$EA_EXE" || true
fi

# 11. Configure unprivileged gamer user
id -u gamer >/dev/null 2>&1 || useradd -m -s /bin/bash -G audio,video gamer
for sub in .config .local .steam game-builds logs ea-prefix; do
    mkdir -p "/home/gamer/$sub"
done

# 12. Wine-GE runner installation for Heroic & Lutris
WINE_GE_DIR="/home/gamer/.config/heroic/tools/wine"
mkdir -p "$WINE_GE_DIR"
WINE_GE_TAR="/tmp/wine-lutris-GE-Proton8-26-x86_64.tar.xz"
if [ ! -d "$WINE_GE_DIR/Wine-GE-Proton8-26" ] && [ ! -d "$WINE_GE_DIR/lutris-GE-Proton8-26-x86_64" ]; then
    echo "▶ Downloading Wine-GE-Proton8-26 compatibility runner..."
    wget -q -c https://github.com/GloriousEggroll/wine-ge-custom/releases/download/GE-Proton8-26/wine-lutris-GE-Proton8-26-x86_64.tar.xz -O "$WINE_GE_TAR" || true
    if [ -f "$WINE_GE_TAR" ] && [ $(stat -c%s "$WINE_GE_TAR") -gt 50000000 ]; then
        echo "▶ Extracting Wine-GE-Proton8-26..."
        tar -xf "$WINE_GE_TAR" -C "$WINE_GE_DIR" || true
        for extracted in "$WINE_GE_DIR"/*; do
            if [ -d "$extracted" ] && [ -f "$extracted/bin/wine" ]; then
                ln -sf "$extracted" "$WINE_GE_DIR/Wine-GE-Proton8-26" || true
                mkdir -p "/home/gamer/.local/share/lutris/runners/wine"
                ln -sf "$extracted" "/home/gamer/.local/share/lutris/runners/wine/Wine-GE-Proton8-26" || true
                if [ ! -f /usr/bin/wine ]; then
                    ln -sf "$extracted/bin/wine" /usr/bin/wine || true
                    ln -sf "$extracted/bin/wineserver" /usr/bin/wineserver || true
                    ln -sf "$extracted/bin/wineboot" /usr/bin/wineboot || true
                fi
                if [ ! -f /usr/local/bin/wine ]; then
                    ln -sf "$extracted/bin/wine" /usr/local/bin/wine || true
                fi
                break
            fi
        done
    fi
fi

# 13. Pre-configure Heroic default settings: disable DXVK/VKD3D/Esync/Fsync
python3 "$BENCH/fix_heroic_config.py" || true

# 14. Pre-initialize clean 64-bit Wine prefix with Wine-GE (prevents kernel32.dll not found and popup dialogs)
if [ -x "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wineboot" ]; then
    echo "▶ Initializing clean default Wine prefix (/home/gamer/.wine)..."
    export WINEPREFIX="/home/gamer/.wine"
    export WINEARCH=win64
    export WINEDLLOVERRIDES="mscoree,mshtml=d"
    runuser -u gamer -- env WINEPREFIX="/home/gamer/.wine" WINEARCH=win64 WINEDLLOVERRIDES="mscoree,mshtml=d" \
        "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wineboot" --init 2>/dev/null || true

    # Pre-install Microsoft Visual C++ 2015-2022 runtimes (x64 and x86) into Wine prefix
    echo "▶ Pre-installing Microsoft Visual C++ runtimes into Wine prefix..."
    REDIST_DIR="/tmp/vc_redist"
    mkdir -p "$REDIST_DIR"
    wget -q -c "https://aka.ms/vs/17/release/vc_redist.x64.exe" -O "$REDIST_DIR/vc_redist.x64.exe" || true
    wget -q -c "https://aka.ms/vs/17/release/vc_redist.x86.exe" -O "$REDIST_DIR/vc_redist.x86.exe" || true

    if [ -f "$REDIST_DIR/vc_redist.x64.exe" ]; then
        runuser -u gamer -- env WINEPREFIX="/home/gamer/.wine" WINEARCH=win64 WINEDLLOVERRIDES="mscoree,mshtml=d" \
            "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wine" "$REDIST_DIR/vc_redist.x64.exe" /install /quiet /norestart 2>/dev/null || true
    fi
    if [ -f "$REDIST_DIR/vc_redist.x86.exe" ]; then
        runuser -u gamer -- env WINEPREFIX="/home/gamer/.wine" WINEARCH=win64 WINEDLLOVERRIDES="mscoree,mshtml=d" \
            "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wine" "$REDIST_DIR/vc_redist.x86.exe" /install /quiet /norestart 2>/dev/null || true
    fi
    echo "✓ Microsoft Visual C++ runtimes installed."
fi

# 14. Inject keyboard lock into Selkies HTML (prevents Esc from exiting browser fullscreen)
python3 -c "
import sys; sys.path.insert(0, '$BENCH')
try:
    from auto_optimize import inject_keyboard_lock
    result = inject_keyboard_lock()
    if result: print('Keyboard lock injected into:', result)
    else: print('No Selkies HTML found to patch for keyboard lock.')
except Exception as e: print('Keyboard lock injection skipped:', e)
" || true

# 14. Compile Selkies gamepad interposers if not present
if [ ! -f "$BENCH/lib/x86_64-linux-gnu/selkies_input_interposer.so" ]; then
    SOURCE="$BENCH/selkies-source"
    if [ ! -d "$SOURCE" ]; then
        git clone --depth 1 --branch 2.1.0 https://github.com/selkies-project/selkies.git "$SOURCE" || true
    fi
    if [ -d "$SOURCE/addons/input-interposer" ]; then
        make -C "$SOURCE/addons/input-interposer" PREFIX="$BENCH" install || true
        make -C "$SOURCE/addons/input-interposer" PREFIX="$BENCH" install32 2>/dev/null || true
        make -C "$SOURCE/addons/fake-udev" || true
        make -C "$SOURCE/addons/fake-udev" all32 2>/dev/null || true
        mkdir -p "$BENCH/lib/x86_64-linux-gnu" "$BENCH/lib/i386-linux-gnu"
        cp -f "$SOURCE/addons/fake-udev/libudev.so.1" "$BENCH/lib/x86_64-linux-gnu/selkies_fake_udev.so" 2>/dev/null || true
        cp -f "$SOURCE/addons/fake-udev/libudev_x86.so.1" "$BENCH/lib/i386-linux-gnu/selkies_fake_udev.so" 2>/dev/null || true
    fi
fi

# 15. Set permissions and ownership
chmod -R 755 "$BENCH"/*.sh 2>/dev/null || true
chmod -R 777 "$BENCH" 2>/dev/null || true
chown -R gamer:gamer /home/gamer 2>/dev/null || true
chmod -R 777 /home/gamer 2>/dev/null || true

echo "=========================================================="
echo "    BENCH ENVIRONMENT SETUP COMPLETED SUCCESSFULLY!       "
echo "=========================================================="
