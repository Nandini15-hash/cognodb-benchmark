"""
ArangoDB backend (AQL, HTTP driver) - complete and ready to run, but NOT
executed by run_benchmark.py in this sandbox because there is no outbound
network access here to a Docker registry (self-hosted) or an ArangoDB
Oasis free-tier endpoint (managed). See docs/environment-caveats.md.

Usage (against a self-hosted container, e.g. from docker-compose.yml, or
an Oasis free-tier deployment):
    export ARANGO_URL="http://localhost:8529"
    export ARANGO_PASSWORD="benchmarkpass"
    python3 -c "
        import os, json
        from harness.arango_backend import ArangoBackend
        b = ArangoBackend(os.environ['ARANGO_URL'], 'root',
                           os.environ['ARANGO_PASSWORD'],
                           'data/nodes.csv', 'data/edges.csv')
        b.connect()
        load = b.load()
        wl = b.workloads()
        json.dump({'platform': b.name, 'load': load, 'workloads': wl},
                   open('results/arangodb.json', 'w'), indent=2)
    "
"""
import csv
import random
import time

from arango import ArangoClient

from harness.metrics import percentiles, run_timed, MixedWorkloadRunner


class ArangoBackend:
    name = "ArangoDB (self-hosted, AQL via python-arango)"

    def __init__(self, url, user, password, nodes_csv, edges_csv, db_name="bench"):
        self.url = url
        self.user = user
        self.password = password
        self.nodes_csv = nodes_csv
        self.edges_csv = edges_csv
        self.db_name = db_name
        self.db = None

    def connect(self):
        client = ArangoClient(hosts=self.url)
        sys_db = client.db("_system", username=self.user, password=self.password)
        if sys_db.has_database(self.db_name):
            sys_db.delete_database(self.db_name)
        sys_db.create_database(self.db_name)
        self.db = client.db(self.db_name, username=self.user, password=self.password)

    def load(self, batch_size=1000):
        nodes = self.db.create_collection("devs")
        edges = self.db.create_collection("follows", edge=True)
        nodes.add_persistent_index(fields=["dev_type"])

        t0 = time.perf_counter()
        docs = []
        with open(self.nodes_csv) as f:
            r = csv.reader(f)
            next(r)
            for nid, dev_type, login in r:
                docs.append({"_key": nid, "dev_type": dev_type, "login": login})
                if len(docs) >= batch_size:
                    nodes.insert_many(docs)
                    docs = []
            if docs:
                nodes.insert_many(docs)
        node_load_s = time.perf_counter() - t0
        n_nodes = nodes.count()

        t0 = time.perf_counter()
        docs = []
        n_rels = 0
        with open(self.edges_csv) as f:
            r = csv.reader(f)
            next(r)
            for src, dst in r:
                docs.append({"_from": f"devs/{src}", "_to": f"devs/{dst}"})
                n_rels += 1
                if len(docs) >= batch_size:
                    edges.insert_many(docs)
                    docs = []
            if docs:
                edges.insert_many(docs)
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
            "method": f"insert_many() batches of {batch_size}",
        }

    def workloads(self, iterations=100, start_node_sample=50):
        random.seed(42)
        all_ids = [d["_key"] for d in self.db.collection("devs").all()]
        start_ids = random.sample(all_ids, min(start_node_sample, len(all_ids)))
        out = {}

        for hop in (1, 2, 3):
            idx = {"i": 0}

            def do_hop(hop=hop, idx=idx):
                sid = start_ids[idx["i"] % len(start_ids)]
                idx["i"] += 1
                aql = (
                    f"FOR v IN {hop}..{hop} ANY 'devs/{sid}' follows "
                    "COLLECT WITH COUNT INTO c RETURN c"
                )
                list(self.db.aql.execute(aql))

            out[f"traversal_{hop}hop_ms"] = percentiles(run_timed(do_hop, iterations, 10))

        idx = {"i": 0}

        def point_lookup(idx=idx):
            sid = start_ids[idx["i"] % len(start_ids)]
            idx["i"] += 1
            self.db.collection("devs").get(sid)

        out["point_lookup_ms"] = percentiles(run_timed(point_lookup, iterations, 10))

        def filtered_lookup():
            list(self.db.aql.execute(
                "FOR d IN devs FILTER d.dev_type == 'ml' LIMIT 50 RETURN d._key"
            ))

        out["filtered_lookup_ms"] = percentiles(run_timed(filtered_lookup, iterations, 10))
        out["indexed_properties"] = ["devs._key (PK)", "devs.dev_type (persistent index)"]

        def aggregation():
            list(self.db.aql.execute(
                "FOR d IN devs COLLECT type = d.dev_type WITH COUNT INTO c RETURN {type, c}"
            ))

        out["aggregation_ms"] = percentiles(run_timed(aggregation, iterations, 10))

        write_counter = {"n": 900000000}

        def read_op():
            sid = random.choice(start_ids)
            self.db.collection("devs").get(sid)

        def write_op():
            write_counter["n"] += 1
            nid = write_counter["n"]
            self.db.collection("devs").insert(
                {"_key": str(nid), "dev_type": "synthetic", "login": f"bench_{nid}"}
            )

        mixed = {}
        for conc in (1, 10, 40):
            runner = MixedWorkloadRunner(read_op, write_op, read_write_ratio=0.9)
            mixed[f"concurrency_{conc}"] = runner.run(conc, duration_s=4.0)
        out["mixed_workload"] = mixed
        return out

    def close(self):
        self.db = None
