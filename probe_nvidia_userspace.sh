#!/usr/bin/env bash
# Experimental, isolated NVIDIA userspace injection. Run inside Kaggle only.
# It never installs a kernel module or replaces system libraries.
set -euo pipefail

bench=/tmp/kaggle-game-dev-bench
work="$bench/nvidia-userspace-probe"
mkdir -p "$work"

version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n 1 | tr -d '[:space:]')
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "Cannot determine a valid loaded NVIDIA driver version: $version" >&2
    exit 2
fi

runfile="$work/NVIDIA-Linux-x86_64-$version.run"
url="https://us.download.nvidia.com/XFree86/Linux-x86_64/$version/NVIDIA-Linux-x86_64-$version.run"
driver="$work/NVIDIA-Linux-x86_64-$version"
if [[ ! -d "$driver" ]]; then
    if [[ $# -ge 1 ]]; then
        cp -- "$1" "$runfile"
    else
        echo "Downloading matching NVIDIA userspace archive: $url"
        curl -fL --retry 2 --connect-timeout 15 "$url" -o "$runfile"
    fi
    expected="${GAMELAB_NVIDIA_RUN_SHA256:-}"
    if [[ -z "$expected" ]]; then
        checksumfile="$work/$(basename "$runfile").sha256sum"
        curl -fLsS --retry 2 "$url.sha256sum" -o "$checksumfile"
        expected=$(awk 'NR == 1 { print $1 }' "$checksumfile")
    fi
    if [[ ! "$expected" =~ ^[[:xdigit:]]{64}$ ]]; then
        echo "No valid SHA-256 checksum for the NVIDIA archive" >&2
        exit 3
    fi
    printf '%s  %s\n' "$expected" "$runfile" | sha256sum -c -
    (cd "$work" && sh "$runfile" --extract-only)
    rm -f "$runfile"
fi
if [[ ! -d "$driver" ]]; then
    echo "NVIDIA archive extraction did not create $driver" >&2
    exit 3
fi

link_libraries() {
    local source_dir=$1 destination=$2
    mkdir -p "$destination"
    while IFS= read -r -d '' library; do
        ln -sfn "$library" "$destination/$(basename "$library")"
    done < <(find "$source_dir" -maxdepth 1 -type f \
        \( -name 'libnvidia-*.so*' -o -name 'libGLX_nvidia.so*' \
           -o -name 'libEGL_nvidia.so*' -o -name 'libGLESv1_CM_nvidia.so*' \
           -o -name 'libGLESv2_nvidia.so*' \) -print0)
}

lib64="$work/lib64"
lib32="$work/lib32"
link_libraries "$driver" "$lib64"
if [[ -d "$driver/32" ]]; then
    link_libraries "$driver/32" "$lib32"
fi
for libdir in "$lib64" "$lib32"; do
    for name in libGLX_nvidia libEGL_nvidia; do
        versioned="$libdir/$name.so.$version"
        if [[ -f "$versioned" ]]; then
            ln -sfn "$versioned" "$libdir/$name.so.0"
        fi
    done
done
for required in "$lib64/libGLX_nvidia.so.0" "$lib64/libEGL_nvidia.so.0" \
                "$lib64/libnvidia-glcore.so.$version" "$lib64/libnvidia-eglcore.so.$version"; do
    if [[ ! -f "$required" ]]; then
        echo "Archive lacks required graphics component: $required" >&2
        exit 4
    fi
done

# Bare sonames let 64- and 32-bit loaders choose the matching ELF class.
cp "$bench/config/egl/10_nvidia.json" "$work/10_nvidia.json"
cp "$bench/config/vulkan/nvidia_icd_glx.json" "$work/nvidia_icd.json"
cp "$bench/config/vulkan/nvidia_icd_egl.json" "$work/nvidia_egl_icd.json"
selected_icd="$work/nvidia_icd.json"
if command -v vulkaninfo >/dev/null; then
    probe_library_path="$lib64:$lib32${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    for manifest in "$work/nvidia_icd.json" "$work/nvidia_egl_icd.json"; do
        summary=$(env -u LD_PRELOAD LD_LIBRARY_PATH="$probe_library_path" \
            VK_DRIVER_FILES="$manifest" VK_ICD_FILENAMES="$manifest" \
            vulkaninfo --summary 2>&1 || true)
        if grep -Eq 'deviceName[[:space:]]*=.*(Tesla|NVIDIA)' <<< "$summary"; then
            selected_icd="$manifest"
            break
        fi
    done
fi
{
    printf 'export LD_LIBRARY_PATH=%q:%q${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\n' "$lib64" "$lib32"
    printf 'export __EGL_VENDOR_LIBRARY_FILENAMES=%q\n' "$work/10_nvidia.json"
    printf 'export VK_DRIVER_FILES=%q\n' "$selected_icd"
    printf 'export VK_ICD_FILENAMES=%q\n' "$selected_icd"
    printf 'export GAMELAB_NVIDIA_LIB32=%q\n' "$lib32"
} > "$work/env.sh"

if [ "$(id -u)" -eq 0 ]; then
    mkdir -p /usr/share/glvnd/egl_vendor.d /etc/vulkan/icd.d
    cp -f "$work/10_nvidia.json" /usr/share/glvnd/egl_vendor.d/10_nvidia.json 2>/dev/null || true
    cp -f "$selected_icd" /etc/vulkan/icd.d/nvidia_icd.json 2>/dev/null || true
    echo "$lib64" > /etc/ld.so.conf.d/nvidia-gpu.conf
    if [[ -d "$lib32" ]]; then
        echo "$lib32" >> /etc/ld.so.conf.d/nvidia-gpu.conf
    fi
    ldconfig 2>/dev/null || true
fi

echo "Isolated driver environment: $work/env.sh"
echo "Selected Vulkan ICD: $selected_icd"
echo "32-bit GL library: $(if [[ -f "$lib32/libGLX_nvidia.so.0" ]]; then echo present; else echo missing; fi)"
