# Maintaining the SMS documentation

## Current source of truth

The current English manual is the hand-authored static site in `docs/*.html`.
Shared styling and behavior live under `docs/assets/`, images under `docs/images/`,
and search data in `docs/data/search-index.json`.

GitHub Pages publishes the `/docs` folder from the repository's `master` branch at
<https://nathanneurotic.github.io/Simple-Media-System/>.

The old DocBook sources under `docs/src/` are retained as a historical reference;
their former generated HTML directories are not committed. Editing those XML files
does not update the current site.

## Update workflow

1. Edit the relevant top-level HTML page and the root `README.md` when the same
   user-facing fact appears there.
2. Keep claims separated by evidence level:
   - source-accepted formats and hard limits;
   - hardware-confirmed profiles from `tools/gen-test-media.sh`;
   - performance guidance, which is content and storage dependent.
3. If a page or section changes, regenerate `docs/data/search-index.json`:

   ```sh
   node tools/build-docs-search-index.mjs
   ```

4. Preview the site locally and test its links as described in
   [`README.buildingdocumentation.md`](README.buildingdocumentation.md).
5. Run `git diff --check` and confirm a second search-index generation produces no
   diff.

When adding a top-level page, add it to the sidebar on every current top-level HTML
page, give each searchable `h2`/`h3` a stable `id`, and add a category mapping to the
search-index generator.

## Accuracy anchors

- Decoder registration and FourCC support: `src/SMS_Codec.c`
- File-extension routing: `src/SMS_FileDir.c`
- Player/container limits: `src/SMS_Player.c`, `src/SMS_Container.c`,
  `include/SMS_Container.h`, `include/SMS_FileContext.h`
- Audio behavior: `src/SMS_AAC.c`, `src/SMS_ContainerFLAC.c`,
  `src/SMS_ContainerOGG.c`
- Network/device behavior: `src/SMS_IOP.c`, `src/SMS_GUIMenuSMS.c`,
  `iop/SMSUdpfs/ATTRIBUTION.md`
- Repeatable media fixtures: `tools/gen-test-media.sh`
- Current published binaries and hashes: the GitHub release page

Do not turn a source-only capability into a hardware-tested claim. Conversely, keep
the exact tested encoding parameters when documenting the fixture matrix; a
container or codec name alone does not describe the tested workload.
