# Mouse look on the NVIDIA Xorg stream

The 8081 desktop uses Selkies WebSockets input on NVIDIA Xorg `:1`. Without
`/dev/uinput`, Selkies injects mouse movement through XTEST. In the live
container, `xinput test-xi2 --root` reported `RawMotion` with the exact
`xdotool mousemove_relative` delta, and that delta rotated Wolfenstein's
camera in active gameplay. A kernel uinput device is therefore not required
for this X11/Wine mouse path. The four virtual gamepad sockets are separate.

Browser pointer lock is required for continuous 360-degree mouse movement.
The Codex in-app browser used for the live check rejected Selkies Gaming Mode:
its console reported `Fullscreen request failed: TypeError: Permissions check
failed`, and a direct `requestPointerLock()` failed as well. The HUD now states
that restriction when it happens. Open the same 8081 stream URL in a normal
Chrome or Edge tab, click the game, and enable Gaming Mode there. This is still
the single desktop and single port; the browser surface changes.

The HUD's input-mode endpoint now resolves from either 8080 or 8081. Mouse
and keyboard mode is the default. Games started by `gpu_runtime.py` or
`launch_idtech5.py` in that mode omit the Selkies gamepad interposer and set
`winebus.sys=d`, preventing virtual Xbox devices from competing with mouse
look. Gamepad mode retains the interposer and Wine bus. Restart a running game
after changing the mode. The Wine prefix already sets
`HKCU\Software\Wine\DirectInput\MouseWarpOverride=force` and
`HKCU\Software\Wine\X11 Driver\GrabPointer=Y`; the direct launcher refreshes
those values when starting a game.

To diagnose a live session:

```bash
DISPLAY=:1 XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority xinput list
DISPLAY=:1 XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority xinput test-xi2 --root
curl -s http://127.0.0.1:8766/input-mode
```
