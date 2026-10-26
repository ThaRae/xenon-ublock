/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Loads filter lists into Ladybird's real content blocker and checks expectations against it.
 *
 * This links liblibweb_content_blocker_rust.a, built unmodified from ladybird/Libraries/LibWeb/ContentBlocker/Rust,
 * and calls the same FFI functions that Web::ContentBlocker (LibWeb/Loader/ContentBlocker.cpp) calls. The rules are
 * joined the way WebView::Application::load_content_blocker_lists() joins enabled lists: each file followed by a
 * newline, then the custom filters (empty here) and a newline.
 *
 * Usage:
 *   engine_check [--rules FILE]... [--vectors FILE]... [--css PAGE_URL CLASSES IDS] [--repeat N]
 *
 * Vector file lines (fields separated by whitespace; the selector is the rest of the line):
 *   block  URL SOURCE_URL TYPE        the engine must block the request
 *   allow  URL SOURCE_URL TYPE        the engine must not block the request
 *   hide   PAGE_URL CLASSES IDS SEL   the page's cosmetic style sheet must contain a rule for SEL
 *   show   PAGE_URL CLASSES IDS SEL   the page's cosmetic style sheet must not contain a rule for SEL
 *   rules  FILTER                     adds FILTER to an inline list; the vectors after it run against
 *                                     an engine built from just the inline list (for engine quirk tests)
 * CLASSES and IDS are comma-separated, or "-" for none. TYPE is an adblock request type (script, image, ...).
 */

#define _POSIX_C_SOURCE 200809L

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* AK::ReadonlySpan<u8> as laid out by ak::Span (AK/Rust/src/slice.rs). */
typedef struct {
    uint8_t const* data;
    size_t size;
} Span;

typedef struct {
    uint8_t* data;
    size_t length;
} ContentBlockerString;

/* From the cbindgen header generated for libweb_content_blocker_rust (ContentBlockerRustFFI.h). */
extern void* rust_content_blocker_create(Span rules);
extern void rust_content_blocker_free(void* engine);
extern bool rust_content_blocker_matches(void const* engine, Span url, Span source_url, Span request_type);
extern ContentBlockerString rust_content_blocker_cosmetic_css(void const* engine, Span url, Span classes, Span ids);
extern void rust_content_blocker_free_string(uint8_t* data, size_t length);

/* The crate reports panics through these hooks, which Ladybird implements in C++ (AK). */
void ladybird_rust_panic(uint8_t const* message, size_t message_length, uint8_t const* filename,
    size_t filename_length, uint32_t line, uint32_t column, bool (*is_panicking)(void))
{
    (void)is_panicking;
    fprintf(stderr, "Rust panic at %.*s:%u:%u: %.*s\n", (int)filename_length, filename, line, column,
        (int)message_length, message);
}
void ladybird_rust_panic_hook_returned(void) { }
void ladybird_rust_panic_may_abort(void) { }
void ladybird_rust_panic_will_abort(void) { abort(); }

static Span span_of(char const* string)
{
    return (Span) { (uint8_t const*)string, strlen(string) };
}

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

typedef struct {
    char* data;
    size_t size;
    size_t capacity;
} Buffer;

static void buffer_append(Buffer* buffer, char const* data, size_t size)
{
    if (buffer->size + size + 1 > buffer->capacity) {
        size_t capacity = buffer->capacity ? buffer->capacity : 4096;
        while (buffer->size + size + 1 > capacity)
            capacity *= 2;
        buffer->data = realloc(buffer->data, capacity);
        if (!buffer->data) {
            perror("realloc");
            exit(2);
        }
        buffer->capacity = capacity;
    }
    memcpy(buffer->data + buffer->size, data, size);
    buffer->size += size;
    buffer->data[buffer->size] = '\0';
}

static void buffer_append_file(Buffer* buffer, char const* path)
{
    FILE* file = fopen(path, "rb");
    if (!file) {
        perror(path);
        exit(2);
    }
    char chunk[65536];
    size_t count;
    while ((count = fread(chunk, 1, sizeof(chunk), file)) > 0)
        buffer_append(buffer, chunk, count);
    fclose(file);
}

/* Web::ContentBlocker::set_rules_from_bytes() only builds cosmetic CSS when this finds a `##`-style marker. */
static bool rules_contain_cosmetic_rules(char const* rules)
{
    for (char const* line = rules; line && *line;) {
        char const* end = strchr(line, '\n');
        size_t length = end ? (size_t)(end - line) : strlen(line);
        while (length && (*line == ' ' || *line == '\t'))
            ++line, --length;
        if (length && line[0] != '!' && line[0] != '[') {
            char const* sharp = memchr(line, '#', length);
            if (sharp && (size_t)(sharp - line) + 1 < length) {
                char const* after = sharp + 1;
                size_t remaining = length - (size_t)(after - line);
                char const* second = memchr(after, '#', remaining);
                if (second) {
                    char const* between = after;
                    size_t between_length = (size_t)(second - after);
                    bool ok = true;
                    if (between_length && between[0] == '@') {
                        if (sharp == line)
                            ok = false;
                        ++between, --between_length;
                    }
                    if (between_length && between[0] == '?')
                        ++between, --between_length;
                    if (ok && between_length == 0)
                        return true;
                }
            }
        }
        line = end ? end + 1 : NULL;
    }
    return false;
}

/* Turns "a,b" into "a\nb\n" (the shape ContentBlocker::cosmetic_style_sheet_for_url passes), "-" into "". */
static char* lines_from_list(char const* list)
{
    if (strcmp(list, "-") == 0)
        return strdup("");
    size_t length = strlen(list);
    char* lines = malloc(length + 2);
    for (size_t i = 0; i < length; ++i)
        lines[i] = list[i] == ',' ? '\n' : list[i];
    lines[length] = '\n';
    lines[length + 1] = '\0';
    return lines;
}

typedef struct {
    void* engine;
    bool has_cosmetic_rules;
} Engine;

static Engine engine_create(Buffer const* rules, double* seconds)
{
    double start = now_seconds();
    void* engine = rust_content_blocker_create((Span) { (uint8_t const*)rules->data, rules->size });
    if (seconds)
        *seconds = now_seconds() - start;
    return (Engine) { engine, rules_contain_cosmetic_rules(rules->data) };
}

static char* engine_css(Engine engine, char const* page_url, char const* classes, char const* ids)
{
    if (!engine.engine || !engine.has_cosmetic_rules)
        return strdup("");
    char* class_lines = lines_from_list(classes);
    char* id_lines = lines_from_list(ids);
    ContentBlockerString css = rust_content_blocker_cosmetic_css(engine.engine, span_of(page_url), span_of(class_lines), span_of(id_lines));
    free(class_lines);
    free(id_lines);
    char* result = malloc(css.length + 1);
    if (css.length)
        memcpy(result, css.data, css.length);
    result[css.length] = '\0';
    rust_content_blocker_free_string(css.data, css.length);
    return result;
}

static bool css_has_rule_for(char const* css, char const* selector)
{
    /* Rules are emitted one per line as "<selector> { <style>; }". */
    size_t selector_length = strlen(selector);
    for (char const* line = css; line && *line;) {
        char const* end = strchr(line, '\n');
        if (strncmp(line, selector, selector_length) == 0 && strncmp(line + selector_length, " { ", 3) == 0)
            return true;
        line = end ? end + 1 : NULL;
    }
    return false;
}

static int passed;
static int failed;

static void run_vector(Engine engine, char* line, char const* origin, int line_number)
{
    char* saveptr = NULL;
    char* verb = strtok_r(line, " \t", &saveptr);
    if (!verb)
        return;
    bool ok;
    if (strcmp(verb, "block") == 0 || strcmp(verb, "allow") == 0) {
        char* url = strtok_r(NULL, " \t", &saveptr);
        char* source = strtok_r(NULL, " \t", &saveptr);
        char* type = strtok_r(NULL, " \t", &saveptr);
        if (!url || !source || !type) {
            fprintf(stderr, "%s:%d: malformed vector\n", origin, line_number);
            ++failed;
            return;
        }
        bool blocked = engine.engine && rust_content_blocker_matches(engine.engine, span_of(url), span_of(source), span_of(type));
        ok = blocked == (verb[0] == 'b');
        printf("%s %s %s %s (from %s)\n", ok ? "PASS" : "FAIL", verb, type, url, source);
    } else if (strcmp(verb, "hide") == 0 || strcmp(verb, "show") == 0) {
        char* page = strtok_r(NULL, " \t", &saveptr);
        char* classes = strtok_r(NULL, " \t", &saveptr);
        char* ids = strtok_r(NULL, " \t", &saveptr);
        char* selector = saveptr;
        while (selector && (*selector == ' ' || *selector == '\t'))
            ++selector;
        if (!page || !classes || !ids || !selector || !*selector) {
            fprintf(stderr, "%s:%d: malformed vector\n", origin, line_number);
            ++failed;
            return;
        }
        char* css = engine_css(engine, page, classes, ids);
        bool present = css_has_rule_for(css, selector);
        free(css);
        ok = present == (verb[0] == 'h');
        printf("%s %s %s on %s (classes %s, ids %s)\n", ok ? "PASS" : "FAIL", verb, selector, page, classes, ids);
    } else {
        fprintf(stderr, "%s:%d: unknown verb '%s'\n", origin, line_number, verb);
        ++failed;
        return;
    }
    if (ok)
        ++passed;
    else
        ++failed;
}

static void strip_newline(char* line)
{
    size_t length = strlen(line);
    while (length && (line[length - 1] == '\n' || line[length - 1] == '\r'))
        line[--length] = '\0';
}

static void run_vectors(Engine engine, char const* path)
{
    FILE* file = fopen(path, "r");
    if (!file) {
        perror(path);
        exit(2);
    }
    char* line = NULL;
    size_t capacity = 0;
    int line_number = 0;
    Buffer inline_rules = { 0 };
    Engine inline_engine = { 0 };
    bool inline_engine_stale = false;
    while (getline(&line, &capacity, file) != -1) {
        ++line_number;
        strip_newline(line);
        char const* trimmed = line;
        while (*trimmed == ' ' || *trimmed == '\t')
            ++trimmed;
        if (!*trimmed || *trimmed == '#')
            continue;
        if (strncmp(trimmed, "rules ", 6) == 0) {
            if (!inline_engine_stale && inline_engine.engine) {
                /* A new inline block starts after vectors ran: begin a fresh list. */
                rust_content_blocker_free(inline_engine.engine);
                inline_engine.engine = NULL;
                inline_rules.size = 0;
            }
            buffer_append(&inline_rules, trimmed + 6, strlen(trimmed + 6));
            buffer_append(&inline_rules, "\n", 1);
            inline_engine_stale = true;
            continue;
        }
        if (inline_rules.size) {
            if (inline_engine_stale) {
                inline_engine = engine_create(&inline_rules, NULL);
                inline_engine_stale = false;
            }
            run_vector(inline_engine, line, path, line_number);
        } else {
            run_vector(engine, line, path, line_number);
        }
    }
    if (inline_engine.engine)
        rust_content_blocker_free(inline_engine.engine);
    free(inline_rules.data);
    free(line);
    fclose(file);
}

int main(int argc, char** argv)
{
    Buffer rules = { 0 };
    char const* vectors[64];
    int vector_count = 0;
    char const* css_page = NULL;
    char const* css_classes = NULL;
    char const* css_ids = NULL;
    int rule_files = 0;
    int repeat = 1;

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--rules") == 0 && i + 1 < argc) {
            buffer_append_file(&rules, argv[++i]);
            buffer_append(&rules, "\n", 1);
            ++rule_files;
        } else if (strcmp(argv[i], "--vectors") == 0 && i + 1 < argc && vector_count < 64) {
            vectors[vector_count++] = argv[++i];
        } else if (strcmp(argv[i], "--css") == 0 && i + 3 < argc) {
            css_page = argv[++i];
            css_classes = argv[++i];
            css_ids = argv[++i];
        } else if (strcmp(argv[i], "--repeat") == 0 && i + 1 < argc) {
            repeat = atoi(argv[++i]);
        } else {
            fprintf(stderr, "usage: %s [--rules FILE]... [--vectors FILE]... [--css PAGE_URL CLASSES IDS] [--repeat N]\n", argv[0]);
            return 2;
        }
    }
    /* The custom filters, which are empty here. */
    buffer_append(&rules, "\n", 1);

    Engine engine = { 0 };
    if (rule_files) {
        double best = 0;
        for (int i = 0; i < (repeat > 0 ? repeat : 1); ++i) {
            if (engine.engine)
                rust_content_blocker_free(engine.engine);
            double seconds = 0;
            engine = engine_create(&rules, &seconds);
            if (i == 0 || seconds < best)
                best = seconds;
        }
        if (!engine.engine) {
            fprintf(stderr, "FAIL the engine rejected the rules (rust_content_blocker_create returned null)\n");
            return 1;
        }
        printf("LOAD %d list(s), %.1f MiB, engine built in %.0f ms%s, cosmetic rules: %s\n", rule_files,
            (double)rules.size / (1024.0 * 1024.0), best * 1000.0, repeat > 1 ? " (best run)" : "",
            engine.has_cosmetic_rules ? "yes" : "no");
    }

    if (css_page) {
        char* css = engine_css(engine, css_page, css_classes, css_ids);
        fputs(css, stdout);
        free(css);
    }

    for (int i = 0; i < vector_count; ++i)
        run_vectors(engine, vectors[i]);

    if (vector_count)
        printf("%d passed, %d failed\n", passed, failed);

    if (engine.engine)
        rust_content_blocker_free(engine.engine);
    free(rules.data);
    return failed ? 1 : 0;
}
