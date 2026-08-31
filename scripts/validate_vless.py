#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    user = {"id": uuid, "encryption": q1(q, "encryption", "none")}
    if flow:
        user["flow"] = flow

    stream = {"network": network, "security": security}
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

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{"listen": "127.0.0.1", "port": listen_port, "protocol": "http", "settings": {}}],
        "outbounds": [{
            "tag": "test",
            "protocol": "vless",
            "settings": {"vnext": [{"address": host, "port": port, "users": [user]}]},
            "streamSettings": stream,
        }],
    }, tag, host, port, network, security


def curl_probe(proxy, url, timeout):
    cp = subprocess.run([
        "curl", "-sS", "-L", "--connect-timeout", "4", "--max-time", str(timeout),
        "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36",
        "-x", proxy, "-o", "/dev/null", "-w", "%{http_code}", url
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return cp.returncode, cp.stdout.strip(), cp.stderr.strip()


def test_link(xray, link, index, timeout):
    listen_port = 18080 + index
    proc = None
    cfg_path = None
    log_path = None
    log = None
    try:
        config, tag, host, port, network, security = build_config(link, listen_port)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as cfg:
            json.dump(config, cfg)
            cfg_path = cfg.name
        fd, log_path = tempfile.mkstemp(prefix="xray-check-", suffix=".log")
        os.close(fd)
        log = open(log_path, "w")
        proc = subprocess.Popen([xray, "run", "-config", cfg_path], stdout=log, stderr=log)
        time.sleep(0.5)
        if proc.poll() is not None:
            log.flush()
            detail = Path(log_path).read_text(errors="ignore")[-400:].replace("\n", " ")
            return index, False, False, link, tag, host, port, f"xray-start-failed {detail}"

        proxy = f"http://127.0.0.1:{listen_port}"
        rc, google_code, _ = curl_probe(proxy, "https://www.google.com/generate_204", timeout)
        google_ok = rc == 0 and google_code in {"200", "204"}
        if not google_ok:
            detail = f"google={google_code or '-'} curl={rc} gemini=- net={network} sec={security}"
            return index, False, False, link, tag, host, port, detail

        # Gemini can redirect to sign-in or return a normal 2xx/3xx response. What we reject
        # here is a dead/empty proxy path (curl error/000) and explicit access blocking.
        grc, gemini_code, _ = curl_probe(proxy, "https://gemini.google.com/", timeout)
        gemini_ok = grc == 0 and gemini_code.isdigit() and 200 <= int(gemini_code) < 400
        detail = f"google={google_code} gemini={gemini_code or '-'} curl={grc} net={network} sec={security}"
        return index, True, gemini_ok, link, tag, host, port, detail
    except Exception as e:
        return index, False, False, link, "parse-error", "", 0, str(e)
    finally:
        if proc is not None:
            try:
                proc.terminate(); proc.wait(timeout=1)
            except Exception:
                try: proc.kill()
                except Exception: pass
        if log is not None:
            try: log.close()
            except Exception: pass
        for p in (cfg_path, log_path):
            if p:
                try: os.unlink(p)
                except OSError: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="speed_tested_50.txt")
    ap.add_argument("--xray", default="./xray")
    ap.add_argument("--working", default="vless_working.txt")
    ap.add_argument("--gemini-working", default="vless_gemini_working.txt")
    ap.add_argument("--report", default="vless_test_results.tsv")
    ap.add_argument("--timeout", type=int, default=8)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    links = [x.strip() for x in Path(args.input).read_text(errors="ignore").splitlines() if x.strip().startswith("vless://")]
    results = []
    print(f"Found {len(links)} VLESS links; workers={args.workers}")
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(test_link, args.xray, link, i, args.timeout) for i, link in enumerate(links, 1)]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            i, ok, gemini_ok, link, tag, host, port, detail = r
            state = "GEMINI" if gemini_ok else ("WORKS" if ok else "FAIL")
            print(f"[{i:02d}/{len(links):02d}] {state:6} {tag[:22]:22} {host}:{port} {detail}", flush=True)

    results.sort(key=lambda r: r[0])
    good = [r[3] for r in results if r[1]]
    gemini_good = [r[3] for r in results if r[2]]
    rows = ["status\tgemini\ttag\thost\tport\tdetail"]
    for _, ok, gemini_ok, _, tag, host, port, detail in results:
        rows.append(f"{'WORKS' if ok else 'FAIL'}\t{'YES' if gemini_ok else 'NO'}\t{tag}\t{host}\t{port}\t{detail}".replace("\n", " "))

    Path(args.working).write_text("".join(x + "\n" for x in good))
    Path(args.gemini_working).write_text("".join(x + "\n" for x in gemini_good))
    Path(args.report).write_text("\n".join(rows) + "\n")
    print(f"Working: {len(good)} / {len(links)}; Gemini-reachable: {len(gemini_good)}")


if __name__ == "__main__":
    main()
