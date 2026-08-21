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

    DÉCISION TERRAIN DU FONDATEUR (21/08/2026) : la clientèle résidentielle
    réelle de TAQINOR est majoritairement RETRAITÉE et présente dans sa villa
    en journée. La courbe de consommation « standard » à double pic (départ au
    travail / retour le soir) ne lui ressemble pas. Le défaut résidentiel est
    donc ``presence_jour``. C'est une OBSERVATION DE TERRAIN du fondateur, PAS
    une statistique nationale — la source servie le dit explicitement pour que
    la page puisse l'étiqueter honnêtement.

    Aucun champ « présence en journée » n'existe aujourd'hui sur ``crm.Lead``
    (vérifié : ``ownership`` = statut d'occupation juridique, ``occupation_pct``
    = taux d'occupation hôtelier — ni l'un ni l'autre ne dit qui est là le
    jour). Le seul signal réellement câblé par le webhook web est le profil
    d'activité PRO (``web_questionnaire.activity_profile`` ∈ day /
    day_evening / continuous), qui décrit un site actif EN JOURNÉE : on
    l'utilise pour les modes non résidentiels quand le lead le porte. Sinon,
    hors résidentiel, le défaut est ``absence_jour``.
    """
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


def _consommation(monthly_consumption):
    """Bloc consommation par saison (niveau RÉEL uniquement), ou ``{}``.

    ``monthly_consumption`` = la série M10 déjà servie (12 kWh/mois issus des
    factures réelles du lead ; ``[]`` quand elle serait une estimation). On n'en
    tire QUE la moyenne journalière par saison : la forme 24 h reste côté page.
    """
    if not monthly_consumption or len(monthly_consumption) != 12:
        return {}
    out = {}
    for saison in SAISONS:
        moyenne = moyenne_journaliere_saison(monthly_consumption, saison)
        if moyenne is None:
            continue
        out[saison] = {'kwh_jour': round(moyenne, 1)}
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
        consommation = _consommation(monthly_consumption)
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
        if options:
            bloc['options'] = options
        if batterie_kwh:
            bloc['batterie_kwh'] = round(batterie_kwh, 1)
        return bloc
    except Exception:  # noqa: BLE001 — le graphe ne casse jamais la page
        logger.warning('courbes_journalieres indisponibles', exc_info=True)
        return None
