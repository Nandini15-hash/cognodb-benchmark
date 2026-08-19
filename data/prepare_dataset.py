"""
Dataset preparation for the CognoDB Cloud graph-database benchmark.

Source dataset: MUSAE-GitHub social network
  Rozemberczki, B., Allen, C., & Sarkar, R. (2021). "Multi-scale Attributed
  Node Embedding." Journal of Complex Networks, 9(2).
  https://github.com/benedekrozemberczki/MUSAE  (GNU GPLv3, freely
  redistributable public research dataset)

Nodes: 37,700 GitHub developers.
Edges: 289,003 mutual "follower" relationships between developers.
This sits inside the assignment's requested 100k-500k relationship range.

We keep the graph exactly as published (no down-sampling) and add one
synthetic, clearly-documented derived property per node ("dev_type": ml/web)
so we have something to index and filter on for the lookup workloads -
the raw edge list alone has no node properties. The synthetic label is
assigned deterministically (hash of node id) purely as benchmark fixture
data; it is NOT the original MUSAE ml_target label (that file was not
reachable from this sandbox's network allowlist), so it carries no
research meaning - it only exists to give every platform an indexed
property to filter on.
"""
import csv
import hashlib
import json
import os

RAW_EDGES = os.path.join(os.path.dirname(__file__), "musae_git_edges.csv")
OUT_NODES = os.path.join(os.path.dirname(__file__), "nodes.csv")
OUT_EDGES = os.path.join(os.path.dirname(__file__), "edges.csv")
OUT_STATS = os.path.join(os.path.dirname(__file__), "dataset_stats.json")


def dev_type_for(node_id: str) -> str:
    h = hashlib.md5(node_id.encode()).hexdigest()
    return "ml" if int(h, 16) % 2 == 0 else "web"


def main():
    node_ids = set()
    edges = []
    with open(RAW_EDGES, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["id_1", "id_2"], header
        for row in reader:
            a, b = row[0], row[1]
            node_ids.add(a)
            node_ids.add(b)
            edges.append((a, b))

    with open(OUT_NODES, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "dev_type", "login"])
        for nid in sorted(node_ids, key=int):
            w.writerow([nid, dev_type_for(nid), f"dev_{nid}"])

    with open(OUT_EDGES, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst"])
        for a, b in edges:
            w.writerow([a, b])

    stats = {
        "source": "MUSAE-GitHub (Rozemberczki et al. 2021)",
        "license": "GNU GPLv3 (research dataset, freely redistributable)",
        "node_count": len(node_ids),
        "relationship_count": len(edges),
        "synthetic_properties": [
            "dev_type (ml|web) - deterministic hash, benchmark fixture only",
            "login - synthetic string label 'dev_<id>', benchmark fixture only",
        ],
    }
    with open(OUT_STATS, "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
