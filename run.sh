#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export LD_LIBRARY_PATH="$DIR/bin:$LD_LIBRARY_PATH"

exec python3 "$DIR/layzee.py" "$@"
