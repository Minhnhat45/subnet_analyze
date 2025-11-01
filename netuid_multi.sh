#!/usr/bin/env bash

set -euo pipefail          # safer bash: fail fast on errors
mkdir -p netuid_data       # create output directory if it doesn't exist

JOBS=10                    # number of simultaneous workers

# feed 1‒128 to xargs; -P$JOBS caps concurrency at 10
seq 1 128 | xargs -n1 -P"$JOBS" -I{} bash -c '
  netuid="$1"
  outfile="netuid_data/${netuid}.json"

  echo "Fetching netuid ${netuid} …"
  if btcli s show --json-out --netuid "$netuid" > "$outfile"; then
    echo "  ✓ Saved to ${outfile}"
  else
    echo "  ✗ Failed for netuid ${netuid}" >&2
  fi
' _ {}                      # “_” is $0 inside the subshell, {} becomes $1

