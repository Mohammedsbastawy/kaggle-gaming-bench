# Community graphics-driver experiments for Kaggle

The Version 28 observations establish a missing *working graphics stack*, not
that every graphics ioctl is blocked. These experiments distinguish a missing
userspace package from a blocked kernel/device path. None is a verified AAA
gaming result in Kaggle yet.

## What others actually demonstrated

| Evidence | Working result | What it does not establish |
| --- | --- | --- |
| [Chrome team on Colab](https://developer.chrome.com/blog/supercharge-web-ai-testing) | `apt-get install vulkan-tools libnvidia-gl-525` changed a T4 from SwiftShader to an NVIDIA renderer and enabled hardware WebGL/WebGPU in headless Chrome. | Wine/Steam display presentation and Kaggle Version 28. |
| [Colab T4 Vulkan trace](https://forums.developer.nvidia.com/t/vk-ext-headless-surface-is-missing-in-vulkaninfo/276615) | After NVIDIA graphics packages, `vulkaninfo` identified a discrete Tesla T4 with NVIDIA driver. | A Vulkan window surface: `VK_EXT_headless_surface` was absent. |
| [Habitat-Sim headless report](https://github.com/facebookresearch/habitat-sim/issues/1511) | Users extracted a driver `.run` matching `nvidia-smi`, exposed `libEGL_nvidia.so.0` through a private GLVND manifest, and reported successful GPU-rendered Habitat episodes. | Container device restrictions and game presentation. |
| [MuJoCo Docker issue](https://github.com/google-deepmind/mujoco/issues/572) and [dm_control Colab tutorial](https://github.com/google-deepmind/dm_control/blob/main/tutorial.ipynb) | A missing `10_nvidia.json` can prevent an already-present NVIDIA EGL library from being selected. | A JSON file alone cannot supply the vendor library. |
| [Kaggle Vulkan discussion](https://www.kaggle.com/discussions/general/666332) and [notebook source](https://www.kaggle.com/code/lbsbmsu/how-to-enable-vulkan-gpu-compute-in-kaggle-r/) | Author reports Vulkan compute after `apt-get install nvidia-driver-570` in a Kaggle R image. | The pulled notebook source has no saved execution output proving device identity; its image and driver may differ from this Python notebook. |
| [Steam Headless startup script](https://github.com/Steam-Headless/docker-steam-headless/blob/master/overlay/etc/cont-init.d/60-configure_gpu_driver.sh) | Downloads the matching `.run` and installs userspace plus 32-bit libraries while skipping kernel modules. | Its normal hosts expose graphics devices; it does not demonstrate a Kaggle bypass. |
| [Colab-Cloud-Gaming](https://github.com/kmille36/Colab-Cloud-Gaming) | Claims playable Steam streaming. | Its `ColabSteam` payload is an ELF binary, not an auditable bootstrap script, and the repository does not publish an NVIDIA renderer/Vulkan trace. |

## Experiment A: matching Ubuntu userspace package

This is the closest analogue of the Chrome team's Colab repair. It is an
**opt-in notebook experiment**, not part of automatic `setup.sh`:

```bash
host=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d '[:space:]')
major=${host%%.*}
echo "loaded host driver: $host"
apt-cache policy "libnvidia-gl-$major" "libnvidia-gl-$major:i386"
apt-get -s install --no-install-recommends \
  "libnvidia-gl-$major" "libnvidia-gl-$major:i386"
```

Continue only if the candidate package versions contain the **exact** host
driver version and the simulated transaction does not replace the kernel or
CUDA stack. Then install the two user libraries and probe:

```bash
apt-get install -y --no-install-recommends \
  "libnvidia-gl-$major" "libnvidia-gl-$major:i386" vulkan-tools
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose
/opt/VirtualGL/bin/eglinfo -e
```

`libnvidia-gl-580` is available in Ubuntu Noble with both bitnesses, including
the EGL/GLX vendor libraries; package availability for the live host version
must be checked at run time. See the [Ubuntu i386 package file list](https://packages.ubuntu.com/noble-updates/i386/libnvidia-gl-580/filelist).

## Experiment B: isolated `.run` extraction

The repository's [probe_nvidia_userspace.sh](probe_nvidia_userspace.sh) follows
the Habitat/Steam Headless approach without replacing `/usr/lib` or installing
a kernel module. It downloads the **exact** loaded driver version from NVIDIA,
extracts the archive, links 64- and 32-bit vendor libraries inside
`/tmp/kaggle-game-dev-bench/nvidia-userspace-probe`, writes private EGL and
Vulkan manifests, then runs EGL/Vulkan/runtime diagnostics. For a previously
verified download, pass its path as the first argument and optionally set
`GAMELAB_NVIDIA_RUN_SHA256`.

Run the probe as the unprivileged `gamer` account after notebook setup (the
notebook makes the bench directory writable). This also lets the Vulkan loader
honor the private `VK_DRIVER_FILES` override; it ignores that override for
elevated applications. From a root notebook shell:

```bash
runuser -u gamer -- bash /tmp/kaggle-game-dev-bench/probe_nvidia_userspace.sh
```

The full NVIDIA runfile can be hundreds of MB. If the probe confirms
`egl_device=true` **and** `virtualgl=true`, opt the next desktop session into
the private libraries before running the notebook's Selkies startup cell:

```python
import os
os.environ['GAMELAB_USE_INJECTED_DRIVER'] = '1'
```

For a terminal-only probe without a desktop restart:

```bash
source /tmp/kaggle-game-dev-bench/nvidia-userspace-probe/env.sh
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose
```

If NVIDIA Vulkan succeeds, source the environment and rerun `setup.sh` from
a **root notebook shell** to fetch DXVK, then retest `vulkan_window`:

```bash
source /tmp/kaggle-game-dev-bench/nvidia-userspace-probe/env.sh
bash /tmp/kaggle-game-dev-bench/setup.sh
runuser -u gamer -- bash -c 'source /tmp/kaggle-game-dev-bench/nvidia-userspace-probe/env.sh; python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose'
```

DXVK is eligible only if its Vulkan
surface on the streamed display works. For WineD3D, VirtualGL's EGL backend
(`vglrun -d egl0`) can copy GPU OpenGL output to Xvfb; the runtime checks the
actual NVIDIA vendor before launching. The `egl_device_display` diagnostic
identifies a different EGL index if needed. `EGL_PLATFORM=device` is useful
for applications that create an EGL device context, but it does not redirect
GLX or a Windows game by itself. [GLVND recognizes the `device` platform](https://github.com/NVIDIA/libglvnd/blob/master/src/EGL/libegl.c);
[VirtualGL documents its `eglN` backend](https://github.com/VirtualGL/virtualgl/blob/main/doc/advancedconfig.txt).

The NVIDIA driver itself documents that `libEGL_nvidia.so.0` can also serve
as a Vulkan ICD on systems without X11 client libraries. The probe tests
both NVIDIA GLX and EGL ICD manifests. [NVIDIA component listing](https://download.nvidia.com/XFree86/Linux-x86_64/580.178.04/README/installedcomponents.html);
[Khronos loader overrides](https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderDriverInterface.md).

## Paths that do not translate existing games

`fake-udev` in this project synthesizes *input device discovery*. It is not
an OpenGL/Vulkan implementation. [`libvdpau-va-gl`](https://github.com/i-rinat/libvdpau-va-gl)
maps video decode/presentation API calls onto existing VA-API/OpenGL; it
requires graphics rather than creating it. A fabricated `/dev/dri/renderD128`
path cannot create a backing DRM kernel render device or grant its ioctls.
Mesa's [NVK driver](https://docs.mesa3d.org/drivers/nvk.html) is a real
open-source Vulkan implementation, but its [device creation code](https://fossies.org/linux/mesa/src/nouveau/vulkan/nvkmd/nouveau/nvkmd_nouveau_pdev.c)
requires a Nouveau DRM render node and rejects a different kernel driver;
it cannot attach to the proprietary `/dev/nvidia0` compute interface.
No reviewed project provides a drop-in WineD3D/DXVK-to-CUDA interposer for
unmodified games. [Nvdiffrast](https://nvlabs.github.io/nvdiffrast/) has a
CUDA rasterizer for triangle tensors and is useful for custom research
benchmarks, but implements neither OpenGL nor Direct3D game APIs.

Stop condition: if the **matching** private libraries are present but EGL
still cannot initialize an NVIDIA device, the failure has moved beyond
GLVND/ICD discovery. Record `eglinfo`, `vulkaninfo`, and `gpu_runtime.py
diagnose` output and keep the CPU fallback; do not infer success from
`nvidia-smi` or NVENC usage.
