"""N64 — Service de calcul tarif ONEE + ROI.

Calcule la facture mensuelle ONEE à partir d'un nombre de kWh, sous le MODÈLE
DE FACTURATION marocain réel :

* PROGRESSIF tant que la consommation mensuelle est ≤ seuil (150 kWh par
  défaut) : chaque tranche est facturée à SON propre prix (les premiers kWh au
  prix bas, les suivants au prix de la tranche suivante, etc.).
* SÉLECTIF dès que la consommation dépasse le seuil : le MOIS ENTIER est
  facturé au PRIX UNIQUE de la tranche dans laquelle tombe le total (PAS de
  progressivité). Une TOLÉRANCE (10 kWh par défaut) décale les bornes
  opératoires vers le haut : les bornes 200/300/500 deviennent 210/310/510,
  de sorte qu'un client à 205 kWh reste facturé au tarif de la tranche
  151–210 et non à celui de 211–310.

Les prix du barème sont déjà TTC (jamais de TVA ajoutée par-dessus).

Une classe SÉPARÉE « force motrice / agricole » facture au tarif unique
``force_motrice_prix_kwh_ttc`` (moins cher), jamais au haut barème résidentiel.

Le ROI : économie annuelle = énergie autoconsommée × prix kWh évité. Le surplus
injecté n'est valorisé QUE si ``surplus_injecte_compense`` est vrai (par défaut
faux : surplus = 0). Les hypothèses par défaut sont conservatrices.

Fonctions PURES : pas d'I/O, pas d'ORM (on reçoit un ``TariffSettings`` déjà
chargé). Les montants sont des ``Decimal`` arrondis au centime.
"""
from decimal import Decimal, ROUND_HALF_UP

# Bornes « théoriques » du barème sélectif, avant tolérance. La tolérance les
# décale vers le haut (200→210, 300→310, 500→510). Elles correspondent aux
# débuts de tranche 151–210 / 211–310 / 311–510 / >510.
_SELECTIVE_NOMINAL_BOUNDS = (200, 300, 500)

_CENT = Decimal('0.01')


def _q(value):
    """Arrondit un Decimal au centime (2 décimales, demi-supérieur)."""
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def _tier_price_at(tiers, kwh):
    """Prix unitaire (Decimal) de la tranche dans laquelle tombe ``kwh``.

    ``tiers`` est la liste triée renvoyée par ``effective_tiers`` :
    [{max_kwh: int|None, prix_kwh_ttc: Decimal}, ...]. Le palier ouvert
    (max_kwh None) attrape tout ce qui dépasse la dernière borne finie.
    """
    for t in tiers:
        if t['max_kwh'] is None or kwh <= t['max_kwh']:
            return t['prix_kwh_ttc']
    # Sécurité : si aucun palier ouvert n'existe, prendre le dernier prix.
    return tiers[-1]['prix_kwh_ttc'] if tiers else Decimal('0')


def _operative_bounds(settings):
    """Bornes opératoires du mode sélectif après application de la tolérance.

    200/300/500 + tolérance → 210/310/510 par défaut.
    """
    tol = int(settings.tolerance_kwh or 0)
    return tuple(b + tol for b in _SELECTIVE_NOMINAL_BOUNDS)


def _selective_price(settings, tiers, kwh):
    """Prix unitaire UNIQUE appliqué au mois entier en mode sélectif.

    On range ``kwh`` selon les bornes opératoires (tolérance incluse) puis on
    lit le prix de la tranche correspondante dans le barème. Sous la tolérance,
    un total de 205 kWh tombe dans 151–210 et garde le tarif de cette tranche.
    """
    b1, b2, b3 = _operative_bounds(settings)
    # On choisit un kWh « représentatif » de la tranche pour lire son prix dans
    # le barème (le barème reste indexé sur les bornes nominales 210/310/510).
    if kwh <= b1:
        probe = b1            # tranche 151–210
    elif kwh <= b2:
        probe = b2            # tranche 211–310
    elif kwh <= b3:
        probe = b3            # tranche 311–510
    else:
        probe = b3 + 1        # >510
    return _tier_price_at(tiers, probe)


def monthly_bill_residentiel(settings, kwh):
    """Facture mensuelle résidentielle (Decimal TTC) pour ``kwh`` kWh.

    ≤ seuil (150) → PROGRESSIF (chaque tranche à son prix).
    > seuil       → SÉLECTIF (mois entier au prix de la tranche atteinte).
    """
    kwh = Decimal(str(kwh or 0))
    if kwh <= 0:
        return Decimal('0.00')
    tiers = settings.effective_tiers()
    seuil = Decimal(str(settings.selective_threshold_kwh or 150))

    if kwh <= seuil:
        # PROGRESSIF : on empile les tranches, chacune à son prix.
        total = Decimal('0')
        remaining = kwh
        lower = Decimal('0')
        for t in tiers:
            cap = t['max_kwh']
            if cap is None:
                slice_kwh = remaining
            else:
                upper = Decimal(str(cap))
                slice_kwh = min(remaining, max(Decimal('0'), upper - lower))
                lower = upper
            if slice_kwh > 0:
                total += slice_kwh * t['prix_kwh_ttc']
                remaining -= slice_kwh
            if remaining <= 0:
                break
        return _q(total)

    # SÉLECTIF : mois entier au prix unique de la tranche atteinte.
    price = _selective_price(settings, tiers, int(kwh))
    return _q(kwh * price)


def monthly_bill_force_motrice(settings, kwh):
    """Facture mensuelle (Decimal TTC) pour la classe force motrice/agricole.

    Tarif unique ``force_motrice_prix_kwh_ttc`` (moins cher), jamais le haut
    barème résidentiel.
    """
    kwh = Decimal(str(kwh or 0))
    if kwh <= 0:
        return Decimal('0.00')
    return _q(kwh * Decimal(str(settings.force_motrice_prix_kwh_ttc)))


def monthly_bill(settings, kwh, classe='residentiel'):
    """Facture mensuelle TTC selon la classe tarifaire.

    classe ∈ {'residentiel', 'force_motrice'} (alias 'agricole').
    """
    if classe in ('force_motrice', 'agricole'):
        return monthly_bill_force_motrice(settings, kwh)
    return monthly_bill_residentiel(settings, kwh)


def effective_kwh_price(settings, kwh, classe='residentiel'):
    """Prix moyen TTC réellement payé par kWh à ce niveau de consommation.

    Sert à valoriser l'énergie solaire ÉVITÉE : on évite des kWh au tarif
    marginal réellement supporté par le client (facture ÷ kWh).
    """
    kwh = Decimal(str(kwh or 0))
    if kwh <= 0:
        return Decimal('0.00')
    return _q(monthly_bill(settings, kwh, classe) / kwh)


def annual_productible_kwh(settings, kwc, productible_kwh_kwc=None):
    """Production annuelle (kWh) d'un champ ``kwc`` kWc.

    ``productible_kwh_kwc`` (ex. issu de PVGIS) prime ; sinon le repli manuel
    conservateur ``productible_manuel_kwh_kwc``. Les pertes système ne sont PAS
    re-appliquées ici quand le productible vient de PVGIS (PVGIS les inclut
    déjà) — c'est l'appelant qui choisit la source ; le repli manuel est lui
    déjà net. On renvoie donc kwc × productible.
    """
    kwc = Decimal(str(kwc or 0))
    if kwc <= 0:
        return Decimal('0')
    p = productible_kwh_kwc if productible_kwh_kwc is not None \
        else settings.productible_manuel_kwh_kwc
    return _q(kwc * Decimal(str(p)))


def compute_roi(settings, kwc, conso_mensuelle_kwh, cout_total_ttc,
                classe='residentiel', autoconsommation_pct=None,
                productible_kwh_kwc=None):
    """ROI conservateur d'un projet solaire.

    Paramètres
    ----------
    kwc : puissance crête installée.
    conso_mensuelle_kwh : consommation mensuelle moyenne du client (kWh).
    cout_total_ttc : prix du projet (TTC) pour le calcul du payback.
    classe : 'residentiel' | 'force_motrice'.
    autoconsommation_pct : part autoconsommée (défaut = réglage conservateur).
    productible_kwh_kwc : productible PVGIS si connu, sinon repli manuel.

    Retourne un dict (Decimal) : production_annuelle_kwh, autoconsommee_kwh,
    surplus_kwh, prix_kwh_evite, economie_annuelle_ttc, valorisation_surplus,
    economie_totale_annuelle, payback_annees.

    Conservateur : le surplus ne vaut quelque chose QUE si la compensation est
    activée ; sinon il est valorisé à zéro (on dimensionne sur l'autoconso).
    """
    kwc = Decimal(str(kwc or 0))
    conso_mois = Decimal(str(conso_mensuelle_kwh or 0))
    prod_annuelle = annual_productible_kwh(settings, kwc, productible_kwh_kwc)

    auto_pct = Decimal(str(
        autoconsommation_pct if autoconsommation_pct is not None
        else settings.autoconsommation_pct_defaut)) / Decimal('100')

    conso_annuelle = conso_mois * 12
    # Énergie solaire réellement consommée sur site : bornée par la conso ET par
    # la part autoconsommable. Conservateur : on n'autoconsomme jamais plus que
    # la conso annuelle.
    autoconsommee = prod_annuelle * auto_pct
    if conso_annuelle > 0:
        autoconsommee = min(autoconsommee, conso_annuelle)
    surplus = max(Decimal('0'), prod_annuelle - autoconsommee)

    prix_kwh = effective_kwh_price(settings, conso_mois, classe)
    economie = _q(autoconsommee * prix_kwh)

    # Surplus : zéro sauf compensation activée.
    if settings.surplus_injecte_compense:
        valorisation_surplus = _q(
            surplus * Decimal(str(settings.surplus_prix_kwh_ttc)))
    else:
        valorisation_surplus = Decimal('0.00')

    economie_totale = _q(economie + valorisation_surplus)
    cout = Decimal(str(cout_total_ttc or 0))
    payback = (_q(cout / economie_totale)
               if economie_totale > 0 and cout > 0 else None)

    return {
        'production_annuelle_kwh': _q(prod_annuelle),
        'autoconsommee_kwh': _q(autoconsommee),
        'surplus_kwh': _q(surplus),
        'prix_kwh_evite': prix_kwh,
        'economie_annuelle_ttc': economie,
        'valorisation_surplus': valorisation_surplus,
        'economie_totale_annuelle': economie_totale,
        'payback_annees': payback,
    }
