# Previewing and building the SMS documentation

## Current GitHub Pages site

The current site is static and needs no build step. From the repository root, serve
it locally with any static HTTP server, for example:

```sh
python -m http.server 8000 --directory docs
```

Then open <http://localhost:8000/>.

Regenerate the client-side search index after changing page text or headings:

```sh
node tools/build-docs-search-index.mjs
```

GitHub Pages publishes the same `/docs` files from `master`, so the local preview is
the deployed structure. Do not preview with `file://`; the browser may block the
search index request.

## Archived DocBook manual

`docs/src/`, `docs/Makefile` and `docs/configure` belong to the historic upstream
DocBook documentation system. They are preserved for provenance and are not used to
produce the current site. Its former generated `docs/HTML/` and `docs/HTML-single/`
directories are not committed here.

If you intentionally need to rebuild that archive, its legacy makefiles expect GNU
make, `xmllint`, `xsltproc`, the DocBook XML DTD and DocBook XSL stylesheets. Run
`make help` inside `docs/` for its old targets. Changes there must not be presented
as current-site updates unless the top-level static HTML is updated separately.
