# flake8: noqa
"""TAQINOR quote engine — AGRICOLE (pompage solaire) renderer package.

A premium multi-page proposal for agricultural solar water-pumping quotes,
mirroring the architecture of the sibling ``residential`` package. Selected by
``agricole.renderer.is_agricultural`` from the single quote engine
(``apps/ventes/quote_engine``) for ``mode_installation == "agricole"`` in the
full/premium format. The legacy one-page renderer still serves the agricole
one-page format and is the automatic fall-back, so a client PDF is never broken.

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from .renderer import is_agricultural, render_pdf_bytes, Unsupported  # noqa: F401
