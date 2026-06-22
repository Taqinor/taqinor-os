"""Services RH (écritures/orchestration) — congés & soldes.

Centralise la LOGIQUE métier testable des congés :

* ``acquisition_mensuelle`` / ``droit_annuel`` — droit à congés payés (Maroc) :
  ~1,5 jour ouvrable par mois de service (18 j/an) + bonus d'ancienneté
  (1,5 j par tranche de 5 ans).
* ``calculer_jours_demande`` — durée décomptée d'une demande (jours ouvrés hors
  fériés/week-end si le type le requiert, sinon jours calendaires).
* ``valider_demande`` / ``refuser_demande`` — transitions du workflow FG163, avec
  mise à jour atomique du compteur ``pris`` du ``SoldeConge`` quand le type
  d'absence déduit le solde.

Tout est cadré société : les fonctions reçoivent des objets déjà scopés par la
vue ; elles ne lisent jamais la société du corps de requête.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import holidays


# Droit légal marocain : 1,5 jour ouvrable acquis par mois de service.
ACQUISITION_PAR_MOIS = Decimal('1.5')
# Bonus d'ancienneté : +1,5 jour par tranche de 5 ans révolus.
BONUS_PAR_TRANCHE = Decimal('1.5')
TRANCHE_ANNEES = 5


def bonus_anciennete(annees_service):
    """Jours de congé supplémentaires liés à l'ancienneté (Maroc).

    +1,5 jour ouvrable par tranche de 5 années de service révolues. ``< 5`` ans
    → 0 ; 5–9 → 1,5 ; 10–14 → 3 ; etc.
    """
    try:
        annees = int(annees_service)
    except (TypeError, ValueError):
        return Decimal('0')
    if annees < TRANCHE_ANNEES:
        return Decimal('0')
    tranches = annees // TRANCHE_ANNEES
    return BONUS_PAR_TRANCHE * tranches


def acquisition_mensuelle(annees_service=0):
    """Jours acquis pour UN mois de service plein (base 1,5 + part ancienneté).

    Le bonus d'ancienneté annuel est réparti sur 12 mois pour rester homogène
    avec une acquisition mois par mois.
    """
    base = ACQUISITION_PAR_MOIS
    part_bonus = bonus_anciennete(annees_service) / Decimal('12')
    return (base + part_bonus).quantize(Decimal('0.01'))


def droit_annuel(annees_service=0):
    """Droit annuel théorique = 12 × base + bonus d'ancienneté.

    12 mois × 1,5 = 18 jours, plus le bonus d'ancienneté de l'année.
    """
    return (ACQUISITION_PAR_MOIS * 12 + bonus_anciennete(annees_service)) \
        .quantize(Decimal('0.01'))


def calculer_jours_demande(type_absence, date_debut, date_fin,
                           extra_holidays=None):
    """Durée décomptée d'une demande de congé (FG163).

    Si ``type_absence.decompte_jours_ouvres`` est vrai, ne compte que les jours
    ouvrés (hors week-end et fériés, cf. ``holidays.working_days`` / FG5) ;
    sinon, compte les jours calendaires. Renvoie un ``Decimal`` (0 si la plage
    est invalide).
    """
    if type_absence is not None and type_absence.decompte_jours_ouvres:
        n = holidays.working_days(date_debut, date_fin, extra_holidays)
    else:
        n = holidays.calendar_days(date_debut, date_fin)
    return Decimal(n)


def _solde_de_lannee(demande):
    """``SoldeConge`` (créé si besoin) de l'employé pour l'année de début."""
    from .models import SoldeConge
    annee = demande.date_debut.year
    solde, _ = SoldeConge.objects.get_or_create(
        company=demande.company, employe=demande.employe, annee=annee)
    return solde


@transaction.atomic
def valider_demande(demande, decide_par=None):
    """Valide une demande SOUMISE et, si le type déduit le solde, met à jour le
    compteur ``pris`` du ``SoldeConge`` de l'année (atomique).

    Idempotent vis-à-vis d'une demande déjà validée : ne re-déduit pas. Lève
    ``ValueError`` si la demande n'est pas dans un état décidable.
    """
    from .models import DemandeConge, SoldeConge
    if demande.statut != DemandeConge.Statut.SOUMISE:
        raise ValueError(
            "Seule une demande soumise peut être validée.")
    # Verrou pessimiste sur le solde pour éviter une double déduction concurrente.
    if demande.type_absence.deduit_solde and demande.jours:
        annee = demande.date_debut.year
        solde, _ = SoldeConge.objects.select_for_update().get_or_create(
            company=demande.company, employe=demande.employe, annee=annee)
        solde.pris = (solde.pris or Decimal('0')) + demande.jours
        solde.save(update_fields=['pris', 'date_modification'])
    demande.statut = DemandeConge.Statut.VALIDEE
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.motif_refus = ''
    demande.save(update_fields=[
        'statut', 'decide_par', 'date_decision', 'motif_refus'])
    return demande


@transaction.atomic
def refuser_demande(demande, decide_par=None, motif_refus=''):
    """Refuse une demande SOUMISE (aucune déduction de solde)."""
    from .models import DemandeConge
    if demande.statut != DemandeConge.Statut.SOUMISE:
        raise ValueError(
            "Seule une demande soumise peut être refusée.")
    demande.statut = DemandeConge.Statut.REFUSEE
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.motif_refus = motif_refus or ''
    demande.save(update_fields=[
        'statut', 'decide_par', 'date_decision', 'motif_refus'])
    return demande


@transaction.atomic
def annuler_demande(demande):
    """Annule une demande. Si elle était VALIDÉE et déduisait le solde, recrédite
    le compteur ``pris`` du ``SoldeConge`` correspondant (atomique)."""
    from .models import DemandeConge, SoldeConge
    if demande.statut == DemandeConge.Statut.VALIDEE \
            and demande.type_absence.deduit_solde and demande.jours:
        annee = demande.date_debut.year
        try:
            solde = SoldeConge.objects.select_for_update().get(
                company=demande.company, employe=demande.employe, annee=annee)
            solde.pris = max(
                Decimal('0'), (solde.pris or Decimal('0')) - demande.jours)
            solde.save(update_fields=['pris', 'date_modification'])
        except SoldeConge.DoesNotExist:
            pass
    demande.statut = DemandeConge.Statut.ANNULEE
    demande.save(update_fields=['statut'])
    return demande
