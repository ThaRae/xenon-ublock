// SPDX-License-Identifier: GPL-3.0-or-later
//
// Turns uBlock Origin's scriptlets and redirect resources into the resource list the `adblock` crate loads with
// Engine::use_resources(). The patched Ladybird content blocker (engine/) uses it for `##+js(...)` scriptlets and
// `$redirect=` surrogates.
//
// Usage: node tools/build_resources.mjs <uBlock source dir> <output.json> <uBlock version>
//
// Scriptlets come from src/js/resources/scriptlets.js, which registers every scriptlet and helper function with its
// name, aliases, dependencies and whether it needs a trusted list. Each becomes a resource holding the function's
// source: adblock calls a scriptlet with the filter's arguments and prepends the helpers it depends on. Scriptlets that
// uBO only lets trusted lists use get permission bit 0x01, which the patched engine grants to trusted lists only.
//
// Redirect resources come from src/js/redirect-resources.js and the files in src/web_accessible_resources/.

import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const TRUSTED_PERMISSION = 0x01;

const MIME_TYPES = {
    css: 'text/css',
    gif: 'image/gif',
    html: 'text/html',
    js: 'application/javascript',
    json: 'application/json',
    mp3: 'audio/mp3',
    mp4: 'video/mp4',
    png: 'image/png',
    txt: 'text/plain',
    xml: 'text/xml',
};

const [ uboDir, outputPath, uboVersion ] = process.argv.slice(2);
if ( !uboDir || !outputPath || !uboVersion ) {
    console.error('usage: node tools/build_resources.mjs <uBlock source dir> <output.json> <uBlock version>');
    process.exit(2);
}

const base64 = data => Buffer.from(data).toString('base64');
const resources = [];
const names = new Set();

function add(resource) {
    for ( const name of [ resource.name, ...resource.aliases ] ) {
        if ( names.has(name) ) {
            throw new Error(`duplicate resource name ${name}`);
        }
        names.add(name);
    }
    resources.push(resource);
}

// Scriptlets and their helpers.
const scriptletsModule = path.join(uboDir, 'src', 'js', 'resources', 'scriptlets.js');
const { builtinScriptlets } = await import(pathToFileURL(scriptletsModule).href);
for ( const scriptlet of builtinScriptlets ) {
    const source = scriptlet.fn.toString();
    // adblock calls a scriptlet (*.js) by the name in its `function NAME(` declaration. Helpers (*.fn) are only
    // prepended as dependencies, so they may also be classes or async functions.
    if ( scriptlet.name.endsWith('.js') && /^function\s+[^\s(){}]+\s*\(/.test(source) === false ) {
        throw new Error(`${scriptlet.name}: not a named function declaration`);
    }
    // adblock injects `application/javascript` resources for `+js(...)` (calling a function-style one by name), and
    // only prepends `fn/javascript` ones as dependencies, so scriptlets and helpers get different types.
    const resource = {
        name: scriptlet.name,
        aliases: scriptlet.aliases ?? [],
        kind: { mime: scriptlet.name.endsWith('.js') ? 'application/javascript' : 'fn/javascript' },
        content: base64(source),
    };
    if ( Array.isArray(scriptlet.dependencies) && scriptlet.dependencies.length !== 0 ) {
        resource.dependencies = scriptlet.dependencies;
    }
    if ( scriptlet.requiresTrust ) {
        resource.permission = TRUSTED_PERMISSION;
    }
    add(resource);
}
const scriptletCount = resources.length;

// Redirect resources. A few share a name with a scriptlet (uBO keeps them in separate maps); the scriptlet wins,
// since adblock looks both up by name, and redirects to those names are not used by uBO's lists.
const redirectsModule = path.join(uboDir, 'src', 'js', 'redirect-resources.js');
const { default: redirectResources } = await import(pathToFileURL(redirectsModule).href);
const skipped = [];
for ( const [ name, details ] of redirectResources ) {
    const file = path.join(uboDir, 'src', 'web_accessible_resources', name);
    if ( fs.existsSync(file) === false ) {
        skipped.push(`${name} (no file)`);
        continue;
    }
    const aliases = [ details.alias ?? [] ].flat().filter(alias => names.has(alias) === false);
    if ( names.has(name) ) {
        skipped.push(`${name} (a scriptlet has that name)`);
        continue;
    }
    const extension = path.extname(name).slice(1);
    add({
        name,
        aliases,
        kind: { mime: MIME_TYPES[extension] ?? 'text/plain' },
        content: base64(fs.readFileSync(file)),
    });
}

fs.writeFileSync(outputPath, JSON.stringify(resources) + '\n');
console.log(
    `uBlock Origin ${uboVersion}: ${scriptletCount} scriptlets and helpers, ` +
    `${resources.length - scriptletCount} redirect resources` +
    (skipped.length !== 0 ? `; skipped ${skipped.join(', ')}` : '')
);
