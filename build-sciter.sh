#!/usr/bin/env bash
# Build the Lekuvo Sciter host against the vendored GTK runtime.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
gcc -std=c11 -O2 -DINT_PTR=intptr_t -D_DEFAULT_SOURCE -DSTATIC_LIB \
    "$DIR/src/sciter_host.c" -I"$DIR/bin/sciter/include" \
    $(pkg-config --cflags --libs gtk+-3.0) \
    -L"$DIR/bin/sciter" -lsciter-gtk -ldl -lm \
    -Wl,-rpath,'$ORIGIN/sciter' \
    -o "$DIR/bin/sciter-lekuvo"
echo "built bin/sciter-lekuvo"
