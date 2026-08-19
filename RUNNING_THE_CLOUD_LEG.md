# Filling in CognoDB / Neo4j / Memgraph / ArangoDB

Everything below assumes you're running from a machine with normal internet
access (this repo's own results matrix could not run these legs from its
build sandbox - see `docs/environment-caveats.md`).

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
