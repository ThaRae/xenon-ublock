# xenon-ublock

uBlock Origin's ad and tracker blocking for [Ladybird](https://ladybird.org)'s content blocker, so that Xenon (a
Ladybird browser with Helium's feature set) can ship it on by default the way [Helium](https://helium.computer) ships
uBlock Origin.

Ladybird has no WebExtensions, so uBlock Origin (uBO) cannot run in it. Ladybird does have a built-in content blocker:
Brave's `adblock` crate, which reads most of uBO's filter syntax. This repository has two parts:

- **Lists** (`tools/build.py`): uBO's default filter lists, fetched, preprocessed, translated where the engine reads
  uBO's syntax differently, and trimmed to what the engine applies (with a report saying why), checked against the
  engine itself.
- **Engine patches** (`engine/`): a Ladybird patch series that adds what uBO needs beyond Ladybird's blocker:
  scriptlets, procedural cosmetic filters, `$redirect` surrogates, `$removeparam`, popup blocking, CNAME uncloaking,
  and an element picker, with uBO's own scriptlets and surrogates (`tools/build_resources.mjs`).
  `integration/xenon/` is the change that makes Xenon build with them.

- [docs/gap-analysis.md](docs/gap-analysis.md): which uBO features work on Ladybird as-is, which this repo
  translates, and which the engine patches add.
- [engine/README.md](engine/README.md): the patches, and how to use, test and rebase them.
- [docs/reports/](docs/reports/): what was kept, translated and dropped in the 2026-10-26 build.

## Status

| | Stock Ladybird (`--engine ladybird`) | With `engine/patches` (`--engine xenon`) |
|---|---|---|
| uBO's default filters that take effect | 93.9% (`ubo`), 91.3% (`helium`) | 99.5% (`ubo`), 99.3% (`helium`) |
| Network blocking, hiding, exceptions, `:style()` | Yes | Yes |
| Scriptlets (`##+js`): YouTube ads, anti-adblock walls | No | Yes, with uBO 1.75.0's scriptlets; `trusted-*` only from uBO's own lists |
| Procedural filters (`:has-text()`, `:upward()`, `:xpath()`, ...), `:remove()`, `:remove-attr()`, `:remove-class()` | No | Yes |
| `$redirect` surrogates, `$redirect-rule` | Blocks without a surrogate | Yes |
| `$removeparam` | No | Plain parameter names (adblock rejects regexes) |
| `$popup` | No | `window.open()`, `_blank` links and forms, popups navigated later |
| CNAME uncloaking | No | Yes, uBO's defaults, `$cname` exceptions |
| Element picker | No | Block Element... in the context menu |
| `$method` | No | Yes |

Still not covered, even with the patches: `$csp`, `$header`, `$permissions`, `$replace`, `$urlskip`, HTML filtering,
`:others()`/`:watch-attr()`, `$to` with positive domains, and WebSocket and worker requests (see the gap analysis).

The lists also work around engine bugs that affect any list loaded into Ladybird directly: one JavaScript-only regex
silently disables every regex filter fused with it, regexes are lowercased (`\D` becomes `\d`), `$domain=site.*`
never matches, and `$to`/`$denyallow` filters are discarded.

## Using it

Requirements: Python 3.11+, a Rust toolchain, a C compiler, and a Ladybird checkout for verification (by default
`../Xenon/ladybird`; override with `--ladybird` or `LADYBIRD_SOURCE_DIR`).

```bash
tools/build.py
```

That fetches and converts both presets into `dist/` (downloads are cached for 6 hours in `build/cache/`), and builds
uBO's scriptlets and redirect surrogates into `dist/resources/` (needs Node.js; `--no-resources` skips it). Options:
`--engine xenon` (lists for Ladybird with `engine/patches`, into `dist-xenon/`), `--preset ubo`, `--lang de --lang
fr` (also build uBO's regional lists for those languages, as uBO does for the browser's locale), `--offline`,
`--refresh`.

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
that ad requests never reach the server and decoy ads are hidden, and runs a control with blocking off. With
`--engine xenon`, it passes a `dist-xenon` preset the way Xenon does, trusted lists and resources included.

For a Xenon built with `engine/patches`, `tools/e2e_engine.py` and `tools/e2e_cname.py` check each engine feature
(see [engine/README.md](engine/README.md)).

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

Xenon (from commit `578e2b1`) bundles the `helium` preset with `Meta/update-filter-lists.py` and passes it as
`--content-blocker-list` arguments (`UI/FilterLists.cpp`), as described below.

`integration/xenon/0001-Build-Ladybird-with-xenon-ublock-s-engine-patches.patch` takes it the rest of the way. Apply it
to Xenon with `git am`, then run `Meta/update-filter-lists.py`:

- `Meta/xenon.py` builds Ladybird from `Build/ladybird-patched`, which `engine/apply.py` makes from the `ladybird`
  submodule (left as it is) and refreshes when the patches change. It finds this repo through `XENON_UBLOCK_DIR`,
  `./xenon-ublock` (a submodule there works for CI) or `../xenon-ublock`. The first build after it reconfigures and
  rebuilds everything.
- `Meta/update-filter-lists.py` converts the lists for the patched engine, puts uBO's own lists in
  `trusted-lists/` and uBO's resources in `resources/`. `UI/FilterLists.cpp` passes them as
  `--trusted-content-blocker-list` and `--content-blocker-resources`.
- Block Element... in the context menu ends in a dialog that shows the filter for the picked element, to edit and
  add to the custom filters (`UI/ElementPicker.cpp`).

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

Publish `dist/` (or `dist-xenon/`) from CI on a schedule, for example as release assets of this repo on
git.avx512.dev. Xenon then registers each list with `Settings::add_content_blocker_list(name, url)`. Ladybird
lists it under custom subscriptions in `about:settings`, and re-downloads it every 24 hours while filter list updates
are on (`setFilterListUpdatesEnabled`, which Ladybird's welcome page turns on together with blocking). To block
before the first download, and offline, Xenon can seed each subscription's file
(`<profile data>/ContentBlocking/Lists/<identifier>.txt`) from the bundled copy. Ladybird loads any enabled list
whose file exists. Point subscriptions at the converted files, never at uBO's raw lists, which load almost nothing
(see the gap analysis).

`Application::import_local_content_blocker_list(name, contents)` is a middle ground: the lists show up in
`about:settings` and can be toggled, but never update.

## Licensing

This repository's code is GPL-3.0-or-later (see `LICENSE`), like uBlock Origin. It reimplements uBO's list semantics
(preprocessor, hostname rules, generic exceptions) from uBO's documentation and source. The engine patches in
`engine/patches/` modify Ladybird and are BSD-2-Clause, like Ladybird, so they can go upstream.

`dist/resources/ublock-resources.json` is built from uBlock Origin's source (its scriptlets and the files in
`web_accessible_resources`), and is GPL-3.0 like uBO; uBO's license is copied next to it.

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
config/lists.json        presets, !#if environment, licenses, the uBO release for resources
tools/build.py           fetch, preprocess, translate, report (--engine ladybird | xenon)
tools/build_resources.mjs  uBO's scriptlets and redirect surrogates as adblock resources
tools/verify.py          check the output against Ladybird's real engine
tools/e2e_xenon.py       check the output in a built Xenon
tools/e2e_engine.py      check the engine patches' features in a patched Xenon
tools/e2e_cname.py       check CNAME uncloaking, with a local DNS server
engine/                  the Ladybird patch series, apply.py, and its README
integration/xenon/       the Xenon change that builds with the patches
probe/                   per-line parser check, pinned to Ladybird's adblock version and features
harness/engine_check.c   links Ladybird's content blocker crate
tests/                   engine behavior and preset expectations
docs/                    gap analysis, build reports
```
