# flake8: noqa
"""TAQINOR quote engine — AGRICOLE (pompage solaire).

AGR310 (D-AGR-2, 02/10/2026) — LE DOCUMENT AGRICOLE DÉDIÉ DE 3 PAGES REVIENT,
réécrit : :mod:`renderer` (``is_agricole`` / ``Unsupported`` /
``render_pdf_bytes``) et :mod:`pages` (P1 l'eau et l'argent, P2 comment ça
marche, P3 équipement, prix, garanties). Toutes ses valeurs viennent de
:func:`synthese.synthese_agricole` — la MÊME fonction que /proposition
(AGR308) — et de la chaîne de totaux canonique du builder. Rendu seul
(règle #4). L'ancien renderer supprimé par QJR236/DV1 (ce7e9f01) n'est PAS
ressuscité : ``economics.py``, ``economics_page.py``, ``constants.py`` et
``cover.py`` restent dans l'historique git.

Le une-page agricole (version courte) reste rendu par le moteur legacy
(``quote_engine/generate_devis_premium.py``).

Modules : :mod:`synthese` (AGR304), :mod:`garanties` (AGR305),
:mod:`mentions` (AGR306), :mod:`schema` (AGR309) et :mod:`agronomy` — le
moteur agronomique v2 (FAO-56, ``ET0_MONTHLY``), lu par
``apps/ventes/public_views.py`` et ``apps/crm/webhooks.py``.
"""
