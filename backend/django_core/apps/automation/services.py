"""Services XKB2/XKB3/ZCTR7/ZCTR8 — demandes d'approbation ad-hoc + délégation
+ options de catégorie + demande d'info + ordre séquentiel/parallèle.

Toute la logique de validation/soumission des ``ApprovalRequest`` vit ici
pour que les vues restent minces. Reste à l'intérieur de ``apps.automation`` ;
utilise ``apps.records`` (app fondation, exemptée de la règle de frontière
cross-app) directement pour les pièces jointes génériques. La notification du
demandeur (ZCTR8) passe par ``apps.notifications.services.notify`` — best-
effort : si l'événement n'est pas (encore) enregistré côté ``notifications``,
l'appel no-op proprement (aucune exception), donc rien ne casse ici.
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import ApprovalDecision, ApprovalDelegation, ApprovalRequest

logger = logging.getLogger(__name__)

# Clé d'événement notifications (ZCTR8). Voir la note de module : no-op sûr
# tant que `notifications.EventType` ne la porte pas encore.
NOTIFY_EVENT_INFO_REQUESTED = 'approval_info_requested'


def _notify_best_effort(user, event_type, title, body='', company=None):
    """Notifie ``user`` best-effort ; n'élève JAMAIS (voir docstring module)."""
    if user is None:
        return
    try:
        from apps.notifications.services import notify
        notify(user, event_type, title, body=body, company=company)
    except Exception:  # pragma: no cover - best-effort
        logger.debug('automation: notification best-effort échouée',
                     exc_info=True)


class ApprovalError(Exception):
    """Erreur métier FR destinée à être renvoyée telle quelle en 400."""


def _approval_request_content_type():
    return ContentType.objects.get_for_model(ApprovalRequest)


def count_attachments(request_obj):
    """Nombre de pièces jointes (records.Attachment) sur cette demande."""
    from apps.records.models import Attachment
    return Attachment.objects.filter(
        content_type=_approval_request_content_type(),
        object_id=request_obj.pk,
    ).count()


def attach_file(request_obj, file, *, user, company):
    """Stocke un fichier (records.storage) et le rattache à la demande."""
    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    meta, err = store_attachment(file)
    if err:
        raise ApprovalError(err)
    return Attachment.objects.create(
        company=company,
        content_type=_approval_request_content_type(),
        object_id=request_obj.pk,
        uploaded_by=user,
        **meta,
    )


def submit_request(
        *, request_type, demandeur, company, payload, has_attachment=False):
    """Valide (champs requis du type) puis crée une ``ApprovalRequest``.

    ZCTR7 — quand ``request_type.piece_jointe_obligatoire`` est vrai, la
    soumission est refusée si ``has_attachment`` est faux (l'appelant
    signale ainsi qu'un fichier a été fourni dans la MÊME requête multipart).
    Rétrocompat : ``piece_jointe_obligatoire=False`` (défaut XKB2) ne change
    rien.

    Lève ``ApprovalError`` (message FR) si un champ requis manque ou si la
    PJ obligatoire est absente.
    """
    errors = request_type.validate_payload(payload)
    if errors:
        raise ApprovalError(' '.join(errors))
    if request_type.piece_jointe_obligatoire and not has_attachment:
        raise ApprovalError(
            'Une pièce jointe est requise pour ce type de demande.')
    return ApprovalRequest.objects.create(
        company=company,
        request_type=request_type,
        demandeur=demandeur,
        payload=payload or {},
    )


# ── XKB3 — Délégation d'approbation (suppléant) ──────────────────────────────

def active_delegation_for(delegant, *, at=None):
    """Délégation ACTIVE (plage courante) où ``delegant`` est le délégant,
    ou ``None`` — hors plage, retour automatique au délégant (rien à faire)."""
    at = at or timezone.now()
    return ApprovalDelegation.objects.filter(
        delegant=delegant, date_debut__lte=at, date_fin__gte=at,
    ).first()


def visible_demandeur_ids_for(user, *, at=None):
    """Ids de demandeurs dont ``user`` doit voir les demandes en attente :
    lui-même s'il est délégant actif (transparence) PLUS chaque délégant pour
    qui ``user`` est actuellement suppléant actif (XKB3)."""
    at = at or timezone.now()
    ids = {user.pk}
    ids.update(
        ApprovalDelegation.objects.filter(
            suppleant=user, date_debut__lte=at, date_fin__gte=at,
        ).values_list('delegant_id', flat=True)
    )
    return ids


def _distinct_favorable_approvers(req):
    return (
        req.decisions
        .filter(decision=ApprovalDecision.Decision.APPROVE)
        .values('decided_by_id').distinct().count()
    )


def rank_of_next_approver(req):
    """Rang (1-based) du PROCHAIN approbateur attendu — nombre de décisions
    favorables déjà enregistrées + 1. Utilisé en mode SEQUENTIEL (ZCTR8) pour
    déterminer qui notifier ensuite."""
    return _distinct_favorable_approvers(req) + 1


def decide_request(req, *, decider, approve, note=''):
    """Enregistre UNE décision d'approbateur (ZCTR7 : ``ApprovalDecision``),
    en posant automatiquement la mention « au nom de » (XKB3) si ``decider``
    agit comme suppléant actif du demandeur au moment de la décision. Hors
    plage de délégation, rien ne change (comportement XKB2 identique).

    ZCTR7 — la demande ne passe APPROVED qu'après ``min_approbations``
    décisions FAVORABLES d'approbateurs DISTINCTS (rétrocompat : min=1 = un
    seul « approve » suffit, comportement XKB2 identique). Un REJECT clôt
    immédiatement la demande (une décision défavorable suffit).

    ZCTR8 — en mode ``SEQUENTIEL``, chaque décision favorable fait AVANCER le
    rang attendu : le prochain rang n'est notifié (best-effort) qu'APRÈS
    cette décision. En mode ``PARALLELE`` (défaut), rien ne change
    (comportement XKB1/XKB2 inchangé : tous notifiés dès la soumission par
    l'appelant existant, hors du périmètre de cette fonction).

    YEVNT11 — SOD : le demandeur ne peut jamais approuver sa propre demande
    (override admin audité, journalisé par ``engine``). La garde SOD
    s'applique à CHAQUE décision (y compris la 2e/3e d'un seuil > 1)."""
    if req.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError('Décision déjà prise.')

    from . import engine
    # Laisse `SodViolation` remonter TELLE QUELLE (distincte d'`ApprovalError`)
    # pour que l'appelant (vue) puisse répondre 403 plutôt que 400.
    engine.enforce_requester_not_approver(
        requester=req.demandeur, approver=decider, company=req.company,
        label=f'approval_request#{req.pk}')

    already_decided = req.decisions.filter(decided_by=decider).exists()
    if already_decided:
        raise ApprovalError('Vous avez déjà décidé pour cette demande.')

    on_behalf_of = None
    demandeur = req.demandeur
    if demandeur is not None and decider.pk != demandeur.pk:
        deleg = active_delegation_for(demandeur)
        if deleg is not None and deleg.suppleant_id == decider.pk:
            on_behalf_of = demandeur

    ApprovalDecision.objects.create(
        request=req, decided_by=decider,
        decision=(ApprovalDecision.Decision.APPROVE if approve
                  else ApprovalDecision.Decision.REJECT),
        note=note or '', on_behalf_of=on_behalf_of,
    )

    if not approve:
        req.status = ApprovalRequest.Status.REJECTED
        req.decided_by = decider
        req.decided_at = timezone.now()
        req.decision_note = note or ''
        req.decided_on_behalf_of = on_behalf_of
        req.save(update_fields=[
            'status', 'decided_by', 'decided_at', 'decision_note',
            'decided_on_behalf_of'])
        return req

    min_needed = max(1, req.request_type.min_approbations or 1)
    if _distinct_favorable_approvers(req) >= min_needed:
        req.status = ApprovalRequest.Status.APPROVED
        req.decided_by = decider
        req.decided_at = timezone.now()
        req.decision_note = note or ''
        req.decided_on_behalf_of = on_behalf_of
        req.save(update_fields=[
            'status', 'decided_by', 'decided_at', 'decision_note',
            'decided_on_behalf_of'])
    # Sinon : décision favorable enregistrée mais le seuil n'est pas encore
    # atteint — la demande reste PENDING (visible pour les autres
    # approbateurs), sans lever d'erreur (l'appelant voit sa décision prise).
    # ZCTR8 — mode séquentiel : le rang suivant vient de devenir éligible ;
    # notifie best-effort (no-op sûr sans EventType enregistré) le prochain
    # rang. En mode PARALLELE, rien de plus à faire ici (déjà notifiés).
    is_sequential = (
        req.request_type.sequence_approbateurs
        == req.request_type.SequenceApprobateurs.SEQUENTIEL)
    if req.status == ApprovalRequest.Status.PENDING and is_sequential:
        notify_next_rank(req)
    return req


def notify_next_rank(req):
    """ZCTR8 — notifie best-effort le PROCHAIN rang d'approbateurs (mode
    séquentiel) : appelé après chaque décision favorable qui ne clôt pas
    encore la demande. Sans destinataire nommé (le palier n'est pas une
    liste d'utilisateurs identifiés dans XKB2), on notifie best-effort le
    demandeur d'avancement — laisse la place à un futur ciblage nommé par
    rang sans changer la signature."""
    rank = rank_of_next_approver(req)
    _notify_best_effort(
        req.demandeur, NOTIFY_EVENT_INFO_REQUESTED,
        title=f'Approbation « {req.request_type.nom} » — rang {rank}',
        body='Une décision favorable vient de faire avancer votre demande '
             'au rang suivant.',
        company=req.company)


# ── ZCTR8 — Demander un complément d'information ────────────────────────────

def request_more_info(req, *, user, motif):
    """Renvoie la demande à son émetteur SANS la rejeter (statut dédié
    ``INFO_REQUESTED``) — motif obligatoire, journalisé (``decision_note``)
    et notifié best-effort au demandeur.

    ``user`` doit être un approbateur du palier (vérifié côté vue via
    ``IsAdminOrResponsableTier``, comme approve/reject)."""
    if req.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError('Décision déjà prise.')
    motif = (motif or '').strip()
    if not motif:
        raise ApprovalError('Un motif est requis.')

    req.status = ApprovalRequest.Status.INFO_REQUESTED
    req.decided_by = user
    req.decided_at = timezone.now()
    req.decision_note = motif
    req.save(update_fields=[
        'status', 'decided_by', 'decided_at', 'decision_note'])

    _notify_best_effort(
        req.demandeur, NOTIFY_EVENT_INFO_REQUESTED,
        title=f'Complément demandé — « {req.request_type.nom} »',
        body=motif, company=req.company)
    return req


def resoumettre(req, *, demandeur, payload=None):
    """Le demandeur ré-ouvre un cycle d'approbation après un
    ``INFO_REQUESTED`` : met à jour ``payload`` (si fourni), revalide les
    champs requis du type, repasse en PENDING, efface les anciennes
    décisions (nouveau cycle — sinon un ancien « approve » compterait encore
    pour un nouveau seuil ``min_approbations``)."""
    if req.status != ApprovalRequest.Status.INFO_REQUESTED:
        raise ApprovalError(
            'Seule une demande « complément demandé » peut être resoumise.')
    if req.demandeur_id != getattr(demandeur, 'pk', None):
        raise ApprovalError(
            'Seul le demandeur original peut resoumettre cette demande.')

    if payload is not None:
        req.payload = payload
    errors = req.request_type.validate_payload(req.payload)
    if errors:
        raise ApprovalError(' '.join(errors))

    req.decisions.all().delete()
    req.status = ApprovalRequest.Status.PENDING
    req.decided_by = None
    req.decided_at = None
    req.decision_note = ''
    req.decided_on_behalf_of = None
    req.save(update_fields=[
        'payload', 'status', 'decided_by', 'decided_at', 'decision_note',
        'decided_on_behalf_of'])
    return req


class DecisionError(Exception):
    """Décision invalide sur une approbation (statut non éligible)."""


# ── XPLT18 — Brouillon de règle proposé par l'agent (langage naturel) ───────

class DraftRuleError(Exception):
    """Brouillon de règle invalide (message FR, destiné à un 400)."""


def create_draft_rule_from_agent(
        *, company, nom, trigger_type, trigger_config,
        action_type, action_config, ordre=0):
    """XPLT18 — crée une ``AutomationRule`` DÉSACTIVÉE à partir d'un brouillon
    structuré produit par l'agent (LLM) après confirmation utilisateur.

    Le LLM ne produit JAMAIS de code libre : ``trigger_type``/``action_type``
    doivent appartenir au catalogue FERMÉ (``TriggerType``/``ActionType``),
    validé ici contre ``selectors.closed_rule_catalogue()`` — jamais contre une
    liste dupliquée côté agent. La règle est TOUJOURS créée ``enabled=False``
    (revue admin obligatoire avant toute exécution réelle) ; ``company`` est
    imposée par l'appelant serveur (jamais lue du brouillon LLM).

    Lève ``DraftRuleError`` (FR) si le déclencheur/l'action n'appartient pas
    au catalogue fermé, ou si ``nom`` est vide.
    """
    from . import selectors
    from .models import AutomationRule

    nom = (nom or '').strip()
    if not nom:
        raise DraftRuleError('Un nom de règle est requis.')

    catalogue = selectors.closed_rule_catalogue()
    if trigger_type not in catalogue['trigger_types']:
        raise DraftRuleError(
            f"Déclencheur inconnu du catalogue : {trigger_type!r}.")
    if action_type not in catalogue['action_types']:
        raise DraftRuleError(
            f"Action inconnue du catalogue : {action_type!r}.")

    if not isinstance(trigger_config, dict):
        raise DraftRuleError('trigger_config doit être un objet JSON.')
    if not isinstance(action_config, dict):
        raise DraftRuleError('action_config doit être un objet JSON.')

    return AutomationRule.objects.create(
        company=company,
        nom=nom,
        enabled=False,  # XPLT18 — toujours désactivée : revue admin requise.
        trigger_type=trigger_type,
        trigger_config=trigger_config or {},
        action_type=action_type,
        action_config=action_config or {},
        ordre=ordre or 0,
    )


def decider_approval(approval, *, approve, user):
    """XKB1 — approuve/rejette une ``AutomationApproval`` en attente.

    Lève ``DecisionError`` si l'approbation n'est pas ``PENDING``. Une
    approbation relance l'action différée (``engine.run_approved``) ; un rejet
    n'exécute jamais l'action."""
    from . import engine
    from .models import AutomationApproval

    if approval.status != AutomationApproval.Status.PENDING:
        raise DecisionError('Décision déjà prise.')

    approval.status = (
        AutomationApproval.Status.APPROVED if approve
        else AutomationApproval.Status.REJECTED)
    approval.decided_by = user
    approval.decided_at = timezone.now()
    approval.save(update_fields=['status', 'decided_by', 'decided_at'])
    if approve:
        engine.run_approved(approval, user=user)
    return approval


# ─────────────────────────────────────────────────────────────────────────────
# YOPSB11 — Archivage par lots de `AutomationRun` (journal à forte croissance)
#
# Le journal des exécutions est append-only et grossit sans borne. La politique
# YOPSB11 (registre partagé YOPSB10) déplace les exécutions plus vieilles que
# `jours` vers `AutomationRunArchive` (par lots, un commit par lot) puis les
# supprime de la table vive. Fenêtre par défaut 0 = OFF (comportement inchangé) ;
# réglage via `AUTOMATION_RUN_ARCHIVE_DAYS`.

DEFAULT_AUTOMATION_RUN_ARCHIVE_DAYS = 0


def _automation_run_to_archive(row):
    return {
        'original_id': row.pk,
        'company_id': row.company_id,
        'rule_id': row.rule_id,
        'target_model': row.target_model,
        'target_id': row.target_id,
        'status': row.status,
        'message': row.message,
        'timestamp': row.timestamp,
    }


def archiver_anciens(now, jours, apply_=True):
    """YOPSB11 — archive les `AutomationRun` plus vieux que `jours` (par lots de
    5 000, un commit par lot). `jours <= 0` (défaut OFF) → 0 ; `apply_=False`
    (dry-run) compte sans déplacer. Renvoie le nombre archivé."""
    from core.retention import archive_old_rows
    from .models import AutomationRun, AutomationRunArchive

    return archive_old_rows(
        AutomationRun, AutomationRunArchive, _automation_run_to_archive,
        cutoff_field='timestamp', now=now, jours=jours, apply_=apply_,
    )
