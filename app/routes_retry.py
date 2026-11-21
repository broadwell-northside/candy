"""Retry a job whose result the age check deleted (D-C-51).

A flagged result is deleted and the job says so plainly. This route offers one thing: run the same job again with a
new seed. It sends the job back through the normal /api/jobs queue (server.create_job), so every text rule, area rule,
age rule and checker rule runs again, exactly as for a new job. It changes no rule and keeps nothing.
register(server_module) adds the route.
"""
import copy
import json
import uuid

from fastapi import Request

import pipelines

S = None  # the server module
# Kinds that read their seed only from this top-level field and refuse any other field (stills._ALLOWED, films._ALLOWED).
TOP_LEVEL_SEED_ONLY = frozenset({"workshop_still", "film"})
_GRAPH_SEEDS = ("seed", "noise_seed")


def _reseed_graph(node, seed):
    """Every whole-number seed input inside a workflow graph (a raw workflow keeps its seeds in the graph)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _GRAPH_SEEDS and isinstance(value, int) and not isinstance(value, bool):
                node[key] = seed
            else:
                _reseed_graph(value, seed)
    elif isinstance(node, list):
        for value in node:
            _reseed_graph(value, seed)


def fresh_params(params, kind=""):
    """A copy of a job's parameters with a new random seed in the place this kind of job reads it from."""
    out = copy.deepcopy(params) if isinstance(params, dict) else {}
    seed = pipelines._rand_seed()
    if kind in TOP_LEVEL_SEED_ONLY:
        out["seed"] = seed
        return out
    if kind == "raw":
        wf = out.get("workflow")
        try:
            graph = json.loads(wf) if isinstance(wf, str) else wf
        except ValueError:
            return out
        _reseed_graph(graph, seed)
        out["workflow"] = json.dumps(graph) if isinstance(wf, str) else graph
        return out
    advanced = out.get("advanced")
    if not isinstance(advanced, dict):
        advanced = {}
    advanced["seed"] = seed
    out["advanced"] = advanced
    if "seed" in out:
        out["seed"] = seed
    return out


def register(server):
    global S
    S = server
    app = server.app
    err = server.err

    @app.post("/api/jobs/{jid}/retry")
    def retry_job(request: Request, jid: str):
        old = S.JOBS.get(jid)
        # The same visibility rule as reading the job: an 18+ job is only for a device that unlocked the 18+ section.
        if not old or (old.get("area") == "adult" and not S.adult_unlocked(request)):
            err("No such job", 404)
        if not old.get("can_retry") or old.get("kind") in pipelines.RETRY_NO_SEED:
            err("Only a job whose result was deleted by the age check, in a tool with a seed to change, can be retried this way.")
        body = {"kind": old["kind"], "params": fresh_params(old.get("params"), old["kind"]), "area": old.get("area") or "default",
                "request_id": uuid.uuid4().hex}
        return S.create_job(request, body)
