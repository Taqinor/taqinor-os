"""AGR109 — volumes d'eau pompés (noyau pur ``core.pompage``).

* :func:`pumping_cycle_yield` et :func:`clearsky_hourly_irradiance` (FG264)
  DÉPLACÉES telles quelles depuis ``apps/ventes/solar_design.py`` ;
* :func:`couverture_besoin_eau` (CAL155) DÉPLACÉE telle quelle depuis
  ``apps/calepinage/services/pompage.py``.

Comportement OCTET-IDENTIQUE ; les deux modules d'origine gardent des
ré-exports. Les tables de module sont des TUPLES (noyau pur : aucune globale
mutable).

Noyau PUR : stdlib seulement, aucune dépendance Django, aucune I/O.
"""
from __future__ import annotations

import math

from core.pompage.hydraulique import _flottant

#: Libellés des mois (mêmes valeurs que ``apps.ventes.solar_design._MONTHS_FR``).
_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


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


# ── FG264 — Rendement pompage par cycle de marche (volume d'eau jour/mois) ─────
# Pour les devis AGRICOLES (pompage solaire) : calcule le VOLUME D'EAU POMPÉ
# journalier et mensuel en fonction de l'IRRADIATION HORAIRE et de la DURÉE de
# pompage. C'est l'extension physique du m³/jour « plat » existant
# (``solar.js`` : ``m3_jour = débit@HMT × heures``, stocké une fois dans
# ``etude_params``) : la pompe solaire suit la puissance du champ, qui suit
# l'irradiation. Au lever/coucher l'irradiation est faible → le débit l'est
# aussi ; à midi l'irradiation est maximale → débit nominal. Le volume d'une
# JOURNÉE n'est donc pas exactement ``débit × heures`` mais l'intégrale du débit
# horaire, pondéré par l'irradiation de chaque heure de la fenêtre de pompage.
#
# Module PUR (aucune base, aucun réseau, aucun prix) :
#   * ``débit@HMT`` (m³/h) vient de la courbe constructeur (même grandeur que
#     ``debitAtHmt`` côté frontend) — JAMAIS fabriqué : sur une pompe sans
#     courbe le débit est None et la routine renvoie un volume None (on n'invente
#     pas de m³/jour, exactement comme l'écran/PDF one-page).
#   * deux entrées possibles, au choix de l'appelant :
#       (a) un PROFIL D'IRRADIATION HORAIRE (liste de W/m² ou de fractions par
#           heure) — chaque heure pompe ``débit × (irr_heure / irr_pic)`` bornée
#           au débit nominal, seulement si l'heure est dans la fenêtre de pompage
#           et au-dessus du seuil de démarrage ;
#       (b) à défaut, l'IRRADIATION JOURNALIÈRE (kWh/m²/j, « heures de soleil
#           plein-équivalent ») + la DURÉE de pompage : on retombe alors sur le
#           modèle plat ``débit × heures`` — STRICTEMENT identique au calcul
#           existant, donc rétro-compatible.
#   * volume MENSUEL = volume journalier × nombre de jours du mois (par défaut
#     les 12 longueurs réelles ; un facteur saisonnier d'irradiation optionnel
#     module chaque mois sans jamais changer la base journalière par défaut).
#
# La liberté de saisie du founder est préservée : AUCUNE valeur n'est rejetée ;
# les valeurs illisibles/négatives sont ramenées à 0, toute division est bornée,
# jamais d'exception. Le shape ``etude_params`` n'est PAS modifié ici (clés
# additives uniquement chez l'appelant) — cette fonction ne fait que le CALCUL.

# Forme horaire d'irradiation « ciel clair » type (24 valeurs, fractions de
# l'irradiation journalière). Cloche centrée sur midi : ~0 la nuit, pic ~13 h.
# Somme ≈ 1.0 (fractions du total journalier). Sert de profil par défaut quand
# l'appelant ne fournit qu'une irradiation journalière mais veut quand même la
# répartition horaire (mode profil avec ``hourly_irradiance=None``).
_CLEARSKY_HOURLY_SHAPE = (
    0.0, 0.0, 0.0, 0.0, 0.0, 0.005,
    0.018, 0.038, 0.062, 0.085, 0.103, 0.116,
    0.122, 0.118, 0.106, 0.088, 0.064, 0.040,
    0.020, 0.005, 0.0, 0.0, 0.0, 0.0,
)

# Nombre de jours par mois (année non bissextile) — base du passage jour → mois.
_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# Seuil de démarrage par défaut : fraction de l'irradiation de pic en-dessous de
# laquelle la pompe ne démarre pas (champ trop faible pour vaincre la HMT).
_PUMP_START_IRRADIANCE_FRACTION = 0.15


def _safe_float(value, default=0.0):
    """Float tolérant : illisible → ``default`` (jamais d'exception)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def clearsky_hourly_irradiance(daily_irradiation_kwh_m2):
    """Répartit une irradiation JOURNALIÈRE sur la forme « ciel clair » 24 h.

    Renvoie une liste de 24 valeurs (kWh/m² par heure) dont la somme vaut
    l'irradiation journalière, en cloche centrée sur midi. Sert de profil horaire
    par défaut quand l'appelant n'a que le total journalier mais veut le rendement
    par cycle de marche. Tolérant : entrée illisible/négative → profil nul.
    """
    di = max(0.0, _safe_float(daily_irradiation_kwh_m2, 0.0))
    # Normalise la forme pour que la somme du profil vaille EXACTEMENT
    # l'irradiation journalière (la forme de référence peut ne pas sommer
    # à 1.0 à l'arrondi près) — garantit « somme du profil = irradiation ».
    total = sum(_CLEARSKY_HOURLY_SHAPE) or 1.0
    return [round(di * frac / total, 5) for frac in _CLEARSKY_HOURLY_SHAPE]


def pumping_cycle_yield(*, debit_hmt_m3h, pumping_hours=None,
                        hourly_irradiance=None,
                        daily_irradiation_kwh_m2=None,
                        start_irradiance_fraction=_PUMP_START_IRRADIANCE_FRACTION,
                        days_in_month=None,
                        monthly_irradiation_factor=None):
    """FG264 — volume d'eau pompé jour/mois selon irradiation horaire + durée.

    Étend le m³/jour « plat » des devis pompage (``débit@HMT × heures``) en
    intégrant le débit HEURE PAR HEURE pondéré par l'irradiation : une pompe
    solaire ne délivre son débit nominal qu'au pic d'ensoleillement ; aux heures
    creuses elle pompe moins.

    Paramètres
    ----------
    debit_hmt_m3h : débit délivré à la HMT (m³/h), issu de la courbe pompe. Si
        None / illisible / ≤ 0 (pompe sans courbe), le volume est None — on
        N'INVENTE PAS de m³/jour (parité avec l'écran/PDF one-page).
    pumping_hours : durée de pompage (h). Utilisée en mode PLAT (sans profil
        horaire) — ``volume_jour = débit × heures`` (rétro-compatible), et pour
        BORNER la fenêtre de pompage en mode profil (les heures les plus
        ensoleillées sont retenues à concurrence de cette durée).
    hourly_irradiance : profil d'irradiation horaire (liste de W/m² ou de
        fractions). Si fourni, le débit de chaque heure = ``débit ×
        (irr_heure / irr_pic)`` borné au débit nominal, et seules les heures
        au-dessus du seuil de démarrage comptent. Une liste de 24 valeurs = une
        journée type ; toute longueur est acceptée. Valeur spéciale
        ``"clearsky"`` : construit le profil 24 h par défaut à partir de
        ``daily_irradiation_kwh_m2`` (forme ciel clair centrée sur midi).
    daily_irradiation_kwh_m2 : irradiation journalière (kWh/m²/j ≈ heures de
        soleil plein-équivalent). En l'absence de ``hourly_irradiance`` ET de
        ``pumping_hours``, sert de durée plein-soleil-équivalente (``débit ×
        irradiation``). N'écrase jamais ``pumping_hours`` si celui-ci est donné.
    start_irradiance_fraction : seuil de démarrage (fraction du pic) en mode
        profil — sous ce seuil l'heure ne pompe pas.
    days_in_month : liste de 12 entiers (jours par mois) ; défaut = année réelle.
    monthly_irradiation_factor : liste de 12 facteurs multipliant le volume
        journalier mois par mois (saisonnalité d'irradiation). Défaut 1.0 partout
        → ``volume_mois = volume_jour × jours_du_mois``.

    Retourne un dict JSON-sérialisable ::

        {daily_m3, monthly_m3: [12], annual_m3, mode, peak_hour_index,
         effective_pumping_hours, daily_by_hour: [...]|None, warnings: []}

    ``daily_m3`` (et tout le reste) vaut None si le débit est inconnu — jamais
    de chiffre fabriqué. Ne lève jamais sur entrées dégradées.
    """
    warnings = []

    debit = _safe_float(debit_hmt_m3h, 0.0)
    if debit <= 0:
        # Pompe sans courbe / débit non renseigné : on n'invente RIEN.
        warnings.append(
            "débit à la HMT inconnu — volume d'eau non calculé (pompe sans "
            "courbe constructeur)")
        return {
            "daily_m3": None,
            "monthly_m3": None,
            "annual_m3": None,
            "mode": "unknown",
            "peak_hour_index": None,
            "effective_pumping_hours": None,
            "daily_by_hour": None,
            "warnings": warnings,
        }

    hours = None
    if pumping_hours is not None:
        h = _safe_float(pumping_hours, 0.0)
        hours = h if h > 0 else 0.0

    # Sentinelle « clearsky » : construire le profil horaire par défaut à partir
    # de l'irradiation journalière (forme ciel clair centrée midi).
    if hourly_irradiance == "clearsky":
        hourly_irradiance = clearsky_hourly_irradiance(daily_irradiation_kwh_m2)

    daily_by_hour = None
    peak_hour_index = None

    # ── Mode PROFIL : intégrale horaire du débit pondéré par l'irradiation ──
    if hourly_irradiance is not None:
        mode = "hourly"
        # Irradiations horaires lues, négatif/illisible → 0 (jamais de rejet).
        irr = [max(0.0, _safe_float(v, 0.0)) for v in hourly_irradiance]
        peak = max(irr) if irr else 0.0
        if peak <= 0:
            warnings.append(
                "profil d'irradiation horaire nul — volume journalier nul")
            daily = 0.0
            daily_by_hour = [0.0] * len(irr)
            effective_hours = 0.0
        else:
            peak_hour_index = irr.index(peak)
            thr_frac = _safe_float(start_irradiance_fraction,
                                   _PUMP_START_IRRADIANCE_FRACTION)
            thr_frac = min(max(thr_frac, 0.0), 1.0)
            threshold = peak * thr_frac
            # Débit de chaque heure = débit nominal × (irr/pic), borné [0, débit],
            # nul si sous le seuil de démarrage.
            per_hour = []
            for v in irr:
                if v < threshold:
                    per_hour.append(0.0)
                else:
                    per_hour.append(min(debit, debit * (v / peak)))
            # Fenêtre de pompage : si une durée est imposée, on ne garde que les
            # ``hours`` heures les plus productives (les plus ensoleillées).
            if hours is not None and hours > 0 and hours < len([
                    x for x in per_hour if x > 0]):
                order = sorted(range(len(per_hour)),
                               key=lambda i: per_hour[i], reverse=True)
                keep = set(order[:int(math.ceil(hours))])
                # Heure partielle de bord : fraction de la dernière heure gardée.
                frac = hours - math.floor(hours)
                per_hour = [
                    (per_hour[i] if i in keep else 0.0) for i in range(
                        len(per_hour))]
                if 0 < frac < 1 and order:
                    last = order[int(math.ceil(hours)) - 1]
                    per_hour[last] *= frac
            daily_by_hour = [round(x, 4) for x in per_hour]
            daily = sum(per_hour)
            effective_hours = round(
                sum(1.0 for x in per_hour if x > 0), 2)
        daily_m3 = round(daily, 2)
        effective_pumping_hours = effective_hours

    # ── Mode PLAT : débit × durée (strictement le calcul existant) ──
    else:
        mode = "flat"
        if hours is None or hours <= 0:
            # Pas de durée : on retombe sur l'irradiation journalière comme
            # nombre d'heures plein-soleil-équivalentes (kWh/m²/j ≈ h_équiv).
            di = _safe_float(daily_irradiation_kwh_m2, 0.0)
            hours = di if di > 0 else 0.0
            if hours > 0:
                mode = "irradiation_equiv"
            else:
                warnings.append(
                    "ni durée de pompage ni irradiation journalière — volume "
                    "journalier nul")
        daily_m3 = round(debit * hours, 2)
        effective_pumping_hours = round(hours, 2)

    # ── Passage jour → mois (× jours du mois, × facteur saisonnier optionnel) ──
    if days_in_month and len(days_in_month) == 12:
        days = [int(_safe_float(d, 0.0)) for d in days_in_month]
    else:
        days = list(_DAYS_IN_MONTH)

    if monthly_irradiation_factor and len(monthly_irradiation_factor) == 12:
        factors = [max(0.0, _safe_float(f, 1.0))
                   for f in monthly_irradiation_factor]
    else:
        factors = [1.0] * 12

    monthly_m3 = [
        round(daily_m3 * days[m] * factors[m], 1) for m in range(12)]
    annual_m3 = round(sum(monthly_m3), 1)

    return {
        "daily_m3": daily_m3,
        "monthly_m3": monthly_m3,
        "monthly_labels": list(_MONTHS_FR),
        "annual_m3": annual_m3,
        "mode": mode,
        "peak_hour_index": peak_hour_index,
        "effective_pumping_hours": effective_pumping_hours,
        "daily_by_hour": daily_by_hour,
        "warnings": warnings,
    }
