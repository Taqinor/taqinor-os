"""Services QHSE — orchestration intra-app.

``instancier_plan_chantier`` ouvre un ``PlanInspectionChantier`` à partir d'un
modèle ITP (``PlanInspectionModele``) sur un chantier (référence lâche par id)
et matérialise un ``ReleveControle`` par point de contrôle du modèle. L'opération
est idempotente : ré-appelée pour le même couple (modèle, chantier, société),
elle réutilise le plan existant et n'ajoute que les relevés manquants.
"""
from decimal import Decimal

from django.db import transaction

from .models import (
    AccuseLecture, ActionCorrectivePreventive, AnalyseNcr, Audit,
    AuditPlanifie,
    CampagneRappel, CauseIncident,
    CheckinSecurite, ConformiteEnvironnementale, ControleReception,
    DeclarationCnss, DemandeActionFournisseur, DemandeChangement,
    DemandeChangementCapa,
    Derogation, DiffusionProcedure,
    ElementRappel,
    EtapeDeclarationAt, ExerciceUrgence, LienSignalementPublic, NonConformite,
    NotationFinChantier, ObservationSecurite, PlanControleReception,
    PlanInspectionChantier,
    PointControleModele,
    ProcedureQualite, ReleveThermographie, ReponseCritere, ReleveControle,
    ReunionQhse, RevueVeilleReglementaire, RisqueOpportunite,
    RisqueOpportuniteCapa, SignalementPublic, VeilleReglementaire,
)


@transaction.atomic
def instancier_plan_chantier(modele, chantier_id, company, date_ouverture=None):
    """Crée (ou réutilise) le plan d'inspection d'un chantier et ses relevés.

    * ``modele`` — un ``PlanInspectionModele`` de la même société.
    * ``chantier_id`` — référence lâche au chantier (jamais un import
      ``installations``).
    * ``company`` — la société, posée côté serveur.

    Idempotent : un seul ``PlanInspectionChantier`` par (modèle, chantier,
    société) ; un seul ``ReleveControle`` par point du modèle. Ré-appeler la
    fonction ne duplique rien et complète seulement les relevés manquants
    (utile si le modèle a gagné des points entre-temps).

    Retourne le ``PlanInspectionChantier``.
    """
    if modele.company_id != company.id:
        raise ValueError("Le modèle d'ITP appartient à une autre société.")

    plan, _ = PlanInspectionChantier.objects.get_or_create(
        company=company,
        modele=modele,
        chantier_id=chantier_id,
        defaults={'date_ouverture': date_ouverture},
    )

    existants = set(
        plan.releves.values_list('point_id', flat=True))
    points = PointControleModele.objects.filter(plan=modele)
    a_creer = [
        ReleveControle(company=company, plan_chantier=plan, point=point)
        for point in points
        if point.id not in existants
    ]
    if a_creer:
        ReleveControle.objects.bulk_create(a_creer)

    return plan


# ── QHSE11 — Pont Réserve (installations.Reserve) → NCR ─────────────────────

@transaction.atomic
def creer_ncr_depuis_reserve(reserve_id, company, signale_par=None,
                             gravite=None):
    """Crée une non-conformité (NCR) à partir d'une réserve de chantier.

    Pont cross-app conforme : la ``Reserve`` est lue via le sélecteur LECTURE
    SEULE de ``installations`` (``reserve_scoped`` / ``reserve_resume``) — jamais
    par un import de ``installations.models`` — et la NCR garde un lien lâche
    (FK chaîne ``installations.Reserve``).

    Idempotent : une seule NCR par réserve. Ré-appeler la fonction renvoie la
    NCR existante sans en créer une seconde. Renvoie ``(ncr, created)``.

    Lève ``ValueError`` si la réserve n'existe pas dans la société.
    """
    from apps.installations.selectors import reserve_resume, reserve_scoped

    reserve = reserve_scoped(company, reserve_id)
    if reserve is None:
        raise ValueError("Réserve introuvable dans votre société.")

    existante = NonConformite.objects.filter(
        company=company, reserve_id=reserve.id).first()
    if existante is not None:
        return existante, False

    resume = reserve_resume(reserve)
    description = resume['description']
    titre = (
        f'Réserve · {description[:80]}' if description
        else f'Réserve #{resume["id"]}')
    ncr = NonConformite.objects.create(
        company=company,
        titre=titre,
        description=description,
        origine='Réserve de fin de chantier',
        gravite=gravite or NonConformite.Gravite.MINEURE,
        chantier_id=resume['chantier_id'],
        reserve_id=reserve.id,
        signale_par=signale_par,
    )
    return ncr, True


# ── XMFG13 — Pont Contrôle qualité d'assemblage → NCR ────────────────────────

@transaction.atomic
def creer_ncr_depuis_controle_assemblage(*, company, ordre_id, titre,
                                         description='', gravite=None,
                                         signale_par=None):
    """Crée une non-conformité (NCR) à partir d'un item de checklist QC en
    échec sur un ordre d'assemblage (XMFG13). Écriture FINE, cross-app
    conforme : l'appelant (`installations`) ne fait que passer les données déjà
    résolues (id + titre + description) — jamais d'import du modèle
    `installations.OrdreAssemblage` ici. Lien lâche via FK chaîne
    `ordre_assemblage`. Idempotent : une seule NCR ouverte par (ordre, titre) ;
    ré-appeler renvoie la NCR existante. Renvoie ``(ncr, created)``."""
    existante = NonConformite.objects.filter(
        company=company, ordre_assemblage_id=ordre_id, titre=titre,
        statut__in=[NonConformite.Statut.OUVERTE,
                    NonConformite.Statut.EN_TRAITEMENT]).first()
    if existante is not None:
        return existante, False

    ncr = NonConformite.objects.create(
        company=company,
        titre=titre,
        description=description,
        origine="Contrôle qualité d'assemblage",
        gravite=gravite or NonConformite.Gravite.MINEURE,
        ordre_assemblage_id=ordre_id,
        signale_par=signale_par,
    )
    return ncr, True


# ── QHSE12 — Relances CAPA en retard (notifications / digest) ───────────────

def relancer_capa_en_retard(company, today=None):
    """Relance les CAPA en retard d'une société (notification au responsable).

    Pour chaque CAPA échue et non résolue (cf. ``selectors.capa_en_retard``),
    émet une notification in-app au responsable (best-effort via
    ``notifications.notify`` — jamais d'exception remontée ; une CAPA sans
    responsable est comptée mais non notifiée). Réutilise l'``EventType``
    existant ``MAINTENANCE_DUE`` (échéance interne dépassée) pour rester additif.

    Renvoie un *digest* : ``{'total': N, 'notifiees': M, 'sans_responsable': K,
    'items': [...]}`` où ``items`` résume chaque CAPA en retard (id, description,
    échéance, responsable, jours de retard). Ne mute aucune CAPA.
    """
    from django.utils import timezone

    from apps.qhse.selectors import capa_en_retard

    if today is None:
        today = timezone.localdate()
    retards = list(capa_en_retard(company, today=today))

    notifiees = 0
    sans_responsable = 0
    items = []
    for capa in retards:
        jours = (today - capa.echeance).days
        ncr = capa.non_conformite
        titre = 'CAPA en retard'
        corps = (
            f"L'action « {capa.description[:80]} » liée à la non-conformité "
            f"« {ncr.titre} » est en retard de {jours} jour(s) "
            f"(échéance {capa.echeance.isoformat()}).")
        if capa.responsable_id is not None:
            _notifier_capa(capa.responsable, titre, corps, company)
            notifiees += 1
        else:
            sans_responsable += 1
        items.append({
            'capa_id': capa.id,
            'description': capa.description,
            'echeance': capa.echeance.isoformat(),
            'jours_retard': jours,
            'responsable_id': capa.responsable_id,
            'non_conformite_id': capa.non_conformite_id,
        })

    return {
        'total': len(retards),
        'notifiees': notifiees,
        'sans_responsable': sans_responsable,
        'items': items,
    }


def _notifier_capa(user, titre, corps, company):
    """Notifie un responsable d'une CAPA en retard (best-effort, sans erreur)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/capa', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── QHSE13 — Vérification d'efficacité CAPA (clôture conditionnée) ──────────

@transaction.atomic
def verifier_efficacite_capa(capa, efficace, verifiee_par=None, commentaire=''):
    """Enregistre la vérification d'efficacité d'une CAPA (QHSE13).

    Une CAPA ne peut être vérifiée qu'une fois RÉALISÉE (le traitement est
    terminé, on en mesure l'effet). Selon le verdict :

    * ``efficace=True``  → la CAPA passe au statut ``VERIFIEE`` (elle devient
      clôturable au niveau de la non-conformité) ;
    * ``efficace=False`` → l'action n'a pas réglé l'écart : la CAPA repasse
      ``EN_COURS`` pour relancer le traitement.

    Pose ``efficace`` / ``commentaire_verification`` / ``date_verification`` /
    ``verifiee_par``. Lève ``ValueError`` si la CAPA n'est pas réalisée.
    Renvoie la CAPA.
    """
    from django.utils import timezone

    S = ActionCorrectivePreventive.Statut
    if capa.statut not in (S.REALISEE, S.VERIFIEE):
        raise ValueError(
            "La CAPA doit être réalisée avant la vérification d'efficacité.")

    capa.efficace = bool(efficace)
    capa.commentaire_verification = commentaire or ''
    capa.date_verification = timezone.now()
    capa.verifiee_par = verifiee_par
    capa.statut = S.VERIFIEE if capa.efficace else S.EN_COURS
    capa.save(update_fields=[
        'efficace', 'commentaire_verification', 'date_verification',
        'verifiee_par', 'statut'])
    return capa


# ── QHSE16 — Audit : score + levée de NCR ──────────────────────────────────

@transaction.atomic
def calculer_score_audit(audit):
    """Calcule et stocke le score pondéré d'un ``Audit`` (% conforme, 0–100).

    Seuls les critères avec résultat ``CONFORME`` ou ``NON_CONFORME`` entrent
    dans le calcul (les ``NA`` sont exclus des numérateur ET dénominateur). Si
    aucun critère applicable n'est renseigné, le score reste ``None``.

    Retourne l'``Audit`` avec ``score`` mis à jour et sauvegardé.
    """
    reponses = list(
        audit.qhse_reponses.select_related('critere').all()
    )
    poids_conforme = Decimal('0')
    poids_total = Decimal('0')
    for rep in reponses:
        if rep.resultat == ReponseCritere.Resultat.NA:
            continue
        poids = Decimal(rep.critere.poids)
        poids_total += poids
        if rep.resultat == ReponseCritere.Resultat.CONFORME:
            poids_conforme += poids

    if poids_total == 0:
        audit.score = None
    else:
        audit.score = (poids_conforme / poids_total * 100).quantize(
            Decimal('0.01'))
    audit.save(update_fields=['score'])
    return audit


@transaction.atomic
def lever_ncr_audit(audit, signale_par=None):
    """Lève une ``NonConformite`` pour chaque réponse non conforme de l'audit.

    Idempotent : si une NCR est déjà enregistrée pour une ``ReponseCritere``
    (``ncr_id`` non nul), elle n'est pas dupliquée. Seules les réponses
    ``NON_CONFORME`` sans NCR existante génèrent une nouvelle NCR.

    Retourne un dict ``{'creees': [ncr_id, ...], 'existantes': [ncr_id, ...]}``.
    """
    reponses_nc = list(
        audit.qhse_reponses.filter(
            resultat=ReponseCritere.Resultat.NON_CONFORME
        ).select_related('critere').all()
    )

    creees = []
    existantes = []
    for rep in reponses_nc:
        if rep.ncr_id is not None:
            existantes.append(rep.ncr_id)
            continue
        titre = (
            f'[Audit] {rep.critere.intitule[:120]}'
        )
        description = rep.note or (
            f'Non-conformité détectée lors de l\'audit du '
            f'{audit.date_audit or "date inconnue"} '
            f'sur le critère « {rep.critere.intitule} ».'
        )
        ncr = NonConformite.objects.create(
            company=audit.company,
            titre=titre,
            description=description,
            origine=f'Audit — {audit.grille.nom}',
            gravite=NonConformite.Gravite.MINEURE,
            chantier_id=audit.chantier_id,
            signale_par=signale_par,
        )
        rep.ncr_id = ncr.id
        rep.save(update_fields=['ncr_id'])
        creees.append(ncr.id)

    return {'creees': creees, 'existantes': existantes}


def ncr_capa_bloquantes(ncr):
    """CAPA qui empêchent la clôture d'une non-conformité (QHSE13).

    Une NCR ne peut être clôturée que si CHACUNE de ses CAPA est vérifiée
    efficace (``statut=VERIFIEE`` ET ``efficace=True``). Renvoie la liste des
    CAPA non encore vérifiées efficaces. Lecture seule.
    """
    S = ActionCorrectivePreventive.Statut
    return [
        capa for capa in ncr.actions.all()
        if not (capa.statut == S.VERIFIEE and capa.efficace is True)
    ]


@transaction.atomic
def cloturer_ncr(ncr):
    """Clôture une non-conformité — conditionnée à l'efficacité des CAPA (QHSE13).

    La clôture n'est autorisée que si toutes les CAPA de la NCR sont vérifiées
    efficaces (cf. ``ncr_capa_bloquantes``) ; une NCR sans CAPA se clôture
    librement. Lève ``ValueError`` sinon. Idempotent si déjà clôturée. Renvoie
    la NCR.

    Une disposition (XQHS2, ``poser_disposition``) reste facultative pour la
    clôture : elle trace *comment* la non-conformité a été traitée (rebut,
    retouche, retour fournisseur…) mais ne bloque pas la fermeture — ce
    contrat QHSE13 est préexistant et ne doit pas être durci silencieusement.
    """
    if ncr.statut == NonConformite.Statut.CLOTUREE:
        return ncr
    bloquantes = ncr_capa_bloquantes(ncr)
    if bloquantes:
        raise ValueError(
            "Clôture impossible : %d action(s) corrective(s) non vérifiée(s) "
            "efficace(s)." % len(bloquantes))
    ncr.statut = NonConformite.Statut.CLOTUREE
    ncr.save(update_fields=['statut'])
    return ncr


# ── ARC10 — Clôture NCR pilotée par le moteur d'approbation core (FG366/FG369) ─
#
# Pilote domaine du moteur BPM générique de ``core`` : la clôture d'une NCR
# passe par un cycle d'approbation à deux temps (agent QHSE → responsable QHSE)
# instancié à partir du modèle FG369 « cloture_ncr » et attaché à la NCR par
# ``contenttypes`` (aucun import de modèle core→qhse : c'est qhse qui pilote le
# moteur, ``core`` reste fondation). La règle ARC10 : toute NOUVELLE approbation
# multi-étapes passe par ce moteur — plus de mécanisme d'approbation ad hoc.
# ``parametres.ApprovalPolicy`` (FG25) reste le successeur pour la
# configurabilité UI (config), ce moteur l'EXÉCUTION.

WORKFLOW_TEMPLATE_CLOTURE_NCR = 'cloture_ncr'


@transaction.atomic
def demarrer_workflow_cloture_ncr(ncr, *, user=None, now=None):
    """Démarre le cycle d'approbation de clôture d'une NCR sur le moteur core.

    Installe (idempotemment) le modèle FG369 « cloture_ncr » pour la société de
    la NCR, puis instancie une ``WorkflowInstance`` core visant la NCR (cible
    générique via contenttypes). ``company`` est TOUJOURS celle de la NCR (posée
    côté serveur, jamais lue d'un corps). Idempotent : si un cycle est déjà EN
    COURS pour cette NCR, on le renvoie sans en créer un second. Refuse une NCR
    déjà clôturée. Retourne la ``WorkflowInstance``.
    """
    from core import workflow as core_workflow
    from core import workflow_templates as core_templates

    if ncr.statut == NonConformite.Statut.CLOTUREE:
        raise ValueError('La non-conformité est déjà clôturée.')

    company = ncr.company
    existante = core_workflow.instance_en_cours_pour(
        ncr, company, definition_code=WORKFLOW_TEMPLATE_CLOTURE_NCR)
    if existante is not None:
        return existante

    definition, _ = core_templates.installer_modele_workflow(
        company, WORKFLOW_TEMPLATE_CLOTURE_NCR)
    return core_workflow.demarrer_workflow(
        definition, ncr, company, user=user, now=now)


def _instance_cloture_ncr(ncr):
    """Résout la ``WorkflowInstance`` de clôture EN COURS d'une NCR (ou lève)."""
    from core import workflow as core_workflow

    instance = core_workflow.instance_en_cours_pour(
        ncr, ncr.company, definition_code=WORKFLOW_TEMPLATE_CLOTURE_NCR)
    if instance is None:
        raise ValueError(
            "Aucun cycle d'approbation de clôture en cours pour cette "
            "non-conformité.")
    return instance


@transaction.atomic
def approuver_etape_cloture_ncr(ncr, *, user=None, commentaire='', now=None):
    """Approuve l'étape courante du cycle de clôture d'une NCR (moteur core).

    Délègue à ``core.workflow.approuver_etape`` (mêmes garde-fous). Quand la
    DERNIÈRE étape est approuvée (instance terminée), clôture effectivement la
    NCR via ``cloturer_ncr`` (donc la garde d'efficacité CAPA QHSE13 s'applique
    toujours). Retourne ``(instance, ncr)``.
    """
    from core import workflow as core_workflow

    instance = _instance_cloture_ncr(ncr)
    core_workflow.approuver_etape(
        instance, user=user, commentaire=commentaire, now=now)
    instance.refresh_from_db()
    if instance.statut == instance.STATUT_TERMINE:
        cloturer_ncr(ncr)
        ncr.refresh_from_db()
    return instance, ncr


@transaction.atomic
def rejeter_etape_cloture_ncr(ncr, *, user=None, commentaire='', now=None):
    """Rejette l'étape courante : le cycle est stoppé, la NCR reste ouverte.

    Délègue à ``core.workflow.rejeter_etape`` (l'instance passe à ``termine``,
    chaîne arrêtée). La NCR n'est PAS clôturée. Retourne ``(instance, ncr)``.
    """
    from core import workflow as core_workflow

    instance = _instance_cloture_ncr(ncr)
    core_workflow.rejeter_etape(
        instance, user=user, commentaire=commentaire, now=now)
    instance.refresh_from_db()
    return instance, ncr


@transaction.atomic
def escalader_workflow_cloture_ncr(ncr, *, now=None):
    """Escalade l'étape courante EN ATTENTE du cycle de clôture de la NCR.

    Délègue à ``core.workflow.escalader_etape`` sur l'étape active (utile après
    un dépassement SLA). Lève ``ValueError`` si aucune étape n'est en attente.
    Retourne l'étape escaladée.
    """
    from core import workflow as core_workflow

    instance = _instance_cloture_ncr(ncr)
    step = core_workflow.etape_courante_de(instance)
    if step is None:
        raise ValueError("Aucune étape en attente à escalader.")
    return core_workflow.escalader_etape(step, now=now)


# ── XQHS2 — Disposition de la NCR + dérogations ─────────────────────────────

@transaction.atomic
def poser_disposition(
        ncr, disposition, *, disposition_par=None, cout_disposition=None,
        fournisseur=None, creer_capa_retouche=False, capa_description=''):
    """Pose la disposition d'une non-conformité (XQHS2).

    ``disposition_par``/``disposition_le`` sont posés CÔTÉ SERVEUR (jamais lus
    du corps). Si ``disposition == RETOUCHE`` et ``creer_capa_retouche=True``,
    pré-remplit une CAPA corrective liée (mêmes valeurs par défaut que le
    linkage NCR→CAPA existant). Si ``disposition == RETOUR_FOURNISSEUR``, le
    ``fournisseur`` (référence FK-chaîne ``stock.Fournisseur``) est requis et
    posé. Renvoie la NCR mise à jour.
    """
    from django.utils import timezone

    valeurs_valides = {c.value for c in NonConformite.Disposition}
    if disposition not in valeurs_valides:
        raise ValueError(f'Disposition invalide : {disposition!r}')

    ncr.disposition = disposition
    ncr.disposition_par = disposition_par
    ncr.disposition_le = timezone.now()
    if cout_disposition is not None:
        ncr.cout_disposition = cout_disposition
    if disposition == NonConformite.Disposition.RETOUR_FOURNISSEUR:
        ncr.fournisseur = fournisseur
    ncr.save(update_fields=[
        'disposition', 'disposition_par', 'disposition_le',
        'cout_disposition', 'fournisseur'])

    if (disposition == NonConformite.Disposition.RETOUCHE
            and creer_capa_retouche):
        ActionCorrectivePreventive.objects.create(
            company=ncr.company,
            non_conformite=ncr,
            type_action=ActionCorrectivePreventive.Type.CORRECTIVE,
            description=capa_description or (
                f'Retouche suite à disposition NCR « {ncr.titre} »'),
        )
    return ncr


def derogations_a_relancer(company, today=None):
    """Dérogations actives à échéance imminente ou déjà expirées (XQHS2).

    Même logique de préalerte que ``ConformiteEnvironnementale`` (QHSE38) :
    retient les dérogations non clôturées dont ``date_expiration`` tombe dans
    la fenêtre ``prealerte_jours`` (ou déjà passée). Scopé société.
    """
    from datetime import timedelta

    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    qs = Derogation.objects.filter(
        company=company, date_expiration__isnull=False
    ).exclude(statut=Derogation.Statut.CLOTUREE)
    return [
        d for d in qs
        if d.date_expiration <= today + timedelta(days=d.prealerte_jours or 0)
    ]


def relancer_derogations(company, today=None):
    """Relance les dérogations à échéance imminente/dépassée (best-effort)."""
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    derogs = derogations_a_relancer(company, today=today)
    notifiees = 0
    items = []
    for derog in derogs:
        titre = 'Dérogation à échéance'
        corps = (
            f'La dérogation liée à la non-conformité '
            f'« {derog.non_conformite.titre} » expire le '
            f'{derog.date_expiration.isoformat()}.')
        if derog.approbateur_id is not None:
            _notifier_derogation(derog.approbateur, titre, corps, company)
            notifiees += 1
        items.append({
            'derogation_id': derog.id,
            'non_conformite_id': derog.non_conformite_id,
            'date_expiration': derog.date_expiration.isoformat(),
        })
    return {'total': len(derogs), 'notifiees': notifiees, 'items': items}


def _notifier_derogation(user, titre, corps, company):
    """Notifie l'approbateur d'une dérogation à échéance (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/non-conformites', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── QHSE17 — Score de notation fin de chantier ──────────────────────────────

@transaction.atomic
def calculer_score_notation(notation):
    """Calcule et stocke le score pondéré d'une ``NotationFinChantier``.

    Agrège les ``ItemNotation`` conformes (``conforme=True``) pondérés en
    pourcentage du total des items renseignés (``conforme`` non nul). Les items
    dont ``conforme`` est ``None`` (pas encore évalués) sont exclus du calcul
    (identique au comportement NA des audits). Si aucun item n'est renseigné,
    ``score`` reste ``None`` et ``verdict`` reste ``None``.

    Le ``verdict`` (``passe`` / ``echec``) est dérivé automatiquement : score ≥
    ``seuil_passage`` → PASSE, score < seuil_passage → ECHEC.

    Retourne la ``notation`` avec ``score`` et ``verdict`` mis à jour et sauvegardés.
    """
    items = list(notation.items.all())
    poids_conforme = Decimal('0')
    poids_total = Decimal('0')
    for item in items:
        if item.conforme is None:
            continue
        poids = Decimal(item.poids)
        poids_total += poids
        if item.conforme:
            poids_conforme += poids

    if poids_total == 0:
        notation.score = None
        notation.verdict = None
    else:
        notation.score = (poids_conforme / poids_total * 100).quantize(
            Decimal('0.01'))
        seuil = Decimal(notation.seuil_passage)
        notation.verdict = (
            NotationFinChantier.Verdict.PASSE
            if notation.score >= seuil
            else NotationFinChantier.Verdict.ECHEC
        )
    notation.save(update_fields=['score', 'verdict'])
    return notation


# ── QHSE18 — Procédure qualité versionnée (docs qualité GED) ────────────────

@transaction.atomic
def nouvelle_version_procedure(company, reference, titre, *, contenu='',
                               document_id=None, auteur=None,
                               date_application=None):
    """Crée la version SUIVANTE d'une procédure qualité (additif, non destructif).

    La version est calculée côté serveur : ``max(version de la référence) + 1``
    pour ce couple (société, ``reference``), via un ``select_for_update`` qui
    sérialise les créations concurrentes (jamais ``count()+1``). La première
    version d'une référence inédite est la v1. Rien n'est écrasé : chaque appel
    AJOUTE une ligne, préservant l'historique complet (comme
    ``ged.services.add_version``).

    Le ``document_id`` est une référence lâche au document GED (jamais un import
    cross-app de ``ged.models``). La nouvelle version naît en ``brouillon`` ;
    l'entrée en vigueur passe par ``activer_procedure``.

    Renvoie la ``ProcedureQualite`` créée.
    """
    last = (ProcedureQualite.objects
            .select_for_update()
            .filter(company=company, reference=reference)
            .order_by('-version')
            .first())
    next_version = (last.version + 1) if last else 1
    return ProcedureQualite.objects.create(
        company=company,
        reference=reference,
        titre=titre,
        version=next_version,
        statut=ProcedureQualite.Statut.BROUILLON,
        contenu=contenu or '',
        document_id=document_id,
        auteur=auteur,
        date_application=date_application,
    )


@transaction.atomic
def activer_procedure(procedure, date_application=None):
    """Met une version de procédure EN VIGUEUR et rend les autres obsolètes.

    Une seule version d'une référence est ``en_vigueur`` à la fois : cette
    version passe ``EN_VIGUEUR`` et toutes les autres versions de la même
    référence (même société) qui étaient en vigueur deviennent ``OBSOLETE``.
    L'historique reste intact (aucune suppression). Renvoie la ``procedure``.
    """
    from django.utils import timezone

    S = ProcedureQualite.Statut
    (ProcedureQualite.objects
        .filter(company=procedure.company, reference=procedure.reference,
                statut=S.EN_VIGUEUR)
        .exclude(pk=procedure.pk)
        .update(statut=S.OBSOLETE))
    procedure.statut = S.EN_VIGUEUR
    procedure.date_application = date_application or timezone.localdate()
    procedure.save(update_fields=['statut', 'date_application'])
    return procedure


# ── QHSE22 — Gate « document unique requis avant pose » ─────────────────────

# Messages de refus lisibles par motif (rendu côté appelant — p. ex.
# ``installations`` qui GATE la transition vers « pose »).
_DUER_MOTIF_MESSAGES = {
    'aucune_evaluation': (
        "Aucun document unique d'évaluation des risques (DUERP) n'a été créé "
        "pour ce chantier ; il est requis avant la pose."),
    'aucune_validee': (
        "Le document unique d'évaluation des risques (DUERP) du chantier n'est "
        "pas validé ; il doit l'être avant la pose."),
    'validee_sans_lignes': (
        "Le document unique d'évaluation des risques (DUERP) validé ne contient "
        "aucun risque évalué ; au moins une ligne est requise avant la pose."),
}


def exiger_document_unique(company, chantier_id):
    """Exige un document unique validé avant la pose (gate, QHSE22).

    Porte publique pour les autres apps (typiquement ``installations``, qui
    l'appelle pour GATER la transition d'un chantier vers « pose ») : laisse
    passer SI ``selectors.document_unique_valide`` confirme un DUERP ``validee``
    non vide pour le chantier (scopé société), sinon lève une
    ``django.core.exceptions.ValidationError`` au message clair selon le motif
    (aucune évaluation / aucune validée / validée sans lignes).

    Référence LÂCHE au chantier par ``chantier_id`` — aucun import cross-app de
    ``installations`` ici ; l'appelant fournit l'id et capte l'exception. Aucune
    mutation. Retourne le dict de statut (cf. ``document_unique_valide``) en cas
    de succès, ce qui en fait aussi un assertion réutilisable.
    """
    from django.core.exceptions import ValidationError

    from .selectors import document_unique_valide

    statut = document_unique_valide(company, chantier_id)
    if not statut['valide']:
        message = _DUER_MOTIF_MESSAGES.get(
            statut['motif'],
            "Un document unique d'évaluation des risques validé est requis "
            "avant la pose.")
        raise ValidationError(message, code=statut['motif'] or 'duer_requis')
    return statut


# ── QHSE31 — Analyse d'incident (arbre des causes) → CAPA ───────────────────

@transaction.atomic
def generer_capa_depuis_analyse(analyse, *, description=None,
                                type_action=None, responsable=None,
                                echeance=None, cause_racine=None):
    """Génère une CAPA à partir d'une analyse d'incident (QHSE31).

    Mirroir EXACT du linkage NCR → CAPA déjà en place (cf. ``lever_ncr_audit`` /
    ``creer_ncr_depuis_reserve``) : la ``ActionCorrectivePreventive`` existante
    porte un FK NON nul vers ``NonConformite``. On crée donc, à la PREMIÈRE
    génération, une NCR-pont depuis l'``Incident`` de l'analyse (origine
    « Analyse d'incident »), on la rattache à l'analyse (``analyse.non_conformite``)
    puis on crée la CAPA sur cette NCR. Les générations suivantes RÉUTILISENT la
    NCR-pont (jamais de doublon) et ajoutent une CAPA de plus.

    La ``cause_racine`` de la CAPA est, par défaut, le libellé de la cause racine
    de l'arbre (si présente), sinon la synthèse de l'analyse. Renvoie la CAPA
    créée.
    """
    company = analyse.company
    incident = analyse.incident

    ncr = analyse.non_conformite
    if ncr is None:
        titre = f'Analyse incident — {incident.titre}'[:255]
        ncr = NonConformite.objects.create(
            company=company,
            titre=titre,
            description=analyse.synthese or analyse.description or '',
            origine="Analyse d'incident",
            gravite=NonConformite.Gravite.MINEURE,
            chantier_id=incident.chantier_id,
            signale_par=analyse.analyste,
        )
        analyse.non_conformite = ncr
        analyse.save(update_fields=['non_conformite'])

    if cause_racine is None:
        racine = analyse.causes.filter(
            type_cause=CauseIncident.TypeCause.CAUSE_RACINE).first()
        cause_racine = racine.libelle if racine else (analyse.synthese or '')

    capa = ActionCorrectivePreventive.objects.create(
        company=company,
        non_conformite=ncr,
        type_action=(
            type_action or ActionCorrectivePreventive.Type.CORRECTIVE),
        description=description or (
            f"Action corrective suite à l'analyse de l'incident "
            f"« {incident.titre} »."),
        cause_racine=cause_racine or '',
        responsable=responsable,
        echeance=echeance,
    )
    return capa


# ── QHSE33 — Inspection sécurité planifiée → NCR ───────────────────────────

@transaction.atomic
def lever_ncr_inspection(inspection, gravite=None, signale_par=None):
    """Lève une non-conformité (NCR) depuis une inspection sécurité (QHSE33).

    Conditionnée à un résultat NON CONFORME : une inspection conforme ou en
    attente ne lève pas de NCR (``ValueError``). Idempotent : une seule NCR par
    inspection — ré-appelée, elle renvoie ``(ncr, False)``. La NCR garde la
    référence lâche au chantier (``chantier_id``) et reprend les observations
    comme description. ``company``/``signale_par`` posés côté serveur.

    Renvoie ``(ncr, created)``.
    """
    from .models import InspectionSecurite, NonConformite

    if inspection.resultat != InspectionSecurite.Resultat.NON_CONFORME:
        raise ValueError(
            'Seule une inspection NON CONFORME peut lever une NCR.')

    if inspection.ncr_id is not None:
        return inspection.ncr, False

    company = inspection.company
    titre = f'Inspection sécurité — {inspection.titre}'[:255]
    ncr = NonConformite.objects.create(
        company=company,
        titre=titre,
        description=inspection.observations or '',
        origine='Inspection sécurité',
        gravite=gravite or NonConformite.Gravite.MINEURE,
        chantier_id=inspection.chantier_id,
        signale_par=signale_par,
    )
    inspection.ncr = ncr
    inspection.save(update_fields=['ncr'])
    return ncr, True


# ── QHSE38 — Relances des conformités environnementales ────────────────────

def relancer_conformites(company, today=None):
    """Relance les conformités environnementales à renouveler / expirées (QHSE38).

    Pour chaque conformité à relancer (cf. ``selectors.conformites_a_relancer``),
    émet une notification in-app au responsable (best-effort via
    ``notifications.notify`` — jamais d'exception remontée ; une conformité sans
    responsable est comptée mais non notifiée). Réutilise l'``EventType``
    existant ``MAINTENANCE_DUE`` (échéance interne) pour rester additif.

    Renvoie un *digest* : ``{'total': N, 'notifiees': M, 'sans_responsable': K,
    'items': [...]}`` où ``items`` résume chaque conformité (id, intitulé,
    échéance, état recalculé, responsable). Ne mute aucune conformité.
    """
    from django.utils import timezone

    from apps.qhse.selectors import conformites_a_relancer

    if today is None:
        today = timezone.localdate()
    confs = list(conformites_a_relancer(company, today=today))

    notifiees = 0
    sans_responsable = 0
    items = []
    for conf in confs:
        etat = conf.statut_calcule(today)
        echeance = conf.date_expiration
        titre = 'Conformité environnementale à renouveler'
        corps = (
            f"La conformité « {conf.intitule} » "
            f"(échéance {echeance.isoformat() if echeance else '—'}) "
            f"est à l'état « {conf.Statut(etat).label} ».")
        if conf.responsable_id is not None:
            _notifier_conformite(conf.responsable, titre, corps, company)
            notifiees += 1
        else:
            sans_responsable += 1
        items.append({
            'conformite_id': conf.id,
            'intitule': conf.intitule,
            'echeance': echeance.isoformat() if echeance else None,
            'etat': etat,
            'responsable_id': conf.responsable_id,
        })

    return {
        'total': len(confs),
        'notifiees': notifiees,
        'sans_responsable': sans_responsable,
        'items': items,
    }


def _notifier_conformite(user, titre, corps, company):
    """Notifie un responsable d'une conformité à renouveler (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/conformites-environnementales', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── XQHS1 — Chaîne d'étapes légales AT/MP (loi 18-12) ────────────────────────

# Délai par type d'étape, exprimé en HEURES pour rester précis sur le délai de
# 48 h (avis employeur). Les autres délais légaux (5 j) sont donnés en jours
# convertis en heures. Les étapes sans délai légal fixe (suivi ITT, certificat
# de guérison, conciliation) n'ont pas d'échéance calculée automatiquement
# (``echeance=None``) — elles restent pilotables manuellement.
DELAI_HEURES_PAR_ETAPE = {
    EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR: 48,
    EtapeDeclarationAt.TypeEtape.DOSSIER_ASSUREUR: 5 * 24,
    EtapeDeclarationAt.TypeEtape.INFORMATION_INSPECTION: 5 * 24,
    EtapeDeclarationAt.TypeEtape.CERTIFICAT_MEDICAL: 5 * 24,
}

# Étapes systématiquement instanciées à la création d'une déclaration.
ETAPES_STANDARD = [
    EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
    EtapeDeclarationAt.TypeEtape.DOSSIER_ASSUREUR,
    EtapeDeclarationAt.TypeEtape.INFORMATION_INSPECTION,
    EtapeDeclarationAt.TypeEtape.CERTIFICAT_MEDICAL,
    EtapeDeclarationAt.TypeEtape.SUIVI_ITT,
    EtapeDeclarationAt.TypeEtape.CERTIFICAT_GUERISON,
]


@transaction.atomic
def instancier_etapes_at(declaration):
    """Instancie la checklist des étapes légales AT/MP d'une déclaration CNSS.

    Idempotent : réutilise les étapes déjà créées pour cette déclaration (une
    seule par ``type_etape``, contrainte d'unicité) et n'ajoute que celles
    manquantes. L'échéance de chaque étape est calculée côté serveur à partir
    de ``declaration.date_accident`` + son délai légal (cf.
    ``DELAI_HEURES_PAR_ETAPE``) ; les étapes sans délai fixe restent sans
    échéance. La ``conciliation`` n'est instanciée QUE si
    ``conciliation_statut`` n'est pas ``non_requise`` (elle est facultative
    selon le dossier).

    Renvoie la liste des ``EtapeDeclarationAt`` de la déclaration (créées +
    déjà existantes).
    """
    from datetime import datetime, time, timedelta

    from django.utils import timezone

    types_a_creer = list(ETAPES_STANDARD)
    if (declaration.conciliation_statut !=
            DeclarationCnss.ConciliationStatut.NON_REQUISE):
        types_a_creer.append(EtapeDeclarationAt.TypeEtape.CONCILIATION)

    existantes = {
        e.type_etape: e
        for e in declaration.etapes.all()
    }

    base_dt = None
    if declaration.date_accident is not None:
        base_dt = timezone.make_aware(
            datetime.combine(declaration.date_accident, time.min))

    for type_etape in types_a_creer:
        if type_etape in existantes:
            continue
        delai_h = DELAI_HEURES_PAR_ETAPE.get(type_etape)
        echeance = (
            base_dt + timedelta(hours=delai_h)
            if (base_dt is not None and delai_h is not None) else None)
        etape = EtapeDeclarationAt.objects.create(
            company=declaration.company,
            declaration=declaration,
            type_etape=type_etape,
            echeance=echeance,
        )
        existantes[type_etape] = etape

    return list(declaration.etapes.all())


@transaction.atomic
def marquer_etape_faite(etape, fait_le=None):
    """Marque une étape AT/MP comme réalisée (``fait_le`` posé côté serveur)."""
    from django.utils import timezone
    etape.fait_le = fait_le or timezone.now()
    etape.save(update_fields=['fait_le', 'statut'])
    return etape


def relancer_etapes_at_en_retard(company, now=None):
    """Relance (notification) les étapes AT/MP à échéance imminente ou dépassée.

    Réutilise le pattern ``relancer_capa_en_retard``/``relancer_conformites`` :
    best-effort, ne mute aucune étape, renvoie un digest
    ``{'total', 'notifiees', 'items'}``.
    """
    from django.utils import timezone

    from apps.qhse.selectors import etapes_at_a_echeance

    if now is None:
        now = timezone.now()
    etapes = list(etapes_at_a_echeance(company, now=now))

    notifiees = 0
    items = []
    for etape in etapes:
        titre = 'Étape AT/MP à échéance'
        corps = (
            f'« {etape.get_type_etape_display()} » de la déclaration CNSS '
            f'accident#{etape.declaration.accident_travail_id} '
            f'({etape.get_statut_display()}).')
        responsable = getattr(
            etape.declaration.accident_travail, 'employe', None)
        cible = getattr(responsable, 'user', None)
        if cible is not None:
            _notifier_etape_at(cible, titre, corps, company)
            notifiees += 1
        items.append({
            'etape_id': etape.id,
            'type_etape': etape.type_etape,
            'echeance': etape.echeance.isoformat() if etape.echeance else None,
            'statut': etape.statut_calcule(now),
            'declaration_id': etape.declaration_id,
        })

    return {'total': len(etapes), 'notifiees': notifiees, 'items': items}


def _notifier_etape_at(user, titre, corps, company):
    """Notifie un responsable d'une étape AT/MP à échéance (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/declarations-cnss', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── XQHS3 — Contrôle qualité à la réception fournisseur ──────────────────────

def plans_actifs_pour_produit(company, produit_id, categorie_id=None):
    """Plans de contrôle réception ACTIFS couvrant ce produit (ou sa catégorie).

    Un plan peut couvrir un produit précis OU une catégorie entière. Scopé
    société. Lecture seule.
    """
    from django.db.models import Q
    qs = PlanControleReception.objects.filter(company=company, actif=True)
    filtre = Q(produit_id=produit_id)
    if categorie_id is not None:
        filtre |= Q(categorie_id=categorie_id)
    return list(qs.filter(filtre))


@transaction.atomic
def instancier_controles_reception(reception, company):
    """Instancie les ``ControleReception`` déclenchés par une réception
    confirmée (XQHS3), abonné à ``core.events.reception_fournisseur_confirmee``.

    Pour CHAQUE ligne de la réception, résout le produit (et sa catégorie) et
    crée un ``ControleReception`` par plan actif qui le couvre — idempotent
    (contrainte d'unicité société+réception+plan : un second appel pour la même
    réception ne duplique rien).

    ``reception`` est l'instance ``stock.ReceptionFournisseur`` (accédée en
    lecture directe ici car on est dans le récepteur de l'événement qu'elle a
    elle-même émis — pas un import de ``stock.models`` en dehors de ce
    contexte réactif). Renvoie la liste des ``ControleReception`` créés.
    """
    crees = []
    lignes = list(reception.lignes.select_related('produit').all())
    for ligne in lignes:
        produit = ligne.produit
        if produit is None:
            continue
        categorie_id = getattr(produit, 'categorie_id', None)
        plans = plans_actifs_pour_produit(company, produit.id, categorie_id)
        for plan in plans:
            controle, created = ControleReception.objects.get_or_create(
                company=company, reception_id=reception.id, plan=plan,
                defaults={'produit_id': produit.id},
            )
            if created:
                crees.append(controle)
    return crees


@transaction.atomic
def statuer_controle_reception(
        controle, verdict, *, controleur=None, notes=''):
    """Pose le verdict d'un contrôle réception (XQHS3).

    ``controleur``/``date_controle`` posés côté serveur. Un verdict ``refuse``
    crée automatiquement une NCR pré-remplie (pont XQHS3→XQHS2) via
    ``lever_ncr_controle_reception`` — idempotent (ne recrée pas de NCR si une
    est déjà liée). Renvoie le contrôle mis à jour.
    """
    from django.utils import timezone

    valeurs_valides = {c.value for c in ControleReception.Verdict}
    if verdict not in valeurs_valides:
        raise ValueError(f'Verdict invalide : {verdict!r}')

    controle.verdict = verdict
    controle.controleur = controleur
    controle.notes = notes or controle.notes
    controle.date_controle = timezone.now()
    controle.save(update_fields=[
        'verdict', 'controleur', 'notes', 'date_controle'])

    if verdict == ControleReception.Verdict.REFUSE:
        lever_ncr_controle_reception(controle)
    return controle


def lever_ncr_controle_reception(controle):
    """Lève une NCR pré-remplie depuis un contrôle réception refusé (XQHS3).

    Idempotent : si ``controle.non_conformite`` est déjà posée, ne recrée rien.
    """
    if controle.non_conformite_id is not None:
        return controle.non_conformite
    ncr = NonConformite.objects.create(
        company=controle.company,
        titre=f'[Réception] Contrôle refusé — {controle.plan.nom}',
        description=(
            controle.notes or
            f'Contrôle qualité à la réception #{controle.reception_id} '
            f'refusé sur le plan « {controle.plan.nom} ».'),
        origine=f'Contrôle réception — {controle.plan.nom}',
        gravite=NonConformite.Gravite.MAJEURE,
    )
    controle.non_conformite = ncr
    controle.save(update_fields=['non_conformite'])
    return ncr


# ── XFSM14 — Thermographie IR : NCR auto sur sévérité maximale ─────────────

@transaction.atomic
def enregistrer_releve_thermographie(
        *, company, equipement_ref, delta_t=None,
        campagne=ReleveThermographie.Campagne.SUIVI,
        chantier_id=None, attachment_id=None,
        seuil_a_surveiller=None, seuil_intervention=None,
        releve_par=None, note=''):
    """Crée un relevé de thermographie et lève une NCR si sévérité maximale.

    Le classement (``classe_severite``) est dérivé automatiquement du
    ``delta_t`` et des seuils au ``save()``. Une classe ``intervention_requise``
    déclenche la levée d'une NCR liée (idempotent par relevé : chaque relevé ne
    lève sa NCR qu'une fois, gérée par l'appelant qui ne repasse pas par ici sur
    un relevé déjà persisté).
    """
    releve = ReleveThermographie(
        company=company, equipement_ref=equipement_ref, delta_t=delta_t,
        campagne=campagne, chantier_id=chantier_id,
        attachment_id=attachment_id, releve_par=releve_par, note=note,
    )
    if seuil_a_surveiller is not None:
        releve.seuil_a_surveiller = seuil_a_surveiller
    if seuil_intervention is not None:
        releve.seuil_intervention = seuil_intervention
    releve.save()

    if (releve.classe_severite == ReleveThermographie.Severite.INTERVENTION_REQUISE
            and releve.ncr_id is None):
        ncr = NonConformite.objects.create(
            company=company,
            titre=f'[Thermographie IR] {equipement_ref}',
            description=(
                note or
                f'Point chaud détecté (ΔT={delta_t}°C) sur {equipement_ref} — '
                f'intervention requise (IEC 62446-3).'),
            origine='Thermographie IR',
            gravite=NonConformite.Gravite.MAJEURE,
            chantier_id=chantier_id,
        )
        releve.ncr = ncr
        releve.save(update_fields=['ncr'])
    return releve


def comparer_campagnes_thermographie(company, equipement_ref):
    """Compare la dernière ``recette`` (baseline) et le dernier ``suivi`` d'un
    équipement (XFSM14). Renvoie ``{'recette': releve|None, 'suivi': releve|None,
    'delta': Decimal|None}`` — ``delta`` = évolution ΔT entre les deux.
    """
    qs = ReleveThermographie.objects.filter(
        company=company, equipement_ref=equipement_ref)
    recette = qs.filter(
        campagne=ReleveThermographie.Campagne.RECETTE
    ).order_by('-date_releve', '-id').first()
    suivi = qs.filter(
        campagne=ReleveThermographie.Campagne.SUIVI
    ).order_by('-date_releve', '-id').first()
    delta = None
    if recette is not None and suivi is not None \
            and recette.delta_t is not None and suivi.delta_t is not None:
        delta = suivi.delta_t - recette.delta_t
    return {'recette': recette, 'suivi': suivi, 'delta': delta}


# ── XFSM24 — Check-in travailleur isolé avec escalade ───────────────────────

def _notifier_escalade_checkin(checkin):
    """Notifie le responsable + téléphone du site (best-effort, sans erreur)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        # XFSM8 — téléphone du site, si dispo, est intégré dans le corps du
        # message (le canal d'envoi effectif reste `notify`, best-effort).
        responsables = checkin.company.users.filter(
            role_legacy__in=('responsable', 'admin', 'manager'))
        corps = (
            f'{checkin.technicien} — check-out prévu dépassé sur '
            f'{checkin.site_ref or "site"} (intervention '
            f'{checkin.intervention_id or "?"}).')
        for resp in responsables:
            notify(resp, EventType.MAINTENANCE_DUE,
                   'Escalade check-in sécurité', body=corps,
                   link='/qhse/checkins', company=checkin.company)
    except Exception:  # pragma: no cover - défensif
        pass


@transaction.atomic
def escalader_checkins_en_retard(company=None, now=None):
    """Escalade tout check-in dont le check-out prévu est dépassé sans
    check-out réel (XFSM24). Idempotent : un check-in déjà escaladé
    (``escalade_declenchee=True``) n'est jamais re-notifié.

    Renvoie la liste des check-ins escaladés dans cet appel.
    """
    from django.utils import timezone

    if now is None:
        now = timezone.now()
    qs = CheckinSecurite.objects.filter(
        heure_checkout_reelle__isnull=True,
        escalade_declenchee=False,
        heure_checkout_prevue__isnull=False,
    )
    if company is not None:
        qs = qs.filter(company=company)

    escalades = []
    for checkin in qs:
        if checkin.en_retard(now=now):
            checkin.escalade_declenchee = True
            checkin.escalade_le = now
            checkin.save(update_fields=['escalade_declenchee', 'escalade_le'])
            _notifier_escalade_checkin(checkin)
            escalades.append(checkin)
    return escalades


# ── XQHS5 — Campagne de rappel / containment par produit-lot-série ─────────

@transaction.atomic
def peupler_campagne_rappel(campagne):
    """Peuple les ``ElementRappel`` d'une campagne depuis le parc réel.

    Lit le parc UNIQUEMENT via ``sav.selectors.equipements_par_produit``
    (jamais un import de ``apps.sav.models``). Idempotent : ré-appelée, elle
    n'ajoute que les équipements pas encore présents dans la campagne
    (contrainte unique ``(campagne, equipement_id)``).

    Renvoie la liste des ``ElementRappel`` créés dans cet appel.
    """
    from apps.sav.selectors import equipements_par_produit

    equipements = equipements_par_produit(
        campagne.company, campagne.produit_id,
        serie_debut=campagne.serie_debut or None,
        serie_fin=campagne.serie_fin or None,
    )
    existants = set(
        ElementRappel.objects.filter(campagne=campagne)
        .values_list('equipement_id', flat=True)
    )
    crees = []
    for eq in equipements:
        if eq['id'] in existants:
            continue
        element = ElementRappel.objects.create(
            company=campagne.company, campagne=campagne,
            equipement_id=eq['id'], numero_serie=eq.get('numero_serie') or '',
            installation_id=eq.get('installation_id'),
        )
        crees.append(element)
    return crees


def _notifier_element_rappel(element, responsable):
    """Notifie le responsable d'un élément de rappel à traiter (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        corps = (
            f'Campagne « {element.campagne.titre} » — équipement '
            f'{element.numero_serie or element.equipement_id} à traiter.')
        notify(responsable, EventType.MAINTENANCE_DUE,
               'Élément de campagne de rappel', body=corps,
               link='/qhse/campagnes-rappel', company=element.company)
    except Exception:  # pragma: no cover - défensif
        pass


@transaction.atomic
def notifier_elements_rappel(campagne):
    """Notifie le responsable de campagne pour chaque élément ``à_notifier``
    et fait avancer son statut à ``notifie`` (XQHS5).

    Renvoie la liste des ``ElementRappel`` notifiés dans cet appel.
    """
    from django.utils import timezone

    if campagne.responsable_id is None:
        return []
    a_notifier = list(
        campagne.elements.filter(statut=ElementRappel.Statut.A_NOTIFIER))
    now = timezone.now()
    for element in a_notifier:
        _notifier_element_rappel(element, campagne.responsable)
        element.statut = ElementRappel.Statut.NOTIFIE
        element.notifie_le = now
        element.save(update_fields=['statut', 'notifie_le'])
    return a_notifier


@transaction.atomic
def planifier_remplacement_element_rappel(element, *, client, created_by):
    """Crée l'intervention SAV de remplacement pour un élément (XQHS5).

    Passe par ``sav.services.create_corrective_ticket`` (jamais un import de
    modèle SAV). Fait avancer l'élément à ``planifie`` et enregistre
    ``ticket_sav_id`` (référence LÂCHE).
    """
    from apps.sav.services import create_corrective_ticket

    installation = None
    if element.installation_id:
        from apps.installations.models import Installation
        installation = Installation.objects.filter(
            pk=element.installation_id).first()

    ticket = create_corrective_ticket(
        company=element.company, client=client, installation=installation,
        description=(
            f'Remplacement — campagne de rappel « {element.campagne.titre} » '
            f'({element.numero_serie or element.equipement_id}).'),
        created_by=created_by,
    )
    element.ticket_sav_id = ticket.id
    element.statut = ElementRappel.Statut.PLANIFIE
    element.save(update_fields=['ticket_sav_id', 'statut'])
    return element


@transaction.atomic
def cloturer_campagne_rappel(campagne, date_verification_efficacite):
    """Clôture une campagne après vérification d'efficacité (XQHS5).

    N'autorise la clôture que si tous les éléments sont ``remplace`` ou
    ``clos`` (traitement terminé) — sinon lève ``ValueError``.
    """
    en_cours = campagne.elements.exclude(
        statut__in=[ElementRappel.Statut.REMPLACE, ElementRappel.Statut.CLOS]
    ).count()
    if en_cours:
        raise ValueError(
            f'{en_cours} élément(s) non traités — clôture impossible.')
    campagne.statut = CampagneRappel.Statut.CLOTUREE
    campagne.date_verification_efficacite = date_verification_efficacite
    campagne.save(update_fields=['statut', 'date_verification_efficacite'])
    campagne.elements.filter(
        statut=ElementRappel.Statut.REMPLACE
    ).update(statut=ElementRappel.Statut.CLOS)
    return campagne


# ── XQHS6 — SCAR : demande d'action corrective fournisseur ─────────────────

@transaction.atomic
def creer_scar_depuis_ncr(
        ncr, *, echeance_reponse=None, description_defaut=''):
    """Crée une SCAR depuis une NCR d'origine fournisseur (XQHS6).

    Exige que la NCR porte un ``fournisseur`` (disposition retour fournisseur
    ou origine fournisseur) — sinon lève ``ValueError``.
    """
    if ncr.fournisseur_id is None:
        raise ValueError(
            'La NCR ne porte pas de fournisseur — impossible de créer une SCAR.')
    return DemandeActionFournisseur.objects.create(
        company=ncr.company, fournisseur=ncr.fournisseur, ncr_source=ncr,
        description_defaut=description_defaut or ncr.description,
        echeance_reponse=echeance_reponse,
    )


@transaction.atomic
def repondre_scar(scar, *, cause_racine, action, preuve_attachment_ids=None):
    """Enregistre la réponse fournisseur à une SCAR (XQHS6)."""
    from django.utils import timezone

    scar.cause_racine_fournisseur = cause_racine
    scar.action_fournisseur = action
    if preuve_attachment_ids is not None:
        scar.preuve_attachment_ids = list(preuve_attachment_ids)
    scar.statut = DemandeActionFournisseur.Statut.REPONDUE
    scar.date_reponse = timezone.now()
    scar.save(update_fields=[
        'cause_racine_fournisseur', 'action_fournisseur',
        'preuve_attachment_ids', 'statut', 'date_reponse'])
    return scar


@transaction.atomic
def verifier_efficacite_scar(scar, efficace, verifiee_par=None):
    """Vérifie l'efficacité d'une SCAR répondue (XQHS6, pattern QHSE13).

    Une SCAR non encore répondue ne peut être vérifiée — lève ``ValueError``.
    ``efficace=True`` clôt la SCAR ; ``efficace=False`` la laisse ``verifiee``
    (réponse jugée insuffisante, à relancer côté appelant).
    """
    from django.utils import timezone

    if scar.statut == DemandeActionFournisseur.Statut.EMISE:
        raise ValueError('SCAR pas encore répondue — vérification impossible.')
    scar.efficace = efficace
    scar.verifiee_par = verifiee_par
    scar.date_verification = timezone.now()
    scar.statut = (
        DemandeActionFournisseur.Statut.CLOSE if efficace
        else DemandeActionFournisseur.Statut.VERIFIEE)
    scar.save(update_fields=[
        'efficace', 'verifiee_par', 'date_verification', 'statut'])
    return scar


# ── XQHS7 — Analyse structurée 5-Pourquoi / 8D sur NCR ──────────────────────

@transaction.atomic
def enregistrer_analyse_ncr(ncr, *, cinq_pourquoi=None, huit_d=None):
    """Crée ou met à jour l'``AnalyseNcr`` d'une NCR (XQHS7).

    ``cinq_pourquoi`` — liste de ``{'pourquoi': str, 'reponse': str}`` (≤5,
    validé par ``AnalyseNcr.clean()``). ``huit_d`` — dict des disciplines D1-D8
    fourni partiellement (merge sur les clés fournies, les autres disciplines
    existantes sont conservées).
    """
    analyse, _ = AnalyseNcr.objects.get_or_create(
        company=ncr.company, non_conformite=ncr)
    if cinq_pourquoi is not None:
        analyse.cinq_pourquoi = cinq_pourquoi
    if huit_d is not None:
        merged = dict(analyse.huit_d or {})
        merged.update(huit_d)
        analyse.huit_d = merged
    analyse.full_clean()
    analyse.save()
    return analyse


def _analyse_ncr_html(analyse):
    """Construit le HTML de l'export 8D/5-Pourquoi (PDF INTERNE, hors
    ``/proposal`` — jamais de prix d'achat)."""
    ncr = analyse.non_conformite
    pourquoi_rows = ''.join(
        f"<tr><td>Pourquoi {i + 1}</td><td>{item.get('pourquoi', '')}</td>"
        f"<td>{item.get('reponse', '')}</td></tr>"
        for i, item in enumerate(analyse.cinq_pourquoi or [])
    )
    huit_d_rows = ''.join(
        f"<tr><td>{code}</td><td>{(analyse.huit_d or {}).get(code, {}).get('texte', '')}</td>"
        f"<td>{(analyse.huit_d or {}).get(code, {}).get('statut', '')}</td></tr>"
        for code in AnalyseNcr.DISCIPLINES
    )
    capa_rows = ''.join(
        f"<tr><td>{a.get_type_action_display()}</td><td>{a.description}</td>"
        f"<td>{a.get_statut_display()}</td></tr>"
        for a in ncr.actions.all()
    )
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:sans-serif;font-size:10pt;color:#1a1a1a;"
        "margin:1.5cm;line-height:1.4;}"
        "h1{font-size:15pt;border-bottom:2px solid #2b5cab;"
        "padding-bottom:6px;}"
        "h2{font-size:12pt;margin-top:18px;}"
        "table{width:100%;border-collapse:collapse;margin-top:6px;}"
        "td,th{border:1px solid #ccc;padding:4px 6px;text-align:left;}"
        "</style></head><body>"
        f"<h1>Analyse NCR — {ncr.titre}</h1>"
        f"<div>Référence : {ncr.reference or ncr.pk} — Gravité : "
        f"{ncr.get_gravite_display()}</div>"
        "<h2>5-Pourquoi</h2>"
        f"<table><tr><th>#</th><th>Pourquoi</th><th>Réponse</th></tr>"
        f"{pourquoi_rows}</table>"
        "<h2>8D</h2>"
        "<table><tr><th>Discipline</th><th>Texte</th><th>Statut</th></tr>"
        f"{huit_d_rows}</table>"
        "<h2>Actions correctives / préventives liées</h2>"
        "<table><tr><th>Type</th><th>Description</th><th>Statut</th></tr>"
        f"{capa_rows}</table>"
        "</body></html>"
    )


def rendre_analyse_ncr_pdf(analyse):
    """Rend un PDF INTERNE (bytes) de l'analyse 5-Pourquoi/8D d'une NCR
    (XQHS7). Ce N'EST PAS un chemin client-facing — ``/proposal`` reste
    l'unique chemin des PDF de devis (règle CLAUDE.md #4). Import
    ``weasyprint`` FONCTION-LOCAL (lib lourde, chargée à la demande)."""
    import weasyprint  # import local : lib lourde, chargée à la demande

    html_str = _analyse_ncr_html(analyse)
    return weasyprint.HTML(string=html_str).write_pdf()


# ── XQHS8 — Registre des exigences légales toutes thématiques ──────────────

def enregistrer_evaluation_conformite(conformite, resultat, *, date=None):
    """Enregistre l'évaluation périodique d'une exigence légale (XQHS8, ISO
    45001/9001 6.1.3 conformité obligations légales).

    Met à jour ``date_derniere_evaluation``/``resultat_derniere_evaluation``
    sans toucher au ``statut`` déclaré (le statut reste piloté par
    ``statut_calcule`` — l'évaluation est une trace périodique distincte).
    """
    from django.utils import timezone

    conformite.date_derniere_evaluation = date or timezone.localdate()
    conformite.resultat_derniere_evaluation = resultat
    conformite.save(update_fields=[
        'date_derniere_evaluation', 'resultat_derniere_evaluation'])
    return conformite


# ── XQHS26 — Veille réglementaire QHSE Maroc (revue périodique assistée) ────
# Version SOBRE sans dépendance externe : AUCUN scraping (règle CLAUDE.md #5).
# Seule la CADENCE de revue est automatisée ; le contenu des textes suivis est
# saisi manuellement.

def _prochaine_echeance(veille, depuis):
    from datetime import timedelta

    jours = veille.cadence_jours or VeilleReglementaire.CADENCE_JOURS_DEFAUT
    return depuis + timedelta(days=jours)


def initialiser_prochaine_revue(veille, *, today=None):
    """Pose ``date_prochaine_revue`` à la création si absente (première
    échéance = aujourd'hui + cadence). Idempotent : ne touche rien si déjà
    posée."""
    from django.utils import timezone

    if veille.date_prochaine_revue is not None:
        return veille
    today = today or timezone.localdate()
    veille.date_prochaine_revue = _prochaine_echeance(veille, today)
    veille.save(update_fields=['date_prochaine_revue'])
    return veille


def generer_revues_veille_dues(company, *, today=None):
    """Génère les tâches de revue DUES (XQHS26) pour une société.

    Une ``VeilleReglementaire`` dont ``date_prochaine_revue`` est ≤
    aujourd'hui reçoit une ``RevueVeilleReglementaire`` (statut ``a_faire``,
    assignée au ``responsable`` de la veille) — SAUF si une revue ``a_faire``
    est déjà ouverte pour elle (idempotent : n'en crée jamais deux en
    attente). Renvoie la liste des revues créées."""
    from django.utils import timezone

    today = today or timezone.localdate()
    dues = VeilleReglementaire.objects.filter(
        company=company, date_prochaine_revue__lte=today,
    ).exclude(
        revues__conclusion=RevueVeilleReglementaire.Conclusion.A_FAIRE,
    )
    created = []
    for veille in dues:
        revue = RevueVeilleReglementaire.objects.create(
            company=company, veille=veille, date_echeance=today,
        )
        created.append(revue)
    return created


@transaction.atomic
def conclure_revue_veille(
        revue, conclusion, *, impact_evalue='', resume_ia='', date=None):
    """Conclut une revue de veille réglementaire (XQHS26).

    Fixe ``conclusion`` (``applicable``/``non_applicable``), avance
    ``date_prochaine_revue`` du parent depuis la date de revue effective, et
    si ``applicable`` lie/instancie une entrée du registre légal généralisé
    (XQHS8, ``ConformiteEnvironnementale``) — idempotent : réutilise
    ``veille.registre_conformite`` si déjà posé, n'en crée jamais deux."""
    from django.utils import timezone

    if conclusion not in (
            RevueVeilleReglementaire.Conclusion.APPLICABLE,
            RevueVeilleReglementaire.Conclusion.NON_APPLICABLE):
        raise ValueError(
            'conclusion doit être "applicable" ou "non_applicable"')

    date_revue = date or timezone.localdate()
    revue.conclusion = conclusion
    revue.date_revue = date_revue
    revue.impact_evalue = impact_evalue
    revue.resume_ia = resume_ia
    revue.save(update_fields=[
        'conclusion', 'date_revue', 'impact_evalue', 'resume_ia'])

    veille = revue.veille
    veille.date_derniere_revue = date_revue
    veille.date_prochaine_revue = _prochaine_echeance(veille, date_revue)
    update_fields = ['date_derniere_revue', 'date_prochaine_revue']

    if conclusion == RevueVeilleReglementaire.Conclusion.APPLICABLE \
            and veille.registre_conformite_id is None:
        registre = ConformiteEnvironnementale.objects.create(
            company=veille.company,
            intitule=veille.texte_suivi,
            type_conformite=ConformiteEnvironnementale.TypeConformite.AUTRE,
            thematique=ConformiteEnvironnementale.Thematique.AUTRE,
            autorite=veille.source,
            responsable=veille.responsable,
            date_derniere_evaluation=date_revue,
            resultat_derniere_evaluation=impact_evalue,
        )
        veille.registre_conformite = registre
        update_fields.append('registre_conformite')

    veille.save(update_fields=update_fields)
    return revue


# ── XQHS9 — Registre des certifications + audits de certification ──────────

@transaction.atomic
def lever_ncr_audit_certification(audit_certif, signale_par=None):
    """Lève une NCR pour un constat majeur d'audit de certification (XQHS9).

    Idempotent : si ``audit_certif.ncr_id`` est déjà posé, ne recrée rien et
    renvoie la NCR existante. N'agit que si ``constat_majeur=True``.
    """
    if audit_certif.ncr_id is not None:
        return NonConformite.objects.filter(pk=audit_certif.ncr_id).first()
    if not audit_certif.constat_majeur:
        return None

    certif = audit_certif.certification
    ncr = NonConformite.objects.create(
        company=audit_certif.company,
        titre=f'[Audit certification] {certif.get_referentiel_display()}',
        description=audit_certif.constats or (
            f'Constat majeur lors de l\'audit '
            f'{audit_certif.get_type_etape_display()} du '
            f'{audit_certif.date_audit or "date inconnue"}.'),
        origine='Audit de certification',
        gravite=NonConformite.Gravite.MAJEURE,
        signale_par=signale_par,
    )
    audit_certif.ncr_id = ncr.id
    audit_certif.save(update_fields=['ncr_id'])
    return ncr


# ── XQHS10 — Programme d'audit interne annuel ───────────────────────────────

@transaction.atomic
def instancier_audit_planifie(audit_planifie):
    """Instancie l'``Audit`` réel d'un ``AuditPlanifie`` (XQHS10).

    Idempotent : si déjà instancié (``audit_planifie.audit_id`` posé), renvoie
    l'audit existant sans en recréer un. Copie grille/date/auditeur.
    """
    if audit_planifie.audit_id is not None:
        return audit_planifie.audit

    audit = Audit.objects.create(
        company=audit_planifie.company, grille=audit_planifie.grille,
        date_audit=audit_planifie.date_cible,
        auditeur=audit_planifie.auditeur,
    )
    audit_planifie.audit = audit
    audit_planifie.statut = AuditPlanifie.Statut.REALISE
    audit_planifie.save(update_fields=['audit', 'statut'])
    return audit


def _notifier_audit_planifie_retard(audit_planifie):
    """Notifie l'auditeur d'un audit planifié en retard (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        if audit_planifie.auditeur_id is None:
            return
        corps = (
            f'Audit planifié « {audit_planifie.processus_domaine} » — '
            f'date cible {audit_planifie.date_cible} dépassée sans '
            f'réalisation.')
        notify(audit_planifie.auditeur, EventType.MAINTENANCE_DUE,
               'Audit planifié en retard', body=corps,
               link='/qhse/programmes-audit', company=audit_planifie.company)
    except Exception:  # pragma: no cover - défensif
        pass


@transaction.atomic
def relancer_audits_planifies_en_retard(company=None, today=None):
    """Relance les ``AuditPlanifie`` non réalisés dont la date cible est
    dépassée (XQHS10, pattern QHSE12). Fait avancer le statut à
    ``en_retard`` (idempotent : un audit déjà ``en_retard`` n'est pas
    re-notifié à chaque appel, seulement à son premier passage en retard).
    """
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    qs = AuditPlanifie.objects.filter(
        statut=AuditPlanifie.Statut.PLANIFIE, date_cible__lt=today)
    if company is not None:
        qs = qs.filter(company=company)

    relances = []
    for audit_planifie in qs:
        audit_planifie.statut = AuditPlanifie.Statut.EN_RETARD
        audit_planifie.save(update_fields=['statut'])
        _notifier_audit_planifie_retard(audit_planifie)
        relances.append(audit_planifie)
    return relances


# ── XQHS12 — Revue de direction + comité de sécurité et d'hygiène ──────────

@transaction.atomic
def creer_capa_depuis_decision(
        decision, *, description=None, responsable=None, echeance=None):
    """Crée une CAPA liée depuis une ``DecisionReunion`` (XQHS12).

    La CAPA a besoin d'une NCR porteuse (contrainte existante) : crée une NCR
    de convenance « Décision de réunion » d'origine ``ReunionQhse`` — pattern
    déjà utilisé par les autres ponts de l'app (ex. inspection → NCR → CAPA).
    Idempotent : si ``decision.capa_id`` est déjà posé, renvoie la CAPA
    existante sans en recréer une.
    """
    if decision.capa_id is not None:
        return ActionCorrectivePreventive.objects.filter(
            pk=decision.capa_id).first()

    ncr = NonConformite.objects.create(
        company=decision.company,
        titre=f'[Réunion QHSE] {decision.reunion.get_type_reunion_display()}',
        description=decision.texte,
        origine='Décision de réunion QHSE',
        gravite=NonConformite.Gravite.MINEURE,
    )
    capa = ActionCorrectivePreventive.objects.create(
        company=decision.company, non_conformite=ncr,
        description=description or decision.texte,
        responsable=responsable or decision.responsable,
        echeance=echeance,
    )
    decision.capa_id = capa.id
    decision.save(update_fields=['capa_id'])
    return capa


@transaction.atomic
def cloturer_reunion_qhse(reunion):
    """Clôture une ``ReunionQhse`` (XQHS12).

    Pour une ``revue_direction`` : exige la checklist ISO 9.3 complète
    (``checklist_9_3_complete()``) — sinon lève ``ValueError``. Les autres
    types de réunion clôturent sans condition supplémentaire.
    """
    if reunion.type_reunion == ReunionQhse.TypeReunion.REVUE_DIRECTION \
            and not reunion.checklist_9_3_complete():
        raise ValueError(
            'Checklist ISO 9.3 incomplète — clôture de la revue de '
            'direction impossible.')
    reunion.statut = ReunionQhse.Statut.CLOTUREE
    reunion.save(update_fields=['statut'])
    return reunion


def _notifier_csh_relance(company, membres):
    """Notifie les membres du CSH de la prochaine réunion due (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        for membre in membres:
            notify(membre, EventType.MAINTENANCE_DUE,
                   'CSH — réunion trimestrielle due',
                   body='Le comité de sécurité et d\'hygiène doit se réunir '
                        '(cadence trimestrielle Code du travail).',
                   link='/qhse/reunions', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


def csh_relance_due(company, cadence_jours=90, today=None):
    """True si la cadence trimestrielle CSH est dépassée depuis la dernière
    réunion tenue (XQHS12, obligation Code du travail).

    Sans aucune réunion CSH antérieure, considère la relance due (première
    réunion à planifier). Ne mute rien — pur, lu par l'appelant (tâche
    périodique/cockpit) pour décider s'il notifie.
    """
    from datetime import timedelta

    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    derniere = ReunionQhse.objects.filter(
        company=company,
        type_reunion=ReunionQhse.TypeReunion.COMITE_HYGIENE_SECURITE,
        statut__in=[ReunionQhse.Statut.TENUE, ReunionQhse.Statut.CLOTUREE],
    ).order_by('-date_reunion').first()
    if derniere is None or derniere.date_reunion is None:
        return True
    return today >= derniere.date_reunion + timedelta(days=cadence_jours)


# ── XQHS14 — Registre des risques & opportunités SMQ ────────────────────────

@transaction.atomic
def lier_capa_risque_opportunite(risque_opportunite, capa):
    """Lie une CAPA existante à un ``RisqueOpportunite`` (XQHS14).

    Idempotent via la contrainte unique ``(risque_opportunite, capa)`` —
    ré-appelée avec le même couple, ne duplique rien.
    """
    lien, _ = RisqueOpportuniteCapa.objects.get_or_create(
        company=risque_opportunite.company,
        risque_opportunite=risque_opportunite, capa=capa)
    return lien


def _notifier_revue_risque_due(risque_opportunite):
    """Notifie le responsable qu'une revue de risque/opportunité est due
    (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        if risque_opportunite.responsable_id is None:
            return
        notify(risque_opportunite.responsable, EventType.MAINTENANCE_DUE,
               'Revue de risque/opportunité due',
               body=f'{risque_opportunite.description[:120]} — revue due.',
               link='/qhse/risques-opportunites',
               company=risque_opportunite.company)
    except Exception:  # pragma: no cover - défensif
        pass


def risques_opportunites_revue_due(company, today=None):
    """Risques/opportunités dont la revue périodique est due (XQHS14).

    « Due » = ``date_revue`` absente OU dépassée de ``frequence_revue_jours``.
    Pure (ne notifie ni ne mute) — l'appelant décide de la relance.
    """
    from datetime import timedelta

    from django.utils import timezone

    if today is None:
        today = timezone.localdate()

    dus = []
    for ro in RisqueOpportunite.objects.filter(company=company):
        if ro.date_revue is None:
            dus.append(ro)
            continue
        limite = ro.date_revue + timedelta(days=ro.frequence_revue_jours or 180)
        if today >= limite:
            dus.append(ro)
    return dus


# ── XQHS15 — Diffusion & accusé de lecture des procédures qualité ──────────

@transaction.atomic
def diffuser_procedure(procedure, users):
    """Diffuse une version de procédure à une population d'utilisateurs
    (XQHS15). Crée la ``DiffusionProcedure`` et un ``AccuseLecture`` par
    utilisateur cible (idempotent : re-diffuser à un utilisateur déjà ciblé ne
    duplique pas son accusé, via la contrainte unique).

    ``users`` — itérable d'utilisateurs (objets, pas des ids) ; leurs ids sont
    stockés dans ``population_cible`` pour la traçabilité de la cible visée.
    """
    users = list(users)
    diffusion = DiffusionProcedure.objects.create(
        company=procedure.company, procedure=procedure,
        population_cible={'user_ids': [u.id for u in users]},
    )
    for user in users:
        AccuseLecture.objects.get_or_create(
            company=procedure.company, diffusion=diffusion, user=user)
    return diffusion


@transaction.atomic
def accuser_lecture(diffusion, user):
    """Enregistre l'accusé de lecture d'un utilisateur (XQHS15).

    ``lu_le`` est une confirmation datée CÔTÉ SERVEUR (jamais une date reçue
    du client). Idempotent : ré-appelé pour le même (diffusion, user), ne fait
    que confirmer la lecture (ne change pas ``lu_le`` une fois posé — la
    première lecture fait foi).
    """
    from django.utils import timezone

    accuse, _ = AccuseLecture.objects.get_or_create(
        company=diffusion.company, diffusion=diffusion, user=user)
    if accuse.lu_le is None:
        accuse.lu_le = timezone.now()
        accuse.save(update_fields=['lu_le'])
    return accuse


def lectures_en_attente(user):
    """Diffusions non lues d'un utilisateur (XQHS15, endpoint « mes lectures
    en attente »). Renvoie un queryset d'``AccuseLecture`` avec ``lu_le`` nul.
    """
    return AccuseLecture.objects.filter(
        user=user, lu_le__isnull=True).select_related(
            'diffusion', 'diffusion__procedure')


def _notifier_retardataire_lecture(accuse):
    """Notifie un utilisateur en retard de lecture (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        procedure = accuse.diffusion.procedure
        notify(accuse.user, EventType.MAINTENANCE_DUE,
               'Lecture de procédure en attente',
               body=f'Procédure « {procedure.titre} » (v{procedure.version}) '
                    f'à lire et accuser réception.',
               link='/qhse/procedures', company=accuse.company)
    except Exception:  # pragma: no cover - défensif
        pass


def relancer_retardataires_lecture(company=None):
    """Relance TOUS les accusés de lecture en attente (XQHS15, pattern
    QHSE12). Renvoie la liste des ``AccuseLecture`` relancés dans cet appel
    (ne mute rien — la relance est une notification, pas un changement
    d'état).
    """
    qs = AccuseLecture.objects.filter(lu_le__isnull=True)
    if company is not None:
        qs = qs.filter(company=company)

    relances = []
    for accuse in qs.select_related('diffusion__procedure'):
        _notifier_retardataire_lecture(accuse)
        relances.append(accuse)
    return relances


@transaction.atomic
def rediffuser_nouvelle_version(procedure_precedente, procedure_nouvelle):
    """Re-déclenche la diffusion sur la population de la version précédente
    quand une nouvelle version entre en vigueur (XQHS15).

    Reprend les utilisateurs de la dernière ``DiffusionProcedure`` de la
    version précédente et diffuse la nouvelle version aux mêmes utilisateurs
    (nouveaux ``AccuseLecture`` à zéro — la lecture de l'ancienne version ne
    vaut pas pour la nouvelle).
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    derniere = procedure_precedente.diffusions.order_by('-id').first()
    if derniere is None:
        return None
    user_ids = (derniere.population_cible or {}).get('user_ids', [])
    users = list(User.objects.filter(id__in=user_ids))
    if not users:
        return None
    return diffuser_procedure(procedure_nouvelle, users)


# ── XQHS16 — Signalement QR public sans compte (danger/incident chantier) ──

SIGNALEMENT_INTROUVABLE = 'introuvable'
SIGNALEMENT_OK = 'ok'


def resolve_lien_signalement_public(token):
    """Résout un ``LienSignalementPublic`` depuis son jeton (XQHS16).

    JAMAIS de société/chantier lus de la requête publique : tout vient du
    jeton. Un jeton inconnu OU un lien révoqué (``actif=False``) renvoient le
    même statut (pas de fuite entre « inconnu » et « révoqué »).

    Renvoie ``(statut, lien|None)``.
    """
    lien = (LienSignalementPublic.objects
            .filter(token=token, actif=True)
            .select_related('company')
            .first())
    if lien is None:
        return SIGNALEMENT_INTROUVABLE, None
    return SIGNALEMENT_OK, lien


def _notifier_signalement_public(signalement):
    """Notifie le responsable HSE du lien (best-effort, jamais bloquant)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        lien = signalement.lien
        if lien.responsable_hse_id is None:
            return
        notify(lien.responsable_hse, EventType.MAINTENANCE_DUE,
               'Nouveau signalement QR chantier',
               body=f'{signalement.get_type_signalement_display()} signalé '
                    f'via QR public sur le chantier #{lien.chantier_id}.',
               link='/qhse/incidents', company=signalement.company)
    except Exception:  # pragma: no cover - défensif
        pass


@transaction.atomic
def creer_signalement_public(
        lien, *, type_signalement, description,
        photo_url='', nom='', telephone=''):
    """Crée un ``SignalementPublic`` à partir d'un lien tokenisé résolu
    (XQHS16). La société vient TOUJOURS du lien (jamais de la requête). Notifie
    (best-effort) le responsable HSE du lien s'il en porte un."""
    signalement = SignalementPublic.objects.create(
        company=lien.company,
        lien=lien,
        type_signalement=type_signalement,
        description=description,
        photo_url=photo_url or '',
        nom=(nom or '').strip(),
        telephone=(telephone or '').strip(),
    )
    _notifier_signalement_public(signalement)
    return signalement


def generer_qr_signalement(lien, base_url=''):
    """Génère le QR (PNG bytes) du lien de signalement public (XQHS16).

    Réutilise la lib déjà pinnée pour le QR de la cérémonie de signature devis
    (``qrcode``, cf. ``apps.ventes.quote_engine``) — aucune nouvelle
    dépendance. Dégrade proprement (``None``) si la lib est absente : ce n'est
    PAS un chemin bloquant, seulement l'aperçu imprimable."""
    try:
        import qrcode
    except ImportError:  # pragma: no cover - défensif
        return None
    import io

    target = f'{base_url.rstrip("/")}/qhse/signalement/{lien.token}/' \
        if base_url else lien.token
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10, border=2)
    qr.add_data(target)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


# ── XQHS17 — Observations sécurité comportementales (BBS) ──────────────────

@transaction.atomic
def convertir_observation_en_ncr(observation, gravite=None, signale_par=None):
    """Convertit une ``ObservationSecurite`` à risque en NCR (XQHS17).

    Idempotent : une observation déjà convertie renvoie sa NCR existante
    (jamais deux NCR pour la même observation). Lève ``ValueError`` si
    l'observation est de type ``sur`` (rien à corriger)."""
    if observation.type_observation != ObservationSecurite.TypeObservation.A_RISQUE:
        raise ValueError(
            'Seule une observation « à risque » peut être convertie en NCR.')
    if observation.non_conformite_liee_id:
        return observation.non_conformite_liee, False

    ncr = NonConformite.objects.create(
        company=observation.company,
        titre=f'BBS · {observation.get_categorie_display()}',
        description=observation.description,
        origine='Observation sécurité (BBS)',
        gravite=gravite or NonConformite.Gravite.MINEURE,
        chantier_id=observation.chantier_id,
        signale_par=signale_par or observation.observateur,
    )
    observation.non_conformite_liee = ncr
    observation.save(update_fields=['non_conformite_liee'])
    return ncr, True


@transaction.atomic
def convertir_observation_en_capa(
        observation, *, description=None, responsable_id=None, echeance=None):
    """Convertit une ``ObservationSecurite`` à risque en CAPA (XQHS17).

    Crée (ou réutilise) une NCR minimale support — CAPA exige une NCR parente
    — puis y attache la CAPA. Idempotent : une observation déjà convertie
    renvoie sa CAPA existante."""
    if observation.action_liee_id:
        return observation.action_liee, False

    ncr, _created = convertir_observation_en_ncr(observation)

    capa = ActionCorrectivePreventive.objects.create(
        company=observation.company,
        non_conformite=ncr,
        type_action=ActionCorrectivePreventive.Type.PREVENTIVE,
        description=description or (
            f'Action suite observation BBS : {observation.description}'),
        responsable_id=responsable_id,
        echeance=echeance,
    )
    observation.action_liee = capa
    observation.save(update_fields=['action_liee'])
    return capa, True


def compteurs_observations_securite(company, chantier_id=None):
    """Compteurs cockpit BBS (XQHS17) : ratio sûr/à-risque + observations par
    superviseur/mois. Agrégation PURE — aucune mutation. Scopé société."""
    from collections import defaultdict

    qs = ObservationSecurite.objects.filter(company=company)
    if chantier_id is not None:
        qs = qs.filter(chantier_id=chantier_id)

    total = qs.count()
    sures = qs.filter(
        type_observation=ObservationSecurite.TypeObservation.SUR).count()
    a_risque = total - sures
    ratio = round(sures / total * 100, 1) if total else None

    par_superviseur_mois = defaultdict(int)
    for obs in qs.exclude(observateur__isnull=True):
        date_ref = obs.date_observation or obs.date_creation.date()
        cle = (obs.observateur_id, date_ref.strftime('%Y-%m'))
        par_superviseur_mois[cle] += 1

    return {
        'total': total,
        'sures': sures,
        'a_risque': a_risque,
        'ratio_sur_pct': ratio,
        'par_superviseur_mois': [
            {'observateur_id': sup, 'mois': mois, 'count': count}
            for (sup, mois), count in sorted(par_superviseur_mois.items())
        ],
    }


# ── XQHS18 — Exercices d'urgence (drills) rattachés aux plans d'urgence ────

@transaction.atomic
def realiser_exercice_urgence(
        exercice, *, date_realisee=None, duree_evacuation_secondes=None,
        nb_participants=None, participants_libre='', observations=''):
    """Enregistre la réalisation d'un exercice d'urgence (XQHS18).

    Pose le chrono + observations et passe le statut à ``REALISE``. Un
    exercice déjà réalisé/annulé n'est pas re-réalisable (idempotence de
    l'ACTION, pas du modèle — ré-appeler renvoie l'exercice inchangé)."""
    from django.utils import timezone

    if exercice.statut != ExerciceUrgence.Statut.PLANIFIE:
        return exercice

    exercice.date_realisee = date_realisee or timezone.localdate()
    exercice.duree_evacuation_secondes = duree_evacuation_secondes
    exercice.nb_participants = nb_participants
    exercice.participants_libre = participants_libre
    exercice.observations = observations
    exercice.statut = ExerciceUrgence.Statut.REALISE
    exercice.save()
    return exercice


@transaction.atomic
def creer_capa_depuis_ecart_exercice(exercice, *, description=None):
    """Crée une CAPA à partir d'un écart constaté lors d'un exercice
    d'urgence (XQHS18). Idempotent : un exercice déjà lié renvoie sa CAPA
    existante. Exige des ``observations`` non vides (l'écart à corriger)."""
    if exercice.capa_liee_id:
        return exercice.capa_liee, False
    if not (exercice.observations or '').strip():
        raise ValueError(
            "Aucun écart renseigné : l'observation est requise pour créer "
            "une CAPA.")

    ncr = NonConformite.objects.create(
        company=exercice.company,
        titre=f'Écart exercice · {exercice.get_type_exercice_display()}',
        description=exercice.observations,
        origine="Exercice d'urgence",
        gravite=NonConformite.Gravite.MINEURE,
        chantier_id=exercice.plan.chantier_id,
    )
    capa = ActionCorrectivePreventive.objects.create(
        company=exercice.company,
        non_conformite=ncr,
        type_action=ActionCorrectivePreventive.Type.CORRECTIVE,
        description=description or (
            f'Correction écart exercice : {exercice.observations}'),
    )
    exercice.capa_liee = capa
    exercice.save(update_fields=['capa_liee'])
    return capa, True


def plans_exercices_dus(company, today=None):
    """Plans d'urgence dont le prochain exercice est dû (XQHS18, pattern
    QHSE12/QHSE38) : aucun exercice réalisé, OU le dernier exercice réalisé
    remonte à plus de ``frequence_mois``. Agrégation PURE — aucune mutation."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import PlanUrgence

    if today is None:
        today = timezone.localdate()

    dus = []
    for plan in PlanUrgence.objects.filter(company=company):
        dernier = (plan.exercices
                   .filter(statut=ExerciceUrgence.Statut.REALISE)
                   .exclude(date_realisee__isnull=True)
                   .order_by('-date_realisee')
                   .first())
        if dernier is None:
            dus.append(plan)
            continue
        delai = timedelta(days=30 * (plan.frequence_mois or 12))
        if today >= dernier.date_realisee + delai:
            dus.append(plan)
    return dus


def _notifier_exercice_du(plan):
    """Notifie (best-effort) que le prochain exercice d'urgence du plan est
    dû."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        responsable = getattr(plan, 'responsable', None)
        cible = responsable or None
        if cible is None:
            return
        notify(cible, EventType.MAINTENANCE_DUE,
               "Exercice d'urgence dû",
               body=f'Le plan « {plan.titre} » doit programmer son prochain '
                    f'exercice (cadence {plan.frequence_mois} mois).',
               link='/qhse/plans-urgence', company=plan.company)
    except Exception:  # pragma: no cover - défensif
        pass


def relancer_exercices_urgence(company=None):
    """Relance TOUS les plans dont le prochain exercice est dû (XQHS18,
    pattern ``relancer_capa_en_retard``). Ne mute rien — la relance est une
    notification. Renvoie les plans relancés."""
    from .models import PlanUrgence

    if company is not None:
        plans = plans_exercices_dus(company)
    else:
        plans = []
        for co in {p.company for p in PlanUrgence.objects.all()}:
            plans.extend(plans_exercices_dus(co))

    for plan in plans:
        _notifier_exercice_du(plan)
    return plans


# ── XQHS19 — Incidents environnementaux : notification + gate de clôture ──

from .models import Incident  # noqa: E402  (évite un cycle d'import module)


def incidents_notification_en_retard(company, today=None):
    """Incidents environnementaux dont la notification requise est en retard
    (XQHS19, pattern ``conformites_a_relancer``/QHSE38). Agrégation PURE."""
    qs = Incident.objects.filter(
        company=company,
        type_incident=Incident.TypeIncident.ENVIRONNEMENT,
        notification_requise=True,
        date_notification__isnull=True,
        date_limite_notification__isnull=False,
    )
    if today is None:
        from django.utils import timezone
        today = timezone.localdate()
    return [inc for inc in qs if inc.date_limite_notification <= today]


def _notifier_notification_retard(incident):
    """Notifie (best-effort) le retard de notification réglementaire."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        if incident.declare_par_id is None:
            return
        notify(incident.declare_par, EventType.MAINTENANCE_DUE,
               'Notification environnementale en retard',
               body=f'Incident « {incident.titre} » : la notification à '
                    f"l'autorité était due le "
                    f'{incident.date_limite_notification}.',
               link='/qhse/incidents', company=incident.company)
    except Exception:  # pragma: no cover - défensif
        pass


def relancer_notifications_environnement(company=None):
    """Relance TOUS les incidents environnementaux en retard de notification
    (XQHS19, pattern ``relancer_conformites``). Ne mute rien. Renvoie les
    incidents relancés."""
    if company is not None:
        incidents = incidents_notification_en_retard(company)
    else:
        incidents = []
        for co in {i.company for i in Incident.objects.filter(
                type_incident=Incident.TypeIncident.ENVIRONNEMENT)}:
            incidents.extend(incidents_notification_en_retard(co))

    for incident in incidents:
        _notifier_notification_retard(incident)
    return incidents


@transaction.atomic
def cloturer_incident(incident):
    """Clôture un incident — conditionnée à la notification si requise
    (XQHS19, pattern ``cloturer_ncr`` QHSE13). Idempotent si déjà clos.
    Lève ``ValueError`` si la notification requise n'a pas été faite."""
    if incident.statut == Incident.Statut.CLOS:
        return incident
    if not incident.peut_cloturer():
        raise ValueError(
            'Clôture impossible : la notification à l’autorité est requise '
            'et n’a pas encore été enregistrée.')
    incident.statut = Incident.Statut.CLOS
    incident.save(update_fields=['statut'])
    return incident


# ── XQHS21 — Relevés de consommation par site → génération bilan carbone ──

from .models import (  # noqa: E402  (évite un cycle d'import)
    LigneBilanCarbone, ReleveConsommation,
)

# Facteurs d'émission par défaut (tCO2e / unité), GHG Protocol / ADEME
# — mêmes ordres de grandeur que ceux déjà saisis manuellement en QHSE39.
# Servent uniquement de PRÉ-REMPLISSAGE éditable (jamais imposés).
_FACTEUR_ELECTRICITE_MAROC = Decimal('0.000700')   # tCO2e/kWh (mix ONEE)
_FACTEUR_GASOIL = Decimal('0.002680')              # tCO2e/L
_FACTEUR_ESSENCE = Decimal('0.002310')              # tCO2e/L
_FACTEUR_EAU = Decimal('0.000344')                  # tCO2e/m3 (traitement/distrib)


@transaction.atomic
def generer_lignes_bilan(bilan, annee):
    """Agrège les relevés QHSE (sites) + le carburant flotte (véhicules) de
    l'``annee`` en ``LigneBilanCarbone`` pré-remplies (XQHS21).

    Idempotent : une ligne déjà générée pour la même (bilan, libellé, scope)
    n'est PAS dupliquée — la génération met à jour la quantité existante
    plutôt que d'ajouter une ligne (l'utilisateur reste libre d'éditer
    ensuite ; ré-appeler la génération recale sur les relevés à date)."""
    from apps.flotte.selectors import consommation_annuelle_flotte

    releves = ReleveConsommation.objects.filter(
        company=bilan.company, periode__year=annee)

    totaux = {
        ReleveConsommation.TypeEnergie.ELECTRICITE: Decimal('0'),
        ReleveConsommation.TypeEnergie.GASOIL: Decimal('0'),
        ReleveConsommation.TypeEnergie.ESSENCE: Decimal('0'),
        ReleveConsommation.TypeEnergie.EAU: Decimal('0'),
    }
    for releve in releves:
        totaux[releve.type_energie] += releve.quantite or Decimal('0')

    # Carburant FLOTTE (véhicules) — lu via le sélecteur cross-app, jamais
    # re-saisi côté QHSE (note du plan XQHS21).
    conso_flotte = consommation_annuelle_flotte(bilan.company, annee)
    totaux[ReleveConsommation.TypeEnergie.GASOIL] += Decimal(
        str(conso_flotte.get('gasoil_litres', 0)))
    totaux[ReleveConsommation.TypeEnergie.ESSENCE] += Decimal(
        str(conso_flotte.get('essence_litres', 0)))

    plan = [
        (ReleveConsommation.TypeEnergie.ELECTRICITE,
         'Électricité (sites + flotte)', LigneBilanCarbone.Scope.SCOPE_2,
         'kWh', _FACTEUR_ELECTRICITE_MAROC),
        (ReleveConsommation.TypeEnergie.GASOIL,
         'Gasoil (groupes électrogènes + véhicules)',
         LigneBilanCarbone.Scope.SCOPE_1, 'L', _FACTEUR_GASOIL),
        (ReleveConsommation.TypeEnergie.ESSENCE,
         'Essence (groupes électrogènes + véhicules)',
         LigneBilanCarbone.Scope.SCOPE_1, 'L', _FACTEUR_ESSENCE),
        (ReleveConsommation.TypeEnergie.EAU, 'Eau', LigneBilanCarbone.Scope.SCOPE_3,
         'm3', _FACTEUR_EAU),
    ]

    lignes = []
    for type_energie, libelle, scope, unite, facteur in plan:
        quantite = totaux[type_energie]
        if quantite <= 0:
            continue
        ligne, _created = LigneBilanCarbone.objects.update_or_create(
            company=bilan.company, bilan=bilan, libelle=libelle,
            defaults={
                'scope': scope,
                'categorie': type_energie,
                'quantite': quantite,
                'unite': unite,
                'facteur_emission': facteur,
            },
        )
        lignes.append(ligne)
    return lignes


# ── XQHS23 — Pont SAV ↔ NCR (boucle défaillances terrain/garantie) ─────────

@transaction.atomic
def creer_ncr_depuis_ticket(ticket_id, company, signale_par=None, gravite=None):
    """Crée une NCR à partir d'un ticket SAV (XQHS23, pont ticket → NCR).

    Le ticket est lu via le sélecteur LECTURE SEULE
    ``sav.selectors.ticket_scoped`` (jamais un import de ``apps.sav.models``,
    règle de modularité cross-app CLAUDE.md) et rattaché en FK-chaîne
    ``'sav.Ticket'`` nullable (``ticket_sav``, string-FK Django standard).
    Idempotent : une seule NCR par ticket — ré-appeler renvoie la NCR
    existante. Lève ``ValueError`` si le ticket n'existe pas dans la
    société."""
    existante = NonConformite.objects.filter(
        company=company, ticket_sav_id=ticket_id).first()
    if existante is not None:
        return existante, False

    from apps.sav.selectors import ticket_scoped

    ticket = ticket_scoped(company, ticket_id)
    if ticket is None:
        raise ValueError("Ticket SAV introuvable dans votre société.")

    ncr = NonConformite.objects.create(
        company=company,
        titre=f'SAV · {ticket.reference}',
        description=ticket.description or '',
        origine='Ticket SAV',
        gravite=gravite or NonConformite.Gravite.MINEURE,
        chantier_id=ticket.installation_id,
        signale_par=signale_par,
        ticket_sav_id=ticket_id,
    )
    return ncr, True


@transaction.atomic
def creer_intervention_depuis_ncr(ncr, description=None):
    """Ouvre une intervention corrective SAV depuis une NCR chantier (XQHS23,
    pont inverse NCR → ticket). Appelle la fonction FINE
    ``sav.services.creer_intervention_depuis_installation`` — QHSE n'importe
    jamais ``sav.models`` directement. Idempotent (même marqueur
    ``[NCR:<reference>]``). Lève ``ValueError`` si la NCR n'a pas de chantier
    rattaché."""
    from apps.sav.services import creer_intervention_depuis_installation

    if ncr.chantier_id is None:
        raise ValueError(
            "Impossible d'ouvrir une intervention : la non-conformité n'a "
            "pas de chantier rattaché.")

    ticket, created = creer_intervention_depuis_installation(
        company=ncr.company,
        installation_id=ncr.chantier_id,
        description=description or (
            f'Intervention corrective suite NCR : {ncr.titre}'),
        ncr_reference=ncr.reference or ncr.pk,
    )
    return ticket, created


# ── XQHS24 — Gestion du changement (MOC léger) ──────────────────────────────

# Transitions valides du cycle de vie MOC. Un changement suit son cycle :
# une approbation (statut APPROUVE) est requise AVANT tout déploiement.
_MOC_TRANSITIONS = {
    DemandeChangement.Statut.BROUILLON: {
        DemandeChangement.Statut.EN_REVUE, DemandeChangement.Statut.ANNULE},
    DemandeChangement.Statut.EN_REVUE: {
        DemandeChangement.Statut.APPROUVE, DemandeChangement.Statut.ANNULE,
        DemandeChangement.Statut.BROUILLON},
    DemandeChangement.Statut.APPROUVE: {
        DemandeChangement.Statut.DEPLOYE, DemandeChangement.Statut.ANNULE},
    DemandeChangement.Statut.DEPLOYE: {DemandeChangement.Statut.CLOS},
    DemandeChangement.Statut.CLOS: set(),
    DemandeChangement.Statut.ANNULE: set(),
}


@transaction.atomic
def transitionner_demande_changement(demande, nouveau_statut, *, approbateur=None):
    """Fait avancer le cycle de vie d'une ``DemandeChangement`` (XQHS24).

    Le passage à ``DEPLOYE`` EXIGE que le changement soit passé par
    ``APPROUVE`` d'abord (gate — la mise en œuvre avant approbation est le
    risque même que le MOC existe pour prévenir). Toute autre transition non
    listée dans ``_MOC_TRANSITIONS`` lève ``ValueError``. Pose
    ``approbateur``/``date_approbation`` au passage à ``APPROUVE``."""
    permis = _MOC_TRANSITIONS.get(demande.statut, set())
    if nouveau_statut not in permis:
        raise ValueError(
            f'Transition {demande.statut} → {nouveau_statut} non autorisée.')

    demande.statut = nouveau_statut
    if nouveau_statut == DemandeChangement.Statut.APPROUVE:
        from django.utils import timezone
        demande.approbateur = approbateur
        demande.date_approbation = timezone.now()
    demande.save()
    return demande


@transaction.atomic
def creer_capa_mise_en_oeuvre_moc(
        demande, *, description, responsable_id=None, echeance=None):
    """Crée une CAPA de mise en œuvre liée à une ``DemandeChangement``
    (XQHS24). Réutilise une NCR support minimale (pattern
    ``convertir_observation_en_capa`` XQHS17) car CAPA exige une NCR
    parente."""
    ncr = NonConformite.objects.create(
        company=demande.company,
        titre=f'MOC · {demande.get_type_changement_display()}',
        description=demande.description,
        origine='Gestion du changement (MOC)',
        gravite=NonConformite.Gravite.MINEURE,
    )
    capa = ActionCorrectivePreventive.objects.create(
        company=demande.company,
        non_conformite=ncr,
        type_action=ActionCorrectivePreventive.Type.PREVENTIVE,
        description=description,
        responsable_id=responsable_id,
        echeance=echeance,
    )
    DemandeChangementCapa.objects.get_or_create(
        company=demande.company, demande_changement=demande, capa=capa)
    return capa


def demandes_changement_a_reverser(company, today=None):
    """Changements temporaires dont la date de réversion est due (XQHS24,
    pattern ``derogations_a_relancer``/QHSE38). Agrégation PURE."""
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    qs = DemandeChangement.objects.filter(
        company=company, est_temporaire=True,
        date_expiration__isnull=False,
        date_expiration__lte=today,
    ).exclude(statut__in=[
        DemandeChangement.Statut.CLOS, DemandeChangement.Statut.ANNULE])
    return list(qs)


def _notifier_reversion_due(demande):
    """Notifie (best-effort) qu'un changement temporaire doit être reversé."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        if demande.approbateur_id is None:
            return
        notify(demande.approbateur, EventType.MAINTENANCE_DUE,
               'Réversion de changement temporaire due',
               body=f'Le changement « {demande.description[:80]} » devait '
                    f'être reversé le {demande.date_expiration}.',
               link='/qhse/gestion-changement', company=demande.company)
    except Exception:  # pragma: no cover - défensif
        pass


def relancer_demandes_changement(company=None):
    """Relance TOUS les changements temporaires en retard de réversion
    (XQHS24, pattern ``relancer_derogations``). Ne mute rien. Renvoie les
    demandes relancées."""
    if company is not None:
        demandes = demandes_changement_a_reverser(company)
    else:
        demandes = []
        for co in {d.company for d in DemandeChangement.objects.filter(
                est_temporaire=True)}:
            demandes.extend(demandes_changement_a_reverser(co))

    for demande in demandes:
        _notifier_reversion_due(demande)
    return demandes


# ── XQHS25 — Assistance IA QHSE (classification + brouillon d'analyse) ────
# Key-gated (GROQ_API_KEY, déjà présente en .env pour d'autres features — pas
# de nouvelle dépendance externe/paid ajoutée ici). Sans clé, les fonctions
# renvoient ``disponible=False`` et une structure vide — jamais d'exception,
# jamais de no-op cassant. TOUJOURS une proposition éditable, jamais appliquée
# automatiquement (pattern propose→confirm du groupe AG).

import json  # noqa: E402
import os  # noqa: E402

import requests  # noqa: E402

_GROQ_CHAT_URL = 'https://api.groq.com/openai/v1/chat/completions'
_GROQ_MODEL_DEFAUT = 'llama-3.1-8b-instant'


def _groq_api_key():
    return os.environ.get('GROQ_API_KEY', '') or ''


def ia_disponible():
    """True si une clé IA (GROQ) est configurée. Sert de garde côté
    vue/front (masque les boutons IA quand False)."""
    return bool(_groq_api_key())


def _appeler_groq(system_prompt, user_prompt, *, timeout=15):
    """Appel HTTP direct à l'API Groq (compatible OpenAI), sans SDK
    supplémentaire (``requests`` est déjà une dépendance du projet). Renvoie
    le contenu texte de la réponse, ou lève une exception (capturée par
    l'appelant) en cas d'échec réseau/clé/timeout."""
    resp = requests.post(
        _GROQ_CHAT_URL,
        headers={
            'Authorization': f'Bearer {_groq_api_key()}',
            'Content-Type': 'application/json',
        },
        json={
            'model': _GROQ_MODEL_DEFAUT,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': 0,
            'response_format': {'type': 'json_object'},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


_CLASSIFICATION_SYSTEM_PROMPT = (
    "Tu es un assistant QHSE pour un installateur solaire au Maroc. À partir "
    "d'une description libre d'incident ou de non-conformité, propose une "
    "classification structurée. Réponds UNIQUEMENT en JSON valide avec les "
    "clés : \"type\" (accident|presqu_accident|incident|environnement pour un "
    "incident, ou une famille de défaut pour une NCR), \"gravite\" "
    "(mineure|majeure|critique), \"code_defaut_suggere\" (courte étiquette "
    "libre), \"justification\" (une phrase). Ne donne AUCUNE autre donnée que "
    "celle décrite dans le texte fourni — aucune donnée d'une autre société "
    "n'est disponible et ne doit être inventée."
)

_ANALYSE_SYSTEM_PROMPT = (
    "Tu es un assistant QHSE. À partir du récit d'investigation d'un "
    "incident/non-conformité, propose un brouillon structuré. Réponds "
    "UNIQUEMENT en JSON valide avec les clés : \"cinq_pourquoi\" (liste de 5 "
    "chaînes, une par niveau, vide si non déterminable), \"cause_racine\" "
    "(une phrase), \"plan_capa\" (liste d'objets {\"description\": str, "
    "\"type_action\": \"corrective\"|\"preventive\"}). Toujours une "
    "PROPOSITION à éditer — jamais présentée comme définitive."
)


def suggerer_classification_incident(description):
    """XQHS25 — suggère type/gravité/code défaut à partir d'une description
    libre (incident ou NCR). Key-gated : sans ``GROQ_API_KEY``, renvoie
    ``{'disponible': False}`` (200, jamais d'exception ni de dépendance dure).

    TOUJOURS une proposition éditable — l'appelant (vue) ne l'applique jamais
    automatiquement à un enregistrement."""
    if not ia_disponible():
        return {'disponible': False}
    if not (description or '').strip():
        return {'disponible': True, 'suggestion': None,
                'erreur': 'description vide'}

    try:
        contenu = _appeler_groq(
            _CLASSIFICATION_SYSTEM_PROMPT, description.strip())
        suggestion = json.loads(contenu)
    except Exception as exc:  # pragma: no cover - dépend d'un service externe
        return {'disponible': True, 'suggestion': None, 'erreur': str(exc)}

    return {'disponible': True, 'suggestion': suggestion}


def suggerer_analyse_capa(recit_investigation):
    """XQHS25 — propose un brouillon 5-Pourquoi + plan CAPA depuis un récit
    d'investigation. Key-gated comme ``suggerer_classification_incident`` —
    dégrade proprement sans clé. TOUJOURS éditable, jamais auto-appliqué."""
    if not ia_disponible():
        return {'disponible': False}
    if not (recit_investigation or '').strip():
        return {'disponible': True, 'suggestion': None,
                'erreur': 'récit vide'}

    try:
        contenu = _appeler_groq(
            _ANALYSE_SYSTEM_PROMPT, recit_investigation.strip())
        suggestion = json.loads(contenu)
    except Exception as exc:  # pragma: no cover - dépend d'un service externe
        return {'disponible': True, 'suggestion': None, 'erreur': str(exc)}

    return {'disponible': True, 'suggestion': suggestion}
