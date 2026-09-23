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

Le ROI : économie annuelle = facture SANS solaire − facture AVEC solaire
(modèle « deux factures », tarifée au MOIS — l'unité du barème — puis
annualisée), PAS une simple multiplication énergie autoconsommée × prix
moyen. Sur le barème SÉLECTIF (ONEE), redescendre sous une marche re-tarife
TOUT le mois restant : un calcul flat sous-estime cette chute super-linéaire.
Miroir du modèle du moteur de devis (``apps/ventes/quote_engine/pricing.py``
``two_bills_savings``) — deux implémentations volontairement séparées, voir
la note de tête de ``monthly_bill_residentiel`` ci-dessous. Le surplus
injecté n'est valorisé QUE si ``surplus_injecte_compense`` est vrai (par
défaut faux : surplus = 0). Les hypothèses par défaut sont conservatrices.

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

    SECONDE IMPLÉMENTATION INDÉPENDANTE — apps/ventes/quote_engine/pricing.py
    ``_monthly_bill_from_kwh``/``ONEE_TRANCHES`` (consommée par le moteur de
    devis/PDF ; celle-ci sert ``apps/ventes/etude.py`` pour l'étude bancable
    et l'écran Tarification & ROI) calcule la MÊME grille/règle. Volontairement
    PAS unifiées (hors périmètre) — verrouillées d'accord par
    apps/ventes/tests/test_tariff_drift_lock.py : si l'une bouge seule, ce
    test passe au rouge.
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

    # SÉLECTIF : mois entier au prix unique de la tranche atteinte. ``kwh`` est
    # déjà un Decimal exact (ligne 101) : ne JAMAIS le tronquer en int() ici —
    # un int(210.5) → 210 fait retomber une conso à 210,5 dans la tranche
    # 151–210 (1,0732) au lieu de 211–310 (1,1676), sous-facturant le mois
    # entier (225,91 MAD au lieu de 245,78 MAD à 210,5 kWh — régression
    # F2 constatée en revue). La comparaison Decimal <= int (dans
    # ``_selective_price``/``_tier_price_at``) est exacte, pas besoin d'un
    # second cast.
    price = _selective_price(settings, tiers, kwh)
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


# ── CALX257 — l'INVERSE du barème : facture MAD TTC/mois → kWh/mois ──────────
# Les deux jumeaux ci-dessus vont kWh → MAD ; le module Calepinage avait
# besoin du sens inverse (ses profils partent des FACTURES du lead) et rendait
# ``kwh: null`` faute de barème. L'inversion est écrite ICI, à côté d'eux, pour
# qu'elle soit par construction l'inverse de LEUR facture — le calepinage ne
# fait que l'appeler (D5 : l'argent se chiffre hors du module).
#
# CE QUI EST RETIRÉ AVANT D'INVERSER : les charges FIXES d'abonnement
# (``redevance_compteur_mad_mois``) — les attribuer à l'énergie fabriquerait
# ~29 kWh/mois fantômes (QJR142 (d), moteur de devis). Réglage VIDE ⇒ ``kwh``
# vaut ``None`` avec un motif qui le NOMME : le défaut relevé sur facture vit
# dans le moteur de devis (``apps.ventes``), que cette app de FONDATION ne lit
# jamais — et le recopier ici ferait une seconde table.

#: Classes admises — la classe est SAISIE, jamais supposée : un même montant ne
#: décrit pas la même énergie au barème résidentiel et au tarif force motrice.
#: ``agricole`` est l'alias déjà accepté par :func:`monthly_bill`.
CLASSES_INVERSION = ('residentiel', 'force_motrice', 'agricole')

#: Le réglage qui porte le barème, nommé dans chaque motif.
REGLAGE_TARIF = 'Paramètres → Tarification & ROI'

#: Ce que le montant inversé est censé contenir — publié avec chaque résultat.
PERIMETRE_INVERSION = (
    "Montant inversé : la facture TTC du mois, charges fixes d'abonnement "
    "comprises (retirées avant l'inversion). La taxe audiovisuelle (TPPAN) "
    "n'est pas modélisée par ce barème : elle n'est pas retirée.")

#: Borne haute de la recherche (kWh/mois). Au-delà, le montant ne décrit aucune
#: consommation du barème : ``kwh`` vaut ``None`` avec son motif, jamais la
#: borne elle-même (même règle que le moteur de devis, QJR142 (e)).
_PLAFOND_INVERSION_KWH = Decimal('1000000')

_DIXIEME = Decimal('0.1')


class FactureInvalide(ValueError):
    """Une entrée de l'inversion refusée, en NOMMANT le champ fautif."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def _resultat_inversion(settings, classe, kwh, motif, *, charges_fixes=None,
                        energie=None):
    return {
        'kwh': kwh,
        'motif': motif,
        'classe': classe,
        'charges_fixes_mad': charges_fixes,
        'energie_mad': energie,
        'reglage': REGLAGE_TARIF,
        'reglage_version': getattr(settings, 'version', None),
        'perimetre': PERIMETRE_INVERSION,
    }


def kwh_depuis_facture(settings, mad_ttc, *, classe):
    """Facture mensuelle TTC (MAD) → consommation du mois (kWh), ou ``None``.

    L'INVERSE de :func:`monthly_bill` : charges fixes retirées, puis recherche
    DICHOTOMIQUE de ``inf{k : monthly_bill(k) ≥ énergie}`` — le seul inverse
    correct d'une facture qui SAUTE aux bornes du barème sélectif. Un montant
    tombé dans un saut est résolu à la borne BASSE (côté prudent : moins de kWh,
    jamais plus). Ancre : la facture réelle SRM n° 643769639 (359 kWh ×
    1,381704 = 496,03 MAD TTC d'énergie, ``models_tariff.py``).

    Args:
        settings: le ``TariffSettings`` DE LA SOCIÉTÉ, déjà chargé — ``None``
            quand aucune société n'est résolue (jamais le réglage de repli).
        mad_ttc: le montant TTC de la facture du mois.
        classe: ``residentiel`` | ``force_motrice`` (alias ``agricole``),
            SAISIE par l'appelant.

    Returns:
        dict — ``kwh`` (``Decimal`` au dixième, ou ``None``), ``motif`` (vide
        quand la conversion a abouti, sinon la raison qui NOMME le réglage ou
        le champ en cause), ``classe``, ``charges_fixes_mad``, ``energie_mad``,
        ``reglage``, ``reglage_version``, ``perimetre``.

    Raises:
        FactureInvalide: classe absente ou inconnue (``champ='classe'``),
            montant illisible ou négatif (``champ='mad_ttc'``).
    """
    if classe not in CLASSES_INVERSION:
        raise FactureInvalide(
            f'Classe tarifaire « {classe} » refusée : elle doit être saisie '
            f'parmi {", ".join(CLASSES_INVERSION)}.', champ='classe')

    if settings is None:
        return _resultat_inversion(settings, classe, None, (
            f"Aucune société résolue : le réglage « {REGLAGE_TARIF} » "
            '(TariffSettings) est introuvable. La conversion MAD → kWh '
            "n'est pas faite — jamais à partir d'un prix moyen supposé."))

    if mad_ttc in (None, ''):
        return _resultat_inversion(settings, classe, None, (
            'Aucun montant de facture pour ce mois : rien à convertir.'))
    try:
        montant = Decimal(str(mad_ttc))
    except Exception:  # noqa: BLE001 — InvalidOperation et types exotiques
        raise FactureInvalide(
            f'Montant de facture illisible (reçu : {mad_ttc!r}).',
            champ='mad_ttc')
    if not montant.is_finite():
        raise FactureInvalide(
            f'Montant de facture illisible (reçu : {mad_ttc!r}).',
            champ='mad_ttc')
    if montant < 0:
        raise FactureInvalide(
            f'Un montant de facture ne peut pas être négatif (reçu : '
            f'{montant}).', champ='mad_ttc')

    fixes = settings.redevance_compteur_mad_mois
    if fixes is None:
        return _resultat_inversion(settings, classe, None, (
            "Les charges fixes d'abonnement ne sont pas déclarées "
            f"(« {REGLAGE_TARIF} » → redevance_compteur_mad_mois) : sans "
            'elles, la location du compteur serait comptée comme de '
            "l'énergie. Renseignez-les (0 si votre facture n'en porte pas) "
            'pour convertir.'))
    fixes = Decimal(str(fixes))
    if fixes < 0:
        return _resultat_inversion(settings, classe, None, (
            "Les charges fixes d'abonnement déclarées sont négatives "
            f'({fixes} MAD, « {REGLAGE_TARIF} » → '
            'redevance_compteur_mad_mois) : conversion refusée.'),
            charges_fixes=fixes)

    energie = montant - fixes
    if energie < 0:
        return _resultat_inversion(settings, classe, None, (
            f'Le montant ({montant} MAD) est inférieur aux charges fixes '
            f"d'abonnement déclarées ({fixes} MAD) : il ne correspond à "
            'aucune consommation.'), charges_fixes=fixes, energie=energie)
    if energie == 0:
        return _resultat_inversion(settings, classe, Decimal('0.0'), '',
                                   charges_fixes=fixes, energie=energie)

    def facture(kwh):
        return monthly_bill(settings, kwh, classe)

    bas, haut = Decimal('0'), Decimal('1000')
    while facture(haut) < energie and haut < _PLAFOND_INVERSION_KWH:
        haut *= 2
    if facture(haut) < energie:
        return _resultat_inversion(settings, classe, None, (
            f"Le montant ({montant} MAD) dépasse ce que le barème « "
            f"{REGLAGE_TARIF} » facture pour {_PLAFOND_INVERSION_KWH} kWh/mois "
            ": il ne décrit aucune consommation de ce barème."),
            charges_fixes=fixes, energie=energie)
    for _ in range(60):
        milieu = (bas + haut) / 2
        if facture(milieu) < energie:
            bas = milieu
        else:
            haut = milieu
    kwh = haut.quantize(_DIXIEME, rounding=ROUND_HALF_UP)
    return _resultat_inversion(settings, classe, kwh, '',
                               charges_fixes=fixes, energie=energie)


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

    ``economie_annuelle_ttc`` est le modèle « deux factures » (facture SANS
    solaire − facture AVEC solaire, au barème réel, mois par mois) — voir la
    note de tête de ce module.

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

    # prix_kwh_evite reste un indicateur d'AFFICHAGE (prix moyen réellement
    # payé au niveau de conso actuel) — champ inchangé, PAS la base du calcul
    # d'économie ci-dessous.
    prix_kwh = effective_kwh_price(settings, conso_mois, classe)

    # Économie « deux factures » (miroir du modèle du moteur de devis —
    # apps/ventes/quote_engine/pricing.py::two_bills_savings ; DEUX
    # implémentations volontairement séparées, verrouillées d'accord par
    # apps/ventes/tests/test_tariff_drift_lock.py) : facture SANS solaire −
    # facture AVEC solaire, tarifée au MOIS (l'unité du barème sélectif),
    # PAS autoconsommée × prix moyen. Sur une grille SÉLECTIVE (ONEE),
    # redescendre sous une marche re-tarife TOUT le mois restant — un calcul
    # flat sous-estimait cette chute super-linéaire (ordre fondateur
    # 18/08/2026, déjà appliqué côté moteur de devis). ``autoconsommee`` est
    # ANNUELLE (ci-dessus) : on la ramène au mois pour tarifer au mois — le
    # seuil des marches est mensuel, jamais diviser l'année APRÈS tarification.
    autoconsommee_mois = (
        autoconsommee / Decimal('12') if autoconsommee else Decimal('0'))
    conso_mois_residuelle = max(Decimal('0'), conso_mois - autoconsommee_mois)
    facture_mensuelle_sans = monthly_bill(settings, conso_mois, classe)
    facture_mensuelle_avec = monthly_bill(
        settings, conso_mois_residuelle, classe)
    economie_mensuelle = facture_mensuelle_sans - facture_mensuelle_avec
    economie = _q(economie_mensuelle * 12)

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
