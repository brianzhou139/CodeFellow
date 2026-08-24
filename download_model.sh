#!/usr/bin/env bash
# Download the public CodeFellow model artifact without credentials.
# Safe to run repeatedly; completed weights are verified before reuse.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$HERE/model"
MODEL_FILE="$MODEL_DIR/CodeFellow-Q4_K_M.gguf"
PARTIAL_FILE="$MODEL_FILE.partial"

# CodeFellow's selected step-100, 0.45-strength, importance-matrix Q4_K_M
# derivative. The public artifact is checksum-pinned for reproducible audits.
MODEL_URL="https://github.com/brianzhou139/CodeFellow/releases/download/gate1-v1/CodeFellow-3B-Kiswahili-Instruct-Q4_K_M.gguf"
MODEL_SHA256="50177433b86f9fdcd0161a89bdfdf0ec2819b396e9987bee5d743b3e9e822ea5"

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
        --out="$(basename "$PARTIAL_FILE")" \
        "$MODEL_URL"
elif command -v curl >/dev/null 2>&1; then
    curl \
        --location \
        --fail \
        --retry 5 \
        --retry-delay 2 \
        --retry-all-errors \
        --continue-at - \
        --output "$PARTIAL_FILE" \
        "$MODEL_URL"
elif command -v wget >/dev/null 2>&1; then
    wget \
        --continue \
        --output-document="$PARTIAL_FILE" \
        "$MODEL_URL"
else
    echo "error: install aria2c, curl, or wget to download the model" >&2
    exit 1
fi

if ! verify_model "$PARTIAL_FILE"; then
    echo "error: downloaded model failed SHA-256 verification" >&2
    rm -f -- "$PARTIAL_FILE"
    exit 1
fi

mv -f -- "$PARTIAL_FILE" "$MODEL_FILE"
echo "verified model ready: $MODEL_FILE"
