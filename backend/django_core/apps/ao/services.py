"""Services du module Appels d'offres (``apps.ao``).

ODX11 — ré-export TRANSITOIRE des fonctions de service AO qui vivent encore
physiquement dans ``apps.compta.services`` (elles y étaient interleavées avec la
logique comptable). Ce module donne au reste du code (urls, appelants cross-app)
un point d'accès ``apps.ao.services`` stable ; ODX22 re-logera le corps des
fonctions ici et retirera ce shim.

``ao`` ne lit crm/ventes QUE via leurs selectors/services ou par référence
opaque — jamais leurs ``models`` (les fonctions ré-exportées référencent
``lead_id`` opaque).
"""

from apps.compta.services import (  # noqa: F401
    echeances_ao_dues,
    taux_reussite_ao,
)
