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
import datetime

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


def _co(user):
    if user.company_id:
        return user.company
    return None


def _automation_items(company):
    from apps.automation import selectors as automation_selectors
    from apps.notifications import selectors as notifications_selectors
    out = []
    for approval in automation_selectors.approvals_en_attente(company):
        # VX218 — état de relance/escalade YEVNT9 (la seule source de cet
        # agrégateur balayée par `sweep_approval_reminders` aujourd'hui ;
        # jamais fabriqué pour les autres sources).
        niveau_escalade, derniere_relance_le = (
            notifications_selectors.escalade_state_pour(approval))
        out.append({
            'source': 'automation',
            'id': approval.id,
            'libelle': approval.description or (
                approval.rule.nom if approval.rule_id else 'Automatisation'),
            'cree_le': approval.date_creation,
            'demandeur': getattr(approval.requested_by, 'username', None),
            'priorite': None,
            # VX100 — aucune source homogène de montant/lien côté automation
            # aujourd'hui : champs présents pour un contrat d'API uniforme,
            # jamais fabriqués.
            'montant': None,
            'lien': None,
            'niveau_escalade': niveau_escalade,
            'derniere_relance_le': derniere_relance_le,
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
            # ZCTR9 — expose la vraie date de création (le champ existe déjà
            # sur EtapeApprobation, il n'était simplement pas remonté avant).
            'cree_le': etape.date_creation,
            'demandeur': None,
            'priorite': None,
            # VX100 — le contrat porte une route détail (`/contrats/:id`) ;
            # lien réel vers la pièce. Aucun montant homogène exposé ici
            # aujourd'hui (jamais fabriqué).
            'montant': None,
            'lien': f'/contrats/{etape.contrat_id}' if etape.contrat_id else None,
            # VX218 — seule `automation` est balayée par YEVNT9 aujourd'hui ;
            # champs présents pour un contrat d'API uniforme, jamais fabriqués.
            'niveau_escalade': None,
            'derniere_relance_le': None,
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
            'priorite': None,
            # VX100 — pas de route détail document ni de montant homogène
            # côté GED aujourd'hui : jamais fabriqués.
            'montant': None,
            'lien': None,
            # VX218 — seule `automation` est balayée par YEVNT9 aujourd'hui ;
            # champs présents pour un contrat d'API uniforme, jamais fabriqués.
            'niveau_escalade': None,
            'derniere_relance_le': None,
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
            # ZCTR9 — DemandeAchat.date_creation existe déjà (auto_now_add).
            'cree_le': da.date_creation,
            'demandeur': None,
            # ZCTR9 — seule source à porter une vraie priorité aujourd'hui.
            'priorite': da.priorite or None,
            # VX100 — montant réel (Σ lignes, property existante
            # ``montant_estime``, jamais fabriqué) ; alimente le tri
            # ``?trier=montant`` (déjà supporté, restait sans donnée).
            'montant': da.montant_estime,
            # VX100 — lien interne vers le chantier ciblé (patron VX79
            # ``/chantiers?id=<pk>``, jamais une route fabriquée) ; `None`
            # si la DA n'a pas de chantier rattaché (pas de fabrication).
            'lien': f'/chantiers?id={da.chantier_id}' if da.chantier_id else None,
            # VX218 — seule `automation` est balayée par YEVNT9 aujourd'hui ;
            # champs présents pour un contrat d'API uniforme, jamais fabriqués.
            'niveau_escalade': None,
            'derniere_relance_le': None,
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
            # ZCTR9 — WorkflowStepInstance hérite de TimestampedModel.
            'cree_le': step.created_at,
            'demandeur': getattr(step.assignee, 'username', None),
            'priorite': None,
            # VX100 — le moteur BPM générique n'a pas de route détail ni de
            # montant homogène : jamais fabriqués.
            'montant': None,
            'lien': None,
            # VX218 — seule `automation` est balayée par YEVNT9 aujourd'hui ;
            # champs présents pour un contrat d'API uniforme, jamais fabriqués.
            'niveau_escalade': None,
            'derniere_relance_le': None,
        })
    return out


_SOURCE_LOADERS = {
    'automation': _automation_items,
    'contrats': _contrats_items,
    'ged': _ged_items,
    'installations': _installations_items,
    'workflow': _core_workflow_items,
}


def _jours_ouvres_ecoules(depuis, company, *, aujourdhui=None):
    """ZCTR9 — nombre de jours OUVRÉS écoulés entre ``depuis`` (datetime/date)
    et aujourd'hui (borne société via ``notifications.calendar_utils``,
    FG5). ``depuis`` non-borné (None) renvoie 0. Le jour de création
    lui-même n'est pas compté (symétrique à ``ajouter_jours_ouvres``)."""
    if depuis is None:
        return 0
    from apps.notifications import calendar_utils

    d = depuis.date() if hasattr(depuis, 'date') else depuis
    today = aujourdhui or timezone.localdate()
    if d >= today:
        return 0
    count = 0
    current = d
    # Borné par construction : une demande en attente ne vit pas des années ;
    # garde-fou dur pour éviter toute boucle pathologique.
    for _ in range(3660):
        current += datetime.timedelta(days=1)
        if current > today:
            break
        if calendar_utils.is_jour_ouvre(current, company):
            count += 1
    return count


def _enrichir_urgence(items, company):
    """ZCTR9 — ajoute ``anciennete_jours`` (jours ouvrés en attente) et
    ``en_retard`` (au-delà du SLA société, défaut 3 j ouvrés — FG5 jours
    ouvrés) à chaque item, en place. Retourne la liste enrichie."""
    from apps.reporting.models import ApprobationSlaConfig

    sla_jours = ApprobationSlaConfig.sla_jours_pour(company)
    for it in items:
        anciennete = _jours_ouvres_ecoules(it.get('cree_le'), company)
        it['anciennete_jours'] = anciennete
        it['en_retard'] = anciennete >= sla_jours
    return items


_TRI_URGENCE = 'urgence'
_TRI_ANCIENNETE = 'anciennete'
_TRI_MONTANT = 'montant'
_TRIS_VALIDES = {_TRI_URGENCE, _TRI_ANCIENNETE, _TRI_MONTANT}


def _trier_items(items, trier):
    """ZCTR9 — tri des items agrégés selon ``?trier=``.

    - ``urgence`` : en retard d'abord, puis ancienneté décroissante.
    - ``anciennete`` : ancienneté décroissante (plus vieux en premier).
    - ``montant`` : demandes avec un montant connu d'abord (décroissant),
      celles sans montant (aucune source homogène ne l'expose aujourd'hui)
      en dernier, triées par ancienneté à défaut.
    Tri stable : conserve l'ordre source/id existant à valeur égale."""
    if trier == _TRI_URGENCE:
        items.sort(key=lambda it: (
            0 if it.get('en_retard') else 1, -it.get('anciennete_jours', 0)))
    elif trier == _TRI_ANCIENNETE:
        items.sort(key=lambda it: -it.get('anciennete_jours', 0))
    elif trier == _TRI_MONTANT:
        items.sort(key=lambda it: (
            it.get('montant') is None,
            -(it.get('montant') or 0),
            -it.get('anciennete_jours', 0)))
    return items


@api_view(['GET'])
@permission_classes([IsAnyRole])
def approbations_en_attente(request):
    """XKB1 — ``GET reporting/approbations-en-attente/``.

    Renvoie les demandes multi-modules EN ATTENTE, scopées à la société de
    l'utilisateur (jamais une autre société). Filtres :
      - ``?source=`` — une seule source (``automation``/``contrats``/``ged``/
        ``installations``/``workflow``).
      - ``?categorie=`` — ZCTR9, alias de ``source`` (la seule facette de
        catégorie homogène à travers les sources aujourd'hui).
      - ``?priorite=`` — ZCTR9, ne retient que les items portant cette
        priorité exacte (seule ``installations`` en expose une aujourd'hui ;
        les autres sources n'ont pas de champ priorité — aucune fabrication
        de donnée, elles sont simplement exclues du filtre).
      - ``?trier=urgence|anciennete|montant`` — ZCTR9, voir ``_trier_items``.
    Chaque item porte désormais ``anciennete_jours`` (jours ouvrés en
    attente, FG5) et ``en_retard`` (au-delà du SLA société paramétrable,
    ``ApprobationSlaConfig``, défaut 3 j ouvrés). VX218 — chaque item porte
    aussi ``niveau_escalade`` (``None``/``'relance'``/``'escalade'``) et
    ``derniere_relance_le``, reflet lecture-seule de l'état YEVNT9
    (``ApprovalReminderState``) pour que le DEMANDEUR voie le niveau
    d'escalade de sa propre demande sans devoir être admin/manager ; seule
    la source ``automation`` est balayée par ce sweep aujourd'hui, les
    autres sources renvoient ces deux champs à ``None`` (jamais fabriqué)."""
    company = _co(request.user)
    if company is None:
        return Response({'items': [], 'total': 0})

    source_filter = (
        request.query_params.get('source')
        or request.query_params.get('categorie'))
    sources = ([source_filter] if source_filter in _SOURCE_LOADERS
               else list(_SOURCE_LOADERS))

    items = []
    for source in sources:
        items.extend(_SOURCE_LOADERS[source](company))

    items = _enrichir_urgence(items, company)

    priorite_filter = request.query_params.get('priorite')
    if priorite_filter:
        items = [it for it in items if it.get('priorite') == priorite_filter]

    items.sort(key=lambda it: (it['source'], it['id']))

    trier = request.query_params.get('trier')
    if trier in _TRIS_VALIDES:
        items = _trier_items(items, trier)

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
    # VX101 — [BUG AUTH] `decider_demande_achat` (installations) et l'étape de
    # contrat ne vérifiaient AUCUN rôle au-delà de `IsAnyRole` : un commercial
    # ou un technicien pouvait approuver une réquisition d'achat ou une étape
    # de contrat. Point d'ancrage unique des 5 sources (`_decider_approbation_
    # core`) : exige le tier Responsable/Admin pour DÉCIDER (approuver/refuser)
    # une source `installations`/`contrats` — la LECTURE (`approbations_en_
    # attente`) reste ouverte à tout rôle, inchangée.
    if source in ('installations', 'contrats') and not user.is_responsable:
        return 403, {'detail': 'Réservé au Responsable ou à l\'Admin.'}
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
