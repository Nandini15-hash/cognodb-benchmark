"""
Orchestrator: loads the prepared dataset into every executable backend,
runs the full workload suite (section 5.2 of the assignment) and writes one
results/<backend>.json per platform.

Platforms executed here are limited to what this environment can actually
reach (see docs/environment-caveats.md): no outbound network to any managed
cloud console, and no Docker registry access to self-host Neo4j / Memgraph /
ArangoDB / FalkorDB. CognoDB Cloud and the originally-planned Docker-hosted
comparators have ready-to-run code under harness/ (neo4j_backend.py,
memgraph_backend.py, arango_backend.py, cognodb_backend.py) but are NOT
invoked by this script - run them from a machine with normal internet
access; see README "Running the cloud/Docker legs yourself".
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from harness.kuzu_backend import KuzuBackend
from harness.sqlite_backend import SqliteBackend
from harness.redis_backend import RedisBackend
from harness.networkx_backend import NetworkXBackend

NODES = os.path.join(os.path.dirname(__file__), "data", "nodes.csv")
EDGES = os.path.join(os.path.dirname(__file__), "data", "edges.csv")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

BACKENDS = [
    ("kuzu", KuzuBackend),
    ("sqlite", SqliteBackend),
    ("redis", RedisBackend),
    ("networkx", NetworkXBackend),
]


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary = {}
    for key, cls in BACKENDS:
        print(f"\n=== {key} ===", flush=True)
        backend = cls(NODES, EDGES)
        t_wall0 = time.time()
        backend.connect()
        load = backend.load()
        print(f"  load: {load}", flush=True)
        workloads = backend.workloads(iterations=100, start_node_sample=50)
        print("  workloads done", flush=True)
        footprint = backend.footprint()
        backend.close()
        wall_s = round(time.time() - t_wall0, 2)

        result = {
            "platform": backend.name,
            "wall_clock_total_s": wall_s,
            "load": load,
            "workloads": workloads,
            "footprint": footprint,
        }
        out_path = os.path.join(RESULTS_DIR, f"{key}.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        summary[key] = {"name": backend.name, "wall_s": wall_s}
        print(f"  wrote {out_path} ({wall_s}s total)", flush=True)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
