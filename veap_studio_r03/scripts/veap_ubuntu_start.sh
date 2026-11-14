#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${VEAP_STUDIO_DATA:=$HOME/veap-studio-data}"
export VEAP_STUDIO_DATA
if ! python3 -c 'import fastapi,uvicorn,multipart,PIL' >/dev/null 2>&1;then
 echo "Install dependencies in an isolated environment: python3 -m pip install -e ."
 exit 2
fi
echo "VEAP local-only pilot at http://127.0.0.1:8765"
exec python3 -m uvicorn veap_studio.api:app --host 127.0.0.1 --port 8765
