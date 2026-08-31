#!/usr/bin/env python3
import json
import socket
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
from urllib.request import Request, urlopen

SRC = Path("vless_working_full_unique.txt")
OUT = Path("v2rayxs_top10.json")
COUNT = 10

PREFERRED = {"US", "GB", "CH", "NL", "NO"}
COUNTRY_NAMES = {
    "US": "USA",
    "GB": "UK",
    "CH": "Switzerland",
    "NL": "Netherlands",
    "NO": "Norway",
}


def q1(q, name, default=""):
    values = q.get(name)
    return values[0] if values else default


def resolve_ip(host):
    try:
        return socket.gethostbyname(host)
    except Exception:
        return host


def country_for_host(host, cache):
    ip = resolve_ip(host)
    if ip in cache:
        return cache[ip]
    code = "XX"
    try:
        req = Request("https://ipwho.is/%s" % ip, headers={"User-Agent": "v2rayxs-country-selector/1.0"})
        with urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("success", True):
            code = str(data.get("country_code") or "XX").upper()
    except Exception as e:
        print("Country lookup failed for %s (%s): %s" % (host, ip, e))
    cache[ip] = code
    return code


def outbound_from_link(link, index, country_code):
    u = urlsplit(link)
    q = parse_qs(u.query, keep_blank_values=True)
    host = u.hostname
    port = u.port or 443
    uuid = unquote(u.username or "")
    network = q1(q, "type", "tcp")
    security = q1(q, "security", "none")
    flow = q1(q, "flow", "")

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

    country_name = COUNTRY_NAMES.get(country_code, country_code if country_code != "XX" else "Unknown")
    return {
        "tag": "AUTO-%02d-%s" % (index, country_name),
        "protocol": "vless",
        "settings": {"vnext": [{"address": host, "port": port, "users": [user]}]},
        "streamSettings": stream,
    }


def main():
    links = [x.strip() for x in SRC.read_text().splitlines() if x.strip().startswith("vless://")]
    cache = {}
    enriched = []
    for order, link in enumerate(links):
        host = urlsplit(link).hostname
        code = country_for_host(host, cache)
        enriched.append((0 if code in PREFERRED else 1, order, link, code))
        print("%s -> %s" % (host, COUNTRY_NAMES.get(code, code)))

    enriched.sort(key=lambda x: (x[0], x[1]))
    selected = enriched[:COUNT]
    if len(selected) != COUNT:
        raise SystemExit("Need exactly %d working candidates, got %d" % (COUNT, len(selected)))

    outbounds = [outbound_from_link(link, i, code) for i, (_, _, link, code) in enumerate(selected, 1)]
    OUT.write_text(json.dumps(outbounds, indent=2, ensure_ascii=True) + "\n")

    print("Created %d automatic V2RayXS outbounds" % len(outbounds))
    print("Selected countries: %s" % ", ".join(x["tag"].split("-", 2)[-1] for x in outbounds))


if __name__ == "__main__":
    main()
