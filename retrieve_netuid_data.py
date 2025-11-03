#!/usr/bin/env python3
import argparse
import sys
import time
import json
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
from threading import Lock

PRINT_LOCK = Lock()

def log(msg: str, *, err: bool = False) -> None:
    with PRINT_LOCK:
        print(msg, file=sys.stderr if err else sys.stdout, flush=True)

def is_empty_payload(s: str) -> bool:
    if not s or not s.strip():
        return True
    try:
        data = json.loads(s)
        if data is None:
            return True
        if isinstance(data, (list, dict)) and len(data) == 0:
            return True
    except json.JSONDecodeError:
        # Non-JSON but non-blank: treat as non-empty
        return False
    return False

def run_btcli_once(netuid: int, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["btcli", "s", "show", "--json-out", "--netuid", str(netuid)],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )

class RateLimiter:
    """Simple global QPS limiter that works across threads."""
    def __init__(self, qps: float):
        self.qps = float(qps)
        self._lock = Lock()
        self._next = 0.0  # monotonic seconds when next call is allowed

    def acquire(self, jitter: float = 0.15):
        if self.qps <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            slot = (self._next if now < self._next else now) + 1.0 / self.qps
            self._next = slot
        if wait > 0:
            time.sleep(wait + random.uniform(0.0, jitter))

def fetch_one(netuid: int, outdir: Path, retries: int, backoff_base: float,
              timeout: float, limiter: RateLimiter) -> bool:
    outfile = outdir / f"{netuid}.json"

    for attempt in range(1, retries + 1):
        limiter.acquire()
        tag = f"[attempt {attempt}/{retries}]"
        log(f"Fetching netuid {netuid} … {tag}")

        try:
            proc = run_btcli_once(netuid, timeout=timeout)
        except subprocess.TimeoutExpired:
            log(f"  ✗ Failed for netuid {netuid}: timeout {tag}", err=True)
            proc = None
        except FileNotFoundError:
            log(f"  ✗ btcli not found in PATH {tag}", err=True)
            return False
        except Exception as e:
            log(f"  ✗ Failed for netuid {netuid}: {e} {tag}", err=True)
            proc = None

        if proc and proc.returncode == 0 and not is_empty_payload(proc.stdout):
            try:
                outfile.write_text(proc.stdout)
                log(f"  ✓ Saved to {outfile}")
                return True
            except Exception as e:
                log(f"  ✗ Failed to write {outfile}: {e} {tag}", err=True)
                # fall through to retry

        else:
            if proc is None:
                err_msg = "no process (timeout/exception)"
            elif proc.returncode != 0:
                err_text = (proc.stderr or "").strip()
                err_msg = err_text if err_text else f"exit code {proc.returncode}"
            else:
                err_msg = "empty response"
            log(f"  ✗ Failed for netuid {netuid}: {err_msg} {tag}", err=True)

        if attempt < retries:
            # exponential backoff + small jitter
            sleep_s = backoff_base * (2 ** (attempt - 1)) + random.uniform(0.0, 0.25)
            time.sleep(sleep_s)

    return False

def maybe_discover_netuids() -> list[int] | None:
    """
    Try to discover existing netuids so we don't query non-existent ones.
    Returns list of ints or None if discovery fails.
    This is defensive: it tries to accept a few plausible JSON shapes.
    """
    try:
        proc = subprocess.run(
            ["btcli", "s", "list", "--json-out"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if proc.returncode != 0 or is_empty_payload(proc.stdout):
            return None
        data = json.loads(proc.stdout)

        # Accept a few shapes:
        #  - list of objects with key 'netuid'
        #  - dict with key 'subnets' -> list with 'netuid'
        #  - flat list of ints
        candidates: set[int] = set()
        def harvest(obj):
            if isinstance(obj, dict):
                if "netuid" in obj and isinstance(obj["netuid"], int):
                    candidates.add(int(obj["netuid"]))
                for v in obj.values():
                    harvest(v)
            elif isinstance(obj, list):
                for v in obj:
                    harvest(v)
            elif isinstance(obj, int):
                candidates.add(int(obj))

        harvest(data)
        return sorted(candidates) if candidates else None
    except Exception:
        return None

def run_batch(netuids: list[int], args) -> tuple[int, list[int]]:
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(args.qps)
    ok = 0
    failed_ids: list[int] = []

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {
            pool.submit(
                fetch_one, n, outdir, args.retries, args.backoff, args.timeout, limiter
            ): n
            for n in netuids
        }
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                if fut.result():
                    ok += 1
                else:
                    failed_ids.append(n)
            except Exception as e:
                log(f"  ✗ Unhandled exception for netuid {n}: {e}", err=True)
                failed_ids.append(n)

    return ok, failed_ids

def main():
    p = argparse.ArgumentParser(description="Fetch btcli subnet JSONs with backoff, QPS limit, and retries.")
    p.add_argument("--jobs", "-j", type=int, default=6, help="Concurrent workers (default: 6)")
    p.add_argument("--qps", type=float, default=3.0, help="Global queries per second across all workers (default: 3.0)")
    p.add_argument("--timeout", type=float, default=20.0, help="Per-call timeout seconds (default: 20)")
    p.add_argument("--start", type=int, default=1, help="First netuid (inclusive)")
    p.add_argument("--end", type=int, default=128, help="Last netuid (inclusive)")
    p.add_argument("--outdir", type=Path, default=Path("netuid_data"), help="Output directory")
    p.add_argument("--retries", type=int, default=3, help="Retries on empty/timeout (default: 3)")
    p.add_argument("--backoff", type=float, default=1.0, help="Base backoff seconds for retries (default: 1.0)")
    p.add_argument("--shuffle", action="store_true", help="Shuffle processing order to avoid late-run clustering")
    p.add_argument("--discover", action="store_true", help="Try to list existing netuids via btcli and only fetch those")
    args = p.parse_args()

    # Decide the target set
    if args.discover:
        discovered = maybe_discover_netuids()
        if discovered:
            netuids = discovered
            log(f"Discovered {len(netuids)} netuids from CLI; querying only those.")
        else:
            log("Could not discover netuids; falling back to range.", err=True)
            netuids = list(range(args.start, args.end + 1))
    else:
        netuids = list(range(args.start, args.end + 1))

    if args.shuffle:
        random.shuffle(netuids)

    # First pass (parallel with QPS cap)
    total = len(netuids)
    ok, failed = run_batch(netuids, args)
    log(f"\nPass 1 → Success: {ok}  Failed: {len(failed)}  Total: {total}")

    # Second pass (slow lane) on failures, if any
    if failed:
        log("Re-trying failures in a slow lane (jobs=2, qps=1.0)…")
        class SlowArgs:  # reuse fetch config with slower settings
            outdir=args.outdir; retries=3; backoff=max(args.backoff, 1.5); timeout=max(args.timeout, 25.0)
            jobs=2; qps=1.0
        ok2, failed2 = run_batch(failed, SlowArgs)
        log(f"Pass 2 → Recovered: {ok2}  Still failed: {len(failed2)}")
        if failed2:
            log("IDs still failing (likely missing/non-existent or endpoint issues): " + ", ".join(map(str, sorted(failed2))), err=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nInterrupted.", err=True)
        sys.exit(130)
