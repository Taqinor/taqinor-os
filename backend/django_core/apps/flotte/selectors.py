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
    Conducteur,
    EnginRoulant,
    EtatDesLieux,
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
