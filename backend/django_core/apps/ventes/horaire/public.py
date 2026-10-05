"""Blocs publiés du moteur horaire (SPL255, déplacé de ``etude_horaire.py``).

Estimation de consommation mensuelle, jours types publics, couverture
batterie publique (curseur « N batteries »), production annuelle et par
saison pour un kWc donné. Lit le moteur fin d'``etude_horaire`` (sens unique :
``etude_horaire`` n'importe PAS ce module en retour). Déplacement pur : corps
octet-identiques (seule la profondeur des imports relatifs locaux change),
prouvé par ``tests/golden/split_eh_public.json``.
"""
import logging
import math

from apps.parametres.pvgis_profils import JOURS_PAR_MOIS, productible_mensuel
from apps.ventes.courbes_journalieres import (
    COUCHES_REDISTRIBUTION,
    production_par_saison,
    renormalisation_redistribution,
)
from apps.ventes.etude_horaire import (
    _mettre_a_l_echelle,
    jours_types_annee,
    simuler_batterie_jour,
    simuler_batterie_pas_fins,
)
from apps.ventes.horaire.base import _num, saison_du_mois
from apps.ventes.horaire.batterie_lignes import (
    RENDEMENT_SOURCE_FICHE,
    RENDEMENT_SOURCE_HYPOTHESE,
)
from apps.ventes.quote_engine.pricing import BATTERY_ROUNDTRIP, PRODUCTION_DERATE

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.etude_horaire")


def estimation_conso_mensuelle(conso_kwh_mensuelles, equipements):
    """T4 (24/08/2026) — décomposition MENSUELLE base/ajouts/total de la
    consommation, contrat public ``estimation_conso`` (voir
    ``apps.ventes.public_views`` et ``apps/web/src/lib/proposition.ts``) :
    ``{base_mensuelle:[12], ajouts:{cle:[12]}, totale_mensuelle:[12]}``.

    ``None`` quand la série de 12 mois n'est pas exploitable OU qu'aucune
    couche d'équipement n'est active (rien à décomposer — la page garde alors
    son affichage actuel, un seul total sans détail).

    LA RÈGLE : les couches de REDISTRIBUTION
    (``courbes_journalieres.COUCHES_REDISTRIBUTION`` — piscine, clim,
    chauffe_eau) sont DÉJÀ dans la facture :
    leur « ajout » mensuel est donc RETIRÉ du ``base_mensuelle`` pour ne
    jamais compter deux fois la même énergie — la ligne « ajout » n'est qu'un
    ÉCLAIRAGE de ce que la facture contient déjà. Le véhicule électrique
    (mode ADDITION, charge future absente des factures passées) s'ajoute
    PAR-DESSUS le total sans rien retirer à la base — exactement la même
    distinction que :func:`courbes_journalieres.forme_consommation_detaillee`.
    ``totale_mensuelle`` retombe donc EXACTEMENT sur
    ``conso_kwh_mensuelles`` pour les mois sans VE, et l'excède seulement de
    la charge VE de ce mois.

    QJR16 (29/08/2026) — L'ÉNERGIE PUBLIÉE EST CELLE QUE LE MOTEUR PLACE.
    L'énergie BRUTE d'une couche de redistribution est ``kW × heures de sa
    fenêtre × jours du mois``, UNIQUEMENT dans les mois de sa saison active
    (``PISCINE_SAISONS``/``CLIM_SAISONS`` = été seulement ; le chauffe-eau
    L-BACK n'a pas de restriction saisonnière) — mais ce n'est PAS ce que la
    forme 24 h place. :func:`courbes_journalieres.forme_consommation_detaillee`
    pose les bosses PUIS RENORMALISE la journée au niveau facture : la couche
    y pèse ``brute × facteur``. Publier la brute faisait dépasser
    ``totale_mensuelle`` au-dessus de la consommation réelle du client dès que
    les équipements déclarés pesaient lourd — l'écrêtage ``max(0, …)`` de la
    base masquait le dépassement au lieu de l'empêcher, en contradiction avec
    la garantie ci-dessus. Le MÊME facteur est donc appliqué ici, et l'écrêtage
    devenu inatteignable est remplacé par un avertissement NOMMÉ (journalisé).

    QJR207 (31/08/2026) — « LE MÊME FACTEUR » EST DÉSORMAIS LE MÊME CODE.
    QJR16 en avait posé une SECONDE écriture, ``conso ÷ (conso + brutes)``, qui
    oubliait ce que le composeur fait d'abord : retirer l'énergie du véhicule
    électrique du niveau (``base = conso − VE``) puisqu'elle est rajoutée APRÈS
    la renormalisation, sans être rediluée. Dès qu'une couche VE coexistait
    avec une couche de redistribution, les deux facteurs divergeaient et le kWh
    par couche publié au client dépassait celui réellement placé dans la
    journée (mesuré : +19,17 kWh en juillet sur 600 kWh/mois + clim 1,4 kW + VE
    4 kWh/jour). La copie est supprimée :
    :func:`courbes_journalieres.renormalisation_redistribution` est l'unique
    définition, importée ici. Le contrat de sortie est INCHANGÉ (le total reste
    la facture + la seule charge VE) — seule la frontière entre ``base`` et
    ``ajouts`` bouge, vers ce que le moteur place vraiment.

    Ne lève jamais.
    """
    if not conso_kwh_mensuelles or len(conso_kwh_mensuelles) != 12:
        return None
    couches = equipements or {}
    if not couches:
        return None

    base = [max(0.0, _num(v)) for v in conso_kwh_mensuelles]
    ajouts = {}
    for index in range(12):
        numero = index + 1
        saison = saison_du_mois(numero)
        jours = JOURS_PAR_MOIS[index]
        conso_mois = base[index]

        # QJR15 — MÊME liste que le composeur de forme : ce qui est publié ici
        # comme un ajout mensuel est exactement ce que la forme 24 h place.
        # QJR16 — en DEUX temps : les énergies BRUTES d'abord, puis le facteur
        # de renormalisation du composeur, appliqué à toutes.
        brutes = {}
        for cle in COUCHES_REDISTRIBUTION:
            couche = couches.get(cle)
            if not couche or couche.get('mode') != 'redistribution':
                continue
            kw = _num(couche.get('kw'))
            heures = couche.get('heures') or ()
            if kw <= 0 or not heures:
                continue
            # CAD173 (Q12) — MÊME porte que le compositeur de forme : le mois
            # décide, pas la saison PVGIS. Deux portes différentes
            # publieraient au client d'autres mois que ceux réellement servis.
            from ..courbes_journalieres import couche_saisonniere_active
            if not couche_saisonniere_active(couche, mois=numero):
                continue
            brutes[cle] = kw * len(heures) * jours

        # QJR207 — LA CHARGE VE DU MOIS, LUE AVANT LE FACTEUR. Le composeur de
        # forme retire cette énergie du niveau AVANT de renormaliser (elle est
        # rajoutée telle quelle en passe 2, jamais rediluée) : la publication
        # doit donc la retirer aussi, sinon elle annonce par couche plus de kWh
        # que le moteur n'en place. Même porte que la passe 2 ci-dessous, d'où
        # la valeur réutilisée plus bas — jamais une seconde dérivation.
        ve_mois = 0.0
        ve = couches.get('ve')
        if ve and ve.get('mode') == 'addition':
            ve_kwh_jour = _num(ve.get('kwh_jour'))
            ve_saisons = ve.get('saisons')
            if ve_kwh_jour > 0 and (not ve_saisons or saison in ve_saisons):
                ve_mois = ve_kwh_jour * jours

        # LE FACTEUR — celui du composeur de forme, IMPORTÉ et non recopié
        # (``courbes_journalieres.renormalisation_redistribution``), lu à
        # l'échelle du mois : le rapport est invariant d'échelle, donc les
        # énergies mensuelles y donnent le facteur de la journée. Sans bosse
        # (ou sans base), il vaut 1,0 et le calcul retrouve son chemin d'avant,
        # à l'octet.
        brute_totale = sum(brutes.values())
        _base_mois, facteur = renormalisation_redistribution(
            conso_mois, ve_mois, brute_totale)

        for cle, brute in brutes.items():
            kwh_mois = round(brute * facteur, 2)
            ajouts.setdefault(cle, [0.0] * 12)
            ajouts[cle][index] = kwh_mois
            base[index] -= kwh_mois

        if base[index] < 0:
            # HORS DÉGÉNÉRESCENCE, inatteignable : la renormalisation garantit
            # ``Σ ajouts ≤ base ≤ conso``. Le seul cas restant est celui où la
            # charge VE déclarée dépasse à elle seule la facture — le composeur
            # de forme sort alors lui aussi de la facture (base nulle, bosses
            # non renormalisées). On le DIT au lieu de l'écrêter en silence.
            logger.warning(
                'estimation_conso_mensuelle: base négative après '
                'renormalisation (mois %d, conso %.2f kWh, ajouts %.2f kWh) — '
                'décomposition et composeur de forme ont divergé',
                numero, conso_mois, conso_mois - base[index])
            base[index] = 0.0

        if ve_mois > 0:
            ajouts.setdefault('ve', [0.0] * 12)
            ajouts['ve'][index] = round(ve_mois, 2)

    if not ajouts:
        return None
    base = [round(v, 2) for v in base]
    total = [round(base[i] + sum(vals[i] for vals in ajouts.values()), 2)
             for i in range(12)]
    return {
        'base_mensuelle': base,
        'ajouts': ajouts,
        'totale_mensuelle': total,
    }


#: T4 (24/08/2026) — les mois « jour type » servis au public (payload
#: ``jours_types``), MÊME quatre mois que le tunnel web
#: (``apps/web/src/lib/jourTypeData.ts``) : janvier/avril/juillet/novembre,
#: un par saison PVGIS (hiver/mi-saison×2/été).
JOURS_TYPES_PUBLICS_MOIS = (1, 4, 7, 11)


def jours_types_publics(*, kwc, conso_kwh_mensuelles, ville=None, lat=None,
                        lon=None, occupation=None, equipements=None,
                        jour_reference=None):
    """T4 (24/08/2026) — les 4 mois « jour type » du payload public
    ``jours_types`` (contrat ``apps/web/src/lib/proposition.ts
    ProposalResponse.jours_types``) : ``{"1"|"4"|"7"|"11": {prod_kw[24],
    conso_kw[24], conso_jour_kwh, prod_jour_kwh, autoconsomme_kwh,
    surplus_kwh}}``.

    RÉUTILISE :func:`jours_types_annee` — SOURCE UNIQUE des courbes horaires
    (même jour type que l'étude complète et le balayage du stockage) — puis
    n'en garde QUE les quatre mois publics, sans aucun second calcul de
    courbe. ``autoconsomme_kwh``/``surplus_kwh`` viennent de
    ``apps.ventes.solar_design.hourly_self_consumption`` (même intégrale
    Σ min(charge, production) que tout le reste du moteur).

    ``None`` quand ``jours_types_annee`` ne peut rien calculer, ou que l'UN
    des quatre mois publics manque (saison sans forme PVGIS) — discipline
    « tout ou rien » côté page (``proposalJoursTypes``) : jamais un jeu
    partiel. Ne lève jamais.

    ``jour_reference`` — QJR164/QJR45 : la DATE contre laquelle le moteur
    calcule (fenêtre Ramadan). Ce jeu part au CLIENT (payload public
    ``jours_types``) : sans elle, il retombait sur l'horloge du serveur au
    moment du rendu, donc un même devis pouvait servir deux jours types
    différents selon l'heure d'affichage — le pipeline pose la date, on la
    transmet. ``None`` ⇒ repli d'horloge posé au fond, dans
    :func:`jours_types_annee` et nulle part ailleurs.
    """
    try:
        from ..solar_design import hourly_self_consumption

        jours_types, _avertissements, _sources = jours_types_annee(
            kwc=kwc, conso_kwh_mensuelles=conso_kwh_mensuelles,
            ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements,
            jour_reference=jour_reference)
        if not jours_types:
            return None
        par_mois = {j['mois']: j for j in jours_types}

        out = {}
        for numero in JOURS_TYPES_PUBLICS_MOIS:
            jour = par_mois.get(numero)
            if jour is None:
                return None
            prod_24h = jour.get('prod_24h') or []
            conso_24h = jour.get('conso_24h') or []
            if len(prod_24h) != 24 or len(conso_24h) != 24:
                return None
            recouvrement = hourly_self_consumption(
                load_curve=conso_24h, production_curve=prod_24h)
            out[str(numero)] = {
                'prod_kw': [round(max(0.0, v), 3) for v in prod_24h],
                'conso_kw': [round(max(0.0, v), 3) for v in conso_24h],
                'conso_jour_kwh': round(jour.get('conso_jour_kwh') or 0.0, 2),
                'prod_jour_kwh': round(jour.get('prod_jour_kwh') or 0.0, 2),
                'autoconsomme_kwh': round(
                    recouvrement.get('self_consumed_kwh') or 0.0, 2),
                'surplus_kwh': round(
                    recouvrement.get('surplus_kwh') or 0.0, 2),
            }
        return out
    except Exception:  # noqa: BLE001 — un jeu jour-type ne casse jamais la page
        logger.warning('jours_types_publics indisponible', exc_info=True)
        return None


#: COUVBAT (26/08/2026) — plafond DUR du nombre de crans « N batteries »
#: ventilés heure par heure dans le payload public. Ce n'est PAS un avis sur ce
#: qui est vendable (c'est ``se_remplit_tous_les_jours``, et le balayage de
#: stockage, qui le disent) : c'est une borne de COÛT — chaque cran rejoue les
#: douze jours types.
#: O1 (revue adversariale Fable, 26/08/2026) — 12 → 16, ALIGNÉ sur
#: ``dimensionnement.MAX_PALIERS_ECHELLE``/``MAX_PALIERS_STOCKAGE`` (déjà
#: bumpés à 16 pour « monter à 30-40 kWh avec des modules de 5 kWh, pas de
#: problème » = 6 à 8 modules). Un plafond de COUVERTURE plus bas que celui
#: de l'échelle/du balayage listerait un palier PRICÉ que le curseur ne
#: pourrait jamais atteindre — la page afficherait un prix sans pouvoir en
#: montrer la couverture.
COUVERTURE_PACKS_PLAFOND = 16


def _pas_fins_ventilables(pas_fins):
    """COUVBAT — CHAQUE pas fin porte-t-il l'heure à laquelle il appartient ?

    Toute la ventilation horaire (bande « direct » comme bande « batterie »)
    range les pas de cinq minutes dans l'heure que dit leur clé ``heure``. Un
    pas sans cette clé serait compté dans les TOTAUX mais dans AUCUNE barre :
    la bande batterie sortirait silencieusement trop courte, et comme la page
    déduit le réseau par différence, l'écart serait attribué au RÉSEAU — on
    dirait au client qu'il importe une énergie qu'il n'importe pas.

    ``pas_fins_du_jour`` pose toujours cette clé ; ce garde-fou vise le jour où
    une autre chronologie arriverait par un autre chemin. Discipline Z2 : on
    OMET le bloc entier plutôt que de dessiner une répartition fausse.
    """
    return all(
        isinstance(etape.get('heure'), int) and 0 <= etape['heure'] < 24
        for etape in (pas_fins or ()))


def _direct_horaire_du_jour(jour_type):
    """COUVBAT — les 24 kWh d'autoconsommation DIRECTE d'un jour type.

    ``Σ min(consommation, production)``, la MÊME intégrale que
    :func:`solar_design.hourly_self_consumption` (pas horaire) et que
    :func:`recouvrement_pas_fins` (pas fin) — simplement gardée heure par
    heure au lieu d'être sommée tout de suite. Quand la chronologie fine
    existe, c'est ELLE qui est lue : sinon la barre dessinée raconterait un
    lissage que le moteur a précisément corrigé.
    """
    conso_24h = jour_type.get('conso_24h') or []
    prod_24h = jour_type.get('prod_24h') or []
    direct_h = [0.0] * 24
    pas_fins = jour_type.get('pas_fins')
    if pas_fins:
        for etape in pas_fins:
            heure = etape.get('heure')
            if not isinstance(heure, int) or not 0 <= heure < 24:
                continue
            direct_h[heure] += min(_num(etape['conso_kwh']),
                                   _num(etape['prod_kwh']))
        return direct_h
    for heure in range(min(len(conso_24h), len(prod_24h), 24)):
        direct_h[heure] = min(max(0.0, _num(conso_24h[heure])),
                              max(0.0, _num(prod_24h[heure])))
    return direct_h


def _deficit_du_jour(jour_type):
    """COUVBAT — le déficit journalier (kWh non couverts par le solaire direct).

    MÊME formule que :func:`balayer_stockage_horaire` (qui en tire son
    ``plafond_deficit_kwh``) : la chronologie fine quand elle existe, l'heure
    sinon. Deux formules différentes donneraient deux « autonomies complètes »
    contradictoires sur la même page.
    """
    pas_fins = jour_type.get('pas_fins')
    if pas_fins:
        return sum(max(0.0, _num(p['conso_kwh']) - _num(p['prod_kwh']))
                   for p in pas_fins)
    conso_24h = jour_type.get('conso_24h') or []
    prod_24h = jour_type.get('prod_24h') or []
    return sum(max(0.0, _num(conso_24h[h]) - _num(prod_24h[h]))
               for h in range(min(len(conso_24h), len(prod_24h))))


def _bornes_pour_packs(puissances_par_pack, nb_packs):
    """COUVBAT — les trois bornes de puissance d'une banque de ``nb_packs``.

    MÊME arithmétique que :func:`puissances_batterie_des_lignes` (« Σ valeur de
    fiche × quantité », puis « le plus petit des goulots PROUVÉS ») appliquée à
    une banque hypothétique : la puissance des PACKS suit le nombre de packs,
    celle du PORT BATTERIE de l'onduleur ne bouge pas (c'est le même onduleur).
    Une fiche muette reste muette — ``None``, jamais une puissance supposée :
    le moteur retombe alors sur sa règle conservatrice, exactement comme
    aujourd'hui.
    """
    par_pack = puissances_par_pack or {}
    packs_dech = _num(par_pack.get('pack_decharge_kw')) * nb_packs or None
    packs_charge = _num(par_pack.get('pack_charge_kw')) * nb_packs or None
    ond_dech = _num(par_pack.get('ond_decharge_kw')) or None
    ond_charge = _num(par_pack.get('ond_charge_kw')) or None
    charges_prouvees = [v for v in (packs_charge, ond_charge) if v]
    borne_charge = min(charges_prouvees) if charges_prouvees else None
    return packs_dech, ond_dech, borne_charge


def couverture_batterie_publique(*, kwc, conso_kwh_mensuelles,
                                 capacite_utile_pack_kwh, nb_packs_max,
                                 nb_packs_plancher=0,
                                 ville=None, lat=None, lon=None,
                                 occupation=None, equipements=None,
                                 puissances_par_pack=None,
                                 batterie_rendement=None,
                                 batterie_rendement_source=None,
                                 jour_reference=None):
    """COUVBAT (ordre fondateur, 26/08/2026) — CE QUE LE CURSEUR « N BATTERIES »
    DOIT MONTRER : la part de la consommation du client réellement COUVERTE
    (solaire direct + batterie) pour chaque N, heure par heure ET sur l'année,
    plus le nombre de batteries qui couvrirait TOUTE la journée et TOUTE la
    nuit.

    Contrat public : ``apps/ventes/contract_samples/couverture_batterie.json``
    (clé ``couverture_batterie`` du payload ``proposal_data``).

    POURQUOI CE CALCUL EST ICI ET PAS DANS LE NAVIGATEUR. La page savait déjà
    dessiner trois bandes « direct / batterie / réseau », mais à partir d'une
    SILHOUETTE générique remise à l'échelle du kWh journalier — un second
    moteur, plus grossier, qui pouvait contredire l'étude. Ici, chaque N rejoue
    les MÊMES douze jours types (:func:`jours_types_annee`, source unique) et
    le MÊME simulateur de batterie que l'étude complète et le balayage du
    stockage (chronologie fine quand elle existe, heure sinon). Le navigateur
    n'a plus qu'à LIRE.

    L'AUTONOMIE COMPLÈTE, ET SON HONNÊTETÉ. La capacité qui couvrirait tout le
    jour type le plus gourmand vaut ``déficit maximal ÷ rendement`` — c'est
    EXACTEMENT le ``plafond_deficit_kwh`` du balayage (au-delà, un kWh de plus
    ne peut RIEN restituer de plus). Cette capacité peut DÉPASSER la plus
    grosse banque que ce toit remplit chaque jour
    (``plafond_remplissage_kwh`` = surplus quotidien du mois le plus faible,
    la règle fondateur « la batterie doit se remplir tous les jours ») : le
    bloc le DIT (``se_remplit_tous_les_jours: false`` +
    ``nb_packs_remplissables``) au lieu de cacher le chiffre ou de le vendre.

    ``None`` (jamais un chiffre inventé) quand l'année n'est pas complète,
    quand la capacité utile d'un pack n'est pas connue, ou sur toute erreur —
    la page garde alors EXACTEMENT son affichage d'avant. Ne lève jamais.

    ``jour_reference`` — QJR164/QJR45 : même transmission que les trois autres
    appelants de :func:`jours_types_annee`. Ce bloc part au CLIENT (payload
    ``couverture_batterie``) ; il doit donc rejouer les jours types du MÊME
    jour que l'étude complète et le balayage, pas ceux de l'horloge du serveur
    au moment du rendu. ``None`` ⇒ repli d'horloge posé au fond, dans
    :func:`jours_types_annee` et nulle part ailleurs.

    ``batterie_rendement`` / ``batterie_rendement_source`` — QJR412 : MÊME
    discipline que :func:`calculer_etude_horaire` (QJR137). Avant cette
    tâche, ce bloc simulait TOUJOURS à ``pricing.BATTERY_ROUNDTRIP`` (0,90) et
    le publiait comme s'il décrivait la batterie vendue, sans dire que
    c'était un forfait — exactement ce que la règle zéro-chiffre-inventé
    interdit. Sans valeur prouvée (``rendement_batterie_des_lignes``, lue par
    l'appelant), l'hypothèse de référence s'applique et se DÉCLARE
    (``rendement_source``) — jamais un chiffre nu.
    """
    try:
        capacite_pack = _num(capacite_utile_pack_kwh)
        if capacite_pack <= 0:
            return None

        # QJR412 — LE RENDEMENT ALLER-RETOUR VIENT DE LA FICHE QUAND ELLE LE
        # PUBLIE (même résolution que QJR137 dans :func:`calculer_etude_horaire`).
        rendement = _num(batterie_rendement)
        if not 0 < rendement <= 1:
            rendement = BATTERY_ROUNDTRIP
            rendement_source = RENDEMENT_SOURCE_HYPOTHESE
        else:
            rendement_source = (batterie_rendement_source
                                or RENDEMENT_SOURCE_FICHE)
        try:
            n_max = int(nb_packs_max)
        except (TypeError, ValueError):
            return None
        try:
            plancher = max(0, int(nb_packs_plancher))
        except (TypeError, ValueError):
            plancher = 0
        # LE PLAFOND DE COÛT NE DOIT JAMAIS RENDRE LE DEVIS INATTEIGNABLE
        # (revue du 26/08/2026). Un devis qui porterait plus de packs que le
        # plafond verrait SA PROPRE configuration tomber hors du curseur : la
        # page servirait alors des crans sans couverture, qui repartiraient en
        # silence vers le simulateur approché. Le nombre de packs RÉELLEMENT
        # au devis est donc un PLANCHER, jamais raboté.
        n_max = max(0, min(n_max, COUVERTURE_PACKS_PLAFOND), plancher)

        jours_types, _avertissements, _sources = jours_types_annee(
            kwc=kwc, conso_kwh_mensuelles=conso_kwh_mensuelles,
            ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements,
            jour_reference=jour_reference)
        if not jours_types or len(jours_types) != 12:
            return None

        # ── Passe 1 : ce qui ne dépend PAS du nombre de batteries ──
        prepares = []
        surplus_min = None
        surplus_min_mois = None
        deficit_max = 0.0
        deficit_max_mois = None
        conso_annuelle = 0.0
        for jour in jours_types:
            # Une chronologie fine non ventilable rendrait TOUTES les bandes
            # de ce bloc fausses (voir _pas_fins_ventilables) : on omet le
            # bloc entier, la page retombe sur son affichage d'avant.
            if not _pas_fins_ventilables(jour.get('pas_fins')):
                return None
            direct_h = _direct_horaire_du_jour(jour)
            direct_jour = sum(direct_h)
            surplus_jour = max(0.0, _num(jour['prod_jour_kwh']) - direct_jour)
            deficit_jour = _deficit_du_jour(jour)
            if surplus_min is None or surplus_jour < surplus_min:
                surplus_min = surplus_jour
                surplus_min_mois = jour['mois']
            if deficit_jour > deficit_max:
                deficit_max = deficit_jour
                deficit_max_mois = jour['mois']
            conso_annuelle += _num(jour['conso_mois_kwh'])
            prepares.append((jour, direct_h, direct_jour))
        if conso_annuelle <= 0:
            return None

        plafond_remplissage = max(0.0, surplus_min or 0.0)
        plafond_remplissage_publie = round(plafond_remplissage, 2)

        # ── L'AUTONOMIE COMPLÈTE, calculée AVANT les crans ──
        # Elle FIXE la portée du curseur : le fondateur veut pouvoir explorer
        # jusqu'à l'autonomie complète (« monter à 30-40 kWh avec des modules
        # de 5 kWh, pas de problème »). Un repère qu'on ne peut pas atteindre
        # avec le curseur ne se compare à rien.
        capacite_requise = (deficit_max / rendement
                            if rendement > 0 else deficit_max)
        nb_packs_autonomie = int(math.ceil(
            capacite_requise / capacite_pack)) if capacite_requise > 0 else 0
        n_max = max(n_max, min(nb_packs_autonomie, COUVERTURE_PACKS_PLAFOND),
                    plancher)

        def _palier(nb_packs):
            """Un cran du curseur : l'année ET les quatre jours types publics."""
            capacite = nb_packs * capacite_pack
            borne_dech, borne_dech_ond, borne_charge = _bornes_pour_packs(
                puissances_par_pack, nb_packs)
            direct_annuel = 0.0
            batterie_annuel = 0.0
            jours_publics = {}
            for jour, direct_h, direct_jour in prepares:
                jours = jour['jours']
                conso_24h = jour['conso_24h']
                pas_fins = jour.get('pas_fins')
                if capacite > 0:
                    if pas_fins:
                        sim = simuler_batterie_pas_fins(
                            pas_fins, capacite,
                            puissance_decharge_kw=borne_dech,
                            puissance_decharge_onduleur_kw=borne_dech_ond,
                            puissance_charge_kw=borne_charge,
                            rendement=rendement)
                    else:
                        sim = simuler_batterie_jour(
                            conso_24h, jour['prod_24h'], capacite,
                            puissance_charge_kw=borne_charge,
                            rendement=rendement)
                else:
                    sim = {'restitue_kwh': 0.0, 'restitue_24h': [0.0] * 24}
                restitue = _num(sim['restitue_kwh'])
                # MÊME BORNE QUE LE BALAYAGE (``balayer_stockage_horaire``) :
                # l'autoconsommation d'un jour ne dépasse ni la consommation ni
                # la production de ce jour. Ceinture, jamais contraignante en
                # pratique — mais deux formules divergentes finiraient par
                # afficher deux couvertures différentes du même client.
                auto_jour = min(direct_jour + restitue,
                                _num(jour['conso_jour_kwh']),
                                _num(jour['prod_jour_kwh']))
                restitue_effectif = max(0.0, auto_jour - direct_jour)
                restitue_h = _mettre_a_l_echelle(
                    sim['restitue_24h'], restitue, restitue_effectif)
                direct_annuel += direct_jour * jours
                batterie_annuel += restitue_effectif * jours
                if jour['mois'] in JOURS_TYPES_PUBLICS_MOIS:
                    reseau_h = []
                    for heure in range(24):
                        conso_h = (max(0.0, _num(conso_24h[heure]))
                                   if heure < len(conso_24h) else 0.0)
                        reste = conso_h - direct_h[heure] - restitue_h[heure]
                        reseau_h.append(max(0.0, reste))
                    # LE TAUX DE CE JOUR-LÀ, SERVI (revue du 26/08/2026). La
                    # page affiche le graphe d'UN jour type et, juste à côté,
                    # un taux de couverture : si l'un parle du jour et l'autre
                    # de l'année, la ligne se contredit elle-même. Le taux
                    # ANNUEL reste servi à part (``couverture_pct`` du cran) —
                    # il n'habille que le repère d'autonomie, qui le nomme.
                    conso_jour = _num(jour['conso_jour_kwh'])
                    jours_publics[str(jour['mois'])] = {
                        'direct_kwh': [round(v, 3) for v in direct_h],
                        'batterie_kwh': [round(v, 3) for v in restitue_h],
                        'reseau_kwh': [round(v, 3) for v in reseau_h],
                        'couverture_pct': (
                            round(100.0 * (direct_jour + restitue_effectif)
                                  / conso_jour, 1) if conso_jour > 0 else 0.0),
                    }
            couvert = direct_annuel + batterie_annuel
            return {
                'nb_packs': nb_packs,
                'capacite_kwh': round(capacite, 2),
                'couverture_pct': round(
                    100.0 * couvert / conso_annuelle, 1),
                'direct_annuel_kwh': round(direct_annuel, 2),
                'batterie_annuel_kwh': round(batterie_annuel, 2),
                'reseau_annuel_kwh': round(
                    max(0.0, conso_annuelle - couvert), 2),
                'se_remplit_tous_les_jours': bool(
                    round(capacite, 2) <= plafond_remplissage_publie),
                'jours_types': jours_publics,
            }

        pas = [_palier(n) for n in range(n_max + 1)]

        capacite_autonomie = nb_packs_autonomie * capacite_pack
        deja_calcule = next(
            (p for p in pas if p['nb_packs'] == nb_packs_autonomie), None)
        if deja_calcule is None and nb_packs_autonomie > 0:
            # Le cran d'autonomie dépasse le plafond DUR des crans servis : on
            # le calcule quand même — pouvoir DIRE « 14 batteries ≈ 99 % de
            # votre consommation » vaut un parcours de plus. Sa ventilation
            # horaire, elle, n'est pas servie (rien ne la dessinerait).
            deja_calcule = _palier(nb_packs_autonomie)
        autonomie = {
            'nb_packs': nb_packs_autonomie,
            'capacite_kwh': round(capacite_autonomie, 2),
            'deficit_jour_max_kwh': round(deficit_max, 2),
            'mois': deficit_max_mois,
            'se_remplit_tous_les_jours': bool(
                round(capacite_autonomie, 2) <= plafond_remplissage_publie),
            'nb_packs_remplissables': int(
                plafond_remplissage_publie // capacite_pack),
            'capacite_remplissable_max_kwh': plafond_remplissage_publie,
            'mois_remplissage_min': surplus_min_mois,
            'couverture_pct': (deja_calcule['couverture_pct']
                               if deja_calcule else None),
            'dans_le_curseur': bool(nb_packs_autonomie <= n_max),
        }

        return {
            'capacite_utile_pack_kwh': round(capacite_pack, 3),
            # QJR412 — CE rendement (fiche quand elle le prouve, hypothèse
            # étiquetée sinon) : jamais plus un 0,90 muet présenté comme la
            # batterie vendue.
            'rendement': round(rendement, 4),
            'rendement_source': rendement_source,
            'conso_annuelle_kwh': round(conso_annuelle, 2),
            'mois_jours_types': list(JOURS_TYPES_PUBLICS_MOIS),
            'nb_packs_max': n_max,
            'pas': pas,
            'autonomie_complete': autonomie,
        }
    except Exception:  # noqa: BLE001 — un bloc d'affichage ne casse pas la page
        logger.warning('couverture_batterie indisponible', exc_info=True)
        return None


def production_annuelle_pour_kwc(kwc, *, ville=None, lat=None, lon=None):
    """PACT10 (« deux optimiseurs ») — production ANNUELLE (kWh) pour un
    ``kwc`` DONNÉ, lecture pure, aucune persistance.

    Réutilise EXACTEMENT la même dérivation que :func:`jours_types_annee`
    (productible mensuel PVGIS × kWc × ``PRODUCTION_DERATE`` — le MÊME derate
    que ``pricing``/``builder``, jamais un second facteur), sommée sur les
    douze mois — jamais un second calcul de productible. Sert
    ``dimensionnement_options.<sans|avec>.production_annuelle_kwh`` : chaque
    option d'un devis résidentiel peut porter son PROPRE kWc (nb panneaux
    différent entre « Sans » et « Avec batterie »), donc sa propre annuelle.

    ``None`` (jamais un chiffre inventé) quand ``kwc`` est absent/nul, ou que
    le productible PVGIS n'est pas résolu (ni coordonnées live, ni ville
    reconnue) — même discipline Z2 que le reste du moteur horaire."""
    try:
        kwc_f = _num(kwc, 0.0)
        if kwc_f <= 0:
            return None
        mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
        if not mensuel:
            return None
        valeurs, _source = mensuel
        total = sum(_num(v) for v in valeurs) * kwc_f * PRODUCTION_DERATE
        return round(total) if total > 0 else None
    except Exception:  # noqa: BLE001 — un bloc d'affichage ne leve jamais
        logger.warning('production_annuelle_pour_kwc indisponible', exc_info=True)
        return None


def production_journaliere_par_saison(kwc, *, ville=None, lat=None, lon=None):
    """PACT10 (« deux optimiseurs ») — bloc production PAR SAISON pour un
    ``kwc`` DONNÉ, MÊME FORME que ``courbes_journalieres.production_par_saison`` (celle
    déjà servie sous ``payload.courbes_journalieres.production``) : chaque
    saison porte ``forme`` (24 parts, heure locale, somme 1,0), ``kwh_jour``,
    ``pic_kw`` (puissance, jamais des kWh) et ses deux ``source*``.

    Réutilise les MÊMES primitives PVGIS que ``courbes_journalieres`` (aucune
    seconde dérivation de la forme horaire ou du productible) : sert
    ``production_par_option`` quand un devis résidentiel porte deux
    dimensionnements DIVERGENTS (kWc différent par option) — la page ne peut
    alors plus lire une seule courbe de production pour les deux cartes
    d'option. Lecture pure, aucune persistance.

    ``{}`` (jamais un chiffre inventé) quand ``kwc`` est absent/nul ou que le
    productible/la forme PVGIS ne sont pas résolus."""
    try:
        kwc_f = _num(kwc, 0.0)
        if kwc_f <= 0:
            return {}
        mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
        if not mensuel:
            return {}
        # QJR611 — une seule boucle : on délègue à courbes_journalieres.
        return production_par_saison(kwc_f, mensuel, ville, lat, lon)
    except Exception:  # noqa: BLE001 — un bloc d'affichage ne leve jamais
        logger.warning(
            'production_journaliere_par_saison indisponible', exc_info=True)
        return {}
