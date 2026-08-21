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

Les FORMES 24 h de CONSOMMATION restent côté page : ce sont des estimations
étiquetées comme telles. Le serveur ne sert que le NIVEAU réel (``kwh_jour``)
pour que la page puisse enfin mettre ces formes à l'échelle du vrai client, et
le drapeau ``occupation`` qui dit quelle forme choisir.

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
