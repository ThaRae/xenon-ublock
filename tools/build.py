#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds Ladybird content blocker lists from uBlock Origin's default filter lists.

For each preset in config/lists.json, this reads the preset's uBO assets.json, takes the filter lists it enables by
default, and fetches them. It then evaluates uBO's preprocessor (!#if, !#include, line continuations), translates the
uBO syntax that Ladybird's engine reads differently, drops what Ladybird cannot apply, and has the probe (probe/,
which parses with the engine's own adblock version) confirm every remaining line. Output, per preset:

  dist/<preset>/lists/<id>.txt     one converted list per upstream list
  dist/<preset>/all.txt            every list in the preset, concatenated (one file to load)
  dist/<preset>/dropped/<id>.tsv   each dropped line with the reason
  dist/<preset>/report.md          what was translated and dropped, per list and per reason
  dist/manifest.json               what was built, from where, and under which license

Usage: tools/build.py [--preset NAME]... [--lang CODE]... [--offline] [--refresh] [--out DIR]
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import itertools
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = "adblock 0.13.3, as built into Ladybird's LibWeb/ContentBlocker"
USER_AGENT = "xenon-ublock/0.1 (filter list converter for Ladybird)"

# Limits from ladybird/Libraries/LibWebView/Application.cpp.
MAXIMUM_LIST_SIZE = 64 * 1024 * 1024
MAXIMUM_COMBINED_LIST_SIZE = 256 * 1024 * 1024

# Overrides that apply to every preset, keyed by uBO asset id.
URL_OVERRIDES = {
    # The Vivaldi/Brave variant of the URLhaus list is written for adblock-rust, the engine Ladybird uses. Helium's
    # fork picks the AdGuard variant, which is 10x the size and adds nothing adblock-rust can use.
    "urlhaus-1": "https://malware-filter.gitlab.io/urlhaus-filter/urlhaus-filter-vivaldi-online.txt",
}


# --- Fetching -----------------------------------------------------------------------------------------------------


class FetchError(Exception):
    pass


class Fetcher:
    def __init__(self, cache_dir: Path, offline: bool, max_age_seconds: float):
        self.cache_dir = cache_dir
        self.offline = offline
        self.max_age_seconds = max_age_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self, url: str):
        key = hashlib.sha256(url.encode()).hexdigest()[:32]
        return self.cache_dir / f"{key}.body", self.cache_dir / f"{key}.json"

    def get(self, url: str) -> tuple[bytes, dict]:
        body_path, meta_path = self._paths(url)
        cached = body_path.exists() and meta_path.exists()
        if cached:
            meta = json.loads(meta_path.read_text())
            fresh = time.time() - meta["fetched_at"] < self.max_age_seconds
            if self.offline or fresh:
                return body_path.read_bytes(), meta
        if self.offline:
            raise FetchError(f"{url}: not in the cache and --offline was given")

        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read(MAXIMUM_LIST_SIZE + 1)
                    final_url = response.geturl()
                if len(body) > MAXIMUM_LIST_SIZE:
                    raise FetchError(f"{url}: larger than {MAXIMUM_LIST_SIZE} bytes")
                meta = {"url": url, "final_url": final_url, "fetched_at": time.time()}
                body_path.write_bytes(body)
                meta_path.write_text(json.dumps(meta))
                return body, meta
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                last_error = error
                time.sleep(1 + attempt * 2)
        if cached:
            print(f"warning: {url}: {last_error}; using the cached copy", file=sys.stderr)
            return body_path.read_bytes(), json.loads(meta_path.read_text())
        raise FetchError(f"{url}: {last_error}")


# --- uBO preprocessor ---------------------------------------------------------------------------------------------


def evaluate_condition(expression: str, environment: dict) -> bool:
    """Evaluates an !#if expression: tokens joined with !, &&, || and parentheses. Unknown tokens are false."""
    tokens = re.findall(r"\(|\)|&&|\|\||!|[^\s()!&|]+", expression)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else None

    def take():
        nonlocal position
        position += 1
        return tokens[position - 1]

    def parse_or():
        value = parse_and()
        while peek() == "||":
            take()
            value = parse_and() or value
        return value

    def parse_and():
        value = parse_unary()
        while peek() == "&&":
            take()
            value = parse_unary() and value
        return value

    def parse_unary():
        token = take() if peek() is not None else None
        if token == "!":
            return not parse_unary()
        if token == "(":
            value = parse_or()
            if peek() == ")":
                take()
            return value
        return bool(environment.get(token, False))

    return parse_or() if tokens else False


def join_continuations(lines: list[str]) -> list[str]:
    """uBO joins a line that ends with ' \\' to the next line, which must be indented."""
    joined = []
    for line in lines:
        if joined and joined[-1].endswith(" \\") and line[:1] in (" ", "\t"):
            joined[-1] = joined[-1][:-2].rstrip() + line.strip()
        else:
            joined.append(line)
    return joined


def decode(body: bytes) -> tuple[str, int]:
    text = body.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text, text.count("\ufffd")


def preprocess(text: str, base_url: str, environment: dict, fetcher: Fetcher, includes: list, depth: int = 0) -> list[str]:
    """Applies !#if/!#else/!#endif and resolves !#include, the way uBO does before it compiles a list."""
    output = []
    stack = []  # (parent_active, condition)
    active = True
    for line in join_continuations(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("!#if ") or stripped.startswith("!#if("):
            condition = evaluate_condition(stripped[4:], environment)
            stack.append((active, condition))
            active = active and condition
            continue
        if stripped.startswith("!#else"):
            if stack:
                parent, condition = stack[-1]
                active = parent and not condition
            continue
        if stripped.startswith("!#endif"):
            if stack:
                active, _ = stack.pop()
            continue
        if not active:
            continue
        if stripped.startswith("!#include "):
            target = stripped[len("!#include "):].strip()
            url = urllib.parse.urljoin(base_url, target)
            base = urllib.parse.urlsplit(base_url)
            resolved = urllib.parse.urlsplit(url)
            directory = base.path.rsplit("/", 1)[0] + "/"
            # uBO only follows includes that stay on the list's origin and under its directory.
            if depth > 4 or resolved.netloc != base.netloc or not resolved.path.startswith(directory):
                print(f"warning: {base_url}: ignoring !#include {target}", file=sys.stderr)
                continue
            body, _ = fetcher.get(url)
            included_text, _ = decode(body)
            includes.append(url)
            output.extend(preprocess(included_text, url, environment, fetcher, includes, depth + 1))
            continue
        output.append(line)
    return output


# --- Translation --------------------------------------------------------------------------------------------------

# A line is kept as-is, kept after a translation, or dropped. Reasons are short identifiers that group the report;
# docs/gap-analysis.md explains each one.

HOSTS_LINE = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1|0|::|::1|::0|255\.255\.255\.255|fe80::1%lo0)\s+(.+)$")
HOSTNAME = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z0-9-]{2,63}\.?$", re.I)
HOSTS_IGNORED_NAMES = {"localhost", "localhost.localdomain", "local", "broadcasthost", "0.0.0.0", "ip6-localhost",
                       "ip6-loopback", "ip6-localnet", "ip6-mcastprefix", "ip6-allnodes", "ip6-allrouters"}
# uBO's reHostnameAscii (static-filtering-parser.js). A network pattern that matches it and has no options is a
# hostname to uBO (||hostname^), while adblock-rust reads it as a URL substring.
UBO_HOSTNAME = re.compile(r"^(?:[\da-z][\da-z_-]*\.)*[\da-z][\da-z-]*[\da-z]$")

COSMETIC_MARKER = re.compile(r"#@?[?$%]?#|\$@?\$")

PROCEDURAL_OPERATORS = (
    "has-text", "upward", "xpath", "matches-css", "matches-css-before", "matches-css-after", "matches-attr",
    "matches-path", "matches-prop", "matches-media", "min-text-length", "watch-attr", "others", "-abp-contains",
    "contains", "-abp-properties", "properties", "if", "if-not", "nth-ancestor", "remove-attr", "remove-class",
    "shadow",
)
PROCEDURAL = re.compile(r":(" + "|".join(re.escape(op) for op in sorted(PROCEDURAL_OPERATORS, key=len, reverse=True)) + r")\(")
UNSAFE_STYLE = re.compile(r"url\(|image-set\(|\\|/\*|[{}]|@import|expression\(", re.I)

# adblock-rust's option names (filters/abstract_network.rs). Anything else makes it drop the filter.
ENGINE_OPTIONS = {
    "domain", "from", "to", "badfilter", "important", "match-case", "third-party", "3p", "first-party", "1p", "tag",
    "redirect", "rewrite", "redirect-rule", "csp", "removeparam", "generichide", "ghide", "document", "doc", "image",
    "media", "object", "object-subrequest", "other", "ping", "beacon", "script", "stylesheet", "css", "subdocument",
    "frame", "xmlhttprequest", "xhr", "websocket", "font", "all", "method",
}
# uBO options with nothing that could stand in for them in Ladybird today.
UNSUPPORTED_OPTIONS = {
    "popup": "needs-engine:popup", "popunder": "needs-engine:popup",
    "inline-script": "needs-engine:csp-injection", "inline-font": "needs-engine:csp-injection",
    "header": "needs-engine:response-headers", "permissions": "needs-engine:permissions-policy",
    "replace": "needs-engine:response-rewrite", "urlskip": "needs-engine:url-rewrite",
    "uritransform": "needs-engine:url-rewrite", "urltransform": "needs-engine:url-rewrite",
    "ipaddress": "needs-engine:ip-address", "cname": "needs-engine:cname", "webrtc": "unsupported-option",
    "genericblock": "unsupported-option", "shide": "needs-engine:specifichide",
    "specifichide": "needs-engine:specifichide", "requestheader": "needs-engine:request-headers",
}


OUTCOME_GROUPS = itertools.count()

# The engine hashes $domain entries literally, so an entity like `example.*` (example + any public suffix) never
# matches a page, and `~example.*` never excludes one. Entities are expanded to these suffixes plus any other suffix
# the preset's lists use with the same name (set by index_entity_suffixes()). uBO matches every public suffix; this
# covers the ones in use.
CORE_ENTITY_SUFFIXES = ("com", "net", "org", "info", "biz", "io", "co", "me", "tv", "cc", "to", "ws", "xyz", "site",
                        "online", "top", "club", "live", "pro", "app", "in", "us", "uk", "de", "fr", "es", "it", "nl",
                        "pl", "ru", "br", "co.uk", "com.br", "com.tr")
SECOND_LEVEL_SUFFIXES = {"co.uk", "org.uk", "com.br", "com.au", "co.in", "com.mx", "com.ar", "co.za", "com.tr",
                         "co.id", "com.my", "com.ph", "com.vn", "co.jp", "co.kr", "com.tw", "com.hk", "com.sg",
                         "com.pk", "com.ng", "com.eg", "com.sa", "com.ua", "co.nz", "com.co", "com.pe", "com.pl"}
entity_suffixes: dict[str, set[str]] = defaultdict(set)


def split_suffix(hostname: str) -> tuple[str, str] | None:
    labels = hostname.split(".")
    if len(labels) < 2:
        return None
    if len(labels) > 2 and ".".join(labels[-2:]) in SECOND_LEVEL_SUFFIXES:
        return ".".join(labels[:-2]), ".".join(labels[-2:])
    return ".".join(labels[:-1]), labels[-1]


def index_entity_suffixes(lines: list[str]):
    """Records which suffixes each name appears with across a preset, from cosmetic hostnames and $domain lists."""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("!"):
            continue
        marker = COSMETIC_MARKER.search(stripped)
        hosts = []
        if marker and marker.start() > 0:
            hosts = stripped[:marker.start()].split(",")
        for match in re.finditer(r"(?:domain|from)=([^,$]+)", stripped):
            hosts += match.group(1).split("|")
        for host in hosts:
            host = host.strip().lstrip("~").lower()
            if host.endswith(".*") or not UBO_HOSTNAME.match(host):
                continue
            parts = split_suffix(host)
            if parts:
                entity_suffixes[parts[0]].add(parts[1])


def expand_entity_domains(entries: list[str]) -> list[str]:
    expanded = []
    for entry in entries:
        if not entry.endswith(".*"):
            expanded.append(entry)
            continue
        negation = "~" if entry.startswith("~") else ""
        name = entry.lstrip("~")[:-2]
        suffixes = sorted(set(CORE_ENTITY_SUFFIXES) | entity_suffixes.get(name, set()))
        expanded.extend(f"{negation}{name}.{suffix}" for suffix in suffixes)
    return list(dict.fromkeys(expanded))


@dataclass
class Outcome:
    line: str | None  # None when dropped
    reason: str | None = None  # drop reason
    notes: list[str] = field(default_factory=list)  # translations applied to a kept line
    cancels: str | None = None  # for a generic #@# exception, the selector it turns off everywhere
    to_entries: list[str] | None = None  # $to / $denyallow domains, for expand_to_option()
    group: int | None = None  # outcomes from one upstream filter that are kept or dropped together


def split_options(rest: str) -> list[str]:
    """Splits a network filter's option string on commas that uBO does not treat as escaped."""
    options, current, i = [], [], 0
    while i < len(rest):
        character = rest[i]
        if character == "\\" and i + 1 < len(rest):
            current.append(rest[i:i + 2])
            i += 2
            continue
        if character == ",":
            options.append("".join(current))
            current = []
        else:
            current.append(character)
        i += 1
    options.append("".join(current))
    return options


def split_network_filter(body: str) -> tuple[str, str | None]:
    """Splits a network filter (without @@) into pattern and options at the last '$' that starts valid options."""
    index = body.rfind("$")
    while index >= 0:
        candidate = body[index + 1:]
        if re.match(r"^~?[a-z0-9_-]+(=|,|$)", candidate, re.I):
            return body[:index], candidate
        index = body.rfind("$", 0, index)
    return body, None


def translate_regex_for_lowercasing(pattern: str) -> tuple[str | None, str | None]:
    """The engine lowercases /regex/ patterns that lack $match-case before compiling them, which flips \\D \\W \\S
    into \\d \\w \\s. Rewrite those into forms that survive lowercasing; refuse escapes that cannot be rewritten."""
    if not re.search(r"\\[A-Z]", pattern):
        return pattern, None
    if re.search(r"\\[BAZPQ]", pattern):
        return None, "regex-uppercase-escape"
    replacements = {"D": "[^0-9]", "W": "[^0-9a-z_]", "S": "[^\\s]"}

    def replace(match):
        letter = match.group(1)
        return replacements.get(letter, match.group(0))

    # Leave escaped backslashes alone: only rewrite \X when it is not itself preceded by an escaping backslash.
    translated = re.sub(r"(?<!\\)\\([DWS])", replace, pattern)
    if re.search(r"(?<!\\)\\[A-Z]", translated):
        return None, "regex-uppercase-escape"
    return translated, "regex-lowercase-safe"


def rewrite_regex_dollars(pattern: str) -> str:
    """The engine starts a filter's options at its last '$', so a /regex/ without options must not contain one.
    Rewrite end anchors to \\z (the same thing without multi-line mode) and literal dollars to \\x24."""
    body = pattern[1:-1]
    output = []
    in_class = False
    i = 0
    while i < len(body):
        character = body[i]
        if character == "\\" and i + 1 < len(body):
            output.append("\\x24" if body[i + 1] == "$" else body[i:i + 2])
            i += 2
            continue
        if character == "$":
            output.append("\\x24" if in_class else "\\z")
        else:
            if character == "[" and not in_class:
                in_class = True
            elif character == "]" and in_class:
                in_class = False
            output.append(character)
        i += 1
    return "/" + "".join(output) + "/"


def translate_network(line: str) -> list[Outcome]:
    outcome = translate_network_filter(line)
    if outcome.line is None or not outcome.to_entries:
        return [outcome]
    return expand_to_option(outcome)


def expand_to_option(outcome: Outcome) -> list[Outcome]:
    """The engine discards filters with $to (and so $denyallow). Rewrite the common forms into filters it keeps:

      *$opts,to=a.com|b.com            ->  ||a.com^$opts  and  ||b.com^$opts
      PATTERN$opts,denyallow=a.com     ->  PATTERN$opts  and  @@||a.com^$opts

    The second form is what $denyallow and $to=~a.com mean: block, except requests to a.com. Its exception also
    unblocks other filters' matches on a.com under the same options, so it can block less than uBO, never more. That
    is only acceptable when the filter is scoped to some sites with $domain, and a.com is not a whole TLD: an unscoped
    `@@||com^$script,3p` would let every third-party .com script through everywhere."""
    line = outcome.line
    exception = line.startswith("@@")
    pattern, options_string = split_network_filter(line[2:] if exception else line)
    options = [option for option in split_options(options_string or "") if option]
    entries = outcome.to_entries
    if exception or any("*" in entry or "/" in entry for entry in entries):
        return [Outcome(None, "inert:to")]
    negated = [entry[1:] for entry in entries if entry.startswith("~")]
    positive = [entry for entry in entries if not entry.startswith("~")]

    def make(prefix: str, filter_pattern: str, filter_options: list[str]) -> str:
        return prefix + filter_pattern + ("$" + ",".join(filter_options) if filter_options else "")

    if positive and not negated:
        if pattern not in ("", "*"):
            return [Outcome(None, "inert:to")]
        return [Outcome(make("", f"||{domain}^", options), None, outcome.notes + ["to-to-hostname-filters"])
                for domain in positive]
    if negated and not positive:
        # Exceptions cannot override $important, and would not cover the redirect half of $redirect.
        if "important" in options or any(option.startswith(("redirect", "rewrite")) for option in options):
            return [Outcome(None, "inert:to")]
        scoped = any(option.startswith(("domain=", "from=")) and
                     any(not entry.startswith("~") for entry in option.partition("=")[2].split("|"))
                     for option in options)
        if not scoped or any("." not in domain for domain in negated):
            return [Outcome(None, "inert:to")]
        note = "denyallow-to-exceptions" if "denyallow" in outcome.notes else "to-to-exceptions"
        notes = [n for n in outcome.notes if n != "denyallow"] + [note]
        # A $badfilter stays on every generated filter, so it still cancels them all. $match-case only applies to
        # /regex/ patterns, and leaving it off an exception only widens the exception.
        exception_options = [option for option in options if option != "match-case"]
        outcomes = [Outcome(make("", pattern, options), None, notes)]
        outcomes += [Outcome(make("@@", f"||{domain}^", exception_options), None, notes) for domain in negated]
        # The block filter must not survive without its exceptions: build_list() keeps or drops them together.
        group = next(OUTCOME_GROUPS)
        for generated in outcomes:
            generated.group = group
        return outcomes
    return [Outcome(None, "inert:to")]


def translate_network_filter(line: str) -> Outcome:
    exception = line.startswith("@@")
    body = line[2:] if exception else line
    pattern, options_string = split_network_filter(body)
    notes = []
    to_entries = []

    if not pattern and options_string is None:
        return Outcome(None, "empty")

    is_regex = len(pattern) > 1 and pattern.startswith("/") and pattern.endswith("/")

    # Without options, a bare hostname (or ||hostname without ^) is a hostname match to uBO: ||hostname^.
    if options_string is None and not is_regex:
        anchored = pattern.startswith("||")
        bare = pattern[2:] if anchored else pattern
        if (anchored or not pattern.startswith("|")) and UBO_HOSTNAME.match(bare.lower()):
            pattern = "||" + bare.lower() + "^"
            notes.append("hostname-anchor-completed" if anchored else "plain-hostname")

    options = split_options(options_string) if options_string is not None else []
    translated = []
    match_case = False
    for option in options:
        option = option.strip()
        if not option:
            continue
        negated = option.startswith("~")
        name, _, value = option.lstrip("~").partition("=")
        name = name.lower()

        if name in ("domain", "from", "to"):
            entries = value.split("|")
            regex_entries = [entry for entry in entries if entry.lstrip("~").startswith("/")]
            if regex_entries:
                # Regex domain entries are dropped by the engine. Dropping a negated one widens the filter.
                if any(entry.startswith("~") for entry in regex_entries):
                    return Outcome(None, "regex-domain")
                entries = [entry for entry in entries if entry not in regex_entries]
                if not entries:
                    return Outcome(None, "regex-domain")
                notes.append("regex-domain-entries-removed")
                option = f"{name}={'|'.join(entries)}"
            if any(entry.endswith(".*") for entry in entries):
                entries = expand_entity_domains(entries)
                notes.append("entity-domain-expanded")
                option = f"{name}={'|'.join(entries)}"
            if name == "to":
                to_entries.extend(entries)
            else:
                translated.append(option)
        elif name == "match-case":
            match_case = True
            translated.append(option)
        elif name in ("_",) or re.fullmatch(r"_+", name):
            notes.append("noop-option")  # uBO's $_ is a no-op used for readability
        elif name == "reason":
            notes.append("reason-stripped")  # message shown on uBO's strict-blocking page
        elif name == "empty" and not negated:
            translated.append("redirect=empty")
            notes.append("empty-to-redirect")
        elif name == "mp4" and not negated:
            translated.extend(["media", "redirect=noopmp4-1s"])
            notes.append("mp4-to-redirect")
        elif name in ("ehide", "elemhide"):
            if not exception:
                return Outcome(None, "unsupported-option")
            # adblock-rust has no $specifichide, so only the generic half of $elemhide carries over.
            translated.append("generichide")
            notes.append("elemhide-to-generichide")
        elif name == "denyallow":
            # $denyallow=a|b is $to=~a|~b; expand_to_option() rewrites both.
            to_entries.extend("~" + entry for entry in value.split("|") if entry)
            notes.append("denyallow")
        elif name in ("strict3p", "strict-third-party"):
            # Only translate when the result blocks no more than uBO would.
            if exception:
                return Outcome(None, "strict-party")
            translated.append("~3p" if negated else "3p")
            notes.append("strict3p-to-3p")
        elif name in ("strict1p", "strict-first-party"):
            if not exception:
                return Outcome(None, "strict-party")
            translated.append("~1p" if negated else "1p")
            notes.append("strict1p-to-1p")
        elif name == "redirect-rule":
            return Outcome(None, "inert:redirect-rule")
        elif name == "removeparam" or name == "queryprune":
            return Outcome(None, "inert:removeparam")
        elif name == "csp":
            return Outcome(None, "inert:csp")
        elif name == "method":
            return Outcome(None, "inert:method")
        elif name in UNSUPPORTED_OPTIONS:
            return Outcome(None, UNSUPPORTED_OPTIONS[name])
        elif name in ENGINE_OPTIONS:
            translated.append(option)
        else:
            return Outcome(None, "unsupported-option")

    if is_regex and not match_case:
        pattern, note = translate_regex_for_lowercasing(pattern)
        if pattern is None:
            return Outcome(None, note)
        if note:
            notes.append(note)
    if is_regex and "$" in pattern and not translated:
        pattern = rewrite_regex_dollars(pattern)
        notes.append("regex-dollar-rewritten")

    result = ("@@" if exception else "") + pattern
    if translated:
        result += "$" + ",".join(translated)
    elif options_string is not None and not options:
        result += "$"
    return Outcome(result, None, notes, to_entries=to_entries or None)


def selector_is_balanced(selector: str) -> bool:
    """Rejects selectors that could swallow the rules after them in the engine's generated style sheet."""
    depth_round = depth_square = 0
    quote = None
    i = 0
    while i < len(selector):
        character = selector[i]
        if character == "\\":
            i += 2
            continue
        if quote:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character == "(":
            depth_round += 1
        elif character == ")":
            depth_round -= 1
        elif character == "[":
            depth_square += 1
        elif character == "]":
            depth_square -= 1
        elif character in "{};":
            return False
        if depth_round < 0 or depth_square < 0:
            return False
        i += 1
    return quote is None and depth_round == 0 and depth_square == 0


def strip_quoted(text: str) -> str:
    return re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", '""', text)


def translate_cosmetic(line: str, marker_match: re.Match) -> Outcome:
    hosts = line[:marker_match.start()]
    marker = marker_match.group(0)
    body = line[marker_match.end():].strip()
    notes = []

    if marker in ("$$", "$@$"):
        return Outcome(None, "needs-engine:html-filtering")
    if "%" in marker:
        return Outcome(None, "needs-engine:scriptlets")  # AdGuard JavaScript rules
    if "$" in marker:
        return Outcome(None, "adguard-css-injection")
    if body.startswith("+js("):
        return Outcome(None, "needs-engine:scriptlets")
    if body.startswith("^"):
        return Outcome(None, "needs-engine:html-filtering")
    if hosts.startswith("[$"):
        return Outcome(None, "location-modifier")
    if not body:
        return Outcome(None, "empty")

    exception = "@" in marker
    if "?" in marker:
        notes.append("extended-marker")
    marker = "#@#" if exception else "##"

    # Hostnames: uBO accepts *##, which is generic. Regex hostnames are unsupported.
    entries = [entry.strip() for entry in hosts.split(",") if entry.strip()] if hosts else []
    if entries == ["*"]:
        entries = []
        notes.append("wildcard-host")
    regex_entries = [entry for entry in entries if entry.lstrip("~").startswith("/")]
    if regex_entries:
        if any(entry.startswith("~") for entry in regex_entries):
            return Outcome(None, "regex-hostname")
        entries = [entry for entry in entries if entry not in regex_entries]
        if not entries:
            return Outcome(None, "regex-hostname")
        notes.append("regex-hostname-entries-removed")
    generic = not entries
    if generic and exception:
        # uBO applies #@#selector on every page; the engine rejects it. build_preset() removes the hiding rules it
        # cancels instead.
        return Outcome(None, "generic-exception-applied", cancels=body)
    if exception and any(entry.startswith("~") for entry in entries):
        # The engine rejects negated hostnames on exceptions. Dropping the negations only widens the exception.
        positive = [entry for entry in entries if not entry.startswith("~")]
        if not positive:
            return Outcome(None, "negated-exception")
        entries = positive
        notes.append("exception-negations-removed")

    # Actions.
    style = None
    abp_brace = re.match(r"^(.*?)\s*\{\s*(.*?)\s*\}$", body)
    if abp_brace:
        selector, declarations = abp_brace.group(1), abp_brace.group(2)
        if re.fullmatch(r"remove\s*:\s*true\s*;?", declarations):
            body = selector + ":remove()"
        else:
            body = f"{selector}:style({declarations})"
    if body.endswith(":remove()"):
        body = body[: -len(":remove()")]
        notes.append("remove-to-hide")
    else:
        style_match = re.search(r":style\((.*)\)$", body)
        if style_match:
            style = style_match.group(1)
            body = body[: style_match.start()]
            if generic:
                return Outcome(None, "generic-style")
            if UNSAFE_STYLE.search(style):
                return Outcome(None, "unsafe-style")

    selector = body
    if ":-abp-has(" in selector:
        selector = selector.replace(":-abp-has(", ":has(")
        notes.append("abp-has-to-has")
    unquoted = strip_quoted(selector)
    procedural = PROCEDURAL.search(unquoted)
    if procedural:
        if procedural.group(1) in ("remove-attr", "remove-class"):
            return Outcome(None, "needs-engine:dom-actions")
        return Outcome(None, "needs-engine:procedural")
    if "[-ext-" in unquoted:
        return Outcome(None, "needs-engine:procedural")
    if not selector or not selector_is_balanced(selector):
        return Outcome(None, "malformed-selector")

    result = ",".join(entries) + marker + selector
    if style is not None:
        result += f":style({style})"
    return Outcome(result, None, notes)


def translate(line: str) -> list[Outcome] | None:
    """Translates one preprocessed line. Returns None for comments and blank lines."""
    stripped = line.strip()
    if not stripped or stripped.startswith("!") or stripped.lower().startswith("[adblock"):
        return None
    if stripped.startswith("#") and not COSMETIC_MARKER.match(stripped):
        return None  # hosts-file comment
    if "\ufffd" in stripped:
        return [Outcome(None, "invalid-utf8")]

    hosts = HOSTS_LINE.match(stripped)
    if hosts:
        names = hosts.group(1).split("#", 1)[0].split()
        outcomes = []
        for name in names:
            name = name.lower().rstrip(".")
            if name in HOSTS_IGNORED_NAMES or not HOSTNAME.match(name):
                continue
            outcomes.append(Outcome(f"||{name}^", None, ["hosts-file"]))
        return outcomes or None

    marker = COSMETIC_MARKER.search(stripped)
    # Same test as the engine (lists.rs detect_filter_type): a second '#' within 4 bytes of the first one, or $$.
    first_sharp = stripped.find("#")
    looks_cosmetic = first_sharp >= 0 and "#" in stripped[first_sharp + 1:first_sharp + 5]
    if marker and (looks_cosmetic or marker.group(0) in ("$$", "$@$")):
        return [translate_cosmetic(stripped, marker)]
    return translate_network(stripped)


# --- Engine probe -------------------------------------------------------------------------------------------------


def probe_binary() -> Path:
    target = ROOT / "build" / "probe-target"
    binary = target / "release" / "xenon-ublock-probe"
    sources = list((ROOT / "probe").rglob("*.rs")) + [ROOT / "probe" / "Cargo.toml"]
    if not binary.exists() or any(source.stat().st_mtime > binary.stat().st_mtime for source in sources):
        subprocess.run(["cargo", "build", "--release", "--quiet", "--manifest-path", str(ROOT / "probe" / "Cargo.toml"),
                        "--target-dir", str(target)], check=True)
    return binary


def probe(binary: Path, lines: list[str], scratch: Path) -> list[dict]:
    scratch.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    result = subprocess.run([str(binary), str(scratch)], check=True, capture_output=True, text=True)
    verdicts = [json.loads(line) for line in result.stdout.splitlines()]
    if len(verdicts) != len(lines):
        raise RuntimeError(f"probe returned {len(verdicts)} verdicts for {len(lines)} lines")
    return verdicts


def engine_drop_reason(verdict: dict) -> str | None:
    """Why a line the probe parsed still has no effect in Ladybird, or None if it does."""
    kind = verdict["t"]
    if kind == "e":
        return "engine-rejects:" + re.sub(r"^(network|cosmetic) filter error: ", "", verdict["error"]).replace(" ", "-")
    if kind == "n":
        if verdict["csp"]:
            return "inert:csp"
        if verdict["removeparam"]:
            return "inert:removeparam"
        if verdict["redirect"] == "rule":
            return "inert:redirect-rule"
        if verdict["method"]:
            return "inert:method"
        if verdict["to"]:
            return "inert:to"
        if verdict["regex_error"]:
            return "regex-unsupported"
        return None
    if verdict["script"]:
        return "needs-engine:scriptlets"
    if verdict["action"] in ("remove-attr", "remove-class"):
        return "needs-engine:dom-actions"
    if verdict["action"] == "remove":
        return "needs-engine:dom-actions"
    return None



# --- uBlock Origin resources --------------------------------------------------------------------------------------


def build_resources(config: dict, fetcher: Fetcher, out_dir: Path) -> dict:
    """Builds the scriptlet and redirect resources the patched engine (engine/) loads, from uBO's source."""
    version = config["version"]
    archive_url = config["source"].format(version=version)
    body, _ = fetcher.get(archive_url)
    source_root = ROOT / "build" / "ubo" / version
    if not (source_root / "src").exists():
        shutil.rmtree(source_root, ignore_errors=True)
        source_root.mkdir(parents=True)
        archive = ROOT / "build" / "ubo" / f"{version}.tar.gz"
        archive.write_bytes(body)
        with tarfile.open(archive) as tar:
            tar.extractall(source_root, filter="data")
        # GitHub archives hold one top-level directory.
        (top,) = [path for path in source_root.iterdir() if path.is_dir()]
        for child in top.iterdir():
            child.rename(source_root / child.name)
        top.rmdir()

    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "ublock-resources.json"
    result = subprocess.run(["node", str(ROOT / "tools" / "build_resources.mjs"), str(source_root), str(output), version],
                            check=True, capture_output=True, text=True)
    print(result.stdout.strip())
    shutil.copyfile(source_root / "LICENSE.txt", out_dir / "LICENSE.txt")
    data = output.read_bytes()
    return {
        "file": f"{out_dir.name}/{output.name}",
        "ublock_version": version,
        "source": archive_url,
        "license": "GPL-3.0",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


# --- Building -----------------------------------------------------------------------------------------------------


@dataclass
class ListSource:
    id: str
    title: str
    group: str
    urls: list[str]
    support_url: str | None


@dataclass
class BuiltList:
    source: ListSource
    upstream_url: str
    upstream_sha256: str
    upstream_bytes: int
    includes: list[str]
    license_header: str | None
    kept: list[str]
    input_filters: int = 0
    kept_upstream: int = 0
    kept_unchanged: int = 0
    translated: Counter = field(default_factory=Counter)
    dropped: Counter = field(default_factory=Counter)
    dropped_lines: list[tuple[str, str]] = field(default_factory=list)
    duplicates: int = 0


def default_lists(assets: dict, languages: set[str]) -> list[ListSource]:
    sources = []
    for list_id, asset in assets.items():
        if asset.get("content") != "filters":
            continue
        regional = asset.get("group") == "regions"
        if regional:
            if not languages or not (set(str(asset.get("lang", "")).split()) & languages):
                continue
        elif asset.get("off"):
            continue
        content_urls = asset.get("contentURL", [])
        content_urls = [content_urls] if isinstance(content_urls, str) else content_urls
        urls = [url for url in content_urls if url.startswith(("https://", "http://"))]
        urls += [url for url in asset.get("cdnURLs", []) if url.startswith(("https://", "http://"))]
        if list_id in URL_OVERRIDES:
            urls = [URL_OVERRIDES[list_id]] + urls
        if not urls:
            print(f"warning: {list_id} has no remote URL; skipping", file=sys.stderr)
            continue
        sources.append(ListSource(list_id, asset.get("title", list_id), asset.get("group", ""), urls,
                                  asset.get("supportURL")))
    return sources


def fetch_list(source: ListSource, fetcher: Fetcher, environment: dict) -> tuple[str, bytes, list[str], list[str]]:
    errors = []
    for url in source.urls:
        try:
            body, _ = fetcher.get(url)
        except FetchError as error:
            errors.append(str(error))
            continue
        text, _ = decode(body)
        includes = []
        lines = preprocess(text, url, environment, fetcher, includes)
        return url, body, includes, lines
    raise FetchError(f"{source.id}: every URL failed: {'; '.join(errors)}")


def build_list(source: ListSource, fetched, binary: Path, scratch: Path, cancelled: set[str]) -> BuiltList:
    """Translates one list and keeps what the engine will apply. `cancelled` holds the selectors that generic #@#
    exceptions anywhere in the preset turn off: the preset loads as one engine, so an exception in one list (usually
    uBO's) cancels hiding rules in another (usually EasyList), as it does in uBO."""
    url, body, includes, lines = fetched
    license_header = None
    for line in lines[:60]:
        match = re.match(r"^!\s*Licen[cs]e:\s*(.+)$", line.strip(), re.I)
        if match:
            license_header = match.group(1).strip()
            break

    built = BuiltList(source, url, hashlib.sha256(body).hexdigest(), len(body), includes, license_header, [])
    upstream = []  # upstream filter lines; counts below are per upstream line
    drop_reasons = defaultdict(list)
    candidates = []  # (upstream index, outcome)
    for line in lines:
        outcomes = translate(line)
        if outcomes is None:
            continue
        index = len(upstream)
        upstream.append(line.strip())
        for outcome in outcomes:
            if outcome.line is None:
                drop_reasons[index].append(outcome.reason)
            elif is_cancelled(outcome.line, cancelled):
                drop_reasons[index].append("cancelled-by-generic-exception")
            else:
                candidates.append((index, outcome))

    verdicts = probe(binary, [outcome.line for _, outcome in candidates], scratch)
    reasons = [engine_drop_reason(verdict) for verdict in verdicts]
    failed_groups = {}
    for (_, outcome), reason in zip(candidates, reasons):
        if reason and outcome.group is not None:
            failed_groups.setdefault(outcome.group, reason)

    seen = set()
    kept_notes = {}  # upstream index -> translations applied
    for (index, outcome), reason in zip(candidates, reasons):
        reason = reason or failed_groups.get(outcome.group)
        if reason:
            drop_reasons[index].append(reason)
            continue
        kept_notes.setdefault(index, set()).update(outcome.notes)
        if outcome.line in seen:
            built.duplicates += 1
            continue
        seen.add(outcome.line)
        built.kept.append(outcome.line)

    built.input_filters = len(upstream)
    built.kept_upstream = len(kept_notes)
    for index, original in enumerate(upstream):
        if index in kept_notes:
            if kept_notes[index]:
                built.translated.update(kept_notes[index])
            else:
                built.kept_unchanged += 1
        else:
            reason = drop_reasons[index][0] if drop_reasons[index] else "unknown"
            built.dropped[reason] += 1
            built.dropped_lines.append((reason, original))
    return built


def generic_exception_selectors(lines: list[str]) -> set[str]:
    """The selectors that a list's generic #@# exceptions turn off on every page."""
    selectors = set()
    for line in lines:
        for outcome in translate(line) or []:
            if outcome.cancels:
                selectors.add(outcome.cancels)
    return selectors


def is_cancelled(line: str, cancelled: set[str]) -> bool:
    hosts, sharp, body = line.partition("##")
    return bool(sharp) and "#" not in hosts and body in cancelled


def list_header(built: BuiltList, license_info: dict | None, generated_at: str) -> str:
    source = built.source
    license_text = license_info["license"] if license_info else "not recorded; review before shipping"
    lines = [
        f"! Title: {source.title} (for Ladybird)",
        f"! Source: {built.upstream_url}",
    ]
    if source.support_url:
        lines.append(f"! Homepage: {source.support_url}")
    lines += [
        f"! License: {license_text}" + (f" ({license_info['url']})" if license_info else ""),
        f"! Converted by xenon-ublock on {generated_at} for {ENGINE}.",
        f"! Kept {built.kept_upstream} of {built.input_filters} upstream filters, as {len(built.kept)} filters; the rest cannot take",
        "! effect in Ladybird. See report.md and dropped/ next to this file for what was dropped and why.",
        "!",
    ]
    return "\n".join(lines) + "\n"


def write_report(path: Path, preset: str, preset_config: dict, built_lists: list[BuiltList], generated_at: str):
    total_input = sum(b.input_filters for b in built_lists)
    total_kept = sum(b.kept_upstream for b in built_lists)
    total_output = sum(len(b.kept) for b in built_lists)
    dropped = Counter()
    translated = Counter()
    examples = defaultdict(list)
    for built in built_lists:
        dropped.update(built.dropped)
        translated.update(built.translated)
        for reason, line in built.dropped_lines:
            if len(examples[reason]) < 3 and len(line) < 200:
                examples[reason].append(f"{built.source.id}: `{line}`")

    out = [f"# {preset_config['title']}: conversion report", "",
           f"Built {generated_at} for {ENGINE}.", "",
           f"{total_kept:,} of {total_input:,} upstream filters kept ({100 * total_kept / max(total_input, 1):.1f}%), "
           f"written as {total_output:,} filters.",
           "Counts are per upstream filter line, after uBO's preprocessor. One upstream line can become several filters "
           "(a hosts-file line with several names, or a `$denyallow` filter and its exceptions).", "",
           "## Lists", "",
           "| List | Upstream filters | Kept | Translated | Dropped | Output filters | Size |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for built in built_lists:
        size = sum(len(line) + 1 for line in built.kept)
        translated_count = built.kept_upstream - built.kept_unchanged
        out.append(f"| {built.source.title} (`{built.source.id}`) | {built.input_filters:,} | {built.kept_upstream:,} | "
                   f"{translated_count:,} | {sum(built.dropped.values()):,} | {len(built.kept):,} | {size / 1024:,.0f} KiB |")
    out += ["", "## Dropped, by reason", "", "| Reason | Filters | Examples |", "|---|---:|---|"]
    for reason, count in dropped.most_common():
        cell = "<br>".join(example.replace("|", "\\|") for example in examples[reason])
        out.append(f"| `{reason}` | {count:,} | {cell} |")
    out += ["", "## Translated", "", "Upstream filters kept after each translation (one filter can need several).", "",
            "| Translation | Filters |", "|---|---:|"]
    for note, count in translated.most_common():
        out.append(f"| `{note}` | {count:,} |")
    scriptlets = Counter()
    for built in built_lists:
        for reason, line in built.dropped_lines:
            match = re.search(r"##\+js\(([^,)]+)", line)
            if match:
                scriptlets[match.group(1).strip()] += 1
    if scriptlets:
        out += ["", "## Scriptlets that were dropped", "",
                "What a scriptlet engine would need first, by number of filters using each scriptlet.", "",
                "| Scriptlet | Filters |", "|---|---:|"]
        for name, count in scriptlets.most_common(25):
            out.append(f"| `{name}` | {count:,} |")
    out += ["", "Reasons are explained in docs/gap-analysis.md. Every dropped line is in `dropped/<id>.tsv`.", ""]
    path.write_text("\n".join(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preset", action="append", help="preset to build (default: all in config/lists.json)")
    parser.add_argument("--lang", action="append", default=[],
                        help="also build uBO's regional lists for this language code, as uBO does for the browser's "
                             "locale (repeatable)")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--cache", type=Path, default=ROOT / "build" / "cache")
    parser.add_argument("--offline", action="store_true", help="only use cached downloads")
    parser.add_argument("--refresh", action="store_true", help="ignore cached downloads")
    parser.add_argument("--max-age", type=float, default=6, help="hours a cached download stays fresh (default 6)")
    parser.add_argument("--no-resources", action="store_true",
                        help="skip building uBO's scriptlet and redirect resources (needs Node.js)")
    args = parser.parse_args()

    config = json.loads((ROOT / "config" / "lists.json").read_text())
    presets = args.preset or list(config["presets"])
    for preset in presets:
        if preset not in config["presets"]:
            parser.error(f"unknown preset {preset}")
    environment = {key: value for key, value in config["environment"].items() if not key.startswith("_")}
    licenses = {key: value for key, value in config["licenses"].items() if not key.startswith("_")}
    languages = {code.lower() for code in args.lang}
    fetcher = Fetcher(args.cache, args.offline, 0 if args.refresh else args.max_age * 3600)
    binary = probe_binary()
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    manifest = {"generated_at": generated_at, "engine": ENGINE, "environment": environment, "presets": {}}
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.no_resources:
        manifest["resources"] = build_resources(config["ublock"], fetcher, args.out / "resources")
    scratch_dir = ROOT / "build" / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    for preset in presets:
        preset_config = config["presets"][preset]
        assets_body, _ = fetcher.get(preset_config["assets"])
        sources = default_lists(json.loads(assets_body), languages)
        print(f"{preset}: {len(sources)} lists")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {source.id: pool.submit(fetch_list, source, fetcher, environment) for source in sources}
            fetched = {list_id: future.result() for list_id, future in futures.items()}

        preset_dir = args.out / preset
        if preset_dir.exists():
            shutil.rmtree(preset_dir)
        (preset_dir / "lists").mkdir(parents=True)
        (preset_dir / "dropped").mkdir()

        cancelled = set().union(*(generic_exception_selectors(fetched[source.id][3]) for source in sources))
        entity_suffixes.clear()
        for source in sources:
            index_entity_suffixes(fetched[source.id][3])
        built_lists = []
        for source in sources:
            built = build_list(source, fetched[source.id], binary, scratch_dir / f"{preset}-{source.id}.txt", cancelled)
            built_lists.append(built)
            print(f"  {source.id}: kept {built.kept_upstream:,} of {built.input_filters:,}")

        manifest_lists = []
        combined = []
        for built in built_lists:
            source = built.source
            license_info = licenses.get(source.id)
            text = list_header(built, license_info, generated_at) + "".join(line + "\n" for line in built.kept)
            data = text.encode("utf-8")
            if len(data) > MAXIMUM_LIST_SIZE:
                raise SystemExit(f"{source.id}: {len(data)} bytes is over Ladybird's per-list limit")
            (preset_dir / "lists" / f"{source.id}.txt").write_bytes(data)
            combined.append(data)
            (preset_dir / "dropped" / f"{source.id}.tsv").write_text(
                "".join(f"{reason}\t{line}\n" for reason, line in built.dropped_lines), encoding="utf-8")
            manifest_lists.append({
                "id": source.id,
                "title": source.title,
                "group": source.group,
                "file": f"{preset}/lists/{source.id}.txt",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "license": license_info["license"] if license_info else None,
                "license_url": license_info["url"] if license_info else None,
                "license_needs_review": not license_info or bool(license_info.get("review")),
                "upstream": {
                    "url": built.upstream_url,
                    "includes": built.includes,
                    "bytes": built.upstream_bytes,
                    "sha256": built.upstream_sha256,
                    "license_header": built.license_header,
                    "homepage": source.support_url,
                },
                "filters": {
                    "upstream": built.input_filters,
                    "kept": built.kept_upstream,
                    "output": len(built.kept),
                    "kept_unchanged": built.kept_unchanged,
                    "translated": dict(built.translated.most_common()),
                    "dropped": dict(built.dropped.most_common()),
                    "duplicates": built.duplicates,
                },
            })
            if not license_info or license_info.get("review"):
                print(f"  note: review the license of {source.id} before shipping it", file=sys.stderr)

        combined_data = b"\n".join(combined)
        if len(combined_data) > MAXIMUM_COMBINED_LIST_SIZE:
            raise SystemExit(f"{preset}: {len(combined_data)} bytes is over Ladybird's combined limit")
        (preset_dir / "all.txt").write_bytes(combined_data)
        write_report(preset_dir / "report.md", preset, preset_config, built_lists, generated_at)
        manifest["presets"][preset] = {
            "title": preset_config["title"],
            "description": preset_config["description"],
            "assets": preset_config["assets"],
            "combined_file": f"{preset}/all.txt",
            "combined_bytes": len(combined_data),
            "combined_sha256": hashlib.sha256(combined_data).hexdigest(),
            "lists": manifest_lists,
        }
        kept = sum(b.kept_upstream for b in built_lists)
        total = sum(b.input_filters for b in built_lists)
        print(f"{preset}: kept {kept:,} of {total:,} filters, {len(combined_data) / 1048576:.1f} MiB -> {preset_dir}")

    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
