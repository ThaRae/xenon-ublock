# uBlock Origin defaults: conversion report

Built 2026-10-26 18:47 UTC for adblock 0.13.3, as built into Ladybird's LibWeb/ContentBlocker.

249,575 of 265,860 upstream filters kept (93.9%), written as 251,055 filters.
Counts are per upstream filter line, after uBO's preprocessor. One upstream line can become several filters (a hosts-file line with several names, or a `$denyallow` filter and its exceptions).

## Lists

| List | Upstream filters | Kept | Translated | Dropped | Output filters | Size |
|---|---:|---:|---:|---:|---:|---:|
| uBlock filters – Ads (`ublock-filters`) | 23,275 | 12,238 | 498 | 11,037 | 13,732 | 1,303 KiB |
| uBlock filters – Badware risks (`ublock-badware`) | 4,983 | 4,661 | 11 | 322 | 4,653 | 130 KiB |
| uBlock filters – Privacy (`ublock-privacy`) | 1,813 | 980 | 11 | 833 | 983 | 35 KiB |
| uBlock filters – Unbreak (`ublock-unbreak`) | 2,551 | 2,025 | 22 | 526 | 2,025 | 138 KiB |
| uBlock filters – Quick fixes (`ublock-quick-fixes`) | 461 | 244 | 15 | 217 | 247 | 25 KiB |
| EasyList (`easylist`) | 74,639 | 71,323 | 6 | 3,316 | 71,313 | 1,828 KiB |
| EasyPrivacy (`easyprivacy`) | 56,384 | 56,350 | 10 | 34 | 56,348 | 1,444 KiB |
| Online Malicious URL Blocklist (`urlhaus-1`) | 98,191 | 98,191 | 0 | 0 | 98,191 | 11,279 KiB |
| Peter Lowe’s Ad and tracking server list (`plowe-0`) | 3,563 | 3,563 | 3,563 | 0 | 3,563 | 68 KiB |

## Dropped, by reason

| Reason | Filters | Examples |
|---|---:|---|
| `needs-engine:scriptlets` | 10,352 | ublock-filters: `tv.youtube.com##+js(trusted-replace-xhr-response, '"adPlacements"', '"no_ads"', /playlist\?list=\|\/player(?:\?.+)?$\|watch\?[tv]=/)`<br>ublock-filters: `www.youtube.com##+js(trusted-replace-xhr-response, /"adPlacements.*?([A-Z]"\}\|"\}{2\,4})\}\]\,/, , /playlist\?list=\|\/player(?:\?.+)?$\|watch\?[tv]=/)`<br>ublock-filters: `www.youtube.com##+js(trusted-replace-xhr-response, /"adPlacements.*?("adSlots"\|"adBreakHeartbeatParams")/gms, $1, /\/player(?:\?.+)?$/)` |
| `needs-engine:popup` | 3,149 | ublock-filters: `\|\|bit.ly^$popup,domain=eurogamer.net`<br>ublock-filters: `*$popup,domain=clik.pw,3p`<br>ublock-filters: `*$popunder,domain=realgfporn.com` |
| `needs-engine:procedural` | 789 | ublock-filters: `youtube.com##.ytlr-horizontal-list-renderer__items > .yt-virtual-list__container > .yt-virtual-list__item--visible.yt-virtual-list__item--selected.yt-virtual-list__item:has-text(Ad)`<br>ublock-filters: `sport1.de##strong:has-text(/anzeige/i)`<br>ublock-filters: `economictimes.indiatimes.com##.active > ul > li:has-text(Ad:)` |
| `inert:redirect-rule` | 476 | ublock-filters: `*$script,domain=aranzulla.it,redirect-rule=noopjs`<br>ublock-filters: `\|\|indiatimes.com^$image,redirect-rule=1x1.gif`<br>ublock-filters: `*$image,redirect-rule=1x1.gif,domain=web.de` |
| `inert:to` | 306 | ublock-filters: `/^https:\/\/[-0-9a-z]{5,}\.(?:com\|org)\/\d{1,2}\/[0-9a-f]{32}$/$script,3p,match-case,to=com\|org`<br>ublock-filters: `/\/[0-9a-f]{32}\.js/$script,xhr,3p,to=com,from=bembed.net\|embedv.net\|listeamed.net\|moflix-stream.day\|moflix-stream.fans\|v6embed.xyz\|vid-guard.com`<br>ublock-filters: `/\.\d{1,2}\.[0-9a-f]{32}\.js$/$script,3p,match-case,to=js.txxx.tube` |
| `inert:removeparam` | 269 | ublock-filters: `\|\|fastlane.rubiconproject.com^$removeparam,domain=aternos.org`<br>ublock-filters: `\|\|htlb.casalemedia.com^$removeparam=r,domain=aternos.org`<br>ublock-filters: `\|\|clips-manifests-aka.warnermediacdn.com^$xhr,removeparam=caid,domain=nba.com` |
| `needs-engine:url-rewrite` | 261 | ublock-filters: `\|\|idnes.cz/_servix/media/video.aspx$script,uritransform=/reklama=1/reklama=0/`<br>ublock-filters: `\|\|meong.club/go/?aHR0c*$doc,urlskip=/\/go\/\?(aHR0c.+)/ -base64`<br>ublock-filters: `\|\|vw.mangaz.com/navi/$doc,uritransform=/navi(\/\d+(?:\/i:\d+)?)/virgo\/view\$1/` |
| `needs-engine:html-filtering` | 161 | ublock-filters: `wetteronline.*##^script:has-text(runCount)`<br>ublock-filters: `gamestorrents.*,gogoanimes.*,limetorrents.*,piratebayz.*##^script:has-text(AaDetector)`<br>ublock-filters: `animepahe.*,kwik.*##^script:has-text('shift')` |
| `needs-engine:dom-actions` | 99 | ublock-filters: `dvdgayonline.com###clickfakeplayer:remove-attr(href)`<br>ublock-filters: `vk.sportsbull.jp##.hidden-by-ima:remove-class(hidden-by-ima)`<br>ublock-filters: `flickr.com##.search-photos-unified-page-view .desktop-nav-ad:remove-class(desktop-nav-ad)` |
| `inert:csp` | 89 | ublock-filters: `\|\|rule34.top^$csp=sandbox allow-forms allow-same-origin allow-scripts allow-modals allow-orientation-lock allow-pointer-lock allow-presentation allow-top-navigation`<br>ublock-filters: `\|\|feet9.com^$csp=worker-src 'none';`<br>ublock-filters: `\|\|hotscope.tv^$csp=script-src 'self' 'unsafe-inline' 'unsafe-eval' data: https://disqus.com *.disqus.com *.google-analytics.com *.disquscdn.com` |
| `generic-exception-applied` | 57 | ublock-filters: `#@#.reklama`<br>ublock-filters: `#@#[class^="div-gpt-ad"]`<br>ublock-filters: `#@#[id^="div-gpt-ad"]` |
| `cancelled-by-generic-exception` | 54 | ublock-filters: `whathifi.com##.adunit`<br>ublock-filters: `timesnownews.com,timesnowhindi.com,timesnowmarathi.com,zoomtventertainment.com##.adunit`<br>ublock-filters: `gmx.*##.ad-content` |
| `inert:method` | 48 | ublock-filters: `/^https:\/\/[-a-z]{8,}\.com\/[f-j][-0-9A-Z_a-z]{2,}\/[0-9A-Za-z][-\/0-9A-Z_a-z]{115,132}$/$script,xhr,3p,match-case,to=com,method=get,header=X-Request-ID:/^[0-9a-f]{32}$/`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.com\/$/$xhr,3p,to=com,method=head,header=access-control-expose-headers:/X-DirectionPartner-Id/`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.net\/$/$xhr,3p,to=net,method=head,header=access-control-expose-headers:/X-DirectionPartner-Id/` |
| `needs-engine:ip-address` | 36 | ublock-filters: `*$doc,ipaddress=199.59.243.227,to=~parked.domain\|animeseries.so\|audiobookbay.li\|hhdstreams.club\|janitor.ai\|kahoo.it\|pix4link.com\|sshagan.net`<br>ublock-filters: `/\/_static\/[a-z0-9]{12}\.js\?nonce=\d+$/$script,1p,match-case,ipaddress=/^1(72\.104\|39\.162)\.\d{3}\.\d{2,3}$/`<br>ublock-badware: `$doc,ipaddress=185.100.85.248` |
| `needs-engine:response-headers` | 35 | ublock-filters: `/^https:\/\/[-0-9a-z]{4,7}.[a-z]{3,5}\/js\/responsive\.js$/$script,3p,match-case,header=x-server`<br>ublock-filters: `/^https:\/\/www\.[a-z]{8,14}\.com\/[a-z]{1,4}\.js$/$script,3p,match-case,header=x-powered-by:Express,from=~edu\|~gov,to=com\|~exploretock.com\|~photopea.com`<br>ublock-filters: `/^https:\/\/www\.[a-z]{8,16}\.com\/(?:[A-Za-z]+\/)*(?:[_0-9A-Za-z]{1,20}[-.])*[_0-9A-Za-z]{1,20}\.js$/$script,xhr,3p,match-case,to=com,header=popads-node` |
| `regex-unsupported` | 29 | ublock-filters: `/^https?:\/\/[a-z]{8,15}\.top\/(?!api\|available\|team)[a-z]{4,}\.json$/$xhr,3p,match-case`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.xyz\/(?!api\|available\|team)[a-z]{4,}\.json$/$xhr,3p,match-case`<br>ublock-filters: `/^https?:\/\/(?:[a-z]{2}\|[a-z]{5,7})?\.?[0-9a-z]{5,16}\.[a-z]{3,7}\/[a-z](?=[a-z]{0,25}[0-9A-Z])[0-9a-zA-Z]{3,26}\/\d{3,6}(?:[?&][_a-z0-9]+=[-0-9a-zA-Z]+)*$/$script,xhr,3p,match-case,redirect=noop.js` |
| `needs-engine:cname` | 29 | ublock-filters: `@@\|\|crackle.com^$cname`<br>ublock-filters: `@@\|\|player.pl^$cname`<br>ublock-unbreak: `@@\|\|player.fm^$cname` |
| `needs-engine:response-rewrite` | 18 | ublock-filters: `\|\|youtube.com/youtubei/v1/get_watch?$xhr,1p,replace=/"adPlacements"/"no_ads"/`<br>ublock-filters: `\|\|youtube.com/youtubei/v1/get_watch?$xhr,1p,replace=/"adSlots"/"no_ads"/`<br>ublock-filters: `/^https:\/\/[a-z]{5,}-[a-z]{5,}\.space\/[a-z0-9]{6,8}\.js$/$script,3p,to=space,replace=/^function a0_0x.+//` |
| `strict-party` | 15 | ublock-filters: `/\.de\/[a-z]{10,18}\.js$/$script,1p,strict1p,match-case,domain=capital.de\|essen-und-trinken.de\|geo.de\|eltern.de`<br>ublock-filters: `/assets/jquery/css.js^$script,1p,strict1p`<br>ublock-filters: `/^https:\/\/[a-z]{4,}\.(?:com\|to)\/z-[a-z0-9]{7,10}(\.js)?$/$script,1p,strict1p,match-case,domain=com\|to` |
| `regex-hostname` | 6 | ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.banner`<br>ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.banners`<br>ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.container > aside.sidebar:has(> .banner)` |
| `needs-engine:specifichide` | 1 | ublock-filters: `@@\|\|magyarhang.org^$shide` |
| `regex-domain` | 1 | ublock-filters: `\|\|blogger.googleusercontent.com/img/$domain=/^main\.uxsyplayer[a-z0-9-]+\.click$/` |
| `unsupported-option` | 1 | ublock-filters: `/^https:\/\/[a-z]{8}\.com\/assets\/js\/[a-z]{4,5}\.js$/$script,3p,match-case,top=avtub.net\|funcrot.net\|vidara.*\|vidara.so\|vidara.to` |
| `needs-engine:request-headers` | 1 | ublock-filters: `\|\|workers.dev/index.js$script,3p,requestheader=Cookie:*doubleclick.net*` |
| `needs-engine:csp-injection` | 1 | ublock-unbreak: `*$1p,inline-script,script,domain=click.allkeyshop.com` |
| `needs-engine:permissions-policy` | 1 | ublock-unbreak: `@@\|\|cjisonline.com^$permissions=browsing-topics=()` |
| `engine-rejects:negated-document` | 1 | easyprivacy: `/webtracking/*$~document,~subdocument,domain=~wwwapps.ups.com` |

## Translated

Upstream filters kept after each translation (one filter can need several).

| Translation | Filters |
|---|---:|
| `hosts-file` | 3,563 |
| `entity-domain-expanded` | 282 |
| `denyallow-to-exceptions` | 246 |
| `remove-to-hide` | 72 |
| `reason-stripped` | 16 |
| `hostname-anchor-completed` | 11 |
| `strict3p-to-3p` | 6 |
| `extended-marker` | 4 |
| `exception-negations-removed` | 3 |
| `to-to-hostname-filters` | 3 |
| `elemhide-to-generichide` | 3 |
| `to-to-exceptions` | 2 |
| `regex-lowercase-safe` | 1 |
| `wildcard-host` | 1 |
| `plain-hostname` | 1 |
| `abp-has-to-has` | 1 |

## Scriptlets that were dropped

What a scriptlet engine would need first, by number of filters using each scriptlet.

| Scriptlet | Filters |
|---|---:|
| `set` | 1,385 |
| `aopr` | 1,259 |
| `acs` | 1,164 |
| `nowoif` | 857 |
| `nostif` | 821 |
| `rmnt` | 803 |
| `aeld` | 672 |
| `no-fetch-if` | 418 |
| `aopw` | 298 |
| `rpnt` | 251 |
| `no-xhr-if` | 244 |
| `aost` | 202 |
| `nano-sib` | 199 |
| `noeval-if` | 148 |
| `nosiif` | 146 |
| `nano-stb` | 130 |
| `json-prune` | 122 |
| `ra` | 110 |
| `trusted-replace-argument` | 83 |
| `set-local-storage-item` | 81 |
| `href-sanitizer` | 75 |
| `nowebrtc` | 60 |
| `remove-cookie` | 60 |
| `set-cookie` | 51 |
| `json-prune-fetch-response` | 48 |

Reasons are explained in docs/gap-analysis.md. Every dropped line is in `dist*/<preset>/dropped/<id>.tsv` after a build.
