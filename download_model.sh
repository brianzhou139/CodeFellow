#!/usr/bin/env bash
# Download the public CodeFellow model artifact without credentials.
# Safe to run repeatedly; completed weights are verified before reuse.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$HERE/model"
MODEL_FILE="$MODEL_DIR/CodeFellow-qlora250-s100-Q4_K_M.gguf"
ARCHIVE_FILE="$MODEL_DIR/CodeFellow-qlora250-s100-Q4_K_M.tgz.partial"

# CodeFellow Gate 2 provisional selected 250-step QLoRA Q4_K_M artifact.
# Keep this URL as a literal public URL for static audit verification.
MODEL_URL="https://github.com/brianzhou139/CodeFellow/releases/download/gate2-v2/CodeFellow-qlora250-s100-Q4_K_M.tgz"
MODEL_SHA256="92ae1b93b4248fec6efccc6fee0e83e1b4b0cb883ce740ab3d03a490c2647cb2"

verify_model() {
    printf '%s  %s\n' "$MODEL_SHA256" "$1" | sha256sum --check --status
}

mkdir -p "$MODEL_DIR"

if [[ -f "$MODEL_FILE" ]]; then
    if verify_model "$MODEL_FILE"; then
        echo "verified model already present: $MODEL_FILE"
        exit 0
    fi
    echo "error: existing model has the wrong SHA-256: $MODEL_FILE" >&2
    echo "remove that file explicitly, then run this script again" >&2
    exit 1
fi

echo "downloading the public CodeFellow model (about 1.8 GiB)"

if command -v aria2c >/dev/null 2>&1; then
    aria2c \
        --continue=true \
        --allow-overwrite=true \
        --auto-file-renaming=false \
        --file-allocation=none \
        --max-connection-per-server=8 \
        --split=8 \
        --dir="$MODEL_DIR" \
        --out="$(basename "$ARCHIVE_FILE")" \
        "$MODEL_URL"
elif command -v curl >/dev/null 2>&1; then
    curl \
        --location \
        --fail \
        --retry 5 \
        --retry-delay 2 \
        --retry-all-errors \
        --continue-at - \
        --output "$ARCHIVE_FILE" \
        "$MODEL_URL"
elif command -v wget >/dev/null 2>&1; then
    wget \
        --continue \
        --output-document="$ARCHIVE_FILE" \
        "$MODEL_URL"
else
    echo "error: install aria2c, curl, or wget to download the model" >&2
    exit 1
fi

tar -xf "$ARCHIVE_FILE" -C "$MODEL_DIR"
rm -f -- "$ARCHIVE_FILE"

if ! verify_model "$MODEL_FILE"; then
    echo "error: extracted model failed SHA-256 verification" >&2
    rm -f -- "$MODEL_FILE"
    exit 1
fi

echo "verified model ready: $MODEL_FILE"
