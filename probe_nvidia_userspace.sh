#!/usr/bin/env bash
# High-Performance NVIDIA Userspace 3D Driver & Vulkan ICD Provisioner for Kaggle
# Offloads 3D rendering to NVIDIA GPU hardware (OpenGL & Vulkan) without modifying the kernel.
set -uo pipefail

bench=/tmp/kaggle-game-dev-bench
work="$bench/nvidia-userspace-probe"
mkdir -p "$work" "$work/lib64" "$work/lib32"

echo "=========================================================="
echo "    NVIDIA 3D HARDWARE ACCELERATION PROVISIONER           "
echo "=========================================================="

if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "Notice: nvidia-smi not found. Running in CPU-only environment."
    exit 0
fi

version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n 1 | tr -d '[:space:]')
if [[ ! "$version" =~ ^[0-9]+(\.[0-9]+)+$ ]]; then
    echo "Notice: Cannot determine loaded NVIDIA driver version ($version)."
    exit 0
fi

major=$(echo "$version" | cut -d. -f1)
echo "▶ Host NVIDIA Driver Version detected: $version (Major Branch: $major)"

installed_ok=false

# Tier 1: Fast APT package installation (~10 seconds)
echo "▶ Tier 1: Checking official NVIDIA 3D graphics packages for driver $major..."
if [ "$(id -u)" -eq 0 ]; then
    apt-get update -o DPkg::Lock::Timeout=60 -qq 2>/dev/null || true
    for pkg in "libnvidia-gl-$major" "libnvidia-gl-${major}-server"; do
        if apt-cache show "$pkg" >/dev/null 2>&1; then
            echo "▶ Found matching repository package: $pkg. Installing userspace libraries..."
            apt-get install -y --no-install-recommends \
                -o DPkg::Lock::Timeout=120 -o APT::Get::Assume-Yes=true \
                "$pkg" "${pkg}:i386" vulkan-tools 2>/dev/null || \
            apt-get install -y --no-install-recommends \
                -o DPkg::Lock::Timeout=120 -o APT::Get::Assume-Yes=true \
                "$pkg" vulkan-tools 2>/dev/null || true
            break
        fi
    done
fi

# Verify if 64-bit GLX/EGL library is now present in standard paths
if ldconfig -p | grep -q "libGLX_nvidia.so.0" || [ -f "/usr/lib/x86_64-linux-gnu/libGLX_nvidia.so.0" ]; then
    echo "✓ NVIDIA 3D graphics libraries verified via system package manager."
    installed_ok=true
fi

# Tier 2: Direct matching NVIDIA archive extraction if APT package was unavailable
if [ "$installed_ok" = false ]; then
    echo "▶ Tier 2: Fetching matching NVIDIA userspace binary archive for $version..."
    runfile="$work/NVIDIA-Linux-x86_64-$version.run"
    if [ ! -f "$runfile" ] || [ $(stat -c%s "$runfile" 2>/dev/null || echo 0) -lt 10000000 ]; then
        urls=(
            "https://us.download.nvidia.com/tesla/$version/NVIDIA-Linux-x86_64-$version.run"
            "https://us.download.nvidia.com/XFree86/Linux-x86_64/$version/NVIDIA-Linux-x86_64-$version.run"
            "https://download.nvidia.com/XFree86/Linux-x86_64/$version/NVIDIA-Linux-x86_64-$version.run"
        )
        for u in "${urls[@]}"; do
            echo "Attempting download from: $u"
            if curl -fL --connect-timeout 10 --max-time 120 "$u" -o "$runfile" 2>/dev/null; then
                if [ -f "$runfile" ] && [ $(stat -c%s "$runfile") -gt 10000000 ]; then
                    echo "✓ Downloaded matching NVIDIA installer: $(stat -c%s "$runfile") bytes"
                    break
                fi
            fi
            rm -f "$runfile"
        done
    fi

    driver="$work/NVIDIA-Linux-x86_64-$version"
    if [ -f "$runfile" ] && [ ! -d "$driver" ]; then
        echo "▶ Extracting userspace graphics components from archive..."
        (cd "$work" && sh "$runfile" --extract-only) 2>/dev/null || true
    fi

    if [ -d "$driver" ]; then
        link_libraries() {
            local src=$1 dst=$2
            mkdir -p "$dst"
            find "$src" -maxdepth 1 -type f \( -name 'libnvidia-*.so*' -o -name 'libGLX_nvidia.so*' -o -name 'libEGL_nvidia.so*' \) -exec cp -sf {} "$dst/" \; 2>/dev/null || true
        }
        link_libraries "$driver" "$work/lib64"
        [ -d "$driver/32" ] && link_libraries "$driver/32" "$work/lib32"

        for libdir in "$work/lib64" "$work/lib32"; do
            for name in libGLX_nvidia libEGL_nvidia; do
                vlib=$(find "$libdir" -name "${name}.so.*" 2>/dev/null | head -n1)
                [ -n "$vlib" ] && ln -sfn "$(basename "$vlib")" "$libdir/${name}.so.0" 2>/dev/null || true
            done
        done
        installed_ok=true
    fi
fi

# Step 3: Register GLVND and Vulkan ICD manifests
mkdir -p /usr/share/glvnd/egl_vendor.d /etc/vulkan/icd.d /usr/share/vulkan/icd.d "$work"

cat > "$work/10_nvidia.json" <<'EOF'
{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}
EOF

cat > "$work/nvidia_icd.json" <<'EOF'
{"file_format_version":"1.0.0","ICD":{"library_path":"libGLX_nvidia.so.0","api_version":"1.3.0"}}
EOF

cat > "$work/nvidia_egl_icd.json" <<'EOF'
{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0","api_version":"1.3.0"}}
EOF

cp -f "$work/10_nvidia.json" /usr/share/glvnd/egl_vendor.d/10_nvidia.json 2>/dev/null || true
cp -f "$work/nvidia_icd.json" /etc/vulkan/icd.d/nvidia_icd.json 2>/dev/null || true
cp -f "$work/nvidia_icd.json" /usr/share/vulkan/icd.d/nvidia_icd.json 2>/dev/null || true

# Step 4: Register libraries with dynamic linker
if [ -d "$work/lib64" ] && [ "$(ls -A "$work/lib64" 2>/dev/null)" ]; then
    echo "$work/lib64" > /etc/ld.so.conf.d/nvidia-gpu.conf
    [ -d "$work/lib32" ] && [ "$(ls -A "$work/lib32" 2>/dev/null)" ] && echo "$work/lib32" >> /etc/ld.so.conf.d/nvidia-gpu.conf
fi
ldconfig 2>/dev/null || true

# Step 5: Write environment exports
{
    printf 'export __EGL_VENDOR_LIBRARY_FILENAMES="/usr/share/glvnd/egl_vendor.d/10_nvidia.json"\n'
    printf 'export VK_DRIVER_FILES="/etc/vulkan/icd.d/nvidia_icd.json"\n'
    printf 'export VK_ICD_FILENAMES="/etc/vulkan/icd.d/nvidia_icd.json"\n'
    if [ -d "$work/lib64" ] && [ "$(ls -A "$work/lib64" 2>/dev/null)" ]; then
        printf 'export LD_LIBRARY_PATH="%s:%s${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n' "$work/lib64" "$work/lib32"
        printf 'export GAMELAB_NVIDIA_LIB32="%s"\n' "$work/lib32"
    fi
} > "$work/env.sh"

echo "✓ NVIDIA userspace graphics bridge successfully configured."
echo "  Vulkan ICD: /etc/vulkan/icd.d/nvidia_icd.json"
echo "  EGL Vendor: /usr/share/glvnd/egl_vendor.d/10_nvidia.json"
