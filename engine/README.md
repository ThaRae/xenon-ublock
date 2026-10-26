# Engine patches

A patch series against Ladybird that adds what uBlock Origin needs beyond Ladybird's content blocker. It applies to
the Ladybird commit in `LADYBIRD_BASE`, the one Xenon pins. The patched parts are BSD-2-Clause, like Ladybird, so
they can go upstream.

| Patch | What it adds |
|---|---|
| `0001` LibWeb+LibWebView: Give the content blocker uBlock Origin's resources | Trusted lists (`--trusted-content-blocker-list`) and uBO's resources (`--content-blocker-resources`), sent to every WebContent process. `adblock`'s `css-validation` feature. The Rust side of everything below: request decisions with surrogates and cleaned URLs, a `$popup` engine, `$cname` exceptions, the document-start script, the uncloak check |
| `0002` LibWeb: Answer $redirect filters with surrogates, and apply $removeparam | Surrogates served from `ResourceLoader` (with CORS headers for the requesting origin), `$removeparam` in main fetch (navigations end at the cleaned URL), the request method for `$method` |
| `0003` LibWeb: Run content blocker scriptlets and procedural filters at document start | The page's scriptlets (`##+js`) and a small runtime for procedural and action filters (`:has-text()`, `:upward()`, `:xpath()`, `:matches-css()`, `:remove()`, `:remove-attr()`, `:remove-class()`, ...), run before any page script in every document, about:blank frames and popups included |
| `0004` LibWeb: Block popups that the content blocker's $popup filters match | `window.open()`, `_blank` links and forms, and popups opened empty then sent somewhere |
| `0005` RequestServer+LibWeb: Uncloak CNAMEs for the content blocker | RequestServer reports a host that DNS shows to be an alias and waits; WebContent's blocker decides, following uBO's defaults. Works with the system resolver (`AI_CANONNAME`) and configured DNS servers |
| `0006` LibWeb+LibWebView+WebContent: Add an element picker for cosmetic filters | `ViewImplementation::start_element_picker()` on top of the DevTools node picker, a Block Element... context menu action, `Settings::add_custom_content_blocker_filter()` |

## Using them

Xenon carries these patches in its own Ladybird patch series, as `Patches/ladybird/0004` to `0009`, after Xenon's own
patches (see `integration/xenon/`). `Meta/xenon.py build` applies the whole series to the `ladybird` submodule with
`Meta/patches.py`. The files here use the same `format-patch` options as Xenon's, and they are the same commits,
based on plain Ladybird instead of on Xenon's patches.

For another Ladybird checkout, `apply.py` makes a patched copy for a build to use, and leaves the checkout alone:

```bash
engine/apply.py --ladybird ../ladybird --into build/ladybird-patched
```

The copy is a `git clone --shared` of the checkout (it borrows its objects) at `LADYBIRD_BASE`, with the patches as
commits. Running it again is a no-op unless the patches or the base changed, so a build can run it every time.
`--check` only tests that the patches apply.

Xenon passes the browser:

- `--trusted-content-blocker-list` for uBO's own lists (`"trusted": true` in `dist-xenon/manifest.json`, the
  `ublock-*` lists), which may use the scriptlets uBO reserves for trusted lists;
- `--content-blocker-list` for the others;
- `--content-blocker-resources dist-xenon/resources/ublock-resources.json`, uBO's scriptlets and redirect surrogates.

Build the lists for the patched engine with `tools/build.py --engine xenon`: they keep the scriptlets, procedural
filters, `$redirect-rule`, `$removeparam`, `$popup` and `$cname` filters that `--engine ladybird` drops.

## Testing

- `tools/e2e_engine.py --app PATH`: scriptlets (trusted and not), procedural filters and actions, surrogates,
  `$removeparam` on navigations and fetch, popups, `$method`, and the element picker's filters, in a patched Xenon.
- `tools/e2e_cname.py --app PATH [--live]`: uncloaking against a local DNS server with CNAME chains, and with `--live`
  through the system resolver.
- `tools/e2e_xenon.py --engine xenon --app PATH`: a whole preset, trusted lists and resources included.

Ladybird's own tests should still pass on the patched tree: `TestContentBlocker` and the RequestServer tests, and
the content blocker's web tests (`test-web --filter '*content-blocker*'`). Run `test-web` from inside the app bundle
(`Xenon.app/Contents/MacOS`) so it finds the helper processes, and give it a Python that has `cryptography`
(`--python-executable`); without it the fixture server has no HTTPS, and the HTTPS tests fail.

From Xenon's build tree, `test-web` doesn't find Ladybird's theme (it looks in `bin/../Resources`), so the
`display_list` tests that dump selection colors see black ones. Under full load, a media test can trip a VERIFY in
`HTMLMediaElement::handle_playback_manager_error`, and test-web then aborts while respawning the process. That's
upstream; run the rest of the suite in smaller `--filter` groups.

## Working on them

The patches are `git format-patch` output from a branch:

```bash
git clone --shared ../Xenon/ladybird build/ladybird-dev
git -C build/ladybird-dev checkout -b xenon-ublock $(cat engine/LADYBIRD_BASE)
git -C build/ladybird-dev am engine/patches/*.patch
# ... edit, commit or amend ...
rm engine/patches/*.patch
git -C build/ladybird-dev format-patch --zero-commit --no-numbered --no-signature --full-index -o "$PWD/engine/patches" $(cat engine/LADYBIRD_BASE)..
```

Keep Xenon's copies in step. To build and test a change, take it into a Xenon checkout's series: run
`Meta/patches.py apply` there, drop the six xenon-ublock commits from `ladybird/`'s `xenon-patches` branch (with
`git reset --hard HEAD~6` while they're the last ones), `git am --3way` the files from `engine/patches`, then
`Meta/patches.py export` and commit `Patches/ladybird`. A change made in Xenon's copy comes back the same way, in the
other direction: `git format-patch` those commits from `ladybird/`, `git am --3way` them in `build/ladybird-dev`, and
export.

When Xenon moves its submodule to a new Ladybird commit, rebase the branch onto it (`git rebase NEW`), fix any
conflicts, export the patches again, and write the new commit to `LADYBIRD_BASE`.

Things to know when changing them:

- `adblock` stays at the version Ladybird pins; `probe/` must use the same version and features
  (`css-validation`), or `tools/build.py --engine xenon` would judge filters differently from the engine.
- The procedural runtime is `Libraries/LibWeb/ContentBlocker/Rust/src/procedural.js`. It runs in the page's main
  world, like uBO's scriptlets. Ladybird has no isolated worlds yet, so pages can see and tamper with it.
- CNAME uncloaking costs one IPC round trip between RequestServer and WebContent for each request whose host DNS
  shows to be an alias (CDN hosts often are). It waits on WebContent's event loop, so a page busy running script
  delays those requests until it yields.
- Not covered yet: `$csp`, `$inline-script`, `$header`, `$permissions`, `$replace`, `$urlskip`, HTML filtering
  (`##^`), `:others()` and `:watch-attr()`, `$to` with positive domains, WebSocket and worker requests (WebSocket
  connections and worker fetches skip the content blocker in Ladybird).
