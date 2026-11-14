"""Create an independent, synthetic ten-image stress pack with transform labels."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from src.common.corruptions import blur, dark, glare, jpeg
from src.common.manifest import build_manifest, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("out/stress/input"))
    args = parser.parse_args()
    root = args.output
    (root / "images").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    cases = [
        ("day", "none", 0), ("night", "none", 0), ("dusk", "blur", 1),
        ("day", "blur", 2), ("night", "dark", 1), ("day", "dark", 2),
        ("day", "glare", 2), ("night", "glare", 1),
        ("day", "compression", 1), ("dusk", "compression", 2),
    ]
    transforms = {"blur": blur, "dark": dark, "glare": glare, "compression": jpeg}
    rows, labels = [], []
    for i, (light, defect, severity) in enumerate(cases):
        image_id = f"stress_{i:02}"
        camera = ["cam_A", "cam_B"][i % 2]
        path = f"images/{image_id}.png"
        luma = {"day": 112, "dusk": 75, "night": 24}[light]
        noise = rng.normal(0, 4, (180, 320))
        pixels = np.uint8(np.clip(luma + noise, 0, 255))
        image = Image.fromarray(pixels).convert("RGB")
        draw = ImageDraw.Draw(image)
        for x in range(12, 300, 30):
            y = int(rng.integers(18, 100))
            draw.rectangle((x, y, x + 18, y + 46), outline=(112, 160, 175), width=2)
        draw.rectangle((108, 119, 208, 159), fill=(155, 135, 95), outline=(220, 220, 180))
        draw.text((118, 129), "SYNTHETIC", fill=(29, 29, 29))
        rgb = np.asarray(image)
        if defect != "none":
            rgb = transforms[defect](rgb, severity, rng=rng)
        Image.fromarray(rgb).save(root / path)
        rows.append(dict(image_id=image_id, path=path, camera_id=camera, light=light, split="eval"))
        labels.append(dict(image_id=image_id, light=light, split="eval", defect_type=defect,
                           is_defect=int(defect != "none"), severity=severity))
    pd.DataFrame(rows).to_csv(root / "images.csv", index=False)
    # Labels are outside the input directory and are used only by the evaluator.
    pd.DataFrame(labels).to_csv(root.with_name(f"{root.name}_labels.csv"), index=False)
    write_manifest(build_manifest(root, ["images.csv", *(row["path"] for row in rows)],
                                  "synthetic:tools/t02_stress.py (seed 42)", "CC0-1.0"),
                   root / "manifest.csv")


if __name__ == "__main__":
    main()
