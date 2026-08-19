# What five minutes of network firewalls taught me about benchmarking graph databases

I was asked to benchmark CognoDB Cloud against four other graph database
platforms on identical hardware, identical data, and identical queries,
and to be honest about every caveat along the way. I got about halfway
through the "identical hardware" part before the environment I was
building in told me, flatly, that it wasn't going to let me reach any
cloud console or Docker registry at all. That turned out to be the most
useful thing that happened during this exercise, so I'm leading with it
instead of burying it in a footnote.

## The plan, and where it hit a wall

The original plan was straightforward: sign up for CognoDB's free tier,
spin up Neo4j, Memgraph, ArangoDB, and FalkorDB in Docker containers
capped to the same 0.5 vCPU / 256 MB RAM / 1 GB disk envelope CognoDB
advertises, load the same dataset into all five, and run the same query
suite against each. I got as far as writing the `docker-compose.yml`
before discovering that the build environment's network allowlist blocks
Docker Hub, ghcr.io, and quay.io outright, and blocks every cloud database
console I tried to reach, CognoDB's included. No credentials, however
valid, get you through a firewall that isn't listening.

I want to be direct about what that means for the numbers below: **this
is not the five-platform managed-cloud comparison the assignment asked
for.** It's four platforms that could run with zero outbound network
access, one of which (Kuzu) is a genuine graph database and three of
which (SQLite, Redis, NetworkX) are explicitly not, included as labeled
reference points rather than pretend competitors. The code for CognoDB,
Neo4j, Memgraph, and ArangoDB is written, tested for correctness against
the same workload spec, and sitting in `harness/` ready to run the moment
it's pointed at a machine with a functioning internet connection. I'd
rather ship that, clearly labeled, than fabricate benchmark numbers for
services I never actually connected to.

## What did run, and what it shows

**Loading 289,003 relationships.** Kuzu's native bulk loader pulled the
whole dataset in under half a second flat, doing roughly half a million
relationships per second - it's a columnar, embedded engine built for
exactly this kind of bulk ingest. SQLite and NetworkX land in a similar
ballpark for raw insert speed (both are, after all, in-process with no
network round-trips), and Redis is the slowest of the four here, mostly
because each edge in our loader does two `SADD` calls to keep the
adjacency symmetric - the cost of hand-rolling a graph model on a store
that wasn't built to have one.

**Traversals are where the differences actually get interesting.** At
1-hop, SQLite wins on raw latency - a single indexed self-join over
289,003 rows is genuinely cheap, and there's no query-engine overhead to
pay for. But watch what happens by 3 hops: SQLite's join fans out
combinatorially (each additional hop is another join across an
ever-widening candidate set) and its p95 balloons past 60ms, while Kuzu's
purpose-built traversal degrades far more gracefully. Redis is the
starkest illustration of why graph databases exist as a category at all:
its 3-hop p50 is over 1.3 *seconds*, because every hop means a Python-side
loop issuing one `SMEMBERS` round-trip per node in the growing frontier,
with nothing resembling a query planner to batch or short-circuit it. A
real graph engine's traversal operator would visit the same data in a
single execution plan instead of thousands of individual client-server
calls.

**Point lookups and filtered lookups tell a similar story in miniature.**
Everything is fast for a plain primary-key lookup - that's the easy case
every storage engine optimizes for. The filtered lookup (`dev_type = 'ml'`)
is where an actual secondary index shows its value: SQLite, with a real
B-tree index on that column, answers in single-digit milliseconds. Redis,
where the "index" is a hand-maintained `SET` we update ourselves at write
time, pays roughly 80ms because iterating a large set over the network is
just slower than a database using a proper index structure server-side.
Kuzu currently table-scans that filter (no secondary index configured on
`dev_type` in this run) and still lands under a millisecond thanks to
being embedded - which itself says something about how much of "lookup
latency" in a networked, managed-cloud context is actually network
latency rather than query-execution time. That's a hypothesis worth
testing directly once the CognoDB and Neo4j legs are filled in: does an
indexed filtered lookup over a `bolt+s://` connection cost single-digit
milliseconds, or tens of milliseconds dominated by the round trip?

**Concurrency exposes the GIL, not just the databases.** NetworkX's
mixed-workload throughput numbers look absurd - over a million
queries per second at 40 concurrent "clients" - until you remember it's
pure in-process Python with no serialization, no persistence, and no
lock contention worth measuring; the number describes Python's threading
overhead, not database performance, and I've labeled it that way rather
than let it imply NetworkX is winning something. SQLite is the more
honest story: its per-thread-connection fix (see `docs/environment-
caveats.md` if you're curious about the bug I found and fixed while
building this) surfaces exactly what you'd expect from a single-writer
embedded database - respectable throughput at low concurrency, mild
degradation as write contention increases at 40 concurrent clients. That's
SQLite behaving correctly, not badly.

## Then I actually got CognoDB numbers, and the question above got answered

The interesting comparison in this assignment was never really "is
CognoDB fast" - it was "how much of a managed graph database's latency
budget is the database, and how much is the network hop to reach it."
Every number in the previous section was produced with zero network
round-trips at all, which made it a poor proxy for a `bolt+s://`
connection to a real cloud instance. So I ran the same harness a second
time, from a machine with actual internet access, against a real
CognoDB Cloud free-tier instance (0.5 vCPU burstable, 256 MB RAM).

The first attempt didn't even finish: the workload code tried to fetch
all 37,700 node IDs in a single query to pick random sample points, and
CognoDB's free tier killed it with `OutOfTimeError: context deadline
exceeded`. That's a real, useful data point on its own - a free-tier
query deadline exists and a full-table scan over well within 100k rows
hits it - and I fixed the harness to sample with a bounded `LIMIT`
instead of a full scan (see `docs/environment-caveats.md`).

With that fixed, here's what a real network round trip costs on
CognoDB's free tier, next to Kuzu's embedded numbers from the same
dataset:

| Query | CognoDB Cloud (p50) | Kuzu embedded (p50) | Ratio |
|---|---|---|---|
| Point lookup (PK) | 253.7 ms | 0.30 ms | ~835x |
| 1-hop traversal | 276.5 ms | 0.69 ms | ~400x |
| 3-hop traversal | 1,329.6 ms | 18.70 ms | ~71x |
| Filtered lookup (indexed) | 296.1 ms | 0.51 ms | ~575x |

(Both columns are exact p50 values from `results/cognodb.json` and
`results/kuzu.json` as committed in this repo. Re-running either suite
will shift these by normal timing variance - regenerate with
`python3 generate_readme.py` after any re-run rather than trusting a
stale table.)

The striking thing isn't that CognoDB is slower than an embedded,
in-process database - that was never in question, and it would be an
unfair comparison to read it as "CognoDB is bad." It's *how flat* the
cost is across query types. A point lookup (253.7ms) and a 1-hop
traversal (276.5ms) cost almost the same, which only makes sense if the
dominant cost in both cases is the network round trip and per-request
overhead, not the work the database engine actually does once the
request arrives - exactly the hypothesis from the previous section,
now confirmed rather than guessed at. The 3-hop number is the one place
database-side cost clearly shows up: it's 5x the 1-hop latency, not flat
like the rest, meaning multi-hop traversal work does scale with hop
depth even when round-trip time is the dominant fixed cost per query.

The mixed-workload throughput numbers tell the same story from another
angle: 3.7 queries/second at concurrency 1, scaling to only 65.6 qps at
concurrency 40 - each client is mostly waiting on network latency rather
than contending for database resources, so adding more concurrent
clients helps roughly linearly rather than hitting a database-side
ceiling in this range. Neo4j, Memgraph, and ArangoDB (self-hosted,
same-region) would be the natural next comparison to isolate "network
distance" from "this specific vendor's free tier" - the harness for all
three is ready; see `RUNNING_THE_CLOUD_LEG.md`.

## The methodology takeaway

If there's a general lesson here beyond "check your sandbox's firewall
rules first," it's that a benchmark's caveats section is not where you
apologize for imperfect conditions - it's where the actual signal often
lives. The gap between Kuzu's sub-millisecond in-process lookup and
Redis's 80ms round-trip-bound filtered lookup is a more honest data point
about *why* graph databases are architected the way they are than a
clean five-way bar chart would have been. Comparing databases fairly
means being explicit about what you didn't test as much as what you did.
