# Helium defaults: conversion report

Built 2026-10-26 17:28 UTC for adblock 0.13.3, as built into Ladybird's LibWeb/ContentBlocker.

351,261 of 384,707 upstream filters kept (91.3%), written as 353,176 filters.
Counts are per upstream filter line, after uBO's preprocessor. One upstream line can become several filters (a hosts-file line with several names, or a `$denyallow` filter and its exceptions).

## Lists

| List | Upstream filters | Kept | Translated | Dropped | Output filters | Size |
|---|---:|---:|---:|---:|---:|---:|
| Helium filters – Annoyances (`helium-annoyances`) | 1 | 1 | 0 | 0 | 1 | 0 KiB |
| Helium filters – Unbreak (`helium-unbreak`) | 3 | 0 | 0 | 3 | 0 | 0 KiB |
| uBlock filters – Ads (`ublock-filters`) | 23,275 | 12,238 | 498 | 11,037 | 13,732 | 1,307 KiB |
| uBlock filters – Badware risks (`ublock-badware`) | 4,983 | 4,661 | 11 | 322 | 4,653 | 130 KiB |
| uBlock filters – Privacy (`ublock-privacy`) | 1,813 | 980 | 11 | 833 | 983 | 35 KiB |
| uBlock filters – Unbreak (`ublock-unbreak`) | 2,551 | 2,025 | 22 | 526 | 2,025 | 138 KiB |
| uBlock filters – Quick fixes (`ublock-quick-fixes`) | 461 | 244 | 15 | 217 | 247 | 25 KiB |
| AdGuard – Ads (`adguard-generic`) | 53,755 | 48,069 | 291 | 5,686 | 48,511 | 4,827 KiB |
| EasyList (`easylist`) | 74,639 | 71,319 | 6 | 3,320 | 71,309 | 1,828 KiB |
| AdGuard/uBO – URL Tracking Protection (`adguard-spyware-url`) | 2,713 | 1 | 0 | 2,712 | 1 | 0 KiB |
| EasyPrivacy (`easyprivacy`) | 56,384 | 56,350 | 10 | 34 | 56,348 | 1,444 KiB |
| Online Malicious URL Blocklist (`urlhaus-1`) | 98,191 | 98,191 | 0 | 0 | 98,191 | 11,279 KiB |
| AdGuard – Cookie Notices (`adguard-cookies`) | 20,558 | 19,187 | 48 | 1,371 | 19,187 | 1,161 KiB |
| EasyList – Cookie Notices (`fanboy-cookiemonster`) | 28,160 | 25,636 | 6 | 2,524 | 25,634 | 969 KiB |
| uBlock filters – Cookie Notices (`ublock-cookies-easylist`) | 2,376 | 214 | 4 | 2,162 | 214 | 22 KiB |
| EasyList – Newsletter Notices (`easylist-newsletters`) | 6,055 | 5,724 | 1 | 331 | 5,723 | 260 KiB |
| EasyList – Notifications (`easylist-notifications`) | 1,686 | 1,595 | 3 | 91 | 1,591 | 64 KiB |
| uBlock filters – Annoyances (`ublock-annoyances`) | 3,540 | 1,263 | 4 | 2,277 | 1,263 | 127 KiB |
| Peter Lowe’s Ad and tracking server list (`plowe-0`) | 3,563 | 3,563 | 3,563 | 0 | 3,563 | 68 KiB |

## Dropped, by reason

| Reason | Filters | Examples |
|---|---:|---|
| `needs-engine:scriptlets` | 22,894 | ublock-filters: `tv.youtube.com##+js(trusted-replace-xhr-response, '"adPlacements"', '"no_ads"', /playlist\?list=\|\/player(?:\?.+)?$\|watch\?[tv]=/)`<br>ublock-filters: `www.youtube.com##+js(trusted-replace-xhr-response, /"adPlacements.*?([A-Z]"\}\|"\}{2\,4})\}\]\,/, , /playlist\?list=\|\/player(?:\?.+)?$\|watch\?[tv]=/)`<br>ublock-filters: `www.youtube.com##+js(trusted-replace-xhr-response, /"adPlacements.*?("adSlots"\|"adBreakHeartbeatParams")/gms, $1, /\/player(?:\?.+)?$/)` |
| `needs-engine:popup` | 3,259 | ublock-filters: `\|\|bit.ly^$popup,domain=eurogamer.net`<br>ublock-filters: `*$popup,domain=clik.pw,3p`<br>ublock-filters: `*$popunder,domain=realgfporn.com` |
| `inert:removeparam` | 3,001 | ublock-filters: `\|\|fastlane.rubiconproject.com^$removeparam,domain=aternos.org`<br>ublock-filters: `\|\|htlb.casalemedia.com^$removeparam=r,domain=aternos.org`<br>ublock-filters: `\|\|clips-manifests-aka.warnermediacdn.com^$xhr,removeparam=caid,domain=nba.com` |
| `needs-engine:procedural` | 2,323 | ublock-filters: `youtube.com##.ytlr-horizontal-list-renderer__items > .yt-virtual-list__container > .yt-virtual-list__item--visible.yt-virtual-list__item--selected.yt-virtual-list__item:has-text(Ad)`<br>ublock-filters: `sport1.de##strong:has-text(/anzeige/i)`<br>ublock-filters: `economictimes.indiatimes.com##.active > ul > li:has-text(Ad:)` |
| `inert:redirect-rule` | 545 | ublock-filters: `*$script,domain=aranzulla.it,redirect-rule=noopjs`<br>ublock-filters: `\|\|indiatimes.com^$image,redirect-rule=1x1.gif`<br>ublock-filters: `*$image,redirect-rule=1x1.gif,domain=web.de` |
| `inert:to` | 306 | ublock-filters: `/^https:\/\/[-0-9a-z]{5,}\.(?:com\|org)\/\d{1,2}\/[0-9a-f]{32}$/$script,3p,match-case,to=com\|org`<br>ublock-filters: `/\/[0-9a-f]{32}\.js/$script,xhr,3p,to=com,from=bembed.net\|embedv.net\|listeamed.net\|moflix-stream.day\|moflix-stream.fans\|v6embed.xyz\|vid-guard.com`<br>ublock-filters: `/\.\d{1,2}\.[0-9a-f]{32}\.js$/$script,3p,match-case,to=js.txxx.tube` |
| `needs-engine:url-rewrite` | 269 | ublock-filters: `\|\|idnes.cz/_servix/media/video.aspx$script,uritransform=/reklama=1/reklama=0/`<br>ublock-filters: `\|\|meong.club/go/?aHR0c*$doc,urlskip=/\/go\/\?(aHR0c.+)/ -base64`<br>ublock-filters: `\|\|vw.mangaz.com/navi/$doc,uritransform=/navi(\/\d+(?:\/i:\d+)?)/virgo\/view\$1/` |
| `needs-engine:html-filtering` | 193 | ublock-filters: `wetteronline.*##^script:has-text(runCount)`<br>ublock-filters: `gamestorrents.*,gogoanimes.*,limetorrents.*,piratebayz.*##^script:has-text(AaDetector)`<br>ublock-filters: `animepahe.*,kwik.*##^script:has-text('shift')` |
| `needs-engine:dom-actions` | 127 | ublock-filters: `dvdgayonline.com###clickfakeplayer:remove-attr(href)`<br>ublock-filters: `vk.sportsbull.jp##.hidden-by-ima:remove-class(hidden-by-ima)`<br>ublock-filters: `flickr.com##.search-photos-unified-page-view .desktop-nav-ad:remove-class(desktop-nav-ad)` |
| `inert:csp` | 120 | ublock-filters: `\|\|rule34.top^$csp=sandbox allow-forms allow-same-origin allow-scripts allow-modals allow-orientation-lock allow-pointer-lock allow-presentation allow-top-navigation`<br>ublock-filters: `\|\|feet9.com^$csp=worker-src 'none';`<br>ublock-filters: `\|\|hotscope.tv^$csp=script-src 'self' 'unsafe-inline' 'unsafe-eval' data: https://disqus.com *.disqus.com *.google-analytics.com *.disquscdn.com` |
| `cancelled-by-generic-exception` | 67 | ublock-filters: `whathifi.com##.adunit`<br>ublock-filters: `timesnownews.com,timesnowhindi.com,timesnowmarathi.com,zoomtventertainment.com##.adunit`<br>ublock-filters: `gmx.*##.ad-content` |
| `generic-exception-applied` | 63 | ublock-filters: `#@#.reklama`<br>ublock-filters: `#@#[class^="div-gpt-ad"]`<br>ublock-filters: `#@#[id^="div-gpt-ad"]` |
| `needs-engine:response-headers` | 50 | ublock-filters: `/^https:\/\/[-0-9a-z]{4,7}.[a-z]{3,5}\/js\/responsive\.js$/$script,3p,match-case,header=x-server`<br>ublock-filters: `/^https:\/\/www\.[a-z]{8,14}\.com\/[a-z]{1,4}\.js$/$script,3p,match-case,header=x-powered-by:Express,from=~edu\|~gov,to=com\|~exploretock.com\|~photopea.com`<br>ublock-filters: `/^https:\/\/www\.[a-z]{8,16}\.com\/(?:[A-Za-z]+\/)*(?:[_0-9A-Za-z]{1,20}[-.])*[_0-9A-Za-z]{1,20}\.js$/$script,xhr,3p,match-case,to=com,header=popads-node` |
| `inert:method` | 49 | ublock-filters: `/^https:\/\/[-a-z]{8,}\.com\/[f-j][-0-9A-Z_a-z]{2,}\/[0-9A-Za-z][-\/0-9A-Z_a-z]{115,132}$/$script,xhr,3p,match-case,to=com,method=get,header=X-Request-ID:/^[0-9a-f]{32}$/`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.com\/$/$xhr,3p,to=com,method=head,header=access-control-expose-headers:/X-DirectionPartner-Id/`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.net\/$/$xhr,3p,to=net,method=head,header=access-control-expose-headers:/X-DirectionPartner-Id/` |
| `regex-unsupported` | 47 | ublock-filters: `/^https?:\/\/[a-z]{8,15}\.top\/(?!api\|available\|team)[a-z]{4,}\.json$/$xhr,3p,match-case`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.xyz\/(?!api\|available\|team)[a-z]{4,}\.json$/$xhr,3p,match-case`<br>ublock-filters: `/^https?:\/\/(?:[a-z]{2}\|[a-z]{5,7})?\.?[0-9a-z]{5,16}\.[a-z]{3,7}\/[a-z](?=[a-z]{0,25}[0-9A-Z])[0-9a-zA-Z]{3,26}\/\d{3,6}(?:[?&][_a-z0-9]+=[-0-9a-zA-Z]+)*$/$script,xhr,3p,match-case,redirect=noop.js` |
| `needs-engine:ip-address` | 36 | ublock-filters: `*$doc,ipaddress=199.59.243.227,to=~parked.domain\|animeseries.so\|audiobookbay.li\|hhdstreams.club\|janitor.ai\|kahoo.it\|pix4link.com\|sshagan.net`<br>ublock-filters: `/\/_static\/[a-z0-9]{12}\.js\?nonce=\d+$/$script,1p,match-case,ipaddress=/^1(72\.104\|39\.162)\.\d{3}\.\d{2,3}$/`<br>ublock-badware: `$doc,ipaddress=185.100.85.248` |
| `needs-engine:cname` | 29 | ublock-filters: `@@\|\|crackle.com^$cname`<br>ublock-filters: `@@\|\|player.pl^$cname`<br>ublock-unbreak: `@@\|\|player.fm^$cname` |
| `needs-engine:response-rewrite` | 21 | ublock-filters: `\|\|youtube.com/youtubei/v1/get_watch?$xhr,1p,replace=/"adPlacements"/"no_ads"/`<br>ublock-filters: `\|\|youtube.com/youtubei/v1/get_watch?$xhr,1p,replace=/"adSlots"/"no_ads"/`<br>ublock-filters: `/^https:\/\/[a-z]{5,}-[a-z]{5,}\.space\/[a-z0-9]{6,8}\.js$/$script,3p,to=space,replace=/^function a0_0x.+//` |
| `strict-party` | 16 | ublock-filters: `/\.de\/[a-z]{10,18}\.js$/$script,1p,strict1p,match-case,domain=capital.de\|essen-und-trinken.de\|geo.de\|eltern.de`<br>ublock-filters: `/assets/jquery/css.js^$script,1p,strict1p`<br>ublock-filters: `/^https:\/\/[a-z]{4,}\.(?:com\|to)\/z-[a-z0-9]{7,10}(\.js)?$/$script,1p,strict1p,match-case,domain=com\|to` |
| `regex-hostname` | 14 | ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.banner`<br>ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.banners`<br>ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.container > aside.sidebar:has(> .banner)` |
| `needs-engine:permissions-policy` | 4 | helium-unbreak: `*$permissions=join-ad-interest-group=(),from=~localhost\|~127.0.0.1\|~[::1]\|~0.0.0.0\|~[::]\|~local,badfilter`<br>helium-unbreak: `*$permissions=run-ad-auction=(),from=~localhost\|~127.0.0.1\|~[::1]\|~0.0.0.0\|~[::]\|~local,badfilter`<br>helium-unbreak: `*$permissions=browsing-topics=(),from=~localhost\|~127.0.0.1\|~[::1]\|~0.0.0.0\|~[::]\|~local,badfilter` |
| `unsupported-option` | 4 | ublock-filters: `/^https:\/\/[a-z]{8}\.com\/assets\/js\/[a-z]{4,5}\.js$/$script,3p,match-case,top=avtub.net\|funcrot.net\|vidara.*\|vidara.so\|vidara.to`<br>adguard-generic: `@@\|\|adguardpartner.com^$generichide,genericblock`<br>adguard-spyware-url: `\|\|ad.doubleclick.net/ddm/clk/$removeparam=/^\\$ja=/` |
| `regex-domain` | 2 | ublock-filters: `\|\|blogger.googleusercontent.com/img/$domain=/^main\.uxsyplayer[a-z0-9-]+\.click$/` |
| `engine-rejects:match-case-without-full-regex` | 2 | adguard-generic: `.com/aS/feedclick?s=$all,match-case`<br>adguard-generic: `\|\|nuvid.com/NB*.js$match-case` |
| `needs-engine:specifichide` | 1 | ublock-filters: `@@\|\|magyarhang.org^$shide` |
| `needs-engine:request-headers` | 1 | ublock-filters: `\|\|workers.dev/index.js$script,3p,requestheader=Cookie:*doubleclick.net*` |
| `needs-engine:csp-injection` | 1 | ublock-unbreak: `*$1p,inline-script,script,domain=click.allkeyshop.com` |
| `generic-style` | 1 | adguard-generic: `##:matches-path(/rinku/land/) form[id][method="post"][style^="display:"]:has(> center > div[style^="margin: 10px 0 10px 0;"]):style(display: block !important;)` |
| `engine-rejects:negated-document` | 1 | easyprivacy: `/webtracking/*$~document,~subdocument,domain=~wwwapps.ups.com` |

## Translated

Upstream filters kept after each translation (one filter can need several).

| Translation | Filters |
|---|---:|
| `hosts-file` | 3,563 |
| `entity-domain-expanded` | 401 |
| `denyallow-to-exceptions` | 266 |
| `remove-to-hide` | 255 |
| `hostname-anchor-completed` | 18 |
| `elemhide-to-generichide` | 16 |
| `reason-stripped` | 16 |
| `regex-lowercase-safe` | 12 |
| `noop-option` | 7 |
| `strict3p-to-3p` | 6 |
| `extended-marker` | 5 |
| `plain-hostname` | 4 |
| `exception-negations-removed` | 3 |
| `to-to-hostname-filters` | 3 |
| `to-to-exceptions` | 2 |
| `regex-dollar-rewritten` | 2 |
| `wildcard-host` | 1 |
| `abp-has-to-has` | 1 |

## Scriptlets that were dropped

What a scriptlet engine would need first, by number of filters using each scriptlet.

| Scriptlet | Filters |
|---|---:|
| `set-cookie` | 2,975 |
| `set` | 1,674 |
| `acs` | 1,571 |
| `aopr` | 1,530 |
| `aeld` | 1,041 |
| `trusted-set-cookie` | 977 |
| `nostif` | 962 |
| `set-constant` | 957 |
| `trusted-click-element` | 925 |
| `rmnt` | 918 |
| `nowoif` | 859 |
| `set-local-storage-item` | 829 |
| `abort-current-script` | 607 |
| `aopw` | 483 |
| `no-fetch-if` | 437 |
| `no-window-open-if` | 428 |
| `prevent-fetch` | 410 |
| `no-setTimeout-if` | 369 |
| `no-xhr-if` | 334 |
| `addEventListener-defuser` | 306 |
| `abort-on-property-read` | 287 |
| `ra` | 284 |
| `rpnt` | 267 |
| `json-prune` | 259 |
| `aost` | 219 |

Reasons are explained in docs/gap-analysis.md. Every dropped line is in `dist/<preset>/dropped/<id>.tsv` after a build.
