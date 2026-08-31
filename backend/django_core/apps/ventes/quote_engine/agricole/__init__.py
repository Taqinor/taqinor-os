# flake8: noqa
"""TAQINOR quote engine — AGRICOLE : le moteur AGRONOMIQUE, et lui seul.

QJR236 (décision fondateur DV1 du 30/08/2026) — LE RENDERER PREMIUM
MULTI-PAGES A ÉTÉ SUPPRIMÉ. Depuis que le dispatch lit le ``pdf_mode``
NORMALISÉ (QJR32), il était INJOIGNABLE : ``build_quote_data`` dégrade PAR
CONCEPTION toute demande agricole « full » en une page (le format à options n'a
pas de sens sans onduleur), donc aucune entrée ne pouvait plus le sélectionner
et ce format avait silencieusement cessé d'être livré. Le une-page sert seul
depuis juin ; la résurrection reste possible par ``git``.

CE QUI RESTE, ET QUI EST VIVANT : :mod:`agronomy` — le moteur agronomique v2
(FAO-56, série mensuelle, ``ET0_MONTHLY``). Il n'a jamais appartenu au
renderer : il est lu par ``apps/ventes/public_views.py`` (``peak_need_m3_day``)
et sa table ``ET0_MONTHLY`` est citée par ``apps/crm/webhooks.py``.

Le PDF agricole une-page est rendu par le moteur legacy
(``quote_engine/generate_devis_premium.py``), inchangé.
"""
