#!/bin/bash
# Builds the Linux package from clean clones of the committed app and engine, inside WSL.
#   wsl -d Ubuntu-24.04 -- bash pack/build-linux.sh <engine branch>
# Needs cargo, zig and cargo-zigbuild, and the PDFium folder (not in git) beside this script.
# The result is copied to target/remedy/dist-linux/ on the Windows side; sign it there.
set -euo pipefail
source ~/.cargo/env 2>/dev/null || true
export PATH="$HOME/.cargo/bin:$HOME/.local/zig-0.16.0:$PATH"
app="$(cd "$(dirname "$0")/.." && pwd)"
users="$(cd "$app/../.." && pwd)"
engine_branch="${1:-main}"
work="$HOME/remedypdf-build"
rm -rf "$work/RemedyPDF" "$work/Projects/RemedyUI"
mkdir -p "$work/Projects"
git clone -q --depth 1 --branch "$engine_branch" "file://$users/Projects/RemedyUI" "$work/Projects/RemedyUI"
git clone -q --depth 1 --branch "$(git -C "$app" rev-parse --abbrev-ref HEAD)" "file://$(dirname "$app")" "$work/RemedyPDF"
cp -r "$app/pdfium" "$work/RemedyPDF/remedyui/pdfium"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-6}"
export CARGO_TARGET_DIR="$work/target-engine"
cargo build -q --release -p cargo-remedy --manifest-path "$work/Projects/RemedyUI/Cargo.toml"
export CARGO_TARGET_DIR="$work/target-app"
cd "$work/RemedyPDF/remedyui"
python3 pack/notices.py | cut -c1-100
"$work/target-engine/release/cargo-remedy" remedy package --target linux
mkdir -p "$app/target/remedy/dist-linux"
cp "$CARGO_TARGET_DIR"/remedy/dist/*linux* "$app/target/remedy/dist-linux/"
ls -l "$app/target/remedy/dist-linux/"
