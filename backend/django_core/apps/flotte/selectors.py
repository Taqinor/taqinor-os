"""Sélecteurs LECTURE SEULE du module Gestion de flotte.

Point d'entrée des LECTURES cross-app vers la flotte. Les autres apps ne lisent
jamais les modèles flotte directement : elles passent par ces fonctions, toutes
scopées par société (CLAUDE.md, règle de modularité cross-app).
"""
import datetime

from django.db import models

from .models import (
    ActifFlotte,
    AffectationConducteur,
    AssuranceVehicule,
    BaremeVignette,
    CarteCarburant,
    CarteGriseVehicule,
    Conducteur,
    ContratVehicule,
    CoutVehicule,
    DemandeVehicule,
    EcheanceEntretien,
    EcheanceReglementaire,
    EnginRoulant,
    EtatDesLieux,
    Garage,
    Infraction,
    OrdreReparation,
    ParametreAmortissementCGI,
    PieceFlotte,
    PlanEntretien,
    Pneumatique,
    PleinCarburant,
    ReleveTelematique,
    ReservationVehicule,
    Sinistre,
    TrajetChantier,
    TrajetTelematique,
    Vehicule,
    VisiteTechnique,
)


def vehicules_de_la_societe(company):
    """Tous les véhicules d'une société (queryset scopé)."""
    return Vehicule.objects.filter(company=company)


def engins_de_la_societe(company):
    """Tous les engins roulants d'une société (queryset scopé)."""
    return EnginRoulant.objects.filter(company=company)


def actifs_de_la_societe(company):
    """FLOTTE5 — Tous les actifs unifiés d'une société (queryset scopé).

    Sélecteur cross-app : les futurs modules entretien/sinistre/document
    appellent cette fonction plutôt que d'importer directement ``ActifFlotte``.
    """
    return ActifFlotte.objects.filter(company=company).select_related(
        'vehicule', 'engin')


def actif_par_vehicule(company, vehicule_id):
    """FLOTTE5 — Retourne l'``ActifFlotte`` associé à un véhicule donné,
    ou ``None`` s'il n'existe pas encore."""
    return ActifFlotte.objects.filter(
        company=company, vehicule_id=vehicule_id).first()


def actif_par_engin(company, engin_id):
    """FLOTTE5 — Retourne l'``ActifFlotte`` associé à un engin donné,
    ou ``None`` s'il n'existe pas encore."""
    return ActifFlotte.objects.filter(
        company=company, engin_id=engin_id).first()


def conducteurs_de_la_societe(company, actif_only=False):
    """FLOTTE7 — Conducteurs d'une société (queryset scopé).

    Si ``actif_only=True``, ne retourne que les conducteurs actifs.
    """
    qs = Conducteur.objects.filter(company=company).select_related('user')
    if actif_only:
        qs = qs.filter(actif=True)
    return qs


def conducteurs_permis_expirant(company, jours=30):
    """FLOTTE7 — Conducteurs dont le permis expire dans les ``jours`` prochains
    jours (inclusif). Ne retourne que les conducteurs avec ``date_expiration``
    renseignée ; les permis déjà expirés sont exclus."""
    today = datetime.date.today()
    horizon = today + datetime.timedelta(days=jours)
    return Conducteur.objects.filter(
        company=company,
        date_expiration__isnull=False,
        date_expiration__gte=today,
        date_expiration__lte=horizon,
    ).select_related('user')


def conducteur_actuel_du_vehicule(company, vehicule_id):
    """FLOTTE8 — Retourne le conducteur actuellement actif pour un véhicule donné.

    Filtre sur ``actif=True`` et la plage de dates : ``date_debut`` dans le passé
    (ou aujourd'hui) et ``date_fin`` soit nulle, soit dans le futur (ou aujourd'hui).
    Retourne le conducteur de l'affectation la plus récente (tri ``-date_debut``),
    ou ``None`` si aucune affectation active n'est trouvée.
    """
    today = datetime.date.today()
    affectation = (
        AffectationConducteur.objects
        .filter(
            company=company,
            vehicule_id=vehicule_id,
            actif=True,
            date_debut__lte=today,
        )
        .filter(
            models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=today)
        )
        .select_related("conducteur")
        .order_by("-date_debut")
        .first()
    )
    return affectation.conducteur if affectation else None


def affectations_du_vehicule(company, vehicule_id):
    """FLOTTE8 — Toutes les affectations (passées et actives) d'un véhicule,
    scopées par société, par ordre chronologique décroissant."""
    return (
        AffectationConducteur.objects
        .filter(company=company, vehicule_id=vehicule_id)
        .select_related("conducteur")
        .order_by("-date_debut")
    )


def affectations_du_conducteur(company, conducteur_id):
    """FLOTTE8 — Toutes les affectations (passées et actives) d'un conducteur,
    scopées par société, par ordre chronologique décroissant."""
    return (
        AffectationConducteur.objects
        .filter(company=company, conducteur_id=conducteur_id)
        .select_related("vehicule")
        .order_by("-date_debut")
    )


def reservations_de_la_societe(company, vehicule_id=None, actives_only=False):
    """FLOTTE10 — Réservations de véhicules d'une société (queryset scopé).

    ``vehicule_id`` filtre sur un véhicule ; ``actives_only`` ne retourne que
    les réservations qui occupent le véhicule (statut ``demandee``/``confirmee``).
    """
    qs = ReservationVehicule.objects.filter(company=company).select_related(
        'vehicule', 'conducteur')
    if vehicule_id is not None:
        qs = qs.filter(vehicule_id=vehicule_id)
    if actives_only:
        qs = qs.filter(statut__in=ReservationVehicule.STATUTS_ACTIFS)
    return qs


def etats_des_lieux_du_vehicule(company, vehicule_id):
    """FLOTTE11 — Tous les états des lieux d'un véhicule (scopé société),
    par ordre chronologique décroissant."""
    return (
        EtatDesLieux.objects
        .filter(company=company, vehicule_id=vehicule_id)
        .select_related('vehicule', 'conducteur', 'reservation')
        .order_by('-date_constat')
    )


def pleins_du_vehicule(company, vehicule_id):
    """FLOTTE12 — Tous les pleins de carburant d'un véhicule (scopé société),
    par ordre chronologique décroissant."""
    return (
        PleinCarburant.objects
        .filter(company=company, vehicule_id=vehicule_id)
        .select_related('vehicule', 'conducteur')
        .order_by('-date_plein', '-kilometrage')
    )


def consommation_vehicule(company, vehicule_id):
    """FLOTTE13 — Consommation d'un véhicule (L/100 km et kWh/100 km).

    Calcule la consommation à partir du carnet de carburant (``PleinCarburant``)
    et du kilométrage au compteur. Méthode « plein-à-plein » : entre deux pleins
    consécutifs (triés par kilométrage croissant), la distance parcourue est
    ``km(n) - km(n-1)`` et le carburant qui l'a couverte est la quantité du plein
    d'ARRIVÉE (``quantite`` du plein ``n``) ; la consommation du segment vaut
    donc ``quantite / distance * 100`` (en L ou kWh pour 100 km selon l'unité du
    plein). Le premier plein de la série ne produit aucun segment (pas de
    distance connue avant lui).

    Garde-fous :
    - ``distance <= 0`` (kilométrage identique ou en recul) → segment ignoré, AUCUNE
      division par zéro.
    - Un changement d'unité (litre↔kwh) entre deux pleins isole les totaux : les
      L et les kWh sont agrégés séparément (jamais additionnés).

    Retourne un dict LECTURE SEULE scopé société :

    ``{
        'vehicule_id', 'nb_pleins', 'nb_segments',
        'distance_totale_km',
        'litres': {'distance_km', 'quantite', 'conso_l_100km'} | None,
        'kwh':    {'distance_km', 'quantite', 'conso_kwh_100km'} | None,
        'segments': [
            {'de_km', 'a_km', 'distance_km', 'quantite', 'unite',
             'conso_100km', 'date_plein'}, …
        ],
    }``

    ``litres`` / ``kwh`` valent ``None`` quand aucun segment exploitable
    n'existe pour cette unité (p. ex. distance nulle partout) — jamais une
    consommation calculée sur une distance nulle. Tous les nombres sont des
    ``float`` arrondis ; les quantités proviennent de ``DecimalField`` converties.
    """
    from .models import PleinCarburant

    pleins = list(
        PleinCarburant.objects
        .filter(company=company, vehicule_id=vehicule_id)
        .order_by('kilometrage', 'date_plein', 'id')
        .values('id', 'kilometrage', 'quantite', 'unite', 'date_plein')
    )

    segments = []
    # Totaux séparés par unité (les L et les kWh ne se mélangent jamais).
    totaux = {
        PleinCarburant.Unite.LITRE: {'distance': 0, 'quantite': 0.0},
        PleinCarburant.Unite.KWH: {'distance': 0, 'quantite': 0.0},
    }
    distance_totale = 0

    for precedent, courant in zip(pleins, pleins[1:]):
        distance = courant['kilometrage'] - precedent['kilometrage']
        if distance <= 0:
            # Compteur identique ou en recul : aucun segment exploitable.
            continue
        quantite = float(courant['quantite'] or 0)
        unite = courant['unite']
        conso = round(quantite / distance * 100, 3)
        distance_totale += distance
        if unite in totaux:
            totaux[unite]['distance'] += distance
            totaux[unite]['quantite'] += quantite
        segments.append({
            'de_km': precedent['kilometrage'],
            'a_km': courant['kilometrage'],
            'distance_km': distance,
            'quantite': round(quantite, 3),
            'unite': unite,
            'conso_100km': conso,
            'date_plein': courant['date_plein'],
        })

    def _agrege(unite, cle_conso):
        bloc = totaux[unite]
        if bloc['distance'] <= 0:
            return None
        return {
            'distance_km': bloc['distance'],
            'quantite': round(bloc['quantite'], 3),
            cle_conso: round(bloc['quantite'] / bloc['distance'] * 100, 3),
        }

    return {
        'vehicule_id': vehicule_id,
        'nb_pleins': len(pleins),
        'nb_segments': len(segments),
        'distance_totale_km': distance_totale,
        'litres': _agrege(PleinCarburant.Unite.LITRE, 'conso_l_100km'),
        'kwh': _agrege(PleinCarburant.Unite.KWH, 'conso_kwh_100km'),
        'segments': segments,
    }


def cartes_de_la_societe(company, actif_only=False, vehicule_id=None):
    """FLOTTE14 — Cartes carburant d'une société (queryset scopé).

    ``actif_only=True`` ne retourne que les cartes actives ; ``vehicule_id``
    filtre sur un véhicule attribué.
    """
    qs = CarteCarburant.objects.filter(company=company).select_related(
        'vehicule', 'conducteur')
    if actif_only:
        qs = qs.filter(actif=True)
    if vehicule_id is not None:
        qs = qs.filter(vehicule_id=vehicule_id)
    return qs


# Seuils par défaut de la détection d'anomalie (FLOTTE14).
# Un saut de kilométrage est jugé invraisemblable au-delà de cette distance
# entre deux pleins consécutifs (compteur trafiqué / saisie erronée).
ANOMALIE_SAUT_KM_MAX = 5000
# Une consommation d'un segment est jugée aberrante si elle dépasse la ligne de
# base du véhicule (médiane de ses segments) de plus de ce facteur.
ANOMALIE_CONSO_FACTEUR = 2.0


def _mediane(valeurs):
    """Médiane d'une liste de nombres (``None`` si vide). Lecture seule."""
    ordonnees = sorted(valeurs)
    n = len(ordonnees)
    if n == 0:
        return None
    milieu = n // 2
    if n % 2 == 1:
        return ordonnees[milieu]
    return (ordonnees[milieu - 1] + ordonnees[milieu]) / 2.0


def anomalies_pleins(company, vehicule_id=None, saut_km_max=ANOMALIE_SAUT_KM_MAX,
                     conso_facteur=ANOMALIE_CONSO_FACTEUR):
    """FLOTTE14 — Détecte les pleins suspects (km incohérent / fraude).

    Parcourt le carnet de carburant (``PleinCarburant``) — scopé société, et
    filtré sur un véhicule si ``vehicule_id`` est fourni — et signale trois
    familles d'anomalie, sans rien écrire :

    1. ``km_recul`` — le kilométrage d'un plein est INFÉRIEUR ou ÉGAL à celui du
       plein chronologiquement précédent du même véhicule : le compteur a reculé
       (ou stagné alors qu'on a refait le plein) → trafiquage probable.
    2. ``km_saut`` — la distance entre deux pleins consécutifs dépasse
       ``saut_km_max`` : saut de compteur invraisemblable.
    3. ``conso_aberrante`` — la consommation du segment plein-à-plein (réutilise
       la math FLOTTE13 : ``quantité du plein d'arrivée / distance × 100``)
       dépasse la ligne de base du véhicule (médiane de ses segments de même
       unité) multipliée par ``conso_facteur``. Le calcul est garde-fou contre
       la division par zéro : un segment à distance nulle ne produit pas de
       conso (il est déjà couvert par ``km_recul``).
    4. ``plafond_depasse`` — le ``prix_total`` du plein dépasse le plafond de la
       carte carburant active rattachée au véhicule (la PLUS BASSE des cartes
       du véhicule, ou des cartes « parc » non rattachées). Aucune carte / aucun
       plafond → aucune alerte.

    Retourne un dict LECTURE SEULE scopé société ::

        {
          'vehicule_id': <id|None>,
          'nb_pleins': <int>,
          'nb_anomalies': <int>,
          'anomalies': [
            {'plein_id', 'vehicule_id', 'type', 'gravite', 'message',
             'date_plein', 'kilometrage'}, …
          ],
        }

    Plusieurs anomalies peuvent porter sur le même plein (une entrée chacune).
    """
    pleins = list(
        PleinCarburant.objects
        .filter(company=company)
        .filter(**({'vehicule_id': vehicule_id}
                   if vehicule_id is not None else {}))
        .order_by('vehicule_id', 'date_plein', 'kilometrage', 'id')
        .values('id', 'vehicule_id', 'kilometrage', 'quantite', 'unite',
                'prix_total', 'date_plein')
    )

    # XFLT12 — Capacité réservoir (L) par véhicule, via le modèle catalogue
    # (``ModeleVehicule``, si rattaché). Sert la détection « plein > réservoir ».
    capacite_reservoir_par_vehicule = dict(
        Vehicule.objects.filter(
            company=company, modele_ref__capacite_reservoir_l__isnull=False,
        ).values_list('id', 'modele_ref__capacite_reservoir_l')
    )

    # Regroupe par véhicule pour comparer des pleins comparables.
    par_vehicule = {}
    for plein in pleins:
        par_vehicule.setdefault(plein['vehicule_id'], []).append(plein)

    # Plafond effectif par véhicule (carte active la plus basse). Le plafond des
    # cartes « parc » (sans véhicule) s'applique à tous les véhicules.
    cartes = list(
        CarteCarburant.objects
        .filter(company=company, actif=True, plafond__isnull=False)
        .values('vehicule_id', 'plafond')
    )
    plafond_global = None
    plafond_par_vehicule = {}
    for carte in cartes:
        montant = float(carte['plafond'])
        if carte['vehicule_id'] is None:
            if plafond_global is None or montant < plafond_global:
                plafond_global = montant
        else:
            actuel = plafond_par_vehicule.get(carte['vehicule_id'])
            if actuel is None or montant < actuel:
                plafond_par_vehicule[carte['vehicule_id']] = montant

    anomalies = []

    def _ajoute(plein, type_, gravite, message):
        anomalies.append({
            'plein_id': plein['id'],
            'vehicule_id': plein['vehicule_id'],
            'type': type_,
            'gravite': gravite,
            'message': message,
            'date_plein': plein['date_plein'],
            'kilometrage': plein['kilometrage'],
        })

    for veh_id, liste in par_vehicule.items():
        plafond = plafond_par_vehicule.get(veh_id, plafond_global)

        # Ligne de base de consommation : médiane des segments par unité.
        consos_par_unite = {}
        segments = []
        for precedent, courant in zip(liste, liste[1:]):
            distance = courant['kilometrage'] - precedent['kilometrage']
            if distance <= 0:
                segments.append((courant, None))
                continue
            quantite = float(courant['quantite'] or 0)
            conso = quantite / distance * 100  # FLOTTE13 : pas de div/0 ici.
            consos_par_unite.setdefault(courant['unite'], []).append(conso)
            segments.append((courant, (distance, conso, courant['unite'])))
        baselines = {
            unite: _mediane(valeurs)
            for unite, valeurs in consos_par_unite.items()
        }

        for index, plein in enumerate(liste):
            # 1) / 2) Cohérence du kilométrage vs le plein précédent.
            if index > 0:
                precedent = liste[index - 1]
                distance = plein['kilometrage'] - precedent['kilometrage']
                if distance <= 0:
                    _ajoute(
                        plein, 'km_recul', 'haute',
                        "Kilométrage en recul ou stagnant vs le plein précédent "
                        f"({precedent['kilometrage']} km → "
                        f"{plein['kilometrage']} km).",
                    )
                elif distance > saut_km_max:
                    _ajoute(
                        plein, 'km_saut', 'moyenne',
                        f"Saut de kilométrage invraisemblable de {distance} km "
                        f"(seuil {saut_km_max} km) depuis le plein précédent.",
                    )

            # 4) Dépassement de plafond carte.
            if plafond is not None and float(plein['prix_total'] or 0) > plafond:
                _ajoute(
                    plein, 'plafond_depasse', 'moyenne',
                    f"Montant du plein ({float(plein['prix_total'] or 0):.2f} "
                    f"MAD) supérieur au plafond de la carte ({plafond:.2f} MAD).",
                )

            # 5) XFLT12 — Plein > capacité réservoir du modèle catalogue
            # (litres uniquement — un plein électrique se mesure en kWh, sans
            # rapport avec un réservoir carburant).
            capacite = capacite_reservoir_par_vehicule.get(veh_id)
            if capacite is not None and plein['unite'] == 'litre' \
                    and float(plein['quantite'] or 0) > capacite:
                _ajoute(
                    plein, 'plein_superieur_reservoir', 'haute',
                    f"Quantité du plein ({float(plein['quantite'] or 0):.1f} L) "
                    f"supérieure à la capacité du réservoir ({capacite} L) — "
                    "fraude probable.",
                )

        # 3) Consommation aberrante vs la ligne de base du véhicule.
        for courant, seg in segments:
            if seg is None:
                continue
            _distance, conso, unite = seg
            base = baselines.get(unite)
            if base is None or base <= 0:
                continue
            if conso > base * conso_facteur:
                _ajoute(
                    courant, 'conso_aberrante', 'moyenne',
                    f"Consommation du segment ({conso:.1f}/100 km) anormalement "
                    f"élevée vs la moyenne du véhicule ({base:.1f}/100 km).",
                )

    anomalies.sort(key=lambda a: (
        str(a['date_plein']), a['plein_id'], a['type']))

    return {
        'vehicule_id': vehicule_id,
        'nb_pleins': len(pleins),
        'nb_anomalies': len(anomalies),
        'anomalies': anomalies,
    }


def emplacement_stock_label(company, emplacement_stock_id):
    """FLOTTE3 — Libellé de l'emplacement de stock lié à un véhicule.

    Résout `emplacement_stock_id` via le sélecteur LECTURE de `apps.stock`
    (import local, jamais `apps.stock.models`). Renvoie le nom de
    l'``EmplacementStock`` s'il existe et appartient à la SOCIÉTÉ, sinon dégrade
    sur l'id nu (``"#<id>"``) ; ``None`` si aucun lien. Lecture seule.
    """
    if not emplacement_stock_id:
        return None
    try:
        from apps.stock import selectors as stock_selectors
        emplacement = stock_selectors.get_emplacement_scoped(
            company, emplacement_stock_id)
    except Exception:
        emplacement = None
    if emplacement is not None:
        return str(emplacement)
    return f'#{emplacement_stock_id}'


# ── FLOTTE15 — Plans d'entretien préventif (km / date / heures) ────────────────

def plans_de_la_societe(company, actif_only=False, actif_flotte_id=None):
    """FLOTTE15 — Plans d'entretien préventif d'une société (queryset scopé).

    ``actif_only=True`` ne retourne que les plans actifs ; ``actif_flotte_id``
    filtre sur un actif unifié (``ActifFlotte``) précis.
    """
    qs = PlanEntretien.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if actif_only:
        qs = qs.filter(actif=True)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    return qs


def _etat_actif_courant(actif_flotte):
    """Lecture seule : kilométrage et compteur d'heures COURANTS d'un actif.

    Renvoie ``(km_courant | None, heures_courant | None)`` selon le type de
    l'actif unifié : un véhicule porte un kilométrage, un engin un compteur
    d'heures. L'autre dimension vaut ``None`` (non applicable).
    """
    if actif_flotte.vehicule_id is not None:
        return actif_flotte.vehicule.kilometrage, None
    if actif_flotte.engin_id is not None:
        # compteur_heures est un Decimal ; on le ramène à un entier de comparaison.
        return None, int(actif_flotte.engin.compteur_heures or 0)
    return None, None


def plan_entretien_echeance(plan, km_courant=None, heures_courant=None,
                            today=None):
    """FLOTTE15 — Calcule l'échéance d'UN plan vs l'état courant de l'actif.

    Pour chaque critère renseigné (km / jours / heures), calcule la prochaine
    échéance ``dernier_réalisé + intervalle`` et la marge restante vs l'état
    courant. Le plan est globalement ``due`` si AU MOINS un critère est dépassé,
    ``upcoming`` si au moins un critère tombe dans sa marge d'alerte sans être
    dépassé, sinon ``ok``. Quand aucune base de comparaison n'est connue (état
    courant manquant pour tous les critères), le statut est ``inconnu``.

    GARDE-FOUS : aucune division n'est effectuée ici (calcul additif), donc pas
    de division par zéro possible ; un intervalle nul/absent est simplement
    ignoré (un ``PositiveIntegerField`` ne peut pas être négatif). Lecture seule.
    """
    today = today or datetime.date.today()
    criteres = []

    # ── Critère kilométrique ──────────────────────────────────────────────────
    if plan.intervalle_km:
        base = plan.dernier_km if plan.dernier_km is not None else 0
        prochaine = base + plan.intervalle_km
        if km_courant is None:
            statut = 'inconnu'
            restant = None
        else:
            restant = prochaine - km_courant
            if restant <= 0:
                statut = 'due'
            elif restant <= plan.seuil_alerte_km:
                statut = 'upcoming'
            else:
                statut = 'ok'
        criteres.append({
            'dimension': 'km',
            'prochaine_echeance': prochaine,
            'restant': restant,
            'statut': statut,
        })

    # ── Critère calendaire ────────────────────────────────────────────────────
    if plan.intervalle_jours:
        # Base : la date du dernier entretien si connue, sinon la date de création
        # du plan, et à défaut (objet non encore persisté) la date du jour.
        base_date = plan.derniere_date
        if base_date is None and plan.date_creation is not None:
            base_date = plan.date_creation.date()
        if base_date is None:
            base_date = today
        prochaine_date = base_date + datetime.timedelta(
            days=plan.intervalle_jours)
        restant_jours = (prochaine_date - today).days
        if restant_jours <= 0:
            statut = 'due'
        elif restant_jours <= plan.seuil_alerte_jours:
            statut = 'upcoming'
        else:
            statut = 'ok'
        criteres.append({
            'dimension': 'jours',
            'prochaine_echeance': prochaine_date.isoformat(),
            'restant': restant_jours,
            'statut': statut,
        })

    # ── Critère horaire (compteur d'heures) ───────────────────────────────────
    if plan.intervalle_heures:
        base = plan.dernier_heures if plan.dernier_heures is not None else 0
        prochaine = base + plan.intervalle_heures
        if heures_courant is None:
            statut = 'inconnu'
            restant = None
        else:
            restant = prochaine - heures_courant
            if restant <= 0:
                statut = 'due'
            elif restant <= plan.seuil_alerte_heures:
                statut = 'upcoming'
            else:
                statut = 'ok'
        criteres.append({
            'dimension': 'heures',
            'prochaine_echeance': prochaine,
            'restant': restant,
            'statut': statut,
        })

    statuts = {c['statut'] for c in criteres}
    if 'due' in statuts:
        statut_global = 'due'
    elif 'upcoming' in statuts:
        statut_global = 'upcoming'
    elif 'ok' in statuts:
        statut_global = 'ok'
    else:
        statut_global = 'inconnu'

    return {'statut': statut_global, 'criteres': criteres}


def plans_entretien_status(company, actif_only=True, statut=None):
    """FLOTTE15 — Liste les entretiens DUS / À VENIR d'une société (lecture seule).

    Parcourt les plans actifs (``actif_only=True`` par défaut) — scopés société —
    et calcule pour chacun son échéance vs l'état COURANT de l'actif ciblé
    (kilométrage du véhicule, compteur d'heures de l'engin, date du jour). Le
    paramètre ``statut`` (``due`` | ``upcoming`` | ``ok`` | ``inconnu``) restreint
    la liste retournée.

    Retourne un dict LECTURE SEULE scopé société ::

        {
          'nb_plans': <int>,           # plans examinés
          'nb_due': <int>,
          'nb_upcoming': <int>,
          'plans': [
            {'plan_id', 'actif_flotte_id', 'actif_label', 'type_entretien',
             'km_courant', 'heures_courant', 'statut', 'criteres': [...]}, …
          ],
        }

    Les plans ``due`` sont listés en premier, puis ``upcoming``, puis le reste.
    Aucune écriture, aucun effet de bord.
    """
    today = datetime.date.today()
    plans = plans_de_la_societe(company, actif_only=actif_only)

    resultats = []
    nb_due = 0
    nb_upcoming = 0
    for plan in plans:
        km_courant, heures_courant = _etat_actif_courant(plan.actif_flotte)
        echeance = plan_entretien_echeance(
            plan, km_courant=km_courant, heures_courant=heures_courant,
            today=today)
        if echeance['statut'] == 'due':
            nb_due += 1
        elif echeance['statut'] == 'upcoming':
            nb_upcoming += 1
        resultats.append({
            'plan_id': plan.id,
            'actif_flotte_id': plan.actif_flotte_id,
            'actif_label': plan.actif_flotte.label,
            'type_entretien': plan.type_entretien,
            'km_courant': km_courant,
            'heures_courant': heures_courant,
            'statut': echeance['statut'],
            'criteres': echeance['criteres'],
        })

    if statut:
        resultats = [r for r in resultats if r['statut'] == statut]

    ordre = {'due': 0, 'upcoming': 1, 'ok': 2, 'inconnu': 3}
    resultats.sort(key=lambda r: (ordre.get(r['statut'], 9),
                                  r['type_entretien']))

    return {
        'nb_plans': len(resultats) if statut else plans.count(),
        'nb_due': nb_due,
        'nb_upcoming': nb_upcoming,
        'plans': resultats,
    }


# ── FLOTTE16 — Échéances d'entretien dues (générées depuis les plans) ──────────

def echeances_de_la_societe(company, statut=None, ouvertes_only=False,
                            plan_id=None):
    """FLOTTE16 — Échéances d'entretien d'une société (queryset scopé).

    Liste les ``EcheanceEntretien`` matérialisées par
    ``services.generer_echeances_entretien`` — les travaux d'entretien DUS à
    planifier / faire. Triées du plus urgent au moins urgent (statut puis date
    d'échéance), elles donnent la « liste des dues / en retard ».

    Filtres : ``statut`` (``a_faire`` | ``planifie`` | ``fait``) restreint à un
    statut précis ; ``ouvertes_only=True`` ne garde que les échéances ouvertes
    (``a_faire`` / ``planifie``) — l'entretien encore à traiter ; ``plan_id``
    restreint à un plan. Lecture seule, scopée société.
    """
    qs = EcheanceEntretien.objects.filter(company=company).select_related(
        'plan', 'actif_flotte', 'actif_flotte__vehicule',
        'actif_flotte__engin')
    if statut:
        qs = qs.filter(statut=statut)
    if ouvertes_only:
        qs = qs.filter(statut__in=EcheanceEntretien.STATUTS_OUVERTS)
    if plan_id is not None:
        qs = qs.filter(plan_id=plan_id)
    return qs


# ── FLOTTE17 — Garages / ateliers + ordres de réparation (atelier + coûts) ─────

def garages_de_la_societe(company, actif_only=False):
    """FLOTTE17 — Garages / ateliers d'une société (queryset scopé).

    ``actif_only=True`` ne retourne que les garages actifs.
    """
    qs = Garage.objects.filter(company=company)
    if actif_only:
        qs = qs.filter(actif=True)
    return qs


def ordres_reparation_de_la_societe(company, actif_flotte_id=None,
                                    garage_id=None, statut=None,
                                    ouverts_only=False):
    """FLOTTE17 — Ordres de réparation d'une société (queryset scopé).

    Filtres : ``actif_flotte_id`` (un actif précis), ``garage_id`` (un garage),
    ``statut`` (``ouvert`` | ``en_cours`` | ``cloture``), ``ouverts_only=True``
    (ne garde que les OR non clôturés). Lecture seule, scopée société.
    """
    qs = OrdreReparation.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'garage', 'echeance')
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if garage_id is not None:
        qs = qs.filter(garage_id=garage_id)
    if statut:
        qs = qs.filter(statut=statut)
    if ouverts_only:
        qs = qs.exclude(statut__in=OrdreReparation.STATUTS_CLOS)
    return qs


def couts_reparation(company, actif_flotte_id=None, garage_id=None,
                     statut=None):
    """FLOTTE17 — Synthèse des coûts de réparation d'une société (lecture seule).

    Agrège les coûts des ``OrdreReparation`` (scopés société, filtrables par
    actif / garage / statut) : totaux main d'œuvre, pièces, total, nombre d'OR,
    et coût MOYEN par OR (garde-fou division par zéro : ``None`` si aucun OR).

    Retourne un dict LECTURE SEULE ::

        {
          'nb_ordres', 'cout_main_oeuvre', 'cout_pieces', 'cout_total',
          'cout_moyen',  # None si nb_ordres == 0
        }

    Tous les montants sont des ``float`` arrondis (issus de ``DecimalField``).
    """
    qs = ordres_reparation_de_la_societe(
        company, actif_flotte_id=actif_flotte_id, garage_id=garage_id,
        statut=statut)
    agg = qs.aggregate(
        nb=models.Count('id'),
        mo=models.Sum('cout_main_oeuvre'),
        pieces=models.Sum('cout_pieces'),
        total=models.Sum('cout_total'),
    )
    nb = agg['nb'] or 0
    total = float(agg['total'] or 0)
    # Garde-fou division par zéro : aucun OR → pas de moyenne.
    cout_moyen = round(total / nb, 2) if nb else None
    return {
        'nb_ordres': nb,
        'cout_main_oeuvre': round(float(agg['mo'] or 0), 2),
        'cout_pieces': round(float(agg['pieces'] or 0), 2),
        'cout_total': round(total, 2),
        'cout_moyen': cout_moyen,
    }


# ── FLOTTE18 — Pneumatiques + pièces ──────────────────────────────────────────

def pneumatiques_de_la_societe(company, vehicule_id=None, statut=None):
    """Pneumatiques d'une société (queryset scopé, filtrable véhicule/statut)."""
    qs = Pneumatique.objects.filter(company=company).select_related('vehicule')
    if vehicule_id is not None:
        qs = qs.filter(vehicule_id=vehicule_id)
    if statut:
        qs = qs.filter(statut=statut)
    return qs


def pieces_de_la_societe(company, vehicule_id=None, ordre_reparation_id=None):
    """Pièces d'une société (queryset scopé, filtrable véhicule / OR)."""
    qs = PieceFlotte.objects.filter(company=company).select_related(
        'vehicule', 'ordre_reparation')
    if vehicule_id is not None:
        qs = qs.filter(vehicule_id=vehicule_id)
    if ordre_reparation_id is not None:
        qs = qs.filter(ordre_reparation_id=ordre_reparation_id)
    return qs


def synthese_pneus_pieces_vehicule(company, vehicule_id):
    """FLOTTE18 — Synthèse pneus + pièces d'un véhicule (lecture seule).

    Agrège, pour un véhicule d'une société :
    - le nombre de pneus montés (``nb_pneus_montes``) et leur coût total ;
    - le nombre de lignes de pièces (``nb_pieces``), la quantité totale et le
      coût total des pièces (quantité × coût unitaire) ;
    - le coût total combiné (pneus + pièces).

    Retourne un dict LECTURE SEULE — tous les montants sont des ``float``
    arrondis. Aucun calcul de moyenne ici, donc pas de division par zéro.
    """
    pneus = pneumatiques_de_la_societe(company, vehicule_id=vehicule_id)
    agg_pneus = pneus.aggregate(
        nb_montes=models.Count(
            'id', filter=models.Q(statut__in=Pneumatique.STATUTS_MONTES)),
        cout=models.Sum('cout'),
    )

    pieces = pieces_de_la_societe(company, vehicule_id=vehicule_id)
    cout_pieces = 0.0
    quantite_pieces = 0
    nb_pieces = 0
    for piece in pieces:
        cout_pieces += piece.cout_total
        quantite_pieces += piece.quantite or 0
        nb_pieces += 1

    cout_pneus = round(float(agg_pneus['cout'] or 0), 2)
    cout_pieces = round(cout_pieces, 2)
    return {
        'vehicule_id': vehicule_id,
        'nb_pneus_montes': agg_pneus['nb_montes'] or 0,
        'cout_pneus': cout_pneus,
        'nb_pieces': nb_pieces,
        'quantite_pieces': quantite_pieces,
        'cout_pieces': cout_pieces,
        'cout_total': round(cout_pneus + cout_pieces, 2),
    }


# ── FLOTTE19 — Échéances réglementaires (visite technique, assurance…) ─────────

def echeances_reglementaires_de_la_societe(company, type_echeance=None,
                                           statut=None, actif_flotte_id=None):
    """FLOTTE19 — Échéances réglementaires d'une société (queryset scopé).

    Filtres facultatifs : ``type_echeance`` (visite_technique | assurance |
    vignette | carte_grise | taxe_essieu | autre), ``statut`` (statut STOCKÉ :
    a_jour | a_renouveler | expire) et ``actif_flotte_id`` (un actif précis).
    Lecture seule, scopée société.
    """
    qs = EcheanceReglementaire.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if type_echeance:
        qs = qs.filter(type_echeance=type_echeance)
    if statut:
        qs = qs.filter(statut=statut)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    return qs


def echeances_reglementaires_status(company, today=None):
    """FLOTTE19 — État des échéances réglementaires d'une société (lecture seule).

    Calcule, pour chaque ``EcheanceReglementaire`` de la société, son état RÉEL
    vs ``today`` (date du jour par défaut, INJECTABLE pour les tests) via
    ``EcheanceReglementaire.statut_calcule`` :

    - ``overdue``  : la date d'échéance est déjà passée (``expire``) ;
    - ``upcoming`` : la date tombe dans la fenêtre ``alerte_jours``
      (``a_renouveler``) ;
    - ``due``      : à jour (``a_jour``).

    Retourne un dict LECTURE SEULE scopé société ::

        {
          'nb_total': <int>,
          'nb_overdue': <int>,
          'nb_upcoming': <int>,
          'nb_ok': <int>,
          'echeances': [
            {'id', 'actif_flotte_id', 'actif_label', 'type_echeance',
             'date_echeance', 'alerte_jours', 'statut_calcule'}, …
          ],
        }

    Les échéances expirées sont listées en premier, puis les imminentes, puis le
    reste — du plus urgent au moins urgent. Aucune écriture, aucun effet de bord.
    """
    if today is None:
        today = datetime.date.today()

    qs = echeances_reglementaires_de_la_societe(company)

    resultats = []
    nb_overdue = 0
    nb_upcoming = 0
    nb_ok = 0
    for echeance in qs:
        statut = echeance.statut_calcule(today=today)
        if statut == EcheanceReglementaire.Statut.EXPIRE:
            nb_overdue += 1
        elif statut == EcheanceReglementaire.Statut.A_RENOUVELER:
            nb_upcoming += 1
        else:
            nb_ok += 1
        resultats.append({
            'id': echeance.id,
            'actif_flotte_id': echeance.actif_flotte_id,
            'actif_label': echeance.actif_flotte.label
            if echeance.actif_flotte_id else None,
            'type_echeance': echeance.type_echeance,
            'date_echeance': echeance.date_echeance,
            'alerte_jours': echeance.alerte_jours,
            'statut_calcule': statut,
        })

    ordre = {
        EcheanceReglementaire.Statut.EXPIRE: 0,
        EcheanceReglementaire.Statut.A_RENOUVELER: 1,
        EcheanceReglementaire.Statut.A_JOUR: 2,
    }
    resultats.sort(key=lambda r: (ordre.get(r['statut_calcule'], 9),
                                  r['date_echeance']
                                  or datetime.date.max))

    return {
        'nb_total': len(resultats),
        'nb_overdue': nb_overdue,
        'nb_upcoming': nb_upcoming,
        'nb_ok': nb_ok,
        'echeances': resultats,
    }


def echeances_reglementaires_expirantes(company, within=30, today=None):
    """FLOTTE19 — Échéances réglementaires DUES/EXPIRÉES sous ``within`` jours.

    Retourne les ``EcheanceReglementaire`` de la société dont la date d'échéance
    est déjà passée OU tombe dans les ``within`` prochains jours (inclusif), du
    plus urgent au moins urgent. ``today`` est INJECTABLE (date du jour par
    défaut). Lecture seule, scopée société.
    """
    if today is None:
        today = datetime.date.today()
    horizon = today + datetime.timedelta(days=within)
    return echeances_reglementaires_de_la_societe(company).filter(
        date_echeance__lte=horizon,
    ).order_by('date_echeance', 'id')


# ── FLOTTE20 — Barème de la vignette / TSAV (CV × énergie) ─────────────────────

def baremes_vignette_de_la_societe(company, energie=None, annee=None,
                                   actif=None):
    """FLOTTE20 — Lignes de barème vignette / TSAV d'une société (queryset scopé).

    Filtres facultatifs : ``energie`` (essence | diesel | electrique | hybride),
    ``annee`` (année exacte du barème) et ``actif`` (bool). Lecture seule, scopée
    société.
    """
    qs = BaremeVignette.objects.filter(company=company)
    if energie:
        qs = qs.filter(energie=energie)
    if annee is not None:
        qs = qs.filter(annee=annee)
    if actif is not None:
        qs = qs.filter(actif=actif)
    return qs


def calcul_tsav(vehicule, annee=None):
    """FLOTTE20 — Montant de la vignette / TSAV d'un véhicule (lecture seule).

    Choisit, dans le barème ÉDITABLE de la société du véhicule, la ligne ACTIVE
    dont l'``energie`` correspond à celle du véhicule et dont la tranche
    ``cv_min ≤ puissance_fiscale ≤ cv_max`` contient sa puissance fiscale, puis
    renvoie un dict LECTURE SEULE ::

        {
          'montant': <Decimal|None>,   # None si aucune tranche ne correspond
          'energie': <str>,
          'puissance_fiscale': <int|None>,
          'annee': <int|None>,         # année effectivement retenue (ou None)
          'bareme_id': <int|None>,     # ligne de barème retenue (ou None)
          'exonere': <bool>,           # True si une ligne correspond ET montant=0
          'note': <str>,               # explication lisible
        }

    **Sélection de l'année** : si ``annee`` est fourni, on cherche d'abord une
    ligne pour CETTE année, puis on retombe sur le barème générique (``annee=0``)
    si aucune ligne datée ne correspond. Sans ``annee``, on prend l'année la plus
    récente disponible (générique inclus). L'électrique est typiquement exonéré
    (une ligne ``electrique`` à ``montant = 0`` → ``montant`` 0 et ``exonere``).

    Aucune écriture, aucun effet de bord. ``annee`` est threadé jusqu'au bout.
    """
    company = vehicule.company
    energie = vehicule.energie
    cv = vehicule.puissance_fiscale

    base = {
        'montant': None,
        'energie': energie,
        'puissance_fiscale': cv,
        'annee': None,
        'bareme_id': None,
        'exonere': False,
        'note': '',
    }

    if cv is None:
        base['note'] = (
            "Puissance fiscale (CV) inconnue : impossible de calculer la TSAV.")
        return base

    qs = BaremeVignette.objects.filter(
        company=company, energie=energie, actif=True,
        cv_min__lte=cv, cv_max__gte=cv,
    )

    # Choix de l'année : la datée demandée en priorité, sinon le générique
    # (annee=0), sinon l'année la plus récente disponible.
    candidat = None
    if annee is not None:
        candidat = qs.filter(annee=annee).order_by('cv_min').first()
        if candidat is None:
            candidat = qs.filter(annee=0).order_by('cv_min').first()
    else:
        candidat = qs.order_by('-annee', 'cv_min').first()

    if candidat is None:
        base['note'] = (
            f"Aucune tranche de barème active pour énergie « {energie} » "
            f"et {cv} CV"
            + (f" (année {annee})." if annee is not None else "."))
        return base

    base['montant'] = candidat.montant
    base['annee'] = candidat.annee
    base['bareme_id'] = candidat.id
    base['exonere'] = candidat.montant == 0
    if base['exonere']:
        base['note'] = (
            f"Exonéré (montant 0) pour énergie « {energie} » et {cv} CV.")
    else:
        base['note'] = (
            f"TSAV {candidat.montant} MAD (énergie « {energie} », {cv} CV, "
            f"tranche {candidat.cv_min}-{candidat.cv_max}).")
    return base


# ── FLOTTE21 — Polices d'assurance auto ────────────────────────────────────────

def assurances_vehicule_de_la_societe(company, statut=None,
                                      actif_flotte_id=None):
    """FLOTTE21 — Polices d'assurance d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (statut STOCKÉ : valide | a_renouveler |
    expiree) et ``actif_flotte_id`` (un actif précis). Lecture seule, scopée
    société.
    """
    qs = AssuranceVehicule.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if statut:
        qs = qs.filter(statut=statut)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    return qs


def assurances_vehicule_expirantes(company, within=30, today=None):
    """FLOTTE21 — Polices d'assurance DUES/EXPIRÉES sous ``within`` jours.

    Retourne les ``AssuranceVehicule`` de la société dont la date d'échéance est
    déjà passée OU tombe dans les ``within`` prochains jours (inclusif), du plus
    urgent au moins urgent. ``today`` est INJECTABLE (date du jour par défaut).
    Lecture seule, scopée société.
    """
    if today is None:
        today = datetime.date.today()
    horizon = today + datetime.timedelta(days=within)
    return assurances_vehicule_de_la_societe(company).filter(
        date_echeance__lte=horizon,
    ).order_by('date_echeance', 'id')


# ── FLOTTE25 — Sinistres ───────────────────────────────────────────────────────

def sinistres_de_la_societe(company, statut=None, actif_flotte_id=None,
                            type_sinistre=None):
    """FLOTTE25 — Sinistres d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (declare | en_cours | clos | indemnise),
    ``actif_flotte_id`` (un actif précis) et ``type_sinistre`` (accident_materiel,
    vol, bris_de_glace…). Lecture seule, scopée société, du plus récent au plus
    ancien.
    """
    qs = Sinistre.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'assurance')
    if statut:
        qs = qs.filter(statut=statut)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if type_sinistre:
        qs = qs.filter(type_sinistre=type_sinistre)
    return qs


# ── FLOTTE26 — Infractions / PV de circulation ─────────────────────────────────

def infractions_de_la_societe(company, statut=None, actif_flotte_id=None,
                              type_infraction=None):
    """FLOTTE26 — Infractions / PV de circulation d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (a_payer | payee | contestee | classee),
    ``actif_flotte_id`` (un actif précis) et ``type_infraction``
    (exces_vitesse, stationnement, feu_rouge…). Lecture seule, scopée société,
    du plus récent au plus ancien.
    """
    qs = Infraction.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'conducteur')
    if statut:
        qs = qs.filter(statut=statut)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if type_infraction:
        qs = qs.filter(type_infraction=type_infraction)
    return qs


# ── FLOTTE27 — Relevés télématiques ────────────────────────────────────────────

def releves_telematiques_de_la_societe(company, actif_flotte_id=None,
                                       source=None):
    """FLOTTE27 — Relevés télématiques d'une société (queryset scopé).

    Filtres facultatifs : ``actif_flotte_id`` (un actif précis) et ``source``
    (manuel | telematique). Lecture seule, scopée société, du plus récent au
    plus ancien.
    """
    qs = ReleveTelematique.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if source:
        qs = qs.filter(source=source)
    return qs


# ── FLOTTE22 — Visites techniques ──────────────────────────────────────────────

def visites_techniques_de_la_societe(company, statut=None,
                                     actif_flotte_id=None):
    """FLOTTE22 — Visites techniques d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (statut STOCKÉ : valide | a_renouveler |
    expiree) et ``actif_flotte_id`` (un actif précis). Lecture seule, scopée
    société.
    """
    qs = VisiteTechnique.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if statut:
        qs = qs.filter(statut=statut)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    return qs


def visites_techniques_expirantes(company, within=30, today=None):
    """FLOTTE22 — Visites techniques DUES/EXPIRÉES sous ``within`` jours.

    Retourne les ``VisiteTechnique`` de la société dont la prochaine visite est
    déjà passée OU tombe dans les ``within`` prochains jours (inclusif), du plus
    urgent au moins urgent. ``today`` est INJECTABLE (date du jour par défaut).
    Lecture seule, scopée société.
    """
    if today is None:
        today = datetime.date.today()
    horizon = today + datetime.timedelta(days=within)
    return visites_techniques_de_la_societe(company).filter(
        date_prochaine__lte=horizon,
    ).order_by('date_prochaine', 'id')


# ── FLOTTE23 — Cartes grises & autorisations de circulation ────────────────────

def cartes_grises_de_la_societe(company, statut=None, actif_flotte_id=None):
    """FLOTTE23 — Cartes grises d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (statut STOCKÉ : valide | a_renouveler |
    expiree) et ``actif_flotte_id`` (un actif précis). Lecture seule, scopée
    société.
    """
    qs = CarteGriseVehicule.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if statut:
        qs = qs.filter(statut=statut)
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    return qs


def cartes_grises_expirantes(company, within=30, today=None):
    """FLOTTE23 — Autorisations de circulation DUES/EXPIRÉES sous ``within`` j.

    Retourne les ``CarteGriseVehicule`` de la société dont l'autorisation de
    circulation a une date de validité déjà passée OU tombant dans les
    ``within`` prochains jours (inclusif), du plus urgent au moins urgent. Les
    cartes grises sans date de validité d'autorisation sont exclues. ``today``
    est INJECTABLE (date du jour par défaut). Lecture seule, scopée société.
    """
    if today is None:
        today = datetime.date.today()
    horizon = today + datetime.timedelta(days=within)
    return cartes_grises_de_la_societe(company).filter(
        autorisation_date_validite__isnull=False,
        autorisation_date_validite__lte=horizon,
    ).order_by('autorisation_date_validite', 'id')


# ── XFLT1 — Contrats véhicule (leasing/LLD/location/entretien) ────────────────

def contrats_vehicule_de_la_societe(company, statut=None, vehicule_id=None):
    """XFLT1 — Contrats véhicule d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (STOCKÉ, pas le statut calculé) et
    ``vehicule_id`` (un véhicule précis). Lecture seule, scopée société.
    """
    qs = ContratVehicule.objects.filter(company=company).select_related(
        'vehicule', 'garage')
    if statut is not None:
        qs = qs.filter(statut=statut)
    if vehicule_id is not None:
        qs = qs.filter(vehicule_id=vehicule_id)
    return qs


def contrats_vehicule_expirants(company, within=30, today=None):
    """XFLT1 — Contrats véhicule DUS/EXPIRÉS sous ``within`` jours.

    Retourne les ``ContratVehicule`` de la société dont ``date_fin`` est déjà
    passée OU tombe dans les ``within`` prochains jours (inclusif), du plus
    urgent au moins urgent. Les contrats sans ``date_fin`` (durée
    indéterminée) ne remontent jamais. ``today`` est INJECTABLE (date du jour
    par défaut). Lecture seule, scopée société.
    """
    if today is None:
        today = datetime.date.today()
    horizon = today + datetime.timedelta(days=within)
    return contrats_vehicule_de_la_societe(company).filter(
        date_fin__isnull=False,
        date_fin__lte=horizon,
    ).order_by('date_fin', 'id')


# ── XFLT3 — Grand livre des coûts par véhicule ──────────────────────────────────

def couts_vehicule_de_la_societe(company, actif_flotte_id=None,
                                 categorie=None):
    """XFLT3 — Coûts véhicule divers d'une société (queryset scopé).

    Filtres facultatifs : ``actif_flotte_id`` (un actif précis) et
    ``categorie``. Lecture seule, scopée société, du plus récent au plus
    ancien.
    """
    qs = CoutVehicule.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'conducteur')
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if categorie is not None:
        qs = qs.filter(categorie=categorie)
    return qs


def ledger_vehicule(company, vehicule_id, periode=None):
    """XFLT3 — Grand livre unifié des coûts d'un véhicule (lecture seule).

    Fusionne, pour un véhicule de la société, TOUTES les sources de coûts déjà
    saisies dans le module flotte en une vue chronologique UNIQUE, triée par
    date décroissante :

    * ``carburant``   — chaque ``PleinCarburant`` (FLOTTE12), montant =
      ``prix_total`` ;
    * ``reparation``  — chaque ``OrdreReparation`` (FLOTTE17) de l'actif,
      montant = ``cout_total`` (daté à l'ouverture) ;
    * ``assurance``   — chaque ``AssuranceVehicule`` (FLOTTE21) de l'actif,
      montant = ``franchise`` (datée au début de couverture, ou à l'échéance
      si le début est absent) ;
    * ``tsav``        — la TSAV annuelle calculée (FLOTTE20, via
      ``calcul_tsav``) pour l'année courante, datée au 1er janvier — omise si
      aucun montant n'est calculable (puissance fiscale inconnue) ;
    * ``infraction``  — chaque ``Infraction`` (FLOTTE26) de l'actif, montant =
      ``montant_amende`` ;
    * ``cout_divers`` — chaque ``CoutVehicule`` (XFLT3) de l'actif (péage,
      parking, lavage, contrat, autre…).

    ``periode`` (optionnel) est un tuple ``(date_debut, date_fin)`` inclusif
    qui borne toutes les sources DATÉES (la TSAV, sans date propre, suit sa
    date d'ancrage au 1er janvier).

    Retourne un dict LECTURE SEULE ::

        {
          'vehicule_id', 'actif_flotte_id', 'nb_lignes',
          'lignes': [ {'source', 'categorie', 'date', 'montant',
                       'libelle', 'conducteur_id', 'objet_id'}, … ],
        }

    Le TCO (FLOTTE31, ``tco_vehicule``) reste intact — ce sélecteur est une
    vue chronologique complémentaire, pas un remplacement de l'agrégat. Aucune
    écriture, aucun effet de bord.
    """
    vehicule = (Vehicule.objects
                .filter(company=company, id=vehicule_id)
                .select_related('actif_flotte')
                .first())
    if vehicule is None:
        return {
            'vehicule_id': vehicule_id, 'actif_flotte_id': None,
            'nb_lignes': 0, 'lignes': [],
        }

    actif_flotte_id = getattr(
        getattr(vehicule, 'actif_flotte', None), 'id', None)

    lignes = []

    def _dans_periode(date_):
        if periode is None or date_ is None:
            return True
        debut, fin = periode
        if debut is not None and date_ < debut:
            return False
        if fin is not None and date_ > fin:
            return False
        return True

    # 1) Carburant.
    for plein in PleinCarburant.objects.filter(
            company=company, vehicule_id=vehicule_id):
        if not _dans_periode(plein.date_plein):
            continue
        lignes.append({
            'source': 'carburant', 'categorie': 'carburant',
            'date': plein.date_plein, 'montant': float(plein.prix_total or 0),
            'libelle': f'Plein — {plein.station}'.strip(' —'),
            'conducteur_id': plein.conducteur_id, 'objet_id': plein.id,
        })

    if actif_flotte_id is not None:
        # 2) Réparations.
        for ordre in OrdreReparation.objects.filter(
                company=company, actif_flotte_id=actif_flotte_id):
            if not _dans_periode(ordre.date_ouverture):
                continue
            lignes.append({
                'source': 'reparation', 'categorie': 'entretien',
                'date': ordre.date_ouverture,
                'montant': float(ordre.cout_total or 0),
                'libelle': f'OR — {ordre.garage}'.strip(' —') if
                ordre.garage_id else 'Ordre de réparation',
                'conducteur_id': None, 'objet_id': ordre.id,
            })

        # 3) Assurances (franchise, datée au début de couverture).
        for assur in AssuranceVehicule.objects.filter(
                company=company, actif_flotte_id=actif_flotte_id):
            date_ = assur.date_debut or assur.date_echeance
            if not _dans_periode(date_):
                continue
            lignes.append({
                'source': 'assurance', 'categorie': 'assurance',
                'date': date_, 'montant': float(assur.franchise or 0),
                'libelle': f'Assurance — {assur.assureur}'.strip(' —'),
                'conducteur_id': None, 'objet_id': assur.id,
            })

        # 4) Infractions.
        for inf in Infraction.objects.filter(
                company=company, actif_flotte_id=actif_flotte_id):
            if not _dans_periode(inf.date_infraction):
                continue
            lignes.append({
                'source': 'infraction', 'categorie': 'amende',
                'date': inf.date_infraction,
                'montant': float(inf.montant_amende or 0),
                'libelle': f'Infraction — {inf.get_type_infraction_display()}',
                'conducteur_id': inf.conducteur_id, 'objet_id': inf.id,
            })

        # 6) Coûts divers.
        for cout in CoutVehicule.objects.filter(
                company=company, actif_flotte_id=actif_flotte_id):
            if not _dans_periode(cout.date):
                continue
            lignes.append({
                'source': 'cout_divers', 'categorie': cout.categorie,
                'date': cout.date, 'montant': float(cout.montant or 0),
                'libelle': (f'{cout.get_categorie_display()} — '
                            f'{cout.fournisseur}').strip(' —'),
                'conducteur_id': cout.conducteur_id, 'objet_id': cout.id,
            })

    # 5) TSAV (annuelle, ancrée au 1er janvier de l'année courante).
    tsav_annee = datetime.date.today().year
    tsav_date = datetime.date(tsav_annee, 1, 1)
    if _dans_periode(tsav_date):
        tsav = calcul_tsav(vehicule, annee=tsav_annee)
        if tsav.get('montant') is not None:
            lignes.append({
                'source': 'tsav', 'categorie': 'vignette',
                'date': tsav_date, 'montant': float(tsav['montant']),
                'libelle': f'TSAV {tsav_annee}',
                'conducteur_id': None, 'objet_id': None,
            })

    lignes.sort(key=lambda x: (x['date'] is None, x['date']), reverse=True)

    return {
        'vehicule_id': vehicule_id,
        'actif_flotte_id': actif_flotte_id,
        'nb_lignes': len(lignes),
        'lignes': lignes,
    }


# ── XFLT7 — Rapport d'analyse des coûts (pivot + benchmark) ────────────────────

def analyse_couts_report(company, group_by='vehicule', periode=None):
    """XFLT7 — Rapport pivot des coûts par véhicule × catégorie × mois
    (lecture seule).

    Construit, pour CHAQUE véhicule de la société, son ``ledger_vehicule``
    (XFLT3, toutes sources unifiées) puis agrège selon ``group_by`` :

    * ``'vehicule'``  — total par véhicule (label + immatriculation) ;
    * ``'categorie'`` — total par catégorie de coût ;
    * ``'mois'``      — total par mois (``'YYYY-MM'``) ;
    * ``'conducteur'``— total par conducteur (lignes sans conducteur exclues) ;
    * ``'garage'``    — total par garage des ``OrdreReparation`` (lignes hors
      réparation exclues).

    ``periode`` (optionnel) est un tuple ``(date_debut, date_fin)`` transmis
    tel quel à ``ledger_vehicule``.

    Calcule aussi, par véhicule : ``cout_par_km`` (coût total / distance
    parcourue, réutilise l'odomètre courant du véhicule — ``None`` si
    kilométrage nul) et signale un OUTLIER de consommation quand la
    consommation moyenne du véhicule (L/100km ou kWh/100km, FLOTTE13) dépasse
    de plus de 20 % la MÉDIANE des véhicules de MÊME modèle
    (``marque``+``modele`` identiques ; un modèle seul dans le parc n'est
    jamais outlier — pas de comparaison possible).

    Retourne un dict LECTURE SEULE ::

        {
          'group_by', 'pivot': [ {'cle', 'libelle', 'total'}, … ],
          'par_vehicule': [ {'vehicule_id', 'label', 'cout_total',
                             'cout_par_km', 'distance_km'}, … ],
          'par_garage': [ {'garage_id', 'garage_nom', 'total'}, … ],
          'outliers': [ {'vehicule_id', 'label', 'conso', 'mediane_modele',
                         'ecart_pct'}, … ],
        }

    Aucune écriture, aucun effet de bord.
    """
    vehicules = list(Vehicule.objects.filter(company=company))

    pivot_totaux = {}
    par_vehicule = []
    par_garage_totaux = {}

    for vehicule in vehicules:
        ledger = ledger_vehicule(company, vehicule.id, periode=periode)
        cout_total = 0.0
        for ligne in ledger['lignes']:
            montant = ligne['montant']
            cout_total += montant

            if group_by == 'categorie':
                cle = ligne['categorie']
                pivot_totaux[cle] = pivot_totaux.get(cle, 0.0) + montant
            elif group_by == 'mois':
                date_ = ligne['date']
                cle = date_.strftime('%Y-%m') if date_ else 'inconnu'
                pivot_totaux[cle] = pivot_totaux.get(cle, 0.0) + montant
            elif group_by == 'conducteur':
                if ligne['conducteur_id'] is not None:
                    cle = ligne['conducteur_id']
                    pivot_totaux[cle] = pivot_totaux.get(cle, 0.0) + montant

            if ligne['source'] == 'reparation' and ligne['objet_id']:
                ordre = OrdreReparation.objects.filter(
                    id=ligne['objet_id']).select_related('garage').first()
                if ordre is not None and ordre.garage_id is not None:
                    nom = ordre.garage.nom
                    par_garage_totaux[nom] = (
                        par_garage_totaux.get(nom, 0.0) + montant)

        if group_by == 'vehicule':
            pivot_totaux[vehicule.id] = cout_total

        distance = vehicule.kilometrage or 0
        cout_par_km = round(cout_total / distance, 3) if distance > 0 \
            else None
        par_vehicule.append({
            'vehicule_id': vehicule.id,
            'label': str(vehicule),
            'cout_total': round(cout_total, 2),
            'cout_par_km': cout_par_km,
            'distance_km': distance,
        })

    # Pivot en liste triée par total décroissant.
    pivot = [
        {'cle': cle, 'libelle': str(cle), 'total': round(total, 2)}
        for cle, total in sorted(
            pivot_totaux.items(), key=lambda kv: kv[1], reverse=True)
    ]

    par_garage = [
        {'garage_nom': nom, 'total': round(total, 2)}
        for nom, total in sorted(
            par_garage_totaux.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # ── Outliers de consommation (>20% au-dessus de la médiane du modèle) ──
    par_modele = {}
    conso_par_vehicule = {}
    for vehicule in vehicules:
        conso = consommation_vehicule(company, vehicule.id)
        valeur = None
        bloc_litres = conso.get('litres')
        bloc_kwh = conso.get('kwh')
        if bloc_litres:
            valeur = bloc_litres['conso_l_100km']
        elif bloc_kwh:
            valeur = bloc_kwh['conso_kwh_100km']
        if valeur is None:
            continue
        conso_par_vehicule[vehicule.id] = valeur
        cle_modele = (vehicule.marque, vehicule.modele)
        par_modele.setdefault(cle_modele, []).append(valeur)

    outliers = []
    for vehicule in vehicules:
        valeur = conso_par_vehicule.get(vehicule.id)
        if valeur is None:
            continue
        cle_modele = (vehicule.marque, vehicule.modele)
        groupe = par_modele.get(cle_modele, [])
        if len(groupe) < 2:
            continue  # Seul de son modèle : pas de comparaison possible.
        mediane = _mediane(groupe)
        if mediane is None or mediane <= 0:
            continue
        ecart_pct = round((valeur - mediane) / mediane * 100, 1)
        if ecart_pct > 20:
            outliers.append({
                'vehicule_id': vehicule.id,
                'label': str(vehicule),
                'conso': valeur,
                'mediane_modele': round(mediane, 2),
                'ecart_pct': ecart_pct,
            })

    return {
        'group_by': group_by,
        'pivot': pivot,
        'par_vehicule': par_vehicule,
        'par_garage': par_garage,
        'outliers': outliers,
    }


# ── XFLT8 — TVA carburant : récupérable vs non déductible ──────────────────────

def synthese_tva_carburant(company, periode):
    """XFLT8 — Synthèse mensuelle TVA carburant récupérable / non déductible
    (lecture seule).

    ``periode`` est un tuple ``(date_debut, date_fin)`` bornant
    ``PleinCarburant.date_plein`` (inclusif — ``None`` de part et d'autre =
    aucune borne). Agrège, pour la société, le total ``montant_tva`` des
    pleins RÉCUPÉRABLES et NON DÉDUCTIBLES, PAR MOIS (``'YYYY-MM'``), pour
    alimenter la déclaration TVA (compta LIT ce sélecteur — jamais l'inverse,
    voir CLAUDE.md).

    Retourne un dict LECTURE SEULE ::

        {
          'periode': [<date_debut>, <date_fin>],
          'par_mois': [
            {'mois': 'YYYY-MM', 'tva_recuperable': <float>,
             'tva_non_deductible': <float>}, …
          ],
          'total_recuperable': <float>, 'total_non_deductible': <float>,
        }

    Aucune écriture, aucun effet de bord.
    """
    debut, fin = periode if periode else (None, None)
    qs = PleinCarburant.objects.filter(company=company)
    if debut is not None:
        qs = qs.filter(date_plein__gte=debut)
    if fin is not None:
        qs = qs.filter(date_plein__lte=fin)

    par_mois = {}
    total_recuperable = 0.0
    total_non_deductible = 0.0

    for plein in qs.values('date_plein', 'montant_tva', 'tva_recuperable'):
        mois = plein['date_plein'].strftime('%Y-%m')
        montant = float(plein['montant_tva'] or 0)
        bloc = par_mois.setdefault(
            mois, {'mois': mois, 'tva_recuperable': 0.0,
                   'tva_non_deductible': 0.0})
        if plein['tva_recuperable']:
            bloc['tva_recuperable'] += montant
            total_recuperable += montant
        else:
            bloc['tva_non_deductible'] += montant
            total_non_deductible += montant

    return {
        'periode': [debut, fin],
        'par_mois': sorted(par_mois.values(), key=lambda b: b['mois']),
        'total_recuperable': round(total_recuperable, 2),
        'total_non_deductible': round(total_non_deductible, 2),
    }


# ── FLOTTE24 — Moteur d'alertes d'échéances réglementaires (J-30/15/7/échu) ────

# Fenêtre maximale de l'alerteur : on ne remonte que les échéances déjà
# expirées (échu) OU dues dans les 30 prochains jours (inclusif). Au-delà,
# l'échéance est « hors fenêtre » et n'apparaît pas dans le moteur d'alertes.
ALERTES_HORIZON_JOURS = 30

# Bornes (en jours restants, inclusif) qui définissent chaque seau d'urgence.
# Un seuil est choisi par ordre croissant : J-7 d'abord (≤ 7 j), puis J-15
# (≤ 15 j), puis J-30 (≤ 30 j). Une date déjà passée tombe dans « échu ».
ALERTES_BUCKETS = (
    ('j7', 7),
    ('j15', 15),
    ('j30', 30),
)


def _bucket_pour_jours(jours_restants):
    """FLOTTE24 — Range un nombre de jours restants dans un seau d'urgence.

    Retourne ``'echu'`` si ``jours_restants`` est négatif (date passée), sinon
    le premier seau (``'j7'`` → ``'j15'`` → ``'j30'``) dont la borne couvre la
    valeur. Retourne ``None`` si la date est hors fenêtre (> 30 j). Lecture
    seule, sans effet de bord.
    """
    if jours_restants is None:
        return None
    if jours_restants < 0:
        return 'echu'
    for nom, borne in ALERTES_BUCKETS:
        if jours_restants <= borne:
            return nom
    return None


def alertes_echeances_reglementaires(company, today=None):
    """FLOTTE24 — Moteur unifié d'alertes d'échéances réglementaires (lecture seule).

    Agrège, pour une société, TOUTES les échéances réglementaires DUES ou
    IMMINENTES portées par les différents modèles flotte et les classe par
    SEAU d'urgence : ``echu`` (date passée), ``j7`` (≤ 7 j), ``j15`` (≤ 15 j),
    ``j30`` (≤ 30 j). Les échéances à plus de 30 jours (hors fenêtre) sont
    EXCLUES.

    Sources agrégées (chacune réutilise le sélecteur ``*_expirantes`` existant
    quand il existe, sinon filtre directement le modèle) :

    * ``echeance_reglementaire`` — ``EcheanceReglementaire.date_echeance``
      (FLOTTE19, via ``echeances_reglementaires_expirantes``) ;
    * ``assurance`` — ``AssuranceVehicule.date_echeance``
      (FLOTTE21, via ``assurances_vehicule_expirantes``) ;
    * ``visite_technique`` — ``VisiteTechnique.date_prochaine``
      (FLOTTE22, via ``visites_techniques_expirantes``) ;
    * ``carte_grise`` — ``CarteGriseVehicule.autorisation_date_validite``
      (FLOTTE23, via ``cartes_grises_expirantes``) ;
    * ``entretien`` — ``EcheanceEntretien.due_le`` des échéances OUVERTES
      (FLOTTE16) — l'échéance de MAINTENANCE datée encore à traiter ;
    * ``contrat_vehicule`` — ``ContratVehicule.date_fin`` (XFLT1, via
      ``contrats_vehicule_expirants``) — contrat de leasing/LLD/location/
      entretien arrivant à échéance. Distinct de ``assurance`` (jamais de
      doublon : le contrat d'assurance reste sur ``AssuranceVehicule`` seul).

    ``today`` est INJECTABLE (date du jour par défaut). Tout est scopé société.

    Retourne un dict LECTURE SEULE ::

        {
          'today': <date>,
          'horizon_jours': 30,
          'nb_total': <int>,
          'nb_echu': <int>, 'nb_j7': <int>, 'nb_j15': <int>, 'nb_j30': <int>,
          'buckets': {
            'echu': [ <alerte>, … ], 'j7': […], 'j15': […], 'j30': […],
          },
          'alertes': [ <alerte>, … ],   # liste plate triée par urgence
        }

    Chaque ``<alerte>`` est un dict ::

        {'source', 'objet_id', 'actif_flotte_id', 'actif_label', 'type',
         'libelle', 'date_echeance', 'jours_restants', 'bucket'}

    La liste plate ``alertes`` est triée du plus urgent au moins urgent (échu
    d'abord, puis par date d'échéance croissante). Aucune écriture, aucun effet
    de bord.
    """
    if today is None:
        today = datetime.date.today()

    alertes = []

    def _ajoute(source, objet_id, actif_flotte_id, actif_label, type_,
                libelle, date_echeance):
        """Ajoute une alerte si sa date tombe dans la fenêtre (échu .. J-30)."""
        if date_echeance is None:
            return
        jours_restants = (date_echeance - today).days
        bucket = _bucket_pour_jours(jours_restants)
        if bucket is None:
            return  # hors fenêtre (> 30 j).
        alertes.append({
            'source': source,
            'objet_id': objet_id,
            'actif_flotte_id': actif_flotte_id,
            'actif_label': actif_label,
            'type': type_,
            'libelle': libelle,
            'date_echeance': date_echeance,
            'jours_restants': jours_restants,
            'bucket': bucket,
        })

    horizon = ALERTES_HORIZON_JOURS

    # 1) Échéances réglementaires génériques (FLOTTE19).
    for ech in echeances_reglementaires_expirantes(
            company, within=horizon, today=today):
        _ajoute(
            'echeance_reglementaire', ech.id, ech.actif_flotte_id,
            ech.actif_flotte.label if ech.actif_flotte_id else None,
            ech.type_echeance, ech.get_type_echeance_display(),
            ech.date_echeance)

    # 2) Polices d'assurance (FLOTTE21).
    for assur in assurances_vehicule_expirantes(
            company, within=horizon, today=today):
        _ajoute(
            'assurance', assur.id, assur.actif_flotte_id,
            assur.actif_flotte.label if assur.actif_flotte_id else None,
            'assurance',
            f'Assurance {assur.assureur} n°{assur.numero_police}'.strip(),
            assur.date_echeance)

    # 3) Visites techniques (FLOTTE22).
    for vt in visites_techniques_expirantes(
            company, within=horizon, today=today):
        _ajoute(
            'visite_technique', vt.id, vt.actif_flotte_id,
            vt.actif_flotte.label if vt.actif_flotte_id else None,
            'visite_technique',
            f'Visite technique {vt.centre}'.strip(),
            vt.date_prochaine)

    # 4) Cartes grises / autorisations de circulation (FLOTTE23).
    for cg in cartes_grises_expirantes(
            company, within=horizon, today=today):
        _ajoute(
            'carte_grise', cg.id, cg.actif_flotte_id,
            cg.actif_flotte.label if cg.actif_flotte_id else None,
            'carte_grise',
            f'Autorisation de circulation n°{cg.numero_carte_grise}'.strip(),
            cg.autorisation_date_validite)

    # 5) Échéances d'entretien DATÉES encore ouvertes (FLOTTE16). Seules les
    # échéances qui portent une ``due_le`` entrent dans l'alerteur calendaire.
    entretiens = (
        echeances_de_la_societe(company, ouvertes_only=True)
        .filter(due_le__isnull=False)
    )
    for ee in entretiens:
        _ajoute(
            'entretien', ee.id, ee.actif_flotte_id,
            ee.actif_flotte.label if ee.actif_flotte_id else None,
            ee.type_entretien,
            f'Entretien : {ee.type_entretien}'.strip(),
            ee.due_le)

    # 6) Contrats véhicule (leasing/LLD/location/entretien) — XFLT1. Rattachés
    # au véhicule directement (pas d'ActifFlotte sur ce modèle) : on résout
    # l'actif_flotte_id via la reverse-relation si elle existe.
    for ctr in contrats_vehicule_expirants(company, within=horizon,
                                           today=today):
        actif = getattr(ctr.vehicule, 'actif_flotte', None)
        _ajoute(
            'contrat_vehicule', ctr.id, actif.id if actif else None,
            str(ctr.vehicule),
            ctr.type_contrat,
            f'Contrat {ctr.get_type_contrat_display()} — '
            f'{ctr.fournisseur}'.strip(' —'),
            ctr.date_fin)

    # Tri du plus urgent au moins urgent : par date d'échéance croissante (les
    # échéances déjà passées, donc les plus anciennes, remontent naturellement
    # en tête), puis par source/objet pour un ordre stable.
    alertes.sort(key=lambda a: (a['date_echeance'], a['source'],
                                a['objet_id']))

    buckets = {'echu': [], 'j7': [], 'j15': [], 'j30': []}
    for alerte in alertes:
        buckets[alerte['bucket']].append(alerte)

    return {
        'today': today,
        'horizon_jours': horizon,
        'nb_total': len(alertes),
        'nb_echu': len(buckets['echu']),
        'nb_j7': len(buckets['j7']),
        'nb_j15': len(buckets['j15']),
        'nb_j30': len(buckets['j30']),
        'buckets': buckets,
        'alertes': alertes,
    }


# ── FLOTTE28 — Suivi de position & trajets télématiques ────────────────────────

def trajets_telematiques_de_la_societe(company, actif_flotte_id=None,
                                       date_debut=None, date_fin=None):
    """FLOTTE28 — Trajets télématiques d'une société (queryset scopé).

    Filtres facultatifs : ``actif_flotte_id`` (un actif précis), ``date_debut``
    et ``date_fin`` (bornent le début du trajet, inclusif). Lecture seule,
    scopée société, du plus récent au plus ancien.
    """
    qs = TrajetTelematique.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'releve_depart', 'releve_arrivee')
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if date_debut is not None:
        qs = qs.filter(debut__date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(debut__date__lte=date_fin)
    return qs


# ── FLOTTE29 — Journal kilométrique & trajets imputés chantier ─────────────────

def trajets_chantier_de_la_societe(company, actif_flotte_id=None,
                                   installation_id=None, date_debut=None,
                                   date_fin=None):
    """FLOTTE29 — Trajets imputés chantier d'une société (queryset scopé).

    Filtres facultatifs : ``actif_flotte_id`` (un actif précis),
    ``installation_id`` (un chantier précis), ``date_debut`` / ``date_fin``
    (bornent ``date_trajet``, inclusif). Lecture seule, scopée société, du plus
    récent au plus ancien.
    """
    qs = TrajetChantier.objects.filter(company=company).select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    if actif_flotte_id is not None:
        qs = qs.filter(actif_flotte_id=actif_flotte_id)
    if installation_id is not None:
        qs = qs.filter(installation_id=installation_id)
    if date_debut is not None:
        qs = qs.filter(date_trajet__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_trajet__lte=date_fin)
    return qs


def journal_kilometrique(company, actif_flotte_id=None, installation_id=None,
                         date_debut=None, date_fin=None):
    """FLOTTE29 — Journal kilométrique agrégé (lecture seule, scopé société).

    Agrège les ``TrajetChantier`` de la société (filtrables par actif / chantier
    / période) en distance totale parcourue et la VENTILE par chantier
    (``installations.Installation`` via son id). Le libellé du chantier est
    résolu à travers ``installations.selectors.installation_scoped`` (jamais
    d'import croisé des modèles). Les trajets non imputés sont regroupés sous
    ``installation_id=None``.

    Retourne un dict LECTURE SEULE ::

        {
          'nb_trajets', 'distance_totale_km',
          'par_chantier': [
            {'installation_id', 'chantier_reference', 'nb_trajets',
             'distance_km'}, …
          ],
        }

    Les distances sont des ``float`` arrondis. Aucune écriture.
    """
    trajets = trajets_chantier_de_la_societe(
        company, actif_flotte_id=actif_flotte_id,
        installation_id=installation_id, date_debut=date_debut,
        date_fin=date_fin)

    par_chantier = {}
    distance_totale = 0.0
    nb_trajets = 0
    for trajet in trajets:
        nb_trajets += 1
        distance = trajet.distance_calculee_km or 0
        distance = float(distance)
        distance_totale += distance
        cle = trajet.installation_id
        bloc = par_chantier.setdefault(
            cle, {'installation_id': cle, 'nb_trajets': 0,
                  'distance_km': 0.0})
        bloc['nb_trajets'] += 1
        bloc['distance_km'] += distance

    # Résolution best-effort du libellé de chantier via le sélecteur d'installations.
    from apps.installations.selectors import installation_scoped
    lignes = []
    for cle, bloc in par_chantier.items():
        reference = None
        if cle is not None:
            chantier = installation_scoped(company, cle)
            reference = getattr(chantier, 'reference', None) \
                if chantier is not None else None
        lignes.append({
            'installation_id': cle,
            'chantier_reference': reference,
            'nb_trajets': bloc['nb_trajets'],
            'distance_km': round(bloc['distance_km'], 2),
        })
    # Tri stable : chantiers imputés d'abord (id croissant), non imputé en fin.
    lignes.sort(key=lambda ligne: (ligne['installation_id'] is None,
                                   ligne['installation_id'] or 0))

    return {
        'nb_trajets': nb_trajets,
        'distance_totale_km': round(distance_totale, 2),
        'par_chantier': lignes,
    }


# ── FLOTTE30 — Amortissement (lien immobilisations comptables) ─────────────────

def amortissement_vehicule(company, vehicule_id):
    """FLOTTE30 — Amortissement (VNC) d'un véhicule via son immobilisation.

    LECTURE cross-app du module comptable : pour un véhicule de la société, lit
    son immobilisation comptable liée (``Vehicule.immobilisation`` →
    ``compta.Immobilisation``, FK par chaîne) et résume son amortissement
    (valeur d'origine, cumul des dotations, valeur nette comptable). La flotte
    n'écrit JAMAIS le module comptable ; elle lit les attributs du plan
    d'amortissement / des dotations existants (reverse-relations).

    Retourne un dict LECTURE SEULE ::

        {
          'vehicule_id', 'immobilisation_id',
          'valeur_origine', 'cumul_amortissements', 'valeur_nette_comptable',
          'derniere_annee', 'amortissable',
        }

    ``amortissable`` est ``False`` (et les montants ``None``) quand le véhicule
    n'est rattaché à aucune immobilisation. Tous les montants sont des
    ``float`` arrondis. Aucune écriture, aucun effet de bord.
    """
    vehicule = (Vehicule.objects
                .filter(company=company, id=vehicule_id)
                .select_related('immobilisation')
                .first())
    if vehicule is None or vehicule.immobilisation_id is None:
        return {
            'vehicule_id': vehicule_id,
            'immobilisation_id': None,
            'valeur_origine': None,
            'cumul_amortissements': None,
            'valeur_nette_comptable': None,
            'derniere_annee': None,
            'amortissable': False,
        }

    immo = vehicule.immobilisation
    valeur_origine = float(immo.cout or 0)
    cumul = 0.0
    vnc = valeur_origine
    derniere_annee = None
    # Dernière dotation (cumul + VNC déjà calculés par le module compta).
    plan = getattr(immo, 'plan_amortissement', None)
    if plan is not None:
        derniere = plan.dotations.order_by('-annee').first()
        if derniere is not None:
            cumul = float(derniere.cumul or 0)
            vnc = float(derniere.valeur_nette or 0)
            derniere_annee = derniere.annee

    return {
        'vehicule_id': vehicule_id,
        'immobilisation_id': immo.id,
        'valeur_origine': round(valeur_origine, 2),
        'cumul_amortissements': round(cumul, 2),
        'valeur_nette_comptable': round(vnc, 2),
        'derniere_annee': derniere_annee,
        'amortissable': True,
    }


# ── XFLT9 — Plafond CGI d'amortissement des véhicules de tourisme ──────────────

def part_non_deductible_amortissement(company, vehicule_id):
    """XFLT9 — Part d'amortissement NON déductible fiscalement (plafond CGI)
    (lecture seule).

    Pour un véhicule ``type_fiscal='tourisme'`` (XFLT4) rattaché à une
    ``compta.Immobilisation`` (FLOTTE30, via ``amortissement_vehicule``) :
    quand la valeur d'acquisition TTC dépasse le plafond CGI de la société
    (``ParametreAmortissementCGI``, défaut 400 000 DH TTC, LF 2025), la part
    de l'amortissement CUMULÉ correspondant à l'excédent n'est pas déductible
    fiscalement — ``part_non_deductible = cumul_amortissements ×
    (valeur_origine − plafond) / valeur_origine``.

    Les véhicules ``type_fiscal='utilitaire'`` (ou sans type fiscal renseigné)
    sont EXONÉRÉS du plafond → ``part_non_deductible = 0``. Un véhicule sans
    immobilisation liée (``amortissable=False``) renvoie aussi 0. La flotte
    LIT compta par sélecteurs (``amortissement_vehicule``) — elle n'écrit
    JAMAIS le module comptable.

    Retourne un dict LECTURE SEULE ::

        {
          'vehicule_id', 'type_fiscal', 'plafond_ttc',
          'valeur_origine', 'cumul_amortissements', 'part_non_deductible',
          'assujetti',   # True si le plafond s'applique (tourisme + amortissable)
        }

    Aucune écriture, aucun effet de bord.
    """
    vehicule = Vehicule.objects.filter(
        company=company, id=vehicule_id).first()
    type_fiscal = getattr(vehicule, 'type_fiscal', '') or ''
    plafond = ParametreAmortissementCGI.plafond_pour(company)

    amort = amortissement_vehicule(company, vehicule_id)
    valeur_origine = amort.get('valeur_origine') or 0.0
    cumul = amort.get('cumul_amortissements') or 0.0

    assujetti = (
        vehicule is not None
        and type_fiscal == Vehicule.TypeFiscal.TOURISME
        and amort.get('amortissable')
    )

    part_non_deductible = 0.0
    if assujetti and valeur_origine > plafond and valeur_origine > 0:
        part_non_deductible = round(
            cumul * (valeur_origine - plafond) / valeur_origine, 2)

    return {
        'vehicule_id': vehicule_id,
        'type_fiscal': type_fiscal,
        'plafond_ttc': plafond,
        'valeur_origine': valeur_origine,
        'cumul_amortissements': cumul,
        'part_non_deductible': part_non_deductible,
        'assujetti': bool(assujetti),
    }


# ── FLOTTE31 — Coût total de possession (TCO) par véhicule ─────────────────────

def tco_vehicule(company, vehicule_id):
    """FLOTTE31 — Coût total de possession (TCO) d'un véhicule (lecture seule).

    Agrège, pour un véhicule de la société, l'ensemble des coûts INTERNES déjà
    saisis dans le module flotte :

    * ``carburant``     — Σ ``PleinCarburant.prix_total`` (FLOTTE12) ;
    * ``reparations``   — Σ coûts des ``OrdreReparation`` de l'actif (FLOTTE17) ;
    * ``pneus_pieces``  — Σ coûts pneus + pièces du véhicule (FLOTTE18) ;
    * ``infractions``   — Σ ``Infraction.montant_amende`` de l'actif (FLOTTE26) ;
    * ``sinistres``     — Σ ``Sinistre.franchise`` à charge de l'actif (FLOTTE25).

    Le ``cout_total`` somme ces postes. ``amortissement`` (cumul des dotations
    via FLOTTE30) est rapporté à titre INDICATIF mais N'EST PAS sommé au total
    (il chevauche la valeur d'acquisition, pas une dépense d'exploitation
    récurrente). Retourne un dict LECTURE SEULE ::

        {
          'vehicule_id', 'actif_flotte_id',
          'carburant', 'reparations', 'pneus_pieces', 'assurances',
          'infractions', 'sinistres', 'cout_total',
          'amortissement_cumule',  # indicatif, hors total
          'distance_totale_km', 'cout_par_km',  # None si distance nulle
        }

    Tous les montants sont des ``float`` arrondis. Aucune écriture.
    """
    vehicule = (Vehicule.objects
                .filter(company=company, id=vehicule_id)
                .select_related('actif_flotte')
                .first())
    actif_flotte_id = None
    if vehicule is not None:
        actif_flotte_id = getattr(
            getattr(vehicule, 'actif_flotte', None), 'id', None)

    # Carburant (par véhicule).
    carburant = float(
        PleinCarburant.objects
        .filter(company=company, vehicule_id=vehicule_id)
        .aggregate(s=models.Sum('prix_total'))['s'] or 0)

    # Réparations (par actif).
    reparations = 0.0
    infractions = 0.0
    sinistres = 0.0
    if actif_flotte_id is not None:
        reparations = float(
            OrdreReparation.objects
            .filter(company=company, actif_flotte_id=actif_flotte_id)
            .aggregate(s=models.Sum('cout_total'))['s'] or 0)
        infractions = float(
            Infraction.objects
            .filter(company=company, actif_flotte_id=actif_flotte_id)
            .aggregate(s=models.Sum('montant_amende'))['s'] or 0)
        sinistres = float(
            Sinistre.objects
            .filter(company=company, actif_flotte_id=actif_flotte_id)
            .aggregate(s=models.Sum('franchise'))['s'] or 0)

    # Pneus + pièces (par véhicule) — réutilise la synthèse FLOTTE18.
    synth = synthese_pneus_pieces_vehicule(company, vehicule_id)
    pneus_pieces = float(synth.get('cout_total', 0) or 0)

    cout_total = (carburant + reparations + pneus_pieces
                  + infractions + sinistres)

    # Distance totale (carnet de carburant, math FLOTTE13).
    conso = consommation_vehicule(company, vehicule_id)
    distance = conso.get('distance_totale_km', 0) or 0
    cout_par_km = round(cout_total / distance, 3) if distance > 0 else None

    amort = amortissement_vehicule(company, vehicule_id)

    return {
        'vehicule_id': vehicule_id,
        'actif_flotte_id': actif_flotte_id,
        'carburant': round(carburant, 2),
        'reparations': round(reparations, 2),
        'pneus_pieces': round(pneus_pieces, 2),
        'infractions': round(infractions, 2),
        'sinistres': round(sinistres, 2),
        'cout_total': round(cout_total, 2),
        'amortissement_cumule': amort.get('cumul_amortissements'),
        'distance_totale_km': distance,
        'cout_par_km': cout_par_km,
    }


# ── FLOTTE33 — Éco-conduite & CO₂ ──────────────────────────────────────────────

# Facteurs d'émission de CO₂ (kg de CO₂ par litre de carburant brûlé). Valeurs
# usuelles « tank-to-wheel » : Diesel ~2,68 kg/L, Essence ~2,31 kg/L. L'électrique
# n'émet pas directement (émission tank-to-wheel nulle ; l'amont réseau n'est pas
# compté ici). Référentiel figé côté code, modifiable au besoin.
CO2_KG_PAR_LITRE = {
    Vehicule.Energie.DIESEL: 2.68,
    Vehicule.Energie.ESSENCE: 2.31,
    Vehicule.Energie.HYBRIDE: 2.31,
    Vehicule.Energie.ELECTRIQUE: 0.0,
}


def eco_conduite_co2(company, vehicule_id):
    """FLOTTE33 — Éco-conduite & empreinte CO₂ d'un véhicule (lecture seule).

    À partir du carnet de carburant (FLOTTE12/13) et de l'énergie du véhicule,
    calcule :

    * ``litres_total`` / ``kwh_total`` — carburant / électricité consommés ;
    * ``co2_kg`` — émissions tank-to-wheel = litres × facteur d'émission de
      l'énergie (0 pour l'électrique) ;
    * ``conso_l_100km`` / ``conso_kwh_100km`` — consommation moyenne (FLOTTE13) ;
    * ``co2_g_par_km`` — intensité carbone (g CO₂ / km), ou ``None`` sans distance ;
    * ``score_eco`` — score d'éco-conduite 0–100 dérivé du nombre d'anomalies de
      consommation (FLOTTE14) rapportées au nombre de pleins : moins il y a de
      pleins en surconsommation, plus le score est haut (100 = aucune anomalie).

    Retourne un dict LECTURE SEULE. Tous les nombres sont des ``float`` arrondis.
    Aucune écriture, aucun effet de bord.
    """
    vehicule = (Vehicule.objects
                .filter(company=company, id=vehicule_id)
                .first())
    energie = getattr(vehicule, 'energie', None)
    facteur = CO2_KG_PAR_LITRE.get(energie, 0.0)

    conso = consommation_vehicule(company, vehicule_id)
    bloc_litres = conso.get('litres') or {}
    bloc_kwh = conso.get('kwh') or {}
    litres_total = float(bloc_litres.get('quantite', 0) or 0)
    kwh_total = float(bloc_kwh.get('quantite', 0) or 0)
    distance = conso.get('distance_totale_km', 0) or 0

    co2_kg = round(litres_total * facteur, 2)
    co2_g_par_km = round(co2_kg * 1000.0 / distance, 1) if distance > 0 \
        else None

    # Score d'éco-conduite : 100 − (part de pleins en surconsommation × 100).
    nb_pleins = conso.get('nb_pleins', 0) or 0
    anomalies = anomalies_pleins(company, vehicule_id=vehicule_id).get(
        'anomalies', [])
    nb_surconso = sum(
        1 for a in anomalies if a.get('type') == 'conso_aberrante')
    if nb_pleins > 0:
        score_eco = round(max(0.0, 100.0 - (nb_surconso / nb_pleins) * 100.0),
                          1)
    else:
        score_eco = None

    return {
        'vehicule_id': vehicule_id,
        'energie': energie,
        'facteur_co2_kg_par_litre': facteur,
        'litres_total': round(litres_total, 2),
        'kwh_total': round(kwh_total, 2),
        'co2_kg': co2_kg,
        'distance_totale_km': distance,
        'conso_l_100km': bloc_litres.get('conso_l_100km'),
        'conso_kwh_100km': bloc_kwh.get('conso_kwh_100km'),
        'co2_g_par_km': co2_g_par_km,
        'nb_pleins': nb_pleins,
        'nb_surconsommation': nb_surconso,
        'score_eco': score_eco,
    }


# ── FLOTTE34 — Documents véhicule (GED) ────────────────────────────────────────

def documents_ged_pour_actif(company, actif_flotte_id):
    """FLOTTE34 — Documents GED liés à un actif de flotte (lecture seule).

    LECTURE cross-app de la GED : retourne les ``Document`` GED rattachés à un
    ``ActifFlotte`` de la société, à travers
    ``ged.selectors.documents_for_target`` (jamais d'import des modèles GED). Le
    rattachement se fait côté GED via un ``DocumentLien`` (GenericForeignKey)
    pointant l'``ActifFlotte``. Retourne un queryset vide si l'actif n'existe
    pas dans la société ou si la GED n'est pas disponible.

    Lecture seule, scopée société.
    """
    actif = (ActifFlotte.objects
             .filter(company=company, id=actif_flotte_id)
             .first())
    if actif is None:
        return ActifFlotte.objects.none()
    try:
        from apps.ged.selectors import documents_for_target
    except Exception:
        return ActifFlotte.objects.none()
    return documents_for_target(company, actif)


# ── FLOTTE35 — Tableau de bord flotte (dispo / échéances / coûts / conso) ──────

def tableau_bord_flotte(company, today=None):
    """FLOTTE35 — Tableau de bord synthétique de la flotte (lecture seule).

    Agrège pour une société les indicateurs clés du parc :

    * ``vehicules`` — total + ventilation par statut (actif / maintenance /
      réformé) et ``disponibles`` (statut actif) ;
    * ``engins`` — total + ventilation par statut ;
    * ``echeances`` — synthèse du moteur d'alertes réglementaires (FLOTTE24) :
      nombre total + par seau d'urgence (echu / j7 / j15 / j30) ;
    * ``couts`` — coûts de réparation agrégés (FLOTTE17) + carburant total
      (FLOTTE12) de la société ;
    * ``entretien`` — nombre d'échéances d'entretien OUVERTES (FLOTTE16) ;
    * ``pool`` — nombre de demandes de véhicule EN ATTENTE (FLOTTE32).

    ``today`` est INJECTABLE (date du jour par défaut). Tout est scopé société.
    Retourne un dict LECTURE SEULE. Aucune écriture, aucun effet de bord.
    """
    if today is None:
        today = datetime.date.today()

    # Véhicules par statut.
    veh_par_statut = {
        row['statut']: row['n']
        for row in (Vehicule.objects.filter(company=company)
                    .values('statut')
                    .annotate(n=models.Count('id')))
    }
    nb_vehicules = sum(veh_par_statut.values())
    disponibles = veh_par_statut.get(Vehicule.Statut.ACTIF, 0)

    # Engins par statut.
    eng_par_statut = {
        row['statut']: row['n']
        for row in (EnginRoulant.objects.filter(company=company)
                    .values('statut')
                    .annotate(n=models.Count('id')))
    }
    nb_engins = sum(eng_par_statut.values())

    # Échéances réglementaires (moteur d'alertes FLOTTE24).
    alertes = alertes_echeances_reglementaires(company, today=today)

    # Coûts : réparations (FLOTTE17) + carburant total (FLOTTE12).
    couts_rep = couts_reparation(company)
    carburant_total = float(
        PleinCarburant.objects.filter(company=company)
        .aggregate(s=models.Sum('prix_total'))['s'] or 0)

    # Entretien ouvert (FLOTTE16).
    nb_entretien_ouvert = (
        echeances_de_la_societe(company, ouvertes_only=True).count())

    # Pool : demandes en attente (FLOTTE32).
    nb_demandes_attente = DemandeVehicule.objects.filter(
        company=company, statut=DemandeVehicule.Statut.DEMANDEE).count()

    return {
        'today': today,
        'vehicules': {
            'total': nb_vehicules,
            'disponibles': disponibles,
            'par_statut': veh_par_statut,
        },
        'engins': {
            'total': nb_engins,
            'par_statut': eng_par_statut,
        },
        'echeances': {
            'total': alertes['nb_total'],
            'echu': alertes['nb_echu'],
            'j7': alertes['nb_j7'],
            'j15': alertes['nb_j15'],
            'j30': alertes['nb_j30'],
        },
        'couts': {
            'reparations_total': couts_rep['cout_total'],
            'carburant_total': round(carburant_total, 2),
        },
        'entretien': {
            'echeances_ouvertes': nb_entretien_ouvert,
        },
        'pool': {
            'demandes_en_attente': nb_demandes_attente,
        },
    }


# ── FLOTTE32 — Pool de véhicules & demandes ────────────────────────────────────

def demandes_vehicule_de_la_societe(company, statut=None, demandeur_id=None):
    """FLOTTE32 — Demandes de véhicule (pool) d'une société (queryset scopé).

    Filtres facultatifs : ``statut`` (demandee | approuvee | refusee | annulee)
    et ``demandeur_id`` (un demandeur précis). Lecture seule, scopée société, de
    la plus récente à la plus ancienne.
    """
    qs = DemandeVehicule.objects.filter(company=company).select_related(
        'demandeur', 'vehicule_attribue', 'decide_par')
    if statut:
        qs = qs.filter(statut=statut)
    if demandeur_id is not None:
        qs = qs.filter(demandeur_id=demandeur_id)
    return qs


# ── XFLT10 — Périodicité visite technique NARSA auto-calculée ──────────────────

def date_mise_circulation_vehicule(vehicule):
    """XFLT10 — Date de mise en circulation d'un véhicule, lecture seule.

    Lit ``CarteGriseVehicule.date_mise_circulation`` (FLOTTE23) via l'actif
    flotte du véhicule — n'est JAMAIS dupliquée sur ``Vehicule`` (XFLT4).
    Retourne ``None`` si aucune carte grise n'est saisie ou si la date n'est
    pas renseignée. Prend la carte grise la plus récente en cas de multiples
    enregistrements pour le même actif.
    """
    actif = getattr(vehicule, 'actif_flotte', None)
    if actif is None:
        return None
    carte = CarteGriseVehicule.objects.filter(
        actif_flotte=actif, date_mise_circulation__isnull=False,
    ).order_by('-date_mise_circulation', '-id').first()
    if carte is None:
        return None
    return carte.date_mise_circulation
