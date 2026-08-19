"""
SQLite backend - NOT a purpose-built graph database. Included as an
explicitly-labeled relational baseline: what you get if you model the same
graph as two indexed tables and do traversal via self-joins. This is useful
context for the analysis (how much a real graph engine buys you over a
general-purpose relational store) but must not be read as a peer of CognoDB
in the "credible, comparable graph database" sense the assignment asks for.
"""
import os
import sqlite3
import threading
import time
import random

from harness.metrics import percentiles, run_timed, MixedWorkloadRunner

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "_sqlite_db.sqlite3")


class SqliteBackend:
    name = "SQLite (relational baseline, NOT a graph database)"

    def __init__(self, nodes_csv, edges_csv):
        self.nodes_csv = nodes_csv
        self.edges_csv = edges_csv
        self.conn = None

    def connect(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("PRAGMA journal_mode=WAL")

    def load(self):
        c = self.conn
        c.execute("CREATE TABLE nodes(id INTEGER PRIMARY KEY, dev_type TEXT, login TEXT)")
        c.execute("CREATE TABLE edges(src INTEGER, dst INTEGER)")

        import csv
        t0 = time.perf_counter()
        with open(self.nodes_csv) as f:
            r = csv.reader(f)
            next(r)
            c.executemany("INSERT INTO nodes VALUES (?,?,?)", r)
        c.commit()
        node_load_s = time.perf_counter() - t0

        # Source dataset is documented as MUTUAL (undirected) follow
        # relationships. SQLite has no native undirected-pattern concept,
        # so - unlike Kuzu, which matches "-[:Follows]-" natively - we make
        # the join symmetric by inserting both (src,dst) and (dst,src) rows.
        # relationship_count below is still the logical (undirected) count
        # from the source file, not the doubled physical row count; see
        # README methodology note on directedness.
        t0 = time.perf_counter()
        pairs = []
        with open(self.edges_csv) as f:
            r = csv.reader(f)
            next(r)
            for src, dst in r:
                pairs.append((src, dst))
        c.executemany("INSERT INTO edges VALUES (?,?)", pairs)
        c.executemany("INSERT INTO edges VALUES (?,?)", [(d, s) for s, d in pairs])
        c.commit()
        rel_load_s = time.perf_counter() - t0
        n_logical_rels = len(pairs)

        t0 = time.perf_counter()
        c.execute("CREATE INDEX idx_edges_src ON edges(src)")
        c.execute("CREATE INDEX idx_edges_dst ON edges(dst)")
        c.execute("CREATE INDEX idx_nodes_devtype ON nodes(dev_type)")
        c.commit()
        index_s = time.perf_counter() - t0

        n_nodes = c.execute("SELECT count(*) FROM nodes").fetchone()[0]
        n_rels = n_logical_rels
        total_s = node_load_s + rel_load_s + index_s

        return {
            "node_count": n_nodes,
            "relationship_count": n_rels,
            "physical_rows_stored": c.execute("SELECT count(*) FROM edges").fetchone()[0],
            "node_load_s": round(node_load_s, 4),
            "relationship_load_s": round(rel_load_s, 4),
            "index_build_s": round(index_s, 4),
            "total_wall_clock_s": round(total_s, 4),
            "nodes_per_second": round(n_nodes / total_s, 1) if total_s > 0 else None,
            "relationships_per_second": round(n_rels / total_s, 1) if total_s > 0 else None,
            "method": "executemany() batch insert + post-hoc CREATE INDEX",
        }

    def workloads(self, iterations=100, start_node_sample=50):
        random.seed(42)
        c = self.conn
        all_ids = [row[0] for row in c.execute("SELECT id FROM nodes")]
        start_ids = random.sample(all_ids, min(start_node_sample, len(all_ids)))
        out = {}

        joins = {
            1: "edges e1",
            2: "edges e1 JOIN edges e2 ON e1.dst = e2.src",
            3: "edges e1 JOIN edges e2 ON e1.dst = e2.src JOIN edges e3 ON e2.dst = e3.src",
        }
        for hop, join_sql in joins.items():
            idx = {"i": 0}

            def do_hop(join_sql=join_sql, idx=idx):
                sid = start_ids[idx["i"] % len(start_ids)]
                idx["i"] += 1
                c.execute(f"SELECT count(*) FROM {join_sql} WHERE e1.src = ?", (sid,)).fetchone()

            out[f"traversal_{hop}hop_ms"] = percentiles(run_timed(do_hop, iterations, 10))

        idx = {"i": 0}

        def point_lookup(idx=idx):
            sid = start_ids[idx["i"] % len(start_ids)]
            idx["i"] += 1
            c.execute("SELECT login FROM nodes WHERE id = ?", (sid,)).fetchone()

        out["point_lookup_ms"] = percentiles(run_timed(point_lookup, iterations, 10))

        def filtered_lookup():
            c.execute("SELECT id FROM nodes WHERE dev_type = 'ml' LIMIT 50").fetchall()

        out["filtered_lookup_ms"] = percentiles(run_timed(filtered_lookup, iterations, 10))
        out["indexed_properties"] = ["nodes.id (PK)", "nodes.dev_type (btree)", "edges.src", "edges.dst"]

        def aggregation():
            c.execute("SELECT dev_type, count(*) FROM nodes GROUP BY dev_type").fetchall()

        out["aggregation_ms"] = percentiles(run_timed(aggregation, iterations, 10))

        # sqlite3 connections are not thread-safe to share across threads.
        # SQLite itself is also single-writer (WAL allows concurrent
        # READERS but serializes writers) - give each client thread its own
        # connection so we measure SQLite's real concurrency ceiling rather
        # than a Python-level connection-sharing bug.
        write_counter = {"n": 900000000}
        write_lock_note = {"contended": 0}
        thread_local = threading.local()

        def get_conn():
            if not hasattr(thread_local, "conn"):
                thread_local.conn = sqlite3.connect(DB_PATH, timeout=5.0)
            return thread_local.conn

        def read_op():
            conn = get_conn()
            sid = random.choice(start_ids)
            conn.execute("SELECT login FROM nodes WHERE id = ?", (sid,)).fetchone()

        def write_op():
            conn = get_conn()
            write_counter["n"] += 1
            nid = write_counter["n"]
            conn.execute("INSERT INTO nodes VALUES (?,?,?)", (nid, "synthetic", f"bench_{nid}"))
            conn.commit()

        mixed = {}
        for conc in (1, 10, 40):
            runner = MixedWorkloadRunner(read_op, write_op, read_write_ratio=0.9)
            mixed[f"concurrency_{conc}"] = runner.run(conc, duration_s=4.0)
        out["mixed_workload"] = mixed
        out["mixed_workload_note"] = (
            "each client thread uses its own sqlite3 connection (timeout=5s); "
            "WAL mode allows concurrent readers but SQLite serializes writers, "
            "so 'errors' below reflects genuine SQLITE_BUSY contention, not a harness bug"
        )
        return out

    def footprint(self):
        size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        wal = DB_PATH + "-wal"
        if os.path.exists(wal):
            size += os.path.getsize(wal)
        return {"stored_data_size_mb": round(size / (1024 * 1024), 2), "memory_usage": "not observable"}

    def close(self):
        if self.conn:
            self.conn.close()
