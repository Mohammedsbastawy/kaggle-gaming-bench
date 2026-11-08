#!/usr/bin/env bash
# Install only the host-specific NVIDIA graphics pieces after restoring a CPU-built cache.
set -e

BENCH=/tmp/kaggle-game-dev-bench
if [ ! -c /dev/nvidiactl ] || [ ! -c /dev/nvidia0 ]; then
    echo 'NVIDIA GPU devices are unavailable; cannot finish cached GPU setup.' >&2
    exit 1
fi

bash "$BENCH/probe_nvidia_userspace.sh"
work="$BENCH/nvidia-userspace-probe"
if [ -f "$work/env.sh" ]; then
    # shellcheck disable=SC1090
    . "$work/env.sh"
fi

if ! [ -x /opt/VirtualGL/bin/vglrun ]; then
    vgl64=/tmp/virtualgl_3.1.5_amd64.deb
    vgl32=/tmp/virtualgl32_3.1.5_amd64.deb
    wget -q https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl_3.1.5_amd64.deb -O "$vgl64"
    wget -q https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl32_3.1.5_amd64.deb -O "$vgl32"
    echo 'df3f7788ce41b182a47c0d298e5cd6d2d63579522cb41825970b7726e825485e  /tmp/virtualgl_3.1.5_amd64.deb' | sha256sum -c -
    echo '7dc63ecb47d7ab9cb486bb21a9a968dee853380da760cc7f36f616d09ec62b9e  /tmp/virtualgl32_3.1.5_amd64.deb' | sha256sum -c -
    apt-get install -y --no-install-recommends "$vgl64" "$vgl32"
fi

if [ ! -c /dev/nvidia-modeset ]; then
    mknod -m 666 /dev/nvidia-modeset c 195 254 2>/dev/null || nvidia-modprobe -m 2>/dev/null || true
fi
apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=120 xserver-xorg-core
if [ -d /usr/local/nvidia/lib64 ]; then
    echo /usr/local/nvidia/lib64 > /etc/ld.so.conf.d/00-nvidia-host.conf
fi
ldconfig
echo 'Host-specific NVIDIA graphics setup complete.'
