# CognoDB Cloud Graph Database Benchmark

Benchmarks CognoDB Cloud against other graph database platforms on an
identical public dataset and workload suite, per the Wexa AI take-home
assignment brief.

**Status: partial.** CognoDB Cloud and the Docker-hosted competitors
(Neo4j, Memgraph, ArangoDB) could not be reached from the sandboxed
environment this repo was built in — see
[`docs/environment-caveats.md`](docs/environment-caveats.md) for exactly
why, and [`RUNNING_THE_CLOUD_LEG.md`](RUNNING_THE_CLOUD_LEG.md) for how to
fill those rows in from a machine with normal internet access. Everything
below that *could* run without external network access was actually
executed — the numbers in this README are real, not placeholders, for the
platforms listed as executed.

**Executed in this build:** Kuzu (embedded, self-hosted), SQLite - relational baseline, NOT a graph database, Redis - adjacency-list baseline, NOT a graph database, NetworkX - in-memory library, NOT a database
**Not yet executed (harness ready):** CognoDB Cloud, Neo4j, Memgraph, ArangoDB

## Dataset

**Source:** MUSAE-GitHub (Rozemberczki et al. 2021) — a peer-reviewed, publicly redistributable
research dataset (GNU GPLv3 (research dataset, freely redistributable)). Nodes are GitHub developers; edges
are mutual "follows" relationships.

- Nodes: **37,700**
- Relationships: **289,003** (within the assignment's
  requested 100k-500k range, no down-sampling applied)

Two properties were added on top of the published dataset purely as
benchmark fixtures (documented, not part of the original research data):
- dev_type (ml|web) - deterministic hash, benchmark fixture only
- login - synthetic string label 'dev_<id>', benchmark fixture only

Regenerate with `python3 data/prepare_dataset.py` (reads
`data/musae_git_edges.csv`, writes `data/nodes.csv` and `data/edges.csv`).


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

| Platform | Nodes/s | Rels/s | Total load (s) | Load method |
|---|---|---|---|---|
| Kuzu (embedded, self-hosted) | 126144.3 | 967004.6 | 0.2989 | native bulk COPY FROM CSV |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 25977.7 | 199141.1 | 1.4512 | executemany() batch insert + post-hoc CREATE INDEX |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 8425.7 | 64590.4 | 4.4744 | pipelined HSET/SADD in batches of 5000 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 28079.6 | 215254.0 | 1.3426 | Graph.add_edges_from() in-process, no serialization |

### Traversals

**1-hop query latency**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| Kuzu (embedded, self-hosted) | 0.694 | 0.833 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.005 | 0.009 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 0.117 | 0.158 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.002 | 0.009 |

**2-hop query latency**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| Kuzu (embedded, self-hosted) | 4.098 | 10.651 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.101 | 0.691 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 11.127 | 38.142 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.463 | 2.504 |

**3-hop query latency**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| Kuzu (embedded, self-hosted) | 18.698 | 31.411 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 10.040 | 59.051 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 1245.083 | 2471.945 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 29.306 | 65.257 |

### Lookups

**Point lookup (by primary key)**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| Kuzu (embedded, self-hosted) | 0.304 | 0.376 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.005 | 0.009 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 0.130 | 0.170 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.000 | 0.002 |

**Indexed/filtered lookup (dev_type = "ml")**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| Kuzu (embedded, self-hosted) | 0.513 | 0.695 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.019 | 0.036 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 76.755 | 87.055 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.195 | 0.243 |

### Aggregation

**Group-by count over dev_type**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| Kuzu (embedded, self-hosted) | 3.041 | 3.960 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 1.837 | 1.933 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 0.200 | 0.259 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.000 | 0.000 |

### Mixed workload

**Mixed read/write throughput (90% read / 10% write, 4s sustained)**

| Platform | Concurrency | Ops | Throughput (qps) | Errors |
|---|---|---|---|---|
| Kuzu (embedded, self-hosted) | 1 | 10610 | 2650.26 | 0 |
| Kuzu (embedded, self-hosted) | 10 | 11219 | 2801.84 | 0 |
| Kuzu (embedded, self-hosted) | 40 | 9441 | 2351.16 | 0 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 1 | 144913 | 36226.85 | 0 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 10 | 150858 | 36958.71 | 0 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 40 | 139593 | 33504.74 | 0 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 1 | 37224 | 9305.83 | 0 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 10 | 30416 | 7601.7 | 0 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 40 | 28145 | 7029.41 | 0 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 1 | 3110907 | 758864.33 | 0 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 10 | 3478855 | 869531.24 | 0 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 40 | 3220014 | 804141.44 | 0 |

### Footprint

| Platform | Stored data size (MB) | Memory usage |
|---|---|---|
| Kuzu (embedded, self-hosted) | 9.39 | not observable (embedded in host process; see caveats) |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 31.4 | not observable |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 18.86 | 18.86 MB (INFO memory used_memory) |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 84.55 | approximate, sys.getsizeof of adjacency dict only (undercounts true RSS) |

## Analysis

See [`ARTICLE.md`](ARTICLE.md) for the full write-up. Short version: Kuzu
(the one real embedded graph engine that could be run in the build
environment) posts sub-millisecond 1-hop and point-lookup latencies and a
half-million-relationships/second bulk load, consistent with published
"embedded, columnar, no network round-trip" graph engine benchmarks
elsewhere. The two non-graph-database baselines are informative in
opposite directions: SQLite's 1-hop query is *faster* than Kuzu's (a single
indexed self-join is cheap), but its cost explodes at 3 hops as the join
fans out combinatorially, while Kuzu's native traversal degrades more
gracefully. Redis's 3-hop latency is dramatically worse than everything
else because every hop is a round trip per frontier node with no query
planner to batch it — a direct illustration of why purpose-built graph
engines exist rather than hand-rolling one on a KV store.

## Caveats (honest, not hidden)

1. **CognoDB Cloud and the Docker-hosted competitors were not executed** —
   see `docs/environment-caveats.md`. This is the single biggest caveat and
   is stated up front, not buried.
2. **No enforced resource cap** on the four platforms that were executed —
   see the methodology section above.
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

```bash
pip install -r requirements.txt
python3 data/prepare_dataset.py     # only needed once
python3 run_benchmark.py            # runs kuzu, sqlite, redis, networkx
python3 generate_readme.py          # regenerates this README from results/
```

For CognoDB / Neo4j / Memgraph / ArangoDB, see
[`RUNNING_THE_CLOUD_LEG.md`](RUNNING_THE_CLOUD_LEG.md).
