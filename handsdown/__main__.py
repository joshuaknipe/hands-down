"""python -m handsdown            start Hands Down in the tray
python -m handsdown --settings   open the settings window
python -m handsdown --camera-view  show frames the app sends (started by "Show camera")
python -m handsdown --self-test  check that a build can load its models and assets"""

import os
import sys

os.environ.setdefault("GLOG_minloglevel", "2")  # quieten MediaPipe's C++ logging


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--settings" in args:
        from handsdown.settings_window import run_settings_window

        return run_settings_window()
    if "--camera-view" in args:
        import subprocess

        from handsdown.app import settings_command
        from handsdown.preview import end_viewer, run_viewer

        window = [None]

        def open_settings() -> None:
            if window[0] is None or window[0].poll() is not None:  # one settings window at a time
                window[0] = subprocess.Popen(settings_command())

        end_viewer(run_viewer(open_settings=open_settings))
    if "--self-test" in args:
        from handsdown.selftest import run_self_test

        return run_self_test()
    from handsdown.app import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
