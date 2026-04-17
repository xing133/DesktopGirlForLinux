from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class DesktopDancerTray:
    def __init__(
        self,
        on_add_wife: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication 尚未初始化")

        icon = QIcon.fromTheme("user-available")
        if icon.isNull():
            icon = QIcon.fromTheme("applications-multimedia")
        if icon.isNull():
            icon = app.style().standardIcon(QStyle.SP_ComputerIcon)

        self._on_add_wife = on_add_wife
        self._on_quit = on_quit

        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip("Desktop Dancer")

        # Linux / macOS use Qt's tray menu path.
        # On Windows, this app runs as a tray-only process without a normal active main window.
        # QSystemTrayIcon.setContextMenu() reaches aboutToShow, but the popup never becomes visible,
        # so Windows keeps a native TrackPopupMenu-based tray menu here.
        self._menu = QMenu()
        add_wife_action = QAction("添加一个老婆")
        add_wife_action.triggered.connect(on_add_wife)
        self._menu.addAction(add_wife_action)
        self._menu.addSeparator()

        quit_action = QAction("退出")
        quit_action.triggered.connect(on_quit)
        self._menu.addAction(quit_action)

        if sys.platform != "win32":
            self._tray.setContextMenu(self._menu)

        self._tray.activated.connect(self._on_tray_activated)

    # ------------------------------------------------------------------

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            if sys.platform == "win32":
                self._show_menu_win32()
            else:
                self._menu.exec(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_add_wife()

    def _show_menu_win32(self) -> None:
        """
        Standard Win32 tray popup flow:
          SetForegroundWindow(tray_msg_hwnd)
          TrackPopupMenu(...)
          PostMessage(WM_NULL)
        """
        import ctypes

        user32 = ctypes.windll.user32
        pos = QCursor.pos()
        tray_hwnd = self._find_qt_tray_hwnd()

        hmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hmenu, 0x0, 1, "添加一个老婆")  # MF_STRING
        user32.AppendMenuW(hmenu, 0x800, 0, None)  # MF_SEPARATOR
        user32.AppendMenuW(hmenu, 0x0, 2, "退出")  # MF_STRING

        if tray_hwnd:
            user32.SetForegroundWindow(tray_hwnd)

        # TPM_LEFTALIGN=0x0, TPM_BOTTOMALIGN=0x20, TPM_RETURNCMD=0x100
        cmd = user32.TrackPopupMenu(
            hmenu,
            0x120,
            pos.x(),
            pos.y(),
            0,
            tray_hwnd or 0,
            None,
        )

        if tray_hwnd:
            user32.PostMessageW(tray_hwnd, 0, 0, 0)  # WM_NULL

        user32.DestroyMenu(hmenu)

        if cmd == 1:
            self._on_add_wife()
        elif cmd == 2:
            self._on_quit()

    @staticmethod
    def _find_qt_tray_hwnd() -> int:
        import ctypes

        pid = ctypes.windll.kernel32.GetCurrentProcessId()
        found = [0]
        buf = ctypes.create_unicode_buffer(256)

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        def _cb(hwnd, _):
            win_pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
            if win_pid.value != pid:
                return True
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            if "TrayIconMessageWindow" in buf.value:
                found[0] = hwnd
                return False
            return True

        ctypes.windll.user32.EnumWindows(_cb, 0)
        return found[0]

    # ------------------------------------------------------------------

    def show(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise RuntimeError("系统托盘不可用")
        self._tray.show()
