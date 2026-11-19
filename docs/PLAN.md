# Taurine — Plan

Goal: a Chromium-based browser for macOS that uses clearly less memory and battery than stock Chrome and is at least as fast, with no security trade-offs.

Labels used below: **[Fact]** is verified against a cited source. **[Est]** is an estimate that still needs confirming. **[Hyp]** is a hypothesis that needs a benchmark before anything ships.

---

## 1. Bottom line

- **Order of work:** measure first, then change policies and launch flags (cheap, reversible), and only then patch and build Chromium (expensive, ongoing). Each layer has to earn its cost with benchmark numbers.
- **The custom build's main value is likely to be product changes, not compiler flags.** Official Chrome builds for Mac already use PGO and ThinLTO **[Fact: `build/config/compiler/pgo/pgo.gni`, `compiler.gni`]**, so compiler tuning probably adds little **[Hyp]**. The product changes are native content blocking, tighter tab lifecycle rules, fewer background services and a cap on renderer processes.
- **The biggest long-term cost is upkeep:** a rebase every Chromium milestone (about every 4 weeks) and security releases shipped within days of upstream, without exception.
- **Hardware is needed before Phase 2:** a dedicated Apple Silicon Mac to build on. Signing and notarizing for distribution needs an Apple Developer ID **[Est: $99/yr, from memory]**.

## 2. Success metrics

All figures are medians over 3 or more runs on one reference Mac, compared with stock Chrome stable of the same version.

| Metric | Tool | Target (set after the Phase 0 baseline) |
|---|---|---|
| Memory with 12 tabs, loaded and after 15 min idle | `bench/bench.py` + macOS `footprint` | −30% after idle **[Est]** |
| Idle background CPU seconds (battery proxy) | `bench/bench.py` | −50% **[Est]** |
| Battery drain over a scripted 1-hour browsing loop | `powermetrics` (sudo) + battery % | −15% **[Est]** |
| Speedometer 3.x, MotionMark, JetStream | browserbench.org | No regression (no more than 2% worse) |
| Cold start to first paint | scripted launch | No regression |
| Site breakage | Manual top-100 site checklist | No more than stock, plus documented blocker-related issues |
| Security patch lag | Release log | ≤ 3 days behind Chrome stable security releases |

The targets are placeholders until Phase 0 produces a baseline. Nothing is marketed until it has been measured.

## 3. Guardrails

1. **Security matches upstream.** Site Isolation, the sandbox and component updates (CRLSets and similar) stay on. Any change that trades security for resources needs explicit sign-off and goes in the risk register.
2. **Every change is gated by a benchmark.** No patch merges without before-and-after numbers on the reference Mac.
3. **Patches stay small and isolated.** Keep a patch series rather than a fork, and prefer feature-flag or default flips over rewriting code.
4. **No Google services or branding.** No "Chrome" name or logo, and no reliance on Google API keys.

## 4. Phases

### Phase 0: Baseline and measurement (week 1–2)
- Pick one reference Mac. Fix its macOS version, close background apps, and run with power settings fixed and the battery charged.
- Extend `bench/` with:
  - `footprint`-based memory, which is closer to Activity Monitor than RSS
  - a `powermetrics` energy sampler
  - automated Speedometer 3.x, JetStream and MotionMark runs
  - cold-start timing
  - a 1-hour scripted browsing loop for battery
- Record baselines for Chrome stable, Chromium and Chromium with the Phase 1 profile.
- **Exit:** a reproducible baseline report, with run-to-run variance under 5%.

### Phase 1: Policy profile (done; needs validating on a Mac)
- `scripts/build_profile.py` generates `dist/Taurine.mobileconfig`. Policy names were checked against Chromium `main` (M160).
- **Remaining:** install it on the reference Mac, confirm `chrome://policy` shows the policies as Mandatory, and run the A/B benchmark.
- **Exit:** benchmark numbers for each policy group. Keep the ones that help; record the trade-offs of each.

### Phase 1.5: Launcher with command-line switches (week 3–4)
- A small signed `.app` wrapper that starts Chromium with tuned switches. Each candidate is benchmarked on its own:
  - `--renderer-process-limit=N` **[Fact: switch exists]**. Fewer processes means less memory but more tabs sharing a process **[Hyp]**.
  - `--process-per-site` **[Fact: switch exists]**. Same-site tabs share a process **[Hyp: saves memory on heavy same-site use]**.
  - `--enable-features` / `--disable-features` toggles for tab lifecycle, prerender and spare-renderer behaviour **[Hyp; exact feature names to be pulled from source per milestone]**.
- **Exit:** the switches that win get promoted to Phase 3 defaults; the rest are dropped.

### Phase 2: Build infrastructure (week 3–8, runs alongside 1.5)
- **Build host:** Apple Silicon Mac, ideally 32 GB+ RAM and 1 TB SSD **[Est]**.
  - Fetch requirements: about 30 GB for the git cache alone, and 30 minutes or more to fetch **[Fact: `docs/mac_build_instructions.md`]**. Checkout plus build output need a lot more disk on top **[Est]**.
  - Xcode and the macOS SDK are required **[Fact: same doc]**.
- **Build config:** `is_official_build=true` so PGO and ThinLTO switch on **[Fact]**; `target_cpu="arm64"`; `is_chrome_branded=false`; proprietary codecs enabled for H.264/AAC playback (check licensing).
- **Patch system:** a `patches/` folder plus a `series` file, applied with a script against a pinned Chromium tag (the same model as ungoogled-chromium). Track each patch's owner and the reason it exists.
- **Rebase automation:** a script that moves to the next stable tag, applies the series and reports which patches failed.
- **Compiler experiment:** `-mcpu=apple-m1` (or newer) against the default **[Hyp: small gain; the cost is dropping older Macs]**.
- **Exit:** reproducible signed builds from a pinned tag, with a clean build time recorded.

### Phase 3: Product patches (month 2–4)
Each item is a separate patch with its own benchmark.

1. **Built-in defaults:** move the Phase 1 policies and winning Phase 1.5 switches into code defaults, so no profile is needed.
2. **Content blocking** (likely the biggest real-world win on heavy sites **[Hyp]**). Options:
   - a. Ship uBlock Origin Lite preinstalled (lowest effort).
   - b. Native network-level blocker, for example Brave's `adblock-rust` **[licence and integration effort to verify]**.
   - c. Keep MV2 support so full uBlock Origin works. Upstream policy support ended in M138 **[Fact: `ExtensionManifestV2Availability` supported_on 110–138]**, so this means carrying a growing patch **[Hyp: high maintenance]**.
   - Do a spike on b vs. c before committing.
3. **Tab lifecycle:** shorter discard and freeze timers, discarding inactive tabs under moderate memory pressure, and showing tab memory in the UI.
4. **Background services:** remove or turn off component downloads that aren't security-critical (on-device AI models, optimization hints), promos and sign-in nudges, and anything that wakes the browser while idle.
5. **Process budget:** a renderer cap that scales with RAM, and smarter process sharing for same-site tabs.
6. **macOS specifics** **[Hyp]**, to be profiled with Instruments before any change:
   - lower QoS for background renderers
   - fewer timer wake-ups (App Nap friendliness)
   - check ANGLE/Metal and video-decode paths use hardware
7. **Startup:** lazy-load non-essential subsystems.

- **Exit:** every patch shows a measured gain and no regression in speed or site compatibility.

### Phase 4: Distribution (month 4–5)
- Apple Developer ID signing, notarization and hardened runtime.
- Auto-update via Sparkle, with a signed appcast and delta updates.
- Branding: a new name and icon, plus a non-Google about page and default search.
- First-run import from Chrome and Safari.
- **Exit:** a public beta DMG that auto-updates.

### Phase 5: Ongoing operations
- **Release train:** follow Chromium stable (about every 4 weeks) and ship security-only releases within 3 days.
- **CI on the build Mac:** nightly rebase against beta for early warning, plus a benchmark regression gate on every release.
- **Patch budget:** review the series every quarter and drop patches that no longer pay for themselves.

## 5. Resources [Est]

| Item | Need |
|---|---|
| People | 1 C++ engineer who knows Chromium (core), plus about 0.5 for release and infra |
| Hardware | 1 dedicated Apple Silicon build Mac, plus 1 reference benchmark Mac (could be the same machine at first) |
| Accounts | Apple Developer Program, update hosting and CDN |
| Time | About 5 months to a public beta at the scope above |

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Patch rebase breaks every release | High | Security lag | Few, small patches; nightly beta rebase; patch budget |
| Gains don't beat Chrome's own Memory/Energy Saver | Medium | Weak value | Phase 0/1 numbers decide whether Phase 2 goes ahead |
| Aggressive discarding causes data loss or annoying reloads | Medium | User churn | Exception lists, keep tabs with form input, tunable levels |
| Content blocking breaks sites | Medium | Support load | Per-site toggle, curated allowlist |
| MV2 retention becomes unmaintainable | High | Patch debt | Prefer native blocking (option 3b) |
| Signing or notarization blocks a release | Low | Delay | Automate in CI; keep certificates current |
| Trademark or licensing problems | Low | Legal | No Google marks; audit third-party licences (codecs, adblock-rust) |

## 7. Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| 1 | Should Phase 2 (custom build) go ahead? | Decide **after** the Phase 0/1 numbers. If the policies alone get most of the gain, ship a profile plus launcher and skip the fork. |
| 2 | Content blocking approach | Native blocker (3b) after a spike; uBO Lite in the meantime |
| 3 | Intel Mac support | Apple Silicon only, unless the user base requires Intel |
| 4 | Staffing and hardware budget | Needed before Phase 2 starts |
| 5 | Name and branding | Needed before Phase 4 |

## 8. Next steps

1. Get a session running on your Mac, or run it yourself: install the profile, confirm it in `chrome://policy`, then run `bench/bench.py` for the stock and taurine labels.
2. I extend `bench/` with `footprint`, `powermetrics` and the browserbench suites (Phase 0).
3. Review the baseline together, then make decision #1.
