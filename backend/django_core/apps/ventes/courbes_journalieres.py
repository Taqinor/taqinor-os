"""Courbes journalières servies à la page proposition (production / conso).

Le graphe « une journée type » de ``/proposition`` dessinait jusqu'ici une
production SYNTHÉTIQUE (cloche calculée côté client) et affichait son sommet en
« kWh » alors que c'est une PUISSANCE (kW). Ce module donne au graphe un
PROPRIÉTAIRE SERVEUR et des chiffres réels :

* la FORME horaire vient de PVGIS (``apps.parametres.pvgis_profils`` : appel
  live au point GPS du chantier, sinon courbe de référence de la ville) ;
* le NIVEAU vient du devis : productible mensuel PVGIS × puissance kWc du devis
  pour la production, factures RÉELLES du lead (série M10 déjà servie) pour la
  consommation ;
* rien n'est servi quand la donnée manque — la clé est ABSENTE et la page garde
  son affichage actuel (décision fondateur Q6 : on omet, on n'approxime pas).

Ce module NE TOUCHE À AUCUN CALCUL D'ARGENT (règle #4) : il lit la sortie du
moteur de devis, il ne la modifie pas.

CJ2b (21/08/2026) — LA FORME DE BASE DE CONSOMMATION DEVIENT SERVEUR. Jusqu'ici
seul le NIVEAU réel (``kwh_jour``) était servi ; la forme 24 h restait une
copie tenue à la main côté page (``dayProfiles.OCCUPANCY_SHAPES``). Chaque
saison de ``consommation`` porte désormais AUSSI ``forme`` — la silhouette
d'occupation SERVEUR (:func:`silhouette_occupation`, section CJ2a plus bas), et
le bloc porte ``consommation_forme_source`` qui nomme l'occupation servie
(``silhouette_occupation:presence_jour`` etc.). C'est la forme DE BASE
UNIQUEMENT : les couches équipements (piscine/clim/VE, voir :func:`_equipements`
ci-dessous) restent composées CÔTÉ PAGE par-dessus cette forme
(``proposalCurve.ts``) — les recomposer ici les compterait deux fois.

L4 (21/08/2026) — ÉQUIPEMENTS DU LEAD (script d'appel commercial : piscine,
véhicule électrique, climatisation, chauffe-eau). Le serveur reste dans le
même rôle : il ne dessine toujours AUCUNE forme de consommation, il sert la
SPÉCIFICATION sourcée de chaque couche (fenêtre d'heures + grandeur réelle),
que la page applique à la silhouette qu'elle a déjà choisie
(``apps/web/src/lib/proposalCurve.ts``). Voir :func:`_equipements` pour la
provenance de chaque nombre — RÈGLE « zéro chiffre inventé » (mémo
``2026-08-21-memo-estimation-consommation.md``, étage 2) : un équipement sans
grandeur réelle saisie NE PRODUIT AUCUNE couche (omission > invention).
"""
from __future__ import annotations

import logging

from apps.parametres.pvgis_profils import (
    SAISONS,
    moyenne_journaliere_saison,
    productible_mensuel,
    profil_production_journalier,
    vers_heure_locale,
)

logger = logging.getLogger(__name__)

# Note d'affichage servie telle quelle à la page : les formes sont livrées en
# heure civile marocaine (UTC+1), sauf pendant le Ramadan où le pays repasse à
# UTC+0 — la courbe réelle est alors décalée d'une heure vers la gauche. Le cas
# Ramadan n'est PAS modélisé (une seule série servie) : il est DIT.
NOTE_HORAIRE = (
    "Heures en heure civile marocaine (UTC+1). Pendant le Ramadan, le Maroc "
    "repasse à UTC+0 : la courbe se décale alors d'une heure plus tôt."
)

# Occupation du logement en journée — vocabulaire servi à la page.
OCCUPATION_PRESENCE = 'presence_jour'
OCCUPATION_ABSENCE = 'absence_jour'
# L4 (extension fondateur, 21/08/2026) — troisième silhouette, jusqu'ici un
# choix VISITEUR côté page uniquement (dayProfiles.OCCUPANCY_SHAPES). Le
# lead.occupation_jour ('partiel') est le premier chemin qui la SERT depuis
# le serveur — la page la reconnaît déjà (``occupancyFromFlag``).
OCCUPATION_PARTIELLE = 'presence_partielle'

# Lead.occupation_jour (present/absent/partiel) → drapeau d'occupation servi.
_OCCUPATION_JOUR_VERS_DRAPEAU = {
    'present': OCCUPATION_PRESENCE,
    'absent': OCCUPATION_ABSENCE,
    'partiel': OCCUPATION_PARTIELLE,
}


def _nombre(valeur):
    """Flottant strictement positif, ou ``None``."""
    try:
        val = float(valeur)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _localisation(devis):
    """(ville, lat, lon) du chantier — via le sélecteur CRM, jamais ses modèles."""
    try:
        from apps.crm.selectors import site_location_for_devis
        loc = site_location_for_devis(devis) or {}
    except Exception:  # noqa: BLE001 — un lead absent/illisible n'arrête rien
        return None, None, None
    return loc.get('site_ville'), loc.get('gps_lat'), loc.get('gps_lng')


def _equipements_lead(devis):
    """Équipements du lead d'un devis — via le sélecteur CRM, jamais ses
    modèles. ``{}`` best-effort quand le lead/sélecteur est indisponible."""
    try:
        from apps.crm.selectors import equipements_pour_devis
        return equipements_pour_devis(devis) or {}
    except Exception:  # noqa: BLE001 — un lead absent/illisible n'arrête rien
        return {}


def _occupation_jour_lead(devis):
    """Présence en journée déclarée au téléphone (``crm.Lead.occupation_jour``),
    ou ``None`` — via le sélecteur CRM, jamais ``crm.models``."""
    try:
        from apps.crm.selectors import occupation_jour_pour_devis
        return occupation_jour_pour_devis(devis)
    except Exception:  # noqa: BLE001 — un lead absent/illisible n'arrête rien
        return None


def _options_reelles(data, batterie_kwh):
    """Variantes batterie que le devis porte VRAIMENT : ``['sans']``, ``['avec']``
    ou ``['sans', 'avec']`` (liste vide quand aucune option n'est valide).

    On lit les drapeaux DÉJÀ calculés par le moteur (``sans_ok``/``avec_ok``/
    ``deux_options``) — la page n'a plus à deviner à partir des totaux.
    """
    sans_ok = bool(data.get('sans_ok'))
    avec_ok = bool(data.get('avec_ok'))
    if bool(data.get('deux_options')) and sans_ok and avec_ok:
        return ['sans', 'avec']
    if avec_ok and not sans_ok:
        return ['avec']
    if sans_ok and not avec_ok:
        return ['sans']
    if sans_ok and avec_ok:
        # Mono-option déclarée alors que les deux paniers restent valides
        # (cas « hybride sans batterie ») : la présence RÉELLE de stockage
        # tranche, jamais le libellé du scénario.
        return ['avec'] if batterie_kwh else ['sans']
    return []


def _occupation(devis, data):
    """(drapeau, source) — le client est-il chez lui en journée ?

    L4 (extension fondateur, 21/08/2026) — ``crm.Lead.occupation_jour`` (script
    d'appel : « Y a-t-il quelqu'un à la maison en journée ? ») PRIME sur tout
    le reste quand le commercial l'a posée : c'est un signal RÉEL de CE client,
    pas un défaut. Absent/pas encore posée ⇒ le comportement HISTORIQUE
    ci-dessous, byte-identique.

    DÉCISION TERRAIN DU FONDATEUR (21/08/2026) : la clientèle résidentielle
    réelle de la société est majoritairement RETRAITÉE et présente dans sa villa
    en journée. La courbe de consommation « standard » à double pic (départ au
    travail / retour le soir) ne lui ressemble pas. Le défaut résidentiel est
    donc ``presence_jour``. C'est une OBSERVATION DE TERRAIN du fondateur, PAS
    une statistique nationale — la source servie le dit explicitement pour que
    la page puisse l'étiqueter honnêtement.

    Avant L4, aucun champ « présence en journée » n'existait sur ``crm.Lead``
    (``ownership`` = statut d'occupation juridique, ``occupation_pct`` = taux
    d'occupation hôtelier — ni l'un ni l'autre ne dit qui est là le jour). Le
    seul signal alors câblé était le profil d'activité PRO du webhook web
    (``web_questionnaire.activity_profile`` ∈ day / day_evening / continuous),
    qui décrit un site actif EN JOURNÉE : toujours utilisé pour les modes non
    résidentiels quand le lead le porte ET qu'``occupation_jour`` est absent.
    Sinon, hors résidentiel, le défaut reste ``absence_jour``.
    """
    lead_occ = _occupation_jour_lead(devis)
    if lead_occ in _OCCUPATION_JOUR_VERS_DRAPEAU:
        return _OCCUPATION_JOUR_VERS_DRAPEAU[lead_occ], 'lead_occupation_jour:%s' % lead_occ

    mode = str(data.get('mode_installation') or '').strip().lower()
    if mode == 'residentiel':
        return OCCUPATION_PRESENCE, 'defaut_residentiel_fondateur'

    try:
        from apps.crm.selectors import profil_activite_pour_devis
        profil = profil_activite_pour_devis(devis)
    except Exception:  # noqa: BLE001 — signal absent → on retombe sur le défaut
        profil = None
    if profil in ('day', 'day_evening', 'continuous'):
        return OCCUPATION_PRESENCE, 'lead_profil_activite:%s' % profil
    return OCCUPATION_ABSENCE, 'defaut_non_residentiel'


def _production(kwc, mensuel, ville, lat, lon):
    """Bloc production par saison, ou ``{}`` si rien n'est servable.

    Chaque saison porte ``forme`` (24 parts, HEURE LOCALE UTC+1, somme 1,0),
    ``kwh_jour`` (énergie réelle du jour moyen de la saison) et ``pic_kw``
    (PUISSANCE moyenne de l'heure de pointe = ``kwh_jour × max(forme)``, jamais
    des kWh) + ``source``.
    """
    if kwc is None or not mensuel:
        # Sans puissance kWc connue (M2) ou sans productible, on ne peut donner
        # NI niveau NI pic : on omet plutôt que d'afficher une forme sans échelle.
        return {}
    valeurs, source_mensuel = mensuel
    out = {}
    for saison in SAISONS:
        resolu = profil_production_journalier(
            saison=saison, lat=lat, lon=lon, ville=ville)
        if not resolu:
            continue
        forme_utc, source_forme = resolu
        forme = vers_heure_locale(forme_utc)
        if not forme:
            continue
        kwh_kwc_jour = moyenne_journaliere_saison(valeurs, saison)
        if kwh_kwc_jour is None:
            continue
        kwh_jour = kwh_kwc_jour * kwc
        out[saison] = {
            'forme': forme,
            'kwh_jour': round(kwh_jour, 1),
            # PUISSANCE (kW) — moyenne sur l'heure de pointe, pas la puissance
            # instantanée, et surtout PAS des kWh (l'ancien libellé « pic ≈
            # 14,3 kWh » de la page confondait les deux).
            'pic_kw': round(kwh_jour * max(forme), 2),
            'source': source_forme,
            'source_productible': source_mensuel,
        }
    return out


def _consommation(monthly_consumption, equipements=None):
    """Bloc consommation par saison (niveau RÉEL uniquement), ou ``{}``.

    ``monthly_consumption`` = la série M10 déjà servie (12 kWh/mois issus des
    factures réelles du lead ; ``[]`` quand elle serait une estimation). On n'en
    tire QUE la moyenne journalière par saison : la forme 24 h reste côté page.

    L4 — quand une couche ``ve`` (véhicule électrique) est active, son
    ``kwh_jour`` (charge FUTURE, absente des factures passées — voir
    :func:`_equipements`) est AJOUTÉ au niveau de chaque saison : c'est
    l'unique couche qui change le total, les autres (piscine/clim)
    REDISTRIBUENT une consommation déjà comptée dans la facture.
    """
    if not monthly_consumption or len(monthly_consumption) != 12:
        return {}
    ve = (equipements or {}).get('ve')
    out = {}
    for saison in SAISONS:
        moyenne = moyenne_journaliere_saison(monthly_consumption, saison)
        if moyenne is None:
            continue
        niveau = moyenne + ve['kwh_jour'] if ve else moyenne
        out[saison] = {'kwh_jour': round(niveau, 1)}
    return out


# ── L4 (21/08/2026) — Équipements du lead : couches de la courbe de conso ────
# Réponses posées au TÉLÉPHONE (crm.Lead, script d'appel), composées ici.
#
# RÈGLE DURE « zéro chiffre inventé » (CLAUDE.md + mémo
# 2026-08-21-memo-estimation-consommation.md, section étage 2) : chaque
# nombre ci-dessous est SOIT une grandeur RÉELLE saisie par le commercial
# (puissance de pompe, nombre de pièces climatisées, km/semaine du véhicule
# électrique), SOIT une conversion/fenêtre SOURCÉE citée en commentaire.
# Aucun défaut de GRANDEUR n'est inventé : sans la valeur réelle, la couche
# correspondante est simplement ABSENTE (omission plutôt qu'invention).
#
# Piscine et climatisation REDISTRIBUENT : l'équipement existe déjà et sa
# consommation est déjà dans les factures du lead (``monthly_consumption``),
# seule la FORME change — jamais ``kwh_jour``. Le véhicule électrique est
# l'EXCEPTION que le mémo indique explicitement : une charge FUTURE, absente
# des factures passées, donc AJOUTÉE au niveau (voir :func:`_consommation`).
#
# Le chauffe-eau électrique n'a NI fenêtre horaire NI puissance sourcées dans
# le mémo (il ne cite qu'un ordre de grandeur kWh/personne/an, et le nombre
# de personnes du foyer n'est pas un champ collecté) : le champ existe sur le
# lead pour le script d'appel et le chatter, mais ne produit ICI aucune
# couche — omission délibérée, jamais une magnitude inventée.

# Source : mémo étage 2 — « piscine (règle T°eau÷2 → 13-14 h/j été,
# bloc 10-18 h) ». La DURÉE totale citée (13-14 h/j) est incompatible avec la
# fenêtre citée dans la MÊME phrase (10h-18h = 8 h) : seule la fenêtre,
# univoque, est retenue ici — la durée n'est PAS appliquée (voir le rapport
# de la mission L4 pour cette réserve).
PISCINE_HEURES = tuple(range(10, 18))  # 10h-18h (borne haute exclue), 8 h
PISCINE_SAISONS = ('ete',)  # usage piscine = saison estivale (mémo)

# Source : mémo étage 2 — « clim (12000 BTU ≈ 1,4 kWh/h non-inverter, défaut
# 8h/j, bloc 13-21h...) ». 13h-21h (borne haute exclue) = exactement 8 h,
# cohérent avec le « défaut 8h/j » du même mémo.
CLIM_HEURES = tuple(range(13, 21))  # 13h-21h (borne haute exclue), 8 h
CLIM_KWH_PAR_UNITE_H = 1.4  # kWh/h par unité 12000 BTU non-inverter (mémo)
CLIM_SAISONS = ('ete',)  # même fenêtre saisonnière que le boost été existant

# Source : mémo étage 2 — « VE (19,8 kWh/100 km ADEME × km/sem — PAS de
# défaut km, saisie obligatoire, charge bloc 21h-6h hors pointe ONEE) ».
# Fenêtre 21h-6h = 9 h ; pas de restriction saisonnière (la recharge n'est
# pas un usage saisonnier au sens du mémo).
VE_HEURES = (21, 22, 23, 0, 1, 2, 3, 4, 5)
VE_KWH_PAR_100KM = 19.8  # ADEME, cité par le mémo


def _nombre_positif(valeur):
    try:
        val = float(valeur)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _entier_positif(valeur):
    try:
        val = int(valeur)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _equipements(lead_equip):
    """Couches d'équipement composables, ou ``{}`` si aucune n'est utilisable.

    ``lead_equip`` = le dict de ``apps.crm.selectors.equipements_pour_devis``
    (lecture cross-app, jamais ``apps.crm.models`` importé ici). Une couche
    n'apparaît QUE si son booléen est vrai ET sa grandeur réelle est
    renseignée — sinon absente (omission, jamais un défaut inventé).
    """
    if not lead_equip:
        return {}
    out = {}

    if lead_equip.get('piscine') is True:
        kw = _nombre_positif(lead_equip.get('piscine_pompe_kw'))
        if kw is not None:
            out['piscine'] = {
                'kw': round(kw, 2),
                'heures': list(PISCINE_HEURES),
                'saisons': list(PISCINE_SAISONS),
                'mode': 'redistribution',
                'source': 'memo_2026-08-21_etage2:piscine_bloc_10_18h',
            }

    if lead_equip.get('clim') is True:
        pieces = _entier_positif(lead_equip.get('clim_pieces'))
        if pieces is not None:
            out['clim'] = {
                'kw': round(pieces * CLIM_KWH_PAR_UNITE_H, 2),
                'heures': list(CLIM_HEURES),
                'saisons': list(CLIM_SAISONS),
                'mode': 'redistribution',
                'source': 'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h',
            }

    if lead_equip.get('voiture_electrique') is True:
        km_semaine = _nombre_positif(lead_equip.get('ve_km_semaine'))
        if km_semaine is not None:
            kwh_jour = km_semaine * VE_KWH_PAR_100KM / 100.0 / 7.0
            out['ve'] = {
                'kwh_jour': round(kwh_jour, 2),
                'heures': list(VE_HEURES),
                'saisons': None,  # toutes saisons — charge non saisonnière
                'mode': 'addition',
                'source': 'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km',
            }

    # chauffe_eau_electrique : DÉLIBÉRÉMENT absent d'``out`` — voir le
    # commentaire d'en-tête (aucune fenêtre/puissance sourcée exploitable).

    return out


def composer_equipements(lead_equip):
    """Couches composables depuis un dict d'équipements BRUT — façade publique.

    Même règle que :func:`_equipements` (une couche n'existe que si son booléen
    est vrai ET sa grandeur réelle est renseignée). Sert l'aperçu générateur,
    qui reçoit les réponses du script d'appel sans devis persisté : un seul
    endroit décide de ce qui compose une couche, jamais deux.
    """
    return _equipements(lead_equip)


def equipements_du_devis(devis):
    """Couches d'équipement composables du lead d'un devis (``{}`` si aucune).

    Façade PUBLIQUE de la composition L4 (:func:`_equipements` appliquée au
    dict du sélecteur CRM) : le moteur horaire CJ2a la consomme sans dupliquer
    une seule règle de provenance ni une seule fenêtre horaire.
    """
    return _equipements(_equipements_lead(devis))


def occupation_du_devis(devis, data=None):
    """``(drapeau, source)`` d'occupation — façade publique de :func:`_occupation`.

    Même chaîne de résolution que la page (réponse RÉELLE du lead d'abord,
    puis défaut fondateur résidentiel, puis profil d'activité PRO) : un seul
    propriétaire pour ce choix, jamais un second défaut dans le moteur.
    """
    return _occupation(devis, data or {})


# ════════════════════════════════════════════════════════════════════════════
# CJ2a — LES SILHOUETTES D'OCCUPATION, CÔTÉ SERVEUR
# ════════════════════════════════════════════════════════════════════════════
# Jusqu'ici les trois silhouettes 24 h vivaient UNIQUEMENT dans la page
# (``apps/web/src/lib/dayProfiles.ts`` ``OCCUPANCY_SHAPES``) : le serveur ne
# servait que le NIVEAU (kWh/jour) et le DRAPEAU d'occupation. Le moteur horaire
# CJ2a (``apps.ventes.etude_horaire``) doit, lui, INTÉGRER heure par heure une
# consommation contre une production — il lui faut donc la FORME, en Python.
#
# LES VALEURS SONT RECOPIÉES VERBATIM de dayProfiles.ts, avec leurs étiquettes
# de provenance — ce ne sont PAS de nouveaux chiffres (règle « zéro chiffre
# inventé »). Un test épingle les deux fichiers l'un à l'autre
# (``test_silhouettes_source_pin``) : si l'un bouge seul, il passe au rouge.
# C'est le serveur qui devient PROPRIÉTAIRE ; la copie TS reste le miroir que
# CJ2b pourra retirer quand l'écran appellera l'endpoint.
#
# PROVENANCE DES POIDS HORAIRES (recherche du 21/08/2026), étiquettes reprises
# telles quelles :
#   [A] FAIT MAROCAIN SOURCÉ — fenêtre de pointe nationale publiée (tarif
#       bi-horaire ONEE : 18h-23h en été, 17h-22h en hiver, one.org.ma) ; record
#       historique d'appel de puissance du réseau marocain le 25/07/2019 à
#       21h45 (presse économique). La domination du soir n'est pas une
#       hypothèse : c'est la forme du réseau marocain.
#   [S] MOTIF DE CLUSTERING SOURCÉ, MAGNITUDE ESTIMÉE — la séparation
#       présent/absent/partiel et l'allure de chaque groupe viennent de la
#       littérature de clustering de courbes de charge résidentielles
#       (ScienceDirect S377877882300333X ; arXiv 2102.11027 ; IOPscience
#       ade3fa). Les VALEURS exactes sont nos estimations calées sur ces allures.
#   [i] INTERPOLATION entre deux heures étiquetées ci-dessus.
#
# Ce sont des POIDS DE FORME, pas des kWh : le NIVEAU vient toujours des
# factures RÉELLES du client.
SILHOUETTES_OCCUPATION = {
    # « Présent en journée » — retraités, foyers mono-actifs, villa occupée.
    OCCUPATION_PRESENCE: (
        0.4, 0.4, 0.4, 0.4, 0.4, 0.4,        # 00-05 h — socle de nuit      [S]
        0.5, 0.8, 1.0, 1.0, 1.1, 1.1,        # 06-11 h            [i][S][S][S][S][i]
        1.35, 1.35, 1.35,                    # 12-14 h — repas + clim        [S]
        1.0, 1.0, 1.0,                       # 15-17 h            [i][i][A]
        1.2, 1.5, 1.8, 1.7,                  # 18-21 h — pointe nationale    [A]
        1.2, 0.7,                            # 22-23 h            [A][i]
    ),
    # « Absent en journée » — actifs partis au travail : creux diurne profond,
    # pointe du soir la plus marquée des trois.
    OCCUPATION_ABSENCE: (
        0.4, 0.4, 0.4, 0.4, 0.4, 0.4,        # 00-05 h                       [S]
        0.7, 1.6,                            # 06-07 h — départ         [i][S]
        1.0,                                 # 08 h                          [i]
        0.45, 0.45, 0.45, 0.45,              # 09-12 h — logement vide       [S]
        0.45, 0.45, 0.45, 0.45,              # 13-16 h — logement vide       [S]
        0.9, 1.4, 1.9, 2.4, 2.3,             # 17-21 h — retour + pointe     [A]
        1.5, 0.9,                            # 22-23 h            [A][i]
    ),
    # « Présence partielle » — télétravail, mi-temps, foyer mixte.
    OCCUPATION_PARTIELLE: (
        0.4, 0.4, 0.4, 0.4, 0.4, 0.4,        # 00-05 h                       [S]
        0.5, 0.9, 1.0,                       # 06-08 h            [i][S][i]
        0.95, 0.95, 0.95,                    # 09-11 h — bureau maison       [S]
        1.1, 1.1,                            # 12-13 h — déjeuner            [S]
        0.9, 0.9, 0.9,                       # 14-16 h                       [S]
        1.1, 1.5, 1.9, 2.2, 2.0,             # 17-21 h — pointe ONEE         [A]
        1.3, 0.8,                            # 22-23 h            [A][i]
    ),
}

#: Silhouette de repli quand le drapeau d'occupation est absent/illisible — le
#: MILIEU HONNÊTE des trois, exactement le choix de ``occupancyFromFlag`` côté
#: page. Jamais un défaut « présent » qui flatterait l'autoconsommation.
OCCUPATION_REPLI = OCCUPATION_PARTIELLE

# POURQUOI LE « BOOST ÉTÉ » (×1,5 sur 13h-21h) DE LA PAGE N'EST PAS APPLIQUÉ ICI.
# Côté page, c'est une PUCE que le visiteur clique pour explorer un scénario ;
# elle module une forme dont le niveau est le même toute l'année. Le moteur
# horaire, lui, met chaque mois à l'échelle de la facture RÉELLE de ce mois
# (facture d'été quand le lead en déclare une distincte) : la surconsommation
# estivale de climatisation est DÉJÀ dans le niveau. Ré-appliquer le
# multiplicateur la compterait DEUX FOIS. La saisonnalité du moteur vient donc
# de la donnée client, jamais d'un coefficient — c'est plus juste ET c'est la
# règle « zéro chiffre inventé ».


def _normaliser_a_un(forme):
    """Ramène une forme positive à une somme de 1,0 (``None`` si insommable)."""
    try:
        vals = [max(0.0, float(v)) for v in forme]
    except (TypeError, ValueError):
        return None
    total = sum(vals)
    if total <= 0:
        return None
    return [v / total for v in vals]


def silhouette_occupation(occupation):
    """Forme 24 h (somme = 1) de l'occupation demandée, repli inclus.

    ``occupation`` est l'un des drapeaux servis par :func:`_occupation`
    (``presence_jour`` / ``absence_jour`` / ``presence_partielle``). Valeur
    inconnue/absente ⇒ :data:`OCCUPATION_REPLI`, jamais une exception.
    """
    brute = SILHOUETTES_OCCUPATION.get(
        occupation, SILHOUETTES_OCCUPATION[OCCUPATION_REPLI])
    return _normaliser_a_un(brute)


def forme_consommation_kwh(kwh_jour, occupation, *, saison=None,
                           equipements=None):
    """Consommation horaire RÉELLE d'un jour : 24 kWh dont la somme = ``kwh_jour``.

    Façade historique de :func:`forme_consommation_detaillee` — elle n'en rend
    que la courbe. Signature et valeurs INCHANGÉES : tous les appelants déjà
    câblés (moteur horaire, aperçu, tests) continuent de lire exactement la
    même liste de 24 kWh.
    """
    return forme_consommation_detaillee(
        kwh_jour, occupation, saison=saison, equipements=equipements)[0]


def forme_consommation_detaillee(kwh_jour, occupation, *, saison=None,
                                 equipements=None):
    """``(conso_24h, couches_horaires)`` — la courbe ET sa décomposition L4.

    C'est la fonction que le moteur horaire intègre contre la production. Elle
    applique EXACTEMENT la règle L4 déjà tenue côté page
    (``proposalCurve.equipmentAdjustedConsumptionKwhShape``), en DEUX PASSES :

    1. **REDISTRIBUTION** (piscine, climatisation) — chaque couche ajoute sa
       puissance RÉELLE (``kw``, saisie par le commercial) sur ses heures
       sourcées, puis l'ensemble est renormalisé pour que la somme retombe
       EXACTEMENT sur le niveau facture (VE exclu) : ces heures grossissent, le
       reste du jour rétrécit d'autant. AUCUN kWh gagné — l'équipement existe
       déjà et sa consommation est DÉJÀ dans la facture, seule la FORME change.
    2. **ADDITION** (véhicule électrique) — ajoutée APRÈS la renormalisation,
       sans être rediluée : c'est la seule charge FUTURE, absente des factures
       passées, donc la seule qui doit vraiment grossir le total. Son énergie
       est déjà comptée dans ``kwh_jour`` par :func:`_consommation`.

    ``kwh_jour`` ≤ 0 ⇒ 24 zéros (aucun niveau inventé). Une couche illisible ou
    hors-saison est ignorée silencieusement, jamais approximée.

    L-GLITCH (24/08/2026) — LA DEUXIÈME VALEUR DE RETOUR. ``couches_horaires``
    dit, pour chaque couche de REDISTRIBUTION réellement appliquée, sa puissance
    déclarée (``kw``) et l'énergie qu'elle place dans CHAQUE heure APRÈS la
    renormalisation (``heures_kwh``). Sans elle, le moteur horaire devrait
    refaire cette composition pour savoir quelle part de l'heure appartient à la
    pompe ou à la clim — c'est-à-dire tenir un SECOND compositeur qui finirait
    par diverger de celui-ci d'une fenêtre ou d'un facteur. La composition reste
    donc à UN seul propriétaire : ce module. Le VE en est absent
    volontairement — sa couche porte une ÉNERGIE (kWh/jour) et aucune puissance
    de chargeur n'est collectée, donc rien à concentrer (voir
    ``etude_horaire.PROFILS_RAFALE``).
    """
    try:
        total = float(kwh_jour)
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0:
        return [0.0] * 24, {}

    forme = silhouette_occupation(occupation) or [1.0 / 24.0] * 24
    couches = equipements or {}

    # Le VE est retiré du niveau AVANT la passe 1 : il ne doit pas être dilué
    # par la renormalisation (il sera rajouté tel quel en passe 2).
    ve = couches.get('ve')
    ve_actif = bool(
        ve and ve.get('mode') == 'addition'
        and _nombre_positif(ve.get('kwh_jour')) is not None
        and (not ve.get('saisons') or saison is None
             or saison in ve['saisons']))
    ve_kwh = float(ve['kwh_jour']) if ve_actif else 0.0
    base_total = max(0.0, total - ve_kwh)

    sortie = [part * base_total for part in forme]

    # ── Passe 1 : redistribution (piscine / clim) ──
    bosse = [0.0] * 24
    actives = {}
    for cle in ('piscine', 'clim'):
        couche = couches.get(cle)
        if not couche or couche.get('mode') != 'redistribution':
            continue
        kw = _nombre_positif(couche.get('kw'))
        if kw is None:
            continue
        saisons = couche.get('saisons')
        if saisons and saison is not None and saison not in saisons:
            continue
        heures_couche = []
        for heure in couche.get('heures') or ():
            if isinstance(heure, int) and 0 <= heure <= 23:
                bosse[heure] += kw
                heures_couche.append(heure)
        if heures_couche:
            actives[cle] = {'kw': kw, 'heures': heures_couche,
                            'source': couche.get('source')}
    # ``facteur`` reste à 1,0 tant qu'aucune bosse n'est posée — exactement le
    # chemin historique, qui ne renormalisait pas dans ce cas.
    facteur = 1.0
    if any(bosse):
        sortie = [v + bosse[h] for h, v in enumerate(sortie)]
        somme = sum(sortie)
        if somme > 0 and base_total > 0:
            facteur = base_total / somme
            sortie = [v * facteur for v in sortie]

    # ── Passe 2 : addition (VE), jamais rediluée ──
    if ve_actif and ve_kwh > 0:
        heures = [h for h in (ve.get('heures') or ())
                  if isinstance(h, int) and 0 <= h <= 23]
        if heures:
            par_heure = ve_kwh / len(heures)
            for heure in heures:
                sortie[heure] += par_heure

    # L'ÉNERGIE DE LA COUCHE, APRÈS RENORMALISATION. La bosse brute (``kw``) est
    # posée AVANT la renormalisation : ce que la couche pèse RÉELLEMENT dans
    # l'heure servie est donc ``kw × facteur``. C'est cette énergie-là — pas la
    # bosse brute — que le moteur concentre en impulsions, sinon il sortirait de
    # l'heure plus d'énergie que la courbe n'en contient.
    for info in actives.values():
        heures_kwh = [0.0] * 24
        for heure in info['heures']:
            heures_kwh[heure] += info['kw'] * facteur
        info['heures_kwh'] = heures_kwh

    return sortie, actives


def construire_courbes_journalieres(devis, data, monthly_consumption=None):
    """Bloc ``courbes_journalieres`` de la charge utile publique, ou ``None``.

    ``None`` (⇒ clé ABSENTE de la charge utile) quand ni la production ni la
    consommation ne sont servables : la page garde alors exactement son
    affichage actuel. Aucune exception ne remonte — un graphe n'empêche jamais
    une proposition de s'afficher.
    """
    try:
        kwc = _nombre(data.get('puissance_kwc'))
        ville_lead, lat, lon = _localisation(devis)
        ville = data.get('client_city') or ville_lead
        mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)

        production = _production(kwc, mensuel, ville, lat, lon)
        equipements = _equipements(_equipements_lead(devis))
        consommation = _consommation(monthly_consumption, equipements)
        if not production and not consommation:
            return None

        batterie_kwh = _nombre(data.get('batterie_kwh_total'))
        options = _options_reelles(data, batterie_kwh)
        occupation, occupation_source = _occupation(devis, data)

        bloc = {
            'note_horaire': NOTE_HORAIRE,
            # Unités explicites : la page ne doit plus jamais étiqueter une
            # puissance en kWh (défaut historique du graphe).
            'unites': {
                'forme': 'part du total du jour (somme = 1)',
                'kwh_jour': 'kWh/jour',
                'pic_kw': 'kW',
                'batterie_kwh': 'kWh',
            },
            'occupation': occupation,
            'occupation_source': occupation_source,
        }
        if production:
            bloc['production'] = production
        if consommation:
            # CJ2b — la forme DE BASE (silhouette d'occupation, AVANT les
            # couches équipements) devient SERVEUR : posée sur CHAQUE saison
            # déjà servie, jamais une forme sans niveau. La page continue de
            # composer ``equipements`` PAR-DESSUS elle-même (les recomposer
            # ici les compterait deux fois — voir l'en-tête du module).
            _forme_base = silhouette_occupation(occupation)
            if _forme_base is not None:
                for _serie_saison in consommation.values():
                    # Une COPIE par saison : partager la même liste entre les
                    # trois saisons ferait qu'une mutation en aval les
                    # changerait toutes les trois à la fois.
                    _serie_saison['forme'] = list(_forme_base)
                bloc['consommation_forme_source'] = (
                    'silhouette_occupation:%s' % occupation)
            bloc['consommation'] = consommation
            # L4 — servi seulement s'il existe une courbe de conso à ajuster
            # (sinon les fenêtres/kw n'ont rien à composer côté page).
            if equipements:
                bloc['equipements'] = equipements
        if options:
            bloc['options'] = options
        if batterie_kwh:
            bloc['batterie_kwh'] = round(batterie_kwh, 1)
        return bloc
    except Exception:  # noqa: BLE001 — le graphe ne casse jamais la page
        logger.warning('courbes_journalieres indisponibles', exc_info=True)
        return None
