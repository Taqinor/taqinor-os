"""Services (écriture/orchestration) du module Hôtellerie & restauration."""
import datetime
from decimal import Decimal

from django.utils import timezone

from .models import (
    Chambre, FicheClient, Folio, LigneFolio, ParametresTaxeSejour,
    PlanTarifaire, Reservation,
)

FICHE_CLIENT_CHAMPS_REQUIS = [
    'nom_complet', 'nationalite', 'type_piece', 'numero_piece',
    'date_naissance',
]


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

    reservation = Reservation.objects.create(
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
    _creer_folio_avec_nuitees(reservation)
    return reservation


# ── NTHOT7 — Folio client unifié (nuitées auto à la création) ──────────────

def _creer_folio_avec_nuitees(reservation):
    """Crée le ``Folio`` de la réservation + UNE ``LigneFolio`` nuitée par
    nuit, selon ``prix_nuit_snapshot`` (figé à la création, NTHOT2/NTHOT3).
    Aucune ligne créée si le prix n'est pas connu (tarif non configuré) —
    le folio reste créé, vide, complétable manuellement."""
    folio = Folio.objects.create(company=reservation.company, reservation=reservation)
    if reservation.prix_nuit_snapshot is None:
        return folio
    nb_nuits = reservation.nb_nuits
    for i in range(nb_nuits):
        nuit = reservation.date_arrivee + datetime.timedelta(days=i)
        LigneFolio.objects.create(
            folio=folio,
            origine=LigneFolio.Origine.NUITEE,
            description=f'Nuitée du {nuit.isoformat()}',
            montant_ht=reservation.prix_nuit_snapshot,
        )
    return folio


class FolioClotureError(ValueError):
    """Levée quand la clôture d'un folio est refusée (déjà soldé, vide, ou
    aucun client CRM résolu pour émettre la facture)."""


def calculer_taxe_sejour(reservation):
    """NTHOT8 — Taxe de séjour due pour ``reservation`` : nb_nuits × nb_adultes
    × montant/nuit/personne (enfants exonérés si le flag société est actif).

    Renvoie ``Decimal('0')`` si aucun paramètre n'est configuré pour la
    société, ou si la taxe est désactivée (``actif=False``)."""
    try:
        params = reservation.company.hospitality_parametres_taxe_sejour
    except ParametresTaxeSejour.DoesNotExist:
        return Decimal('0')
    if not params.actif:
        return Decimal('0')

    nb_personnes = reservation.nb_adultes
    if not params.exoneration_enfants:
        nb_personnes += reservation.nb_enfants

    return (
        Decimal(reservation.nb_nuits) * Decimal(nb_personnes)
        * params.montant_par_nuit_par_personne)


def cloturer_folio(folio, *, user):
    """Clôture UN folio en UNE facture ventes consolidée (jamais de double-
    facturation — refuse un folio déjà ``solde``).

    Ajoute automatiquement la ligne ``taxe_sejour`` (NTHOT8, si configurée et
    active) AVANT facturation, puis passe EXCLUSIVEMENT par
    ``apps.ventes.services`` (function-local, jamais un import de
    ``apps.ventes.models.Facture``) : ``creer_facture_regie`` crée la facture
    BROUILLON, puis ``ajouter_lignes_frais_refactures`` y pousse le détail
    ligne par ligne du folio (recalcule les totaux depuis les lignes)."""
    if folio.statut == Folio.Statut.SOLDE:
        raise FolioClotureError('Ce folio est déjà clôturé.')

    reservation = folio.reservation
    taxe = calculer_taxe_sejour(reservation)
    if taxe > 0 and not folio.lignes.filter(
            origine=LigneFolio.Origine.TAXE_SEJOUR).exists():
        LigneFolio.objects.create(
            folio=folio, origine=LigneFolio.Origine.TAXE_SEJOUR,
            description='Taxe de séjour', montant_ht=taxe, tva=Decimal('0'))

    lignes = list(folio.lignes.all())
    if not lignes:
        raise FolioClotureError('Le folio est vide : aucune ligne à facturer.')
    if reservation.client_id is None:
        raise FolioClotureError(
            "Impossible de clôturer : aucun client CRM résolu sur la "
            "réservation (renseignez un client avant de facturer).")

    from apps.ventes.services import (
        ajouter_lignes_frais_refactures, creer_facture_regie,
    )

    facture = creer_facture_regie(
        company=folio.company,
        client=reservation.client,
        user=user,
        libelle=f'Séjour — réservation #{reservation.pk}',
        montant_ht=Decimal('0'),
    )
    ajouter_lignes_frais_refactures(
        facture=facture,
        lignes=[
            {
                'designation': ligne.description or ligne.get_origine_display(),
                'montant_ht': ligne.montant_ht,
                'taux_tva': ligne.tva,
            }
            for ligne in lignes
        ],
        user=user,
    )

    folio.statut = Folio.Statut.SOLDE
    folio.facture_id = facture.id
    folio.date_cloture = timezone.now()
    folio.save(update_fields=['statut', 'facture_id', 'date_cloture'])
    return facture


# ── NTHOT6 — Check-out et libération de chambre ─────────────────────────────

class CheckOutError(ValueError):
    """Levée quand le check-out est refusé (réservation pas en cours, ou
    solde folio non réglé sans override admin)."""


def check_out(reservation, *, user=None, override=False):
    """Check-out : passe la réservation ``terminee`` et la chambre ``sale``
    (JAMAIS directement ``libre`` — repasse par le housekeeping, NTHOT9).

    Refuse (``CheckOutError``) si le folio n'est pas soldé, SAUF ``override``
    (admin/responsable) — dans ce cas, l'override est journalisé via
    ``apps.audit`` (foundation, exempte de la frontière cross-app)."""
    if reservation.statut != Reservation.Statut.EN_COURS:
        raise CheckOutError(
            "Seule une réservation en cours (check-in effectué) peut faire "
            "l'objet d'un check-out.")

    folio = getattr(reservation, 'folio', None)
    if folio is not None and folio.statut != Folio.Statut.SOLDE:
        if not override:
            raise CheckOutError(
                "Le solde du folio n'est pas réglé — clôturez le folio "
                "(NTHOT7) avant le check-out, ou utilisez l'override admin.")
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record

        record(
            AuditLog.Action.STATUS,
            instance=reservation,
            company=reservation.company,
            user=user,
            detail=(
                f'Check-out forcé (override admin) malgré folio #{folio.pk} '
                'non soldé.'),
        )

    reservation.statut = Reservation.Statut.TERMINEE
    reservation.save(update_fields=['statut'])

    if reservation.chambre_id:
        reservation.chambre.statut = Chambre.Statut.SALE
        reservation.chambre.save(update_fields=['statut'])

    return reservation


# ── NTHOT5 — Check-in avec fiche de police marocaine ────────────────────────

class CheckInError(ValueError):
    """Levée quand le check-in est refusé (fiche client incomplète/absente,
    ou aucune chambre disponible à assigner)."""


def _validate_fiche_data(fiche):
    manquants = [c for c in FICHE_CLIENT_CHAMPS_REQUIS if not fiche.get(c)]
    if manquants:
        raise CheckInError(
            'Fiche client incomplète (champs manquants : '
            f'{", ".join(manquants)}).')


def check_in(reservation, *, fiches_data, user=None):
    """Check-in : passe la réservation ``en_cours``, assigne une chambre si
    besoin (LIBRE du type demandé) et la passe ``occupee``, crée une
    ``FicheClient`` PAR occupant. Refuse (``CheckInError``) si aucune fiche
    n'est fournie ou si une fiche est incomplète — AUCUNE fiche n'est créée
    dans ce cas (tout ou rien)."""
    if not fiches_data:
        raise CheckInError(
            'Au moins une fiche client complète est requise pour le check-in.')
    for fiche in fiches_data:
        _validate_fiche_data(fiche)

    chambre = reservation.chambre
    if chambre is None:
        if reservation.type_chambre is None:
            raise CheckInError(
                'Aucune chambre à assigner : ni chambre ni type de chambre '
                'renseignés sur la réservation.')
        chambre = Chambre.objects.filter(
            company=reservation.company,
            type_chambre=reservation.type_chambre,
            statut=Chambre.Statut.LIBRE,
        ).order_by('numero').first()
        if chambre is None:
            raise CheckInError(
                'Aucune chambre libre du type demandé à assigner.')
        reservation.chambre = chambre

    fiches = [
        FicheClient.objects.create(
            company=reservation.company,
            reservation=reservation,
            **{k: fiche[k] for k in FICHE_CLIENT_CHAMPS_REQUIS},
        )
        for fiche in fiches_data
    ]

    chambre.statut = Chambre.Statut.OCCUPEE
    chambre.save(update_fields=['statut'])
    reservation.statut = Reservation.Statut.EN_COURS
    reservation.save(update_fields=['statut', 'chambre'])
    return fiches
