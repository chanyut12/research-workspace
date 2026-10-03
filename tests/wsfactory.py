"""Builds the golden fixture: a complete, valid research workspace touching every ID type."""
from __future__ import annotations

from pathlib import Path

import rw_io

P = rw_io.PATHS
T = "2026-10-04T00:00:00+00:00"


def _gate(approved=False, ids=(), at=None):
    return {"approved": approved, "approved_at": at, "approved_ids": list(ids), "note": None}


def set_stage(ws: Path, stage: str) -> None:
    state = rw_io.read_json(ws / P["state"])
    state["stage"] = stage
    rw_io.write_json(ws / P["state"], state)


def edit_jsonl(path: Path, row_id: str, **changes) -> None:
    rows = rw_io.read_jsonl(path)
    for r in rows:
        if r.get("id") == row_id:
            r.update(changes)
    rw_io.write_jsonl(path, rows)


def edit_hypothesis(ws: Path, hid: str, **changes) -> None:
    data = rw_io.read_yaml(ws / P["hypotheses"])
    for h in data["hypotheses"]:
        if h["id"] == hid:
            h.update(changes)
    rw_io.write_yaml(ws / P["hypotheses"], data)


def make_good_workspace(root: Path) -> Path:
    ws = Path(root)
    ws.mkdir(parents=True, exist_ok=True)
    rw_io.write_json(ws / P["state"], {
        "schema_version": 1, "title": "Stroke outcome prediction", "stage": "WRITING",
        "protocol_version": 1,
        "gates": {"G1": _gate(True, at="2026-10-03T00:00:00+00:00"),
                  "G2": _gate(True, ["H-001", "H-002"], "2026-10-08T00:00:00+00:00"),
                  "G3": _gate(True, ["X-001"], "2026-10-12T00:00:00+00:00"),
                  "G4": _gate()}})
    for entry in [
        {"timestamp": "2026-10-01T09:00:00+00:00", "kind": "init", "reason": "workspace created"},
        {"timestamp": "2026-10-03T09:00:00+00:00", "kind": "approve", "gate": "G1"},
        {"timestamp": "2026-10-12T09:00:00+00:00", "kind": "approve", "gate": "G3", "ids": ["X-001"]},
    ]:
        rw_io.append_jsonl(ws / P["decision_log"], {"from": None, "to": None, "gate": None, "ids": [],
                                                    "reason": None, "cause_ids": [], **entry})
    rw_io.write_yaml(ws / P["protocol"], {
        "protocol_version": 1, "title": "Stroke outcome prediction",
        "research_questions": [{"id": "RQ-1", "text": "Which admission features predict 90-day poor outcome after ischemic stroke?"}],
        "review_type": "scoping",
        "eligibility": {"include": ["Adults with ischemic stroke",
                                    "Reports a prediction model or risk factor for functional outcome"],
                        "exclude": ["Case reports"]},
        "sources": ["openalex", "crossref"],
        "date_range": {"from_year": 2015, "to_year": 2026},
        "languages": ["en"], "notes": None})
    for row in [
        dict(query_id="Q-001", purpose="scoping", for_id="RQ-1", source="openalex",
             query="ischemic stroke outcome prediction", filters="{}", timestamp=T, count="2",
             raw_file="literature/raw/Q-001-openalex.json", status="ok"),
        dict(query_id="Q-002", purpose="contradicting", for_id="H-001", source="openalex",
             query="NIHSS no association functional outcome", filters="{}", timestamp=T, count="0",
             raw_file="literature/raw/Q-002-openalex.json", status="ok"),
        dict(query_id="Q-003", purpose="both", for_id="H-002", source="crossref",
             query="atrial fibrillation stroke onset to door delay", filters="{}", timestamp=T, count="3",
             raw_file="literature/raw/Q-003-crossref.json", status="ok"),
    ]:
        rw_io.append_csv(ws / P["search_log"], row, rw_io.SEARCH_LOG_FIELDS)
    rw_io.write_jsonl(ws / P["records"], [
        {"id": "S-001", "title": "Admission NIHSS predicts functional outcome after ischemic stroke",
         "year": 2019, "doi": "10.1000/s001", "identifiers": {"openalex": "W1"}, "sources": ["openalex"],
         "query_ids": ["Q-001"], "abstract": "NIHSS predicts outcome.", "authors": ["Ann Author"],
         "venue": "Stroke", "url": "https://doi.org/10.1000/s001"},
        {"id": "S-002", "title": "Machine learning for 90-day outcome after stroke", "year": 2022,
         "doi": "10.1000/s002", "identifiers": {"openalex": "W2"}, "sources": ["openalex"],
         "query_ids": ["Q-001"], "abstract": None, "authors": ["Bo Lee"], "venue": "J Stroke", "url": None},
    ])
    for sid in ("S-001", "S-002"):
        for stage in ("title-abstract", "full-text"):
            rw_io.append_csv(ws / P["screening"], dict(id=sid, stage=stage, decision="include", reason_code="INC",
                                                       confidence="0.9", reviewer="evidence-analyst",
                                                       timestamp=T, protocol_version="1"), rw_io.SCREENING_FIELDS)
    base_e = {"population_or_dataset": "1,200 adults with ischemic stroke", "method": "logistic regression",
              "outcome": "mRS 3-6 at 90 days", "limitations": ["single centre"], "extractor_confidence": 0.9,
              "verification_status": "verified"}
    rw_io.write_jsonl(ws / P["evidence"], [
        {"id": "E-001", "study_id": "S-001", "rq_id": "RQ-1",
         "claim": "Higher admission NIHSS was associated with poor 90-day outcome",
         "source_location": {"page": 4, "section": "Results", "table": None, "figure": None},
         "evidence_type": "reported_result", "effect_or_result": "OR 1.18 per point (95% CI 1.12-1.25)", **base_e},
        {"id": "E-002", "study_id": "S-001", "rq_id": "RQ-1",
         "claim": "Authors suggest NIHSS should be part of any outcome model",
         "source_location": {"page": None, "section": "Discussion", "table": None, "figure": None},
         "evidence_type": "author_interpretation", "effect_or_result": None, **base_e},
        {"id": "E-003", "study_id": "S-002", "rq_id": "RQ-1",
         "claim": "Gradient boosting reached AUROC 0.82 for 90-day outcome",
         "source_location": {"page": None, "section": None, "table": "Table 2", "figure": None},
         "evidence_type": "reported_result", "effect_or_result": "AUROC 0.82", **base_e},
    ])
    m1 = ws / "meetings" / "M-001-2026-10-05-expert-consult"
    m2 = ws / "meetings" / "M-002-2026-10-10-advisor-review"
    rw_io.write_yaml(m1 / "meeting.yaml", {
        "id": "M-001", "type": "expert-consult", "date": "2026-10-05",
        "participants": [{"role": "clinician", "name": None}], "agenda": ["feature plausibility"],
        "prep_questions": ["Which admission variables matter clinically?"], "notes_file": "notes.md",
        "transcript_file": None, "logged": True})
    (m1 / "notes.md").write_text("# M-001\n\n- คนไข้ AF ที่ onset ตอนกลางคืนมักมาถึงช้า\n- glucose แรกรับอาจสัมพันธ์กับ outcome\n",
                                 encoding="utf-8")
    rw_io.write_yaml(m2 / "meeting.yaml", {
        "id": "M-002", "type": "advisor-review", "date": "2026-10-10",
        "participants": [{"role": "advisor", "name": None}], "agenda": ["progress"], "prep_questions": [],
        "notes_file": "notes.md", "transcript_file": None, "logged": True})
    (m2 / "notes.md").write_text("# M-002\n\n- อย่าใช้ accuracy เพราะ class imbalance\n", encoding="utf-8")
    rw_io.write_jsonl(ws / P["observations"], [
        {"id": "O-001", "meeting_id": "M-001", "speaker_role": "clinician",
         "statement": "คนไข้ AF ที่ onset ตอนกลางคืนมักมาถึงช้า", "form": "verbatim",
         "basis": "clinical-experience", "source_ref": "notes.md:3", "confirmed_by_user": True, "recorded_at": T},
        {"id": "O-002", "meeting_id": "M-001", "speaker_role": "clinician",
         "statement": "Admission glucose may relate to outcome", "form": "paraphrase",
         "basis": "clinical-experience", "source_ref": "notes.md:4", "confirmed_by_user": True, "recorded_at": T},
    ])
    rw_io.write_jsonl(ws / P["comments"], [
        {"id": "K-001", "meeting_id": "M-002", "target": "X-001",
         "text": "อย่าใช้ accuracy เพราะ class imbalance ใช้ AUROC/AUPRC", "severity": "must",
         "status": "addressed", "resolution": "primary metric switched to AUROC", "changed_ids": ["X-001"],
         "deferred_until": None, "source_ref": "notes.md:3", "confirmed_by_user": True, "updated_at": T},
        {"id": "K-002", "meeting_id": "M-002", "target": "general",
         "text": "คุยกับหมอเรื่องนิยาม label 90-day mRS", "severity": "consider", "status": "open",
         "resolution": None, "changed_ids": [], "deferred_until": None, "source_ref": "notes.md:3",
         "confirmed_by_user": True, "updated_at": T},
    ])
    rw_io.write_yaml(ws / P["hypotheses"], {"schema_version": 1, "hypotheses": [
        {"id": "H-001", "rq_id": "RQ-1",
         "statement": "Adding admission NIHSS to age and sex improves AUROC for 90-day poor outcome",
         "origin": "literature", "based_on": ["E-001", "E-002"], "literature_checks": ["Q-002"],
         "status": "approved", "rationale": "Consistent association in S-001"},
        {"id": "H-002", "rq_id": "RQ-1",
         "statement": "Night-time onset in AF patients is associated with longer onset-to-door time",
         "origin": "expert", "based_on": ["O-001"], "literature_checks": ["Q-003"],
         "status": "approved", "rationale": "Clinician observation M-001"},
    ]})
    x1 = ws / "experiments" / "X-001"
    rw_io.write_yaml(x1 / "spec.yaml", {
        "id": "X-001", "hypothesis_id": "H-001", "objective": "Test H-001 on the registry",
        "dataset": {"name": "stroke-registry", "version": "2026-09", "path": "data/registry.csv"},
        "split": "patient-level 70/15/15 stratified", "metrics": ["auroc", "f1"], "primary_metric": "auroc",
        "seeds": [1, 2, 3], "analysis_plan": "bootstrap 95% CI on test split",
        "baselines": ["age+sex logistic regression"], "status": "running"})
    rw_io.write_jsonl(x1 / "runs.jsonl", [
        {"run_id": "RUN-001", "experiment_id": "X-001", "started_at": T, "status": "ok",
         "code_commit": "abc1234", "environment": "python 3.11", "params": {"model": "logreg"},
         "metrics": {"auroc": 0.81, "f1": 0.62}, "notes": None},
        {"run_id": "RUN-002", "experiment_id": "X-001", "started_at": T, "status": "failed",
         "code_commit": "abc1234", "environment": "python 3.11", "params": {"model": "xgb"},
         "metrics": {}, "notes": "out of memory"},
    ])
    rw_io.write_jsonl(x1 / "results.jsonl", [
        {"id": "R-001", "experiment_id": "X-001", "run_id": "RUN-001", "metric": "auroc", "value": 0.81,
         "ci": [0.78, 0.84], "split": "test", "summary": "NIHSS model AUROC on test"},
        {"id": "R-002", "experiment_id": "X-001", "run_id": "RUN-001", "metric": "f1", "value": 0.62,
         "ci": None, "split": "test", "summary": "F1 at 0.5 threshold"},
    ])
    rw_io.write_jsonl(ws / P["claims"], [
        {"id": "C-001", "text": "Admission NIHSS is associated with poor 90-day outcome", "cites": ["E-001"],
         "support_level": "literature", "section": "Background"},
        {"id": "C-002", "text": "Our NIHSS model reached AUROC 0.81 (95% CI 0.78-0.84)", "cites": ["R-001"],
         "support_level": "experimental", "section": "Results"},
        {"id": "C-003", "text": "Clinicians observe late arrival in AF patients with night onset",
         "cites": ["O-001"], "support_level": "expert-opinion", "section": "Discussion"},
        {"id": "C-004", "text": "Published and our results are in a similar range", "cites": ["E-003", "R-002"],
         "support_level": "mixed", "section": "Discussion"},
    ])
    (ws / P["report"]).write_text(
        "# Report\n\nNIHSS matters [C-001]. AUROC 0.81 [C-002].\n"
        "ผู้เชี่ยวชาญให้ความเห็นว่า... [C-003]. Similar range [C-004].\n", encoding="utf-8")
    rw_io.write_jsonl(ws / P["doi_verification"], [
        {"id": "S-001", "doi": "10.1000/s001", "status": "verified", "detail": "", "checked_at": T},
        {"id": "S-002", "doi": "10.1000/s002", "status": "verified", "detail": "", "checked_at": T},
    ])
    rw_io.write_json(ws / P["audit"], {"generated_at": T, "automated_issues": [], "claim_reviews": [
        {"claim_id": c, "verdict": "PASS", "note": None, "reviewed_at": T}
        for c in ("C-001", "C-002", "C-003", "C-004")]})
    return ws
