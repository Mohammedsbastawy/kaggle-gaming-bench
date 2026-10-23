# GPU 3D deployment and CPU fallback

## Version 28 result

The live Kaggle container reports `/dev/nvidia0` and `/dev/nvidiactl`, but no
`/dev/nvidia-modeset`, NVIDIA Vulkan ICD, NVIDIA 32-bit GL, DXVK files, or
working NVIDIA GLX/VirtualGL renderer. `glxinfo` identifies llvmpipe and
`vkCreateInstance` returns `ERROR_INCOMPATIBLE_DRIVER`. The 60 FPS Selkies
stream and NVENC utilization measure capture/encoding, not game FPS. Do not
interpret CUDA or NVENC access as graphics access.

Run one final independent EGL check after updating the notebook or checkout:

```bash
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose
/opt/VirtualGL/bin/eglinfo -e
/opt/VirtualGL/bin/eglinfo egl0
```

`egl_device` must be true and `egl_renderer` must identify an NVIDIA OpenGL
renderer. Then `vglrun -d egl0 glxinfo -B` must report NVIDIA as **OpenGL
vendor** (use `egl_device_display` in place of `egl0` if the probe selects
another GPU), and an actual game must render correctly on Xvfb. The EGL device
backend does not need an NVIDIA Xorg or `/dev/nvidia-modeset`; it does need a
working NVIDIA graphics userspace driver and accessible GPU device interfaces.
VirtualGL redirects OpenGL and WineD3D, not Direct3D or Vulkan by itself.
DXVK requires a working NVIDIA Vulkan ICD and an X11 Vulkan surface on the
captured display. Zink requires Vulkan too; Lavapipe and SwiftShader are CPU
renderers and cannot unlock the T4.

If `eglinfo egl0` fails, inspect the **host driver version** and mounted
graphics libraries before further changes:

```bash
nvidia-smi --query-gpu=driver_version --format=csv,noheader
ldconfig -p | grep -E 'lib(EGL_nvidia|GLX_nvidia|nvidia-glcore|vulkan)\.so'
find /usr/share/glvnd/egl_vendor.d /etc/vulkan/icd.d /usr/share/vulkan/icd.d \
  -maxdepth 1 -type f -print 2>/dev/null
ls -l /dev/nvidia* /dev/dri/* 2>/dev/null
```

Installing an **exactly compatible** NVIDIA graphics userspace package is a
bounded experiment only if the platform permits it. Back up the environment
first and retest `eglinfo`, GLX, Vulkan, and NVENC after installation. Installing
`libGLX_nvidia.so` alone, symlinking it, or writing a JSON ICD without its
matching implementation libraries cannot create GPU rendering. Never install
an NVIDIA kernel driver inside the notebook container. The host's container
runtime controls device and library exposure, so a failed EGL device probe
should end GPU attempts in that Kaggle session **after** the matching
userspace experiment in [community 3D research](COMMUNITY_3D_RESEARCH.md).

## Explicit CPU mode

The Legendary GUI and menu use `gpu_runtime.py launch`. If a game must be
tested on software rendering, start the desktop with
`GAMELAB_ALLOW_SOFTWARE=1` in its environment (or export it in the launcher's
shell). For the Kaggle notebook, run `os.environ['GAMELAB_ALLOW_SOFTWARE']='1'`
in a Python cell **before** the Selkies startup cell. The wrapper then selects
WineD3D + llvmpipe, limits llvmpipe worker
threads to the container's effective CPU quota minus headroom for Selkies,
runs the game at lower scheduling priority, and tries a temporary 854x480
Xvfb mode. It restores the prior mode when the game exits.

```bash
export GAMELAB_ALLOW_SOFTWARE=1
export GAMELAB_SOFTWARE_RESOLUTION=640x360  # 854x480 default; off disables
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py launch APP_NAME /path/to/wine
```

`xrandr` may reject a mode that the live Xvfb session does not expose. In that
case the wrapper reports the failure and keeps the current desktop mode. Set
the **game's own render resolution** to 640x360 or 854x480 as well, use its
lowest quality/shadow settings, and limit in-game FPS to 15–30 if possible.
Lowering 1280x720 to 640x360 reduces pixel count by 75%, but geometry,
shader compilation, and Wine translation can still dominate. `LP_NUM_THREADS`
can be overridden explicitly for benchmarking. `MESA_GLTHREAD=true`, fake
GL-version overrides, forced shader skipping, FSR after software rasterization,
and Lavapipe/SwiftShader substitution are not general AAA performance fixes.
This CPU profile is for 2D/lightweight titles and functional testing; the
observed 2–5 FPS AAA titles need graphics passthrough or a different host.

## Full graphics host

On an Ubuntu GPU VM that you control, install the host NVIDIA driver and
NVIDIA Container Toolkit, configure Docker's NVIDIA runtime, then create the
container with the required capabilities **at creation time**. Use an image
containing this repository, its Python environment, Wine, Selkies, and 32-bit
system libraries; the current Kaggle notebook assumes `/kaggle/working` and
Kaggle's Jupyter proxy and needs a provider-specific start page and URL for
standalone hosting.

```bash
docker run --rm -it --gpus all \
  --shm-size=2g \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics,display,compat32 \
  -p 8080:8080 \
  YOUR_BENCH_IMAGE:TAG bash

# In the container, before games:
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose
/opt/VirtualGL/bin/eglinfo egl0
```

Acceptance criteria: NVIDIA EGL or GLX vendor/renderer, NVIDIA `vulkaninfo`
physical device, a successful Vulkan X11 surface on the actual stream display,
working 32- and 64-bit graphics libraries, and a measured game FPS/GPU graphics
load while NVENC runs. If Xvfb lacks NVIDIA Vulkan WSI, use the repository's
headless NVIDIA Xorg path with VirtualGL for OpenGL, or a Vulkan-capable
display server captured by Selkies. `vglrun` does not bridge DXVK's Vulkan
swapchain into Xvfb.

Provider choices:

| Provider | Starting point | Required check |
| --- | --- | --- |
| AWS EC2 | G4dn (T4), with NVIDIA GRID/gaming driver or a suitable NVIDIA AMI | Host Docker/NVIDIA toolkit under your control; verify graphics before app deployment. |
| Google Compute Engine | G2 (L4) or N1 + T4, using the supported RTX Virtual Workstation driver for visualization | Enable virtual workstation support as required and install its matching driver. |
| RunPod | GPU Pod with a custom image | Managed Pod graphics mounts are not guaranteed; run the probes before installing games. |
| Vast.ai | GPU instance with custom image and container environment options | Host offering and container graphics mounts vary; run the probes before installing games. |

On a managed Pod without host Docker control, request
`NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics,display,compat32`
**in its template/environment before creation**, then verify rather than
assuming this setting changes its runtime mounts. A VM with host Docker
control is the most reproducible deployment target.

References: [NVIDIA Container Toolkit driver capabilities](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html),
[NVIDIA headless EGL](https://developer.nvidia.com/blog/egl-eye-opengl-visualization-without-x-server/),
[VirtualGL EGL backend](https://github.com/VirtualGL/virtualgl/blob/main/doc/advancedconfig.txt),
[Mesa llvmpipe](https://docs.mesa3d.org/drivers/llvmpipe.html),
[AWS graphics driver options](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/install-nvidia-driver.html),
[Google Cloud Linux virtual workstation](https://docs.cloud.google.com/compute/docs/virtual-workstation/linux-gpu),
[RunPod custom Pod images](https://docs.runpod.io/runpodctl/reference/runpodctl-remove-pods), and
[Vast.ai Docker environment](https://github.com/vast-ai/docs/blob/main/guides/instances/docker-environment.mdx).
