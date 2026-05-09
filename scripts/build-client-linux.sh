#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="lanpulse-client-builder"

docker build -f "$ROOT_DIR/client/Dockerfile.bundle" -t "$IMAGE_NAME" "$ROOT_DIR"

docker run --rm \
  -v "$ROOT_DIR/client:/workspace/client" \
  -v "$ROOT_DIR/downloads:/workspace/downloads" \
  "$IMAGE_NAME" \
  bash -lc '
    set -euo pipefail
    npm ci
    npx tauri build --bundles appimage
    artifact="$(find src-tauri/target/release/bundle/appimage -maxdepth 1 -name "*.AppImage" | head -n 1)"
    cp "$artifact" /workspace/downloads/client-latest-linux.AppImage
  '

printf "Linux client bundle copied to %s/downloads/client-latest-linux.AppImage\n" "$ROOT_DIR"
