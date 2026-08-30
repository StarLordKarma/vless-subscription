#!/usr/bin/env python3
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote

SRC = Path("vless_working_full_unique.txt")
OUT = Path("v2rayxs_top5.json")
OUT_DIR = Path("outbounds-auto")
COUNT = 5


def q1(q, name, default=""):
    values = q.get(name)
    return values[0] if values else default


def outbound_from_link(link, index):
    u = urlsplit(link)
    q = parse_qs(u.query, keep_blank_values=True)
    host = u.hostname
    port = u.port or 443
    uuid = unquote(u.username or "")
    label = unquote(u.fragment or (host or "server"))
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

    tag = "AUTO-%02d-%s" % (index, label)
    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {"vnext": [{"address": host, "port": port, "users": [user]}]},
        "streamSettings": stream,
    }


def main():
    links = [x.strip() for x in SRC.read_text().splitlines() if x.strip().startswith("vless://")][:COUNT]
    outbounds = [outbound_from_link(link, i) for i, link in enumerate(links, 1)]
    OUT.write_text(json.dumps(outbounds, indent=2, ensure_ascii=True) + "\n")
    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("AUTO-*.json"):
        old.unlink()
    for outbound in outbounds:
        (OUT_DIR / (outbound["tag"] + ".json")).write_text(json.dumps(outbound, indent=2, ensure_ascii=True) + "\n")
    print("Created %d automatic V2RayXS outbounds" % len(outbounds))


if __name__ == "__main__":
    main()
