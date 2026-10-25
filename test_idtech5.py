import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import launch_idtech5


class IdTech5LaunchTests(unittest.TestCase):
    def run_launcher(self, glx_output, vgl_output="", game_args=(),
                     fallback_output=None, xorg_ready=False):
        argv = ["launch_idtech5.py", "--wine", "/wine/bin/wine",
                "/games/WolfNewOrder_x64.exe", *game_args]
        outputs = [(0, glx_output), (0, vgl_output)]
        if fallback_output is not None:
            outputs.append((0, fallback_output))
        with patch.object(sys, "argv", argv), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "exists", return_value=xorg_ready), \
             patch.object(launch_idtech5, "probe",
                          side_effect=outputs) as probe, \
             patch.object(launch_idtech5.subprocess, "call", return_value=0) as call:
            status = launch_idtech5.main()
        return status, probe, call

    def test_missing_glx_stops_before_wine(self):
        status, probe, call = self.run_launcher("  RANDR  (opcode: 140)\n")
        self.assertEqual(status, 78)
        self.assertEqual(probe.call_count, 1)
        call.assert_not_called()

    def test_nvidia_probe_launches_wine_with_virtualgl_on_visible_display(self):
        info = ("OpenGL vendor string: NVIDIA Corporation\n"
                "OpenGL renderer string: Tesla T4/PCIe/SSE2\n")
        with patch.dict(os.environ, {"DISPLAY": ":0",
                                  "MESA_GL_VERSION_OVERRIDE": "4.5COMPAT"}):
            status, _, call = self.run_launcher(
                "  GLX  (opcode: 150)\n", info,
                ("+com_skipIntroVideo", "1", "+r_fullscreen", "0"))
        self.assertEqual(status, 0)
        command = call.call_args.args[0]
        self.assertEqual(command[:3], [str(launch_idtech5.VGL), "-d", "egl0"])
        self.assertIn("wine", str(command[3]))
        self.assertNotIn("-dl", command)
        self.assertEqual(command[-4:], ["+com_skipIntroVideo", "1", "+r_fullscreen", "0"])
        self.assertEqual(call.call_args.kwargs["env"]["DISPLAY"], ":0")
        self.assertNotIn("MESA_GL_VERSION_OVERRIDE", call.call_args.kwargs["env"])

    def test_auto_prefers_verified_gpu0_glx_server(self):
        info = ("OpenGL vendor string: NVIDIA Corporation\n"
                "OpenGL renderer string: Tesla T4/PCIe/SSE2\n")
        status, _, call = self.run_launcher("  GLX  (opcode: 150)\n", info,
                                            xorg_ready=True)
        self.assertEqual(status, 0)
        self.assertEqual(call.call_args.args[0][1:3], ["-d", ":1"])
        self.assertNotIn("+r_customWidth", call.call_args.args[0])

    def test_auto_falls_back_to_egl_when_glx_probe_fails(self):
        info = ("OpenGL vendor string: NVIDIA Corporation\n"
                "OpenGL renderer string: Tesla T4/PCIe/SSE2\n")
        status, probe, call = self.run_launcher(
            "  GLX  (opcode: 150)\n", "Error: unable to open :1",
            fallback_output=info, xorg_ready=True)
        self.assertEqual(status, 0)
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(call.call_args.args[0][1:3], ["-d", "egl0"])


if __name__ == "__main__":
    unittest.main()
