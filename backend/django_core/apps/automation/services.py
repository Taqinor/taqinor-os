"""Services XKB2/XKB3/ZCTR7 — demandes d'approbation ad-hoc + délégation +
options de catégorie (min approbations / PJ obligatoire / champs).

Toute la logique de validation/soumission des ``ApprovalRequest`` vit ici
pour que les vues restent minces. Reste à l'intérieur de ``apps.automation`` ;
utilise ``apps.records`` (app fondation, exemptée de la règle de frontière
cross-app) directement pour les pièces jointes génériques.
"""
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import ApprovalDecision, ApprovalDelegation, ApprovalRequest


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


def decide_request(req, *, decider, approve, note=''):
    """Enregistre UNE décision d'approbateur (ZCTR7 : ``ApprovalDecision``),
    en posant automatiquement la mention « au nom de » (XKB3) si ``decider``
    agit comme suppléant actif du demandeur au moment de la décision. Hors
    plage de délégation, rien ne change (comportement XKB2 identique).

    ZCTR7 — la demande ne passe APPROVED qu'après ``min_approbations``
    décisions FAVORABLES d'approbateurs DISTINCTS (rétrocompat : min=1 = un
    seul « approve » suffit, comportement XKB2 identique). Un REJECT clôt
    immédiatement la demande (une décision défavorable suffit).

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
    return req
