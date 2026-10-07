"""Milestone 1 feasibility tools. Run: python -m feasibility <command> --help"""

import argparse
import os
import sys

os.environ.setdefault("GLOG_minloglevel", "2")  # quieten MediaPipe's C++ logging

from handsdown.camera import backend_by_name, backends_for_platform


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m feasibility", description="Hands Down milestone 1 feasibility tools")
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="Open the camera with each backend and report frame flow")
    probe.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    probe.add_argument("--seconds", type=float, default=3.0, help="how long to read from each backend")

    record = sub.add_parser("record", help="Record labelled clips with live tracking")
    record.add_argument("--label", required=True, help="where the hand is, e.g. hair_scalp or chin_rest")
    record.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    record.add_argument("--backend", default=None, help="camera backend (default: the first for this OS)")

    sub.add_parser("analyse", help="Measure hand visibility in recorded clips and give a verdict")

    co = sub.add_parser("coexist", help="Test camera sharing with Teams in both launch orders")
    co.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    co.add_argument("--backends", default=None, help="comma-separated backends (default: all for this OS)")
    co.add_argument("--observe", type=float, default=15.0, help="seconds both apps run together per trial")

    args = parser.parse_args(argv)

    if args.command == "probe":
        from feasibility.probe import run_probe

        return run_probe(args.camera, backends_for_platform(), args.seconds)
    if args.command == "record":
        from feasibility.clips import LABELS
        from feasibility.record import run_record
        from handsdown.paths import clips_dir

        if args.label not in LABELS:
            parser.error(f"--label must be one of: {', '.join(LABELS)}")
        backend = backend_by_name(args.backend) if args.backend else backends_for_platform()[0]
        return run_record(args.label, args.camera, backend, clips_dir())
    if args.command == "analyse":
        from feasibility.analyse import run_analyse
        from handsdown.paths import clips_dir, reports_dir

        return run_analyse(clips_dir(), reports_dir())
    if args.command == "coexist":
        from datetime import datetime

        from feasibility.coexist import default_backends, make_opener, run_session
        from feasibility.report import write_report
        from handsdown.paths import reports_dir

        backends = args.backends.split(",") if args.backends else default_backends()
        report = run_session(backends, make_opener(args.camera), ask=input, say=print, observe_seconds=args.observe)
        print(f"Report written to {write_report(reports_dir(), 'coexist', report, datetime.now())}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
