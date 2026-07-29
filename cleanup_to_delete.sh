#!/usr/bin/env bash
#
# Cleans up _to_delete/. Cowork's device bridge can only write/overwrite
# files on your machine, never delete them -- so the push pattern used
# throughout this project's history has been: copy the real content of a
# file into _to_delete/, then blank out the original in place. That leaves
# two things behind for every entry: the real bytes in _to_delete/, and a
# 0-byte stub with the same name sitting wherever the original lived.
#
# For each file in _to_delete/, this script finds any other file in the
# repo with the same name (the emptied stub) and deletes it, then removes
# the real copy from _to_delete/ too -- leaving the folder itself intact
# and empty, ready for next time.
#
# Run it from anywhere; it resolves its own location and operates relative
# to that, not your current working directory.
#
# Usage: ./cleanup_to_delete.sh

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"

if [ ! -d _to_delete ]; then
  echo "No _to_delete/ directory found in $root -- nothing to do."
  exit 0
fi

shopt -s nullglob
found_any=false
for f in _to_delete/*; do
  found_any=true
  name="$(basename "$f")"
  find . -type f -name "$name" -not -path "./_to_delete/*" -delete
  rm -f "$f"
  echo "cleaned: $name"
done

if [ "$found_any" = false ]; then
  echo "_to_delete/ is already empty -- nothing to do."
else
  echo "done."
fi
