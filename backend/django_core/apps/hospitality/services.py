"""Services (écriture/orchestration) du module Hôtellerie & restauration."""
from .models import PlanTarifaire, Reservation


# ── NTHOT2 — Tarification saisonnière (rack/corporate/ota) ─────────────────

# Priorité par défaut quand aucun canal n'est explicitement demandé (ou que le
# canal demandé n'a pas de plan pour la date) : corporate > ota > rack.
_CANAL_PRIORITE_DEFAUT = [
    PlanTarifaire.Canal.CORPORATE,
    PlanTarifaire.Canal.OTA,
    PlanTarifaire.Canal.RACK,
]


def prix_applicable(type_chambre, date, canal=None):
    """Résout le prix/nuit HT applicable à ``type_chambre`` pour ``date``.

    Plusieurs plans peuvent se chevaucher — jamais ambigu :
    1. si ``canal`` est fourni, un plan EXPLICITE pour ce canal à cette date
       est prioritaire ;
    2. sinon (ou si aucun plan pour ce canal), priorité par défaut
       corporate > ota > rack ;
    3. une date sans plan spécifique retombe naturellement sur le tarif rack
       (un plan rack à large plage de dates joue le rôle de tarif par défaut).

    Renvoie ``None`` si aucun plan ne couvre la date (aucun tarif configuré).
    """
    candidats = PlanTarifaire.objects.filter(
        type_chambre=type_chambre, date_debut__lte=date, date_fin__gte=date)

    if canal:
        exact = candidats.filter(canal=canal).order_by('-date_debut').first()
        if exact is not None:
            return exact.prix_nuit_ht

    for c in _CANAL_PRIORITE_DEFAUT:
        plan = candidats.filter(canal=c).order_by('-date_debut').first()
        if plan is not None:
            return plan.prix_nuit_ht

    return None


# ── NTHOT3 — Réservations (walk-in/téléphone/email) ─────────────────────────

class ReservationOverlapError(ValueError):
    """Levée quand une réservation ``confirmee`` chevauche une autre sur la
    MÊME chambre (validation applicative, jamais une contrainte SQL — deux
    réservations ``annulee``/``en_attente`` peuvent librement se chevaucher)."""


def check_reservation_overlap(
        chambre, date_arrivee, date_depart, *, exclude_id=None):
    """Refuse une réservation ``confirmee`` qui chevaucherait une autre
    réservation ``confirmee`` sur la même chambre. No-op si ``chambre`` est
    ``None`` (réservation sur type de chambre seulement, pas encore assignée).
    """
    if chambre is None:
        return
    qs = Reservation.objects.filter(
        chambre=chambre,
        statut=Reservation.Statut.CONFIRMEE,
        date_arrivee__lt=date_depart,
        date_depart__gt=date_arrivee,
    )
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    if qs.exists():
        raise ReservationOverlapError(
            f'La chambre {chambre.numero} est déjà réservée sur une période '
            'qui chevauche ces dates.')


def resolve_client_reservation(
        company, *, client_id=None, email='', telephone=''):
    """Résout le client d'une réservation — pattern « resolve_client_for_lead »
    (CLAUDE.md) : FK ``crm.Client`` existant (par id explicite, ou retrouvé par
    email/téléphone via ``apps.crm.selectors``, jamais un import de
    ``apps.crm.models``), sinon ``None`` (saisie directe nom/téléphone gérée
    par l'appelant sur les champs ``client_nom``/``client_telephone``).
    """
    if client_id:
        from apps.crm.selectors import get_company_client
        return get_company_client(company, client_id)

    from apps.crm.selectors import find_client_by_email, find_client_by_phone

    if email:
        client = find_client_by_email(email, company=company)
        if client is not None:
            return client
    if telephone:
        client = find_client_by_phone(company, telephone)
        if client is not None:
            return client
    return None


def creer_reservation(
        *, company, user, chambre=None, type_chambre=None,
        date_arrivee, date_depart, nb_adultes=1, nb_enfants=0,
        origine=Reservation.Origine.WALK_IN,
        client_id=None, client_nom='', client_telephone='',
        canal_tarif=None):
    """Crée une réservation avec validation de chevauchement + snapshot prix.

    Lève ``ReservationOverlapError`` (→ 400 côté vue) si la chambre est déjà
    réservée sur une période chevauchante. Le prix/nuit est figé via
    ``prix_applicable`` (NTHOT2) au type de chambre effectif (celui de la
    chambre assignée, sinon ``type_chambre``)."""
    check_reservation_overlap(chambre, date_arrivee, date_depart)

    client = resolve_client_reservation(
        company, client_id=client_id, email='', telephone=client_telephone)

    effective_type = (chambre.type_chambre if chambre else type_chambre)
    prix_snapshot = None
    if effective_type is not None:
        prix_snapshot = prix_applicable(
            effective_type, date_arrivee, canal=canal_tarif)

    return Reservation.objects.create(
        company=company,
        chambre=chambre,
        type_chambre=type_chambre or effective_type,
        origine=origine,
        date_arrivee=date_arrivee,
        date_depart=date_depart,
        nb_adultes=nb_adultes,
        nb_enfants=nb_enfants,
        client=client,
        client_nom=client_nom,
        client_telephone=client_telephone,
        statut=Reservation.Statut.CONFIRMEE,
        prix_nuit_snapshot=prix_snapshot,
        created_by=user,
    )
