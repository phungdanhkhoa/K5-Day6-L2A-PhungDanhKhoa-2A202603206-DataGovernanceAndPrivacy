"""Offline T02 raw-image quality triage."""

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import laplacian_variance, to_gray
from .common.manifest import verify_manifest
from .common.review import apply_overrides, load_review_decisions, make_review_queue, write_review_queue


ACTIONS = {"KEEP", "RECAPTURE", "HOLD"}


def load(ctx: RunContext) -> pd.DataFrame:
    if ctx.track != "t02":
        raise NotImplementedError("This submission implements T02.")
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.is_file() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log("pipeline", "provenance_problems", str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed: {problems[:3]}")
    df = pd.read_csv(ctx.input_dir / "images.csv", dtype=str).fillna("")
    required = ["image_id", "path", "camera_id", "light", "split"]
    if df.empty or set(required) - set(df.columns) or df[required].eq("").any().any():
        raise ValueError("images.csv needs nonempty image_id, path, camera_id, light and split")
    if df.image_id.duplicated().any():
        raise ValueError("Duplicate image_id in images.csv")
    if not df.split.isin(["dev", "eval"]).all() or not df.light.isin(["day", "dusk", "night"]).all():
        raise ValueError("Invalid split or light in images.csv")
    root = ctx.input_dir.resolve()
    listed = set(pd.read_csv(manifest).path) if manifest.is_file() else set(df.path)
    for path in df.path:
        if path not in listed or not (root / path).resolve().is_relative_to(root):
            raise ValueError(f"Image must be listed and inside input root: {path}")
    return df.sort_values("image_id", kind="stable").reset_index(drop=True)


def blockiness(gray: np.ndarray) -> float:
    """Compare absolute gradients crossing JPEG block boundaries with interior gradients."""
    x = np.abs(np.diff(gray, axis=1))
    y = np.abs(np.diff(gray, axis=0))
    if min(gray.shape) <= 8:
        return 0.0
    x_boundary = np.arange(x.shape[1]) % 8 == 7
    y_boundary = np.arange(y.shape[0]) % 8 == 7
    boundary = (x[:, x_boundary].mean() + y[y_boundary, :].mean()) / 2
    interior = (x[:, ~x_boundary].mean() + y[~y_boundary, :].mean()) / 2
    return float(boundary / max(interior, 1.0))


def features(path: Path) -> tuple[np.ndarray, float]:
    try:
        with Image.open(path) as img:
            gray = to_gray(np.asarray(img.convert("RGB")))
    except OSError as exc:
        raise ValueError(f"Cannot decode image {path}") from exc
    return gray, laplacian_variance(gray)


def process(ctx: RunContext, data: pd.DataFrame, *, baseline: bool) -> pd.DataFrame:
    rows = []
    for row in data.itertuples(index=False):
        gray, sharpness = features(ctx.input_dir / row.path)
        if baseline:
            score = ctx.param("baseline_laplacian") / max(sharpness, 1.0)
            defect, detail = "blur", f"Laplacian variance {sharpness:.1f}"
        else:
            cutoff = ctx.param("blur_laplacian").get(row.camera_id, ctx.param("blur_laplacian")["default"])
            exposure = float(gray.mean())
            peak_tile = max(float((tile > 245).mean())
                            for band in np.array_split(gray, min(4, gray.shape[0]), axis=0)
                            for tile in np.array_split(band, min(6, gray.shape[1]), axis=1))
            blocks = blockiness(gray)
            signals = {
                "blur": cutoff / max(sharpness, 1.0),
                "dark": ctx.param("min_mean")[row.light] / max(exposure, 1.0),
                "glare": peak_tile / ctx.param("min_glare_tile_fraction"),
                "compression": blocks / ctx.param("min_block_ratio"),
            }
            # Bounded scores keep one very large signal from dominating by orders of magnitude.
            scores = {name: value / (1.0 + value) for name, value in signals.items()}
            defect = max(scores, key=scores.get)
            score = scores[defect]
            detail = f"Lap={sharpness:.1f}, mean={exposure:.1f}, bright tile={peak_tile:.3f}, block ratio={blocks:.2f}"
        suspect = score >= (1.0 if baseline else 0.5)
        rows.append({
            "score": score, "pred_defect_type": defect if suspect else "none",
            "pred_action": "RECAPTURE" if suspect else "KEEP",
            "reason": f"{defect if suspect else 'below thresholds'} ({detail})",
        })
    return pd.concat([data, pd.DataFrame(rows)], axis=1).sort_values("score", ascending=False, kind="stable")


def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    queue = make_review_queue(
        scored[scored.split == "eval"], "image_id", "score", int(ctx.param("budget", 20)),
        reason_col="reason", action_col="pred_action", slice_col="light", evidence_col="path",
    )
    write_review_queue(queue, ctx.out("review_queue.csv"))
    render_contact_sheet(queue, ctx.out("contact_sheet.html"),
                         image_root=ctx.input_dir, title=f"T02 QC · {ctx.run_name}")
    return queue


def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    path = ctx.output_dir / "review_queue_reviewed.csv"
    final = scored.assign(final_action=scored.pred_action, review_status="outside_queue")
    queued = final.image_id.isin(queue.item_id)
    final.loc[queued, "review_status"] = "pending"
    if not path.exists():
        return final
    decisions = load_review_decisions(path)
    if decisions.item_id.duplicated().any() or not decisions.item_id.isin(queue.item_id).all():
        raise ValueError("Review decisions must have unique item IDs from the current queue")
    suggestions = queue.set_index("item_id").suggested_action
    prior = final.set_index("image_id").final_action
    overrides = []
    for row in decisions.itertuples(index=False):
        status = row.reviewer_decision
        action = row.override_value.strip().upper()
        if not row.review_note.strip() and status in {"edit", "reject", "escalate"}:
            raise ValueError(f"Review decision needs a note for {row.item_id}")
        if status == "edit" and action not in ACTIONS:
            raise ValueError(f"Edit requires KEEP, RECAPTURE or HOLD for {row.item_id}")
        if status == "reject":
            if action and action not in ACTIONS:
                raise ValueError(f"Invalid reject override for {row.item_id}")
            action = action or ("KEEP" if suggestions[row.item_id] == "RECAPTURE" else "RECAPTURE")
        if status == "escalate":
            action = "HOLD"
        if status in {"approve", "skip"}:
            action = prior[row.item_id]
        overrides.append(action)

    # Validate every row before applying or logging any action.
    decisions = decisions.assign(override_value=overrides)
    changes = decisions[decisions.reviewer_decision.isin(["edit", "reject", "escalate"])].copy()
    changes.loc[changes.reviewer_decision == "escalate", "reviewer_decision"] = "edit"
    final = apply_overrides(final, changes, "image_id", "final_action")
    for row in decisions.itertuples(index=False):
        mask = final.image_id == row.item_id
        final.loc[mask, "review_status"] = row.reviewer_decision
        ctx.audit.log(row.reviewer, f"review:{row.reviewer_decision}", row.item_id,
                      before=prior[row.item_id], after=row.override_value, reason=row.review_note,
                      reviewed_at=row.reviewed_at)
    ctx.stats["n_reviewed"] = int((decisions.reviewer_decision != "skip").sum())
    return final


def decide(ctx: RunContext, final: pd.DataFrame, *, baseline: bool) -> Decision:
    evaluated = final[final.split == "eval"]
    pending = int(evaluated.review_status.isin(["pending", "skip"]).sum())
    unresolved = int((evaluated.final_action == "HOLD").sum())
    recaptures = int((evaluated.final_action == "RECAPTURE").sum())
    if baseline:
        status, code, reason = "HOLD", "BASELINE_ONLY", "Single-feature comparator cannot authorize release."
    elif evaluated.empty or pending or unresolved:
        status, code, reason = "HOLD", "REVIEW_PENDING", "Complete the priority queue and resolve escalations."
    elif recaptures:
        status, code, reason = "REWORK", "RECAPTURE_REQUIRED", "Recapture flagged images before release."
    else:
        status, code, reason = "GO", "QC_QUEUE_CLEARED", "Priority queue cleared for this synthetic QC run."
    return Decision(status, code, reason, ctx.config["owner"], scope="t02/eval",
                    evidence=["ranked_review.csv", "review_queue.csv", "audit_log.jsonl"],
                    metrics={"eval_images": len(evaluated), "pending": pending,
                             "unresolved": unresolved, "recaptures": recaptures})


def run(ctx: RunContext, *, baseline: bool = False) -> None:
    data = load(ctx)
    scored = process(ctx, data, baseline=baseline)
    ctx.stats["n_items"] = len(scored)
    ctx.audit.log("pipeline", "ranked", "t02", after={"n": len(scored), "seed": ctx.seed})
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    columns = ["image_id", "score", "pred_defect_type", "pred_action", "final_action",
               "review_status", "split", "light", "camera_id", "path", "reason"]
    final[columns].to_csv(ctx.out("ranked_review.csv"), index=False)
    write_decision(decide(ctx, final, baseline=baseline), ctx.out("decision.json"), ctx.out("decision_log.csv"))
