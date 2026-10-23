import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gpu_runtime


class RuntimeTests(unittest.TestCase):
    def test_tesla_renderer_uses_vendor_not_model_name(self):
        output = ("OpenGL vendor string: NVIDIA Corporation\n"
                  "OpenGL renderer string: Tesla T4/PCIe/SSE2\n")
        self.assertTrue(gpu_runtime.nvidia_renderer(output))
        self.assertFalse(gpu_runtime.nvidia_renderer(
            "OpenGL vendor string: Mesa\nOpenGL renderer string: llvmpipe\n"))

    def test_software_threads_reserve_stream_cpu_under_quota(self):
        with patch.dict(os.environ, {"LP_NUM_THREADS": ""}), \
             patch.object(gpu_runtime.os, "sched_getaffinity", return_value=set(range(16)), create=True), \
             patch.object(gpu_runtime, "cpu_quota_count", return_value=4):
            self.assertEqual(gpu_runtime.software_threads(), 2)

    def test_software_threads_explicit_override(self):
        with patch.dict(os.environ, {"LP_NUM_THREADS": "3"}):
            self.assertEqual(gpu_runtime.software_threads(), 3)

    def test_egl_probe_selects_nvidia_device_after_software_device(self):
        software = "OpenGL vendor string: Mesa\nOpenGL renderer string: llvmpipe\n"
        tesla = ("OpenGL vendor string: NVIDIA Corporation\n"
                 "OpenGL renderer string: Tesla T4/PCIe/SSE2\n")
        with patch.object(gpu_runtime.Path, "is_file", return_value=True), \
             patch.object(gpu_runtime, "run", side_effect=[
                 (0, "egl0\negl1\n"), (0, software), (0, tesla)]):
            self.assertEqual(gpu_runtime.egl_device_probe({}),
                             (True, "OpenGL renderer string: Tesla T4/PCIe/SSE2", "egl1"))

    def test_private_32bit_driver_is_checked_by_elf_class(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "libGLX_nvidia.so.0"
            library.write_bytes(b"\x7fELF\x01mock")
            with patch.dict(os.environ, {"GAMELAB_NVIDIA_LIB32": directory}):
                self.assertTrue(gpu_runtime.has_32bit_library(library.name))
                library.write_bytes(b"\x7fELF\x02mock")
                with patch.object(gpu_runtime, "run", return_value=(1, "")):
                    self.assertFalse(gpu_runtime.has_32bit_library(library.name))


if __name__ == "__main__":
    unittest.main()
