import os
import sys

# Linux 某些环境下 Qt 视频渲染会因 GLX 初始化失败而黑屏/报错。
# 先强制软件渲染，确保预览流程可用。
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")

from app.main import run, run_add_wife_only


def main():
    if "--open-add-wife-only" in sys.argv:
        raise SystemExit(run_add_wife_only())
    raise SystemExit(run())


if __name__ == "__main__":
    main()
