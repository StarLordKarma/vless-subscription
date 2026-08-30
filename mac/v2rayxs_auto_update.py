#!/usr/bin/python
from __future__ import print_function
import json
import os
import plistlib
import subprocess
import tempfile
import time

DOMAIN = "cenmrev.V2RayXS"
URL = "https://starlordkarma.github.io/vless-subscription/v2rayxs_top10.json"
PREFIX = "AUTO-"


def run(cmd, quiet=False):
    if quiet:
        return subprocess.call(cmd, stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
    return subprocess.call(cmd)


def export_prefs(path):
    return run(["/usr/bin/defaults", "export", DOMAIN, path], True) == 0


def app_running():
    return run(["/usr/bin/pgrep", "-x", "V2RayXS"], True) == 0


def open_app():
    run(["/usr/bin/open", "-a", "V2RayXS"], True)


def quit_app():
    if app_running():
        run(["/usr/bin/osascript", "-e", 'tell application "V2RayXS" to quit'], True)
        time.sleep(1.5)


def is_auto(profile):
    return isinstance(profile, dict) and str(profile.get("tag", "")).startswith(PREFIX)


def main():
    tmpdir = tempfile.mkdtemp(prefix="v2rayxs-auto-")
    bundle = os.path.join(tmpdir, "top10.json")
    prefs = os.path.join(tmpdir, "prefs.plist")
    newprefs = os.path.join(tmpdir, "prefs-new.plist")

    rc = run(["/usr/bin/curl", "-fsSL", "--connect-timeout", "10", "--max-time", "30", URL, "-o", bundle], True)
    if rc != 0:
        print("Download failed; keeping current V2RayXS servers")
        if not app_running():
            open_app()
        return 1

    try:
        new_auto = json.load(open(bundle, "r"))
    except Exception as e:
        print("Invalid server bundle: %s" % e)
        return 2

    if not isinstance(new_auto, list) or not new_auto:
        print("Empty server bundle; keeping current V2RayXS servers")
        return 3

    if not export_prefs(prefs):
        print("Could not read V2RayXS preferences")
        if not app_running():
            open_app()
        return 4

    data = plistlib.readPlist(prefs)
    if data.get("enableEncryption"):
        print("V2RayXS config encryption is enabled; automatic profile update skipped")
        return 5

    current = data.get("profiles", []) or []
    old_auto = [p for p in current if is_auto(p)]
    if json.dumps(old_auto, sort_keys=True) == json.dumps(new_auto, sort_keys=True):
        print("Automatic servers are already current")
        if not app_running():
            open_app()
        return 0

    quit_app()

    if export_prefs(prefs):
        data = plistlib.readPlist(prefs)
        current = data.get("profiles", []) or []

    manual = [p for p in current if not is_auto(p)]
    data["profiles"] = manual + new_auto

    status = data.get("appStatus", {}) or {}
    status["proxyState"] = True
    status["proxyMode"] = 1
    data["appStatus"] = status

    plistlib.writePlist(data, newprefs)
    if run(["/usr/bin/defaults", "import", DOMAIN, newprefs], True) != 0:
        print("Could not save V2RayXS preferences")
        open_app()
        return 6

    time.sleep(0.5)
    open_app()
    print("Updated %d automatic V2RayXS servers" % len(new_auto))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
