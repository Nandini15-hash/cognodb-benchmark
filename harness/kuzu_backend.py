"""
Kuzu backend (https://kuzudb.com) - an embedded, disk-backed, ACID graph
DBMS with a Cypher-subset query language. Chosen as the primary "self-hosted"
comparator in this environment because it is pip-installable and needs no
external network access, which this sandbox does not have (see
docs/environment-caveats.md). It is a genuine purpose-built graph database,
not a workaround data structure.

Load method: Kuzu's native bulk `COPY FROM` CSV loader (its documented
fastest ingestion path, analogous to Neo4j's `neo4j-admin import` or a
managed platform's bulk-import endpoint).
"""
import os
import shutil
import time
import random

import kuzu

from harness.metrics import percentiles, run_timed, MixedWorkloadRunner

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "_kuzu_db")


def _fresh_db_path():
    if os.path.isdir(DB_PATH):
        shutil.rmtree(DB_PATH)
    elif os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    return DB_PATH


class KuzuBackend:
    name = "Kuzu (embedded, self-hosted)"

    def __init__(self, nodes_csv, edges_csv):
        self.nodes_csv = os.path.abspath(nodes_csv)
        self.edges_csv = os.path.abspath(edges_csv)
        self.db = None
        self.conn = None

    def connect(self):
        path = _fresh_db_path()
        self.db = kuzu.Database(path)
        self.conn = kuzu.Connection(self.db)

    def load(self):
        self.conn.execute(
            "CREATE NODE TABLE Dev(id INT64, dev_type STRING, login STRING, PRIMARY KEY(id))"
        )
        self.conn.execute("CREATE REL TABLE Follows(FROM Dev TO Dev)")

        t0 = time.perf_counter()
        self.conn.execute(f'COPY Dev FROM "{self.nodes_csv}" (header=true)')
        node_load_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        self.conn.execute(f'COPY Follows FROM "{self.edges_csv}" (header=true)')
        rel_load_s = time.perf_counter() - t0

        n_nodes = self.conn.execute("MATCH (n:Dev) RETURN count(n)").get_next()[0]
        n_rels = self.conn.execute("MATCH ()-[r:Follows]->() RETURN count(r)").get_next()[0]

        total_s = node_load_s + rel_load_s
        return {
            "node_count": n_nodes,
            "relationship_count": n_rels,
            "node_load_s": round(node_load_s, 4),
            "relationship_load_s": round(rel_load_s, 4),
            "total_wall_clock_s": round(total_s, 4),
            "nodes_per_second": round(n_nodes / total_s, 1) if total_s > 0 else None,
            "relationships_per_second": round(n_rels / total_s, 1) if total_s > 0 else None,
            "method": "native bulk COPY FROM CSV",
        }

    def workloads(self, iterations=100, start_node_sample=50):
        random.seed(42)
        all_ids = [row[0] for row in _rows(self.conn.execute("MATCH (n:Dev) RETURN n.id"))]
        start_ids = random.sample(all_ids, min(start_node_sample, len(all_ids)))

        out = {}

        # --- Traversals: 1-hop, 2-hop, 3-hop ---
        for hop in (1, 2, 3):
            pattern = "->".join(["(n:Dev)"] + [f"(m{i}:Dev)" for i in range(1, hop + 1)])
            # Source dataset (MUSAE-GitHub) is documented as MUTUAL follow
            # relationships, i.e. logically undirected. Kuzu supports
            # undirected pattern matching natively (verified), so we use
            # "-[:Follows]-" (no arrow) rather than physically duplicating
            # every edge - see README methodology note on directedness.
            rel_pattern = "-[:Follows]-".join(["(n:Dev)"] + [f"(m{i}:Dev)" for i in range(1, hop + 1)])
            idx = {"i": 0}

            def do_hop(hop=hop, idx=idx):
                sid = start_ids[idx["i"] % len(start_ids)]
                idx["i"] += 1
                q = f"MATCH {rel_pattern} WHERE n.id = {sid} RETURN count(*)"
                list(_rows(self.conn.execute(q)))

            samples = run_timed(do_hop, iterations=iterations, warmup=10)
            out[f"traversal_{hop}hop_ms"] = percentiles(samples)

        # --- Point lookup (by primary key) ---
        idx = {"i": 0}

        def point_lookup(idx=idx):
            sid = start_ids[idx["i"] % len(start_ids)]
            idx["i"] += 1
            list(_rows(self.conn.execute(f"MATCH (n:Dev) WHERE n.id = {sid} RETURN n.login")))

        out["point_lookup_ms"] = percentiles(run_timed(point_lookup, iterations, 10))

        # --- Indexed / filtered lookup (by dev_type) ---
        def filtered_lookup():
            list(_rows(self.conn.execute(
                "MATCH (n:Dev) WHERE n.dev_type = 'ml' RETURN n.id LIMIT 50"
            )))

        out["filtered_lookup_ms"] = percentiles(run_timed(filtered_lookup, iterations, 10))
        out["indexed_properties"] = ["Dev.id (primary key)"]
        out["filter_note"] = "dev_type has no secondary index in Kuzu run (table scan); see caveats"

        # --- Aggregation ---
        def aggregation():
            list(_rows(self.conn.execute(
                "MATCH (n:Dev) RETURN n.dev_type, count(*) ORDER BY n.dev_type"
            )))

        out["aggregation_ms"] = percentiles(run_timed(aggregation, iterations, 10))

        # --- Mixed read/write workload ---
        write_counter = {"n": 900000000}

        def read_op():
            sid = random.choice(start_ids)
            list(_rows(self.conn.execute(f"MATCH (n:Dev) WHERE n.id = {sid} RETURN n.login")))

        def write_op():
            write_counter["n"] += 1
            nid = write_counter["n"]
            self.conn.execute(
                f"CREATE (n:Dev {{id: {nid}, dev_type: 'synthetic', login: 'bench_{nid}'}})"
            )

        mixed = {}
        for conc in (1, 10, 40):
            runner = MixedWorkloadRunner(read_op, write_op, read_write_ratio=0.9)
            mixed[f"concurrency_{conc}"] = runner.run(conc, duration_s=4.0)
        out["mixed_workload"] = mixed

        return out

    def footprint(self):
        size_bytes = _dir_size(DB_PATH)
        return {
            "stored_data_size_mb": round(size_bytes / (1024 * 1024), 2),
            "memory_usage": "not observable (embedded in host process; see caveats)",
        }

    def close(self):
        self.conn = None
        self.db = None


def _rows(query_result):
    while query_result.has_next():
        yield query_result.get_next()


def _dir_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total
