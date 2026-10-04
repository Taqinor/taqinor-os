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

AGR109 — LE MOTEUR A DÉMÉNAGÉ dans le noyau pur ``core.pompage``
(``hydraulique``, ``selection``, ``volumes``), partagé par ventes ET calepinage.
Ce module garde des RÉ-EXPORTS (appelants inchangés, comportement
octet-identique) et ne porte plus en propre que :func:`pompage_mensuel_pvgis`,
qui lit PVGIS (une app Django) et ne peut donc pas vivre dans le noyau.
"""
from __future__ import annotations

from core.pompage.hydraulique import (  # noqa: F401 — ré-exports AGR109
    _CHAMPS_PUITS_REQUIS,
    _debit_a_hmt,
    _flottant,
    debit_a_hmt,
    hmt_puits_iteree,
)
from core.pompage.selection import (  # noqa: F401 — ré-exports AGR109
    TENSION_MONO_V,
    TENSION_TRI_V,
    _RE_TENSION_MONO,
    _RE_TENSION_TRI,
    _a_prix,
    _tension_alim,
    selection_pompe,
    selection_variateur,
    tension_produit,
)
from core.pompage.volumes import (  # noqa: F401 — ré-exports AGR109
    JOURS_PAR_MOIS,
    couverture_besoin_eau,
    pumping_cycle_yield,
)


# ═══════════════════════════════════════════════════════════════════════════
# CAL157 — m³/jour PAR MOIS depuis l'irradiance PVGIS RÉELLE du site.
# ═══════════════════════════════════════════════════════════════════════════

def pompage_mensuel_pvgis(*, debit_hmt_m3h, pumping_hours=None, ville=None,
                          lat=None, lon=None, jours_par_mois=None):
    """CAL157 — 12 volumes mensuels pondérés par l'irradiation PVGIS RÉELLE
    du site (au lieu du m³/jour PLAT × jours du mois), en ALIMENTANT
    ``apps.ventes.solar_design.pumping_cycle_yield`` (jamais un second
    calcul de volume) via son paramètre ``monthly_irradiation_factor``.

    Source d'irradiation : ``apps.parametres.pvgis_profils.productible_mensuel``
    — le client PVGIS EXISTANT (live au point GPS, sinon table de la ville
    reconnue, sinon ancre la plus proche ; JAMAIS une saisonnalité inventée).
    Les facteurs mensuels sont l'``E_m`` de chaque mois RAPPORTÉ À LA MOYENNE
    annuelle (un mois deux fois plus ensoleillé que la moyenne pompe deux fois
    plus, à débit nominal égal).

    LE CALCUL PLAT HISTORIQUE RESTE PUBLIÉ, JAMAIS REMPLACÉ EN SILENCE
    (CLAUDE.md) — ``m3_mois_plat`` ET ``m3_mois_pvgis`` sortent tous les
    deux, avec l'écart mois par mois.

    PVGIS indisponible pour ce site (pas de coordonnées ET ville non
    reconnue) ⇒ ``m3_mois_pvgis``/``source_irradiation`` valent ``None``,
    warning explicite ; le m³/jour plat reste calculé et publié (jamais un
    résultat vide faute d'irradiation).
    """
    from apps.parametres.pvgis_profils import productible_mensuel

    plat = pumping_cycle_yield(debit_hmt_m3h=debit_hmt_m3h,
                               pumping_hours=pumping_hours,
                               days_in_month=jours_par_mois)

    resultat_pvgis = productible_mensuel(ville=ville, lat=lat, lon=lon)
    if resultat_pvgis is None:
        return {
            'm3_jour_plat': plat['daily_m3'],
            'm3_mois_plat': plat['monthly_m3'],
            'm3_mois_pvgis': None,
            'source_irradiation': None,
            'ecart_m3_mois': None,
            'warnings': plat['warnings'] + [
                "irradiation PVGIS indisponible pour ce site (ni coordonnées "
                "ni ville reconnue) — m³/jour reste le calcul plat (débit × "
                "heures), aucune pondération mensuelle publiée"],
        }
    valeurs_e_m, source = resultat_pvgis
    moyenne = sum(valeurs_e_m) / len(valeurs_e_m) if valeurs_e_m else 0.0
    facteurs = ([v / moyenne for v in valeurs_e_m] if moyenne
                else [1.0] * 12)

    pondere = pumping_cycle_yield(debit_hmt_m3h=debit_hmt_m3h,
                                  pumping_hours=pumping_hours,
                                  days_in_month=jours_par_mois,
                                  monthly_irradiation_factor=facteurs)

    ecarts = None
    if plat['monthly_m3'] is not None and pondere['monthly_m3'] is not None:
        ecarts = [round(pondere['monthly_m3'][i] - plat['monthly_m3'][i], 1)
                  for i in range(12)]

    return {
        'm3_jour_plat': plat['daily_m3'],
        'm3_mois_plat': plat['monthly_m3'],
        'm3_mois_pvgis': pondere['monthly_m3'],
        'source_irradiation': source,
        'ecart_m3_mois': ecarts,
        'warnings': plat['warnings'] + pondere['warnings'],
    }
