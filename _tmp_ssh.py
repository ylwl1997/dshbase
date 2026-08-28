#!/usr/bin/env python3
"""Remote SSH helper via paramiko for GLink interop work."""
import argparse
import sys
import time

import paramiko

HOST = "100.66.1.16"
USER = "root"
PWD = "60851.org"


def connect(timeout=20):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username=USER,
        password=PWD,
        timeout=timeout,
        look_for_keys=False,
        allow_agent=False,
    )
    return c


def run(c, cmd, timeout=120, get_pty=False):
    print(f"\n===== {cmd} =====", flush=True)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
    if err:
        sys.stdout.write("[stderr]\n" + err)
        if not err.endswith("\n"):
            sys.stdout.write("\n")
    print(f"[exit={code}]", flush=True)
    return code, out, err


def put(c, local, remote):
    sftp = c.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    print(f"PUT {local} -> {remote}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmds", nargs="*", help="shell commands to run")
    ap.add_argument("-c", "--cmd", action="append", default=[], help="command")
    ap.add_argument("--put", nargs=2, metavar=("LOCAL", "REMOTE"))
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--pty", action="store_true")
    args = ap.parse_args()
    cmds = list(args.cmds) + list(args.cmd)
    c = connect()
    try:
        if args.put:
            put(c, args.put[0], args.put[1])
        for cmd in cmds:
            run(c, cmd, timeout=args.timeout, get_pty=args.pty)
        if not cmds and not args.put:
            run(c, "echo OK; hostname; date", timeout=30)
    finally:
        c.close()


if __name__ == "__main__":
    main()
