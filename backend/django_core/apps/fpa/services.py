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


def _mois_iterables(mois_debut, mois_fin):
    """Suite de tuples ``(annee, mois)`` de ``mois_debut`` à ``mois_fin``
    inclus (dates au 1er du mois)."""
    a, m = mois_debut.year, mois_debut.month
    fin = (mois_fin.year, mois_fin.month)
    out = []
    while (a, m) <= fin:
        out.append((a, m))
        m += 1
        if m > 12:
            m = 1
            a += 1
    return out


def projeter_masse_salariale(company, departement, mois_debut, mois_fin,
                             hypothese_recrutements=None):
    """NTFPA9 — projection mensuelle de la masse salariale CHARGÉE (charges
    patronales incluses) sur ``[mois_debut, mois_fin]``.

    Combine le référentiel salaires courant (``paie.selectors`` — jamais un
    import de ``paie.models``) + une liste d'hypothèses de recrutement/départ.
    Chaque hypothèse est un dict ``{'salaire_brut_estime', 'date_effet'
    (date), 'type_mouvement' ('embauche'|'depart')}``. Un recrutement s'ajoute
    à partir de son mois d'effet ; un départ se retranche.

    Renvoie une liste ``[{'annee', 'mois', 'masse_salariale_chargee'}]``.
    ``departement`` est accepté pour l'API (segmentation future) mais la base
    salaires courante est company-wide (le référentiel paie n'est pas ventilé
    par département FP&A)."""
    from decimal import Decimal

    from apps.paie import selectors as paie_selectors

    base = paie_selectors.masse_salariale_base_mensuelle(company)
    taux = paie_selectors.taux_charges_patronales(company)
    facteur_charge = Decimal('1') + Decimal(taux)

    hypotheses = list(hypothese_recrutements or [])

    resultat = []
    for annee, mois in _mois_iterables(mois_debut, mois_fin):
        brut = Decimal(base)
        for hyp in hypotheses:
            date_effet = hyp.get('date_effet')
            if date_effet is None:
                continue
            # Actif à partir du mois d'effet inclus.
            if (date_effet.year, date_effet.month) <= (annee, mois):
                montant = Decimal(str(hyp.get('salaire_brut_estime') or 0))
                if hyp.get('type_mouvement') == 'depart':
                    brut -= montant
                else:
                    brut += montant
        chargee = (brut * facteur_charge).quantize(Decimal('0.01'))
        resultat.append({
            'annee': annee, 'mois': mois,
            'masse_salariale_chargee': chargee,
        })
    return resultat


def projeter_revenu_pipeline(company, mois_debut, mois_fin):
    """NTFPA11 — revenu prévisionnel pondéré-probabilité issu du pipeline CRM,
    par mois de clôture prévue. Lit ``crm.selectors`` (jamais ``crm.models``).
    Recalcul à la demande, aucun cache. Renvoie ``{'YYYY-MM': Decimal}``."""
    from apps.crm import selectors as crm_selectors

    return crm_selectors.revenu_pipeline_pondere_par_mois(
        company, mois_debut, mois_fin)


def promouvoir_scenario_en_base(scenario, user):
    """NTFPA17 — promeut un scénario en budget de base : applique ses deltas
    aux lignes RÉELLES du cycle (copie), archive l'ancien scénario de base et
    fige l'audit de la bascule. Réservé FP&A/Directeur (garde côté vue)."""
    from decimal import Decimal

    from .models import (
        LigneBudgetDepartement, ScenarioBudgetaire,
    )

    company = scenario.company
    cycle = scenario.cycle

    # Archive l'ancien scénario de base du cycle (fige-le en archivé).
    ancien = ScenarioBudgetaire.objects.filter(
        company=company, cycle=cycle, est_scenario_base=True
    ).exclude(pk=scenario.pk).first()
    if ancien is not None:
        ancien.est_scenario_base = False
        ancien.statut = ScenarioBudgetaire.Statut.ARCHIVE
        ancien.save(update_fields=['est_scenario_base', 'statut'])

    # Applique les deltas aux lignes réelles (copie in situ, cycle non clos).
    total_par_categorie = {}
    for ligne in LigneBudgetDepartement.objects.filter(company=company, cycle=cycle):
        total_par_categorie.setdefault(ligne.categorie, []).append(ligne)

    for delta in scenario.lignes.all():
        cibles = []
        if delta.ligne_budget_id:
            ligne = LigneBudgetDepartement.objects.filter(
                pk=delta.ligne_budget_id).first()
            if ligne is not None:
                cibles = [ligne]
        elif delta.categorie:
            cibles = total_par_categorie.get(delta.categorie, [])
        for ligne in cibles:
            montant = Decimal(str(ligne.montant_prevu or 0))
            if delta.delta_pct is not None:
                montant += montant * Decimal(str(delta.delta_pct)) / Decimal('100')
            if delta.delta_montant is not None:
                # Delta absolu réparti sur les cibles de la catégorie.
                montant += Decimal(str(delta.delta_montant)) / Decimal(len(cibles))
            ligne.montant_prevu = montant
            ligne.save(update_fields=['montant_prevu'])

    scenario.est_scenario_base = True
    scenario.statut = ScenarioBudgetaire.Statut.ACTIF
    scenario.save(update_fields=['est_scenario_base', 'statut'])

    from apps.audit.recorder import record
    from apps.audit.models import AuditLog
    record(AuditLog.Action.STATUS, instance=scenario, company=company,
           user=user, detail=f'Scénario « {scenario.nom} » promu en budget de base.')
    return scenario


def analyse_sensibilite(company, cycle_id, variable, plage_pct):
    """NTFPA18 — Monte-Carlo simplifié (sensibilité) : fait varier UNE variable
    sur ``[-plage_pct, +plage_pct]`` par pas de 5 % et recalcule le revenu
    prévisionnel total pour chaque pas (via NTFPA11). Stdlib seul, aucune
    dépendance (pas de numpy/scipy).

    Renvoie une liste de dicts ``{'variation_pct', 'revenu_total'}`` (9 points
    pour plage=20)."""
    from decimal import Decimal

    # Revenu prévisionnel de base sur les 12 mois de l'année du cycle.
    from .models import CycleBudgetaire

    cycle = CycleBudgetaire.objects.filter(company=company, pk=cycle_id).first()
    if cycle is None:
        return []
    base = projeter_revenu_pipeline(company, cycle.date_debut, cycle.date_fin)
    revenu_base = sum(base.values(), Decimal('0'))

    points = []
    pas = 5
    variation = -plage_pct
    while variation <= plage_pct:
        facteur = Decimal('1') + Decimal(variation) / Decimal('100')
        points.append({
            'variation_pct': variation,
            'revenu_total': str((revenu_base * facteur).quantize(Decimal('0.01'))),
        })
        variation += pas
    return points
