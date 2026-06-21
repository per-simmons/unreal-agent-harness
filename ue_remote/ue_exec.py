#!/usr/bin/env python3
"""ue_exec.py - run an arbitrary Python string inside a LIVE Unreal Editor.

Uses UE's official remote_execution.py (UDP discovery + TCP command channel)
to call real UE/Cesium FUNCTIONS in the running editor, not just set raw
UPROPERTYs. This is the path that fires BlueprintSetters (e.g. the Cesium
georeference rebase) which the MCP property-set path bypasses.

Prereqs:
  - [/Script/PythonScriptPlugin.PythonScriptPluginSettings] bRemoteExecution=True
    in the project's Config/DefaultEngine.ini  (needs ONE editor restart).
  - The editor must be RUNNING. This client only connects; it never launches it.

Usage:
  python3 ue_exec.py "import unreal; print(unreal.SystemLibrary.get_engine_version())"
  python3 ue_exec.py --file path/to/script.py
  python3 ue_exec.py --mode eval "1 + 1"
  cat script.py | python3 ue_exec.py -          # read from stdin

Exit codes: 0 = command ran (UE stdout printed). 2 = no editor discovered.
            3 = UE reported the command failed. 1 = client/usage error.
"""

import argparse
import os
import sys
import time

# Make sure we import the sibling official client regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import remote_execution as ue  # noqa: E402

# Same-host setup: editor binds 0.0.0.0 (all adapters), client talks loopback.
# Both share the multicast group/port set in DefaultEngine.ini.
DISCOVERY_TIMEOUT = 5.0  # seconds to wait for the editor to answer UDP pings


def _build_config():
    cfg = ue.RemoteExecutionConfig()
    # Defaults already match DefaultEngine.ini (239.0.0.1:6766, bind 127.0.0.1,
    # command endpoint 127.0.0.1:6776). Allow env overrides for flexibility.
    grp = os.environ.get("UE_REMOTE_MULTICAST")  # e.g. "239.0.0.1:6766"
    if grp and ":" in grp:
        host, port = grp.rsplit(":", 1)
        cfg.multicast_group_endpoint = (host, int(port))
    bind = os.environ.get("UE_REMOTE_BIND_ADDRESS")
    if bind:
        cfg.multicast_bind_address = bind
    return cfg


def run(command, exec_mode, discovery_timeout=DISCOVERY_TIMEOUT):
    """Connect to the running editor, run `command`, return (ok, output)."""
    remote = ue.RemoteExecution(_build_config())
    remote.start()
    try:
        # Poll for the editor to appear via UDP multicast discovery.
        deadline = time.time() + discovery_timeout
        node_id = None
        while time.time() < deadline:
            nodes = remote.remote_nodes
            if nodes:
                node_id = nodes[0]["node_id"]
                break
            time.sleep(0.1)

        if not node_id:
            return None, (
                "No Unreal Editor discovered on the multicast group within "
                f"{discovery_timeout:.0f}s. Is the editor running, and was it "
                "restarted AFTER bRemoteExecution=True was set?"
            )

        remote.open_command_connection(node_id)
        result = remote.run_command(command, unattended=True, exec_mode=exec_mode)
        # result: {'success': bool, 'command': str, 'result': str, 'output': [ {type, output}, ... ]}
        out_lines = []
        for entry in result.get("output", []) or []:
            out_lines.append(entry.get("output", ""))
        text = "".join(out_lines)
        # 'result' carries the eval value / repr in eval/statement modes.
        if result.get("result") and result.get("result") not in ("None", text):
            text = (text + result["result"]) if text else result["result"]
        return bool(result.get("success", False)), text
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()


def _read_command(args):
    if args.file:
        with open(args.file, "r") as f:
            return f.read()
    if args.command == "-":
        return sys.stdin.read()
    return args.command


def main():
    p = argparse.ArgumentParser(description="Run Python inside a live Unreal Editor.")
    p.add_argument("command", nargs="?", help="Python source, or '-' to read stdin.")
    p.add_argument("--file", "-f", help="Read the Python source from this file.")
    p.add_argument(
        "--mode",
        choices=["file", "statement", "eval"],
        default="file",
        help="Execution mode. 'file' (default) runs a multi-statement script; "
        "'eval' returns the value of a single expression.",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=DISCOVERY_TIMEOUT,
        help="Seconds to wait for editor discovery (default 5).",
    )
    args = p.parse_args()

    if not args.command and not args.file:
        p.error("provide a command string, --file, or '-' for stdin")

    command = _read_command(args)
    mode = {
        "file": ue.MODE_EXEC_FILE,
        "statement": ue.MODE_EXEC_STATEMENT,
        "eval": ue.MODE_EVAL_STATEMENT,
    }[args.mode]

    ok, output = run(command, mode, discovery_timeout=args.timeout)

    if ok is None:
        sys.stderr.write(output + "\n")
        sys.exit(2)

    sys.stdout.write(output if output is not None else "")
    if output and not output.endswith("\n"):
        sys.stdout.write("\n")
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
