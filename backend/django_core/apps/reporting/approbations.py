"""XKB1 — Boîte d'approbations centralisée (agrégateur cross-app).

Un écran unique listant TOUT ce qui attend l'approbation de l'utilisateur
courant à travers les modules, agrégé depuis les sources d'objets « en
attente » existantes :

  * ``automation.AutomationApproval`` (status pending) — via
    ``apps.automation.selectors.approvals_en_attente`` +
    ``apps.automation.services.decider_approval`` ;
  * ``contrats.EtapeApprobation`` (statut en_attente) — via
    ``apps.contrats.selectors.etapes_approbation_en_attente`` +
    ``apps.contrats.services.approuver_etape``/``rejeter_etape`` ;
  * ``ged.DemandeApprobation`` (statut en_attente) — via
    ``apps.ged.selectors.demandes_approbation_en_attente`` +
    ``apps.ged.services.approve_demande``/``reject_demande`` ;
  * ``installations.DemandeAchat`` (statut soumise, FG310 — vit dans
    installations, PAS stock) — via
    ``apps.installations.selectors.demandes_achat_en_attente`` +
    ``apps.installations.services.decider_demande_achat`` ;
  * ``core.WorkflowStepInstance`` d'approbation en attente (moteur BPM
    FG366) — via ``core.workflow.pending_steps_for_company`` +
    ``core.workflow.decide_step``.

La remise devis (garde synchrone 403 ``_guard_discount_approval``) n'est PAS
une source : elle ne produit aucun objet « en attente ».

Lecture EXCLUSIVEMENT via les selectors des apps cibles ; écriture
EXCLUSIVEMENT via leurs services. Jamais d'import de ``models``/``views``
d'une autre app (contrat import-linter). ``core`` est fondation, importable
directement (``core.workflow``)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


def _co(user):
    if user.company_id:
        return user.company
    return None


def _automation_items(company):
    from apps.automation import selectors as automation_selectors
    out = []
    for approval in automation_selectors.approvals_en_attente(company):
        out.append({
            'source': 'automation',
            'id': approval.id,
            'libelle': approval.description or (
                approval.rule.nom if approval.rule_id else 'Automatisation'),
            'cree_le': approval.date_creation,
            'demandeur': getattr(approval.requested_by, 'username', None),
        })
    return out


def _contrats_items(company):
    from apps.contrats import selectors as contrats_selectors
    out = []
    for etape in contrats_selectors.etapes_approbation_en_attente(company):
        out.append({
            'source': 'contrats',
            'id': etape.id,
            'libelle': f'Contrat {etape.contrat.reference} — étape {etape.niveau}'
            if getattr(etape.contrat, 'reference', None)
            else f'Contrat #{etape.contrat_id} — étape {etape.niveau}',
            'cree_le': None,
            'demandeur': None,
        })
    return out


def _ged_items(company):
    from apps.ged import selectors as ged_selectors
    out = []
    for demande in ged_selectors.demandes_approbation_en_attente(company):
        out.append({
            'source': 'ged',
            'id': demande.id,
            'libelle': f'Document {getattr(demande.document, "nom", demande.document_id)}',
            'cree_le': demande.created_at,
            'demandeur': getattr(demande.demandeur, 'username', None),
        })
    return out


def _installations_items(company):
    from apps.installations import selectors as installations_selectors
    out = []
    for da in installations_selectors.demandes_achat_en_attente(company):
        out.append({
            'source': 'installations',
            'id': da.id,
            'libelle': f'Réquisition {da.reference}',
            'cree_le': None,
            'demandeur': None,
        })
    return out


def _core_workflow_items(company):
    from core import workflow as core_workflow
    out = []
    for step in core_workflow.pending_steps_for_company(company):
        out.append({
            'source': 'workflow',
            'id': step.id,
            'libelle': step.step_def.nom if step.step_def_id else 'Étape workflow',
            'cree_le': None,
            'demandeur': getattr(step.assignee, 'username', None),
        })
    return out


_SOURCE_LOADERS = {
    'automation': _automation_items,
    'contrats': _contrats_items,
    'ged': _ged_items,
    'installations': _installations_items,
    'workflow': _core_workflow_items,
}


@api_view(['GET'])
@permission_classes([IsAnyRole])
def approbations_en_attente(request):
    """XKB1 — ``GET reporting/approbations-en-attente/``.

    Renvoie les demandes multi-modules EN ATTENTE, scopées à la société de
    l'utilisateur (jamais une autre société). ``?source=`` filtre à une seule
    source (``automation``/``contrats``/``ged``/``installations``/
    ``workflow``)."""
    company = _co(request.user)
    if company is None:
        return Response({'items': [], 'total': 0})

    source_filter = request.query_params.get('source')
    sources = ([source_filter] if source_filter in _SOURCE_LOADERS
               else list(_SOURCE_LOADERS))

    items = []
    for source in sources:
        items.extend(_SOURCE_LOADERS[source](company))

    items.sort(key=lambda it: (it['source'], it['id']))
    return Response({'items': items, 'total': len(items)})


def _decider_approbation_core(company, user, source, obj_id, decision, motif):
    """Logique métier partagée par ``decider_approbation`` (vue DRF) et
    ``decider_en_masse`` (boucle en masse). Prend des arguments déjà
    parsés — aucune dépendance à un objet ``request`` — pour éviter tout
    besoin de fabriquer un faux ``HttpRequest`` lors des appels en boucle.

    Retourne ``(status_code, body_dict)``."""
    if company is None:
        return 403, {'detail': 'Accès refusé.'}

    if source not in _SOURCE_LOADERS:
        return 400, {'detail': 'Source inconnue.'}
    if decision not in ('approuver', 'refuser'):
        return 400, {'detail': 'Décision invalide.'}
    approve = decision == 'approuver'
    if not approve and not motif:
        return 400, {'detail': 'Un motif de refus est obligatoire.'}

    try:
        if source == 'automation':
            from apps.automation import selectors as automation_selectors
            from apps.automation import services as automation_services
            approval = (automation_selectors.approvals_en_attente(company)
                        .filter(id=obj_id).first())
            if approval is None:
                return 404, {'detail': 'Introuvable.'}
            automation_services.decider_approval(
                approval, approve=approve, user=user)

        elif source == 'contrats':
            from apps.contrats import selectors as contrats_selectors
            from apps.contrats import services as contrats_services
            etape = (contrats_selectors.etapes_approbation_en_attente(company)
                     .filter(id=obj_id).first())
            if etape is None:
                return 404, {'detail': 'Introuvable.'}
            if approve:
                contrats_services.approuver_etape(
                    etape, approbateur=user, commentaire=motif)
            else:
                contrats_services.rejeter_etape(
                    etape, approbateur=user, commentaire=motif)

        elif source == 'ged':
            from apps.ged import selectors as ged_selectors
            from apps.ged import services as ged_services
            demande = (ged_selectors.demandes_approbation_en_attente(company)
                       .filter(id=obj_id).first())
            if demande is None:
                return 404, {'detail': 'Introuvable.'}
            if approve:
                ged_services.approve_demande(
                    demande, user=user, commentaire=motif)
            else:
                ged_services.reject_demande(
                    demande, user=user, commentaire=motif)

        elif source == 'installations':
            from apps.installations import selectors as installations_selectors
            from apps.installations import services as installations_services
            da = (installations_selectors.demandes_achat_en_attente(company)
                  .filter(id=obj_id).first())
            if da is None:
                return 404, {'detail': 'Introuvable.'}
            installations_services.decider_demande_achat(
                da, approuver=approve, user=user, motif_refus=motif)

        else:  # workflow
            from core import workflow as core_workflow
            step = next(
                (s for s in core_workflow.pending_steps_for_company(company)
                 if s.id == int(obj_id)), None) if obj_id else None
            if step is None:
                return 404, {'detail': 'Introuvable.'}
            core_workflow.decide_step(
                step, approve=approve, user=user, commentaire=motif)
    except Exception as exc:  # garde générique : jamais de 500 opaque
        return 400, {'detail': str(exc)}

    return 200, {'detail': 'Décision enregistrée.'}


@api_view(['POST'])
@permission_classes([IsAnyRole])
def decider_approbation(request):
    """XKB1 — ``POST reporting/approbations-en-attente/decider/``.

    Corps : ``{source, id, decision: 'approuver'|'refuser', motif}``. Le motif
    est OBLIGATOIRE pour un refus. Approuve/refuse en appelant le service de
    l'app source (jamais de mutation directe depuis reporting) puis
    journalise (le journal reste porté par l'app source, ex. TicketActivity /
    AutomationApproval.decided_at — pas de duplication ici)."""
    company = _co(request.user)
    source = request.data.get('source')
    obj_id = request.data.get('id')
    decision = request.data.get('decision')
    motif = (request.data.get('motif') or '').strip()

    status_code, body = _decider_approbation_core(
        company, request.user, source, obj_id, decision, motif)
    return Response(body, status=status_code)


@api_view(['POST'])
@permission_classes([IsAnyRole])
def decider_en_masse(request):
    """XKB1 — actions en masse : ``{items: [{source, id}], decision, motif}``.

    Applique la même décision à chaque item via ``_decider_approbation_core``
    (réutilise sa logique un par un, sans passer par un ``Request`` DRF
    factice) ; renvoie le détail des réussites/échecs sans jamais laisser un
    échec interrompre les suivants."""
    company = _co(request.user)
    if company is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    items = request.data.get('items') or []
    decision = request.data.get('decision')
    motif = (request.data.get('motif') or '').strip()

    resultats = []
    for item in items:
        status_code, body = _decider_approbation_core(
            company, request.user, item.get('source'), item.get('id'),
            decision, motif)
        resultats.append({
            'source': item.get('source'), 'id': item.get('id'),
            'ok': status_code == 200,
            'detail': body.get('detail'),
        })
    return Response({'resultats': resultats})
