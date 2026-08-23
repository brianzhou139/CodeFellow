#!/usr/bin/env bash
# Download the public CPU-int8 NLLB translator used by the Kiswahili lane.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRANSLATION_DIR="$HERE/translation/nllb-200-distilled-600M-ct2-int8"
BASE_URL="https://huggingface.co/mijuanlo/nllb-200-distilled-600M-ct2-int8/resolve/main"

declare -A SHA256=(
    [model.bin]="398726640cc2a02cc6a35277fa3cf2159ce8a1a66b48aa1b6c8837a47e3dd00c"
    [config.json]="bf8ade7c3f1683e5f13001bab18b04a1ccd1a6801208efd227ed13b2ff6f15e7"
    [shared_vocabulary.json]="af53bfd0e6f726209e7325e45b87ab3b14e5856f7d42d7b9be91de3287c45267"
    [sentencepiece.bpe.model]="14bb8dfb35c0ffdea7bc01e56cea38b9e3d5efcdcb9c251d6b40538e1aab555a"
)

mkdir -p "$TRANSLATION_DIR"

download_file() {
    local name="$1"
    local target="$TRANSLATION_DIR/$name"
    local partial="$target.partial"
    if [[ -f "$target" ]] && printf '%s  %s\n' "${SHA256[$name]}" "$target" | sha256sum --check --status; then
        echo "verified translator file: $name"
        return
    fi
    if command -v curl >/dev/null 2>&1; then
        curl --location --fail --retry 5 --retry-delay 2 --retry-all-errors \
            --continue-at - --output "$partial" "$BASE_URL/$name"
    elif command -v wget >/dev/null 2>&1; then
        wget --continue --output-document="$partial" "$BASE_URL/$name"
    else
        echo "error: install curl or wget to download the translator" >&2
        exit 1
    fi
    printf '%s  %s\n' "${SHA256[$name]}" "$partial" | sha256sum --check --status || {
        echo "error: checksum failed for $name" >&2
        rm -f -- "$partial"
        exit 1
    }
    mv -f -- "$partial" "$target"
}

for file in config.json model.bin sentencepiece.bpe.model shared_vocabulary.json; do
    download_file "$file"
done

echo "verified offline Kiswahili translator ready: $TRANSLATION_DIR"
