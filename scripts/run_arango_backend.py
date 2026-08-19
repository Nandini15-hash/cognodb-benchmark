#!/usr/bin/env python3
"""Run the ArangoDB backend against the prepared dataset and write a
results JSON. Reads connection details from ARANGO_URL / ARANGO_PASSWORD
env vars - never pass credentials on the command line or commit them.

Usage: python3 scripts/run_arango_backend.py results/arangodb.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.arango_backend import ArangoBackend

NODES = os.path.join(os.path.dirname(__file__), "..", "data", "nodes.csv")
EDGES = os.path.join(os.path.dirname(__file__), "..", "data", "edges.csv")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    out_path = sys.argv[1]

    url = os.environ.get("ARANGO_URL", "http://localhost:8529")
    password = os.environ["ARANGO_PASSWORD"]

    b = ArangoBackend(url, "root", password, NODES, EDGES)
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
