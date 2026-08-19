# Filling in CognoDB / Neo4j / Memgraph / ArangoDB

**Status: done.** All four legs below have now been run for real and their
results are committed in `results/`. This doc is kept as-is (rather than
rewritten in the past tense) so it still works as a step-by-step guide if
you want to reproduce or re-run any of these legs yourself - see
`docs/environment-caveats.md` for why they couldn't run from this repo's
original build sandbox, and the README's Caveats section for the two real
bugs (Memgraph index syntax, Memgraph aggregation variable scoping) that
came up while running them.

## 1. CognoDB Cloud

1. Sign up at https://console.cognodb.com/signup (free, no card) and create
   a free `c0` instance.
2. Copy the generated `bolt+s://<instance-id>.databases.cognodb.cloud` URI
   and password for user `cognodb` - shown once, so save it immediately.
3. Run:
   ```bash
   export BOLT_URI="bolt+s://<instance-id>.databases.cognodb.cloud"
   export BOLT_USER="cognodb"
   export BOLT_PASSWORD="<paste>"
   python3 scripts/run_bolt_backend.py "CognoDB Cloud" results/cognodb.json
   ```

## 2. Neo4j and Memgraph (self-hosted, matched resources)

```bash
docker compose up -d neo4j memgraph
export BOLT_URI="bolt://localhost:7687"; export BOLT_USER="neo4j"; export BOLT_PASSWORD="benchmarkpass"
python3 scripts/run_bolt_backend.py "Neo4j (self-hosted)" results/neo4j.json

export BOLT_URI="bolt://localhost:7688"; export BOLT_USER=""; export BOLT_PASSWORD=""
python3 scripts/run_bolt_backend.py "Memgraph (self-hosted)" results/memgraph.json
```
(Memgraph's community image runs unauthenticated by default; adjust if you
enabled auth.)

## 3. ArangoDB (self-hosted)

```bash
docker compose up -d arangodb
export ARANGO_URL="http://localhost:8529"
export ARANGO_PASSWORD="benchmarkpass"
python3 scripts/run_arango_backend.py results/arangodb.json
```

## 4. Regenerate the README tables

Once you have `results/*.json` for every platform you tested:
```bash
python3 generate_readme.py
```
This rewrites the results-matrix section of `README.md` from whatever JSON
files exist in `results/` - it does not require every platform to be
present, so partial runs are fine.
