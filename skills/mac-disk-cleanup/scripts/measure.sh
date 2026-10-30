#!/usr/bin/env bash
# Read-only baseline for a macOS disk cleanup run: which container is full,
# local snapshots, and sizes of the usual hotspots. Writes a report and prints it.
#   measure.sh <run-dir>
set -uo pipefail

run_dir=${1:?usage: measure.sh <run-dir>}
mkdir -p "$run_dir/reports"
report="$run_dir/reports/$(date +%Y%m%d-%H%M%S)-baseline.txt"

if ! command -v dust >/dev/null; then
  echo "dust not found: brew install dust (du is far slower on large homes)" >&2
  exit 1
fi

size() { # dust one level deep, biggest last; -x stays on this filesystem
  dust -x -d 1 -n "${2:-10}" -b -P "$1" 2>/dev/null | tail -n "$(( ${2:-10} + 1 ))"
}

{
  echo "# Disk baseline $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo
  echo "## APFS containers"
  diskutil apfs list | grep -E 'Container disk|Capacity In Use|Not Allocated|Volume disk|Name:|Consumed'
  echo
  echo "## Free space (df -k, Data volume)"
  df -k /System/Volumes/Data
  echo
  echo "## Local snapshots (hold deleted blocks until removed)"
  tmutil listlocalsnapshots / 2>&1
  echo
  echo "## Cleanups possibly already running"
  pgrep -fl 'uv cache|nix-collect-garbage|nix-store --gc|brew cleanup|npm cache|tmutil delete' | grep -v pgrep || echo "(none)"
  find "$HOME/disk-cleanup-tracker/runs" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -3
  echo
  echo "## Home"
  size "$HOME" 20
  for d in "$HOME/Library/Caches" "$HOME/Library/Application Support" "$HOME/.cache" \
           "$HOME/.local/share" "$HOME/Downloads"; do
    [ -d "$d" ] || continue
    echo; echo "## $d"; size "$d" 8
  done
  echo
  echo "## Outside home"
  dust -x -d 1 -n 10 -b /Applications /opt/homebrew /private/var 2>/dev/null | tail -12
} | tee "$report"

echo
echo "Report: $report"
