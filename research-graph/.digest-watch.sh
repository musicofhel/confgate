#!/usr/bin/env bash
# Watch confgate triage workers; report each brief as it lands with the paper's
# real wall-clock duration (worker process start -> brief mtime). Exits as soon
# as at least one NEW brief is reported (so the parent gets re-invoked to ping),
# or when the dispatcher is fully done, or after a generous safety cap.
set -uo pipefail
cd "$(dirname "$0")"

DAY="$(date +%Y-%m-%d)"
BRIEF_DIR="briefs"
STARTS=".digest-starts"        # "id epoch" — when each worker process started
REPORTED=".digest-reported"    # ids already announced
touch "$STARTS" "$REPORTED"

# Dispatcher start = fallback for any worker that finished before we recorded it.
DISP_START="$(for p in $(pgrep -f 'triage_pending\.sh' 2>/dev/null); do stat -c %Y "/proc/$p" 2>/dev/null; done | sort -n | head -1)"
[ -n "$DISP_START" ] || DISP_START="$(awk 'NR==1||$2<m{m=$2}END{print m}' "$STARTS" 2>/dev/null)"

seed_starts() {
  for pid in $(pgrep -f 'bash triage_one\.sh' 2>/dev/null); do
    id="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | awk '{print $3}')"
    # only real arxiv ids (NNNN.NNNNN) — skips xargs's "-P" etc.
    [[ "$id" =~ ^[0-9]{4}\.[0-9]{4,5}$ ]] || continue
    grep -q "^$id " "$STARTS" 2>/dev/null || echo "$id $(stat -c %Y "/proc/$pid" 2>/dev/null)" >> "$STARTS"
  done
}

fmt() { printf '%dm%02ds' $(( $1 / 60 )) $(( $1 % 60 )); }

MAX=$(( 40 * 60 )); waited=0
while :; do
  seed_starts
  new=0
  for f in "$BRIEF_DIR"/triage-"$DAY"-*.md; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .md)"; id="${base#triage-$DAY-}"
    grep -qx "$id" "$REPORTED" 2>/dev/null && continue
    start="$(awk -v i="$id" '$1==i{print $2}' "$STARTS")"
    [ -n "$start" ] || start="$DISP_START"
    end="$(stat -c %Y "$f")"
    if [ -n "$start" ]; then dur="$(fmt $(( end - start )))"; else dur="unknown"; fi
    echo "DONE $id $dur"
    echo "$id" >> "$REPORTED"
    new=1
  done
  [ "$new" -eq 1 ] && exit 0

  # Dispatcher and all workers gone? Nothing more will land.
  if ! pgrep -f 'triage_pending\.sh' >/dev/null 2>&1 && ! pgrep -f 'bash triage_one\.sh' >/dev/null 2>&1; then
    echo "DISPATCHER_DONE"; exit 0
  fi
  sleep 20; waited=$(( waited + 20 ))
  [ "$waited" -ge "$MAX" ] && { echo "WATCH_TIMEOUT"; exit 0; }
done
