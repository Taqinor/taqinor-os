# flake8: noqa
"""AGRICOLE agronomy — RÉ-EXPORT du moteur FAO-56 du noyau ``core.pompage``.

AGR112 — le moteur agronomique (série MENSUELLE FAO-56, besoin de pointe) a
DÉMÉNAGÉ dans ``core/pompage/agronomie.py`` : la règle #4 veut que le moteur de
devis ne fasse que RENDRE, et un noyau pur se teste sans base. Ce module ne
garde que des ré-exports pour ``apps/ventes/public_views.py``
(``peak_need_m3_day``) et le rendu. Corrections portées par le noyau : profil
Kc mensuel de l'olivier (FAO-56 T12 note 24), culture sans profil ⇒ besoin omis
+ alerte (fin du Kc plat), besoin nommé « agronomique plein », constantes mortes
supprimées. Voir l'en-tête de ``core/pompage/agronomie.py``.
"""
from __future__ import annotations

from core.pompage.agronomie import (
    CROP_CITED,
    CROP_STAGES,
    DAYS_IN_MONTH,
    ET0_MONTHLY,
    ET0_MONTHLY_DEFAUT,
    ET0_SOURCES,
    IRRIGATION_EFFICIENCY,
    IRRIGATION_EFFICIENCY_DEFAUT,
    KC_OLIVIER_MENSUEL,
    NATURE_AGRONOMIQUE,
    RAIN_EFF_DEFAUT,
    RAIN_EFF_MONTHLY,
    _jsround,
    _num,
    annual_water_from_monthly,
    besoin_agronomique,
    crop_kc_monthly,
    monthly_water_demand,
    peak_need_m3_day,
    source_et0,
)
