"""Render PDF pages to images and record their dimensions.

Word-level coordinate fidelity is the foundation of the whole system, so we
render at a resolution high enough for accurate reading while staying within
the vision model's high-resolution ceiling (2576px on the long edge).
"""

from __future__ import annotations

from dataclasses import dataclass

import pypdfium2 as pdfium
from PIL import Image

TARGET_LONG_EDGE = 2000  # px; comfortable for reading and for the model
MAX_LONG_EDGE = 2576     # px; the model's high-res coordinate ceiling


@dataclass
class RenderedPage:
    image: Image.Image
    width: int
    height: int
    width_pt: float
    height_pt: float


def render_pdf(pdf_bytes: bytes) -> list[RenderedPage]:
    pdf = pdfium.PdfDocument(pdf_bytes)
    pages: list[RenderedPage] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            w_pt, h_pt = page.get_size()
            long_edge_pt = max(w_pt, h_pt)
            scale = min(TARGET_LONG_EDGE, MAX_LONG_EDGE) / long_edge_pt
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil().convert("RGB")
            pages.append(
                RenderedPage(
                    image=pil,
                    width=pil.width,
                    height=pil.height,
                    width_pt=w_pt,
                    height_pt=h_pt,
                )
            )
    finally:
        pdf.close()
    return pages
