#!/usr/bin/env python3
"""Run the Bolt/Cypher backend (CognoDB, Neo4j, or Memgraph) against the
prepared dataset and write a results JSON. Reads connection details from
BOLT_URI / BOLT_USER / BOLT_PASSWORD env vars - never pass credentials on
the command line or commit them to the repo.

Usage: python3 scripts/run_bolt_backend.py "<display name>" results/out.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.bolt_backend import BoltBackend

NODES = os.path.join(os.path.dirname(__file__), "..", "data", "nodes.csv")
EDGES = os.path.join(os.path.dirname(__file__), "..", "data", "edges.csv")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    display_name, out_path = sys.argv[1], sys.argv[2]

    uri = os.environ["BOLT_URI"]
    user = os.environ.get("BOLT_USER", "")
    password = os.environ.get("BOLT_PASSWORD", "")

    b = BoltBackend(uri, user, password, display_name, NODES, EDGES)
    b.connect()
    load = b.load()
    print("load:", load)
    workloads = b.workloads(iterations=100, start_node_sample=50)
    print("workloads done")
    b.close()

    result = {"platform": b.name, "load": load, "workloads": workloads}
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
