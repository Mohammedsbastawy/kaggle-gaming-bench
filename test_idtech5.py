import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import launch_idtech5


class IdTech5LaunchTests(unittest.TestCase):
    def run_launcher(self, glx_output, vgl_output=""):
        argv = ["launch_idtech5.py", "--wine", "/wine/bin/wine",
                "/games/WolfNewOrder_x64.exe"]
        with patch.object(sys, "argv", argv), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(launch_idtech5, "probe",
                          side_effect=[(0, glx_output), (0, vgl_output)]) as probe, \
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
            status, _, call = self.run_launcher("  GLX  (opcode: 150)\n", info)
        self.assertEqual(status, 0)
        command = call.call_args.args[0]
        self.assertEqual(command[:4], [str(launch_idtech5.VGL), "-d", "egl0",
                                       str(Path("/wine/bin/wine").resolve())])
        self.assertNotIn("-dl", command)
        self.assertEqual(call.call_args.kwargs["env"]["DISPLAY"], ":0")
        self.assertNotIn("MESA_GL_VERSION_OVERRIDE", call.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
