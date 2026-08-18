"""Premium quote-PDF engine, vendored from RedaSolar/devis-simulator.

Public API:
  - generate_premium_devis_pdf(devis_id, pdf_options=None) -> str
        render + store in MinIO; pdf_options picks the simulator format
        (full 3-page premium / one-page, monthly-chart and devis-final flags)
  - build_quote_data(devis, pdf_options=None) -> dict
  - clean_pdf_options(raw) -> dict                (whitelist client options)
  - cle_pdf_a_jour(devis, pdf_options=None) -> str
        PVFRESH — clé MinIO GARANTIE à jour : réutilise le fichier stocké quand
        son empreinte de données correspond encore, le re-rend sinon
  - calculate_savings_roi(kwc, total_sans, total_avec) -> dict
"""
from .builder import (
    build_quote_data,
    clean_pdf_options,
    cle_pdf_a_jour,
    empreinte_donnees_pdf,
    generate_premium_devis_pdf,
)
from .pricing import calculate_savings_roi

__all__ = [
    "build_quote_data",
    "clean_pdf_options",
    "cle_pdf_a_jour",
    "empreinte_donnees_pdf",
    "generate_premium_devis_pdf",
    "calculate_savings_roi",
]
