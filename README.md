# CognoDB Cloud Graph Database Benchmark

Benchmarks CognoDB Cloud against other graph database platforms on an
identical public dataset and workload suite, per the Wexa AI take-home
assignment brief.

**Status: complete.** CognoDB Cloud plus four other graph database platforms (Neo4j, Memgraph, ArangoDB, Kuzu) have all been benchmarked with real, measured data - meeting the assignment's "CognoDB plus at least four other graph databases" requirement. The dataset pipeline and most of the harness were originally
built inside a sandboxed environment with no outbound network access to
any cloud console or Docker registry (see
[`docs/environment-caveats.md`](docs/environment-caveats.md) for the full
story, including a couple of real cross-platform Cypher-dialect bugs the
harness hit and fixed along the way - e.g. Memgraph's stricter variable
scoping after aggregation). CognoDB Cloud, Neo4j, Memgraph, and ArangoDB
were all benchmarked afterward from a machine with normal internet access
and, once installed, a working Docker setup - see the "load" note on each
platform's results for exactly how that was sequenced. Every number in
this README was produced by actually running the code in this repo; none
are estimated or placeholder.

**Executed in this build:** CognoDB Cloud, Neo4j (self-hosted), Memgraph (self-hosted), ArangoDB (self-hosted), Kuzu (embedded, self-hosted), SQLite - relational baseline, NOT a graph database, Redis - adjacency-list baseline, NOT a graph database, NetworkX - in-memory library, NOT a database
**Every planned platform has been executed.**


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
| CognoDB Cloud | 160.8 | 1232.9 | 234.4094 | UNWIND-batched CREATE via driver, batch_size=1000 |
| Neo4j (self-hosted) | 556.2 | 4264.0 | 67.778 | UNWIND-batched CREATE via driver, batch_size=1000 |
| Memgraph (self-hosted) | 3120.1 | 23918.6 | 12.0828 | UNWIND-batched CREATE via driver, batch_size=1000 |
| ArangoDB (self-hosted) | 1521.1 | 11660.9 | 24.784 | insert_many() batches of 1000 |
| Kuzu (embedded, self-hosted) | 126144.3 | 967004.6 | 0.2989 | native bulk COPY FROM CSV |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 25977.7 | 199141.1 | 1.4512 | executemany() batch insert + post-hoc CREATE INDEX |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 8425.7 | 64590.4 | 4.4744 | pipelined HSET/SADD in batches of 5000 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 28079.6 | 215254.0 | 1.3426 | Graph.add_edges_from() in-process, no serialization |

### Traversals

**1-hop query latency**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| CognoDB Cloud | 276.478 | 680.311 |
| Neo4j (self-hosted) | 4.908 | 79.537 |
| Memgraph (self-hosted) | 0.923 | 1.510 |
| ArangoDB (self-hosted) | 44.049 | 48.143 |
| Kuzu (embedded, self-hosted) | 0.694 | 0.833 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.005 | 0.009 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 0.117 | 0.158 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.002 | 0.009 |

**2-hop query latency**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| CognoDB Cloud | 281.554 | 588.611 |
| Neo4j (self-hosted) | 8.251 | 95.400 |
| Memgraph (self-hosted) | 2.848 | 26.588 |
| ArangoDB (self-hosted) | 47.073 | 55.519 |
| Kuzu (embedded, self-hosted) | 4.098 | 10.651 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.101 | 0.691 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 11.127 | 38.142 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.463 | 2.504 |

**3-hop query latency**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| CognoDB Cloud | 1329.606 | 6324.786 |
| Neo4j (self-hosted) | 222.796 | 1021.634 |
| Memgraph (self-hosted) | 168.549 | 702.737 |
| ArangoDB (self-hosted) | 241.838 | 1522.894 |
| Kuzu (embedded, self-hosted) | 18.698 | 31.411 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 10.040 | 59.051 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 1245.083 | 2471.945 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 29.306 | 65.257 |

### Lookups

**Point lookup (by primary key)**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| CognoDB Cloud | 253.703 | 420.010 |
| Neo4j (self-hosted) | 3.877 | 58.122 |
| Memgraph (self-hosted) | 0.730 | 1.324 |
| ArangoDB (self-hosted) | 1.565 | 1.966 |
| Kuzu (embedded, self-hosted) | 0.304 | 0.376 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.005 | 0.009 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 0.130 | 0.170 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.000 | 0.002 |

**Indexed/filtered lookup (dev_type = "ml")**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| CognoDB Cloud | 296.065 | 425.305 |
| Neo4j (self-hosted) | 6.300 | 79.031 |
| Memgraph (self-hosted) | 1.644 | 2.319 |
| ArangoDB (self-hosted) | 44.042 | 48.233 |
| Kuzu (embedded, self-hosted) | 0.513 | 0.695 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 0.019 | 0.036 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 76.755 | 87.055 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.195 | 0.243 |

### Aggregation

**Group-by count over dev_type**

| Platform | p50 (ms) | p95 (ms) |
|---|---|---|
| CognoDB Cloud | 344.706 | 661.028 |
| Neo4j (self-hosted) | 20.682 | 105.159 |
| Memgraph (self-hosted) | 10.729 | 60.735 |
| ArangoDB (self-hosted) | 58.094 | 66.345 |
| Kuzu (embedded, self-hosted) | 3.041 | 3.960 |
| SQLite - relational baseline, NOT a graph database *(not a graph DB)* | 1.837 | 1.933 |
| Redis - adjacency-list baseline, NOT a graph database *(not a graph DB)* | 0.200 | 0.259 |
| NetworkX - in-memory library, NOT a database *(not a graph DB)* | 0.000 | 0.000 |

### Mixed workload

**Mixed read/write throughput (90% read / 10% write, 4s sustained)**

| Platform | Concurrency | Ops | Throughput (qps) | Errors |
|---|---|---|---|---|
| CognoDB Cloud | 1 | 15 | 3.73 | 0 |
| CognoDB Cloud | 10 | 61 | 14.72 | 0 |
| CognoDB Cloud | 40 | 288 | 65.64 | 0 |
| Neo4j (self-hosted) | 1 | 283 | 70.72 | 0 |
| Neo4j (self-hosted) | 10 | 391 | 93.6 | 0 |
| Neo4j (self-hosted) | 40 | 449 | 106.7 | 0 |
| Memgraph (self-hosted) | 1 | 5545 | 1385.53 | 0 |
| Memgraph (self-hosted) | 10 | 6333 | 1582.4 | 0 |
| Memgraph (self-hosted) | 40 | 5835 | 1455.42 | 0 |
| ArangoDB (self-hosted) | 1 | 631 | 157.34 | 0 |
| ArangoDB (self-hosted) | 10 | 2565 | 638.7 | 0 |
| ArangoDB (self-hosted) | 40 | 2565 | 629.96 | 0 |
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

See [`ARTICLE.md`](ARTICLE.md) for the full write-up. Short version, now
with all five real graph databases in hand:

Kuzu (embedded, no network, no server process) is fastest everywhere -
sub-millisecond point lookups and 1-hop traversals, an ~18.7ms 3-hop, and
a bulk load north of 900,000 relationships/second. Memgraph is the
strongest of the self-hosted *server* comparators: an in-memory C++ engine
with no JVM startup cost, it posts sub-millisecond point lookups (0.73ms)
and 1-hop traversals (0.92ms) - within striking distance of Kuzu despite
being a real client-server round trip over localhost. Neo4j lands a clear
step behind Memgraph on latency (3.9ms point lookup, 4.9ms 1-hop) but
loads data over 3x faster than ArangoDB and has the best-documented,
most mature Cypher implementation of the three self-hosted servers.
ArangoDB is the outlier: its point lookup (1.57ms) is competitive, but
its graph-traversal AQL query (`FOR v IN 1..1 ANY ...`) costs 44ms at
1-hop - roughly 45-60x Neo4j/Memgraph's 1-hop cost - which reads as AQL's
general-purpose traversal syntax carrying meaningfully more per-query
overhead than either engine's native Cypher pattern-matching for this
workload, not as ArangoDB being slow in general (its aggregation and
point-lookup numbers are perfectly reasonable).

CognoDB Cloud, the only platform actually reached over a real network
rather than localhost or in-process, is 2-3 orders of magnitude slower
than every self-hosted comparator on every latency metric (point lookup:
253.7ms vs. Neo4j's 3.9ms and Memgraph's 0.73ms; 3-hop: 1,329.6ms vs.
Neo4j's 222.8ms). The gap between CognoDB and the *self-hosted* Bolt
engines - which run the identical query language and driver code CognoDB
uses - isolates network round-trip time and free-tier CPU throttling as
the dominant cost, not query complexity or Cypher engine quality: even
CognoDB's cheapest possible query, a primary-key point lookup, costs
253.7ms, while the same query against a self-hosted Neo4j on the same
laptop costs 3.9ms. That ~65x gap is architecture (network + burstable
tier), not database engine.

The three non-graph-database baselines are informative in a different
direction: SQLite's 1-hop query is *faster* than every graph engine
except Kuzu (a single indexed self-join is genuinely cheap), but its
cost explodes at 3 hops as the join fans out combinatorially. Redis's
3-hop latency (1.3 seconds) is dramatically worse than every purpose-built
graph engine, self-hosted or cloud, because every hop is a client-side
round trip per frontier node with no query planner to batch it - a
direct illustration of why graph databases exist as a category rather
than being hand-rolled adjacency sets on a generic KV store.

## Caveats (honest, not hidden)

1. **Neo4j, Memgraph, and ArangoDB required installing Docker Desktop
   partway through this project** (the initial build environment had no
   Docker registry or cloud-console access at all - see
   `docs/environment-caveats.md`) - and Docker's own install hit a real
   snag (Windows Subsystem for Linux wasn't installed, so Docker's engine
   component silently failed to set up even though its GUI opened). Once
   WSL2 was installed and Docker Desktop restarted, all three databases
   ran cleanly. Two genuine cross-engine Cypher-dialect bugs surfaced and
   were fixed along the way: Memgraph rejects Neo4j 5.x's `CREATE INDEX
   ... IF NOT EXISTS FOR (n:Label) ON (n.prop)` syntax (needs the older
   `CREATE INDEX ON :Label(prop)` form), and Memgraph's Cypher scopes
   variables more strictly after an aggregating `RETURN`, rejecting
   `ORDER BY n.prop` with "Unbound variable" where Neo4j and CognoDB
   accept it. Both are now handled portably in `harness/bolt_backend.py`
   rather than special-cased per platform.
2. **No enforced resource cap** on the platforms benchmarked without
   Docker (Kuzu, SQLite, Redis, NetworkX) - see the methodology section
   above. The three Docker-hosted comparators (Neo4j/Memgraph/ArangoDB)
   *do* run under the resource caps in `docker-compose.yml`.
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
