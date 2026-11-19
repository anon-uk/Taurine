#!/usr/bin/env python3
"""Build a macOS configuration profile (.mobileconfig) from policies/*.json.

Policies delivered by a configuration profile are "forced" in macOS managed
preferences, which Chromium loads as MANDATORY. Values set with
`defaults write` are loaded only as RECOMMENDED, which most of these
policies ignore (see components/policy/core/common/policy_loader_mac.mm).

Usage:
  python3 scripts/build_profile.py                 # base policies
  python3 scripts/build_profile.py --with-adblock  # + uBlock Origin Lite
  python3 scripts/build_profile.py --memory-limit-mb 4096
"""
import argparse
import json
import plistlib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = uuid.UUID("6f1c6f1e-7a0e-4b8e-9a51-7461757269ee")  # fixed: stable UUIDs
BUNDLES = {
    "chromium": "org.chromium.Chromium",
    "chrome": "com.google.Chrome",
}


def load(name):
    return json.loads((ROOT / "policies" / f"{name}.json").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-adblock", action="store_true",
                    help="force-install uBlock Origin Lite (third-party extension)")
    ap.add_argument("--memory-limit-mb", type=int,
                    help="TotalMemoryLimitMb: discard tabs above this (min 1024)")
    ap.add_argument("--targets", default="chromium,chrome",
                    help="comma list of: " + ",".join(BUNDLES))
    ap.add_argument("--out", default=str(ROOT / "dist" / "Taurine.mobileconfig"))
    a = ap.parse_args()

    policies = load("base")
    if a.with_adblock:
        policies.update(load("adblock"))
    if a.memory_limit_mb:
        policies["TotalMemoryLimitMb"] = max(1024, a.memory_limit_mb)

    variant = "base" + ("+adblock" if a.with_adblock else "")
    payloads = []
    for t in a.targets.split(","):
        bundle = BUNDLES[t.strip()]
        ident = f"dev.taurine.policy.{bundle}"
        payloads.append({
            "PayloadType": bundle,
            "PayloadIdentifier": ident,
            "PayloadUUID": str(uuid.uuid5(NS, ident)).upper(),
            "PayloadVersion": 1,
            "PayloadDisplayName": f"Taurine policies ({bundle})",
            **policies,
        })

    top_id = "dev.taurine.profile"
    profile = {
        "PayloadType": "Configuration",
        "PayloadIdentifier": top_id,
        "PayloadUUID": str(uuid.uuid5(NS, top_id)).upper(),
        "PayloadVersion": 1,
        "PayloadScope": "System",
        "PayloadDisplayName": "Taurine",
        "PayloadDescription": f"Taurine performance/battery policies ({variant}).",
        "PayloadRemovalDisallowed": False,
        "PayloadContent": payloads,
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        plistlib.dump(profile, f)
    print(f"wrote {out} ({variant}, {len(policies)} policies, "
          f"targets={a.targets})")


if __name__ == "__main__":
    main()
