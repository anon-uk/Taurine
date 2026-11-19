#!/usr/bin/env python3
"""A/B benchmark for Chromium on macOS: memory and idle CPU with a fixed tab set.

Run once with the Taurine profile removed (label "stock"), once installed
(label "taurine"), then compare with --report.

  python3 bench/bench.py --label stock
  python3 bench/bench.py --label taurine
  python3 bench/bench.py --report

Measures (stdlib only, no sudo):
  - rss_mb: summed RSS of the browser process tree. RSS double-counts shared
    pages, so treat it as a relative signal between runs, not absolute usage.
  - idle_cpu_s: CPU seconds the browser tree burned while every tab but one
    sat in the background. This is the battery proxy: no CPU, no drain.
Memory Saver and intensive throttling act after minutes of inactivity, so
the idle phase must be long (default 15 min) for them to show up.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BROWSER = "/Applications/Chromium.app/Contents/MacOS/Chromium"
PORT = 9333


def ps_tree(root_pid):
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,time="],
                         capture_output=True, text=True, check=True).stdout
    procs = {}
    for line in out.splitlines():
        pid, ppid, rss, t = line.split(None, 3)
        procs[int(pid)] = (int(ppid), int(rss), cpu_seconds(t.strip()))
    tree, frontier = {root_pid}, [root_pid]
    while frontier:
        p = frontier.pop()
        for pid, (ppid, _, _) in procs.items():
            if ppid == p and pid not in tree:
                tree.add(pid)
                frontier.append(pid)
    live = [procs[p] for p in tree if p in procs]
    return {
        "procs": len(live),
        "rss_mb": round(sum(r for _, r, _ in live) / 1024, 1),
        "cpu_s": round(sum(c for _, _, c in live), 2),
    }


def cpu_seconds(t):
    # ps time formats: "MM:SS.ss", "H:MM:SS.ss", "D-HH:MM:SS"
    days = 0
    if "-" in t:
        d, t = t.split("-", 1)
        days = int(d)
    secs = 0.0
    for part in t.split(":"):
        secs = secs * 60 + float(part)
    return secs + days * 86400


def cdp(path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"null")


def wait_for_cdp(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return cdp("/json/version")
        except OSError:
            time.sleep(0.5)
    raise SystemExit("browser did not expose DevTools on port %d" % PORT)


def run(a):
    urls = [u.strip() for u in Path(a.urls).read_text().splitlines()
            if u.strip() and not u.startswith("#")]
    profile = tempfile.mkdtemp(prefix="taurine-bench-")
    proc = subprocess.Popen([
        a.browser, f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}",
        "--no-first-run", "--no-default-browser-check", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        version = wait_for_cdp()
        tabs = [cdp("/json/new?" + urllib.parse.quote(u, safe=":/?&=%"), "PUT")
                for u in urls]
        print(f"opened {len(tabs)} tabs; settling {a.settle}s")
        time.sleep(a.settle)
        # Foreground the first tab so the rest are background tabs.
        cdp(f"/json/activate/{tabs[0]['id']}")
        loaded = ps_tree(proc.pid)
        print(f"loaded: {loaded}; idling {a.idle}s")
        peak = loaded["rss_mb"]
        end = time.time() + a.idle
        while time.time() < end:
            time.sleep(min(30, max(0, end - time.time())))
            peak = max(peak, ps_tree(proc.pid)["rss_mb"])
        idle = ps_tree(proc.pid)
        result = {
            "label": a.label, "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "browser": version.get("Browser"), "tabs": len(tabs),
            "settle_s": a.settle, "idle_s": a.idle,
            "rss_mb_loaded": loaded["rss_mb"], "rss_mb_after_idle": idle["rss_mb"],
            "rss_mb_peak": peak, "procs_loaded": loaded["procs"],
            "procs_after_idle": idle["procs"],
            "idle_cpu_s": round(idle["cpu_s"] - loaded["cpu_s"], 2),
        }
        with open(a.out, "a") as f:
            f.write(json.dumps(result) + "\n")
        print(json.dumps(result, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def report(a):
    rows = [json.loads(l) for l in open(a.out) if l.strip()]
    keys = ["rss_mb_loaded", "rss_mb_after_idle", "rss_mb_peak",
            "procs_after_idle", "idle_cpu_s"]
    by = {}
    for r in rows:
        by.setdefault(r["label"], []).append(r)
    print(f"{'label':<12}{'runs':>5}" + "".join(f"{k:>19}" for k in keys))
    for label, rs in by.items():
        med = [sorted(r[k] for r in rs)[len(rs) // 2] for k in keys]
        print(f"{label:<12}{len(rs):>5}" + "".join(f"{m:>19}" for m in med))
    print("(medians; run each label 3+ times, same machine, on battery or AC "
          "consistently, other apps closed)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--browser", default=os.environ.get("TAURINE_BROWSER", DEFAULT_BROWSER))
    ap.add_argument("--urls", default=str(HERE / "urls.txt"))
    ap.add_argument("--settle", type=int, default=60)
    ap.add_argument("--idle", type=int, default=900)
    ap.add_argument("--out", default=str(HERE / "results.jsonl"))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    report(a) if a.report else run(a)
