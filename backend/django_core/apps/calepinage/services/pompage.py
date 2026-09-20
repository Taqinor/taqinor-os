"""CAL155-158 — dimensionnement du pompage solaire, côté module.

CE QUE CE FICHIER NE RECODE PAS
--------------------------------
Le calcul du volume pompé heure par heure existe déjà et reste la SEULE
source : ``apps.ventes.solar_design.pumping_cycle_yield`` (débit × profil
horaire pondéré par l'irradiation, ou mode PLAT débit × heures). Ce module
ne fait qu'ALIMENTER ses paramètres avec des données RÉELLES — besoin en eau
saisi, HMT calculée depuis un puits, facteurs mensuels PVGIS, pompe/variateur
assortis — jamais un second calcul de volume.

ZÉRO CHIFFRE INVENTÉ (CLAUDE.md)
----------------------------------
Chaque fonction de ce fichier documente sa source : ``saisie`` (l'utilisateur
a tapé la valeur), ``fiche`` (la fiche technique/catalogue du produit),
``pvgis`` (l'irradiation réelle du site) — jamais une valeur par défaut
inventée. Une donnée manquante fait tomber le résultat vers ``None`` (la
carte correspondante disparaît côté écran), jamais vers 0 ni vers une
hypothèse tacite.

Fonctions PURES (pas de requête, pas d'écriture) : les appelants (vues,
sélecteurs) construisent les entrées depuis ``apps.stock.selectors`` et
``apps.parametres.pvgis_profils``, jamais l'inverse.
"""
from __future__ import annotations

#: Tensions standard du catalogue pompage (CLAUDE.md « Pompage sizing »).
TENSION_MONO_V = 220
TENSION_TRI_V = 380


def _flottant(valeur, defaut=None):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


# ═══════════════════════════════════════════════════════════════════════════
# CAL155 — besoin en eau journalier/mensuel + réservoir + autonomie
# ═══════════════════════════════════════════════════════════════════════════

#: Jours par mois (année non bissextile) — même convention que
#: ``apps.ventes.solar_design._DAYS_IN_MONTH``, dupliquée ici en tant que
#: CONSTANTE PURE (pas d'import croisé pour une liste de 12 entiers connus).
JOURS_PAR_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def couverture_besoin_eau(*, besoin_m3_jour=None, besoin_m3_mois=None,
                          volume_reservoir_m3=None, production_m3_mois=None,
                          jours_par_mois=None):
    """CAL155 — couverture du besoin en eau MOIS PAR MOIS + autonomie réservoir.

    ``besoin_m3_jour`` : besoin JOURNALIER constant (m³/j), SAISI par
    l'utilisateur — sert de repli pour tout mois sans valeur mensuelle
    explicite.
    ``besoin_m3_mois`` : liste de 12 besoins MENSUELS SAISIS (m³/mois),
    ``None`` à un index = pas de saisie mensuelle pour ce mois-là (repli sur
    ``besoin_m3_jour``). Les deux peuvent se combiner (saisonnalité connue
    certains mois seulement).
    ``production_m3_mois`` : les 12 volumes PRODUITS (typiquement
    ``pumping_cycle_yield(...)['monthly_m3']`` ou le résultat pondéré PVGIS
    de :func:`pompage_mensuel_pvgis`).

    AUCUN besoin saisi (ni journalier ni mensuel) ⇒ ``besoin_m3_mois`` et
    ``couverture_pct_mois`` valent ``None`` — « besoin non saisi ⇒ aucun taux
    de couverture publié » (CLAUDE.md, zéro chiffre inventé : publier un taux
    contre un besoin supposé mentirait).

    Rend ``{besoin_m3_mois: [12]|None, couverture_pct_mois: [12]|None,
    autonomie_jours: float|None, besoin_source: 'saisie'|None}``.
    """
    jours = list(jours_par_mois) if jours_par_mois and len(jours_par_mois) == 12 \
        else list(JOURS_PAR_MOIS)
    besoin_jour = _flottant(besoin_m3_jour)
    mensuel_saisi = list(besoin_m3_mois) if besoin_m3_mois and len(besoin_m3_mois) == 12 \
        else [None] * 12

    besoin_effectif = []
    for mois in range(12):
        valeur_mois = _flottant(mensuel_saisi[mois])
        if valeur_mois is not None:
            besoin_effectif.append(valeur_mois)
        elif besoin_jour is not None:
            besoin_effectif.append(besoin_jour * jours[mois])
        else:
            besoin_effectif.append(None)

    if all(v is None for v in besoin_effectif):
        return {
            'besoin_m3_mois': None,
            'couverture_pct_mois': None,
            'autonomie_jours': None,
            'besoin_source': None,
        }

    production = list(production_m3_mois) if production_m3_mois and len(
        production_m3_mois) == 12 else [None] * 12
    couverture = []
    for mois in range(12):
        besoin = besoin_effectif[mois]
        prod = _flottant(production[mois])
        if besoin is None or besoin <= 0 or prod is None:
            couverture.append(None)
        else:
            couverture.append(round(prod / besoin * 100, 1))

    autonomie = None
    reservoir = _flottant(volume_reservoir_m3)
    if reservoir is not None and reservoir > 0:
        # Référence d'autonomie : le besoin journalier SAISI s'il existe,
        # sinon la moyenne des besoins mensuels effectivement saisis/déduits
        # (jamais une hypothèse — dérivée directement de ce que l'utilisateur
        # a tapé).
        reference = besoin_jour
        if reference is None:
            valeurs = [v for v in besoin_effectif if v is not None]
            moyenne_mois = sum(valeurs) / len(valeurs) if valeurs else None
            reference = (moyenne_mois / (sum(jours) / 12)
                         if moyenne_mois is not None else None)
        if reference is not None and reference > 0:
            autonomie = round(reservoir / reference, 1)

    return {
        'besoin_m3_mois': [round(v, 2) if v is not None else None
                           for v in besoin_effectif],
        'couverture_pct_mois': couverture,
        'autonomie_jours': autonomie,
        'besoin_source': 'saisie',
    }
