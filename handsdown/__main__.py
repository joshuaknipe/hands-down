"""python -m handsdown            start Hands Down in the tray
python -m handsdown --settings   open the settings window
python -m handsdown --self-test  check that a build can load its models and assets"""

import os
import sys

os.environ.setdefault("GLOG_minloglevel", "2")  # quieten MediaPipe's C++ logging


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--settings" in args:
        from handsdown.settings_window import run_settings_window

        return run_settings_window()
    if "--self-test" in args:
        from handsdown.selftest import run_self_test

        return run_self_test()
    from handsdown.app import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
