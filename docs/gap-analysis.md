# uBlock Origin on Ladybird: gap analysis

What of uBlock Origin (uBO), and of the uBO fork that Helium ships, can run on Ladybird's content blocker. What this
repository does about the rest, and what needs engine work.

Based on Ladybird at `c6f7e21193` (the submodule pinned in Xenon on 2026-10-26), whose blocker is Brave's `adblock`
crate 0.13.3 with default features. Every claim below about engine behavior is checked by `tests/engine-quirks.txt`
against the real engine (see [Verification](#verification)). Paths are relative to the `ladybird/` checkout unless
they start with `adblock/`, which means `~/.cargo/registry/src/*/adblock-0.13.3/`.

## Summary

| uBO feature | Ladybird today | With this repo | Engine work needed |
|---|---|---|---|
| Static network filtering | Most syntax and options | 94% of uBO's default filters load and take effect | `$redirect` resources, `$removeparam`, `$csp`, `$method`, `$to`, entity domains, popups, CNAME |
| Cosmetic filtering (hiding) | Specific, generic, entity, exceptions, `:style()` | Generic `#@#` exceptions and `:remove()` translated | Procedural operators, `:remove-attr/-class` |
| Scriptlet injection (`##+js`) | Parsed, never injected | Dropped (10,352 filters in uBO's defaults) | Resources plus document-start injection: the biggest gap |
| Redirect resources | `$redirect` blocks without a surrogate; `$redirect-rule` inert | Kept as blocking filters | Load resources; serve `BlockerResult::redirect` |
| HTML filtering (`##^`) | Not supported | Dropped | Response-stream filtering (uBO only does this on Firefox) |
| Element picker | None. Custom filters are stored and applied | Nothing to do here | Picker UI in Xenon plus a small WebContent hook |
| Per-site toggle | Yes, per exact host | Nothing to do here | Optional: subdomain matching, uBO's per-site switches |
| CNAME uncloaking (Helium) | No | Dropped `$cname` exceptions | DNS-aware re-check in RequestServer |
| List preprocessing (`!#if`, `!#include`, hosts files) | No | Done at build time | Only needed if raw uBO lists are subscribed to directly |

So what blocks today, with this repo's lists: ad, tracker and malware **requests** from all of uBO's default lists
(EasyList, EasyPrivacy, uBO's own lists, URLhaus, Peter Lowe's), and **element hiding** with specific, generic and
`:style()` rules. What does not: anything that needs JavaScript in the page (scriptlets, which are how uBO handles
YouTube ads and most anti-adblock walls), surrogate scripts, URL cleaning, popups, and CNAME uncloaking.

## How Ladybird's blocker works

- **One engine per WebContent process, built from all lists at once.** The UI process concatenates every enabled
  list file, the `--content-blocker-list` files and the custom filters into one buffer
  (`Libraries/LibWebView/Application.cpp:799`, `load_content_blocker_lists`). Each WebContent process passes the
  whole buffer to `rust_content_blocker_create`, which calls `FilterSet::add_filter_list` with `ParseOptions::default()`
  and `Engine::new_with_filter_set` (`Libraries/LibWeb/ContentBlocker/Rust/src/lib.rs:350`). No resources are loaded
  and no scriptlet permissions are granted. If the buffer is not valid UTF-8, creation fails and nothing is blocked.
- **Network.** `ResourceLoader` asks `ContentBlocker::is_filtered` for every fetch, with the page URL as the source
  and a request type derived from the fetch destination or initiator (`Libraries/LibWeb/Loader/ResourceLoader.cpp:233`,
  `Libraries/LibWeb/Loader/ContentBlocker.cpp`). Only `BlockerResult::should_block()` is used; the request method is
  passed as an empty string (`lib.rs:394`). DNS prefetch and preconnect are filtered too, typed `other`.
- **Cosmetic.** `Document::content_blocker_style_sheet()` (`Libraries/LibWeb/DOM/Document.cpp:1110`) collects the
  document's classes and ids and asks the engine for CSS: specific `hide_selectors`, plus generic class/id rules when
  there is no `$generichide`, plus any procedural action that `as_css()` can express (a plain selector, or a selector
  with `:style()`) (`lib.rs:272`). Each rule becomes `selector { display: none !important; }`. The sheet is added to
  the **user** style sheet (`Libraries/LibWeb/CSS/StyleScope.cpp:281`), so its `!important` beats the page's. New
  classes and ids re-query the engine (`Libraries/LibWeb/DOM/Element.cpp:288`).
- **Settings.** `Settings` keeps the on/off switch, a catalog of built-in lists (EasyList and friends, all off by
  default, `Libraries/LibWebView/Settings.cpp:498`), custom subscriptions by URL, imported local lists, custom
  filters, and per-site exceptions. Subscriptions are re-downloaded every 24 hours when filter updates and background
  networking are on. Limits: 64 MiB per list, 256 MiB combined (`Application.cpp:102`).

## Static network filtering

### Supported as-is

Hostname anchors (`||`), left and right anchors (`|`), wildcards (`*`), separators (`^`), exceptions (`@@`),
`/regex/` patterns that Rust's `regex` crate accepts, and these options (`adblock/src/filters/abstract_network.rs`):

`domain=`/`from=` (plain hostnames), `third-party`/`3p`, `first-party`/`1p`, `script`, `image`, `stylesheet`/`css`,
`object`, `subdocument`/`frame`, `xmlhttprequest`/`xhr`, `websocket`, `font`, `media`, `ping`/`beacon`, `other`,
`document`/`doc`, `all`, `important`, `badfilter`, `match-case` (on `/regex/` only), `generichide`/`ghide`.

`$document` blocks the navigation. uBO shows a "strict blocking" page that lets the user continue; Ladybird just fails
the load. That matters for uBO's Badware list, which is mostly `$doc` filters: users get no explanation and no way
through except turning the blocker off for the site.

### Translated by this repo

| uBO syntax | Problem in the engine | Translation | Filters (uBO / Helium preset) |
|---|---|---|---|
| Hosts-file lines (`127.0.0.1 host`) | Parsed as a URL substring with a space; never matches | `\|\|host^` | 3,563 / 3,563 (all of Peter Lowe's) |
| Bare hostname or `\|\|host` without `^`, no options | Substring match; uBO matches the hostname | `\|\|host^` (uBO's `reHostnameAscii` test) | 12 / 22 |
| `$denyallow=a.com`, `$to=~a.com` | `$to` filters are discarded by the builder (`adblock/src/filters/fb_network_builder.rs:262`) | Block filter plus `@@\|\|a.com^$same-options`, only when scoped with `$domain` and `a.com` is not a TLD; kept or dropped together | 248 / 268 |
| `*$opts,to=a.com` | Same | `\|\|a.com^$opts` | 3 / 3 |
| `$domain=site.*` (entity) | Entries are hashed literally (`adblock/src/filters/network.rs:480`); `site.*` never matches, `~site.*` never excludes | Expanded to `site.com\|site.net\|…`: 34 common suffixes plus every suffix the preset's lists use for that name. An approximation: uBO matches every public suffix | 282 / 401 |
| `/regex/` with `\D`, `\W`, `\S` | Patterns without `$match-case` are ASCII-lowercased before compiling (`network.rs:836`), turning `\D` into `\d` | `[^0-9]`, `[^0-9a-z_]`, `[^\s]` | 1 / 12 |
| `/regex/` containing `$`, no options | Options start at the last `$`, inside the regex | `$` → `\z`, literal `\$` → `\x24` | 0 / 2 |
| `$empty`, `$mp4` | Unknown options drop the filter | `$redirect=empty`, `$media,redirect=noopmp4-1s` | 0 / 0 |
| `$elemhide`/`$ehide` on exceptions | Unknown option | `$generichide` (the generic half; there is no `$specifichide`) | 3 / 16 |
| `$strict3p` (block), `$strict1p` (exception) | Unknown option | `$3p` / `$1p`: only where the result blocks no more than uBO | 6 / 6 |
| `$reason=`, `$_` | Unknown option | Removed (a message for uBO's blocking page; a no-op) | 16 / 23 |

### Dropped: needs engine work

| uBO syntax | What the engine does | What it would take | Filters (uBO / Helium) |
|---|---|---|---|
| `$popup`, `$popunder` | Unknown option | Check `window.open` and `target=_blank` navigations with a popup type. Ladybird's own popup blocker covers some of this | 3,149 / 3,259 |
| `$redirect-rule=` | Only fills `BlockerResult::redirect`, which Ladybird ignores | See [Redirect resources](#redirect-resources) | 476 / 545 |
| `$removeparam` | Only fills `BlockerResult::rewritten_url`, ignored. Regex values are rejected | Follow `rewritten_url` (redirect the request, or rewrite before navigation) | 269 / 3,001 (almost all of Helium's URL Tracking Protection list) |
| `$to=` with positive TLD lists (`$doc,to=com`) | Discarded by the builder | Upgrade `adblock` or stop skipping `$to` filters in its builder | 306 / 306 |
| `$csp`, `$inline-script`, `$inline-font` | `$csp` filled into a list nobody queries | Append `Engine::get_csp_directives()` to document responses as a `Content-Security-Policy` header | 90 / 121 |
| `$method=` | Never matches: the method is passed as `""` (`lib.rs:394`) | Pass the request method through `rust_content_blocker_matches` | 48 / 49 |
| `$urlskip=`, `$uritransform=` | Unknown option | URL rewriting before navigation | 261 / 269 |
| `$header=`, `$requestheader=` | Unknown option | Match on response headers after they arrive | 36 / 51 |
| `$ipaddress=` | Unknown option | Match after DNS resolution, in RequestServer | 36 / 36 |
| `$cname` (exceptions) | Unknown option | Comes with [CNAME uncloaking](#cname-uncloaking) | 29 / 29 |
| `$replace=` | Unknown option | Response body rewriting (uBO does this only on Firefox) | 18 / 21 |
| `$permissions=` | Unknown option | Append a `Permissions-Policy` header | 1 / 4 |
| `$shide`/`$specifichide` | Unknown option | A small addition to `adblock` | 1 / 1 |
| Other options `adblock` does not know (`$top=`, `$genericblock`, regex `$removeparam`) | Unknown option | Case by case | 1 / 4 |
| `$strict1p` (block), `$strict3p` (exception) | Unknown option | Hostname-level party check | 15 / 16 |
| JavaScript-only regex (look-around, back-references) | `regex` cannot compile it | None in Rust's `regex`; keep dropping | 29 / 47 |
| Regex `$domain` entries | Silently removed | Regex domain support in `adblock` | 1 / 2 |

### Engine bugs this repo works around

These make some valid filters silently ineffective in Ladybird today, including for any list a user subscribes to
directly. They belong upstream in `adblock` (or in Ladybird's copy of how it uses it).

1. **One bad regex disables its whole group.** The optimizer fuses option-identical, token-less filters into one
   `RegexSet` (`adblock/src/optimizer.rs:14`). If any member fails to compile (`adblock/src/regex_manager.rs:234`), the
   whole set never matches, with no error. uBO's lists contain dozens of JavaScript-only regexes. `build.py` asks the
   probe to compile every `/regex/` and drops the ones that fail.
2. **Regexes are lowercased.** `\D`, `\W`, `\S`, `\B`, `\P{…}` change meaning. `build.py` rewrites the first three
   and drops the rest.
3. **Entity domains in `$domain` never match**, and a negated one (`~site.*`) never excludes, which makes a filter
   apply on the very site it was meant to skip.
4. **`$to` (and so `$denyallow`) filters are discarded** after parsing, without a warning.
5. **`:style()` is not validated.** `css-validation` is off, so `url(…)`, `\` and `}` pass through into the generated
   style sheet, and a list or custom filter can inject arbitrary CSS into every page. `build.py` rejects unsafe styles
   and selectors that are unbalanced or contain `{`, `}` or `;`. Ladybird should enable `adblock`'s `css-validation`
   feature or validate before building the sheet.
6. **Invalid UTF-8 anywhere disables all blocking**: `rust_content_blocker_create` returns null for the whole
   buffer. `build.py` only writes UTF-8.

## Cosmetic filtering

| uBO syntax | Ladybird today | This repo |
|---|---|---|
| `example.com##sel`, `example.*##sel`, `~sub.example.com` | Works | Kept |
| `##sel` (generic) | Works: class/id-keyed rules when the page has that class or id, others always | Kept |
| `example.com#@#sel` | Works | Kept |
| `#@#sel` (generic exception) | Rejected by `adblock` | Applied at build time: the preset is one engine, so the hiding rules it cancels are removed from every list, as uBO does on every page (57 exceptions, 54 rules) |
| `~a.com,b.com#@#sel` | Rejected (`double-negation`) | The negated hosts are removed, which only widens the exception |
| `$generichide`, `$elemhide` | `$generichide` works | `$elemhide` → `$generichide` |
| `$specifichide` | Not supported | Dropped |
| `:style(…)` | Works (applied as CSS) | Kept if the style is safe; generic `:style()` is rejected by the engine, as in uBO |
| `:remove()` | Parsed, never applied | Turned into plain hiding (72 / 255 filters) |
| `:remove-attr()`, `:remove-class()` | Parsed, never applied | Dropped (needs DOM mutation, 98 / 127) |
| Procedural: `:has-text`, `:upward`, `:xpath`, `:matches-css`, `:matches-path`, `:min-text-length`, `:watch-attr`, `:others`, … | Passed through as CSS (css-validation is off), then dropped by Ladybird's CSS parser | Dropped (790 / 2,323). Needs a procedural engine in WebContent (a DOM observer that evaluates the operators) |
| `:has()`, `:is()`, `:not()` | Plain CSS, applied by Ladybird | Kept; `:-abp-has()` becomes `:has()` |
| `#?#` | Same as `##` | Normalized to `##` |
| `[$path=…]host##`, regex hostnames | Rejected | Dropped (6 / 14) |
| `##^…` HTML filtering | Rejected | Dropped (161 / 193) |
| AdGuard `#$#`, `#%#`, `$$` | Rejected | Dropped |

The engine has one limitation that does not matter for real sites: site-specific rules cannot target an IPv6 literal
host.

## Scriptlet injection

**Not possible today; the largest gap.** `##+js(…)` filters parse, and `Engine::url_cosmetic_resources()` returns
their code in `injected_script`, but only if resources were loaded, and Ladybird neither loads any nor has a place to
inject them. 10,352 of uBO's default filters (22,894 in Helium's preset) are scriptlets. They are uBO's main tool for
YouTube and Twitch ads (`json-prune`, `trusted-replace-xhr-response`), anti-adblock walls (`set`, `aopr`, `acs`), and
popunders (`nowoif`). The per-scriptlet counts are in `docs/reports/`.

What it would take:

1. **Resources.** Build `adblock`'s resource list from uBO's `scriptlets.js` and `web_accessible_resources`
   (`adblock` has a `resource-assembler` feature, and Brave publishes the same data as `brave/adblock-resources`), ship
   it with Xenon, and call `Engine::use_resources()`. uBO's resources are GPL-3.0.
2. **Permissions.** uBO restricts `trusted-*` scriptlets to trusted lists. Pass a `PermissionMask` in `ParseOptions`
   for uBO's own lists only, which means parsing those lists separately from user subscriptions.
3. **Injection.** Run `injected_script` in the page's main world before any page script, in every frame including
   `about:blank` ones, on every navigation. That needs a document-start hook in LibWeb.

## Redirect resources

`$redirect=` filters both block and redirect. Ladybird only blocks, so the page gets a failed request instead of a
neutered surrogate (`noopjs`, `google-ima.js`, `googletagmanager_gtm.js`, a 1×1 GIF). That can break pages that the
surrogate exists to keep working. `$redirect-rule=` does nothing. `build.py` keeps `$redirect=` filters (they still
block, and will redirect once Ladybird can) and drops `$redirect-rule=`.

What it would take: the same resources as scriptlets, then, in `ResourceLoader`, serving `BlockerResult::redirect`
(a `data:` URL) as the response body instead of failing the request.

## Element picker

uBO's picker highlights the element under the pointer, proposes a cosmetic filter (and network filters for the
element's resources), previews it, and saves it to "My filters". Ladybird has the back half: custom filters are
stored in settings (`Settings::set_custom_content_blocker_filters`) and applied by the engine. The front half is
missing:

- **WebContent:** a pick mode that hit-tests, outlines the hovered element, and returns a CSS selector for it (and
  candidate resource URLs). The inspector's DOM-node highlighting is a starting point.
- **Xenon:** UI to refine the selector, preview, and append `host##selector` to the custom filters.

Every save rebuilds the engine in every WebContent process (about 100–160 ms each with these presets).

## Per-site toggle

Ladybird has it: `Settings::set_content_blocker_enabled_for_site()` stores hosts, and `Page` skips both network and
cosmetic filtering when the top-level document's host is in the set (`Libraries/LibWeb/Page/Page.cpp:1913`). Xenon
only needs a toolbar control for it.

Differences from uBO: the match is on the exact host (disabling `example.com` does not cover `www.example.com`; uBO's
trusted-site directives cover subdomains), and uBO's other per-site switches (no cosmetic filtering, no popups, no
large media, no remote fonts, no JavaScript) and dynamic filtering rules have no counterpart.

## CNAME uncloaking

Helium's fork adds a `chrome.dns.resolve()` with a `canonical_name` flag so uBO can do on Chromium what it does on
Firefox: resolve each request's host, and if it is a CNAME alias (a first-party subdomain pointing at a tracker), run
the request through the filters again with the canonical name. Helium's patch is
`patches/helium/core/ublock-dns-uncloaking.patch` in imputnet/helium.

In Ladybird, filtering happens in WebContent before DNS, and DNS happens in RequestServer (with LibDNS, which sees
CNAME chains). What it would take:

1. After resolution in RequestServer, if the canonical name differs from the request host, re-check the request with
   the canonical host, either with a blocker instance in RequestServer or an IPC round trip to WebContent.
2. Honor `$cname` exceptions (`@@||host^$cname`, 29 in uBO's lists) and uBO's defaults: skip first-party aliases and
   anything behind a proxy.

There is no list-level substitute. AdGuard publishes lists of known disguised tracker subdomains
(AdguardTeam/cname-trackers), which block some of the same requests by name, but that is not uncloaking.

## List loading and preprocessing

Ladybird feeds list text straight to `adblock`, which treats `!` lines as comments. So a uBO list subscribed to
directly loses a lot:

- **`!#include`** is not followed. uBO's own lists are mostly includes: `filters.txt` is a header plus includes of
  `filters-2020.txt` … `filters-2026.txt`, so subscribing to its URL loads almost nothing.
- **`!#if` / `!#else`** are ignored, so both branches load: Firefox-only, Safari-only, mobile-only and uBO-Lite
  filters all apply.
- **Hosts-file lists** (Peter Lowe's, Dan Pollock's) do not match at all, and bare hostnames match as substrings.

`build.py` evaluates `!#if` with a Ladybird environment (`config/lists.json`: `ext_ublock` and `cap_user_stylesheet`
true, everything else false), follows same-directory includes, joins ` \` line continuations, and rewrites hosts
lines, so the output needs none of this.

## Other uBO features

| Feature | Ladybird |
|---|---|
| Blocked-request count | Yes (`show_content_blocker_count`, `page_did_block_resource`) |
| Filter list updates | Yes, every 24 hours, for lists with a URL |
| Strict blocking page for `$document` | No: the load just fails |
| Logger | No (blocked requests are logged with `dbgln`) |
| Dynamic filtering, "My rules" | No |
| Regional lists by locale | Not automatic; `build.py --lang` builds uBO's regional lists for given languages |

## Verification

- `tests/engine-quirks.txt` asserts every engine behavior above against Ladybird's real crate, built unmodified from
  the submodule and linked into `harness/engine_check.c`.
- `tools/verify.py` loads every built list alone and each preset whole into that engine, runs `tests/vectors.txt`, and
  samples filters from every list to check they take effect in the full preset. On the 2026-10-26 build, 99.9% (uBO)
  and 99.8% (Helium) of samples did; the rest are cancelled by exceptions in uBO's unbreak lists, as intended.
- `tools/e2e_xenon.py` runs the built Xenon headless with the preset and a throwaway profile, and checks on a local
  page that ad requests never reach the server and decoy ads are hidden, with a control run with blocking off.

## Drop reasons

The ids used in `dist/<preset>/report.md` and `dropped/*.tsv`.

| Reason | Meaning |
|---|---|
| `needs-engine:scriptlets` | `##+js()` or AdGuard `#%#` |
| `needs-engine:procedural` | uBO/ABP/AdGuard procedural cosmetic operators |
| `needs-engine:dom-actions` | `:remove-attr()`, `:remove-class()` |
| `needs-engine:html-filtering` | `##^…` or AdGuard `$$` |
| `needs-engine:popup` | `$popup`, `$popunder` |
| `needs-engine:url-rewrite` | `$urlskip`, `$uritransform`, `$urltransform` |
| `needs-engine:response-headers`, `:request-headers` | `$header`, `$requestheader` |
| `needs-engine:response-rewrite` | `$replace` |
| `needs-engine:csp-injection` | `$inline-script`, `$inline-font` |
| `needs-engine:permissions-policy` | `$permissions` |
| `needs-engine:ip-address` | `$ipaddress` |
| `needs-engine:cname` | `$cname` |
| `needs-engine:specifichide` | `$specifichide`, `$shide` |
| `inert:*` | The engine accepts the filter but it has no effect in Ladybird (`csp`, `removeparam`, `redirect-rule`, `method`, `to`) |
| `regex-unsupported` | `/regex/` that Rust's `regex` rejects (would also disable fused regexes) |
| `regex-uppercase-escape` | `/regex/` with `\B`, `\A`, `\Z`, `\P`, `\Q`, which lowercasing breaks |
| `regex-domain`, `regex-hostname` | Regex in `$domain` or before `##` where removing it would widen the filter, or nothing else is left |
| `strict-party` | `$strict1p`/`$strict3p` where `$1p`/`$3p` would block more than uBO |
| `generic-exception-applied` | A `#@#sel` exception, applied by removing what it cancels |
| `cancelled-by-generic-exception` | A hiding rule that a generic exception in the preset turns off |
| `generic-style` | `##sel:style()` without a hostname (rejected by uBO and the engine) |
| `unsafe-style` | `:style()` with `url(`, `\`, `{`, `}`, comments or `@import` |
| `malformed-selector` | Unbalanced, or contains `{`, `}` or `;` |
| `location-modifier` | `[$path=…]` before `##` |
| `adguard-css-injection` | AdGuard `#$#` |
| `negated-exception` | A cosmetic exception with only negated hostnames |
| `unsupported-option` | Any other option `adblock` does not know |
| `engine-rejects:*` | Anything else the probe says the engine rejects, with its error |
| `invalid-utf8` | A line that was not valid UTF-8 upstream |
