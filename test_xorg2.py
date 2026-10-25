import remote_exec

conf = """
Section "ServerLayout"
    Identifier "HeadlessNVIDIA"
    Screen 0 "Screen0"
EndSection
Section "Device"
    Identifier "GPU0"
    Driver "nvidia"
    BusID "PCI:0:4:0"
    Option "AllowEmptyInitialConfiguration" "true"
    Option "ConnectedMonitor" "DFP-0"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "GPU0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1280x720"
    EndSubSection
EndSection
"""

cmd = f"""
cat << 'EOF' > /tmp/test-xorg2.conf
{conf.strip()}
EOF
Xorg :1 -config /tmp/test-xorg2.conf -auth /tmp/kaggle-game-dev-bench/nvidia-Xauthority -nolisten tcp -noreset > /tmp/xorg1_run.log 2>&1 &
sleep 2
cat /tmp/xorg1_run.log | tail -20
DISPLAY=:1 XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority glxinfo -B 2>&1 | head -15
"""

res = remote_exec.run_cmd(cmd)
print("Result:\n", res)
