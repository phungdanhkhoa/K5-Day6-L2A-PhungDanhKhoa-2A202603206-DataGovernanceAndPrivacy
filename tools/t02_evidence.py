"""Generate local T02 evaluation and replay a disclosed visual review."""

import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.common.io import read_json
from src.common.review import AuditLog


EVIDENCE = Path("reports/evidence")
ROOT = Path("out/evidence")
GOLD = Path("reports/t02_visual_gold.csv")
TRACK = ["--track", "t02"]
COMMON = TRACK + ["--offline", "--seed", "42"]


def call(module, *args):
    subprocess.run([sys.executable, "-m", module, *map(str, args)], check=True)


def review_poc(output: Path, gold: pd.DataFrame) -> None:
    queue = pd.read_csv(output / "review_queue.csv", keep_default_na=False)
    joined = queue.join(gold.set_index("image_id"), on="item_id", validate="one_to_one")
    for row in joined.itertuples():
        action = "RECAPTURE" if row.is_defect else "KEEP"
        queue.loc[row.Index, ["reviewer", "reviewer_decision", "override_value", "review_note"]] = [
            "Codex visual assessment (AI)",
            "approve" if action == row.suggested_action else "edit",
            "" if action == row.suggested_action else action,
            f"Visual gold: {row.defect_type}. Demonstration replay. Human sign-off pending.",
        ]
    queue.to_csv(output / "review_queue_reviewed.csv", index=False)
    queue.to_csv(EVIDENCE / "review_queue_reviewed.csv", index=False)


def main() -> None:
    # A fresh directory keeps previous review runs out of the benchmark.
    output = ROOT
    suffix = 1
    while output.exists():
        output = ROOT.with_name(f"{ROOT.name}-{suffix}")
        suffix += 1
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    gold = pd.read_csv(GOLD)
    for name in ("baseline", "poc"):
        destination = output / name
        module = "src.t02_baseline" if name == "baseline" else "src.pipeline"
        call("src.main", *COMMON, "--pipeline", module, "--run-name", name, "--output", destination)
        pred = destination / "ranked_review.csv"
        call("src.evaluate", *TRACK, "--gt", GOLD, "--pred", pred, "--run-name", name,
             "--out", f"reports/metrics_{name}.json")
        (EVIDENCE / f"{name}_run_info.json").write_bytes((destination / "run_info.json").read_bytes())
        predictions = pd.read_csv(pred)
        if name == "poc":
            review_poc(destination, gold)
            call("src.main", *COMMON, "--output", destination)
            reviewed = pd.read_csv(pred)
            pd.testing.assert_frame_equal(reviewed[["image_id", "score"]], predictions[["image_id", "score"]])
            events = AuditLog(destination / "audit_log.jsonl").read()
            reviewed_events = [event for event in events if event["action"].startswith("review:")]
            assert len(reviewed_events) == 20
            assert read_json(destination / "decision.json")["status"] == "REWORK"
            for filename in ("audit_log.jsonl", "decision_log.csv", "decision.json",
                             "ranked_review.csv", "review_queue.csv"):
                (EVIDENCE / filename).write_text((destination / filename).read_text(encoding="utf-8"),
                                                 encoding="utf-8")
            Path("demo/contact_sheet.html").write_bytes((destination / "contact_sheet.html").read_bytes())
        else:
            (EVIDENCE / "baseline_ranked_review.csv").write_bytes(pred.read_bytes())
    call("src.compare", "reports/metrics_baseline.json", "reports/metrics_poc.json",
         "--out", "reports/table1_baseline_vs_poc.md")

    stress = output / "stress" / "input"
    call("tools.t02_stress", "--output", stress)
    labels = pd.read_csv(stress.with_name("input_labels.csv"))
    results = labels.copy()
    for name, pipeline in (("baseline", "src.t02_baseline"), ("poc", "src.pipeline")):
        dest = stress.parent / name
        call("src.main", *COMMON, "--input", stress, "--pipeline", pipeline, "--output", dest)
        pred = pd.read_csv(dest / "ranked_review.csv")
        results = results.merge(pred[["image_id", "pred_action", "pred_defect_type"]].rename(
            columns={"pred_action": f"{name}_action", "pred_defect_type": f"{name}_type"}),
            on="image_id", validate="one_to_one")
    assert len(results) == len(labels) == 10
    results.to_csv(EVIDENCE / "stress_results.csv", index=False)


if __name__ == "__main__":
    main()
