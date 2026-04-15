from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class PlayerBridge:
    """桥接现有 dancer.py，先确保 M1 可运行。"""

    def __init__(self, project_root: Path, dancer_dir: str = "dancer"):
        self._project_root = project_root
        self._dancer_dir = dancer_dir
        self._proc: subprocess.Popen | None = None

    def start_default_animation(self) -> None:
        if self._proc and self._proc.poll() is None:
            return

        script_path = self._project_root / "dancer.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--dancer-dir",
            self._dancer_dir,
        ]
        self._proc = subprocess.Popen(cmd, cwd=str(self._project_root))

    def switch_to_dancer(self, name: str) -> None:
        """切换到指定角色：写入 .last 文件，然后重启 dancer.py。"""
        last_file = self._project_root / self._dancer_dir / ".last"
        last_file.write_text(name, encoding="utf-8")
        self.stop()
        self.start_default_animation()

    def stop(self) -> None:
        if not self._proc:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=3)
        self._proc = None
