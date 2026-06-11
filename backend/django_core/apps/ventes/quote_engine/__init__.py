"""Premium quote-PDF engine, vendored from RedaSolar/devis-simulator.

Public API:
  - generate_premium_devis_pdf(devis_id) -> str   (render + store in MinIO)
  - build_quote_data(devis) -> dict               (OS quote -> generator data dict)
  - calculate_savings_roi(kwc, total_sans, total_avec) -> dict
"""
from .builder import build_quote_data, generate_premium_devis_pdf
from .pricing import calculate_savings_roi

__all__ = [
    "build_quote_data",
    "generate_premium_devis_pdf",
    "calculate_savings_roi",
]
