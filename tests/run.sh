#!/usr/bin/env bash
# Viewer test suite entrypoint.
#
# 1. Copies the repo into a temp serving dir (outside the repo) and rewires
#    the copy for local testing: BASE_URL -> the local test origin, a test
#    manifest under manifests/9999-test/, and an image_to_volume.json entry
#    mapping the fake image ID 9990001 to it.
# 2. Starts server.py (static files + fake IIIF image service + delay control).
# 3. Runs the Playwright suite (run_tests.js).
# 4. Cleans up server + temp dir; exits non-zero on any failure.
#
# Env:
#   TEST_PORT          port for the local server (default 8765)
#   PW_CHROMIUM_PATH   path to a Chromium binary (else CHROMIUM_BIN, else
#                      Playwright's own installed browser)
#   NODE_PATH          only needed if playwright is provided globally rather
#                      than installed in tests/ (see tests/README.md)
set -euo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$TESTS_DIR")"
PORT="${TEST_PORT:-8765}"
ORIGIN="http://127.0.0.1:${PORT}"

# Fail fast with a useful message if playwright isn't resolvable. Resolve
# from TESTS_DIR (same as run_tests.js will) so tests/node_modules counts.
if ! (cd "$TESTS_DIR" && node -e "require('playwright')") 2>/dev/null; then
  echo "ERROR: cannot require('playwright')." >&2
  echo "Run 'npm install' in tests/, or set NODE_PATH to a global install (see tests/README.md)." >&2
  exit 1
fi

SERVE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/green-books-viewer-tests.XXXXXX")"
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$SERVE_DIR"
}
trap cleanup EXIT

echo "Building serving copy in $SERVE_DIR/site ..."
mkdir -p "$SERVE_DIR/site"
# Copy the working tree (not a git export) so uncommitted changes are tested.
(cd "$REPO_DIR" && tar --exclude=.git --exclude=tests --exclude=node_modules -cf - .) \
  | tar -xf - -C "$SERVE_DIR/site"

# Rewire the copy for the local origin.
python3 - "$SERVE_DIR/site" "$ORIGIN" "$TESTS_DIR" << 'PYEOF'
import json, os, sys
site, origin, tests_dir = sys.argv[1], sys.argv[2], sys.argv[3]

# 1. BASE_URL -> local origin. viewer.html computes BASE_URL host-relatively
# (a ternary spanning several lines); replace the whole statement with an
# explicit local-origin constant so the test drives a known value.
viewer_path = os.path.join(site, "viewer.html")
text = open(viewer_path, encoding="utf-8").read()
needle = ('const BASE_URL = location.hostname === "hadro.github.io"\n'
          '  ? "https://hadro.github.io/green-books"\n'
          '  : new URL(".", location.href).href.replace(/\\/$/, "");')
assert needle in text, "BASE_URL statement not found in viewer.html — update tests/run.sh"
open(viewer_path, "w", encoding="utf-8").write(
    text.replace(needle, 'const BASE_URL = "%s";' % origin))

# 2. Test manifest from the fixture template
tpl = open(os.path.join(tests_dir, "fixtures", "manifest.template.json"), encoding="utf-8").read()
manifest_dir = os.path.join(site, "manifests", "9999-test")
os.makedirs(manifest_dir, exist_ok=True)
open(os.path.join(manifest_dir, "manifest.json"), "w", encoding="utf-8").write(
    tpl.replace("__ORIGIN__", origin))

# 3. Lookup entry: fake image ID -> test volume
lookup_path = os.path.join(site, "image_to_volume.json")
lookup = json.load(open(lookup_path))
lookup["9990001"] = "9999-test"
json.dump(lookup, open(lookup_path, "w"))

print("serving copy rewired for", origin)
PYEOF

echo "Starting server on port $PORT ..."
python3 "$TESTS_DIR/server.py" "$SERVE_DIR/site" "$PORT" > "$SERVE_DIR/server.log" 2>&1 &
SERVER_PID=$!

# Wait for the server to accept requests.
for i in $(seq 1 50); do
  if curl -sf -o /dev/null "$ORIGIN/viewer.html"; then break; fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR: server exited early; log follows:" >&2
    cat "$SERVE_DIR/server.log" >&2
    exit 1
  fi
  sleep 0.2
done
curl -sf -o /dev/null "$ORIGIN/viewer.html" || { echo "ERROR: server never came up" >&2; exit 1; }

echo "Running Playwright suite ..."
TEST_PORT="$PORT" node "$TESTS_DIR/run_tests.js"
