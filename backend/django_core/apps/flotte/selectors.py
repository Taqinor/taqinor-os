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
    CarteCarburant,
    Conducteur,
    EcheanceEntretien,
    EnginRoulant,
    EtatDesLieux,
    PlanEntretien,
    PleinCarburant,
    ReservationVehicule,
    Vehicule,
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
