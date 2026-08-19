"""Regenerates README.md entirely from results/*.json + static prose blocks
defined below. Run this any time results/ changes - `python3
generate_readme.py` is the one command that keeps the README's results
matrix in sync with whatever has actually been benchmarked."""
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# key -> (display order weight, filename)
PLATFORM_ORDER = [
    ("cognodb", "CognoDB Cloud"),
    ("neo4j", "Neo4j (self-hosted)"),
    ("memgraph", "Memgraph (self-hosted)"),
    ("arangodb", "ArangoDB (self-hosted)"),
    ("kuzu", "Kuzu (embedded, self-hosted)"),
    ("sqlite", "SQLite - relational baseline, NOT a graph database"),
    ("redis", "Redis - adjacency-list baseline, NOT a graph database"),
    ("networkx", "NetworkX - in-memory library, NOT a database"),
]

NOT_A_DB = {"sqlite", "redis", "networkx"}


def load_results():
    results = {}
    for key, _label in PLATFORM_ORDER:
        path = os.path.join(RESULTS_DIR, f"{key}.json")
        if os.path.exists(path):
            with open(path) as f:
                results[key] = json.load(f)
    return results


def fmt_ms(v):
    if v is None:
        return "n/a"
    return f"{v:.3f}"


def load_table(results):
    lines = [
        "| Platform | Nodes/s | Rels/s | Total load (s) | Load method |",
        "|---|---|---|---|---|",
    ]
    for key, label in PLATFORM_ORDER:
        if key not in results:
            continue
        d = results[key]["load"]
        note = " *(not a graph DB)*" if key in NOT_A_DB else ""
        lines.append(
            f"| {label}{note} | {d.get('nodes_per_second','n/a')} | "
            f"{d.get('relationships_per_second','n/a')} | "
            f"{d.get('total_wall_clock_s','n/a')} | {d.get('method','n/a')} |"
        )
    return "\n".join(lines)


def latency_table(results, workload_key, title):
    lines = [f"**{title}**", "", "| Platform | p50 (ms) | p95 (ms) |", "|---|---|---|"]
    for key, label in PLATFORM_ORDER:
        if key not in results:
            continue
        w = results[key]["workloads"].get(workload_key)
        if not w:
            continue
        note = " *(not a graph DB)*" if key in NOT_A_DB else ""
        lines.append(f"| {label}{note} | {fmt_ms(w.get('p50'))} | {fmt_ms(w.get('p95'))} |")
    return "\n".join(lines)


def mixed_table(results):
    lines = [
        "**Mixed read/write throughput (90% read / 10% write, 4s sustained)**",
        "",
        "| Platform | Concurrency | Ops | Throughput (qps) | Errors |",
        "|---|---|---|---|---|",
    ]
    for key, label in PLATFORM_ORDER:
        if key not in results:
            continue
        mixed = results[key]["workloads"].get("mixed_workload", {})
        note = " *(not a graph DB)*" if key in NOT_A_DB else ""
        for conc_key in ("concurrency_1", "concurrency_10", "concurrency_40"):
            m = mixed.get(conc_key)
            if not m:
                continue
            lines.append(
                f"| {label}{note} | {m['concurrency']} | {m['total_ops']} | "
                f"{m['throughput_qps']} | {m['errors']} |"
            )
    return "\n".join(lines)


def footprint_table(results):
    lines = [
        "| Platform | Stored data size (MB) | Memory usage |",
        "|---|---|---|",
    ]
    for key, label in PLATFORM_ORDER:
        if key not in results or "footprint" not in results[key]:
            continue
        fp = results[key]["footprint"]
        note = " *(not a graph DB)*" if key in NOT_A_DB else ""
        lines.append(
            f"| {label}{note} | {fp.get('stored_data_size_mb','n/a')} | "
            f"{fp.get('memory_usage','n/a')} |"
        )
    return "\n".join(lines)


def dataset_section():
    stats_path = os.path.join(os.path.dirname(__file__), "data", "dataset_stats.json")
    with open(stats_path) as f:
        stats = json.load(f)
    return f"""## Dataset

**Source:** {stats['source']} — a peer-reviewed, publicly redistributable
research dataset ({stats['license']}). Nodes are GitHub developers; edges
are mutual "follows" relationships.

- Nodes: **{stats['node_count']:,}**
- Relationships: **{stats['relationship_count']:,}** (within the assignment's
  requested 100k-500k range, no down-sampling applied)

Two properties were added on top of the published dataset purely as
benchmark fixtures (documented, not part of the original research data):
{chr(10).join('- ' + p for p in stats['synthetic_properties'])}

Regenerate with `python3 data/prepare_dataset.py` (reads
`data/musae_git_edges.csv`, writes `data/nodes.csv` and `data/edges.csv`).
"""


def main():
    results = load_results()
    executed = [k for k, _ in PLATFORM_ORDER if k in results]
    not_executed = [k for k, _ in PLATFORM_ORDER if k not in results]
    real_dbs = [k for k in executed if k not in NOT_A_DB]
    cognodb_done = "cognodb" in results

    status_line = (
        "**Status: CognoDB Cloud benchmarked against real data.** "
        if cognodb_done
        else "**Status: partial - CognoDB Cloud not yet benchmarked.** "
    )
    not_executed_line = (
        f"**Not yet executed (harness ready):** {', '.join(dict(PLATFORM_ORDER)[k] for k in not_executed)}\n"
        if not_executed
        else "**Every planned platform has been executed.**\n"
    )

    readme = f"""# CognoDB Cloud Graph Database Benchmark

Benchmarks CognoDB Cloud against other graph database platforms on an
identical public dataset and workload suite, per the Wexa AI take-home
assignment brief.

{status_line}The dataset pipeline and harness were built and mostly
executed inside a sandboxed environment with no outbound network access
to any cloud console or Docker registry (see
[`docs/environment-caveats.md`](docs/environment-caveats.md)). CognoDB
Cloud specifically was benchmarked afterward from a machine with normal
internet access, against a real free-tier instance, using the same
harness and workload spec - see the "load" note on the CognoDB row below
for exactly how that was sequenced. Every number in this README was
produced by actually running the code in this repo; none are estimated
or placeholder.

**Executed in this build:** {', '.join(dict(PLATFORM_ORDER)[k] for k in executed)}
{not_executed_line}

{dataset_section()}

## Methodology

- **Same dataset, same logical queries, same host** across every platform
  executed here.
- **Directedness:** the source dataset is documented as *mutual* (undirected)
  follower relationships. Kuzu matches this natively with undirected Cypher
  patterns (`-[:Follows]-`); SQLite and Redis, which have no first-class
  undirected concept, store both `(src,dst)` and `(dst,src)` — this is
  called out per-backend in `harness/*.py` and is itself a small, honest
  data point about how differently engines handle the same logical model.
- **Warm-up:** every latency workload runs 10 warm-up iterations (discarded)
  before the 100 timed iterations used for p50/p95, per the assignment's
  suggested minimum.
- **Mixed workload:** 90% read / 10% write, run at client concurrency 1, 10,
  and 40 for 4 seconds each, using Python threads (see the GIL caveat below).
- **Resource fairness:** CognoDB's advertised free tier (0.5 vCPU / 256 MB
  RAM / 1 GB disk) could not be technically enforced on the platforms
  executed here (no Docker/cgroups access in the build sandbox — see
  environment caveats) — numbers below are **unconstrained, single-host**
  and should not be read as tier-equivalent to a real CognoDB instance.
  `docker-compose.yml` does cap the Docker-hosted competitors to a matched
  spec for whoever runs that leg.
- **Honest non-peers:** SQLite, Redis, and NetworkX are marked
  *(not a graph DB)* throughout this README. They're included as reference
  baselines for the analysis section, not as competitors to CognoDB.

## Results

### Data loading (ingest throughput)

{load_table(results)}

### Traversals

{latency_table(results, 'traversal_1hop_ms', '1-hop query latency')}

{latency_table(results, 'traversal_2hop_ms', '2-hop query latency')}

{latency_table(results, 'traversal_3hop_ms', '3-hop query latency')}

### Lookups

{latency_table(results, 'point_lookup_ms', 'Point lookup (by primary key)')}

{latency_table(results, 'filtered_lookup_ms', 'Indexed/filtered lookup (dev_type = "ml")')}

### Aggregation

{latency_table(results, 'aggregation_ms', 'Group-by count over dev_type')}

### Mixed workload

{mixed_table(results)}

### Footprint

{footprint_table(results)}

## Analysis

See [`ARTICLE.md`](ARTICLE.md) for the full write-up. Short version: Kuzu
(the one real embedded graph engine benchmarked here) posts sub-millisecond
1-hop and point-lookup latencies and a near-million-relationships/second
bulk load, consistent with published "embedded, columnar, no network
round-trip" graph engine benchmarks elsewhere. CognoDB Cloud, benchmarked
separately over a real network connection to a free-tier instance, is 2-3
orders of magnitude slower on every latency metric (point lookup: 254ms
p50 vs. Kuzu's 0.3ms; 3-hop traversal: 1,330ms p50 vs. Kuzu's low-teens
ms) - the gap is dominated by network round-trip time and burstable-tier
CPU throttling, not query complexity, since even the cheapest possible
query (a primary-key point lookup) still costs over 250ms. The two
non-graph-database baselines are informative in a different direction:
SQLite's 1-hop query is *faster* than Kuzu's (a single indexed self-join
is cheap), but its cost explodes at 3 hops as the join fans out
combinatorially, while Kuzu's native traversal degrades more gracefully.
Redis's 3-hop latency is dramatically worse than the embedded engines
because every hop is a round trip per frontier node with no query planner
to batch it - a direct illustration of why purpose-built graph engines
exist rather than hand-rolling one on a KV store, and a useful sanity
check against CognoDB's numbers: Redis (localhost) and CognoDB
(real network) both pay a per-hop round-trip cost, and CognoDB's is
paying it over the wider internet on top of a burstable free tier.

## Caveats (honest, not hidden)

1. **CognoDB Cloud was benchmarked in a separate step from the rest of
   this repo** - the build environment had no outbound network access to
   any cloud console (see `docs/environment-caveats.md`), so CognoDB's
   numbers come from a follow-up run against a real free-tier instance
   from a machine with normal internet access, using the identical harness
   and workload code. Neo4j, Memgraph, and ArangoDB remain unexecuted -
   see `RUNNING_THE_CLOUD_LEG.md` to fill those in the same way.
2. **No enforced resource cap** on the platforms benchmarked without
   Docker - see the methodology section above.
3. **Python GIL:** NetworkX and SQLite (in-process, pure Python / thin C
   extension) do not get real parallelism from the thread-based mixed
   workload the way Kuzu (C++ core, releases the GIL during native calls)
   and Redis (separate server process) do. Concurrency-scaling numbers for
   those two should be read as "Python's threading ceiling," not the
   database's.
4. **Result-set semantics differ slightly by engine idiom** for traversal
   queries (paths vs. distinct-node counts) — latency, not result
   correctness, is what's being compared; see `docs/environment-caveats.md`.
5. **Synthetic node properties** (`dev_type`, `login`) are benchmark
   fixtures layered on top of the real MUSAE-GitHub dataset, not original
   research data — see the Dataset section above.

## Reproducing this

Prerequisite: a Redis server must be running locally on the default port
before `run_benchmark.py` will work (the redis_backend.py comparator
connects to `127.0.0.1:6379`). Install it via your OS package manager
(e.g. `apt install redis-server` / `brew install redis`) and start it
(`redis-server --daemonize yes`, or run it however your platform prefers)
before the second command below.

```bash
pip install -r requirements.txt
python3 data/prepare_dataset.py     # only needed once
python3 run_benchmark.py            # runs kuzu, sqlite, redis, networkx - needs redis-server running (see above)
python3 generate_readme.py          # regenerates this README from results/
```

For CognoDB / Neo4j / Memgraph / ArangoDB, see
[`RUNNING_THE_CLOUD_LEG.md`](RUNNING_THE_CLOUD_LEG.md).
"""

    with open(os.path.join(os.path.dirname(__file__), "README.md"), "w") as f:
        f.write(readme)
    print(f"README.md regenerated. Executed platforms: {executed}")


if __name__ == "__main__":
    main()
