# uBlock Origin defaults: conversion report

Built 2026-10-26 18:47 UTC for Ladybird's content blocker with xenon-ublock's engine/patches (adblock 0.13.3 with css-validation, uBlock Origin's resources).

264,543 of 265,860 upstream filters kept (99.5%), written as 266,163 filters.
Counts are per upstream filter line, after uBO's preprocessor. One upstream line can become several filters (a hosts-file line with several names, or a `$denyallow` filter and its exceptions).

## Lists

| List | Upstream filters | Kept | Translated | Dropped | Output filters | Size |
|---|---:|---:|---:|---:|---:|---:|
| uBlock filters – Ads (`ublock-filters`) | 23,275 | 22,676 | 470 | 599 | 24,167 | 2,285 KiB |
| uBlock filters – Badware risks (`ublock-badware`) | 4,983 | 4,703 | 11 | 280 | 4,695 | 135 KiB |
| uBlock filters – Privacy (`ublock-privacy`) | 1,813 | 1,532 | 19 | 281 | 1,678 | 106 KiB |
| uBlock filters – Unbreak (`ublock-unbreak`) | 2,551 | 2,481 | 21 | 70 | 2,481 | 168 KiB |
| uBlock filters – Quick fixes (`ublock-quick-fixes`) | 461 | 438 | 15 | 23 | 441 | 72 KiB |
| EasyList (`easylist`) | 74,639 | 74,579 | 289 | 60 | 74,569 | 1,929 KiB |
| EasyPrivacy (`easyprivacy`) | 56,384 | 56,380 | 10 | 4 | 56,378 | 1,452 KiB |
| Online Malicious URL Blocklist (`urlhaus-1`) | 98,191 | 98,191 | 0 | 0 | 98,191 | 11,279 KiB |
| Peter Lowe’s Ad and tracking server list (`plowe-0`) | 3,563 | 3,563 | 3,563 | 0 | 3,563 | 68 KiB |

## Dropped, by reason

| Reason | Filters | Examples |
|---|---:|---|
| `inert:to` | 336 | ublock-filters: `*$script,redirect-rule=noopjs,from=dutchycorp.*,to=~sentry-cdn.com`<br>ublock-filters: `/^https:\/\/[-0-9a-z]{5,}\.(?:com\|org)\/\d{1,2}\/[0-9a-f]{32}$/$script,3p,match-case,to=com\|org`<br>ublock-filters: `/\/[0-9a-f]{32}\.js/$script,xhr,3p,to=com,from=bembed.net\|embedv.net\|listeamed.net\|moflix-stream.day\|moflix-stream.fans\|v6embed.xyz\|vid-guard.com` |
| `needs-engine:url-rewrite` | 261 | ublock-filters: `\|\|idnes.cz/_servix/media/video.aspx$script,uritransform=/reklama=1/reklama=0/`<br>ublock-filters: `\|\|meong.club/go/?aHR0c*$doc,urlskip=/\/go\/\?(aHR0c.+)/ -base64`<br>ublock-filters: `\|\|vw.mangaz.com/navi/$doc,uritransform=/navi(\/\d+(?:\/i:\d+)?)/virgo\/view\$1/` |
| `needs-engine:html-filtering` | 161 | ublock-filters: `wetteronline.*##^script:has-text(runCount)`<br>ublock-filters: `gamestorrents.*,gogoanimes.*,limetorrents.*,piratebayz.*##^script:has-text(AaDetector)`<br>ublock-filters: `animepahe.*,kwik.*##^script:has-text('shift')` |
| `inert:csp` | 89 | ublock-filters: `\|\|rule34.top^$csp=sandbox allow-forms allow-same-origin allow-scripts allow-modals allow-orientation-lock allow-pointer-lock allow-presentation allow-top-navigation`<br>ublock-filters: `\|\|feet9.com^$csp=worker-src 'none';`<br>ublock-filters: `\|\|hotscope.tv^$csp=script-src 'self' 'unsafe-inline' 'unsafe-eval' data: https://disqus.com *.disqus.com *.google-analytics.com *.disquscdn.com` |
| `needs-engine:procedural-operator` | 81 | ublock-filters: `ufacw.com###wpsafe-generate, #wpsafe-link:others()`<br>ublock-filters: `ottlatest.com##div#wpsafe-link:others()`<br>ublock-filters: `informaxonline.com###wpsafe-generate, #wpsafe-link:others()` |
| `generic-exception-applied` | 57 | ublock-filters: `#@#.reklama`<br>ublock-filters: `#@#[class^="div-gpt-ad"]`<br>ublock-filters: `#@#[id^="div-gpt-ad"]` |
| `cancelled-by-generic-exception` | 53 | ublock-filters: `whathifi.com##.adunit`<br>ublock-filters: `timesnownews.com,timesnowhindi.com,timesnowmarathi.com,zoomtventertainment.com##.adunit`<br>ublock-filters: `gmx.*##.ad-content` |
| `needs-engine:response-headers` | 41 | ublock-filters: `/^https:\/\/[-a-z]{8,}\.com\/[f-j][-0-9A-Z_a-z]{2,}\/[0-9A-Za-z][-\/0-9A-Z_a-z]{115,132}$/$script,xhr,3p,match-case,to=com,method=get,header=X-Request-ID:/^[0-9a-f]{32}$/`<br>ublock-filters: `/^https:\/\/[-0-9a-z]{4,7}.[a-z]{3,5}\/js\/responsive\.js$/$script,3p,match-case,header=x-server`<br>ublock-filters: `/^https:\/\/www\.[a-z]{8,14}\.com\/[a-z]{1,4}\.js$/$script,3p,match-case,header=x-powered-by:Express,from=~edu\|~gov,to=com\|~exploretock.com\|~photopea.com` |
| `engine-rejects:empty-redirection` | 41 | ublock-filters: `@@\|\|pagead2.googlesyndication.com/pagead/js/adsbygoogle.js$xhr,redirect-rule,domain=carousell.*`<br>ublock-filters: `@@\|\|g.doubleclick.net/tag/js/gpt.js$script,redirect-rule,domain=pomponik.pl`<br>ublock-filters: `@@\|\|googletagmanager.com/gtm.js$script,redirect-rule,domain=soranews24.com` |
| `needs-engine:ip-address` | 37 | ublock-filters: `*$doc,ipaddress=199.59.243.227,to=~parked.domain\|animeseries.so\|audiobookbay.li\|hhdstreams.club\|janitor.ai\|kahoo.it\|pix4link.com\|sshagan.net`<br>ublock-filters: `/\/_static\/[a-z0-9]{12}\.js\?nonce=\d+$/$script,1p,match-case,ipaddress=/^1(72\.104\|39\.162)\.\d{3}\.\d{2,3}$/`<br>ublock-badware: `$doc,ipaddress=185.100.85.248` |
| `regex-unsupported` | 30 | ublock-filters: `/^https?:\/\/[a-z]{8,15}\.top\/(?!api\|available\|team)[a-z]{4,}\.json$/$xhr,3p,match-case`<br>ublock-filters: `/^https?:\/\/[a-z]{8,15}\.xyz\/(?!api\|available\|team)[a-z]{4,}\.json$/$xhr,3p,match-case`<br>ublock-filters: `/^https?:\/\/(?:[a-z]{2}\|[a-z]{5,7})?\.?[0-9a-z]{5,16}\.[a-z]{3,7}\/[a-z](?=[a-z]{0,25}[0-9A-Z])[0-9a-zA-Z]{3,26}\/\d{3,6}(?:[?&][_a-z0-9]+=[-0-9a-zA-Z]+)*$/$script,xhr,3p,match-case,redirect=noop.js` |
| `needs-engine:popup` | 25 | ublock-filters: `*$popunder,domain=realgfporn.com`<br>ublock-filters: `*$popunder,3p,domain=bs.to\|burningseries.*`<br>ublock-filters: `*$popunder,domain=hotpornfile.org` |
| `engine-rejects:scriptlet-args-could-not-be-parsed` | 19 | ublock-filters: `bild.de##+js(rpnt, script, "adBlockWallEnabled":true, "adBlockWallEnabled":false)`<br>ublock-filters: `short.pe##+js(nostif, '0x)`<br>ublock-filters: `xmovies08.org##+js(aeld, , '0x)` |
| `needs-engine:response-rewrite` | 18 | ublock-filters: `\|\|youtube.com/youtubei/v1/get_watch?$xhr,1p,replace=/"adPlacements"/"no_ads"/`<br>ublock-filters: `\|\|youtube.com/youtubei/v1/get_watch?$xhr,1p,replace=/"adSlots"/"no_ads"/`<br>ublock-filters: `/^https:\/\/[a-z]{5,}-[a-z]{5,}\.space\/[a-z0-9]{6,8}\.js$/$script,3p,to=space,replace=/^function a0_0x.+//` |
| `strict-party` | 15 | ublock-filters: `/\.de\/[a-z]{10,18}\.js$/$script,1p,strict1p,match-case,domain=capital.de\|essen-und-trinken.de\|geo.de\|eltern.de`<br>ublock-filters: `/assets/jquery/css.js^$script,1p,strict1p`<br>ublock-filters: `/^https:\/\/[a-z]{4,}\.(?:com\|to)\/z-[a-z0-9]{7,10}(\.js)?$/$script,1p,strict1p,match-case,domain=com\|to` |
| `engine-rejects:removeparam-regex-unsupported` | 14 | ublock-filters: `\|\|content.uplynk.com/api/*&ad=$xhr,removeparam=/^ad/,domain=abc7ny.com\|abc7.com\|abc7chicago.com\|6abc.com\|abc7news.com\|abc13.com\|abc11.com\|abc30.com\|abcnews.go.com`<br>ublock-filters: `://foxvideo-sports$xhr,3p,removeparam=ad.prof,domain=foxsports.com`<br>ublock-filters: `\|\|g.doubleclick.net/gampad/ads?$xhr,removeparam=/^(cookie\|ga_\|u_)/,domain=soranews24.com` |
| `engine-rejects:empty-removeparam` | 11 | ublock-filters: `\|\|fastlane.rubiconproject.com^$removeparam,domain=aternos.org`<br>ublock-filters: `\|\|sotlpy6yh.mxcontent.net/d/*/*?$removeparam`<br>ublock-privacy: `\|\|adthrive.com^$removeparam,from=~mediaite.com\|~a-z-animals.com` |
| `regex-hostname` | 6 | ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.banner`<br>ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.banners`<br>ublock-filters: `/^www\.selcuksportshd[a-z0-9-]+\.xyz$/##.container > aside.sidebar:has(> .banner)` |
| `engine-rejects:unsupported-syntax` | 6 | ublock-filters: `anisearch.*###screenshots span[style="width:222px"] > a[href]:remove-class(/ad/i)`<br>ublock-filters: `bombuj.*###players a[href][target="_blank"]:remove-attr(/href\|target/)`<br>ublock-filters: `plasticsnews.com##[class*="has-interstitial-ads"]:remove-class(/^has-interstitial-ads/)` |
| `unsupported-option` | 3 | ublock-filters: `/\/[0-9a-z]{2}\/[0-9a-f]{32}\.js/$script,xhr,3p,match-case,method=get,to=com,top=pro\|to\|top\|tv\|win\|~gov.to\|~gov.tv\|~twitch.tv`<br>ublock-filters: `/\/[0-9a-z]{2}\/[0-9a-f]{32}\.js/$script,xhr,3p,match-case,method=get,to=com,top=anihq.org\|bestbondagevideos.com\|filmifen.com\|hogtiehub.com\|playarcady.com\|supjav.com\|voe.sx`<br>ublock-filters: `/^https:\/\/[a-z]{8}\.com\/assets\/js\/[a-z]{4,5}\.js$/$script,3p,match-case,top=avtub.net\|funcrot.net\|vidara.*\|vidara.so\|vidara.to` |
| `engine-rejects:procedural-filters-can-only-accept-a-single-CSS-selector` | 2 | ublock-filters: `watchfreexxx.net##.happy-player-beside, .happy-section, .widget_execphp:has-text(/Advertisement\|ExoLoader/)`<br>ublock-filters: `pandamovie.*,pandamovies.me,pornkino.cc,speedporn.*,xxxscenes.net##.happy-player-beside, .happy-section, .widget_execphp:has-text(/Advertisement\|ExoLoader/)` |
| `engine-rejects:unrecognised-option` | 2 | ublock-filters: `\|\|link.theplatform.com/s/*/media/*=m3u&*_webdesktop_vod*$xhr,domain=foxsports.com,removeparam=/^((?!formats\|profile).)*$/`<br>ublock-filters: `\|\|link.theplatform.com/s/*/media*=rotten_tomatoes_video$xhr,removeparam=/^((?!SMIL\|formats).)*$/` |
| `engine-rejects:removeparam-with-exception` | 2 | ublock-filters: `@@\|\|medium.ngtv.io/v2/media/live*$removeparam=ssaiProfile,domain=adultswim.com`<br>ublock-unbreak: `@@\|\|che168.com^$xhr,removeparam=s_cid` |
| `needs-engine:specifichide` | 1 | ublock-filters: `@@\|\|magyarhang.org^$shide` |
| `regex-domain` | 1 | ublock-filters: `\|\|blogger.googleusercontent.com/img/$domain=/^main\.uxsyplayer[a-z0-9-]+\.click$/` |
| `needs-engine:request-headers` | 1 | ublock-filters: `\|\|workers.dev/index.js$script,3p,requestheader=Cookie:*doubleclick.net*` |
| `needs-engine:scriptlets` | 1 | ublock-filters: `chzzk.naver.com#%#//scriptlet('trusted-set-local-storage-item', 'homeSkinCollapsedUntil', '9999999999999')` |
| `needs-engine:csp-injection` | 1 | ublock-unbreak: `*$1p,inline-script,script,domain=click.allkeyshop.com` |
| `needs-engine:permissions-policy` | 1 | ublock-unbreak: `@@\|\|cjisonline.com^$permissions=browsing-topics=()` |
| `engine-rejects:negated-document` | 1 | easyprivacy: `/webtracking/*$~document,~subdocument,domain=~wwwapps.ups.com` |

## Translated

Upstream filters kept after each translation (one filter can need several).

| Translation | Filters |
|---|---:|
| `hosts-file` | 3,563 |
| `entity-domain-expanded` | 313 |
| `extended-marker` | 296 |
| `denyallow-to-exceptions` | 246 |
| `reason-stripped` | 16 |
| `to-to-hostname-filters` | 11 |
| `hostname-anchor-completed` | 11 |
| `strict3p-to-3p` | 6 |
| `strict1p-to-1p` | 6 |
| `exception-negations-removed` | 3 |
| `elemhide-to-generichide` | 3 |
| `to-to-exceptions` | 2 |
| `abp-has-to-has` | 2 |
| `regex-lowercase-safe` | 1 |
| `wildcard-host` | 1 |
| `plain-hostname` | 1 |
| `abp-contains-to-has-text` | 1 |

## Scriptlets that were dropped

What a scriptlet engine would need first, by number of filters using each scriptlet.

| Scriptlet | Filters |
|---|---:|
| `acs` | 4 |
| `rpnt` | 3 |
| `nostif` | 3 |
| `aeld` | 2 |
| `trusted-replace-xhr-response` | 2 |
| `trusted-rpfr` | 2 |
| `trusted-rpnt` | 1 |
| `rmnt` | 1 |
| `trusted-set-local-storage-item` | 1 |

Reasons are explained in docs/gap-analysis.md. Every dropped line is in `dist*/<preset>/dropped/<id>.tsv` after a build.
