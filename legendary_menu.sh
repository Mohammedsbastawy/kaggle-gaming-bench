#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
export HOME="/home/gamer"
export LEGENDARY_CONFIG_PATH="$HOME/.config/heroic/legendaryConfig/legendary"
export BROWSER="/bin/true"
mkdir -p "$LEGENDARY_CONFIG_PATH" "$HOME/.config/legendary" "$HOME/logs"
set -o pipefail

# Source auto-optimizer Wine settings if available
if [ -f "$HOME/.config/gamelab_wine_env.sh" ]; then
    source "$HOME/.config/gamelab_wine_env.sh"
fi

# Ensure credentials and configs are synced on startup
python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py >/dev/null 2>&1 || true

while true; do
    clear
    echo "=================================================================="
    echo "           LEGENDARY CLI - EPIC GAMES NATIVE MANAGER              "
    echo "=================================================================="
    echo " Epic Library Location : $LEGENDARY_CONFIG_PATH"
    echo " Rendering Backend     : WineD3D (OpenGL software rendering / llvmpipe)"
    echo " Shared Session        : Synced automatically with Heroic Games"
    echo "------------------------------------------------------------------"
    echo " [1] List installed games and launchable apps"
    echo " [2] Quick Launch an installed game (Brotato, Wolfenstein, etc)"
    echo " [3] Log in to Epic Games (or check login status)"
    echo " [4] List all games in your Epic Games library"
    echo " [5] Install a game from your Epic library"
    echo " [6] Fix Heroic settings (Disable DXVK / Enable WineD3D)"
    echo " [7] Open an interactive Bash shell as gamer user"
    echo " [8] Print a game's launch command without starting it"
    echo " [0] Exit"
    echo "=================================================================="
    read -p "Select option [0-8]: " choice

    case "$choice" in
        1)
            echo ""
            echo "Syncing Epic library from Heroic..."
            python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py 2>/dev/null || true
            echo ""
            legendary list-installed
            echo ""
            read -p "Press Enter to return to menu..."
            ;;
        2)
            echo ""
            echo "Installed games:"
            legendary list-installed
            echo ""
            read -p "Enter Game App Name (from the list above): " appname
            if [ -n "$appname" ]; then
                if ! sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_gaming.sh; then
                    echo "Game compatibility preparation failed."
                    read -p "Press Enter to return to menu..."
                    continue
                fi
                WINE_BIN=""
                for candidate in "/home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine" \
                                 /home/gamer/.config/heroic/tools/wine/*/bin/wine \
                                 /usr/bin/wine /usr/local/bin/wine /usr/games/wine; do
                    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
                        WINE_BIN="$candidate"
                        break
                    fi
                done
                if [ -z "$WINE_BIN" ]; then
                    echo "Error: No Wine runner found on system!"
                else
                    echo "Checking GPU 3D renderer before launching $appname using runner: $WINE_BIN"
                    export WINEPREFIX="/home/gamer/.wine"
                    
                    # Auto-heal prefix if kernel32.dll is missing
                    if [ ! -f "$WINEPREFIX/drive_c/windows/system32/kernel32.dll" ]; then
                        echo "Initializing Wine prefix with Wine-GE..."
                        WINEBOOT_BIN="$(dirname "$WINE_BIN")/wineboot"
                        if [ -x "$WINEBOOT_BIN" ]; then
                            WINEDLLOVERRIDES="mscoree,mshtml=d" "$WINEBOOT_BIN" --init 2>/dev/null || true
                        fi
                    fi
                    
                    python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py launch "$appname" "$WINE_BIN" 2>&1 | tee -a /home/gamer/logs/legendary-game.log
                    echo "Legendary exit status: ${PIPESTATUS[0]}" | tee -a /home/gamer/logs/legendary-game.log
                fi
            fi
            read -p "Press Enter to return to menu..."
            ;;
        3)
            echo ""
            echo "Checking Epic Games login status..."
            python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py 2>/dev/null || true
            if [ -f "$HOME/.config/heroic/legendaryConfig/legendary/user.json" ] || [ -f "$HOME/.config/legendary/user.json" ]; then
                echo "✓ Found existing Epic Games session!"
                legendary status 2>/dev/null
                echo ""
                read -p "Already logged in! Do you want to re-authenticate with a new code? (y/N): " reauth
                if [[ ! "$reauth" =~ ^[Yy]$ ]]; then
                    read -p "Press Enter to return to menu..."
                    continue
                fi
            fi

            echo ""
            echo "=================================================================="
            echo "                   EPIC GAMES LOGIN INSTRUCTIONS                  "
            echo "=================================================================="
            echo " 1. Open this URL in your PC browser (Chrome/Edge/Firefox):"
            echo "    https://legendary.gl/epiclogin"
            echo ""
            echo " 2. Sign in with your Epic Games account."
            echo ""
            echo " 3. The page will display a JSON code containing 'authorizationCode'."
            echo "    Example: {\"authorizationCode\": \"3a7b9c1d2e...\"}"
            echo ""
            echo " 4. Copy the authorizationCode value (or the whole JSON text)"
            echo "    and paste it into the prompt below."
            echo "=================================================================="
            echo ""
            legendary auth
            python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py 2>/dev/null || true
            echo ""
            read -p "Press Enter to return to menu..."
            ;;
        4)
            echo ""
            legendary list
            echo ""
            read -p "Press Enter to return to menu..."
            ;;
        5)
            echo ""
            read -p "Enter Game App Name to install: " install_app
            if [ -n "$install_app" ]; then
                legendary install "$install_app"
                python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py 2>/dev/null || true
            fi
            read -p "Press Enter to return to menu..."
            ;;
        6)
            echo ""
            python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py
            echo ""
            read -p "Press Enter to return to menu..."
            ;;
        7)
            echo "Dropping into shell as user gamer. Type 'exit' to return."
            bash
            ;;
        8)
            legendary list-installed
            read -p "Enter Game App Name: " appname
            if [ -n "$appname" ]; then
                WINE_BIN=""
                for candidate in "/home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine" \
                                 /home/gamer/.config/heroic/tools/wine/*/bin/wine \
                                 /usr/bin/wine /usr/local/bin/wine /usr/games/wine; do
                    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
                        WINE_BIN="$candidate"
                        break
                    fi
                done
                legendary launch "$appname" --wine "${WINE_BIN:-wine}" --dry-run 2>&1 | tee -a /home/gamer/logs/legendary-dry-run.log
                echo "Legendary dry-run exit status: ${PIPESTATUS[0]}" | tee -a /home/gamer/logs/legendary-dry-run.log
            fi
            read -p "Press Enter to return to menu..."
            ;;
        0)
            break
            ;;
        *)
            echo "Invalid option."
            sleep 1
            ;;
    esac
done
