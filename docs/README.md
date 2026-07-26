# SMS documentation

The current user manual is the static site in this directory:

- Live site: <https://nathanneurotic.github.io/Simple-Media-System/>
- Deployment source: the repository's `master` branch, `/docs` folder
- Entry page: [`index.html`](index.html)

GitHub Pages serves these HTML, CSS, JavaScript, image and data files directly. No
Jekyll or DocBook build is required for the current site.

The files under `src/` preserve the historic upstream DocBook source. The
`legacy-manual.html` page records which legacy material is actually present, including
the retained `pitrz/` MPEG-2 encoding guide. The former English, Portuguese and Russian
generated manual directories are not part of this repository.

See:

- [`README.maintainers.md`](README.maintainers.md) to update or validate the site.
- [`README.buildingdocumentation.md`](README.buildingdocumentation.md) to preview it
  locally or work with the archived DocBook manual.
