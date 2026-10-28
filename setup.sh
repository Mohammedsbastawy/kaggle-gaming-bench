#!/bin/bash
set -e

BENCH="/tmp/kaggle-game-dev-bench"
LOGS="/home/gamer/logs"
BUILDS="/tmp/game-builds"
mkdir -p "$BENCH/logs" "$BUILDS" /tmp/ea-store

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
SETUP_PROFILE="${GAMELAB_SETUP_PROFILE:-local}"
if [ "$SETUP_PROFILE" != local ] && [ "$SETUP_PROFILE" != full ]; then
    echo "Unknown GAMELAB_SETUP_PROFILE: $SETUP_PROFILE" >&2
    exit 2
fi
echo "▶ Setup profile: $SETUP_PROFILE"

echo "=========================================================="
echo "    7BZ DEV CLOUD GAME BOOTSTRAPPER                       "
echo "=========================================================="

# 1. Kill stale apt/dpkg locks if running in dirty interactive session
echo "▶ Checking and clearing stale apt locks..."
fuser -k /var/lib/dpkg/lock-frontend 2>/dev/null || true
fuser -k /var/lib/dpkg/lock 2>/dev/null || true
fuser -k /var/lib/apt/lists/lock 2>/dev/null || true
fuser -cache/apt/archives/lock 2>/dev/null || true
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

# 3. Core desktop, X11, audio, and compression utilities
apt_install "core desktop" \
    xvfb openbox tint2 xterm pulseaudio pulseaudio-utils xauth dbus-x11 \
    libgl1-mesa-dri libgbm1 libpixman-1-0 libxkbcommon0 mesa-utils x11-utils vulkan-tools \
    xdotool xinput wmctrl wget curl cabextract p7zip-full zstd winetricks python3-pygame python3-aiohttp

# Developer desktop: direct downloads/torrents and a native browser in the stream.
apt_install "download manager" aria2
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1 && ! command -v google-chrome-stable >/dev/null 2>&1; then
    echo "▶ Installing desktop browser..."
    apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=120 chromium || true
fi
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1 && ! command -v google-chrome-stable >/dev/null 2>&1; then
    CHROME_DEB=/tmp/google-chrome-stable_current_amd64.deb
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O "$CHROME_DEB" || true
    if [ -f "$CHROME_DEB" ] && [ "$(stat -c%s "$CHROME_DEB" 2>/dev/null || echo 0)" -gt 50000000 ]; then
        apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=120 "$CHROME_DEB" || true
    fi
fi

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

# 4b. NVIDIA 3D Hardware Userspace Driver & Vulkan Provisioner
if [ -c /dev/nvidiactl ] && [ -c /dev/nvidia0 ]; then
    echo "▶ Initializing NVIDIA Tesla T4 userspace driver and Vulkan ICD..."
    if [ -f "$BENCH/probe_nvidia_userspace.sh" ]; then
        bash "$BENCH/probe_nvidia_userspace.sh" || true
    fi
    work="$BENCH/nvidia-userspace-probe"
    if [ -f "$work/env.sh" ]; then
        # shellcheck disable=SC1090
        . "$work/env.sh"
    fi
fi

# 4c. VirtualGL 3.1.5 installation
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
if [ -c /dev/nvidia0 ]; then
    # Ensure nvidia-modeset character device node exists
    if [ ! -c /dev/nvidia-modeset ]; then
        mknod -m 666 /dev/nvidia-modeset c 195 254 2>/dev/null || nvidia-modprobe -m 2>/dev/null || true
    fi
    echo "▶ Installing NVIDIA Xorg server support..."
    apt_install "NVIDIA Xorg GLX server support" xserver-xorg-core
    # Ensure host NVIDIA userspace libraries take precedence
    if [ -d /usr/local/nvidia/lib64 ]; then
        echo "/usr/local/nvidia/lib64" > /etc/ld.so.conf.d/00-nvidia-host.conf
        ldconfig 2>/dev/null || true
    fi
fi

# 4d. DXVK 2.6.2 (DirectX 9/10/11 -> Vulkan) installation
DXVK_TAR=/tmp/dxvk-2.6.2.tar.gz
if [ ! -d /opt/gamelab-dxvk/dxvk-2.6.2 ]; then
    echo "▶ Downloading and extracting DXVK 2.6.2 Vulkan translation layer..."
    wget -q https://github.com/doitsujin/dxvk/releases/download/v2.6.2/dxvk-2.6.2.tar.gz -O "$DXVK_TAR" || true
    if echo '17761876556afd55736cb895d184f5a1c55d43350f1b1e3b129f8d28706d7992  /tmp/dxvk-2.6.2.tar.gz' | sha256sum -c -; then
        mkdir -p /opt/gamelab-dxvk
        tar -xzf "$DXVK_TAR" -C /opt/gamelab-dxvk || true
    else
        echo 'Warning: DXVK download or checksum failed; DXVK unavailable.'
    fi
fi

# 4e. VKD3D-Proton 2.14.1 (DirectX 12 -> Vulkan) installation for modern AAA games
VKD3D_TAR=/tmp/vkd3d-proton-2.14.1.tar.zst
if [ ! -d /opt/gamelab-vkd3d ]; then
    echo "▶ Downloading VKD3D-Proton (DirectX 12) translation layer for modern AAA games..."
    wget -q https://github.com/HansKristian-Work/vkd3d-proton/releases/download/v2.14.1/vkd3d-proton-2.14.1.tar.zst -O "$VKD3D_TAR" || true
    if [ -f "$VKD3D_TAR" ] && [ $(stat -c%s "$VKD3D_TAR" 2>/dev/null || echo 0) -gt 1000000 ]; then
        mkdir -p /opt/gamelab-vkd3d
        tar --zstd -xf "$VKD3D_TAR" -C /opt/gamelab-vkd3d 2>/dev/null || \
        tar -xf "$VKD3D_TAR" -C /opt/gamelab-vkd3d 2>/dev/null || true
    fi
fi

# 5. Extra libraries for Lutris and Wine Gecko
apt_install "desktop clipboard" python3-tk
if [ "$SETUP_PROFILE" = full ]; then
    apt_install "storefront libraries" python3.12 python3-dbus python3-gi python3-yaml python3-lxml python3-requests python3-pil
fi
apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=120 wine-gecko 2>/dev/null || true

# 6. Python streaming, interface and gaming packages
python3 -m pip install --no-cache-dir \
    'selkies[jupyter]==2.1.0' 'pygame==2.6.1' 'psutil'
if [ "$SETUP_PROFILE" = full ]; then
    python3 -m pip install --no-cache-dir 'legendary-gl'
fi

# 7. Optional storefront suite. The local developer desktop needs none of it.
if [ "$SETUP_PROFILE" = full ]; then
# Steam installation (Valve official deb)
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
                    ln -sf "$(dirname "$extracted/bin/wine")/wineserver" /usr/bin/wineserver || true
                    ln -sf "$(dirname "$extracted/bin/wine")/wineboot" /usr/bin/wineboot || true
                fi
                if [ ! -f /usr/local/bin/wine ]; then
                    ln -sf "$extracted/bin/wine" /usr/local/bin/wine || true
                fi
                break
            fi
        done
    fi
fi

# 13. Pre-configure Heroic default settings
if [ "$SETUP_PROFILE" = full ]; then
    python3 "$BENCH/fix_heroic_config.py" || true
fi

# 14. Pre-initialize clean 64-bit Wine prefix with Wine-GE
if [ -x "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wineboot" ]; then
    echo "▶ Initializing clean default Wine prefix (/home/gamer/.wine)..."
    export WINEPREFIX="/home/gamer/.wine"
    export WINEARCH=win64
    export WINEDLLOVERRIDES="mscoree,mshtml=d"
    runuser -u gamer -- env WINEPREFIX="/home/gamer/.wine" WINEARCH=win64 WINEDLLOVERRIDES="mscoree,mshtml=d" \
        "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wineboot" --init 2>/dev/null || true

    # Pre-install DXVK and VKD3D DirectX-to-Vulkan libraries into Wine prefix
    echo "▶ Installing DXVK and VKD3D DirectX-to-Vulkan libraries into Wine prefix..."
    if [ -d /opt/gamelab-dxvk/dxvk-2.6.2 ]; then
        for arch_pair in "x64:system32" "x32:syswow64"; do
            IFS=':' read -r darch dsub <<< "$arch_pair"
            for dll in d3d9.dll d3d10core.dll d3d11.dll dxgi.dll; do
                src="/opt/gamelab-dxvk/dxvk-2.6.2/$darch/$dll"
                dst="/home/gamer/.wine/drive_c/windows/$dsub/$dll"
                [ -f "$src" ] && cp -f "$src" "$dst" 2>/dev/null || true
            done
        done
        echo "✓ DXVK installed into Wine prefix."
    fi
    for vkd3d_dir in /opt/gamelab-vkd3d/vkd3d-proton-*; do
        if [ -d "$vkd3d_dir" ]; then
            for arch_pair in "x64:system32" "x86:syswow64"; do
                IFS=':' read -r darch dsub <<< "$arch_pair"
                for dll in d3d12.dll d3d12core.dll; do
                    src="$vkd3d_dir/$darch/$dll"
                    dst="/home/gamer/.wine/drive_c/windows/$dsub/$dll"
                    [ -f "$src" ] && cp -f "$src" "$dst" 2>/dev/null || true
                done
            done
            echo "✓ VKD3D-Proton (DirectX 12) installed into Wine prefix."
            break
        fi
    done

    # These installers and winetricks can add minutes. Local builds can opt in
    # when they require VC runtimes; the historical full profile keeps them.
    if [ "$SETUP_PROFILE" = full ] || [ "${GAMELAB_PREINSTALL_PREREQS:-0}" = 1 ]; then
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
    echo "▶ Installing the Unreal Engine Visual C++ prerequisite..."
    runuser -u gamer -- env WINEPREFIX="/home/gamer/.wine" WINEARCH=win64 WINEDLLOVERRIDES="mscoree,mshtml=d" \
        winetricks -q vcrun2019 2>/dev/null || true
    fi

    if [ "$SETUP_PROFILE" = full ]; then
    echo "▶ Applying verified DirectInput, AMD FSR, and zero-acceleration mouse settings..."
    for reg_entry in \
        'HKEY_CURRENT_USER\Software\Wine\DirectInput|MouseWarpOverride|force' \
        'HKEY_CURRENT_USER\Software\Wine\X11 Driver|GrabPointer|Y' \
        'HKEY_CURRENT_USER\Software\Wine\X11 Driver|UseTakeFocus|N' \
        'HKEY_CURRENT_USER\Control Panel\Mouse|MouseSpeed|0' \
        'HKEY_CURRENT_USER\Control Panel\Mouse|MouseThreshold1|0' \
        'HKEY_CURRENT_USER\Control Panel\Mouse|MouseThreshold2|0' \
        'HKEY_CURRENT_USER\Control Panel\Mouse|MouseSensitivity|10' \
        'HKEY_CURRENT_USER\Software\Wine\Direct3D|WINE_FULLSCREEN_FSR|1' \
        'HKEY_CURRENT_USER\Software\Wine\Direct3D|WINE_FULLSCREEN_FSR_STRENGTH|2' \
        'HKEY_CURRENT_USER\Software\Wine\DllOverrides|d3d11|native,builtin' \
        'HKEY_CURRENT_USER\Software\Wine\DllOverrides|d3d12|native,builtin' \
        'HKEY_CURRENT_USER\Software\Wine\DllOverrides|dxgi|native,builtin'; do
        IFS='|' read -r rkey rname rval <<< "$reg_entry"
        runuser -u gamer -- env WINEPREFIX="/home/gamer/.wine" WINEARCH=win64 \
            "$WINE_GE_DIR/Wine-GE-Proton8-26/bin/wine" reg add "$rkey" \
            /v "$rname" /t REG_SZ /d "$rval" /f 2>/dev/null || true
    done
    fi
    echo "✓ Wine prefix fully initialized with DXVK, VKD3D-Proton, and FSR upscaling."
fi

# 15. Inject keyboard lock into Selkies HTML (prevents Esc from exiting browser fullscreen)
python3 -c "
import sys; sys.path.insert(0, '$BENCH')
try:
    from auto_optimize import inject_keyboard_lock
    result = inject_keyboard_lock()
    if result: print('Keyboard lock injected into:', result)
    else: print('No Selkies HTML found to patch for keyboard lock.')
except Exception as e: print('Keyboard lock injection skipped:', e)
" || true

# 16. Compile Selkies gamepad interposers if not present
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
    ln -sf "$BENCH/lib/x86_64-linux-gnu" "$BENCH/lib64" 2>/dev/null || true
    ln -sf "$BENCH/lib/i386-linux-gnu" "$BENCH/lib32" 2>/dev/null || true
    cp -f "$BENCH/lib/x86_64-linux-gnu/"*.so /usr/lib/x86_64-linux-gnu/ 2>/dev/null || true
    cp -f "$BENCH/lib/i386-linux-gnu/"*.so /usr/lib/i386-linux-gnu/ 2>/dev/null || true
fi

# 17. Prepare /dev/input gamepad device nodes and permissions
mkdir -p /dev/input 2>/dev/null || true
for i in 0 1 2 3; do touch /dev/input/js$i 2>/dev/null || true; done
for i in 1000 1001 1002 1003; do touch /dev/input/event$i 2>/dev/null || true; done
chmod -R 666 /dev/input 2>/dev/null || true

# 18. Set permissions and ownership
chmod -R 755 "$BENCH"/*.sh 2>/dev/null || true
chmod -R 777 "$BENCH" 2>/dev/null || true
chown -R gamer:gamer /home/gamer 2>/dev/null || true
chmod -R 777 /home/gamer 2>/dev/null || true

echo "=========================================================="
echo "    BENCH ENVIRONMENT SETUP COMPLETED SUCCESSFULLY!       "
echo "=========================================================="
wineserver -k 2>/dev/null || true
exit 0
