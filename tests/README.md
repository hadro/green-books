# Viewer tests

End-to-end tests for the Clover IIIF viewer integration in `index.html` — the
content-state deep-link flow ("zoom to segment"), the info-panel open/close
driver, and the viewer chrome options.

## What the suite does

`run.sh`:

1. Copies the repo working tree to a temp dir (outside the repo) and rewires
   the copy: `BASE_URL` → the local test origin, a synthetic IIIF Presentation
   3 manifest at `manifests/9999-test/manifest.json` (from
   `fixtures/manifest.template.json`), and an `image_to_volume.json` entry
   mapping fake image ID `9990001` to it.
2. Starts `server.py`: static file server for the copy **plus** a fake IIIF
   Image API v2 level-0 service at `/iiif/2/9990001/` (test images are
   synthesized at any requested size — there is no static image fixture) and
   a `GET /_control/delay?ms=N` endpoint that delays every image-service
   response, simulating a cold/slow NYPL load.
3. Runs `run_tests.js` (Playwright, headless Chromium): four scenarios on
   fresh browser contexts — desktop (1280×800) and mobile (400×800), each
   fast and slow (7 s per image-service response; the slow cases are the
   regression tests for the historical "zoom doesn't happen on cold loads"
   bug).
4. Exits non-zero if any assertion fails; cleans up server + temp dir.

Assertions per case (subset varies): the content-state overlay ends up
substantial and centered in the viewer (the observable zoom signal), the info
panel is auto-closed, the `gb-zoom-pending` flash-suppression class is added
and later cleared (in slow cases: the aside's computed opacity is verified to
be 0 for the whole pending window), no ghost annotation label, no download
button / IIIF badge, header subtitle injection works, and no page errors.

## Running locally

```sh
cd tests
npm install                                  # installs pinned playwright
npx playwright install --with-deps chromium  # once, downloads the browser
./run.sh
```

Environment overrides:

| Variable | Meaning |
|---|---|
| `TEST_PORT` | Local server port (default `8765`) |
| `PW_CHROMIUM_PATH` (or `CHROMIUM_BIN`) | Path to a Chromium binary; skips Playwright's own browser download |
| `NODE_PATH` | Only needed when `playwright` comes from a global install instead of `tests/node_modules` |

Example against a pre-provisioned environment (no npm install), e.g. a
sandbox with a global Playwright and system Chromium:

```sh
NODE_PATH=/opt/node22/lib/node_modules \
PW_CHROMIUM_PATH=/opt/pw-browsers/chromium \
tests/run.sh
```

## Matcher unit tests

`tests/matching_test.js` covers `gb-matching.js` — the address-signature
resolver behind "Also listed in" and the cross-edition timeline. Plain Node, no
dependencies, no server:

```sh
node tests/matching_test.js
```

It pins the address-parsing invariants (trailing directionals must not change a
signature; streets *named* for a direction keep their name; ordinals canonicalize;
frontage ranges expand but ordinals don't) and grouping on the A. G. Gaston Motel
rows, which is what caught the trailing-directional bug.

## CI

`.github/workflows/viewer-tests.yml` runs `tests/run.sh` on pushes and PRs
that touch `index.html`, `clover.umd-*.js`, or `tests/**`.

`.github/workflows/matcher-tests.yml` runs `tests/matching_test.js` on pushes
and PRs that touch `gb-matching.js` or the test itself. Separate workflow
because it needs no browser and finishes in about a second — and because the
viewer workflow's path filter never mentioned `gb-matching.js`, so matcher
changes previously ran no CI at all.
