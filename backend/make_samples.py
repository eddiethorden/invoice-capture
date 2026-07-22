"""Generate a batch of varied sample invoices and drop them into the intake
folder, writing the ground-truth map the mock extractor reads.

    backend/.venv/bin/python make_samples.py [N]

Default N = 48. Each invoice has unique content (so a unique fingerprint) and a
recorded ground truth, so in mock mode every one opens with its own data.
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

from app import intake, store
from app.sample_factory import build_records, render

HERE = Path(__file__).resolve().parent


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def main(n: int) -> None:
    incoming = intake.base_dir() / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)

    ground_truth: dict[str, dict] = {}
    records = build_records(n)
    problem_counts: dict[str, int] = {}

    for rec in records:
        img, truth = render(rec)
        buf = io.BytesIO()
        img.save(buf, "PDF", resolution=150.0)
        pdf_bytes = buf.getvalue()

        fp = store.fingerprint(pdf_bytes)
        ground_truth[fp] = truth

        name = f"{slug(rec.supplier.name)}_{rec.number}.pdf"
        (incoming / name).write_bytes(pdf_bytes)
        for p in rec.problems:
            problem_counts[p] = problem_counts.get(p, 0) + 1

    gt_path = HERE / "samples" / "ground_truth.json"
    gt_path.parent.mkdir(exist_ok=True)
    gt_path.write_text(json.dumps(ground_truth))

    print(f"wrote {len(records)} invoices to {incoming}")
    print(f"ground truth: {gt_path} ({len(ground_truth)} entries)")
    print("intentional issues included:", problem_counts)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 48)
