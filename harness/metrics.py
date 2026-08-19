"""Shared timing / percentile utilities used by every backend benchmark."""
import time
import statistics
import threading
from contextlib import contextmanager


def percentiles(samples_ms, ps=(50, 95)):
    if not samples_ms:
        return {f"p{p}": None for p in ps}
    s = sorted(samples_ms)
    out = {}
    for p in ps:
        k = (len(s) - 1) * (p / 100)
        f = int(k)
        c = min(f + 1, len(s) - 1)
        if f == c:
            out[f"p{p}"] = s[f]
        else:
            out[f"p{p}"] = s[f] + (s[c] - s[f]) * (k - f)
    return out


@contextmanager
def timer_ms():
    """Yields a dict; after the block exits, dict['ms'] holds elapsed ms."""
    result = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["ms"] = (time.perf_counter() - start) * 1000.0


def run_timed(fn, iterations, warmup=10):
    """Run fn() `warmup` times (discarded), then `iterations` times,
    returning the list of per-call latencies in ms."""
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


class MixedWorkloadRunner:
    """Runs a mixed read/write workload with N concurrent client threads for
    a fixed wall-clock duration and reports sustained throughput."""

    def __init__(self, read_fn, write_fn, read_write_ratio=0.9):
        self.read_fn = read_fn
        self.write_fn = write_fn
        self.read_write_ratio = read_write_ratio

    def run(self, concurrency, duration_s=5.0):
        stop_at = time.perf_counter() + duration_s
        counters = [0] * concurrency
        errors = [0] * concurrency

        def worker(idx):
            n = 0
            rng_state = idx
            while time.perf_counter() < stop_at:
                rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
                is_read = (rng_state % 100) < (self.read_write_ratio * 100)
                try:
                    if is_read:
                        self.read_fn()
                    else:
                        self.write_fn()
                    n += 1
                except Exception:
                    errors[idx] += 1
            counters[idx] = n

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(concurrency)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0
        total_ops = sum(counters)
        total_errors = sum(errors)
        return {
            "concurrency": concurrency,
            "duration_s": round(elapsed, 3),
            "total_ops": total_ops,
            "throughput_qps": round(total_ops / elapsed, 2) if elapsed > 0 else None,
            "errors": total_errors,
        }
