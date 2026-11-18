"""Compare 512-token chunks, same-page packing and 768-token Docling chunks.

Run inside the worker with an explicit fresh private output directory, PDF hash,
page-checked fact labels and dollar envelope. Only aggregate results are public.
"""

import argparse
import hashlib
import os
import statistics
import unicodedata
from collections import ChainMap
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import evaluate_retrieval as ev
import httpx
import psycopg
import tiktoken
from dotenv import dotenv_values
from psycopg.rows import dict_row

from folio.ai.routing import generation_client
from folio.ai.tokens import check_budget
from folio.config import Settings
from folio.conversations.config import ChatSettings
from folio.conversations.retrieval import vector_candidates
from folio.database import Database
from folio.indexing.preparation import prepare
from folio.indexing.provider import embedding_client


class ContinuedCalls:
    """Replay exact completed inputs, and charge only newly admitted provider calls."""

    def __init__(self, fresh, prior):
        self.fresh = fresh
        self.prior = prior
        self.state = {"calls": ChainMap(fresh.state["calls"], prior)}

    def call(self, key, payload, reservation, invoke):
        if key in self.prior:
            record = self.prior[key]
            if record["state"] != "complete" or record["input_hash"] != ev.digest(payload):
                raise ValueError("Prior call is incomplete or its input changed")
            return record["result"]
        return self.fresh.call(key, payload, reservation, invoke)


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def hits(question, passages):
    return [
        any(
            set(p["pages"]).intersection(fact["pages"])
            and all(normalized(a) in normalized(p["text"]) for a in fact["anchors"])
            for p in passages
        )
        for fact in question["facts"]
    ]


def install_candidates(conn, index, candidates, vectors):
    # Session-local shadow tables let every representation use the shipped pgvector SQL.
    conn.execute("TRUNCATE pg_temp.index_chunks, pg_temp.chunk_sources")
    with conn.cursor() as cur:
        with cur.copy(
            "COPY pg_temp.index_chunks (index_id,ordinal,text,embedding) FROM STDIN"
        ) as cp:
            for c, v in zip(candidates, vectors, strict=True):
                cp.write_row((index["id"], c["ordinal"], c["text"], str(v)))
        with cur.copy("COPY pg_temp.chunk_sources FROM STDIN") as cp:
            for c in candidates:
                for s in c["source_ids"]:
                    cp.write_row((index["id"], c["ordinal"], index["revision_id"], s))
    conn.execute("ANALYZE pg_temp.index_chunks")
    conn.execute("ANALYZE pg_temp.chunk_sources")


def run(args):
    cfg = Settings()
    db = Database(cfg.database_url)
    labels = ev.read(args.labels)
    out = args.output.resolve()
    if not any(out.is_relative_to(ev.ROOT / directory) for directory in (".local", "output")):
        raise ValueError("Private output belongs under .local/ or output/")
    if not args.budget.is_finite() or args.budget <= 0:
        raise ValueError("Supply a positive finite allowance")
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    db.open()
    try:
        with psycopg.connect(cfg.database_url, autocommit=True, row_factory=dict_row) as conn:
            if not conn.execute("SELECT pg_try_advisory_lock(718402700) AS ok").fetchone()["ok"]:
                raise ValueError("Another Folio evaluation is active")
            index = conn.execute(
                """SELECT i.* FROM document_indexes i
                JOIN extraction_revisions r ON r.id=i.revision_id
                JOIN file_versions f ON f.id=r.file_version_id
                WHERE f.sha256=%s AND i.state='ready' ORDER BY i.created_at DESC LIMIT 1""",
                (labels["sha"],),
            ).fetchone()
            if not index:
                raise ValueError("PDF has no ready index")
            run_index(db, conn, cfg, labels, index, args)
    finally:
        db.close()


def run_index(db, conn, cfg, labels, index, args):
    out = args.output
    ep = index["policy"]
    chat = ChatSettings().policy(cfg) | {"max_output_tokens": 512}
    if ep["chunk_tokens"] != 512 or ep["gateway"] != "openai" or ep.get("group_same_page"):
        raise ValueError("Expected an ungrouped, direct OpenAI 512-token reference index")
    codec = tiktoken.get_encoding("cl100k_base")

    def count(s):
        return len(codec.encode_ordinary(s))

    data = ev.snapshot(
        conn,
        {"index_id": str(index["id"]), "revision_id": str(index["revision_id"]), "questions": []},
        require_turn=False,
    )
    original = data["chunks"]
    vector_cache = {c["text"]: c["vector"] for c in original}
    packed = ev.pack_chunks(original, count)
    plan = prepare(db, index | {"policy": ep | {"chunk_tokens": 768}}, cfg.artifact_root)
    pages = {}
    for row in conn.execute(
        "SELECT element_id,page_no FROM element_locations WHERE revision_id=%s",
        (index["revision_id"],),
    ):
        pages.setdefault(row["element_id"], set()).add(row["page_no"])
    wider = []
    for c in plan["chunks"]:
        sources = [s["element_id"] for s in c["sources"]]
        wider.append(
            c | {"source_ids": sources, "pages": sorted(set().union(*(pages[s] for s in sources)))}
        )
    variants = {"original512": original, "group512": packed, "docling768": wider}
    manifest = {
        "pdf": labels["sha"],
        "labels": ev.digest(labels),
        "index": str(index["id"]),
        "policy": ep,
        "generation": chat,
        "jev": ev.JEV_MODEL,
        "repeats": args.repeats,
        "script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluation_helpers": hashlib.sha256(Path(ev.__file__).read_bytes()).hexdigest(),
        "jev_pricing": ev.JEV_PRICING_VERSION,
    }
    prior_path = (args.prior / "ledger.json").resolve() if args.prior else None
    for root in (ev.ROOT / ".local", ev.ROOT / "output"):
        for path in root.rglob("ledger.json"):
            if path.resolve() != prior_path and ev.read(path).get("budget", {}).get(
                "document_id"
            ) == str(index["document_id"]):
                raise ValueError(
                    "This document already has an evaluation ledger. Link its first run."
                )
    prior = ev.read(prior_path) if prior_path else None
    if prior:
        if (
            prior["budget"]["phase"] != "closed"
            or ev.digest(prior["manifest"]) != ev.digest(manifest)
            or str(index["document_id"]) != str(prior["budget"]["document_id"])
        ):
            raise ValueError("Continuation needs an identical configuration and a settled ledger")
    fresh = ev.Ledger(
        conn,
        out / "ledger.json",
        manifest,
        index["document_id"],
        ep["document_budget_usd"],
        args.budget,
        prior["budget"]["cumulative_document_evaluation_usd"] if prior else "0",
    )
    ledger = ContinuedCalls(fresh, prior["calls"] if prior else {})

    conn.execute(
        "CREATE TEMP TABLE index_chunks (index_id uuid, ordinal int, text text, "
        "embedding vector(1536), PRIMARY KEY(index_id,ordinal))"
    )
    conn.execute(
        "CREATE TEMP TABLE chunk_sources (index_id uuid, chunk_ordinal int, revision_id uuid, "
        "element_id text, PRIMARY KEY(index_id,chunk_ordinal,element_id))"
    )
    key = os.environ.get("TYPESAFE_API_KEY") or dotenv_values(ev.ROOT / ".env").get(
        "TYPESAFE_API_KEY"
    )
    if not key:
        raise ValueError("TypeSafe credential missing")

    def vectors(texts):
        need = list(dict.fromkeys(s for s in texts if s not in vector_cache))
        for offset in range(0, len(need), 32):
            batch = need[offset : offset + 32]
            # Write vectors once per batch. Keep repeated ledger checkpoints small.
            k = ev.digest(batch)

            def invoke(batch=batch, k=k):
                result = embedding_client(ep).embed(batch)
                ev.save(out / (k + ".json"), result.vectors)
                return {"cost_usd": result.cost_usd, "metadata": result.metadata}

            ledger.call(
                k,
                {"texts": batch, "model": ep["model_id"]},
                Decimal(sum(count(t) + 32 for t in batch)) * Decimal("0.02") / 1000000,
                invoke,
            )
            directory = args.prior if k in ledger.prior else out
            vector_cache.update(zip(batch, ev.read(directory / (k + ".json")), strict=True))
        return [vector_cache[s] for s in texts]

    results = {"counts": {k: len(v) for k, v in variants.items()}, "cases": []}
    chosen = []
    fresh.reserve()
    try:
        with httpx.Client(
            base_url="https://api.typesafe.ai/v1/",
            timeout=60,
            trust_env=False,
            headers={"Authorization": "Bearer " + key},
        ) as client:
            # Probe contract before transferring private text.
            ev.score_candidates(
                ledger,
                client,
                "probe",
                "What is the capacity?",
                [{"ordinal": 1, "text": "Capacity: 42 litres.", "pages": [1]}],
            )
            queries = []
            for i, q in enumerate(labels["questions"]):
                key_q = f"query-{i}"
                vec = ev.embed(ledger, key_q, [q["question"]], ep)[0]
                queries.append((vec, ledger.state["calls"][key_q]["seconds"]))
            for j, (variant, cs) in enumerate(variants.items()):
                install_candidates(conn, index, cs, vectors([c["text"] for c in cs]))
                for i, (q, (vec, emb_s)) in enumerate(
                    zip(labels["questions"], queries, strict=True)
                ):
                    measurements = {}
                    orders = [6, 12, 30]
                    for k in orders[(i + j) % 3 :] + orders[: (i + j) % 3]:
                        start = perf_counter()
                        selected = vector_candidates(conn, index["id"], ev.serialized(vec), k)
                        sql_s = perf_counter() - start
                        shortlist = [p | {"ordinal": p["chunk_ordinal"]} for p in selected]
                        rank_times = []
                        if k == 30:
                            candidate_hits = hits(q, shortlist)
                            size = (
                                count(ev.serialized(ev.jev_payload(q["question"], shortlist)))
                                + 1024
                                + 128 * len(shortlist)
                            )
                            if size > 48000:
                                raise ValueError("Shortlist exceeds request bound")
                            for rep in range(args.repeats):
                                ranked, m = ev.score_candidates(
                                    ledger, client, f"{variant}-{i}-{rep}", q["question"], shortlist
                                )
                                if rep == 0:
                                    first = ranked[:6]
                                rank_times.append(m["seconds"])
                            selected = first
                        method = "jev30to6" if k == 30 else f"vector{k}"
                        chosen.append((variant, method, i, q, selected))
                        measurements[method] = {
                            "hits": hits(q, selected),
                            "sql_s": sql_s,
                            "query_s": emb_s,
                            "jev_s": rank_times,
                            "retrieval_s": emb_s
                            + sql_s
                            + (statistics.median(rank_times) if rank_times else 0),
                            "tokens": sum(count(p["text"]) for p in selected),
                            "top30_hits": candidate_hits if k == 30 else None,
                        }
                    results["cases"].append(
                        {
                            "variant": variant,
                            "q": i,
                            "index_hits": hits(q, cs),
                            "methods": measurements,
                        }
                    )
                    ev.save(out / "measured.json", results)
        if args.answers:
            # Prioritize all three requested retrieval paths and predeclared alternate cases.
            chosen.sort(key=lambda x: (x[0] != "original512", x[2] not in (2, 6), x[2]))
            cache = {}
            for variant, method, i, q, selected in chosen:
                if args.answer_arm and args.answer_arm != f"{variant}/{method}":
                    continue
                k = ev.digest([i, [(p["text"], p["pages"]) for p in selected]])
                if k not in cache:
                    call_key = "answer-" + k
                    policy = chat
                    if call_key in ledger.prior:
                        policy = ledger.prior[call_key]["payload"]["policy"]
                    else:
                        msgs, schema = ev.prompt(data, q["question"], selected, chat)
                        estimate = check_budget(
                            msgs, schema, chat, generation_client(chat).profile()
                        )
                        # Input is already frozen. Use the counted input plus Folio's full margin.
                        policy = chat | {"input_limit_tokens": estimate["input_tokens_estimate"]}
                    try:
                        result = ev.generate(ledger, call_key, data, q, selected, policy)
                    except ValueError as error:
                        if str(error) != "Evaluation envelope exhausted; no call was made":
                            raise
                        results.setdefault("generation_budget_skips", []).append(
                            [variant, method, i]
                        )
                        ev.save(out / "measured.json", results)
                        continue
                    cache[k] = {
                        k: result[k]
                        for k in ["validated", "validation_error", "provider_seconds"]
                        if k in result
                    }
                    cache[k]["evidence"] = [
                        {"text": p["text"], "pages": p["pages"]} for p in selected
                    ]
                ev.save(out / f"answer-{variant}-{method}-{i}.json", cache[k])
    finally:
        fresh.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=Decimal, required=True)
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--answers", action="store_true")
    parser.add_argument(
        "--answer-arm",
        choices=[
            f"{v}/{m}"
            for v in ("original512", "group512", "docling768")
            for m in ("vector6", "vector12", "jev30to6")
        ],
        help="Limit paid answer checks to one of the measured arms",
    )
    parser.add_argument("--prior", type=Path, help="Exact completed calls from the first run")
    run(parser.parse_args())
