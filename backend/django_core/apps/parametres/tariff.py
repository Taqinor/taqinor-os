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
import datetime as _dt
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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


# ═════════════════════════════════════════════════════════════════════════════
# CALX274 — TRANCHES HORAIRES (time-of-use) SAISIES PAR LA SOCIÉTÉ
# ═════════════════════════════════════════════════════════════════════════════
# Constat : ``apps/ventes/solar_design.py`` portait ses propres tarifs par
# tranche (pointe 1,45 / pleine 1,15 / creuse 0,85 MAD/kWh, commentés « à
# CONFIRMER par le founder selon le contrat ONEE réel ») et les appliquait dès
# qu'un appelant ne passait rien. Ces trois nombres n'avaient AUCUNE source.
#
# Désormais le découpage horaire et ses tarifs sont SAISIS par la société
# (``TariffSettings.tou_heures`` / ``tou_tarifs``) avec la SOURCE et sa DATE
# (``tou_source`` / ``tou_date_source``). Tant que les quatre ne sont pas
# saisis, :func:`tou_depuis_reglages` rend ``None`` et l'économie horaire est
# OMISE avec son motif (:data:`MOTIF_TOU_NON_SAISI`) — jamais chiffrée sur un
# tarif supposé. Aucun libellé de tranche n'est imposé : la société nomme ses
# tranches comme sur SA facture (« pointe », « pleine », « creuse », …).
#
# Fonctions PURES : elles lisent des attributs (``getattr``) — un
# ``TariffSettings`` chargé ou tout objet qui en porte les champs — et ne
# touchent jamais la base. ``models_tariff.TariffSettings.clean`` et, demain,
# le sérialiseur de l'écran Tarification appellent :func:`erreurs_reglages_tarif`
# (point d'entrée UNIQUE des refus, clé = nom du champ fautif).

#: Une journée compte 24 heures : le découpage horaire en porte exactement 24.
HEURES_TOU = 24

#: Les quatre champs d'une grille horaire société (CALX274).
CHAMPS_TOU = ('tou_heures', 'tou_tarifs', 'tou_source', 'tou_date_source')

#: Motif publié quand aucune grille horaire complète n'est saisie. Il NOMME
#: le réglage à renseigner et l'écran où il se trouve.
MOTIF_TOU_NON_SAISI = (
    "omis : aucun tarif horaire saisi par la société — renseigner les tranches "
    "horaires (tou_heures), leurs tarifs (tou_tarifs), la source (tou_source) "
    "et sa date (tou_date_source) dans Paramètres → Tarification & ROI")


def _vide(valeur):
    """Vrai quand un réglage n'est pas saisi (None, chaîne/liste/dict vides)."""
    if valeur is None:
        return True
    if isinstance(valeur, str):
        return not valeur.strip()
    if isinstance(valeur, (list, tuple, dict)):
        return len(valeur) == 0
    return False


def _libelle_tranche(valeur):
    """Libellé de tranche normalisé (minuscule, sans blancs), ou ``''``."""
    if not isinstance(valeur, str):
        return ''
    return valeur.strip().lower()


def _nombre_positif(valeur):
    """``Decimal`` ≥ 0 lu dans ``valeur``, ou ``None`` si illisible/négatif."""
    if isinstance(valeur, bool):
        return None
    try:
        d = Decimal(str(valeur).strip().replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not d.is_finite() or d < 0:
        return None
    return d


def _date_saisie(valeur):
    """``datetime.date`` lu dans ``valeur`` (date ou ISO ``AAAA-MM-JJ``)."""
    if isinstance(valeur, _dt.datetime):
        return valeur.date()
    if isinstance(valeur, _dt.date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return _dt.date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def _libelles_d_une_liste(heures, chemin, erreurs):
    """Valide une liste de 24 libellés ; rend les libellés normalisés.

    Une erreur est rangée sous la clé ``tou_heures`` (le champ fautif) avec un
    message qui NOMME l'élément (``chemin``) ; rend ``None`` si la liste est
    refusée.
    """
    if not isinstance(heures, (list, tuple)) or len(heures) != HEURES_TOU:
        erreurs.setdefault(
            'tou_heures',
            f"{chemin} : exactement {HEURES_TOU} libellés de tranche sont "
            "attendus, un par heure de 00 h à 23 h.")
        return None
    libelles = [_libelle_tranche(h) for h in heures]
    for index, libelle in enumerate(libelles):
        if not libelle:
            erreurs.setdefault(
                'tou_heures',
                f"{chemin}[{index}] : libellé de tranche vide ou illisible "
                f"pour l'heure {index:02d} h.")
            return None
    return libelles


def _libelles_des_heures(tou_heures, erreurs):
    """Ensemble des libellés employés par ``tou_heures``.

    ``tou_heures`` est une liste de 24 libellés (toute l'année) ou, depuis
    CALX275, un objet ``{saison: [24 libellés]}`` — chaque saison validée
    séparément, une saison inconnue refusée en la NOMMANT.
    """
    if isinstance(tou_heures, dict):
        libelles = set()
        for saison, heures in tou_heures.items():
            if saison not in SAISONS_TOU:
                erreurs.setdefault(
                    'tou_heures',
                    f"tou_heures.{saison} : saison inconnue — saisons "
                    f"admises : {', '.join(SAISONS_TOU)}.")
                return set()
            liste = _libelles_d_une_liste(
                heures, f'tou_heures.{saison}', erreurs)
            if liste is None:
                return set()
            libelles.update(liste)
        return libelles
    libelles = _libelles_d_une_liste(tou_heures, 'tou_heures', erreurs)
    return set(libelles or ())


# ── CALX275 — tranches horaires PAR SAISON ───────────────────────────────────
#: Les saisons admises d'un découpage horaire : EXACTEMENT celles des profils
#: de consommation société (``ProfilTypeConsommation.SAISONS``,
#: ``apps/calepinage/models.py``) — un test CI verrouille l'égalité. ``annuel``
#: = un découpage valable toute l'année, déclaré comme tel.
SAISONS_TOU = ('annuel', 'hiver', 'printemps', 'ete', 'automne')

#: Mois (1-12) de chaque saison : les trimestres MÉTÉOROLOGIQUES standard,
#: ceux qu'emploie déjà le dépôt pour PVGIS (``apps/parametres/pvgis_profils.py``
#: ``MOIS_PAR_SAISON`` : hiver = DJF, été = JJA, mi-saison = MAM + SON, ici
#: séparée en printemps = MAM et automne = SON). Aucun mois n'est choisi ici.
MOIS_PAR_SAISON_TOU = {
    'hiver': (12, 1, 2),
    'printemps': (3, 4, 5),
    'ete': (6, 7, 8),
    'automne': (9, 10, 11),
}


def saison_du_mois(mois):
    """Saison météorologique (``hiver``/``printemps``/``ete``/``automne``) du
    mois ``mois`` (1-12), ou ``None`` si le mois est inconnu/illisible."""
    try:
        m = int(mois)
    except (TypeError, ValueError):
        return None
    for saison, mois_saison in MOIS_PAR_SAISON_TOU.items():
        if m in mois_saison:
            return saison
    return None


def erreurs_tou(tou_heures, tou_tarifs, tou_source, tou_date_source):
    """Refus d'une grille horaire société, ``{champ: message}`` (vide = valide).

    * rien de saisi (ni heures ni tarifs) ⇒ aucune erreur : la société n'a
      simplement pas de grille horaire, l'économie horaire sera OMISE ;
    * heures et tarifs se saisissent ENSEMBLE, chaque tranche employée par
      une heure doit porter son tarif (MAD/kWh, nombre ≥ 0) ;
    * dès qu'une grille est saisie, ``tou_source`` et ``tou_date_source`` sont
      OBLIGATOIRES — un tarif sans provenance datée est refusé en nommant le
      champ, jamais enregistré en silence.
    """
    erreurs = {}
    heures_saisies = not _vide(tou_heures)
    tarifs_saisis = not _vide(tou_tarifs)
    if not heures_saisies and not tarifs_saisis:
        return erreurs

    libelles = set()
    if heures_saisies:
        libelles = _libelles_des_heures(tou_heures, erreurs)
    else:
        erreurs['tou_heures'] = (
            "tou_heures : des tarifs par tranche sont saisis sans le découpage "
            "horaire qui dit à quelle heure chaque tranche s'applique.")

    tarifs = {}
    if tarifs_saisis:
        if not isinstance(tou_tarifs, dict):
            erreurs['tou_tarifs'] = (
                "tou_tarifs : un objet {tranche: MAD/kWh} est attendu.")
        else:
            for cle, valeur in tou_tarifs.items():
                libelle = _libelle_tranche(cle)
                prix = _nombre_positif(valeur)
                if not libelle or prix is None:
                    erreurs.setdefault(
                        'tou_tarifs',
                        f"tou_tarifs.{cle} : tarif illisible ou négatif — un "
                        "nombre ≥ 0 en MAD/kWh est attendu.")
                    continue
                tarifs[libelle] = prix
    else:
        erreurs['tou_tarifs'] = (
            "tou_tarifs : le découpage horaire est saisi sans les tarifs de "
            "ses tranches.")

    if libelles and tarifs and 'tou_tarifs' not in erreurs:
        manquants = sorted(libelles - set(tarifs))
        if manquants:
            erreurs['tou_tarifs'] = (
                f"tou_tarifs.{manquants[0]} : la tranche « {manquants[0]} » est "
                "employée par tou_heures mais n'a aucun tarif saisi.")

    if _vide(tou_source):
        erreurs['tou_source'] = (
            "tou_source : la source des tarifs horaires est obligatoire "
            "(facture, contrat ou barème officiel d'où viennent ces valeurs).")
    if _date_saisie(tou_date_source) is None:
        erreurs['tou_date_source'] = (
            "tou_date_source : la date de la source des tarifs horaires est "
            "obligatoire (AAAA-MM-JJ).")
    return erreurs


def tou_depuis_reglages(reglages):
    """Grille horaire SAISIE par la société, ou ``None`` (économie omise).

    Rend ``None`` tant que les quatre champs de :data:`CHAMPS_TOU` ne sont pas
    tous saisis ET valides (source ET date comprises) : un appelant qui reçoit
    ``None`` publie :data:`MOTIF_TOU_NON_SAISI`, jamais un tarif supposé.
    Sinon ::

        {'heures': [24 libellés normalisés]
                   | {saison: [24 libellés]}   (CALX275, saisons SAISONS_TOU),
         'tarifs': {libellé: float MAD/kWh},
         'source': str, 'date_source': 'AAAA-MM-JJ'}
    """
    if reglages is None:
        return None
    valeurs = {champ: getattr(reglages, champ, None) for champ in CHAMPS_TOU}
    if any(_vide(v) for v in valeurs.values()):
        return None
    if erreurs_tou(**valeurs):
        return None
    brutes = valeurs['tou_heures']
    if isinstance(brutes, dict):
        # CALX275 — découpage PAR SAISON : chaque saison saisie, normalisée.
        heures = {saison: _libelles_d_une_liste(liste, saison, {})
                  for saison, liste in brutes.items()}
    else:
        heures = _libelles_d_une_liste(brutes, 'tou_heures', {})
    tarifs = {
        _libelle_tranche(cle): float(_nombre_positif(valeur))
        for cle, valeur in valeurs['tou_tarifs'].items()
    }
    return {
        'heures': heures,
        'tarifs': tarifs,
        'source': str(valeurs['tou_source']).strip(),
        'date_source': _date_saisie(valeurs['tou_date_source']).isoformat(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# CALX276 — MÉCANISME DE COMPENSATION DU SURPLUS, TYPÉ ET SAISI
# ═════════════════════════════════════════════════════════════════════════════
# Avant : un booléen ``surplus_injecte_compense`` + un ``surplus_prix_kwh_ttc`` ;
# le report de crédit, le plafond et le ratio n'existaient qu'en ARGUMENTS de
# ``solar_design.net_metering_savings`` — jamais persistés, jamais traçables.
# Désormais le mécanisme est un réglage société TYPÉ (vide par défaut), avec
# ses paramètres. Le TARIF DE RACHAT est ``surplus_prix_kwh_ttc`` : tant qu'il
# vaut 0 (son défaut) il est « non saisi » — la loi 82-21 n'a publié AUCUN
# tarif d'injection, et le service publie alors :data:`MOTIF_TARIF_RACHAT_ABSENT`
# au lieu d'une valeur. Le défaut de 0,04 $/kWh documenté par OpenSolar n'est
# PAS repris (aucune source marocaine).

#: Les trois mécanismes admis (OpenSolar « Buy All, Sell All » / « Net
#: Billing » / « Net Energy Metering with credit carryover » ; PV*SOL :
#: injection totale / surplus / net metering avec report).
MECANISMES_COMPENSATION = ('injection_totale', 'surplus', 'net_metering_report')

#: Mécanisme non saisi : le surplus n'est PAS valorisé (ni 0, ni supposé).
MOTIF_MECANISME_NON_SAISI = (
    "omis : aucun mécanisme de compensation du surplus saisi par la société "
    "(mecanisme_compensation, Paramètres → Tarification & ROI) — le surplus "
    "n'est pas valorisé")

#: Tarif de rachat non saisi (loi 82-21 : aucun tarif d'injection publié).
MOTIF_TARIF_RACHAT_ABSENT = (
    "omis : aucun tarif d'injection publié, aucun tarif saisi par la société "
    "(surplus_prix_kwh_ttc)")


def _entier_positif(valeur):
    """Entier ≥ 1 lu dans ``valeur``, ou ``None``."""
    if isinstance(valeur, bool):
        return None
    try:
        n = int(Decimal(str(valeur).strip()))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return n if n >= 1 else None


def erreurs_compensation(mecanisme, report_periode, plafond_annuel_kwh,
                         ratio_compensation):
    """Refus du mécanisme de compensation, ``{champ: message}`` (vide = valide).

    Mécanisme vide ⇒ aucune erreur (rien n'est valorisé). ``net_metering_report``
    exige ``report_periode`` (mois ≥ 1) ; plafond ≥ 0 ; ratio dans [0, 1].
    """
    erreurs = {}
    meca = (mecanisme or '').strip() if isinstance(mecanisme, str) else ''
    if meca and meca not in MECANISMES_COMPENSATION:
        erreurs['mecanisme_compensation'] = (
            f"mecanisme_compensation : « {meca} » inconnu — mécanismes admis : "
            f"{', '.join(MECANISMES_COMPENSATION)}.")
    if meca == 'net_metering_report' and _entier_positif(report_periode) is None:
        erreurs['report_periode'] = (
            "report_periode : obligatoire pour le net-metering avec report — "
            "durée (en mois, ≥ 1) pendant laquelle un crédit reste reportable.")
    elif not _vide(report_periode) and _entier_positif(report_periode) is None:
        erreurs['report_periode'] = (
            "report_periode : un nombre entier de mois ≥ 1 est attendu.")
    if not _vide(plafond_annuel_kwh) and _nombre_positif(
            plafond_annuel_kwh) is None:
        erreurs['plafond_annuel_kwh'] = (
            "plafond_annuel_kwh : un nombre de kWh ≥ 0 est attendu.")
    if not _vide(ratio_compensation):
        ratio = _nombre_positif(ratio_compensation)
        if ratio is None or ratio > 1:
            erreurs['ratio_compensation'] = (
                "ratio_compensation : une fraction entre 0 et 1 est attendue "
                "(1 = un kWh injecté compense un kWh soutiré).")
    return erreurs


def mecanisme_depuis_reglages(reglages):
    """Mécanisme de compensation SAISI par la société, ou ``None``.

    ``None`` tant que ``mecanisme_compensation`` est vide ou invalide : le
    surplus est alors OMIS avec :data:`MOTIF_MECANISME_NON_SAISI`. Sinon ::

        {'mecanisme': str, 'report_periode': int | None,
         'plafond_annuel_kwh': float | None, 'ratio_compensation': float | None,
         'tarif_rachat_mad_kwh': float | None}   # None = non saisi (0)
    """
    if reglages is None:
        return None
    meca = getattr(reglages, 'mecanisme_compensation', '') or ''
    champs = (meca, getattr(reglages, 'report_periode', None),
              getattr(reglages, 'plafond_annuel_kwh', None),
              getattr(reglages, 'ratio_compensation', None))
    if not meca or erreurs_compensation(*champs):
        return None
    plafond = _nombre_positif(champs[2]) if not _vide(champs[2]) else None
    ratio = _nombre_positif(champs[3]) if not _vide(champs[3]) else None
    rachat = _nombre_positif(getattr(reglages, 'surplus_prix_kwh_ttc', None))
    return {
        'mecanisme': meca,
        'report_periode': (_entier_positif(champs[1])
                           if not _vide(champs[1]) else None),
        'plafond_annuel_kwh': float(plafond) if plafond is not None else None,
        'ratio_compensation': float(ratio) if ratio is not None else None,
        'tarif_rachat_mad_kwh': (float(rachat) if rachat is not None
                                 and rachat > 0 else None),
    }


# ═════════════════════════════════════════════════════════════════════════════
# CALX277 — STRUCTURE DE LA GRILLE : TRANCHES / PRIX UNIQUE / DEUX POSTES
# ═════════════════════════════════════════════════════════════════════════════
# La grille société n'exprimait que des paliers de consommation mensuelle
# (barème ONEE). Une société HORS Maroc facture souvent au prix unique du kWh
# (« Flat Rate », structure de premier rang d'OpenSolar) ou à deux postes
# horaires (heures hautes / heures basses). ``structure_tarif`` le déclare ;
# ``tranches`` reste le DÉFAUT et rend EXACTEMENT la facture d'aujourd'hui.
# Une structure choisie sans ses prix est REFUSÉE en nommant le champ manquant
# — jamais facturée sur un prix supposé.

#: Les trois structures admises ; ``tranches`` = le barème ONEE historique.
STRUCTURES_TARIF = ('tranches', 'prix_unique', 'deux_postes')

#: Structure par défaut : celle d'aujourd'hui (barème à paliers ONEE).
STRUCTURE_TARIF_DEFAUT = 'tranches'


def erreurs_structure(structure_tarif, pays_tarif, prix_unique_kwh,
                      poste_haut, poste_bas):
    """Refus de la structure tarifaire, ``{champ: message}`` (vide = valide)."""
    erreurs = {}
    structure = (structure_tarif or STRUCTURE_TARIF_DEFAUT)
    if structure not in STRUCTURES_TARIF:
        erreurs['structure_tarif'] = (
            f"structure_tarif : « {structure} » inconnue — structures admises "
            f": {', '.join(STRUCTURES_TARIF)}.")
        return erreurs
    if structure == 'prix_unique' and _nombre_positif(prix_unique_kwh) is None:
        erreurs['prix_unique_kwh'] = (
            "prix_unique_kwh : la structure « prix unique » exige le prix du "
            "kWh (nombre ≥ 0).")
    if structure == 'deux_postes':
        for champ, valeur, libelle in (
                ('poste_haut', poste_haut, 'heures hautes'),
                ('poste_bas', poste_bas, 'heures basses')):
            if _nombre_positif(valeur) is None:
                erreurs[champ] = (
                    f"{champ} : la structure « deux postes » exige le prix du "
                    f"kWh en {libelle} (nombre ≥ 0).")
    if not _vide(pays_tarif):
        code = str(pays_tarif).strip().upper()
        if len(code) != 2 or not code.isalpha() or not code.isascii():
            erreurs['pays_tarif'] = (
                "pays_tarif : un code pays ISO 3166 à deux lettres est attendu "
                "(ex. MA, FR, SN).")
    return erreurs


def structure_de(reglages):
    """Structure tarifaire déclarée (``tranches`` si rien n'est saisi)."""
    valeur = getattr(reglages, 'structure_tarif', None) or ''
    return valeur if valeur in STRUCTURES_TARIF else STRUCTURE_TARIF_DEFAUT


def facture_mensuelle(reglages, kwh, *, classe='residentiel',
                      kwh_poste_haut=None):
    """Facture mensuelle selon la STRUCTURE déclarée par la société (CALX277).

    Rend ``{structure, montant_ttc, motif, detail}`` — ``montant_ttc`` est un
    ``Decimal`` au centime, ou ``None`` avec un ``motif`` qui nomme la donnée
    manquante (jamais un prix supposé) :

    * ``tranches`` (défaut) — EXACTEMENT :func:`monthly_bill` d'aujourd'hui
      (barème ONEE progressif/sélectif, ou classe force motrice) ;
    * ``prix_unique`` — ``kwh × prix_unique_kwh`` ;
    * ``deux_postes`` — ``kwh_poste_haut × poste_haut + (kwh − kwh_poste_haut)
      × poste_bas`` : la RÉPARTITION des kWh entre les deux postes doit être
      fournie par l'appelant (elle vient d'une courbe horaire), jamais devinée.

    Les prix sont ceux SAISIS, tels que facturés (TTC par convention — CALX278
    sépare les taxes).
    """
    structure = structure_de(reglages)
    kwh_d = Decimal(str(kwh or 0))
    resultat = {'structure': structure, 'montant_ttc': None, 'motif': None,
                'detail': {}}
    if classe in ('force_motrice', 'agricole') or structure == 'tranches':
        resultat['montant_ttc'] = monthly_bill(reglages, kwh_d, classe)
        return resultat
    if kwh_d <= 0:
        resultat['montant_ttc'] = Decimal('0.00')
        return resultat

    if structure == 'prix_unique':
        prix = _nombre_positif(getattr(reglages, 'prix_unique_kwh', None))
        if prix is None:
            resultat['motif'] = (
                "omis : structure « prix unique » sans prix du kWh saisi "
                "(prix_unique_kwh)")
            return resultat
        resultat['detail'] = {'prix_kwh': prix}
        resultat['montant_ttc'] = _q(kwh_d * prix)
        return resultat

    haut = _nombre_positif(getattr(reglages, 'poste_haut', None))
    bas = _nombre_positif(getattr(reglages, 'poste_bas', None))
    manquant = ('poste_haut' if haut is None
                else 'poste_bas' if bas is None else None)
    if manquant:
        resultat['motif'] = (
            f"omis : structure « deux postes » sans le prix du {manquant} "
            f"saisi ({manquant})")
        return resultat
    part_haut = _nombre_positif(kwh_poste_haut)
    if part_haut is None or part_haut > kwh_d:
        resultat['motif'] = (
            "omis : la répartition des kWh entre poste haut et poste bas n'est "
            "pas fournie (kwh_poste_haut) — elle se lit sur une courbe "
            "horaire, jamais supposée")
        return resultat
    part_bas = kwh_d - part_haut
    resultat['detail'] = {'kwh_poste_haut': part_haut,
                          'kwh_poste_bas': part_bas,
                          'poste_haut': haut, 'poste_bas': bas}
    resultat['montant_ttc'] = _q(part_haut * haut + part_bas * bas)
    return resultat


def erreurs_reglages_tarif(reglages):
    """Point d'entrée UNIQUE des refus des réglages tarifaires, ``{champ: msg}``.

    Appelé par ``TariffSettings.clean`` (et, demain, par le sérialiseur de
    l'écran Tarification — CALX72) : chaque tâche du lot 5 y AJOUTE son
    contrôle, si bien qu'aucune porte de saisie ne peut en oublier un.
    """
    erreurs = {}
    erreurs.update(erreurs_tou(
        *(getattr(reglages, champ, None) for champ in CHAMPS_TOU)))
    erreurs.update(erreurs_compensation(
        getattr(reglages, 'mecanisme_compensation', ''),
        getattr(reglages, 'report_periode', None),
        getattr(reglages, 'plafond_annuel_kwh', None),
        getattr(reglages, 'ratio_compensation', None)))
    erreurs.update(erreurs_structure(
        getattr(reglages, 'structure_tarif', None),
        getattr(reglages, 'pays_tarif', None),
        getattr(reglages, 'prix_unique_kwh', None),
        getattr(reglages, 'poste_haut', None),
        getattr(reglages, 'poste_bas', None)))
    return erreurs
