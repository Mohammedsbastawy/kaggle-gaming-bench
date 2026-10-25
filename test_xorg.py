import remote_exec

script = """
cat > /tmp/test-xorg.conf << 'EOF'
Section "ServerLayout"
    Identifier "HeadlessNVIDIA"
    Screen 0 "Screen0"
EndSection
Section "Device"
    Identifier "GPU0"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration" "true"
    Option "UseDisplayDevice" "none"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "GPU0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Virtual 1280 720
    EndSubSection
EndSection
EOF
Xorg :1 -config /tmp/test-xorg.conf -auth /tmp/kaggle-game-dev-bench/nvidia-Xauthority -nolisten tcp -noreset &
sleep 2
cat /var/log/Xorg.1.log | grep -E '\(EE\)|\(II\) NVIDIA' | tail -25
"""

res = remote_exec.run_cmd(script)
print("Result:\n", res)
