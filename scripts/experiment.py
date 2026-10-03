"""Experiments (X-xxx): pre-registered spec, every run logged (RUN-xxx), results (R-xxx) linked to runs."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

import ids
import rw_io
import rw_state
import validate

RUN_STATUSES = ("ok", "failed", "aborted")


def _xdir(ws, xid) -> Path:
    d = Path(ws) / "experiments" / xid
    if not (d / "spec.yaml").exists():
        raise ValueError(f"unknown experiment {xid}")
    return d


def _git_commit(ws) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(ws), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def new_experiment(ws, hypothesis_id, objective, dataset, split, metrics, primary_metric, seeds,
                   analysis_plan, baselines=()) -> Path:
    ws = Path(ws)
    if hypothesis_id not in ids.existing_ids(ws, "H"):
        raise ValueError(f"hypothesis {hypothesis_id} does not exist")
    if primary_metric not in metrics:
        raise ValueError(f"primary metric {primary_metric} must be one of the metrics {metrics}")
    xid = ids.next_id(ws, "X")
    spec = {"id": xid, "hypothesis_id": hypothesis_id, "objective": objective, "dataset": dict(dataset),
            "split": split, "metrics": list(metrics), "primary_metric": primary_metric,
            "seeds": [int(s) for s in seeds], "analysis_plan": analysis_plan, "baselines": list(baselines),
            "status": "draft"}
    problems = validate.validate_object("experiment", spec, f"experiments/{xid}/spec.yaml")
    if problems:
        raise ValueError("; ".join(problems))
    d = ws / "experiments" / xid
    rw_io.write_yaml(d / "spec.yaml", spec)
    (d / "outputs").mkdir(exist_ok=True)
    return d


def log_run(ws, xid, status, params=None, metrics=None, code_commit=None, environment=None, notes=None) -> dict:
    ws = Path(ws)
    d = _xdir(ws, xid)
    if xid not in rw_state.load_state(ws)["gates"]["G3"]["approved_ids"]:
        raise ValueError(f"{xid} is not approved at G3; ask the user to run /rw-approve G3 {xid} before running it")
    if status not in RUN_STATUSES:
        raise ValueError(f"status must be one of {', '.join(RUN_STATUSES)}")
    run = {"run_id": ids.next_run_id(ws, xid), "experiment_id": xid, "started_at": rw_io.now_iso(),
           "status": status, "code_commit": code_commit or _git_commit(ws),
           "environment": environment or f"python {sys.version.split()[0]} on {platform.platform()}",
           "params": params or {}, "metrics": metrics or {}, "notes": notes}
    rw_io.append_jsonl(d / "runs.jsonl", run)
    spec = rw_io.read_yaml(d / "spec.yaml")
    if spec.get("status") == "approved":
        spec["status"] = "running"
        rw_io.write_yaml(d / "spec.yaml", spec)
    return run


def add_result(ws, xid, run_id, metric, value, split, summary, ci=None) -> dict:
    ws = Path(ws)
    d = _xdir(ws, xid)
    run = next((r for r in rw_io.read_jsonl(d / "runs.jsonl") if r.get("run_id") == run_id), None)
    if run is None:
        raise ValueError(f"unknown run {run_id} in {xid}")
    if run.get("status") != "ok":
        raise ValueError(f"results can only come from runs with status ok ({run_id} is {run.get('status')})")
    spec = rw_io.read_yaml(d / "spec.yaml")
    if metric not in spec["metrics"]:
        raise ValueError(f"{metric} is not in the pre-registered metrics {spec['metrics']} of {xid}")
    res = {"id": ids.next_id(ws, "R"), "experiment_id": xid, "run_id": run_id, "metric": metric,
           "value": float(value), "ci": [float(x) for x in ci] if ci else None, "split": split, "summary": summary}
    rw_io.append_jsonl(d / "results.jsonl", res)
    return res


def mark_done(ws, xid) -> dict:
    d = _xdir(ws, xid)
    spec = rw_io.read_yaml(d / "spec.yaml")
    spec["status"] = "done"
    rw_io.write_yaml(d / "spec.yaml", spec)
    return spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Create experiments and record runs and results.")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--hypothesis", required=True)
    n.add_argument("--objective", required=True)
    n.add_argument("--dataset-name", required=True)
    n.add_argument("--dataset-version", required=True)
    n.add_argument("--dataset-path", required=True)
    n.add_argument("--split", required=True)
    n.add_argument("--metric", action="append", required=True)
    n.add_argument("--primary", required=True)
    n.add_argument("--seed", action="append", type=int, required=True)
    n.add_argument("--plan", required=True)
    n.add_argument("--baseline", action="append", default=[])
    lr = sub.add_parser("log-run")
    lr.add_argument("experiment_id")
    lr.add_argument("--status", required=True, choices=RUN_STATUSES)
    lr.add_argument("--params", default="{}", help="JSON object")
    lr.add_argument("--metrics", default="{}", help="JSON object")
    lr.add_argument("--commit")
    lr.add_argument("--env")
    lr.add_argument("--notes")
    ar = sub.add_parser("add-result")
    ar.add_argument("experiment_id")
    ar.add_argument("--run", required=True)
    ar.add_argument("--metric", required=True)
    ar.add_argument("--value", required=True, type=float)
    ar.add_argument("--split", required=True)
    ar.add_argument("--summary", required=True)
    ar.add_argument("--ci", nargs=2, type=float, metavar=("LOW", "HIGH"))
    dn = sub.add_parser("done")
    dn.add_argument("experiment_id")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.cmd == "new":
        d = new_experiment(ws, a.hypothesis, a.objective, {"name": a.dataset_name, "version": a.dataset_version,
                                                           "path": a.dataset_path}, a.split, a.metric, a.primary,
                           a.seed, a.plan, a.baseline)
        print(f"{d.name} created (draft) — the user approves it with /rw-approve G3 {d.name}")
    elif a.cmd == "log-run":
        r = log_run(ws, a.experiment_id, a.status, json.loads(a.params), json.loads(a.metrics), a.commit, a.env,
                    a.notes)
        print(f"{a.experiment_id} {r['run_id']} {r['status']}")
    elif a.cmd == "add-result":
        print(add_result(ws, a.experiment_id, a.run, a.metric, a.value, a.split, a.summary, a.ci)["id"])
    else:
        mark_done(ws, a.experiment_id)
        print(f"{a.experiment_id} done")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
