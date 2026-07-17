# flake8: noqa
"""INDUSTRIEL premium renderer — part of the single quote engine.

Selected for ``mode_installation == 'industriel'`` (full/premium format) by
``industriel.renderer`` from ``generate_premium_devis_pdf``, BEFORE the legacy
fall-back and after the agricole block. Renders only — never changes a devis
status (CLAUDE.md rule #4). Reuses ``residential.theme`` for company identity /
fonts / footer. CSS tables only (never flex — see quote_engine/RENDERING_NOTES.md).
"""
