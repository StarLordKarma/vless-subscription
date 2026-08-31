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
        devnull = open(os.devnull, "w")
        try:
            return subprocess.call(cmd, stdout=devnull, stderr=devnull)
        finally:
            devnull.close()
    return subprocess.call(cmd)


def export_prefs(path):
    return run(["/usr/bin/defaults", "export", DOMAIN, path], True) == 0


def load_prefs(tmpdir, exported_path):
    # Catalina's `defaults export` can produce a plist representation that
    # Python 2.7 plistlib cannot parse directly. Convert it explicitly to XML1.
    xml_path = os.path.join(tmpdir, "prefs.xml")
    if run(["/usr/bin/plutil", "-convert", "xml1", "-o", xml_path, exported_path], True) != 0:
        raise RuntimeError("plutil could not convert V2RayXS preferences to XML")
    return plistlib.readPlist(xml_path)


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


def desired_status(data, first_auto_index):
    status = data.get("appStatus", {}) or {}
    return (
        status.get("proxyState") is True and
        int(status.get("proxyMode", -1)) == 1 and
        int(status.get("selectedServerIndex", -1)) == int(first_auto_index) and
        status.get("useCusProfile") is False and
        status.get("useMultipleServer") is False
    )


def apply_status(data, first_auto_index):
    status = data.get("appStatus", {}) or {}
    status["proxyState"] = True
    status["proxyMode"] = 1
    status["selectedServerIndex"] = int(first_auto_index)
    status["selectedCusServerIndex"] = -1
    status["useCusProfile"] = False
    status["useMultipleServer"] = False
    data["appStatus"] = status


def main():
    tmpdir = tempfile.mkdtemp(prefix="v2rayxs-auto-")
    bundle = os.path.join(tmpdir, "top10.json")
    prefs = os.path.join(tmpdir, "prefs-export.plist")
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

    if not isinstance(new_auto, list) or len(new_auto) != 10:
        print("Server bundle does not contain exactly 10 profiles; keeping current servers")
        return 3

    if not export_prefs(prefs):
        print("Could not read V2RayXS preferences")
        if not app_running():
            open_app()
        return 4

    try:
        data = load_prefs(tmpdir, prefs)
    except Exception as e:
        print("Could not parse V2RayXS preferences: %s" % e)
        return 5

    if data.get("enableEncryption"):
        print("V2RayXS config encryption is enabled; automatic profile update skipped")
        return 6

    current = data.get("profiles", []) or []
    manual = [p for p in current if not is_auto(p)]
    old_auto = [p for p in current if is_auto(p)]
    first_auto_index = len(manual)

    profiles_current = json.dumps(old_auto, sort_keys=True) == json.dumps(new_auto, sort_keys=True)
    status_current = desired_status(data, first_auto_index)

    if profiles_current and status_current:
        print("Automatic servers and AUTO-01 selection are already current")
        if not app_running():
            open_app()
        return 0

    quit_app()

    # Re-export after quitting so V2RayXS flushes its latest settings first.
    if export_prefs(prefs):
        try:
            data = load_prefs(tmpdir, prefs)
            current = data.get("profiles", []) or []
        except Exception as e:
            print("Could not re-read V2RayXS preferences: %s" % e)
            open_app()
            return 7

    manual = [p for p in current if not is_auto(p)]
    first_auto_index = len(manual)
    data["profiles"] = manual + new_auto

    # Start V2RayXS in the state already proven to work on this Mac:
    # Global Mode, core enabled, single server, first AUTO profile selected.
    apply_status(data, first_auto_index)

    plistlib.writePlist(data, newprefs)
    if run(["/usr/bin/defaults", "import", DOMAIN, newprefs], True) != 0:
        print("Could not save V2RayXS preferences")
        open_app()
        return 8

    time.sleep(0.5)
    open_app()
    print("Updated 10 automatic V2RayXS servers; AUTO-01 selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
