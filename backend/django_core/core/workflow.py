"""FG366 — Moteur de workflow multi-étapes (BPM) + SLA / escalades.

Services PURS et GÉNÉRIQUES qui pilotent les modèles de ``core.models``
(``WorkflowDefinition``/``WorkflowStepDefinition``/``WorkflowInstance``/
``WorkflowStepInstance``). Aucun import d'app métier : la cible d'une instance
est désignée via ``contenttypes`` (fondation Django), donc ce moteur fait
tourner une chaîne d'approbation sur n'importe quel modèle sans le connaître.

Principes de conception
-----------------------

* **Déterminisme testable.** Toute fonction qui dépend du temps reçoit ``now``
  (ou ``today``) en argument — JAMAIS d'appel interne à ``timezone.now()`` au
  cœur de la logique. ``demarrer_workflow`` accepte ``now`` pour figer le départ
  et calculer les échéances SLA ; ``etapes_sla_depassees`` reçoit ``now``.
* **Multi-tenant.** ``company`` est imposé côté serveur partout : les instances
  et étapes copient la société passée, jamais une valeur du corps de requête.
* **SLA.** Pour une étape dont la définition porte ``sla_heures``,
  ``sla_echeance = started + sla_heures``. Sans ``sla_heures``, pas de minuterie
  (``sla_echeance`` reste vide → jamais en dépassement).

API publique
------------

* ``demarrer_workflow(definition, target, company, user=None, now=None)``
  instancie l'instance + toutes les étapes (en attente) et active la première.
* ``approuver_etape`` / ``rejeter_etape`` enregistrent une décision sur l'étape
  courante puis ``avancer`` fait progresser séquentiellement.
* ``avancer(instance, now=None)`` passe à l'étape suivante (auto-approuve les
  étapes ``type_approbation == 'auto'``) et clôt l'instance à la fin.
* ``etapes_sla_depassees(company, now)`` (sélecteur) liste les étapes en attente
  dont l'échéance SLA est passée — base des escalades.
* ``escalader_etape(step, now=None)`` marque une étape ``escalade``.

RÈGLE D'ARCHITECTURE (ARC10) — ce moteur EST LE moteur d'approbation
--------------------------------------------------------------------

**Toute NOUVELLE approbation multi-étapes passe par ce moteur
``core.WorkflowDefinition``/``WorkflowInstance``** — plus jamais un cinquième
mécanisme d'approbation ad hoc. Historiquement cinq mécanismes coexistaient
(``automation.AutomationApproval``, ``contrats.RegleApprobation``/
``EtapeApprobation``, ``ged.DemandeApprobation``, ``installations.DemandeAchat``,
et ce moteur BPM) ; l'agrégateur ``apps/reporting/approbations.py`` les remonte
déjà tous dans une boîte unique (source 5 = ce moteur, via
``pending_steps_for_company`` / ``decide_step``). Les nouveaux besoins
n'ajoutent pas de sixième chemin : ils installent un modèle FG369
(``core.workflow_templates``) et attachent une ``WorkflowInstance`` à leur
cible métier par ``contenttypes`` — sans que ``core`` n'importe l'app.

Pilote domaine vivant : la **clôture de non-conformité qhse** (hors règle #4,
volontairement) tourne sur ce moteur via le modèle FG369 ``cloture_ncr`` et les
services ``apps/qhse/services.py`` (``demarrer_workflow_cloture_ncr`` /
``approuver_etape_cloture_ncr`` / ``rejeter_etape_cloture_ncr`` /
``escalader_workflow_cloture_ncr``). Créée → approuvée → rejetée → escaladée,
couvertes en tests.

Successeur pour la **configurabilité UI** : ``parametres.ApprovalPolicy``
(FG25) porte les politiques déclaratives (type d'action + seuil + palier
d'approbateur) éditables par l'admin ; c'est la couche de configuration qui
alimentera à terme la sélection/instanciation de ces définitions de workflow —
ce moteur reste l'EXÉCUTION, FG25 la CONFIGURATION.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import (
    WorkflowInstance,
    WorkflowStepInstance,
)

__all__ = [
    'demarrer_workflow',
    'avancer',
    'approuver_etape',
    'rejeter_etape',
    'escalader_etape',
    'etape_courante_de',
    'etapes_sla_depassees',
    'flag_overdue_steps',
    'instance_en_cours_pour',
]


def _resolve_now(now):
    """Retourne ``now`` tel quel, ou ``timezone.now()`` par défaut.

    On centralise ce SEUL point de défaut pour que les couches internes
    reçoivent toujours un ``now`` explicite (déterminisme)."""
    return now if now is not None else timezone.now()


def _sla_echeance(started, sla_heures):
    """``started + sla_heures`` (datetime) ou ``None`` si pas de SLA."""
    if not sla_heures:
        return None
    return started + datetime.timedelta(hours=sla_heures)


@transaction.atomic
def demarrer_workflow(definition, target, company, user=None, now=None):
    """Instancie un workflow sur ``target`` et active sa première étape.

    Crée une ``WorkflowInstance`` (cible générique via contenttypes) plus une
    ``WorkflowStepInstance`` par ``WorkflowStepDefinition`` de la définition,
    en calculant l'échéance SLA de chaque étape à partir de ``started`` (= now).
    La première étape devient ``etape_courante = 1`` ; les étapes ``auto`` en
    tête sont franchies immédiatement par ``avancer``.

    ``company`` est imposé sur l'instance ET chaque étape. ``now`` est passé
    pour un calcul SLA déterministe.
    """
    started = _resolve_now(now)
    ct = ContentType.objects.get_for_model(target.__class__)

    instance = WorkflowInstance.objects.create(
        company=company,
        definition=definition,
        content_type=ct,
        object_id=target.pk,
        statut=WorkflowInstance.STATUT_EN_COURS,
        etape_courante=1,
        started_le=started,
    )

    step_defs = list(definition.steps.order_by('ordre', 'id'))
    for sd in step_defs:
        WorkflowStepInstance.objects.create(
            company=company,
            instance=instance,
            step_def=sd,
            ordre=sd.ordre,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            sla_echeance=_sla_echeance(started, sd.sla_heures),
        )

    if not step_defs:
        # Définition sans étape → instance terminée d'emblée.
        instance.statut = WorkflowInstance.STATUT_TERMINE
        instance.ended_le = started
        instance.save(update_fields=['statut', 'ended_le', 'updated_at'])
        return instance

    # Franchit immédiatement les étapes 'auto' en tête de file.
    avancer(instance, now=started, _from_start=True)
    return instance


def instance_en_cours_pour(target, company, definition_code=None):
    """Sélecteur : la ``WorkflowInstance`` EN COURS attachée à ``target``.

    Résout la cible générique (``content_type`` + ``object_id``) sans que
    ``core`` ait à connaître le modèle métier — n'importe quelle app peut
    demander « quel workflow tourne actuellement sur cet objet ? ». Bornée à la
    société (multi-tenant, jamais de fuite) et, optionnellement, à un
    ``definition_code`` (utile quand plusieurs types de workflow peuvent viser
    le même objet). Retourne la plus récente ou ``None``.
    """
    ct = ContentType.objects.get_for_model(target.__class__)
    qs = WorkflowInstance.objects.filter(
        company=company,
        content_type=ct,
        object_id=target.pk,
        statut=WorkflowInstance.STATUT_EN_COURS,
    )
    if definition_code is not None:
        qs = qs.filter(definition__code=definition_code)
    return qs.order_by('-id').first()


def etape_courante_de(instance):
    """Retourne la ``WorkflowStepInstance`` active (ou ``None``)."""
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        return None
    return (
        instance.step_instances
        .filter(ordre=instance.etape_courante)
        .order_by('id')
        .first()
    )


def _steps_apres(instance, ordre):
    """Étapes dont l'``ordre`` est strictement supérieur, triées."""
    return list(
        instance.step_instances
        .filter(ordre__gt=ordre)
        .order_by('ordre', 'id')
    )


@transaction.atomic
def avancer(instance, now=None, _from_start=False):
    """Fait progresser l'instance après une décision (ou au démarrage).

    Auto-approuve toute étape ``type_approbation == 'auto'`` rencontrée, puis
    s'arrête sur la première étape ``en_attente`` non-auto (qui devient
    ``etape_courante``). Si plus aucune étape n'est en attente, l'instance est
    terminée. ``now`` est passé pour horodater déterministiquement.
    """
    moment = _resolve_now(now)
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        return instance

    while True:
        step = etape_courante_de(instance)
        if step is None:
            # Plus d'étape à l'ordre courant → cherche la suivante en attente.
            suivantes = _steps_apres(instance, instance.etape_courante)
            pending = [s for s in suivantes
                       if s.statut == WorkflowStepInstance.STATUT_EN_ATTENTE]
            if not pending:
                _terminer(instance, moment)
                return instance
            instance.etape_courante = pending[0].ordre
            instance.save(update_fields=['etape_courante', 'updated_at'])
            continue

        if step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
            # Déjà décidée (approuvée au démarrage…) → passe à la suivante.
            _avancer_pointeur(instance, step, moment)
            continue

        if step.step_def.type_approbation == \
                step.step_def.APPROBATION_AUTO:
            step.statut = WorkflowStepInstance.STATUT_APPROUVE
            step.decided_le = moment
            step.save(update_fields=['statut', 'decided_le', 'updated_at'])
            _avancer_pointeur(instance, step, moment)
            continue

        # Étape manuelle / par rôle en attente : on s'arrête ici.
        return instance


def _avancer_pointeur(instance, step, moment):
    """Déplace ``etape_courante`` vers la prochaine étape, ou termine."""
    suivantes = _steps_apres(instance, step.ordre)
    if not suivantes:
        _terminer(instance, moment)
        return
    instance.etape_courante = suivantes[0].ordre
    instance.save(update_fields=['etape_courante', 'updated_at'])


def _terminer(instance, moment):
    instance.statut = WorkflowInstance.STATUT_TERMINE
    instance.ended_le = moment
    instance.save(update_fields=['statut', 'ended_le', 'updated_at'])


@transaction.atomic
def approuver_etape(instance, user=None, commentaire='', now=None):
    """Approuve l'étape courante puis avance séquentiellement.

    Lève ``ValueError`` si l'instance n'est pas en cours ou n'a pas d'étape
    active en attente.
    """
    moment = _resolve_now(now)
    step = etape_courante_de(instance)
    if step is None or step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
        raise ValueError("Aucune étape en attente à approuver.")
    step.statut = WorkflowStepInstance.STATUT_APPROUVE
    step.assignee = user
    step.decided_le = moment
    if commentaire:
        step.commentaire = commentaire
    step.save(update_fields=[
        'statut', 'assignee', 'decided_le', 'commentaire', 'updated_at'])
    avancer(instance, now=moment)
    return step


@transaction.atomic
def rejeter_etape(instance, user=None, commentaire='', now=None):
    """Rejette l'étape courante : l'instance est terminée (chaîne stoppée).

    Lève ``ValueError`` si aucune étape n'est en attente.
    """
    moment = _resolve_now(now)
    step = etape_courante_de(instance)
    if step is None or step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
        raise ValueError("Aucune étape en attente à rejeter.")
    step.statut = WorkflowStepInstance.STATUT_REJETE
    step.assignee = user
    step.decided_le = moment
    if commentaire:
        step.commentaire = commentaire
    step.save(update_fields=[
        'statut', 'assignee', 'decided_le', 'commentaire', 'updated_at'])
    _terminer(instance, moment)
    return step


@transaction.atomic
def escalader_etape(step, now=None):
    """Marque une étape ``escalade`` (décision d'escalade après dépassement)."""
    moment = _resolve_now(now)
    step.statut = WorkflowStepInstance.STATUT_ESCALADE
    step.decided_le = moment
    step.save(update_fields=['statut', 'decided_le', 'updated_at'])
    return step


def etapes_sla_depassees(company, now):
    """Sélecteur : étapes ``en_attente`` d'une société dont le SLA est dépassé.

    ``now`` est OBLIGATOIRE et passé explicitement (déterminisme — pas de
    ``timezone.now()`` interne). Une étape est en dépassement si elle est
    encore en attente, porte une ``sla_echeance`` et que ``sla_echeance < now``.
    Bornée à l'instance encore en cours. Triée par échéance la plus ancienne.
    """
    return list(
        WorkflowStepInstance.objects.filter(
            company=company,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            sla_echeance__isnull=False,
            sla_echeance__lt=now,
            instance__statut=WorkflowInstance.STATUT_EN_COURS,
        ).order_by('sla_echeance', 'id')
    )


def flag_overdue_steps(company, now):
    """Escalade en masse les étapes en dépassement SLA d'une société.

    Retourne la liste des étapes escaladées. ``now`` est passé explicitement.
    """
    overdue = etapes_sla_depassees(company, now)
    for step in overdue:
        escalader_etape(step, now=now)
    return overdue


# ── XKB1 — boîte d'approbations centralisée (lecture cross-app) ──────────────

def pending_steps_for_company(company):
    """XKB1 — étapes BPM ``en_attente`` d'une société (instances en cours).

    Sélecteur LECTURE SEULE utilisé par l'agrégateur d'approbations
    (``apps/reporting``) : ``core`` reste la fondation, aucune app métier
    n'est importée ici. Triée par échéance SLA la plus proche d'abord (NULL en
    dernier), puis id."""
    from django.db.models import F
    return list(
        WorkflowStepInstance.objects.filter(
            company=company,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            instance__statut=WorkflowInstance.STATUT_EN_COURS,
        ).select_related('instance', 'step_def')
        .order_by(F('sla_echeance').asc(nulls_last=True), 'id')
    )


def decide_step(step, *, approve, user=None, commentaire='', now=None):
    """XKB1 — approuve/rejette une étape BPM en attente en résolvant son
    ``WorkflowInstance`` propriétaire (l'agrégateur ne connaît que l'étape).

    ``approve=True`` → ``approuver_etape`` ; ``approve=False`` →
    ``rejeter_etape``. Délègue entièrement à ces fonctions existantes (mêmes
    garde-fous, même transaction atomique)."""
    if approve:
        return approuver_etape(
            step.instance, user=user, commentaire=commentaire, now=now)
    return rejeter_etape(
        step.instance, user=user, commentaire=commentaire, now=now)
