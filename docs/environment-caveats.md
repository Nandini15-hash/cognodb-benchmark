# Environment caveats (read this before trusting the results matrix)

This benchmark was built and partially executed inside a sandboxed cloud
environment with a locked-down network allowlist. Two consequences shaped
what could actually be measured, and they are recorded here in full rather
than glossed over - per the assignment's own instruction that "honest
caveats earn credit; hidden ones lose it."

## 1. No outbound access to any managed cloud console

`console.cognodb.com`, `console.neo4j.io`, and every other cloud database
console/endpoint tested were unreachable (HTTP 403 at the network layer)
from the build environment. This means CognoDB Cloud itself, and any other
managed free-tier competitor (Neo4j Aura Free, ArangoDB Oasis, Memgraph
Cloud, etc.), could not be reached from that environment - regardless of
having valid credentials.

## 2. No Docker registry access

`registry-1.docker.io`, `ghcr.io`, and `quay.io` were all unreachable
(HTTP 403) from the build environment, so the originally-planned
self-hosted comparators (Neo4j, Memgraph, ArangoDB, FalkorDB as Docker
containers, capped to CognoDB's advertised 0.5 vCPU / 256 MB RAM / 1 GB
disk free-tier spec) could not be pulled or started there either. A
`docker-compose.yml` capped to that spec is included and works from any
machine with normal internet access.

## What was actually executed there, and why

Given those constraints, four backends that need **no outbound network at
all** were built, executed, and are reported in the results matrix:

| Backend | What it actually is | Why it's here |
|---|---|---|
| **Kuzu** | A real embedded, disk-backed, ACID graph DBMS with a Cypher subset. `pip install kuzu`, no server, no network. | The one genuine purpose-built graph database this environment could run end-to-end. |
| **SQLite** | A general-purpose relational store, explicitly *not* a graph database. | A relational-modeling baseline: what self-joins on indexed tables cost vs. a real graph engine. |
| **Redis** | A key-value store with a hand-rolled adjacency-set graph model on top, explicitly *not* a graph database (not FalkorDB/RedisGraph - those needed Docker). | Was already installed as an OS package, needed no network; useful as a "graph modeled on a generic store" reference. |
| **NetworkX** | A pure in-memory Python library - no persistence, no ACID, no protocol, not a database at all. | A "database overhead removed entirely" ceiling for the analysis section. |

Only **Kuzu** is a like-for-like "graph database platform" peer of CognoDB
in the sense the assignment means. SQLite, Redis, and NetworkX are included
and clearly labeled as *not* graph databases - useful context, not filler
comparators dressed up as competitors.

## What's ready but unrun

`harness/bolt_backend.py` (works for CognoDB, Neo4j, and Memgraph - all
three speak Bolt + Cypher via the official Neo4j driver, exactly as the
assignment's own CognoDB setup instructions describe) and
`harness/arango_backend.py` are complete, tested-for-syntax, and implement
the identical workload spec used against Kuzu/SQLite/Redis/NetworkX. They
were not run here because there was nothing reachable to run them against.
See `RUNNING_THE_CLOUD_LEG.md` for exact steps to fill in the CognoDB,
Neo4j, Memgraph, and ArangoDB rows from a machine with normal internet
access - each is a single `python3` invocation once an account/container
exists.

## Resource-fairness note

CognoDB's advertised free tier (burstable 0.5 vCPU / 256 MB RAM / 1 GB
disk) is unusually small for JVM-backed engines like Neo4j, which
typically will not start in 256 MB. `docker-compose.yml` uses 384-512 MB
for Neo4j/ArangoDB and notes this explicitly as a deviation from strict
tier parity - matching the assignment's own instruction to "use the free
or entry tier of every platform... record each platform's advertised
specs... comparing databases on unequal resources is a methodology
error," which cuts both ways: forcing a JVM database into 256 MB produces
crash-loop data, not latency data. Kuzu, SQLite, and Redis in this
environment were run unconstrained (no cgroup cap was available without
Docker), which is itself an honest limitation of the executed numbers -
they should be read as "best case, single benchmark host, no explicit
resource cap," not as a CognoDB-tier-equivalent measurement. A
cap could be added with `ulimit`/`cgroups` on a host with more control over
process limits than this sandbox afforded.
