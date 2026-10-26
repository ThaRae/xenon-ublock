// SPDX-License-Identifier: GPL-3.0-or-later
//
// Reads filter lines and reports, one JSON object per line, how Ladybird's content blocker parses each of them.
//
// Ladybird builds its blocker with `adblock` 0.13.3 and default features, and hands it every list as one string
// (see ladybird/Libraries/LibWeb/ContentBlocker/Rust/src/lib.rs). This probe uses the same version and parser entry
// point, so "the probe accepts it" means "the engine accepts it". It also reports the properties that decide whether
// an accepted filter has any effect in Ladybird, which only acts on block/allow decisions and on CSS it can apply.
//
// Usage: xenon-ublock-probe <filters.txt>   (JSON lines on stdout, in input order)

use std::io::{BufWriter, Write};

use adblock::filters::cosmetic::{CosmeticFilterAction, CosmeticFilterMask};
use adblock::filters::network::{FilterPart, NetworkFilter, NetworkFilterMask, NetworkFilterMaskHelper};
use adblock::lists::{ParseOptions, ParsedLine, parse_filter};
use serde_json::{Value, json};

/// Compiles a `/regex/` pattern the way `adblock::regex_manager::compile_regex` does.
fn complete_regex_error(pattern: &str) -> Option<String> {
    if pattern.len() < 2 {
        return None;
    }
    let unescaped = pattern[1..pattern.len() - 1].replace("\\/", "/").replace("\\:", ":");
    regex::bytes::RegexBuilder::new(&unescaped)
        .unicode(false)
        .build()
        .err()
        .map(|error| error.to_string().lines().last().unwrap_or_default().trim().to_string())
}

fn network_verdict(filter: &NetworkFilter<'_>) -> Value {
    let mut regex_error = None;
    if filter.is_complete_regex() {
        let patterns: Vec<&str> = match &filter.filter {
            FilterPart::Empty => vec![],
            FilterPart::Simple(pattern) => vec![pattern.as_ref()],
            FilterPart::AnyOf(patterns) => patterns.iter().map(AsRef::as_ref).collect(),
        };
        regex_error = patterns.into_iter().find_map(complete_regex_error);
    }

    let redirect = if !filter.is_redirect() {
        Value::Null
    } else if filter.also_block_redirect() {
        json!("block")
    } else {
        json!("rule")
    };

    let methods = NetworkFilterMask::FROM_GET | NetworkFilterMask::FROM_HEAD | NetworkFilterMask::FROM_POST;

    json!({
        "t": "n",
        "exception": filter.is_exception(),
        "important": filter.is_important(),
        "badfilter": filter.is_badfilter(),
        "csp": filter.is_csp(),
        "removeparam": filter.is_removeparam(),
        "redirect": redirect,
        "method": filter.mask.intersects(methods),
        // The engine's builder discards filters with $to (filters/fb_network_builder.rs).
        "to": filter.has_to_option(),
        "generichide": filter.is_generic_hide(),
        "regex": filter.is_complete_regex(),
        "regex_error": regex_error,
    })
}

fn main() {
    let Some(path) = std::env::args().nth(1) else {
        eprintln!("usage: xenon-ublock-probe <filters.txt>");
        std::process::exit(2);
    };
    let text = match std::fs::read_to_string(&path) {
        Ok(text) => text,
        Err(error) => {
            eprintln!("{path}: {error}");
            std::process::exit(1);
        }
    };

    let stdout = std::io::stdout();
    let mut out = BufWriter::new(stdout.lock());

    // Ladybird parses with `ParseOptions::default()` (standard format, all rule types, no scriptlet permissions)
    // and without debug info.
    let options = ParseOptions::default();
    for line in text.lines() {
        let verdict = match parse_filter(line, false, options) {
            Ok(ParsedLine::Network(filter)) => network_verdict(&filter),
            Ok(ParsedLine::Cosmetic(filter)) => {
                let action = match &filter.action {
                    None => Value::Null,
                    Some(CosmeticFilterAction::Remove) => json!("remove"),
                    Some(CosmeticFilterAction::Style(_)) => json!("style"),
                    Some(CosmeticFilterAction::RemoveAttr(_)) => json!("remove-attr"),
                    Some(CosmeticFilterAction::RemoveClass(_)) => json!("remove-class"),
                };
                json!({
                    "t": "c",
                    "unhide": filter.mask.contains(CosmeticFilterMask::UNHIDE),
                    "script": filter.mask.contains(CosmeticFilterMask::SCRIPT_INJECT),
                    "generic": !filter.has_hostname_constraint(),
                    "action": action,
                })
            }
            Err(error) => json!({ "t": "e", "error": error.to_string() }),
        };
        if serde_json::to_writer(&mut out, &verdict).is_err() || out.write_all(b"\n").is_err() {
            std::process::exit(1);
        }
    }
    if out.flush().is_err() {
        std::process::exit(1);
    }
}
