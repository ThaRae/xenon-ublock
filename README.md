# xenon-ublock

uBlock Origin's ad and tracker blocking for [Ladybird](https://ladybird.org)'s content blocker, so that Xenon (a
Ladybird browser with Helium's feature set) can ship it on by default the way [Helium](https://helium.computer) ships
uBlock Origin.

Ladybird has no WebExtensions, so uBlock Origin (uBO) cannot run in it. Ladybird does have a built-in content blocker:
Brave's `adblock` crate, which reads most of uBO's filter syntax. This repository turns uBO's default filter lists
into lists that blocker applies correctly. It fetches them, evaluates uBO's preprocessor, translates the syntax the
engine reads differently, drops what it cannot apply (with a report saying why), and checks the result against the
engine itself.

- [docs/gap-analysis.md](docs/gap-analysis.md): which uBO features work on Ladybird as-is, which this repo
  translates, and which need engine work.
- [docs/reports/](docs/reports/): what was kept, translated and dropped in the 2026-10-26 build.

## Status

What blocks today, with these lists loaded:

- **Network requests**: ads, trackers, malware and badware from every list uBO enables by default. 93.9% of the
  upstream filters in the `ubo` preset and 91.3% in the `helium` preset take effect.
- **Element hiding**: site-specific, generic and entity (`example.*`) rules, exceptions, and `:style()`.

What needs engine work (details and sizes in the gap analysis):

- **Scriptlets** (`##+js`), 10,352 of uBO's default filters. This is how uBO handles YouTube ads and most anti-adblock
  walls, and is the largest gap.
- **Surrogate resources** for `$redirect` (the request is blocked instead), `$removeparam` URL cleaning, `$csp`,
  popup blocking (`$popup`), procedural cosmetic operators (`:has-text()` and friends), HTML filtering, and CNAME
  uncloaking.
- **Engine bugs** that this repo works around and that affect any list loaded into Ladybird directly: one
  JavaScript-only regex silently disables every regex filter fused with it, regexes are lowercased (`\D` becomes
  `\d`), `$domain=site.*` never matches, and `$to`/`$denyallow` filters are discarded.

## Using it

Requirements: Python 3.11+, a Rust toolchain, a C compiler, and a Ladybird checkout for verification (by default
`../Xenon/ladybird`; override with `--ladybird` or `LADYBIRD_SOURCE_DIR`).

```bash
tools/build.py
```

That fetches and converts both presets into `dist/` (downloads are cached for 6 hours in `build/cache/`). Options:
`--preset ubo`, `--lang de --lang fr` (also build uBO's regional lists for those languages, as uBO does for the
browser's locale), `--offline`, `--refresh`.

```bash
tools/verify.py
```

That builds Ladybird's content blocker crate, unmodified, from the checkout (into `build/`, with `--locked`, so the
checkout is untouched), links a small C harness against it, and checks that:

- the engine still behaves the way the translations assume (`tests/engine-quirks.txt`);
- every list loads on its own, and each preset loads whole (it also times the engine build);
- known ad and tracker requests are blocked, ordinary ones are not, and cosmetic rules apply (`tests/vectors.txt`);
- sampled filters from every list take effect in the full preset.

```bash
tools/e2e_xenon.py --app ../Xenon/Build/release/bin/Xenon.app
```

That runs a built Xenon (or Ladybird) headless with a throwaway profile and a preset. It checks on a local test page
that ad requests never reach the server and decoy ads are hidden, and runs a control with blocking off.

## Presets

| Preset | Lists | Output |
|---|---|---|
| `ubo` | uBO's defaults: uBlock filters (Ads, Badware risks, Privacy, Quick fixes, Unbreak), EasyList, EasyPrivacy, Online Malicious URL Blocklist, Peter Lowe's list | 9 lists, 15.9 MiB, about 100 ms to build the engine |
| `helium` | What Helium's uBO fork (imputnet/uBlock) enables: the above, plus AdGuard Ads, AdGuard/uBO URL Tracking Protection, AdGuard and EasyList cookie notices, uBlock filters Cookie Notices and Annoyances, EasyList Newsletters and Notifications, and Helium's own Annoyances and Unbreak lists | 19 lists, 23.1 MiB, about 150 ms |

The list set comes from each project's `assets.json` at build time (entries without `"off": true`), so it follows
upstream. One override: both presets use the Vivaldi/Brave variant of the URLhaus list, which is written for the
engine Ladybird uses. Helium's fork uses the AdGuard variant, which is ten times the size.

For Xenon, `helium` is the closer match to Helium. Most of the size is URLhaus (11 MiB, about 98,000 malware URLs).
Each WebContent process builds its own engine from the full text, so a smaller set starts faster.

## Architecture

```
assets.json (uBO, or Helium's fork)         config/lists.json
          │ default-on lists                 (presets, !#if environment, licenses)
          ▼
 fetch + cache ──► uBO preprocessor ──► translate ──► probe ──► dist/<preset>/
 (tools/build.py)   !#if, !#include,     per line:     same       lists/<id>.txt
                    line continuations   keep, rewrite, adblock    all.txt
                                         or drop        version    dropped/<id>.tsv
                                                        as the     report.md
                                                        engine   dist/manifest.json
                                                          │
          ladybird/Libraries/LibWeb/ContentBlocker/Rust   │
          (built unmodified) ──► harness/engine_check.c ◄─┘ tools/verify.py
```

- **`tools/build.py`** is the converter. Translation rules, with the reasoning for each, are in the gap analysis. The
  rule it follows when rewriting: a translated filter may block less than uBO would, never more. Some translations
  are applied across a preset, which is fine because Ladybird loads all enabled lists into one engine. Generic
  `#@#selector` exceptions are applied by removing the hiding rules they cancel. Entity domains are expanded using the
  suffixes that the preset's lists use.
- **`probe/`** is a Rust program pinned to the exact `adblock` version and features Ladybird builds. `build.py` sends
  it every translated line and gets back how the engine parses it. Lines the engine rejects, or accepts without
  effect in Ladybird (`$csp`, `$removeparam`, `$redirect-rule`, `$method`, `$to`, regexes Rust cannot compile), are
  dropped. `tools/verify.py` fails if Ladybird moves to a different `adblock` version than the probe.
- **`harness/engine_check.c`** calls the same FFI functions as `Web::ContentBlocker`, on rules joined the way
  `WebView::Application` joins them.

### Output

`dist/manifest.json` lists every preset and list: title, file, size, SHA-256, filter counts by reason, the upstream
URL and its hash, every `!#include` that was followed, and the license. Each list file starts with a header naming its
source, license and what was kept. `dist/` is not committed; build it, or publish it from CI (see below).

## Bundling and enabling in Xenon

Ladybird already has everything needed to load these lists. What Xenon has to decide is how they reach the profile.
Turning ad blocking on is `Settings::set_content_blocker_enabled(true)`, which is what Ladybird's own welcome page
sends (`setContentBlockerEnabled`). Lists only take effect while that is on, and the per-site toggle
(`set_content_blocker_enabled_for_site`) applies to them too.

### Now: bundle the files

1. Build a preset and copy `dist/<preset>/lists/*.txt` and `dist/manifest.json` into the app bundle, for example
   `Xenon.app/Contents/Resources/content-blocking/`. Either vendor a snapshot or run `tools/build.py` from Xenon's
   build.
2. Hand them to Ladybird as `--content-blocker-list <path>` arguments. Xenon's `main()` can append them to the
   arguments before `Application::create()`; per Xenon's conventions that belongs in a Xenon-only file, with only a
   call added to the copied `main.cpp`.

   Do not add the paths in `create_platform_options()` instead. They would load at startup, but
   `apply_content_blocker_settings()` calls `rebuild_content_blocker_list_paths()`
   (`Libraries/LibWebView/Application.cpp:788`), which resets the paths to the command-line ones, so the lists would
   disappear the first time the user changes any blocking setting.
3. Have the welcome page's ad blocking switch call `setContentBlockerEnabled`. Leave Ladybird's built-in catalog
   (EasyList, EasyPrivacy, …) off: those are the raw upstream lists, which duplicate these and are loaded without
   any of the fixes above.

Trade-offs: the lists update only when Xenon does, and they do not appear in `about:settings` (explicit paths are not
in the list registry), so they cannot be toggled one by one.

### Later: subscribe by URL, for daily updates

Publish `dist/` from CI on a schedule (GitHub Pages or release assets of this repo; that needs a remote, which this
repo does not have yet). Xenon then registers each list with `Settings::add_content_blocker_list(name, url)`. Ladybird
lists it under custom subscriptions in `about:settings`, and re-downloads it every 24 hours while filter list updates
are on (`setFilterListUpdatesEnabled`, which Ladybird's welcome page turns on together with blocking). To block
before the first download, and offline, Xenon can seed each subscription's file
(`<profile data>/ContentBlocking/Lists/<identifier>.txt`) from the bundled copy. Ladybird loads any enabled list
whose file exists. Point subscriptions at the converted files, never at uBO's raw lists, which load almost nothing
(see the gap analysis).

`Application::import_local_content_blocker_list(name, contents)` is a middle ground: the lists show up in
`about:settings` and can be toggled, but never update.

## Licensing

This repository's code is GPL-3.0-or-later (see `LICENSE`), like uBlock Origin. It contains no uBO code; it
reimplements uBO's list semantics (preprocessor, hostname rules, generic exceptions) from uBO's documentation and
source.

The lists it produces are modified versions of third-party lists, each under its own license, recorded per list in
`config/lists.json`, in `dist/manifest.json`, and in each output file's header:

| Lists | License |
|---|---|
| uBlock filters: Ads, Badware risks, Privacy, Quick fixes, Unbreak, Annoyances, Cookie Notices; AdGuard/uBO URL Tracking Protection | GPL-3.0 ([uBlockOrigin/uAssets](https://github.com/uBlockOrigin/uAssets)) |
| EasyList, EasyPrivacy, EasyList Cookie Notices, Newsletters, Notifications | GPL-3.0-or-later or CC BY-SA 3.0-or-later, at your choice ([easylist.to](https://easylist.to/pages/licence.html)) |
| AdGuard Ads, AdGuard Cookie Notices | GPL-3.0 ([AdguardTeam/AdguardFilters](https://github.com/AdguardTeam/AdguardFilters)) |
| Helium filters: Annoyances, Unbreak | AGPL-3.0 ([imputnet/helium-services](https://github.com/imputnet/helium-services)) |
| Online Malicious URL Blocklist (URLhaus) | CC0-1.0 for the lists, MIT for the scripts ([malware-filter/urlhaus-filter](https://gitlab.com/malware-filter/urlhaus-filter)) |
| Peter Lowe's Ad and tracking server list | **No license stated.** The site credits Peter Lowe and asks questions to go to pgl@yoyo.org. Get permission before bundling it; uBO bundles a copy, but that is uBO's arrangement |
| uBO regional lists (`--lang`) | Various; not recorded. `build.py` flags them for review |

What shipping them in Xenon involves, in short (this is not legal advice): the GPL and AGPL lists are distributed
with Xenon in modified form, so ship their license texts, keep the notices (the output headers say where each list
came from and that it was converted), and make the source available: the upstream URLs and this repository. The
EasyList lists can be taken under the GPL like the rest. CC0 needs nothing. Peter Lowe's list needs permission, or
leave it out (`plowe-0` is 3,563 hostnames, most of which EasyList and EasyPrivacy also block).

## Layout

```
config/lists.json        presets, !#if environment, licenses
tools/build.py           fetch, preprocess, translate, report
tools/verify.py          check the output against Ladybird's real engine
tools/e2e_xenon.py       check the output in a built Xenon
probe/                   per-line parser check, pinned to Ladybird's adblock version
harness/engine_check.c   links Ladybird's content blocker crate
tests/                   engine behavior and preset expectations
docs/                    gap analysis, build reports
```
