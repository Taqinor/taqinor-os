"""Services (écritures/orchestration) de l'app FP&A (apps.fpa)."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import CycleBudgetaire, SoumissionBudgetDepartement


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


def dupliquer_cycle_precedent(company, cycle_source, nouveau_nom):
    """NTFPA7 — copie toutes les ``LigneBudgetDepartement`` d'un cycle
    (typiquement clos) vers un NOUVEAU cycle ``brouillon`` (base de départ
    éditable, jamais un écrasement du cycle source)."""
    from .models import LigneBudgetDepartement

    nouveau = CycleBudgetaire.objects.create(
        company=company, nom=nouveau_nom,
        exercice_comptable_id=cycle_source.exercice_comptable_id,
        date_debut=cycle_source.date_debut, date_fin=cycle_source.date_fin,
        type_cycle=cycle_source.type_cycle,
        statut=CycleBudgetaire.Statut.BROUILLON,
    )
    lignes = LigneBudgetDepartement.objects.filter(
        company=company, cycle=cycle_source)
    LigneBudgetDepartement.objects.bulk_create([
        LigneBudgetDepartement(
            company=company, cycle=nouveau, departement_id=ligne.departement_id,
            categorie=ligne.categorie, mois=ligne.mois,
            montant_prevu=ligne.montant_prevu, commentaire=ligne.commentaire,
        )
        for ligne in lignes
    ])
    return nouveau


def _prefixes_pour_categorie(company, categorie):
    """NTFPA21 — préfixes de compte CGNC couvrant une catégorie FP&A : le
    mapping configuré s'il existe, sinon le repli par défaut."""
    from .models import DEFAULT_COMPTE_CGNC_PREFIXES, MappingCategorieCompte

    mappes = list(
        MappingCategorieCompte.objects
        .filter(company=company, categorie=categorie)
        .values_list('compte_cgnc_prefixe', flat=True))
    if mappes:
        return tuple(mappes)
    return DEFAULT_COMPTE_CGNC_PREFIXES.get(categorie, ())


def generer_prevision_glissante(prevision):
    """NTFPA8 — pré-remplit les mois futurs d'une prévision glissante à partir
    de la moyenne glissante des 3 derniers mois réels (lue via
    ``apps.compta.selectors`` — jamais un import de ``compta.models``).

    Les lignes ``source='manuel'`` déjà saisies ne sont JAMAIS écrasées : une
    régénération mensuelle préserve tous les ajustements humains."""
    from apps.compta.selectors import moyenne_mensuelle_par_prefixes

    from .models import Categorie, LignePrevisionGlissante, SourcePrevision

    company = prevision.company
    existantes_manuelles = set(
        LignePrevisionGlissante.objects
        .filter(prevision=prevision, source=SourcePrevision.MANUEL)
        .values_list('mois_relatif', 'categorie'))

    # Moyenne de référence par catégorie (constante sur l'horizon — un point de
    # départ éditable, pas une projection sophistiquée).
    moyennes = {}
    for categorie, _ in Categorie.choices:
        prefixes = _prefixes_pour_categorie(company, categorie)
        moyennes[categorie] = moyenne_mensuelle_par_prefixes(
            company, prefixes, prevision.date_reference, n_mois=3)

    crees = 0
    for mois_relatif in range(1, prevision.horizon_mois + 1):
        for categorie, _ in Categorie.choices:
            if (mois_relatif, categorie) in existantes_manuelles:
                continue
            LignePrevisionGlissante.objects.update_or_create(
                company=company, prevision=prevision,
                mois_relatif=mois_relatif, categorie=categorie,
                defaults={
                    'montant_prevu': moyennes.get(categorie, 0),
                    'source': SourcePrevision.STATISTIQUE,
                },
            )
            crees += 1
    return crees
