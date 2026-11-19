# Taurine

Aggressive memory, battery and performance defaults for Chromium on macOS.

**Phase 1 (this repo now):** a configuration profile of Chromium enterprise policies plus an A/B benchmark. Nothing to compile. Works with Chromium (`org.chromium.Chromium`) and Google Chrome (`com.google.Chrome`).
**Phase 2 (later):** a patch set and custom build. Full roadmap: [docs/PLAN.md](docs/PLAN.md).

## Use it

```bash
python3 scripts/build_profile.py                   # dist/Taurine.mobileconfig
python3 scripts/build_profile.py --with-adblock    # also force-installs uBlock Origin Lite
python3 scripts/build_profile.py --memory-limit-mb 4096   # also caps total browser memory
```

1. Double-click the `.mobileconfig`, then approve it in System Settings (search "Profiles").
2. Restart the browser and open `chrome://policy`. Each policy should show **Mandatory** with source **Platform**.
3. To undo, remove the "Taurine" profile in System Settings.

A profile is needed because `defaults write` values load only as *recommended*, and most of these policies ignore recommended values (`components/policy/core/common/policy_loader_mac.mm`).

## What it changes and why

Every policy name and value below was checked against Chromium's policy definitions on `main` (M160), in `components/policy/resources/templates/policy_definitions/`.

| Policy | Value | Effect | Trade-off |
|---|---|---|---|
| HighEfficiencyModeEnabled | true | Memory Saver on: discards inactive background tabs | Discarded tabs reload when selected |
| MemorySaverModeSavings | 2 (Maximum) | Tabs go inactive sooner | More reloads and network use |
| BackgroundTabFreezingEnabled | true | Pauses JS and timers in inactive background tabs (M155+) | Tabs playing audio/video, using WebRTC, etc. are exempt by design |
| IntensiveWakeUpThrottlingEnabled | true | Background tabs (backgrounded 5+ min) run JS timers at most once a minute | Some background page actions are delayed up to 1 minute |
| BatterySaverModeAvailability | 1 | Frame-rate throttling on battery at low charge | Policy can't force it always-on; value 2 has meant the same as 1 since M121 |
| NetworkPredictionOptions | 2 (never) | No DNS prefetch, preconnect or prerender | Some navigations may be slightly slower; less wasted CPU, memory and data |
| GenAILocalFoundationalModelSettings | 1 | Doesn't download the on-device AI model (and deletes it if present) | Turns off on-device AI features |
| HardwareAccelerationModeEnabled | true | Keeps GPU decode and compositing on | None (this is the default; set to stop it being turned off) |
| MetricsReportingEnabled, UrlKeyedAnonymizedDataCollectionEnabled, SpellCheckServiceEnabled, ShoppingListEnabled, PromotionsEnabled | false | Less background network and service work | Loses cloud spellcheck and price tracking |
| *ExtensionInstallForcelist* (opt-in) | uBlock Origin Lite | Blocks ads and trackers, usually the biggest real-world saving on heavy sites | Forces third-party code into the browser; MV3 Lite version, no cosmetic filtering. MV2 policy support ended in M138 |
| *TotalMemoryLimitMb* (opt-in) | your choice | Discards tabs above a total memory cap (Win/Mac only) | Too low means constant reloads |

**Left untouched on purpose:** Site Isolation (`SitePerProcess`) and component updates (`ComponentUpdatesEnabled`). Weakening either saves memory or network at a direct cost to security.

## Measure it

```bash
python3 bench/bench.py --label stock      # profile removed
python3 bench/bench.py --label taurine    # profile installed
python3 bench/bench.py --report
```

The script opens the 12 tabs in `bench/urls.txt` in a fresh browser profile, waits 1 minute for them to load, then leaves all but one in the background for 15 minutes. It records summed RSS (a relative measure, since shared memory is double-counted) and idle CPU seconds (a proxy for battery drain). Run each label 3 or more times and compare medians. Set `TAURINE_BROWSER` or `--browser` to point at Chrome instead of Chromium.

No improvement figures are claimed until these runs exist.
