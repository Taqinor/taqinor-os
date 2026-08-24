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

L-GLITCH (ordre fondateur, 24/08/2026) — LA RÉSOLUTION FINE. « are you also
counting the small glitches in your calculus now ? those glitches might go up
for 30min ». Un pas HORAIRE lisse les pointes d'appareil et fait croire qu'une
pompe de piscine ou une climatisation est autoconsommée alors que sa pointe
dépasse la production. Les équipements DÉCLARÉS à l'appel dont la puissance est
CONNUE sont donc restitués en IMPULSIONS dérivées de leur propre couche, et les
heures qui en portent sont recalculées à cinq minutes. Mêmes kWh, pointes
visibles — voir la section « 3 bis » plus bas pour la méthode, ses sources et
ses choix d'interim.

RÈGLE #4 : ce module ne rend AUCUN PDF, ne change AUCUN statut, n'expose AUCUN
prix d'achat ni marge. Il CALCULE et rend un dict ; c'est l'appelant qui le
range dans ``Devis.etude_params['etude_horaire']``.

Fonctions PURES au cœur (aucun ORM) ; seule :func:`etude_horaire_pour_devis`
lit un ``Devis`` et le CRM, toujours via ``apps.crm.selectors``.
"""
from __future__ import annotations

import logging
import math

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
    forme_consommation_detaillee,
    occupation_du_devis,
)
from apps.ventes.quote_engine import bareme
from apps.ventes.quote_engine.pricing import BATTERY_ROUNDTRIP, PRODUCTION_DERATE
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


def serie_kwh_depuis_mad(serie_mad, *, tranches=None, charges_fixes_mad=None,
                         tppan=True, millesime=bareme.MILLESIME_COURANT):
    """12 montants MAD/mois → 12 consommations kWh/mois (back-calcul barème).

    ORDRE FONDATEUR : « back-calculating the kwh he consumed looking at his
    bill and tranches ». L'inversion passe par
    :func:`~apps.ventes.quote_engine.bareme.kwh_depuis_facture_mad` — les
    VRAIES tranches (progressif ≤ 150, sélectif au-delà avec tolérance), les
    DEUX lignes fixes (location du compteur + entretien du branchement) et la
    TPPAN retirées correctement. JAMAIS une division par un prix moyen.

    JOURS DE RÉFÉRENCE. Le lead déclare un montant « par mois », pas une
    période de relevé : on inverse donc sur le mois PLEIN de 30 jours
    (:data:`bareme.TPPAN_JOURS_REFERENCE`), la base même du barème TPPAN. La
    proratisation aux jours réels n'intervient qu'ensuite, mois par mois, dans
    le calcul des économies.

    Mémoïsé : le lead ne porte au plus que deux montants distincts, on
    n'inverse donc qu'au plus deux fois.

    Renvoie ``(kwh_mensuels, detail)``, ou ``(None, {})`` si la série d'entrée
    est inexploitable.
    """
    if not serie_mad or len(serie_mad) != 12:
        return None, {}

    cache = {}

    def _inverser(mad):
        if mad not in cache:
            cache[mad] = bareme.kwh_depuis_facture_mad(
                mad, tranches=tranches, charges_fixes_mad=charges_fixes_mad,
                tppan=tppan, millesime=millesime)
        return cache[mad]

    kwh = []
    for mad in serie_mad:
        resultat = _inverser(mad)
        kwh.append(resultat['kwh_mensuel'])

    if not any(v > 0 for v in kwh):
        return None, {}

    exemple = next(iter(cache.values()))
    return kwh, {
        'methode': 'inversion_bareme_tranches',
        'charges_fixes_mad': round(exemple['location_entretien_mad'], 2),
        'charges_fixes_source': exemple['charges_fixes_source'],
        'millesime': millesime,
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

    RÉGIME ÉTABLI (ordre fondateur, 24/08/2026 — « si tu calcules la simple
    décharge de la nuit... les petites décharges de la journée et de la
    matinée en plus ») : le jour type étant périodique, l'état de charge se
    REPORTE d'un jour sur l'autre — on itère le cycle jusqu'à l'équilibre
    (l'état de 00 h = l'état de 24 h), si bien que le reliquat du soir sert
    le déficit d'avant l'aube. L'ancien départ-à-vide tronquait cette
    décharge nocturne. À l'équilibre périodique, la conservation d'énergie
    donne exactement « restitué = 0,90 × chargé » sur le cycle : l'invariant
    « restitué ≤ 0,90 × chargé » épinglé par les tests reste vrai par
    construction.

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

    def _cycle(soc_depart):
        soc = max(0.0, min(_num(soc_depart), capacite))
        pic_soc = soc
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
        return charge_total, restitue_total, pic_soc, soc

    # Convergence vers l'équilibre périodique : l'état de fin de journée
    # devient l'état de départ du cycle suivant. Borné par la capacité et
    # monotone, le point fixe est atteint en quelques itérations (garde-fou
    # à 8 pour ne jamais boucler sur un profil dégénéré).
    soc_depart = 0.0
    charge_total = restitue_total = pic_soc = 0.0
    for _ in range(8):
        charge_total, restitue_total, pic_soc, soc_fin = _cycle(soc_depart)
        if abs(soc_fin - soc_depart) <= 1e-6:
            break
        soc_depart = soc_fin

    # À l'équilibre, ce qui a été RESTITUÉ pendant le cycle ne peut excéder
    # 0,90 × ce qui a été CHARGÉ pendant ce même cycle (conservation, l'état
    # de départ égalant l'état d'arrivée). On borne explicitement pour que
    # l'invariant épinglé reste vrai même hors convergence parfaite.
    restitue_total = min(restitue_total, rendement * charge_total)

    return {
        'restitue_kwh': restitue_total,
        'charge_kwh': charge_total,
        'capacite_utilisee_kwh': pic_soc,
    }


# ════════════════════════════════════════════════════════════════════════════
# 3 bis. L-GLITCH — LES IMPULSIONS D'APPAREIL, ET LA RÉSOLUTION FINE
# ════════════════════════════════════════════════════════════════════════════
# ORDRE FONDATEUR (24/08/2026) : « are you also counting the small glitches in
# your calculus now ? those glitches might go up for 30min », puis la précision
# du même jour : « j'ai dit JUSQU'À 30 min... tu cherches le timing le plus
# réaliste ».
#
# LE BIAIS QUE CETTE COUCHE CORRIGE (recherche du 24/08/2026, sourcée). Un pas
# de temps HORAIRE lisse les pointes d'appareil : l'énergie d'un compresseur qui
# tire 3 kW pendant une demi-heure est étalée en 1,5 kW pendant soixante
# minutes. Sous la courbe de production, ce lissage fait croire que tout est
# autoconsommé, alors qu'en réalité la pointe DÉPASSE la production pendant la
# demi-heure et retombe à zéro ensuite. Conséquences mesurées dans la
# littérature : l'autoconsommation directe est SURESTIMÉE (~9 points,
# Ayala-Gilardón & al. 2018), le besoin de batterie SOUS-estimé ; le seuil
# critique est l'appareil ≥ 2 kW (Beck & al. 2016) ; l'erreur est maximale quand
# production ≈ consommation.
#
# CE QU'ON NE FAIT PAS. Aucun FACTEUR DE CORRECTION publié n'existe pour ce
# biais, et aucun modèle stochastique européen de charge n'est transposable au
# parc marocain : en inventer un violerait la règle « zéro chiffre inventé ».
#
# CE QU'ON FAIT — INJECTION D'IMPULSIONS DÉRIVÉES. Pour chaque équipement que le
# client a DÉCLARÉ à l'appel ET dont la puissance est CONNUE (piscine : la
# puissance de pompe saisie ; clim : 1,4 kW/unité du mémo × nombre de pièces),
# l'énergie que SA couche L4 place déjà dans une heure donnée n'est pas
# réinventée : elle est CONCENTRÉE. La puissance est la puissance déclarée ; la
# durée en découle par division. 1,5 kWh d'un appareil de 3 kW = 30 minutes à
# 3 kW — le « glitch » du fondateur, DÉRIVÉ d'une donnée réelle, pas décrété.
# Le total de kWh du jour, du mois et de l'année ne bouge pas d'un iota : c'est
# un RAFFINEMENT de la même énergie (conservation épinglée par test).
#
# LE PLAFOND DES 30 MINUTES EST UN PLAFOND, PAS UNE DURÉE (correction fondateur
# du 24/08). Quand l'énergie divisée par la puissance dépasse 30 minutes,
# l'énergie s'éclate en PLUSIEURS rafales égales de 30 minutes au plus : les
# compresseurs et les pompes CYCLENT, ils ne tiennent pas une heure pleine d'un
# seul tenant.

#: PLAFOND FONDATEUR (24/08/2026, verbatim « j'ai dit JUSQU'À 30 min »). Aucune
#: rafale ne dépasse cette durée : au-delà, l'énergie s'éclate en plusieurs.
#: Ce n'est PAS un paramètre d'ajustement — c'est une borne donnée par le
#: fondateur, que la calibration Deye pourra resserrer, jamais desserrer.
RAFALE_PLAFOND_MINUTES = 30.0

#: Pas d'échantillonnage de la résolution fine — 5 minutes, la granularité des
#: exports de la flotte d'onduleurs Deye du fondateur. C'est la seule
#: « vérité terrain » disponible aujourd'hui pour trancher plus fin que l'heure,
#: donc le seul pas qu'on s'autorise : descendre à la minute produirait une
#: précision que rien ne pourrait vérifier.
PAS_FIN_MINUTES = 5.0
SOUS_PAS_PAR_HEURE = 12  # 60 / 5

#: POSITION de chaque rafale dans sa fenêtre, en part de la marge disponible
#: (0,0 = collée au début, 0,5 = centrée, 1,0 = collée à la fin).
#:
#: VALEUR D'INTERIM ASSUMÉE — À CALIBRER SUR LES EXPORTS DEYE 5 MIN DE LA FLOTTE
#: DU FONDATEUR (le banc de calibration est le chantier suivant). Rien dans les
#: données collectées aujourd'hui ne dit à quelle minute de l'heure un
#: compresseur démarre : on POSE le début de fenêtre, on le DIT, et on range ce
#: choix dans une constante nommée pour que la calibration le remplace sans
#: toucher une ligne de moteur.
RAFALE_POSITION_INTERIM = 0.0

#: Numéro de forme du bloc ``glitch`` servi en sortie (indépendant de
#: :data:`ETUDE_HORAIRE_VERSION` — voir le commentaire de
#: :func:`calculer_etude_horaire`).
GLITCH_VERSION = 1

#: PROFIL DE CYCLE PAR ÉQUIPEMENT — des DONNÉES, jamais des littéraux dispersés
#: dans le moteur : la calibration Deye remplacera ces lignes et rien d'autre.
#:
#: ``puissance`` dit d'où vient la puissance concentrée (règle « zéro chiffre
#: inventé » : jamais une puissance supposée). ``cycle`` dit d'où vient la
#: sous-structure (nombre et position des rafales) — aujourd'hui l'interim
#: ci-dessus pour tout le monde. Le jour où une source RÉELLE documente un cycle
#: (le mémo de consommation pour la clim, une fiche constructeur pour une pompe),
#: elle prime sur l'interim et se cite ici.
PROFILS_RAFALE = {
    'piscine': {
        'actif': True,
        'plafond_minutes': RAFALE_PLAFOND_MINUTES,
        'position_fenetre': RAFALE_POSITION_INTERIM,
        'puissance': 'lead:equip_piscine_pompe_kw',
        'cycle': 'interim_a_calibrer_deye_5min',
    },
    'clim': {
        'actif': True,
        'plafond_minutes': RAFALE_PLAFOND_MINUTES,
        'position_fenetre': RAFALE_POSITION_INTERIM,
        'puissance': 'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h',
        'cycle': 'interim_a_calibrer_deye_5min',
    },
    # CHAUFFE-EAU — EXCEPTION DOCUMENTÉE, INERTE AUJOURD'HUI. Un chauffe-eau
    # électrique chauffe EN CONTINU jusqu'à coupure du thermostat : il ne cycle
    # pas comme un compresseur, et sa rafale serait donc d'un seul tenant.
    # Elle resterait néanmoins plafonnée à 30 minutes tant que rien de mieux
    # n'est prouvé (le plafond fondateur ne se desserre pas sur une intuition).
    # RIEN NE SORT AUJOURD'HUI : aucune puissance de chauffe-eau n'est collectée
    # au téléphone, donc ``courbes_journalieres`` ne compose AUCUNE couche pour
    # lui — l'équipement reste informatif. ``actif: False`` le dit à voix haute
    # plutôt que de le laisser deviner par l'absence.
    'chauffe_eau': {
        'actif': False,
        'plafond_minutes': RAFALE_PLAFOND_MINUTES,
        'position_fenetre': RAFALE_POSITION_INTERIM,
        'puissance': None,
        'cycle': 'chauffe_continue_jusqu_a_coupure_thermostat',
        'motif_inactif': 'aucune_puissance_collectee',
    },
    # VÉHICULE ÉLECTRIQUE — DÉLIBÉRÉMENT ABSENT DE CETTE TABLE. Sa couche L4
    # porte une ÉNERGIE (kWh/jour ADEME × km déclarés) répartie sur la fenêtre
    # nocturne, et la puissance du CHARGEUR n'est pas collectée. La seule
    # « puissance » qu'on pourrait en tirer est kWh_jour ÷ 9 h — c'est-à-dire
    # exactement le plat que la couche pose déjà : concentrer à cette
    # puissance-là ne changerait rien, et concentrer à une puissance de chargeur
    # supposée (3,7 ? 7,4 ? 11 kW ?) serait un chiffre inventé. On ne fait donc
    # RIEN, conformément à l'ordre : « uniquement si une puissance dérivable
    # existe, sinon rien ».
}

#: Profil de repli quand une couche n'a pas d'entrée nommée — jamais un plafond
#: plus large que celui du fondateur.
PROFIL_RAFALE_DEFAUT = {
    'actif': True,
    'plafond_minutes': RAFALE_PLAFOND_MINUTES,
    'position_fenetre': RAFALE_POSITION_INTERIM,
    'puissance': 'couche_l4',
    'cycle': 'interim_a_calibrer_deye_5min',
}


def rafales_de_l_heure(energie_kwh, puissance_kw, *, profil=None):
    """Découpe l'énergie d'UNE heure en rafales à ``puissance_kw``, ou ``None``.

    L'unique dérivation de la couche : ``durée = énergie ÷ puissance``. 1,5 kWh
    d'un appareil de 3 kW font 30 minutes à 3 kW — pas un pourcentage de marche
    choisi, pas un profil emprunté à une autre géographie.

    * La durée totale est bornée à 60 minutes : au-delà, l'appareil consomme
      déjà plus que sa puissance nominale sur l'heure (donnée incohérente ou
      plusieurs unités), et il n'y a plus rien à concentrer.
    * Le PLAFOND fondateur découpe ensuite : ``n = ⌈durée ÷ plafond⌉`` rafales
      ÉGALES de ``durée ÷ n`` minutes, une par fenêtre de ``60 ÷ n`` minutes.
      Une clim dont la couche pèse 45 minutes sort donc en DEUX rafales de
      22,5 minutes, pas en un bloc continu.
    * La POSITION dans la fenêtre vient du profil (interim documenté).

    Renvoie ``{puissance_kw, duree_totale_min, nb_rafales, duree_rafale_min,
    fenetres: [(début_min, fin_min)], energie_rafales_kwh}``.
    """
    energie = _num(energie_kwh)
    puissance = _num(puissance_kw)
    if energie <= 0 or puissance <= 0:
        return None

    profil = profil or PROFIL_RAFALE_DEFAUT
    plafond = _num(profil.get('plafond_minutes'), RAFALE_PLAFOND_MINUTES)
    # Le plafond fondateur est un MAXIMUM : un profil ne peut que le resserrer.
    if not 0 < plafond <= RAFALE_PLAFOND_MINUTES:
        plafond = RAFALE_PLAFOND_MINUTES

    duree_totale = min(60.0, energie / puissance * 60.0)
    # La tolérance évite qu'une durée EXACTEMENT égale au plafond (30,0 min)
    # ne se scinde en deux rafales à cause d'un dernier bit flottant.
    nb = max(1, int(math.ceil(duree_totale / plafond - 1e-9)))
    duree_rafale = duree_totale / nb
    fenetre = 60.0 / nb

    position = _num(profil.get('position_fenetre'), RAFALE_POSITION_INTERIM)
    position = min(1.0, max(0.0, position))
    decalage = position * max(0.0, fenetre - duree_rafale)

    fenetres = []
    for index in range(nb):
        debut = index * fenetre + decalage
        fenetres.append((debut, debut + duree_rafale))

    return {
        'puissance_kw': puissance,
        'duree_totale_min': duree_totale,
        'nb_rafales': nb,
        'duree_rafale_min': duree_rafale,
        'fenetres': fenetres,
        'energie_rafales_kwh': puissance * duree_totale / 60.0,
    }


def _repartir_rafale(parts, debut_min, fin_min, puissance_kw,
                     pas_minutes=PAS_FIN_MINUTES):
    """Verse l'énergie d'une rafale dans les sous-pas qu'elle recouvre.

    Le recouvrement est calculé EXACTEMENT (une rafale de 22,5 min remplit
    quatre pas de 5 min et la moitié du cinquième) : l'énergie versée vaut
    toujours ``puissance × durée``, jamais un arrondi de grille. Le pas de
    5 minutes est la résolution d'ÉCHANTILLONNAGE, pas une contrainte de
    calage — sinon la conservation d'énergie dépendrait de la grille.
    """
    for index in range(len(parts)):
        borne_basse = index * pas_minutes
        borne_haute = borne_basse + pas_minutes
        chevauchement = min(fin_min, borne_haute) - max(debut_min, borne_basse)
        if chevauchement > 0:
            parts[index] += puissance_kw * chevauchement / 60.0


def pas_fins_du_jour(conso_24h, prod_24h, couches_horaires):
    """Chronologie FINE d'un jour type, ou ``(None, {})`` sans impulsion.

    RÉSOLUTION FINE SEULEMENT LÀ OÙ ELLE SERT : seules les heures qui portent
    une impulsion sont sous-découpées en pas de 5 minutes ; les autres restent
    UN pas d'une heure. Sous-découper les vingt-quatre heures coûterait douze
    fois plus pour un résultat identique — l'heure sans appareil déclaré est
    déjà plate par construction.

    Dans une heure porteuse :

    * les rafales sont posées à la puissance DÉCLARÉE de leur équipement ;
    * le RÉSIDUEL de l'heure (tout ce qui n'appartient pas aux couches
      concentrées : éclairage, veilles, frigo, et la part non concentrée) est
      étalé PLAT sur les soixante minutes. C'est le socle sur lequel la rafale
      s'ajoute — un appareil démarre PAR-DESSUS le reste du logement, il ne le
      remplace pas ;
    * la PRODUCTION est PLATE dans l'heure. Le soleil varie LENTEMENT à
      l'échelle de cinq minutes (la course du soleil, pas un interrupteur) :
      lui inventer une sous-structure serait ajouter du bruit non mesuré, alors
      que l'erreur corrigée ici vient de la CHARGE, qui commute.

    Deux couches qui tombent sur la même heure (piscine 10h-18h et clim
    13h-21h se recouvrent) posent chacune SON cycle, indépendamment : leur
    superposition est une CONSÉQUENCE arithmétique, jamais une hypothèse de
    simultanéité qu'on aurait décrétée.

    Chaque pas porte ``plafond_decharge_kw`` = le déficit HORAIRE de son heure
    (voir :func:`simuler_batterie_pas_fins`).

    Renvoie ``(pas, meta)``.
    """
    rafales_par_heure = {}
    couches_utilisees = set()
    for cle, info in (couches_horaires or {}).items():
        profil = PROFILS_RAFALE.get(cle, PROFIL_RAFALE_DEFAUT)
        if not profil.get('actif', True):
            continue
        puissance = _num((info or {}).get('kw'))
        if puissance <= 0:
            continue
        for heure, energie in enumerate((info or {}).get('heures_kwh') or ()):
            rafale = rafales_de_l_heure(energie, puissance, profil=profil)
            if rafale is None:
                continue
            rafales_par_heure.setdefault(heure, []).append(rafale)
            couches_utilisees.add(cle)

    if not rafales_par_heure:
        return None, {}

    pas = []
    for heure in range(24):
        conso_h = max(0.0, _num(conso_24h[heure])) if heure < len(conso_24h) else 0.0
        prod_h = max(0.0, _num(prod_24h[heure])) if heure < len(prod_24h) else 0.0
        plafond_decharge = max(0.0, conso_h - prod_h)
        rafales = rafales_par_heure.get(heure)
        if not rafales:
            pas.append({'heure': heure, 'duree_h': 1.0,
                        'conso_kwh': conso_h, 'prod_kwh': prod_h,
                        'plafond_decharge_kw': plafond_decharge})
            continue

        energie_rafales = sum(r['energie_rafales_kwh'] for r in rafales)
        # Le résiduel ne peut pas être négatif : les couches concentrées sont
        # une PART de l'heure servie (elles y ont été posées puis renormalisées
        # avec elle). La borne est une ceinture, pas une correction.
        residuel = max(0.0, conso_h - energie_rafales)
        parts = [residuel / SOUS_PAS_PAR_HEURE] * SOUS_PAS_PAR_HEURE
        for rafale in rafales:
            for debut, fin in rafale['fenetres']:
                _repartir_rafale(parts, debut, fin, rafale['puissance_kw'])

        prod_pas = prod_h / SOUS_PAS_PAR_HEURE
        duree_pas = 1.0 / SOUS_PAS_PAR_HEURE
        for part in parts:
            pas.append({'heure': heure, 'duree_h': duree_pas,
                        'conso_kwh': part, 'prod_kwh': prod_pas,
                        'plafond_decharge_kw': plafond_decharge})

    meta = {
        'heures_impulsion': sorted(rafales_par_heure),
        'couches': sorted(couches_utilisees),
        'nb_rafales': sum(r['nb_rafales'] for liste in rafales_par_heure.values()
                          for r in liste),
    }
    return pas, meta


def recouvrement_pas_fins(pas):
    """Autoconsommation DIRECTE sur la chronologie fine (kWh/jour).

    Même intégrale que ``solar_design.hourly_self_consumption``, à un pas plus
    fin : ``Σ min(consommation, production)``. Elle est TOUJOURS inférieure ou
    égale à la version horaire — c'est exactement le biais de lissage que cette
    couche corrige, et un test l'épingle dans ce sens.
    """
    return sum(min(_num(p['conso_kwh']), _num(p['prod_kwh'])) for p in pas)


def simuler_batterie_pas_fins(pas, capacite_kwh_utile, *,
                              puissance_decharge_kw=None,
                              rendement=BATTERY_ROUNDTRIP):
    """:func:`simuler_batterie_jour` sur la chronologie FINE, décharge BORNÉE.

    Même modèle en RÉGIME ÉTABLI (point fixe sur l'état de charge, le reliquat
    du soir sert l'avant-aube), même rendement aller-retour — une seule
    différence : la puissance de décharge est BORNÉE, parce qu'à cinq minutes
    la question « la batterie suit-elle la pointe ? » a enfin un sens.

    LA BORNE, ET POURQUOI ELLE EST CELLE-LÀ :

    * ``puissance_decharge_kw`` fourni ⇒ c'est LUI. Il ne vient que d'une
      donnée PUBLIÉE sur la fiche batterie (voir
      :func:`puissance_batterie_du_devis`) ;
    * absent ⇒ RÈGLE CONSERVATRICE du fondateur (« si aucune puissance publiée
      sur la fiche... elle ne sert pas le pic et le pic tire du réseau ») :
      chaque pas est borné au ``plafond_decharge_kw`` de son heure, c'est-à-dire
      au débit que le modèle HORAIRE prouvait déjà. La batterie continue donc de
      faire exactement ce qu'elle faisait, et le DÉPASSEMENT créé par
      l'impulsion part au réseau. Aucune puissance n'est supposée : on refuse
      simplement de créditer la batterie d'une performance que rien ne prouve.

    Cette borne est NON CONTRAIGNANTE sur une heure sans impulsion (un pas
    d'une heure, plafond = déficit de l'heure) : sur un jour sans impulsion,
    cette fonction rend donc EXACTEMENT ce que rend :func:`simuler_batterie_jour`
    — un test l'épingle.
    """
    capacite = _num(capacite_kwh_utile)
    if capacite <= 0 or not pas:
        return {'restitue_kwh': 0.0, 'charge_kwh': 0.0,
                'capacite_utilisee_kwh': 0.0}

    rendement = _num(rendement, BATTERY_ROUNDTRIP)
    if rendement <= 0:
        rendement = BATTERY_ROUNDTRIP

    borne_fiche = _num(puissance_decharge_kw)

    def _cycle(soc_depart):
        soc = max(0.0, min(_num(soc_depart), capacite))
        pic_soc = soc
        charge_total = 0.0
        restitue_total = 0.0
        for etape in pas:
            conso = max(0.0, _num(etape['conso_kwh']))
            prod = max(0.0, _num(etape['prod_kwh']))
            if prod > conso:
                charge = min(prod - conso, capacite - soc)
                if charge > 0:
                    soc += charge
                    charge_total += charge
                    pic_soc = max(pic_soc, soc)
            elif conso > prod:
                besoin = conso - prod
                if borne_fiche > 0:
                    plafond_kw = borne_fiche
                else:
                    plafond_kw = _num(etape.get('plafond_decharge_kw'))
                plafond_kwh = plafond_kw * _num(etape['duree_h'])
                disponible = soc * rendement
                restitue = min(besoin, disponible, plafond_kwh)
                if restitue > 0:
                    soc -= restitue / rendement
                    restitue_total += restitue
        return charge_total, restitue_total, pic_soc, soc

    soc_depart = 0.0
    charge_total = restitue_total = pic_soc = 0.0
    for _ in range(8):
        charge_total, restitue_total, pic_soc, soc_fin = _cycle(soc_depart)
        if abs(soc_fin - soc_depart) <= 1e-6:
            break
        soc_depart = soc_fin

    restitue_total = min(restitue_total, rendement * charge_total)

    return {
        'restitue_kwh': restitue_total,
        'charge_kwh': charge_total,
        'capacite_utilisee_kwh': pic_soc,
    }


# ════════════════════════════════════════════════════════════════════════════
# 4. LE MOTEUR
# ════════════════════════════════════════════════════════════════════════════

def jours_types_annee(*, kwc, conso_kwh_mensuelles, ville=None, lat=None,
                      lon=None, occupation=None, equipements=None):
    """Les DOUZE JOURS TYPES d'une installation : consommation et production 24 h.

    SOURCE UNIQUE des courbes horaires du moteur. :func:`calculer_etude_horaire`
    (l'étude complète) et :func:`balayer_stockage_horaire` (le balayage du
    stockage, DIM2) lisent le MÊME jour type : deux constructions parallèles
    finiraient immanquablement par diverger d'un derate, d'une silhouette ou
    d'un nombre de jours — et les deux moitiés du tableau ne parleraient plus du
    même client.

    Renvoie ``(jours, avertissements, sources)``. ``jours`` vaut ``None`` dès
    qu'un ancrage manque (puissance nulle, série de consommation absente,
    localisation non résolue par PVGIS) — règle Z2 : on omet, on n'approxime
    pas. Un mois dont la saison n'a pas de forme PVGIS est OMIS de la liste et
    consigné dans ``avertissements`` : l'appelant décide (les deux appelants
    exigent les douze).
    """
    puissance = _num(kwc)
    if puissance <= 0:
        return None, [], {}

    if not conso_kwh_mensuelles or len(conso_kwh_mensuelles) != 12:
        return None, [], {}
    conso_mois = [max(0.0, _num(v)) for v in conso_kwh_mensuelles]
    if not any(v > 0 for v in conso_mois):
        return None, [], {}

    formes, source_prod = _formes_production_par_saison(
        ville=ville, lat=lat, lon=lon)
    if not formes:
        return None, [], {}

    mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
    if not mensuel:
        return None, [], {}
    productibles, source_productible = mensuel

    couches = equipements or {}
    avertissements = []
    jours_types = []

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
        # PERTES SYSTÈME — ordre fondateur (18/08) : 20 % AU TOTAL. Les
        # productibles PVGIS sont demandés à ``loss=14``
        # (``pvgis_profils.PVGIS_LOSS_PCT``), donc 14 % sont DÉJÀ dedans : on
        # n'applique que le COMPLÉMENT, ``PRODUCTION_DERATE`` ≈ 0,9302 — la
        # MÊME constante que ``pricing`` et ``builder``. Sans elle, ce moteur
        # annoncerait ~7,5 % de production (et donc d'économies) de plus que
        # tout le reste de la chaîne, sur la même installation.
        prod_mois_kwh = _num(productibles[index]) * puissance * PRODUCTION_DERATE
        prod_jour_kwh = prod_mois_kwh / jours if jours else 0.0
        prod_24h = [part * prod_jour_kwh for part in forme_prod]

        # ── Consommation du JOUR MOYEN de ce mois (silhouette + équipements) ──
        conso_mois_kwh = conso_mois[index]
        conso_jour_kwh = conso_mois_kwh / jours if jours else 0.0
        conso_24h, couches_horaires = forme_consommation_detaillee(
            conso_jour_kwh, occupation, saison=saison, equipements=couches)

        # L-GLITCH — la chronologie FINE du même jour type, posée ICI et nulle
        # part ailleurs : le balayage du stockage (DIM2) et l'étude complète
        # lisent la MÊME liste de pas. Deux constructions parallèles finiraient
        # par diverger d'une rafale, et les deux moitiés du tableau ne
        # parleraient plus du même client.
        pas_fins, impulsions = pas_fins_du_jour(
            conso_24h, prod_24h, couches_horaires)

        jours_types.append({
            'mois': numero,
            'saison': saison,
            'jours': jours,
            'conso_mois_kwh': conso_mois_kwh,
            'conso_jour_kwh': conso_jour_kwh,
            'prod_mois_kwh': prod_mois_kwh,
            'prod_jour_kwh': prod_jour_kwh,
            'conso_24h': conso_24h,
            'prod_24h': prod_24h,
            'couches_horaires': couches_horaires,
            'pas_fins': pas_fins,
            'impulsions': impulsions,
        })

    return jours_types, avertissements, {
        'production': source_prod,
        'productible': source_productible,
    }


def _bloc_vide():
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


def _glitch_vide():
    """Compteurs L-GLITCH neutres — cumulés à PART de l'agrégat historique.

    Ils vivent dans leur propre dictionnaire, jamais dans :func:`_bloc_vide`,
    pour une raison de contrat : sans équipement déclaré, la sortie du moteur
    doit rester BYTE-IDENTIQUE à celle d'avant cette couche (épinglé par test).
    Des clés à zéro glissées dans l'agrégat historique la casseraient pour tous
    les devis du parc, y compris ceux que rien ne concerne.
    """
    return {
        'part_glitch_kwh': 0.0,
        'part_glitch_batterie_kwh': 0.0,
        'part_glitch_reseau_kwh': 0.0,
        'part_glitch_sans_mad': 0.0,
        'part_glitch_avec_mad': 0.0,
        'heures_impulsion': 0.0,
    }


def _finaliser_glitch(glitch):
    """Arrondis d'affichage des compteurs L-GLITCH (heures en entier)."""
    sortie = {cle: round(val, 2) for cle, val in glitch.items()}
    sortie['heures_impulsion'] = int(round(glitch['heures_impulsion']))
    return sortie


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
                           batterie_puissance_decharge_kw=None,
                           batterie_puissance_charge_kw=None,
                           tranches=None, charges_fixes_mad=None,
                           tppan=True, millesime=bareme.MILLESIME_COURANT,
                           source_conso=None, detail_conso=None):
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
    batterie_puissance_decharge_kw : puissance de décharge PUBLIÉE sur la fiche
        (kW). Elle ne sert QUE la résolution fine (L-GLITCH) : c'est elle qui
        décide si la batterie suit une pointe de trente minutes. ``None`` ⇒
        règle conservatrice (la pointe tire du réseau) — jamais une puissance
        supposée. Voir :func:`simuler_batterie_pas_fins`.
    batterie_puissance_charge_kw : puissance de charge publiée (kW), servie
        telle quelle en sortie à titre INFORMATIF. Elle ne borne rien : c'est
        une grandeur de charge, et s'en servir comme borne de décharge serait
        une équivalence inventée.
    tranches / charges_fixes_mad / tppan / millesime : passés tels quels au
        barème. ``charges_fixes_mad`` remplace en bloc les deux lignes fixes
        (location du compteur + entretien du branchement) quand la société a
        relevé les siennes ; ``None`` ⇒ les valeurs SOURCÉES des factures.

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

    jours_types, avertissements, sources = jours_types_annee(
        kwc=puissance, conso_kwh_mensuelles=conso_kwh_mensuelles,
        ville=ville, lat=lat, lon=lon,
        occupation=occupation, equipements=equipements)
    if jours_types is None:
        return None
    source_prod = sources.get('production')
    source_productible = sources.get('productible')

    capacite = _num(batterie_kwh_utile)
    couches = equipements or {}
    decharge_kw = _num(batterie_puissance_decharge_kw)

    mois_sortie = []
    saisons_cumul = {saison: _bloc_vide() for saison in SAISONS}
    annuel_cumul = _bloc_vide()
    glitch_mois = []
    glitch_saisons = {saison: _glitch_vide() for saison in SAISONS}
    glitch_annuel = _glitch_vide()
    glitch_couches = set()
    glitch_rafales = 0

    for jour_type in jours_types:
        numero = jour_type['mois']
        saison = jour_type['saison']
        jours = jour_type['jours']
        prod_mois_kwh = jour_type['prod_mois_kwh']
        prod_jour_kwh = jour_type['prod_jour_kwh']
        prod_24h = jour_type['prod_24h']
        conso_mois_kwh = jour_type['conso_mois_kwh']
        conso_jour_kwh = jour_type['conso_jour_kwh']
        conso_24h = jour_type['conso_24h']
        pas_fins = jour_type.get('pas_fins')

        # ── Recouvrement horaire — LE moteur existant, courbes RÉELLES ──
        recouvrement = hourly_self_consumption(
            load_curve=conso_24h, production_curve=prod_24h)
        auto_jour_horaire = recouvrement['self_consumed_kwh']

        # ── Variante batterie : le surplus du jour sert le déficit du soir ──
        batterie_horaire = simuler_batterie_jour(conso_24h, prod_24h, capacite)
        auto_avec_horaire = min(
            auto_jour_horaire + batterie_horaire['restitue_kwh'],
            conso_jour_kwh, prod_jour_kwh)

        # ── L-GLITCH : le MÊME jour, à cinq minutes, quand un appareil déclaré
        # y pose des impulsions. Sans équipement déclaré, ``pas_fins`` est
        # ``None`` et l'on reste EXACTEMENT sur le chemin horaire ci-dessus.
        if pas_fins:
            auto_jour_sans = recouvrement_pas_fins(pas_fins)
            batterie = simuler_batterie_pas_fins(
                pas_fins, capacite,
                puissance_decharge_kw=decharge_kw or None)
        else:
            auto_jour_sans = auto_jour_horaire
            batterie = batterie_horaire

        auto_jour_avec = auto_jour_sans + batterie['restitue_kwh']
        # Garde d'honnêteté : on n'autoconsomme jamais plus que ce que le
        # client consomme, ni plus que ce que le champ produit.
        auto_jour_avec = min(auto_jour_avec, conso_jour_kwh, prod_jour_kwh)

        auto_mois_sans = auto_jour_sans * jours
        auto_mois_avec = auto_jour_avec * jours

        # ── L'ARGENT : deux factures, au MOIS (l'unité du barème) ──
        # ``jours`` est le nombre RÉEL de jours du mois : les bornes du barème
        # TPPAN se proratisent dessus (vérifié sur les factures du fondateur).
        _bareme_kwargs = {
            'jours': jours, 'millesime': millesime, 'tranches': tranches,
            'charges_fixes_mad': charges_fixes_mad, 'tppan': tppan,
        }
        eco_sans = bareme.economie_deux_factures_mad(
            conso_mois_kwh, max(0.0, conso_mois_kwh - auto_mois_sans),
            **_bareme_kwargs)
        eco_avec = bareme.economie_deux_factures_mad(
            conso_mois_kwh, max(0.0, conso_mois_kwh - auto_mois_avec),
            **_bareme_kwargs)

        # ── CE QUE LES IMPULSIONS ONT CHANGÉ, chiffré et nommé ──
        glitch = _glitch_vide()
        if pas_fins:
            impulsions = jour_type.get('impulsions') or {}
            glitch_couches.update(impulsions.get('couches') or ())
            glitch_rafales += int(impulsions.get('nb_rafales') or 0)
            glitch['heures_impulsion'] = float(
                len(impulsions.get('heures_impulsion') or ()))
            perdu_direct = max(0.0, auto_jour_horaire - auto_jour_sans) * jours
            perdu_avec = max(0.0, auto_avec_horaire - auto_jour_avec) * jours
            eco_sans_horaire = bareme.economie_deux_factures_mad(
                conso_mois_kwh,
                max(0.0, conso_mois_kwh - auto_jour_horaire * jours),
                **_bareme_kwargs)
            eco_avec_horaire = bareme.economie_deux_factures_mad(
                conso_mois_kwh,
                max(0.0, conso_mois_kwh - auto_avec_horaire * jours),
                **_bareme_kwargs)
            glitch['part_glitch_kwh'] = perdu_direct
            glitch['part_glitch_reseau_kwh'] = perdu_avec
            # Ce que la batterie REPREND de la pointe : la différence entre ce
            # que l'impulsion a retiré au direct et ce qui finit vraiment au
            # réseau. Sans puissance de décharge publiée, la règle
            # conservatrice l'annule — c'est DIT, pas caché.
            glitch['part_glitch_batterie_kwh'] = max(
                0.0, perdu_direct - perdu_avec)
            glitch['part_glitch_sans_mad'] = (
                eco_sans_horaire['economie_mad'] - eco_sans['economie_mad'])
            glitch['part_glitch_avec_mad'] = (
                eco_avec_horaire['economie_mad'] - eco_avec['economie_mad'])
        glitch_mois.append(glitch)
        _cumuler(glitch_saisons[saison], glitch)
        _cumuler(glitch_annuel, glitch)

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

    # ANNÉE COMPLÈTE OU RIEN. Un mois manquant (saison sans forme PVGIS)
    # donnerait un « annuel » qui n'est pas une année : des consommateurs le
    # liraient comme un total sur douze mois et sous-estimeraient tout. On OMET
    # plutôt que de servir un agrégat trompeur (même règle que Z2).
    if len(mois_sortie) != 12:
        return None

    if annuel_cumul['production_kwh'] <= 0:
        avertissements.append(
            'production annuelle nulle — vérifier la puissance et la '
            'localisation du chantier')

    resultat = {
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

    # ── L-GLITCH : des champs ADDITIFS, et SEULEMENT quand ils ont un sens ──
    # AUCUN équipement concentrable déclaré ⇒ pas une seule clé de plus, pas un
    # centième de différence : la sortie est celle d'avant cette couche, pour
    # tout le parc existant. C'est aussi pourquoi ``ETUDE_HORAIRE_VERSION`` ne
    # bouge PAS — la forme du bloc historique est inchangée ; le bloc ``glitch``
    # porte son propre numéro de forme (:data:`GLITCH_VERSION`).
    if glitch_annuel['heures_impulsion'] > 0:
        for index, sortie_mois in enumerate(mois_sortie):
            sortie_mois.update(_finaliser_glitch(glitch_mois[index]))
        for saison, bloc_saison in resultat['saisons'].items():
            bloc_saison.update(_finaliser_glitch(glitch_saisons[saison]))
        resultat['annuel'].update(_finaliser_glitch(glitch_annuel))
        resultat['glitch'] = {
            'version': GLITCH_VERSION,
            'methode': 'impulsions_derivees',
            'couches': sorted(glitch_couches),
            'nb_rafales_jour_type': glitch_rafales,
            'pas_minutes': PAS_FIN_MINUTES,
            'plafond_rafale_minutes': RAFALE_PLAFOND_MINUTES,
            'plafond_source': 'fondateur_2026-08-24',
            'position_rafale_fenetre': RAFALE_POSITION_INTERIM,
            'position_source': 'interim_a_calibrer_deye_5min',
            'production_dans_l_heure': 'plate',
            'batterie_puissance_decharge_kw': (
                round(decharge_kw, 2) if decharge_kw > 0 else None),
            'batterie_puissance_decharge_source': (
                'fiche_technique' if decharge_kw > 0
                else 'aucune_publiee_regle_conservatrice'),
            'batterie_puissance_charge_kw': (
                round(_num(batterie_puissance_charge_kw), 2)
                if _num(batterie_puissance_charge_kw) > 0 else None),
            'note': (
                "Les appareils déclarés à l'appel (pompe de piscine, "
                "climatisation) sont restitués en impulsions à leur puissance "
                "réelle plutôt qu'étalés sur l'heure : mêmes kWh, pointes "
                "visibles. Sans puissance de décharge publiée sur la fiche "
                "batterie, la pointe n'est pas servie par le stockage."),
        }

    return resultat


# ════════════════════════════════════════════════════════════════════════════
# 4 bis. DIM2 — LE STOCKAGE COMME DEUXIÈME DIMENSION DU BALAYAGE
# ════════════════════════════════════════════════════════════════════════════
# ORDRE FONDATEUR (24/08/2026) : « peut-être rajouter des batteries », puis, le
# même jour, la règle qui la borne — « le stockage avec des batteries toujours
# pleines..... pas rajouter du stockage pour ne pas le charger ».
#
# Jusqu'ici la batterie était une CONSÉQUENCE des kWc (``composition_
# residentielle`` vise ``max(5, arrondi(kwp/5) × 5)`` kWh). Un client qui paie
# 3 500 DH/mois plafonnait donc à 15 kWh de stockage et ne voyait JAMAIS la
# configuration qui ferait retomber son résiduel sous la marche des 500 kWh/mois
# — là où tout le mois se re-tarife de 1,62 à 1,38.
#
# Cette fonction rend le stockage MESURABLE : pour UNE taille de champ, elle
# évalue plusieurs capacités d'un seul parcours des douze jours types, et
# expose de quoi refuser un palier qui ne se remplirait pas.


def balayer_stockage_horaire(*, kwc, conso_kwh_mensuelles, capacites_kwh,
                             ville=None, lat=None, lon=None,
                             occupation=None, equipements=None,
                             batterie_puissance_decharge_kw=None,
                             tranches=None, charges_fixes_mad=None,
                             tppan=True, millesime=bareme.MILLESIME_COURANT):
    """DIM2 — plusieurs capacités de stockage évaluées sur UNE taille de champ.

    UN SEUL parcours des douze jours types (:func:`jours_types_annee`) sert
    TOUTES les capacités : évaluer douze paliers coûte donc un douzième de
    boucle mensuelle, pas douze études complètes.

    LES DEUX PLAFONDS PHYSIQUES, tous deux MESURÉS sur ce client-ci — aucun des
    deux n'est un chiffre choisi :

    * ``plafond_remplissage_kwh`` — RÈGLE FONDATEUR : la batterie doit se
      remplir TOUS LES JOURS. C'est donc le SURPLUS QUOTIDIEN (production moins
      autoconsommation directe) du MOIS LE PLUS FAIBLE de l'année : au-delà,
      il existe un mois — décembre ou janvier — où le champ ne produit pas
      assez pour charger la banque, et l'on vendrait des kWh de batterie qui
      dorment. Conséquence VOULUE : stockage et champ montent ENSEMBLE.
    * ``plafond_deficit_kwh`` — le déficit du jour type le plus gourmand divisé
      par le rendement aller-retour : la restitution vaut au plus
      ``capacité × rendement``, donc au-delà, un kWh de plus ne peut RIEN
      restituer de plus, quelle que soit la production.

    ``plafond_stockage_kwh`` est le plus contraignant des deux, et
    ``plafond_motif`` DIT lequel — un refus muet serait un refus incompris.

    ``capacites_kwh`` est évalué TEL QUEL, y compris au-dessus des plafonds :
    c'est ce qui permet à l'appelant d'AFFICHER un palier refusé avec son taux
    de remplissage du pire mois (« 20 kWh refusé : rempli 62 % en janvier »).
    L'admissibilité est une décision de l'appelant, pas un silence d'ici.

    Renvoie ``None`` quand l'année n'est pas complète (même règle que
    :func:`calculer_etude_horaire` : une année tronquée n'est pas une année).
    """
    jours_types, _avertissements, _sources = jours_types_annee(
        kwc=kwc, conso_kwh_mensuelles=conso_kwh_mensuelles,
        ville=ville, lat=lat, lon=lon,
        occupation=occupation, equipements=equipements)
    if not jours_types or len(jours_types) != 12:
        return None

    capacites = sorted({round(_num(c), 3) for c in (capacites_kwh or ())
                        if _num(c) > 0})
    decharge_kw = _num(batterie_puissance_decharge_kw)

    production_kwh = 0.0
    consommation_kwh = 0.0
    autoconsomme_direct_kwh = 0.0
    surplus_min = None
    surplus_min_mois = None
    deficit_max = 0.0
    deficit_max_mois = None
    cumuls = {c: {'economie_mad': 0.0, 'autoconsomme_kwh': 0.0,
                  'import_kwh': 0.0, 'remplissage_somme': 0.0,
                  'remplissage_min': None} for c in capacites}

    for jour_type in jours_types:
        conso_24h = jour_type['conso_24h']
        prod_24h = jour_type['prod_24h']
        jours = jour_type['jours']
        conso_mois_kwh = jour_type['conso_mois_kwh']
        conso_jour_kwh = jour_type['conso_jour_kwh']
        prod_jour_kwh = jour_type['prod_jour_kwh']
        # L-GLITCH — LA SOURCE EST UNIQUE. Le balayage lit la MÊME chronologie
        # fine que l'étude complète (posée une fois par ``jours_types_annee``) :
        # les paliers de stockage sont donc évalués contre les MÊMES impulsions
        # que celles qui chiffrent l'économie. Un balayage resté à l'heure
        # pendant que l'étude descend à cinq minutes recommanderait une capacité
        # calibrée sur un client qui n'existe pas.
        pas_fins = jour_type.get('pas_fins')

        production_kwh += jour_type['prod_mois_kwh']
        consommation_kwh += conso_mois_kwh

        if pas_fins:
            auto_direct_jour = recouvrement_pas_fins(pas_fins)
        else:
            recouvrement = hourly_self_consumption(
                load_curve=conso_24h, production_curve=prod_24h)
            auto_direct_jour = recouvrement['self_consumed_kwh']
        autoconsomme_direct_kwh += auto_direct_jour * jours

        # LE SURPLUS DU JOUR TYPE : l'énergie réellement disponible pour
        # charger — c'est ELLE que la règle « batteries toujours pleines »
        # borne, pas la production brute.
        surplus_jour = max(0.0, prod_jour_kwh - auto_direct_jour)
        if surplus_min is None or surplus_jour < surplus_min:
            surplus_min = surplus_jour
            surplus_min_mois = jour_type['mois']

        if pas_fins:
            deficit_jour = sum(
                max(0.0, _num(p['conso_kwh']) - _num(p['prod_kwh']))
                for p in pas_fins)
        else:
            deficit_jour = sum(
                max(0.0, _num(conso_24h[h]) - _num(prod_24h[h]))
                for h in range(min(len(conso_24h), len(prod_24h))))
        if deficit_jour > deficit_max:
            deficit_max = deficit_jour
            deficit_max_mois = jour_type['mois']

        bareme_kwargs = {
            'jours': jours, 'millesime': millesime, 'tranches': tranches,
            'charges_fixes_mad': charges_fixes_mad, 'tppan': tppan,
        }
        for capacite in capacites:
            if pas_fins:
                batterie = simuler_batterie_pas_fins(
                    pas_fins, capacite,
                    puissance_decharge_kw=decharge_kw or None)
            else:
                batterie = simuler_batterie_jour(conso_24h, prod_24h, capacite)
            auto_jour = min(auto_direct_jour + batterie['restitue_kwh'],
                            conso_jour_kwh, prod_jour_kwh)
            auto_mois = auto_jour * jours
            eco = bareme.economie_deux_factures_mad(
                conso_mois_kwh, max(0.0, conso_mois_kwh - auto_mois),
                **bareme_kwargs)
            cumul = cumuls[capacite]
            cumul['economie_mad'] += eco['economie_mad']
            cumul['autoconsomme_kwh'] += auto_mois
            cumul['import_kwh'] += max(0.0, conso_mois_kwh - auto_mois)
            ratio = batterie['charge_kwh'] / capacite if capacite > 0 else 0.0
            cumul['remplissage_somme'] += ratio
            pire = cumul['remplissage_min']
            if pire is None or ratio < pire['ratio']:
                cumul['remplissage_min'] = {
                    'mois': jour_type['mois'],
                    'ratio': ratio,
                    'charge_jour_kwh': batterie['charge_kwh'],
                    'surplus_jour_kwh': surplus_jour,
                }

    plafond_remplissage = max(0.0, surplus_min or 0.0)
    plafond_deficit = (deficit_max / BATTERY_ROUNDTRIP
                       if BATTERY_ROUNDTRIP > 0 else deficit_max)
    if plafond_remplissage <= plafond_deficit:
        plafond, motif = plafond_remplissage, 'remplissage_quotidien'
    else:
        plafond, motif = plafond_deficit, 'deficit_nocturne'
    # LE VERDICT SE PRONONCE SUR LES CHIFFRES PUBLIÉS. Comparer les valeurs
    # brutes ferait refuser une banque de 35,00 kWh devant un plafond de
    # 34,9962 kWh — soit 4 Wh d'écart — tout en AFFICHANT « 35,00 > 35,00 » :
    # un refus que personne ne peut comprendre en lisant le tableau. On ne
    # prétend pas connaître un surplus quotidien au milliwattheure.
    plafond_publie = round(plafond, 2)
    plafond_remplissage_publie = round(plafond_remplissage, 2)

    paliers = []
    for capacite in capacites:
        cumul = cumuls[capacite]
        pire = cumul['remplissage_min'] or {}
        paliers.append({
            'capacite_kwh': round(capacite, 2),
            'economie_mad': round(cumul['economie_mad'], 2),
            'autoconsomme_kwh': round(cumul['autoconsomme_kwh'], 2),
            'import_kwh': round(cumul['import_kwh'], 2),
            'residuel_kwh_mois': round(cumul['import_kwh'] / 12.0, 2),
            'taux_autoconso': round(
                _taux(cumul['autoconsomme_kwh'], production_kwh), 4),
            'couverture': round(
                _taux(cumul['autoconsomme_kwh'], consommation_kwh), 4),
            'remplissage_moyen': round(cumul['remplissage_somme'] / 12.0, 4),
            'remplissage_pire_mois': {
                'mois': pire.get('mois'),
                'ratio': round(_num(pire.get('ratio')), 4),
                'charge_jour_kwh': round(_num(pire.get('charge_jour_kwh')), 2),
                'surplus_jour_kwh': round(
                    _num(pire.get('surplus_jour_kwh')), 2),
            },
            'se_remplit_tous_les_jours': bool(
                round(capacite, 2) <= plafond_remplissage_publie),
            'sous_plafond_physique': bool(
                round(capacite, 2) <= plafond_publie),
        })

    import_direct = max(0.0, consommation_kwh - autoconsomme_direct_kwh)
    return {
        'kwc': round(_num(kwc), 3),
        'production_annuelle_kwh': round(production_kwh, 2),
        'consommation_annuelle_kwh': round(consommation_kwh, 2),
        'residuel_sans_kwh_mois': round(import_direct / 12.0, 2),
        'surplus_jour_min_kwh': round(plafond_remplissage, 2),
        'surplus_jour_min_mois': surplus_min_mois,
        'deficit_jour_max_kwh': round(deficit_max, 2),
        'deficit_jour_max_mois': deficit_max_mois,
        'plafond_remplissage_kwh': round(plafond_remplissage, 2),
        'plafond_deficit_kwh': round(plafond_deficit, 2),
        'plafond_stockage_kwh': round(plafond, 2),
        'plafond_motif': motif,
        'rendement_batterie': BATTERY_ROUNDTRIP,
        'paliers': paliers,
    }


# ════════════════════════════════════════════════════════════════════════════
# 5. ENTRÉES APPLICATIVES — depuis un devis, ou depuis un profil brut
# ════════════════════════════════════════════════════════════════════════════

def profil_depuis_factures(*, facture_hiver_mad=None, facture_ete_mad=None,
                           ete_differente=False, factures_mensuelles_mad=None,
                           conso_kwh_mensuelles=None, tranches=None,
                           charges_fixes_mad=None, tppan=True):
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
                charges_fixes_mad=charges_fixes_mad, tppan=tppan)
            if kwh:
                return kwh, 'factures_mensuelles_reelles', detail

    serie_mad = serie_mad_mensuelle(
        facture_hiver_mad, facture_ete_mad, ete_differente)
    if serie_mad:
        kwh, detail = serie_kwh_depuis_mad(
            serie_mad, tranches=tranches,
            charges_fixes_mad=charges_fixes_mad, tppan=tppan)
        if kwh:
            source = ('facture_hiver_ete' if (ete_differente
                                              and _num(facture_ete_mad) > 0)
                      else 'facture_hiver')
            return kwh, source, detail

    return None, 'absente', {}


def capacite_batterie_du_devis(devis):
    """Capacité UTILE totale (kWh) réellement chiffrée sur un devis, ou ``None``.

    Somme les lignes classées ``batterie`` par ``services.classer_produit`` (le
    MÊME classifieur que la composition — jamais une seconde règle de
    reconnaissance) en lisant la capacité utile de chaque fiche
    (``dimensionnement.capacite_utile_batterie``).

    ``None`` (et non 0,0) quand le devis ne porte aucune batterie : le moteur
    distingue ainsi « pas de stockage » de « stockage de capacité nulle ».
    """
    try:
        from apps.ventes.dimensionnement import capacite_utile_batterie
        from apps.ventes.services import classer_produit
        total = 0.0
        for ligne in devis.lignes.all():
            designation = getattr(ligne, 'designation', '') or ''
            if classer_produit(designation) != 'batterie':
                continue
            kwh = capacite_utile_batterie(
                getattr(ligne, 'produit', None), designation)
            if kwh:
                total += float(kwh) * float(getattr(ligne, 'quantite', 0) or 0)
        return total if total > 0 else None
    except Exception:  # noqa: BLE001 — lignes illisibles ⇒ pas de stockage
        logger.warning('capacité batterie illisible', exc_info=True)
        return None


def puissance_batterie_du_devis(devis):
    """Puissances PUBLIÉES de la batterie d'un devis — ce que la fiche PROUVE.

    L-GLITCH a besoin de savoir si le stockage peut SUIVRE une pointe de trente
    minutes. Cette fonction ne répond que par des grandeurs réellement fichées
    (``apps.stock.selectors.specs_for_produit``, lecture cross-app par sélecteur,
    jamais ``stock.models``) :

    * ``decharge_kw`` — la puissance de DÉCHARGE. **Aucune fiche du catalogue ne
      la publie aujourd'hui** : le modèle ``FicheTechnique`` porte
      ``bat_max_charge_kw`` (« Puissance de charge maximale »), et rien pour la
      décharge. La clé ``max_decharge_kw`` est lue quand même — le jour où le
      champ existera, ce moteur s'en servira sans une ligne de plus.
    * ``charge_kw`` — la puissance de CHARGE publiée (BAT-DEY-5 : 3,84 kW =
      75 A × 51,2 V, valeur constructeur). Rendue à titre INFORMATIF et servie
      telle quelle dans le bloc ``glitch``.

    POURQUOI LA CHARGE NE SERT PAS DE BORNE DE DÉCHARGE. Ce sont deux grandeurs
    distinctes : un pack peut parfaitement accepter 75 A en charge et en rendre
    100 en décharge, ou l'inverse. Recopier l'une dans l'autre serait inventer
    une équivalence que le constructeur ne publie pas — exactement ce que la
    règle « zéro chiffre inventé » interdit. Sans décharge publiée, le moteur
    applique la règle CONSERVATRICE (la pointe tire du réseau), et le dit.

    Renvoie ``{'decharge_kw': …|None, 'decharge_source': …, 'charge_kw': …|None,
    'charge_source': …}``. Ne lève jamais.
    """
    resultat = {'decharge_kw': None,
                'decharge_source': 'aucune_publiee_regle_conservatrice',
                'charge_kw': None, 'charge_source': None}
    try:
        from apps.stock.selectors import specs_for_produit
        from apps.ventes.services import classer_produit
        decharge = None
        charge = None
        for ligne in devis.lignes.all():
            designation = getattr(ligne, 'designation', '') or ''
            if classer_produit(designation) != 'batterie':
                continue
            produit = getattr(ligne, 'produit', None)
            if produit is None:
                continue
            specs = (specs_for_produit(produit) or {}).get('batterie') or {}
            # LA PLUS PETITE DES FICHES BORNE L'ENSEMBLE : deux packs en
            # parallèle dont l'un plafonne à 3,84 kW ne prouvent pas 7,68 kW —
            # additionner supposerait un câblage et un BMS qu'on ne voit pas.
            for cle, courant in (('max_decharge_kw', decharge),
                                 ('max_charge_kw', charge)):
                valeur = specs.get(cle)
                if not valeur:
                    continue
                valeur = float(valeur)
                if cle == 'max_decharge_kw':
                    decharge = valeur if courant is None else min(courant, valeur)
                else:
                    charge = valeur if courant is None else min(courant, valeur)
        if decharge and decharge > 0:
            resultat['decharge_kw'] = decharge
            resultat['decharge_source'] = 'fiche:max_decharge_kw'
        if charge and charge > 0:
            resultat['charge_kw'] = charge
            resultat['charge_source'] = 'fiche:max_charge_kw'
    except Exception:  # noqa: BLE001 — fiche illisible ⇒ règle conservatrice
        logger.warning('puissances batterie illisibles', exc_info=True)
    return resultat


def _reglages_tarifaires(company):
    """``(tranches, charges_fixes)`` de la société — best-effort, jamais bloquant.

    ``parametres`` est une app FONDATION (exemptée de la frontière cross-app) ;
    l'import reste local au point d'usage, comme partout dans ``apps/ventes``.
    Réglages illisibles ⇒ ``(None, None)`` : le barème applique alors la grille
    du millésime et les charges fixes SOURCÉES des factures du fondateur.

    ``charges_fixes`` (réglage ``redevance_compteur_mad_mois``) REMPLACE en
    bloc les deux lignes fixes quand une société a relevé les siennes — une
    autre zone / un autre calibre de compteur peut légitimement différer.
    """
    if company is None:
        return None, None
    tranches = None
    charges_fixes = None
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
        charges_fixes = float(brut) if brut is not None else None
    except Exception:  # noqa: BLE001 — réglage absent ⇒ défaut sourcé
        charges_fixes = None
    return tranches, charges_fixes


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
    tranches, charges_fixes = _reglages_tarifaires(company)

    etude_params = getattr(devis, 'etude_params', None) or {}
    factures_mensuelles = etude_params.get('factures_mensuelles_reelles')

    bills = lead_bills_for_devis(devis) or {}
    conso, source_conso, detail_conso = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=factures_mensuelles,
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'),
        tranches=tranches, charges_fixes_mad=charges_fixes)
    if not conso:
        return None

    if bills.get('distributeur'):
        detail_conso = {**detail_conso,
                        'distributeur': bills['distributeur']}

    # L'OCCUPATION A BESOIN DU MARCHÉ. ``_occupation`` applique le défaut
    # fondateur ``presence_jour`` UNIQUEMENT quand elle sait que le devis est
    # résidentiel ; sans ``mode_installation`` elle retombe sur
    # ``absence_jour`` (le défaut NON résidentiel) et le devis serait calculé
    # avec la pire silhouette d'autoconsommation — l'inverse de la décision
    # terrain du fondateur. On le lit donc sur le devis quand l'appelant ne le
    # fournit pas, sans jamais écraser ce qu'il fournit.
    contexte = dict(data)
    if not contexte.get('mode_installation'):
        contexte['mode_installation'] = getattr(devis, 'mode_installation', None)
    occupation, occupation_source = occupation_du_devis(devis, contexte)
    equipements = equipements_du_devis(devis)

    # LA BATTERIE VIENT DU DEVIS RÉEL. Sans cela, un devis « deux options »
    # sortirait avec « avec batterie » économisant EXACTEMENT autant que
    # « sans » — donc plus cher pour rien sur la proposition client.
    capacite = batterie_kwh_utile
    if capacite is None:
        capacite = data.get('batterie_kwh_total')
    if capacite is None:
        capacite = capacite_batterie_du_devis(devis)

    # L-GLITCH — les puissances PUBLIÉES de la banque, lues sur les fiches du
    # devis. Elles ne décident rien d'autre que ceci : la batterie suit-elle une
    # pointe de trente minutes ? Sans décharge publiée, non (règle fondateur).
    puissances = puissance_batterie_du_devis(devis)

    resultat = calculer_etude_horaire(
        kwc=puissance, conso_kwh_mensuelles=conso,
        ville=ville, lat=lat, lon=lon,
        occupation=occupation, equipements=equipements,
        batterie_kwh_utile=capacite,
        batterie_puissance_decharge_kw=puissances['decharge_kw'],
        batterie_puissance_charge_kw=puissances['charge_kw'],
        tranches=tranches, charges_fixes_mad=charges_fixes,
        source_conso=source_conso, detail_conso=detail_conso)
    if resultat is not None:
        resultat['occupation_source'] = occupation_source
    return resultat
