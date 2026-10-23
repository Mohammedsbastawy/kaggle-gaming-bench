#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
export HOME="/home/gamer"
export LEGENDARY_CONFIG_PATH="$HOME/.config/heroic/legendaryConfig/legendary"
mkdir -p "$LEGENDARY_CONFIG_PATH" "$HOME/logs"
set -o pipefail

while true; do
    clear
    echo "=================================================================="
    echo "           LEGENDARY CLI - EPIC GAMES NATIVE MANAGER              "
    echo "=================================================================="
    echo " Heroic Epic library: $LEGENDARY_CONFIG_PATH "
    echo " Direct launch uses system Wine and WineD3D diagnostics "
    echo "------------------------------------------------------------------"
    echo " [1] List installed games and launchable apps"
    echo " [2] Quick Launch an installed game (Wolfenstein, Borderlands, etc)"
    echo " [3] Log in to Epic Games (legendary auth)"
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
                echo "Launching $appname via WineD3D (OpenGL software rendering)..."
                WINE_BIN="/usr/bin/wine"
                legendary launch "$appname" --wine "$WINE_BIN" 2>&1 | tee -a /home/gamer/logs/legendary-game.log
                echo "Legendary exit status: ${PIPESTATUS[0]}" | tee -a /home/gamer/logs/legendary-game.log
            fi
            read -p "Press Enter to return to menu..."
            ;;
        3)
            echo ""
            echo "Starting Epic Games authentication..."
            legendary auth
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
                legendary launch "$appname" --wine /usr/bin/wine --dry-run 2>&1 | tee -a /home/gamer/logs/legendary-dry-run.log
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
