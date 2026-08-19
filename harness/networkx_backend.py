"""
NetworkX backend - a pure in-memory Python graph library, not a database at
all (no persistence, no ACID, no query language, no client/server protocol).
Included purely as a "what's the ceiling if you skip database overhead
entirely" reference point for the analysis section - explicitly not one of
the four graph database platforms required by the assignment.
"""
import os
import time
import random
import csv

import networkx as nx

from harness.metrics import percentiles, run_timed, MixedWorkloadRunner


class NetworkXBackend:
    name = "NetworkX (in-memory Python library, NOT a database)"

    def __init__(self, nodes_csv, edges_csv):
        self.nodes_csv = nodes_csv
        self.edges_csv = edges_csv
        self.g = None
        self.dev_type = {}
        self.login = {}
        self.by_type = {"ml": set(), "web": set()}

    def connect(self):
        self.g = nx.Graph()

    def load(self):
        t0 = time.perf_counter()
        with open(self.nodes_csv) as f:
            r = csv.reader(f)
            next(r)
            for nid, dev_type, login in r:
                nid = int(nid)
                self.g.add_node(nid)
                self.dev_type[nid] = dev_type
                self.login[nid] = login
                self.by_type.setdefault(dev_type, set()).add(nid)
        node_load_s = time.perf_counter() - t0
        n_nodes = self.g.number_of_nodes()

        t0 = time.perf_counter()
        with open(self.edges_csv) as f:
            r = csv.reader(f)
            next(r)
            edges = [(int(a), int(b)) for a, b in r]
        self.g.add_edges_from(edges)
        rel_load_s = time.perf_counter() - t0
        n_rels = len(edges)

        total_s = node_load_s + rel_load_s
        return {
            "node_count": n_nodes,
            "relationship_count": n_rels,
            "node_load_s": round(node_load_s, 4),
            "relationship_load_s": round(rel_load_s, 4),
            "total_wall_clock_s": round(total_s, 4),
            "nodes_per_second": round(n_nodes / total_s, 1) if total_s > 0 else None,
            "relationships_per_second": round(n_rels / total_s, 1) if total_s > 0 else None,
            "method": "Graph.add_edges_from() in-process, no serialization",
        }

    def workloads(self, iterations=100, start_node_sample=50):
        random.seed(42)
        g = self.g
        all_ids = list(g.nodes)
        start_ids = random.sample(all_ids, min(start_node_sample, len(all_ids)))
        out = {}

        def hop_n(sid, n):
            frontier = {sid}
            seen = {sid}
            for _ in range(n):
                nxt = set()
                for node in frontier:
                    nxt |= set(g.neighbors(node))
                nxt -= seen
                seen |= nxt
                frontier = nxt
            return len(frontier)

        for hop in (1, 2, 3):
            idx = {"i": 0}

            def do_hop(hop=hop, idx=idx):
                sid = start_ids[idx["i"] % len(start_ids)]
                idx["i"] += 1
                hop_n(sid, hop)

            out[f"traversal_{hop}hop_ms"] = percentiles(run_timed(do_hop, iterations, 10))

        idx = {"i": 0}

        def point_lookup(idx=idx):
            sid = start_ids[idx["i"] % len(start_ids)]
            idx["i"] += 1
            _ = self.login[sid]

        out["point_lookup_ms"] = percentiles(run_timed(point_lookup, iterations, 10))

        def filtered_lookup():
            list(self.by_type.get("ml", set()))[:50]

        out["filtered_lookup_ms"] = percentiles(run_timed(filtered_lookup, iterations, 10))
        out["indexed_properties"] = ["dict/set lookups in host process memory - not a real index structure"]

        def aggregation():
            return len(self.by_type.get("ml", set())), len(self.by_type.get("web", set()))

        out["aggregation_ms"] = percentiles(run_timed(aggregation, iterations, 10))

        write_counter = {"n": 900000000}

        def read_op():
            sid = random.choice(start_ids)
            _ = self.login[sid]

        def write_op():
            write_counter["n"] += 1
            nid = write_counter["n"]
            self.g.add_node(nid)
            self.login[nid] = f"bench_{nid}"
            self.dev_type[nid] = "synthetic"

        mixed = {}
        for conc in (1, 10, 40):
            runner = MixedWorkloadRunner(read_op, write_op, read_write_ratio=0.9)
            mixed[f"concurrency_{conc}"] = runner.run(conc, duration_s=4.0)
        out["mixed_workload"] = mixed
        return out

    def footprint(self):
        import sys
        approx = sys.getsizeof(self.g) + sum(sys.getsizeof(v) for v in self.g._adj.values())
        return {
            "stored_data_size_mb": round(approx / (1024 * 1024), 2),
            "memory_usage": "approximate, sys.getsizeof of adjacency dict only (undercounts true RSS)",
        }

    def close(self):
        self.g = None
