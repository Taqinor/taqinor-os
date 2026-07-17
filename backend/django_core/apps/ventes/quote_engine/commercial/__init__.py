# flake8: noqa
"""COMMERCIAL premium renderer — part of the single quote engine.

Selected for ``mode_installation == 'commercial'`` (full/premium format) by
``commercial.renderer`` from ``generate_premium_devis_pdf``, BEFORE the legacy
fall-back. Renders only — never changes a devis status (CLAUDE.md rule #4).
Category-aware (etude_params.categorie_commerciale, QX44). Reuses
``residential.theme``. CSS tables only (see quote_engine/RENDERING_NOTES.md).
"""
