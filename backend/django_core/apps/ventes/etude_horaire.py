"""CJ2a — LE calcul canonique des économies résidentielles : intégration HORAIRE.

ORDRE FONDATEUR (CJ2) : « the total saving should be function of [saisons] and
not just assuming client will consume 60 % of total pv production but rather
follow the consumption curves fixed in the call ».

CE QUI CHANGE. Les économies résidentielles ne descendent plus d'un FORFAIT
(``pricing.AUTOCONSO_SANS = 0,60`` × production × prix) mais du RECOUVREMENT
RÉEL, heure par heure, entre :

* la PRODUCTION — forme horaire PVGIS de la saison du mois (appel live au point
  GPS du chantier, sinon courbe de référence de la ville : jamais une cloche
  inventée) mise à l'échelle du productible mensuel PVGIS × kWc du devis ;
* la CONSOMMATION — silhouette d'occupation du client (réponse RÉELLE au script
  d'appel, ``crm.Lead.occupation_jour``) + couches d'équipement (piscine, clim,
  véhicule électrique), mise à l'échelle de la facture RÉELLE de CE mois-là.

MOIS PAR MOIS, jamais une moyenne annuelle : c'est là que vit la saisonnalité
que le fondateur réclame. Un été où la production culmine PENDANT que la
climatisation tourne n'a rien à voir avec un hiver où la pointe de consommation
tombe à 20 h, une heure après le coucher du soleil — le forfait 60 % ne voyait
ni l'un ni l'autre.

L'ARGENT vient ensuite du BARÈME, jamais d'un prix moyen : pour chaque mois,
``facture(consommation) − facture(consommation − autoconsommé)``
(:mod:`apps.ventes.quote_engine.bareme`, charges fixes comprises). Sur la
grille SÉLECTIVE marocaine, redescendre sous une marche re-tarife TOUT le mois
restant — une chute super-linéaire qu'un calcul plat sous-estime lourdement.

CE MODULE NE REMPLACE RIEN DE FORCE. Il RÉUTILISE le moteur d'agrégation
horaire déjà éprouvé (``solar_design.hourly_self_consumption``, signature
inchangée) en lui donnant enfin de VRAIES courbes à la place de ses courbes
synthétiques (``etude.production_horaire_zone`` = cloche ciel clair tuilée sur
12 mois égaux ; ``etude._tiled_load_curve`` = profil générique unique).

RÈGLE Z2 (fondateur, 20/08/2026) PRÉSERVÉE : sans ancrage réel — ni factures,
ni profil — ce module renvoie ``None``. Le forfait 60 % survit alors comme
REPLI ÉTIQUETÉ dans ``pricing``, jamais déguisé en mesure. On omet, on
n'approxime pas.

RÈGLE #4 : ce module ne rend AUCUN PDF, ne change AUCUN statut, n'expose AUCUN
prix d'achat ni marge. Il CALCULE et rend un dict ; c'est l'appelant qui le
range dans ``Devis.etude_params['etude_horaire']``.

Fonctions PURES au cœur (aucun ORM) ; seule :func:`etude_horaire_pour_devis`
lit un ``Devis`` et le CRM, toujours via ``apps.crm.selectors``.
"""
from __future__ import annotations

import logging

from apps.parametres.pvgis_profils import (
    JOURS_PAR_MOIS,
    MOIS_PAR_SAISON,
    SAISONS,
    productible_mensuel,
    profil_production_journalier,
    vers_heure_locale,
)
from apps.ventes.courbes_journalieres import (
    equipements_du_devis,
    forme_consommation_kwh,
    occupation_du_devis,
)
from apps.ventes.quote_engine import bareme
from apps.ventes.quote_engine.pricing import BATTERY_ROUNDTRIP
from apps.ventes.solar_design import hourly_self_consumption

logger = logging.getLogger(__name__)

#: Version du bloc ``etude_params['etude_horaire']``. Incrémentée à TOUT
#: changement de forme — jamais de mutation silencieuse d'un bloc déjà posé.
ETUDE_HORAIRE_VERSION = 1

#: Mois (index 0 = janvier) considérés « été » quand le lead déclare une
#: facture d'été DISTINCTE. Mai→octobre — MÊME découpage que
#: ``apps/ventes/public_views._monthly_consumption``, qui sert déjà la série
#: mensuelle de la page : deux découpages différents feraient diverger l'écran
#: et le moteur sur le même client.
MOIS_ETE_FACTURE = frozenset({4, 5, 6, 7, 8, 9})

#: Mois (1-12) → saison PVGIS, dérivé de ``MOIS_PAR_SAISON`` (source unique :
#: hiver = DJF, mi-saison = MAM+SON, été = JJA). Jamais un second découpage.
_SAISON_DU_MOIS = {
    mois: saison
    for saison, mois_tuple in MOIS_PAR_SAISON.items()
    for mois in mois_tuple
}


def _num(valeur, defaut=0.0):
    """Flottant tolérant — illisible/``None`` → ``defaut``, jamais d'exception."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def saison_du_mois(mois):
    """Saison PVGIS d'un mois 1-12 (``None`` hors bornes)."""
    return _SAISON_DU_MOIS.get(mois)


# ════════════════════════════════════════════════════════════════════════════
# 1. CONSOMMATION — la série 12 mois en kWh, back-calculée depuis les factures
# ════════════════════════════════════════════════════════════════════════════

def serie_mad_mensuelle(facture_hiver_mad, facture_ete_mad=None,
                        ete_differente=False):
    """12 montants MAD/mois depuis les factures déclarées par le lead.

    Le lead ne porte JAMAIS douze factures : il porte une facture d'hiver, et
    éventuellement une facture d'été distincte (``ete_differente``). On répète
    donc honnêtement ces deux points réels sur les douze mois — on n'invente
    AUCUNE variation mensuelle que la donnée client ne contient pas. Même
    convention que ``public_views._monthly_consumption`` (été = mai→octobre).

    Sans facture d'hiver exploitable ⇒ ``None`` (aucune série fabriquée).
    """
    hiver = _num(facture_hiver_mad)
    if hiver <= 0:
        return None
    ete = _num(facture_ete_mad)
    utilise_ete = bool(ete_differente) and ete > 0
    return [
        (ete if (utilise_ete and m in MOIS_ETE_FACTURE) else hiver)
        for m in range(12)
    ]


def serie_kwh_depuis_mad(serie_mad, *, tranches=None,
                         redevance_compteur_mad=None, tppan=True):
    """12 montants MAD/mois → 12 consommations kWh/mois (back-calcul barème).

    ORDRE FONDATEUR : « back-calculating the kwh he consumed looking at his
    bill and tranches ». L'inversion passe par
    :func:`~apps.ventes.quote_engine.bareme.kwh_depuis_facture_mad` — les
    VRAIES tranches (progressif ≤ 150, sélectif au-delà avec tolérance),
    charges fixes retirées d'abord. JAMAIS une division par un prix moyen.

    Mémoïsé : le lead ne porte au plus que deux montants distincts, on
    n'inverse donc qu'au plus deux fois.

    Renvoie ``(kwh_mensuels, detail)`` où ``detail`` porte le biais éventuel
    (redevance compteur inconnue ⇒ kWh légèrement surestimé), ou
    ``(None, {})`` si la série d'entrée est inexploitable.
    """
    if not serie_mad or len(serie_mad) != 12:
        return None, {}

    cache = {}

    def _inverser(mad):
        if mad not in cache:
            cache[mad] = bareme.kwh_depuis_facture_mad(
                mad, tranches=tranches,
                redevance_compteur_mad=redevance_compteur_mad, tppan=tppan)
        return cache[mad]

    kwh = []
    for mad in serie_mad:
        resultat = _inverser(mad)
        kwh.append(resultat['kwh_mensuel'])

    if not any(v > 0 for v in kwh):
        return None, {}

    exemple = next(iter(cache.values()))
    return kwh, {
        'redevance_connue': exemple['redevance_connue'],
        'biais_redevance_inconnue': exemple['biais_redevance_inconnue'],
        'methode': 'inversion_bareme_tranches',
    }


# ════════════════════════════════════════════════════════════════════════════
# 2. PRODUCTION — les vraies formes PVGIS, par saison
# ════════════════════════════════════════════════════════════════════════════

def _formes_production_par_saison(ville=None, lat=None, lon=None):
    """``{saison: forme 24 h heure locale}`` + source, ou ``({}, None)``.

    Résolution PVGIS déjà en place (live au point GPS → courbe de référence de
    la ville reconnue → RIEN). Aucune cloche synthétique de repli : sans forme
    réelle, le moteur ne calcule pas (règle « on omet, on n'approxime pas »).
    """
    formes = {}
    source = None
    for saison in SAISONS:
        resolu = profil_production_journalier(
            saison=saison, lat=lat, lon=lon, ville=ville)
        if not resolu:
            continue
        forme_utc, source_forme = resolu
        forme = vers_heure_locale(forme_utc)
        if forme:
            formes[saison] = forme
            source = source or source_forme
    return formes, source


# ════════════════════════════════════════════════════════════════════════════
# 3. BATTERIE — simulation journalière charge/décharge (aucune constante neuve)
# ════════════════════════════════════════════════════════════════════════════

def simuler_batterie_jour(conso_24h, prod_24h, capacite_kwh_utile,
                          rendement=BATTERY_ROUNDTRIP):
    """Énergie SUPPLÉMENTAIRE autoconsommée grâce au stockage, sur un jour type.

    Modèle CHRONOLOGIQUE, heure par heure :

    * heure excédentaire (production > consommation) : le surplus charge la
      batterie, borné par la capacité UTILE restante ;
    * heure déficitaire (consommation > production) : la batterie restitue,
      bornée par le besoin ET par ce qu'elle contient, avec le rendement
      aller-retour ``BATTERY_ROUNDTRIP`` (0,90 — constante EXISTANTE de
      ``pricing``, jamais un nouveau chiffre) appliqué à la restitution.

    LA BATTERIE PART VIDE À 00 h. C'est le choix CONSERVATEUR et il est
    délibéré : le déficit d'avant l'aube (00h-06h) n'est donc pas servi par le
    surplus de la veille. Un modèle « en régime établi » (report du reliquat
    d'un jour sur l'autre) donnerait des économies plus GRANDES — on préfère
    annoncer moins que promettre trop, et l'invariant « restitué ≤ 0,90 ×
    chargé » reste vrai par construction, ce qu'un test épingle.

    Retourne ``{restitue_kwh, charge_kwh, capacite_utilisee_kwh}``.
    Capacité nulle/absente ⇒ tout à zéro (aucune énergie inventée).
    """
    capacite = _num(capacite_kwh_utile)
    if capacite <= 0:
        return {'restitue_kwh': 0.0, 'charge_kwh': 0.0,
                'capacite_utilisee_kwh': 0.0}

    rendement = _num(rendement, BATTERY_ROUNDTRIP)
    if rendement <= 0:
        rendement = BATTERY_ROUNDTRIP

    soc = 0.0          # état de charge (kWh stockés)
    pic_soc = 0.0
    charge_total = 0.0
    restitue_total = 0.0

    for heure in range(min(len(conso_24h), len(prod_24h))):
        conso = max(0.0, _num(conso_24h[heure]))
        prod = max(0.0, _num(prod_24h[heure]))
        if prod > conso:
            charge = min(prod - conso, capacite - soc)
            if charge > 0:
                soc += charge
                charge_total += charge
                pic_soc = max(pic_soc, soc)
        elif conso > prod:
            besoin = conso - prod
            disponible = soc * rendement
            restitue = min(besoin, disponible)
            if restitue > 0:
                soc -= restitue / rendement
                restitue_total += restitue

    return {
        'restitue_kwh': restitue_total,
        'charge_kwh': charge_total,
        'capacite_utilisee_kwh': pic_soc,
    }


# ════════════════════════════════════════════════════════════════════════════
# 4. LE MOTEUR
# ════════════════════════════════════════════════════════════════════════════

def _bloc_vide(cle_prefixe=''):
    """Agrégat neutre (tous compteurs à zéro) — jamais de ``None`` arithmétique."""
    return {
        'production_kwh': 0.0,
        'consommation_kwh': 0.0,
        'autoconsomme_sans_kwh': 0.0,
        'autoconsomme_avec_kwh': 0.0,
        'surplus_sans_kwh': 0.0,
        'import_sans_kwh': 0.0,
        'economie_sans_mad': 0.0,
        'economie_avec_mad': 0.0,
        'facture_avant_mad': 0.0,
        'facture_apres_sans_mad': 0.0,
        'facture_apres_avec_mad': 0.0,
    }


def _cumuler(cible, source):
    """Ajoute ``source`` dans ``cible`` clé à clé (agrégation saison/année)."""
    for cle, valeur in source.items():
        if cle in cible:
            cible[cle] += valeur


def _taux(numerateur, denominateur):
    """Ratio borné [0,1] ; dénominateur nul ⇒ 0,0 (jamais une division sauvage)."""
    if denominateur <= 0:
        return 0.0
    return min(1.0, max(0.0, numerateur / denominateur))


def _finaliser(bloc):
    """Ajoute les taux dérivés + arrondis d'affichage à un agrégat cumulé."""
    prod = bloc['production_kwh']
    conso = bloc['consommation_kwh']
    sortie = {cle: round(val, 2) for cle, val in bloc.items()}
    sortie['taux_autoconso_sans'] = round(
        _taux(bloc['autoconsomme_sans_kwh'], prod), 4)
    sortie['taux_autoconso_avec'] = round(
        _taux(bloc['autoconsomme_avec_kwh'], prod), 4)
    sortie['couverture_sans'] = round(
        _taux(bloc['autoconsomme_sans_kwh'], conso), 4)
    sortie['couverture_avec'] = round(
        _taux(bloc['autoconsomme_avec_kwh'], conso), 4)
    return sortie


def calculer_etude_horaire(*, kwc, conso_kwh_mensuelles,
                           ville=None, lat=None, lon=None,
                           occupation=None, equipements=None,
                           batterie_kwh_utile=None,
                           tranches=None, redevance_compteur_mad=None,
                           tppan=True, source_conso=None,
                           detail_conso=None):
    """LE calcul canonique. Renvoie le bloc ``etude_horaire``, ou ``None``.

    Paramètres
    ----------
    kwc : puissance crête candidate (kWc). ≤ 0 ⇒ ``None``.
    conso_kwh_mensuelles : 12 consommations RÉELLES (kWh/mois, janvier→
        décembre), déjà back-calculées depuis les factures par
        :func:`serie_kwh_depuis_mad` (ou fournies directement quand une saisie
        en kWh existe). Absente/inexploitable ⇒ ``None`` (règle Z2 : aucun
        ancrage réel, aucun chiffre).
    ville / lat / lon : localisation du chantier — chaîne PVGIS existante.
        Aucune forme résolue ⇒ ``None`` (jamais une cloche inventée).
    occupation : drapeau d'occupation (``presence_jour`` / ``absence_jour`` /
        ``presence_partielle``) ; inconnu ⇒ repli documenté de
        ``courbes_journalieres``.
    equipements : couches L4 (piscine/clim/VE) déjà composées.
    batterie_kwh_utile : capacité UTILE du stockage (kWh). Absente ⇒ la
        variante « avec batterie » est identique à « sans » (aucune énergie
        décalée inventée).
    tranches / redevance_compteur_mad / tppan : passés tels quels au barème.

    Renvoie un dict JSON-sérialisable ::

        {version, kwc, source_production, source_consommation, occupation,
         equipements_actifs, batterie_kwh_utile, mois: [12], saisons: {...},
         annuel: {...}, avertissements: []}

    Ne lève JAMAIS : toute donnée manquante fait renvoyer ``None`` ou dégrade
    honnêtement, jamais une exception qui casserait un devis.
    """
    puissance = _num(kwc)
    if puissance <= 0:
        return None

    if not conso_kwh_mensuelles or len(conso_kwh_mensuelles) != 12:
        return None
    conso_mois = [max(0.0, _num(v)) for v in conso_kwh_mensuelles]
    if not any(v > 0 for v in conso_mois):
        return None

    formes, source_prod = _formes_production_par_saison(
        ville=ville, lat=lat, lon=lon)
    if not formes:
        return None

    mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
    if not mensuel:
        return None
    productibles, source_productible = mensuel

    capacite = _num(batterie_kwh_utile)
    couches = equipements or {}
    avertissements = []

    mois_sortie = []
    saisons_cumul = {saison: _bloc_vide() for saison in SAISONS}
    annuel_cumul = _bloc_vide()

    for index in range(12):
        numero = index + 1
        saison = saison_du_mois(numero)
        jours = JOURS_PAR_MOIS[index]
        forme_prod = formes.get(saison)
        if forme_prod is None:
            avertissements.append(
                'saison %s sans forme PVGIS — mois %d omis du calcul'
                % (saison, numero))
            continue

        # ── Production du JOUR MOYEN de ce mois ──
        prod_mois_kwh = _num(productibles[index]) * puissance
        prod_jour_kwh = prod_mois_kwh / jours if jours else 0.0
        prod_24h = [part * prod_jour_kwh for part in forme_prod]

        # ── Consommation du JOUR MOYEN de ce mois (silhouette + équipements) ──
        conso_mois_kwh = conso_mois[index]
        conso_jour_kwh = conso_mois_kwh / jours if jours else 0.0
        conso_24h = forme_consommation_kwh(
            conso_jour_kwh, occupation, saison=saison, equipements=couches)

        # ── Recouvrement horaire — LE moteur existant, courbes RÉELLES ──
        recouvrement = hourly_self_consumption(
            load_curve=conso_24h, production_curve=prod_24h)
        auto_jour_sans = recouvrement['self_consumed_kwh']

        # ── Variante batterie : le surplus du jour sert le déficit du soir ──
        batterie = simuler_batterie_jour(conso_24h, prod_24h, capacite)
        auto_jour_avec = auto_jour_sans + batterie['restitue_kwh']
        # Garde d'honnêteté : on n'autoconsomme jamais plus que ce que le
        # client consomme, ni plus que ce que le champ produit.
        auto_jour_avec = min(auto_jour_avec, conso_jour_kwh, prod_jour_kwh)

        auto_mois_sans = auto_jour_sans * jours
        auto_mois_avec = auto_jour_avec * jours

        # ── L'ARGENT : deux factures, au MOIS (l'unité du barème) ──
        eco_sans = bareme.economie_deux_factures_mad(
            conso_mois_kwh, max(0.0, conso_mois_kwh - auto_mois_sans),
            tranches=tranches, redevance_compteur_mad=redevance_compteur_mad,
            tppan=tppan)
        eco_avec = bareme.economie_deux_factures_mad(
            conso_mois_kwh, max(0.0, conso_mois_kwh - auto_mois_avec),
            tranches=tranches, redevance_compteur_mad=redevance_compteur_mad,
            tppan=tppan)

        bloc = {
            'production_kwh': prod_mois_kwh,
            'consommation_kwh': conso_mois_kwh,
            'autoconsomme_sans_kwh': auto_mois_sans,
            'autoconsomme_avec_kwh': auto_mois_avec,
            'surplus_sans_kwh': max(0.0, prod_mois_kwh - auto_mois_sans),
            'import_sans_kwh': max(0.0, conso_mois_kwh - auto_mois_sans),
            'economie_sans_mad': eco_sans['economie_mad'],
            'economie_avec_mad': eco_avec['economie_mad'],
            'facture_avant_mad': eco_sans['facture_avant_mad'],
            'facture_apres_sans_mad': eco_sans['facture_apres_mad'],
            'facture_apres_avec_mad': eco_avec['facture_apres_mad'],
        }
        _cumuler(saisons_cumul[saison], bloc)
        _cumuler(annuel_cumul, bloc)

        sortie_mois = _finaliser(bloc)
        sortie_mois['mois'] = numero
        sortie_mois['saison'] = saison
        sortie_mois['jours'] = jours
        mois_sortie.append(sortie_mois)

    if not mois_sortie:
        return None

    if annuel_cumul['production_kwh'] <= 0:
        avertissements.append(
            'production annuelle nulle — vérifier la puissance et la '
            'localisation du chantier')

    return {
        'version': ETUDE_HORAIRE_VERSION,
        'kwc': round(puissance, 3),
        'source_production': source_prod,
        'source_productible': source_productible,
        'source_consommation': source_conso or 'inconnue',
        'detail_consommation': detail_conso or {},
        'occupation': occupation,
        'equipements_actifs': sorted(couches.keys()),
        'batterie_kwh_utile': round(capacite, 2) if capacite > 0 else None,
        'mois': mois_sortie,
        'saisons': {saison: _finaliser(cumul)
                    for saison, cumul in saisons_cumul.items()
                    if cumul['consommation_kwh'] > 0
                    or cumul['production_kwh'] > 0},
        'annuel': _finaliser(annuel_cumul),
        'avertissements': avertissements,
    }


# ════════════════════════════════════════════════════════════════════════════
# 5. ENTRÉES APPLICATIVES — depuis un devis, ou depuis un profil brut
# ════════════════════════════════════════════════════════════════════════════

def profil_depuis_factures(*, facture_hiver_mad=None, facture_ete_mad=None,
                           ete_differente=False, factures_mensuelles_mad=None,
                           conso_kwh_mensuelles=None, tranches=None,
                           redevance_compteur_mad=None, tppan=True):
    """Résout la série 12 mois en kWh depuis ce que le client a réellement donné.

    Ordre de PRIORITÉ (le plus réel d'abord) :

    1. ``conso_kwh_mensuelles`` — 12 kWh déjà mesurés (le cas idéal) ;
    2. ``factures_mensuelles_mad`` — 12 factures RÉELLES saisies
       (``etude_params['factures_mensuelles_reelles']``), back-calculées une à
       une : c'est la seule source qui porte une VRAIE variation mensuelle ;
    3. facture d'hiver (+ facture d'été si distincte) — les deux points réels
       que le lead porte, répétés honnêtement sur les douze mois.

    Renvoie ``(kwh_mensuels | None, source, detail)``.
    """
    if conso_kwh_mensuelles and len(conso_kwh_mensuelles) == 12:
        valeurs = [max(0.0, _num(v)) for v in conso_kwh_mensuelles]
        if any(v > 0 for v in valeurs):
            return valeurs, 'kwh_mensuels_saisis', {'methode': 'saisie_directe'}

    if factures_mensuelles_mad and len(factures_mensuelles_mad) == 12:
        valeurs = [_num(v) for v in factures_mensuelles_mad]
        if all(v > 0 for v in valeurs):
            kwh, detail = serie_kwh_depuis_mad(
                valeurs, tranches=tranches,
                redevance_compteur_mad=redevance_compteur_mad, tppan=tppan)
            if kwh:
                return kwh, 'factures_mensuelles_reelles', detail

    serie_mad = serie_mad_mensuelle(
        facture_hiver_mad, facture_ete_mad, ete_differente)
    if serie_mad:
        kwh, detail = serie_kwh_depuis_mad(
            serie_mad, tranches=tranches,
            redevance_compteur_mad=redevance_compteur_mad, tppan=tppan)
        if kwh:
            source = ('facture_hiver_ete' if (ete_differente
                                              and _num(facture_ete_mad) > 0)
                      else 'facture_hiver')
            return kwh, source, detail

    return None, 'absente', {}


def _reglages_tarifaires(company):
    """``(tranches, redevance)`` de la société — best-effort, jamais bloquant.

    ``parametres`` est une app FONDATION (exemptée de la frontière cross-app) ;
    l'import reste local au point d'usage, comme partout dans ``apps/ventes``.
    Réglages illisibles ⇒ ``(None, None)`` : le barème applique alors la grille
    nationale et ignore la redevance — exactement le comportement d'aujourd'hui.
    """
    if company is None:
        return None, None
    tranches = None
    redevance = None
    try:
        from apps.parametres.selectors import residential_tranches_for
        surcharge = residential_tranches_for(company)
        if surcharge:
            # Le sélecteur rend un DICT pur (l'app fondation ne connaît pas
            # ``quote_engine``) : on le reconstruit en ``TrancheTable``, MÊME
            # idiome que ``builder.py`` — sinon la table serait itérée sur ses
            # CLÉS et le barème calculerait n'importe quoi.
            from apps.ventes.quote_engine.pricing import TrancheTable
            tranches = TrancheTable(
                surcharge['pairs'],
                selective_threshold=surcharge['selective_threshold'],
                boundary_tolerance=surcharge['boundary_tolerance'])
    except Exception:  # noqa: BLE001 — surcharge absente ⇒ grille nationale
        tranches = None
    try:
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings.get(company=company)
        brut = getattr(reglages, 'redevance_compteur_mad_mois', None)
        redevance = float(brut) if brut is not None else None
    except Exception:  # noqa: BLE001 — réglage absent ⇒ charge ignorée
        redevance = None
    return tranches, redevance


def etude_horaire_pour_devis(devis, *, kwc=None, batterie_kwh_utile=None,
                             data=None):
    """Bloc ``etude_horaire`` d'un devis RÉSIDENTIEL, ou ``None``.

    Lit tout ce dont le moteur a besoin sur le devis et son lead — toujours par
    les sélecteurs CRM (``apps.crm.selectors``), jamais ``apps.crm.models``.

    ``None`` (⇒ clé ABSENTE d'``etude_params``) quand l'ancrage réel manque :
    pas de facture, pas de localisation résoluble, ou pas de puissance. C'est
    la règle Z2 — l'appelant retombe alors sur le forfait ÉTIQUETÉ de
    ``pricing``, jamais sur un chiffre d'apparence factuelle.

    Ne lève JAMAIS : un calcul d'étude n'empêche pas d'enregistrer un devis.
    """
    try:
        return _etude_horaire_pour_devis(
            devis, kwc=kwc, batterie_kwh_utile=batterie_kwh_utile,
            data=data or {})
    except Exception:  # noqa: BLE001 — l'étude ne casse jamais un devis
        logger.warning('etude_horaire indisponible', exc_info=True)
        return None


def _etude_horaire_pour_devis(devis, *, kwc, batterie_kwh_utile, data):
    """Cœur de :func:`etude_horaire_pour_devis` (exceptions gérées au-dessus)."""
    from apps.crm.selectors import lead_bills_for_devis, site_location_for_devis

    puissance = kwc if kwc is not None else data.get('puissance_kwc')
    if _num(puissance) <= 0:
        return None

    localisation = site_location_for_devis(devis) or {}
    ville = data.get('client_city') or localisation.get('site_ville')
    lat = localisation.get('gps_lat')
    lon = localisation.get('gps_lng')

    company = getattr(devis, 'company', None)
    tranches, redevance = _reglages_tarifaires(company)

    etude_params = getattr(devis, 'etude_params', None) or {}
    factures_mensuelles = etude_params.get('factures_mensuelles_reelles')

    bills = lead_bills_for_devis(devis) or {}
    conso, source_conso, detail_conso = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=factures_mensuelles,
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'),
        tranches=tranches, redevance_compteur_mad=redevance)
    if not conso:
        return None

    if bills.get('distributeur'):
        detail_conso = {**detail_conso,
                        'distributeur': bills['distributeur']}

    occupation, occupation_source = occupation_du_devis(devis, data)
    equipements = equipements_du_devis(devis)

    capacite = (batterie_kwh_utile if batterie_kwh_utile is not None
                else data.get('batterie_kwh_total'))

    resultat = calculer_etude_horaire(
        kwc=puissance, conso_kwh_mensuelles=conso,
        ville=ville, lat=lat, lon=lon,
        occupation=occupation, equipements=equipements,
        batterie_kwh_utile=capacite,
        tranches=tranches, redevance_compteur_mad=redevance,
        source_conso=source_conso, detail_conso=detail_conso)
    if resultat is not None:
        resultat['occupation_source'] = occupation_source
    return resultat
