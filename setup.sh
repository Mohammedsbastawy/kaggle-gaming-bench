#!/usr/bin/env bash
# Cold-boot essentials only. Games and storefronts are installed on first use.
set -euo pipefail

bench=/tmp/kaggle-game-dev-bench
started=$SECONDS
mkdir -p "$bench/logs" /tmp/game-builds /home/gamer/logs
export DEBIAN_FRONTEND=noninteractive

for arch in x86_64-linux-gnu i386-linux-gnu; do
    for library in selkies_input_interposer.so selkies_fake_udev.so; do
        test -s "$bench/lib/$arch/$library" || {
            echo "Missing prebuilt $arch/$library" >&2
            exit 2
        }
    done
done
(cd "$bench" && sha256sum -c SHA256SUMS >/dev/null)

# Pip and APT download independently. Fail startup if either essential install fails.
(
    python3 -m pip install --disable-pip-version-check --prefer-binary \
        'selkies[jupyter]==2.1.0' 'pygame==2.6.1' \
        > "$bench/logs/pip-core.log" 2>&1
) &
pip_pid=$!

apt-get update -qq > "$bench/logs/apt-update.log" 2>&1
apt-get install -y -qq --no-install-recommends \
    xvfb openbox tint2 xterm pulseaudio pulseaudio-utils xauth dbus-x11 \
    python3-tk x11-utils xdotool wmctrl mesa-utils sudo \
    > "$bench/logs/apt-core.log" 2>&1
if ! wait "$pip_pid"; then
    tail -n 70 "$bench/logs/pip-core.log" >&2
    exit 1
fi

if ! id gamer >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G audio,video gamer
fi
install -d -o gamer -g gamer -m 755 /home/gamer/logs /home/gamer/.config
install -d -o gamer -g gamer -m 777 /tmp/game-builds
install -d -o gamer -g gamer -m 700 /home/gamer/.config/pulse
mkdir -p /dev/input

# Gamer can ask only these root-owned, argument-whitelisted installers to run.
cat > /etc/sudoers.d/7bz-gaming <<'EOF'
gamer ALL=(root) NOPASSWD: /bin/bash /tmp/kaggle-game-dev-bench/ensure_gaming.sh, /bin/bash /tmp/kaggle-game-dev-bench/ensure_storefront.sh *
EOF
chmod 440 /etc/sudoers.d/7bz-gaming
visudo -cf /etc/sudoers.d/7bz-gaming >/dev/null

echo "CORE_BOOT_SECONDS=$((SECONDS-started))"
