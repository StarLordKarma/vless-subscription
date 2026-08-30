#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote


def q1(q, name, default=""):
    values = q.get(name)
    return values[0] if values else default


def build_config(link, listen_port):
    u = urlsplit(link)
    q = parse_qs(u.query, keep_blank_values=True)

    host = u.hostname
    port = u.port or 443
    uuid = unquote(u.username or "")
    tag = unquote(u.fragment or host or "server")
    network = q1(q, "type", "tcp")
    security = q1(q, "security", "none")
    flow = q1(q, "flow", "")

    if not host or not uuid:
        raise ValueError("missing host or UUID")

    user = {
        "id": uuid,
        "encryption": q1(q, "encryption", "none"),
    }
    if flow:
        user["flow"] = flow

    stream = {
        "network": network,
        "security": security,
    }

    if security == "reality":
        stream["realitySettings"] = {
            "serverName": q1(q, "sni", ""),
            "fingerprint": q1(q, "fp", "chrome"),
            "publicKey": q1(q, "pbk", ""),
            "shortId": q1(q, "sid", ""),
            "spiderX": q1(q, "spx", ""),
        }

    if network == "ws":
        stream["wsSettings"] = {
            "path": q1(q, "path", "/"),
            "headers": {"Host": q1(q, "host", "")} if q1(q, "host", "") else {},
        }
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": q1(q, "serviceName", q1(q, "servicename", "")),
            "multiMode": q1(q, "mode", "") == "multi",
        }

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "listen": "127.0.0.1",
            "port": listen_port,
            "protocol": "http",
            "settings": {},
        }],
        "outbounds": [{
            "tag": "test",
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": host,
                    "port": port,
                    "users": [user],
                }]
            },
            "streamSettings": stream,
        }],
    }
    return config, tag, host, port, network, security


def test_link(xray, link, index, total, timeout):
    listen_port = 18080 + (index % 1000)
    proc = None
    cfg_path = None
    log_path = None
    try:
        config, tag, host, port, network, security = build_config(link, listen_port)

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as cfg:
            json.dump(config, cfg)
            cfg_path = cfg.name

        log_fd, log_path = tempfile.mkstemp(prefix="xray-check-", suffix=".log")
        os.close(log_fd)
        log = open(log_path, "w")
        proc = subprocess.Popen(
            [xray, "run", "-config", cfg_path],
            stdout=log,
            stderr=log,
        )

        time.sleep(0.6)
        if proc.poll() is not None:
            log.close()
            detail = Path(log_path).read_text(errors="ignore")[-500:].replace("\n", " ")
            return False, tag, host, port, f"xray-start-failed {detail}"

        cmd = [
            "curl", "-sS",
            "--connect-timeout", "4",
            "--max-time", str(timeout),
            "-x", f"http://127.0.0.1:{listen_port}",
            "-o", "/dev/null",
            "-w", "%{http_code}",
            "https://www.google.com/generate_204",
        ]
        cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        code = cp.stdout.strip()
        ok = cp.returncode == 0 and code in {"200", "204"}
        detail = f"HTTP={code or '-'} curl={cp.returncode} net={network} sec={security}"
        return ok, tag, host, port, detail
    except Exception as e:
        return False, "parse-error", "", 0, str(e)
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        for p in (cfg_path, log_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="speed_tested_50.txt")
    ap.add_argument("--xray", default="./xray")
    ap.add_argument("--working", default="vless_working.txt")
    ap.add_argument("--report", default="vless_test_results.tsv")
    ap.add_argument("--timeout", type=int, default=8)
    args = ap.parse_args()

    links = [
        line.strip() for line in Path(args.input).read_text(errors="ignore").splitlines()
        if line.strip().startswith("vless://")
    ]

    good = []
    rows = ["status\ttag\thost\tport\tdetail"]
    print(f"Found {len(links)} VLESS links")

    for i, link in enumerate(links, 1):
        ok, tag, host, port, detail = test_link(args.xray, link, i, len(links), args.timeout)
        status = "WORKS" if ok else "FAIL"
        safe_tag = tag.replace("\t", " ").replace("\n", " ")
        safe_detail = detail.replace("\t", " ").replace("\n", " ")
        print(f"[{i:02d}/{len(links):02d}] {status:5} {safe_tag[:22]:22} {host}:{port} {safe_detail}")
        rows.append(f"{status}\t{safe_tag}\t{host}\t{port}\t{safe_detail}")
        if ok:
            good.append(link)

    Path(args.working).write_text("".join(x + "\n" for x in good))
    Path(args.report).write_text("\n".join(rows) + "\n")
    print(f"Working: {len(good)} / {len(links)}")


if __name__ == "__main__":
    main()
