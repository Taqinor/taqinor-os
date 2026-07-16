"""Services (écritures/orchestration) de l'app FP&A (apps.fpa)."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SoumissionBudgetDepartement


def _get_or_creer_soumission(company, cycle, departement):
    soumission, _ = SoumissionBudgetDepartement.objects.get_or_create(
        company=company, cycle=cycle, departement=departement,
        defaults={'statut': SoumissionBudgetDepartement.Statut.EN_SAISIE},
    )
    return soumission


def soumettre_budget_departement(company, cycle, departement, user):
    """NTFPA5 — soumet le budget d'un département pour un cycle donné.

    Verrouille l'édition (``LigneBudgetDepartement._verifier_non_soumis``)
    jusqu'à décision (validation ou rejet). Refuse si déjà soumis/validé."""
    soumission = _get_or_creer_soumission(company, cycle, departement)
    if soumission.statut in (
            SoumissionBudgetDepartement.Statut.SOUMIS,
            SoumissionBudgetDepartement.Statut.VALIDE):
        raise ValidationError(
            'Ce budget de département est déjà soumis ou validé.')
    soumission.statut = SoumissionBudgetDepartement.Statut.SOUMIS
    soumission.soumis_par = user
    soumission.soumis_le = timezone.now()
    soumission.save(
        update_fields=['statut', 'soumis_par', 'soumis_le'])

    from apps.records.services import log_note
    log_note(
        soumission, user,
        f'Budget soumis pour validation ({departement.nom}, {cycle.nom}).',
        company=company)

    return soumission


def valider_budget_departement(company, cycle, departement, user):
    """NTFPA5 — valide (FP&A/Directeur) un budget de département soumis."""
    soumission = _get_or_creer_soumission(company, cycle, departement)
    if soumission.statut != SoumissionBudgetDepartement.Statut.SOUMIS:
        raise ValidationError(
            "Seul un budget « soumis » peut être validé.")
    soumission.statut = SoumissionBudgetDepartement.Statut.VALIDE
    soumission.valide_par = user
    soumission.valide_le = timezone.now()
    soumission.save(update_fields=['statut', 'valide_par', 'valide_le'])

    from apps.records.services import log_note
    log_note(soumission, user, 'Budget validé.', company=company)

    from apps.audit.recorder import record
    from apps.audit.models import AuditLog
    record(AuditLog.Action.STATUS, instance=soumission, company=company,
           user=user, detail=f'Budget {departement.nom} validé pour {cycle.nom}.')

    return soumission


def rejeter_budget_departement(company, cycle, departement, user, motif=''):
    """NTFPA5 — rejette (FP&A/Directeur) un budget de département soumis.

    Un budget rejeté repasse en saisie (édition rouverte, motif visible au
    responsable via le chatter)."""
    soumission = _get_or_creer_soumission(company, cycle, departement)
    if soumission.statut != SoumissionBudgetDepartement.Statut.SOUMIS:
        raise ValidationError(
            "Seul un budget « soumis » peut être rejeté.")
    soumission.statut = SoumissionBudgetDepartement.Statut.REJETE
    soumission.motif_rejet = motif or ''
    soumission.save(update_fields=['statut', 'motif_rejet'])

    from apps.records.services import log_note
    log_note(
        soumission, user,
        f'Budget rejeté — motif : {motif or "(non précisé)"}', company=company)

    return soumission
