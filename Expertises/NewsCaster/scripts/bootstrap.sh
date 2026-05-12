#!/bin/bash
# NewsCaster bootstrap — idempotent setup for nullevi daily digest Cloud Routine / manual runs.
#
# Use:
#   source Expertises/NewsCaster/scripts/bootstrap.sh    # exports HTTPLIB2_CA_CERTS into the parent shell
#   bash   Expertises/NewsCaster/scripts/bootstrap.sh    # installs only (env vars do not persist)
#
# Single source of truth for runtime deps: Expertises/NewsCaster/pyproject.toml [project] dependencies.
# Mirrors the BlueberrySprite bootstrap.sh pattern (L00467-era processed) with the SVG/font/X-client
# layers stripped — NewsCaster only ships Gmail HTTPS API.
#
# The two corrections preserved from BBS:
#   - debian-managed `cryptography 41.0.7` lacks a RECORD file, so `pip install --upgrade`
#     refuses; we retry with `--ignore-installed cffi cryptography` to bypass.
#   - httplib2 (pulled by google-api-python-client) does not honor REQUESTS_CA_BUNDLE /
#     SSL_CERT_FILE, so MITM-proxied harnesses fail TLS verification unless
#     HTTPLIB2_CA_CERTS points at the system CA bundle.

set -u

# Detect source vs exec so we can use `return` when sourced, `exit` when executed.
_nc_sourced=0
if [ "${BASH_SOURCE[0]:-}" != "${0:-}" ]; then
    _nc_sourced=1
fi

_nc_die() {
    echo "[newscaster-bootstrap] FAIL: $*" >&2
    if [ "$_nc_sourced" = "1" ]; then
        return 1
    else
        exit 1
    fi
}

_nc_log() { echo "[newscaster-bootstrap] $*"; }

# Resolve script dir robustly whether sourced or executed.
_nc_script_path="${BASH_SOURCE[0]:-$0}"
_nc_script_dir="$(cd "$(dirname "$_nc_script_path")" && pwd)"
_nc_pyproject_dir="$(cd "$_nc_script_dir/.." && pwd)"

if [ ! -f "$_nc_pyproject_dir/pyproject.toml" ]; then
    _nc_die "pyproject.toml not found at $_nc_pyproject_dir"
fi

# 1. Install runtime deps from pyproject.toml.
# Install the dependency list rather than the project itself: NewsCaster/ sits next to
# runtime data dirs (state/, scripts/tests/) and `pip install NewsCaster/` would hit
# setuptools flat-layout ambiguities. The codebase is run via
# `python scripts/main.py …` (pyproject.toml sets pythonpath=["scripts"] for pytest).
_nc_log "extracting runtime deps from pyproject.toml"
_nc_deps_file="$(mktemp)"
python - "$_nc_pyproject_dir/pyproject.toml" >"$_nc_deps_file" <<'PY' || _nc_die "pyproject.toml parse failed"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    data = tomllib.load(f)
for dep in data.get("project", {}).get("dependencies", []):
    print(dep)
PY

if [ ! -s "$_nc_deps_file" ]; then
    _nc_log "no runtime deps declared — skipping pip install"
else
    _nc_log "pip install -r <pyproject deps> ($(wc -l < "$_nc_deps_file") packages)"
    if ! pip install --quiet --upgrade -r "$_nc_deps_file" 2>/tmp/newscaster-bootstrap-pip.log; then
        _nc_log "first install failed — retrying with --ignore-installed for cffi/cryptography"
        cat /tmp/newscaster-bootstrap-pip.log >&2
        pip install --quiet --ignore-installed cffi cryptography \
            || _nc_die "cffi/cryptography reinstall failed"
        pip install --quiet --upgrade -r "$_nc_deps_file" \
            || _nc_die "deps install failed after cryptography fix"
    fi
fi
rm -f "$_nc_deps_file"

# 2. Defensive cryptography/cffi sanity check — even if step 1 succeeded, the debian
# build can leave a stale shared object that crashes at import time. Catch it here
# rather than at Gmail send time.
if ! python -c "import cryptography.exceptions" 2>/dev/null; then
    _nc_log "cryptography import broken — forcing reinstall of cffi + cryptography"
    pip install --quiet --ignore-installed cffi cryptography \
        || _nc_die "cffi/cryptography reinstall failed (import probe)"
fi

# 3. Verify the imports we actually rely on. Failing here surfaces the issue before
# validate-config / run hits it.
_nc_log "verifying imports"
python - <<'PY' || _nc_die "import verification failed"
import importlib.util, sys
required = [
    "googleapiclient",
    "google.auth",
    "google_auth_oauthlib",
    "cryptography",
]
missing = [m for m in required if importlib.util.find_spec(m) is None]
if missing:
    print("missing modules:", missing, file=sys.stderr)
    sys.exit(1)
PY

# 4. Export HTTPLIB2_CA_CERTS so httplib2 (Gmail API transport) trusts the system
# trust store. Only set when not already set, so operator overrides win.
if [ -z "${HTTPLIB2_CA_CERTS:-}" ]; then
    for _nc_ca in \
        /etc/ssl/certs/ca-certificates.crt \
        /etc/pki/tls/certs/ca-bundle.crt \
        /etc/ssl/cert.pem; do
        if [ -f "$_nc_ca" ]; then
            export HTTPLIB2_CA_CERTS="$_nc_ca"
            _nc_log "HTTPLIB2_CA_CERTS=$_nc_ca"
            break
        fi
    done
    if [ -z "${HTTPLIB2_CA_CERTS:-}" ]; then
        _nc_log "warn: no CA bundle found; Gmail HTTPS API may fail TLS verify"
    fi
else
    _nc_log "HTTPLIB2_CA_CERTS already set ($HTTPLIB2_CA_CERTS) — leaving as-is"
fi

_nc_log "ready"

unset _nc_sourced _nc_script_path _nc_script_dir _nc_pyproject_dir _nc_ca _nc_deps_file
unset -f _nc_die _nc_log
