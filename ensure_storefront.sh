#!/usr/bin/env bash
# Root-owned, argument-whitelisted on-demand storefront installer.
set -euo pipefail
store=${1:-}
case "$store" in
    legendary|steam|heroic|lutris|minigalaxy) ;;
    *) echo "Unsupported storefront: $store" >&2; exit 2 ;;
esac
exec 9>/opt/7bz-gaming.lock
flock 9
stamp="/opt/7bz-storefront-$store.ready"
[[ -f "$stamp" ]] && exit 0
export DEBIAN_FRONTEND=noninteractive
echo "Installing $store on first launch..."
case "$store" in
    legendary)
        python3 -m pip install --disable-pip-version-check --prefer-binary legendary-gl
        ;;
    steam)
        dpkg --add-architecture i386
        apt-get update -qq
        deb=/tmp/steam_latest.deb
        curl -fLsS --retry 2 https://repo.steampowered.com/steam/archive/stable/steam_latest.deb -o "$deb"
        test "$(stat -c%s "$deb")" -gt 1000000
        apt-get install -y -qq --no-install-recommends "$deb"
        ;;
    heroic)
        deb=/tmp/heroic-2.22.4.deb
        curl -fLsS --retry 2 \
            https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/releases/download/v2.22.4/Heroic-2.22.4-linux-amd64.deb \
            -o "$deb"
        test "$(stat -c%s "$deb")" -gt 10000000
        apt-get install -y -qq --no-install-recommends "$deb"
        ;;
    lutris|minigalaxy)
        sed -i 's/Components: main universe/Components: main universe multiverse/g' \
            /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null || true
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends "$store"
        ;;
esac
touch "$stamp"
echo "$store ready"
