"""Sample a live game session without confusing stream FPS with game FPS.

Run after entering repeatable gameplay. Save one JSON report per configuration.
The HUD's stream FPS and NVIDIA encoder usage are deliberately not game FPS.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import subprocess
import time


def cpu_stat():
    path = Path("/sys/fs/cgroup/cpu.stat")
    try:
        return {key: int(value) for key, value in
                (line.split() for line in path.read_text().splitlines())}
    except (OSError, ValueError):
        return {}


def gpus():
    try:
        output = subprocess.check_output([
            "nvidia-smi", "--query-gpu=index,utilization.gpu,utilization.encoder,memory.used",
            "--format=csv,noheader,nounits"], text=True, timeout=5,
            stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return []
    result = []
    for line in output.splitlines():
        fields = [part.strip() for part in line.split(",")]
        if len(fields) != 4:
            continue
        try:
            result.append(dict(index=int(fields[0]), gpu_percent=int(fields[1]),
                               encoder_percent=int(fields[2]), memory_mib=int(fields[3])))
        except ValueError:
            continue
    return result


def summarize(samples):
    if not samples:
        return None
    return dict(mean=round(statistics.mean(samples), 2),
                maximum=max(samples))


def benchmark(seconds, interval):
    start = time.monotonic()
    previous_time = start
    previous_cpu = cpu_stat()
    cpu_cores = []
    throttled_ms_per_second = []
    gpu_samples = {}
    while True:
        remaining = seconds - (time.monotonic() - start)
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
        now = time.monotonic()
        current_cpu = cpu_stat()
        elapsed = now - previous_time
        if "usage_usec" in current_cpu and "usage_usec" in previous_cpu:
            cpu_cores.append((current_cpu["usage_usec"] - previous_cpu["usage_usec"])
                             / (elapsed * 1_000_000))
        if "throttled_usec" in current_cpu and "throttled_usec" in previous_cpu:
            throttled_ms_per_second.append(
                (current_cpu["throttled_usec"] - previous_cpu["throttled_usec"])
                / (elapsed * 1000))
        previous_cpu, previous_time = current_cpu, now
        for gpu in gpus():
            bucket = gpu_samples.setdefault(gpu["index"], dict(gpu_percent=[],
                                    encoder_percent=[], memory_mib=[]))
            for metric in ("gpu_percent", "encoder_percent", "memory_mib"):
                bucket[metric].append(gpu[metric])
    return dict(cpu_cores=summarize(cpu_cores),
                cpu_throttled_ms_per_second=summarize(throttled_ms_per_second),
                gpus={index: {name: summarize(values) for name, values in metrics.items()}
                      for index, metrics in gpu_samples.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="game/backend/settings for this run")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--game-fps", type=float,
                        help="measured in-game FPS, never Selkies stream FPS")
    parser.add_argument("--input-latency-ms", type=float,
                        help="client HUD latency measured during this run")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seconds < 1 or args.interval <= 0:
        parser.error("seconds and interval must be positive")
    report = dict(timestamp=datetime.now(timezone.utc).isoformat(), label=args.label,
                  duration_seconds=args.seconds,
                  graphics_backend=os.environ.get("GAMELAB_GRAPHICS_BACKEND", "auto"),
                  vgl_fps=os.environ.get("GAMELAB_VGL_FPS", "60"),
                  websocket_queue=os.environ.get("GAMELAB_WS_QUEUE", "12"),
                  game_fps=args.game_fps, input_latency_ms=args.input_latency_ms,
                  measurements=benchmark(args.seconds, args.interval))
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
