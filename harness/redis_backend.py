"""
Redis backend - NOT a purpose-built graph database either. Models the graph
by hand as adjacency sets (SET followers:<id>) plus hashes for node
properties and a secondary SET index for dev_type. Included because Redis
was the only real, already-installed server this sandbox could reach
without external network access (no Docker registry access to pull
FalkorDB/RedisGraph - see docs/environment-caveats.md). Like the SQLite
backend, treat this as a labeled reference point, not a peer graph database
platform.
"""
import os
import time
import random
import subprocess

import redis

from harness.metrics import percentiles, run_timed, MixedWorkloadRunner


class RedisBackend:
    name = "Redis (hand-rolled adjacency-list baseline, NOT a graph database)"

    def __init__(self, nodes_csv, edges_csv):
        self.nodes_csv = nodes_csv
        self.edges_csv = edges_csv
        self.r = None

    def connect(self):
        subprocess.run(["redis-cli", "FLUSHALL"], capture_output=True)
        self.r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
        self.r.ping()

    def load(self):
        import csv
        pipe = self.r.pipeline(transaction=False)
        t0 = time.perf_counter()
        n_nodes = 0
        with open(self.nodes_csv) as f:
            reader = csv.reader(f)
            next(reader)
            for nid, dev_type, login in reader:
                pipe.hset(f"node:{nid}", mapping={"dev_type": dev_type, "login": login})
                pipe.sadd(f"idx:dev_type:{dev_type}", nid)
                n_nodes += 1
                if n_nodes % 5000 == 0:
                    pipe.execute()
                    pipe = self.r.pipeline(transaction=False)
            pipe.execute()
        node_load_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        pipe = self.r.pipeline(transaction=False)
        n_rels = 0
        with open(self.edges_csv) as f:
            reader = csv.reader(f)
            next(reader)
            for src, dst in reader:
                pipe.sadd(f"adj:{src}", dst)
                pipe.sadd(f"adj:{dst}", src)  # dataset is undirected mutual-follow
                n_rels += 1
                if n_rels % 5000 == 0:
                    pipe.execute()
                    pipe = self.r.pipeline(transaction=False)
            pipe.execute()
        rel_load_s = time.perf_counter() - t0

        total_s = node_load_s + rel_load_s
        return {
            "node_count": n_nodes,
            "relationship_count": n_rels,
            "node_load_s": round(node_load_s, 4),
            "relationship_load_s": round(rel_load_s, 4),
            "total_wall_clock_s": round(total_s, 4),
            "nodes_per_second": round(n_nodes / total_s, 1) if total_s > 0 else None,
            "relationships_per_second": round(n_rels / total_s, 1) if total_s > 0 else None,
            "method": "pipelined HSET/SADD in batches of 5000",
        }

    def workloads(self, iterations=100, start_node_sample=50):
        random.seed(42)
        r = self.r
        all_ids = [k.split(":", 1)[1] for k in r.scan_iter("node:*")]
        start_ids = random.sample(all_ids, min(start_node_sample, len(all_ids)))
        out = {}

        def hop_n(sid, n):
            frontier = {sid}
            for _ in range(n):
                nxt = set()
                for node in frontier:
                    nxt |= r.smembers(f"adj:{node}")
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
            r.hget(f"node:{sid}", "login")

        out["point_lookup_ms"] = percentiles(run_timed(point_lookup, iterations, 10))

        def filtered_lookup():
            list(r.sscan_iter("idx:dev_type:ml", count=50))

        out["filtered_lookup_ms"] = percentiles(run_timed(filtered_lookup, iterations, 10))
        out["indexed_properties"] = ["node:<id> hash key (PK)", "idx:dev_type:<value> secondary set index"]

        def aggregation():
            r.scard("idx:dev_type:ml")
            r.scard("idx:dev_type:web")

        out["aggregation_ms"] = percentiles(run_timed(aggregation, iterations, 10))

        write_counter = {"n": 900000000}

        def read_op():
            sid = random.choice(start_ids)
            r.hget(f"node:{sid}", "login")

        def write_op():
            write_counter["n"] += 1
            nid = write_counter["n"]
            r.hset(f"node:{nid}", mapping={"dev_type": "synthetic", "login": f"bench_{nid}"})

        mixed = {}
        for conc in (1, 10, 40):
            runner = MixedWorkloadRunner(read_op, write_op, read_write_ratio=0.9)
            mixed[f"concurrency_{conc}"] = runner.run(conc, duration_s=4.0)
        out["mixed_workload"] = mixed
        return out

    def footprint(self):
        info = self.r.info("memory")
        return {
            "stored_data_size_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
            "memory_usage": f"{round(info.get('used_memory', 0) / (1024 * 1024), 2)} MB (INFO memory used_memory)",
        }

    def close(self):
        self.r = None
