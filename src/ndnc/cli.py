from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path
from .parser.parser import parse
from .interp.evaluator import Interpreter
from .server import Server

def main():
    ap = argparse.ArgumentParser(prog="ndnc", description="NDN DSL interpreter")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_run = sub.add_parser("run", help="Interpret and run a .ndn file")
    ap_run.add_argument("source", type=Path)
    ap_run.add_argument("--result-file", type=Path,
                        help="Write the result as JSON (binary results use a base64 object), separately from stdout")
    ap_run.add_argument("--output", type=Path,
                        help="Save the result directly to a file; binary results are written unchanged")
    ap_run.add_argument("ndn_args", nargs="*", metavar="ARG",
                        help="NDN names passed as arg0, arg1, ... to the script")

    ap_serve = sub.add_parser("serve", help="Start NDN server (producer)")

    args = ap.parse_args()

    if args.cmd == "run":
        code = args.source.read_text(encoding="utf-8")
        prog = parse(code)
        # 位置引数を arg0, arg1, ... として Interpreter に渡す
        ndn_args = {f"arg{i}": v for i, v in enumerate(args.ndn_args)}
        result = Interpreter(args=ndn_args, base_dir=args.source.resolve().parent).run(prog)
        if args.output is not None:
            data = result if isinstance(result, bytes) else ('' if result is None else str(result)).encode('utf-8')
            args.output.write_bytes(data)
        if args.result_file is not None:
            if isinstance(result, bytes):
                result = {"encoding": "base64", "data": base64.b64encode(result).decode("ascii")}
            args.result_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    elif args.cmd == "serve":
        Server().run()


if __name__ == "__main__":
    main()
