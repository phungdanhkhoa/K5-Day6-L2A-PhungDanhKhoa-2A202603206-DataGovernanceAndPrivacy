import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


FIXTURE = Path("fixtures/t02_raw_qc")


def run_qc(output, input_dir=FIXTURE):
    return subprocess.run(
        [sys.executable, "-m", "src.main", "--offline", "--seed", "42",
         "--input", str(input_dir), "--output", str(output)],
        capture_output=True, text=True,
    )


def test_offline_ranking_and_review_roundtrip(tmp_path):
    run = run_qc(tmp_path)
    assert run.returncode == 0, run.stderr
    ranked = pd.read_csv(tmp_path / "ranked_review.csv")
    source = pd.read_csv(FIXTURE / "images.csv")
    assert set(ranked.image_id) == set(source.image_id)
    assert ranked.image_id.is_unique and ranked.score.is_monotonic_decreasing
    queue = pd.read_csv(tmp_path / "review_queue.csv", keep_default_na=False)
    expected = ranked[ranked.split == "eval"].head(20).image_id.tolist()
    assert queue.item_id.tolist() == expected
    assert (tmp_path / "contact_sheet.html").read_text().count("data:image/jpeg;base64,") == 20
    assert json.loads((tmp_path / "decision.json").read_text())["status"] == "HOLD"

    queue.loc[0, ["reviewer", "reviewer_decision", "override_value", "review_note"]] = [
        "QA fixture", "edit", "KEEP", "Synthetic override exercise",
    ]
    queue.to_csv(tmp_path / "review_queue_reviewed.csv", index=False)
    rerun = run_qc(tmp_path)
    assert rerun.returncode == 0, rerun.stderr
    final = pd.read_csv(tmp_path / "ranked_review.csv")
    pd.testing.assert_series_equal(ranked.score, final.score)
    assert final.set_index("image_id").loc[queue.item_id.iloc[0], "final_action"] == "KEEP"
    events = [json.loads(line) for line in (tmp_path / "audit_log.jsonl").read_text().splitlines()]
    assert any(event["actor"] == "QA fixture" and event["after"] == "KEEP" for event in events)


def test_tampered_input_fails_closed(tmp_path):
    fixture = tmp_path / "input"
    shutil.copytree(FIXTURE, fixture, ignore=shutil.ignore_patterns("gt"))
    path = fixture / "images.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    output = tmp_path / "out"
    run = run_qc(output, fixture)
    assert run.returncode == 2
    assert "provenance check failed" in run.stderr
    assert not (output / "ranked_review.csv").exists()
