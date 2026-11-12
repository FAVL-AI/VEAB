#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
sha256sum -c docs/scenario-contract-sha256.txt
