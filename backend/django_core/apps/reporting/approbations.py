"""XKB1 — Boîte d'approbations centralisée (agrégateur cross-app).

Un écran unique listant TOUT ce qui attend l'approbation de l'utilisateur
courant à travers les modules, agrégé depuis les sources d'objets « en
attente » existantes :

  * ``automation.AutomationApproval`` (status pending) — via
    ``apps.automation.selectors.approvals_en_attente`` +
    ``apps.automation.services.decider_approval`` ;
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
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

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
_TRI_IA = 'ia'
_TRIS_VALIDES = {_TRI_URGENCE, _TRI_ANCIENNETE, _TRI_MONTANT, _TRI_IA}

# NTAI37 — poids du score de priorisation « ia ». PUR (aucun appel LLM) :
# une combinaison DÉTERMINISTE de trois signaux déjà présents sur chaque item
# — jamais un chiffre inventé. Plafonds explicites pour qu'un seul signal
# extrême (une ancienneté de plusieurs années, un montant à 7 chiffres) ne
# domine pas tout le score.
_IA_POIDS_RETARD = 5.0
_IA_POIDS_ESCALADE = 3.0
_IA_POIDS_RELANCE = 1.5
_IA_ANCIENNETE_PLAFOND_JOURS = 30
_IA_MONTANT_PLAFOND = 1_000_000


def _score_ia(item):
    """NTAI37 — score de priorisation DÉTERMINISTE + une raison courte en
    clair, à partir des SEULS signaux déjà portés par l'item (urgence/SLA
    ZCTR9, montant réel VX100, escalade VX218) — jamais un signal fabriqué
    pour l'occasion. Renvoie ``(score, raison)``."""
    raisons = []
    score = 0.0

    if item.get('en_retard'):
        score += _IA_POIDS_RETARD
        raisons.append(
            'en retard (%s j ouvrés)' % item.get('anciennete_jours', 0))

    niveau = item.get('niveau_escalade')
    if niveau == 'escalade':
        score += _IA_POIDS_ESCALADE
        raisons.append('escaladée')
    elif niveau == 'relance':
        score += _IA_POIDS_RELANCE
        raisons.append('déjà relancée')

    anciennete = min(item.get('anciennete_jours', 0) or 0,
                     _IA_ANCIENNETE_PLAFOND_JOURS)
    score += anciennete / _IA_ANCIENNETE_PLAFOND_JOURS

    montant = item.get('montant')
    if montant:
        score += min(float(montant), _IA_MONTANT_PLAFOND) / _IA_MONTANT_PLAFOND
        if not item.get('en_retard'):
            raisons.append('montant élevé (%s MAD)' % montant)

    if not raisons:
        raisons.append(
            'ancienneté %s j ouvrés' % item.get('anciennete_jours', 0))
    return round(score, 4), ', '.join(raisons)


def _enrichir_score_ia(items):
    """NTAI37 — ajoute ``score_ia``/``raison_ia`` à chaque item, en place.
    Suppose ``_enrichir_urgence`` déjà appliqué (lit ``en_retard``/
    ``anciennete_jours``)."""
    for it in items:
        score, raison = _score_ia(it)
        it['score_ia'] = score
        it['raison_ia'] = raison
    return items


def _trier_items(items, trier):
    """ZCTR9 — tri des items agrégés selon ``?trier=``.

    - ``urgence`` : en retard d'abord, puis ancienneté décroissante.
    - ``anciennete`` : ancienneté décroissante (plus vieux en premier).
    - ``montant`` : demandes avec un montant connu d'abord (décroissant),
      celles sans montant (aucune source homogène ne l'expose aujourd'hui)
      en dernier, triées par ancienneté à défaut.
    - ``ia`` (NTAI37) : ``score_ia`` décroissant (urgence/impact combinés) —
      voir :func:`_score_ia`.
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
    elif trier == _TRI_IA:
        _enrichir_score_ia(items)
        items.sort(key=lambda it: -it.get('score_ia', 0))
    return items


@api_view(['GET'])
@permission_classes([IsAnyRole])
def approbations_en_attente(request):
    """XKB1 — ``GET reporting/approbations-en-attente/``.

    Renvoie les demandes multi-modules EN ATTENTE, scopées à la société de
    l'utilisateur (jamais une autre société). Filtres :
      - ``?source=`` — une seule source (``automation``/``installations``/
        ``workflow``).
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
    # VX101 — [BUG AUTH] `decider_demande_achat` (installations) ne vérifiait
    # AUCUN rôle au-delà de `IsAnyRole` : un commercial ou un technicien
    # pouvait approuver une réquisition d'achat. Point d'ancrage unique des
    # sources (`_decider_approbation_core`) : exige le tier Responsable/Admin
    # pour DÉCIDER (approuver/refuser) la source `installations` — la
    # LECTURE (`approbations_en_attente`) reste ouverte à tout rôle,
    # inchangée.
    if source == 'installations' and not user.is_responsable:
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


def _approuver_en_masse_workflow(company, user, workflow_items, motif):
    """WFL16-INBOX — route les items ``source='workflow'`` d'une approbation
    groupée via ``core.workflow.approuver_en_masse`` (NTWFL16, livré) au lieu
    de les décider un par un via ``_decider_approbation_core`` : ce dernier
    n'appliquait AUCUNE garde de cohorte — un lot mélangeant deux types
    d'objet ou deux paliers différents « passait » silencieusement, alors que
    ``approuver_en_masse`` l'exige explicitement (même type d'objet + même
    palier pour tout le lot, sinon ``ValueError``).

    Renvoie une liste d'entrées ``{source, id, ok, detail}`` — même forme que
    la boucle historique, pour ne rien changer côté frontend."""
    from core import workflow as core_workflow

    resultats = []
    ids_par_item = {}
    for item in workflow_items:
        try:
            ids_par_item[item.get('id')] = int(item.get('id'))
        except (TypeError, ValueError):
            resultats.append({
                'source': 'workflow', 'id': item.get('id'), 'ok': False,
                'detail': 'Identifiant invalide.',
            })

    voulus = set(ids_par_item.values())
    steps = [
        s for s in core_workflow.pending_steps_for_company(company)
        if s.id in voulus
    ]
    trouves = {s.id for s in steps}
    for raw_id, step_id in ids_par_item.items():
        if step_id not in trouves:
            resultats.append({
                'source': 'workflow', 'id': raw_id, 'ok': False,
                'detail': 'Introuvable.',
            })

    if not steps:
        return resultats

    try:
        rapport = core_workflow.approuver_en_masse(
            steps, user=user, commentaire=motif)
    except ValueError as exc:
        # Sélection vide ou cohortes mélangées (types/paliers différents) :
        # AUCUNE étape de ce sous-lot n'a été décidée — un motif explicite,
        # jamais un succès partiel silencieux.
        for step in steps:
            resultats.append({
                'source': 'workflow', 'id': step.id, 'ok': False,
                'detail': str(exc),
            })
        return resultats

    decides = {d.pk for d in rapport['decisions']}
    exclus = {e['step_id']: e['motif'] for e in rapport['exclusions']}
    for step in steps:
        if step.id in decides:
            resultats.append({
                'source': 'workflow', 'id': step.id, 'ok': True,
                'detail': 'Décision enregistrée.',
            })
        else:
            resultats.append({
                'source': 'workflow', 'id': step.id, 'ok': False,
                'detail': exclus.get(
                    step.id, 'Exclu de l\'approbation groupée.'),
            })
    return resultats


@api_view(['POST'])
@permission_classes([IsAnyRole])
def decider_en_masse(request):
    """XKB1 — actions en masse : ``{items: [{source, id}], decision, motif}``.

    Applique la même décision à chaque item via ``_decider_approbation_core``
    (réutilise sa logique un par un, sans passer par un ``Request`` DRF
    factice) ; renvoie le détail des réussites/échecs sans jamais laisser un
    échec interrompre les suivants.

    WFL16-INBOX — EXCEPTION pour ``decision='approuver'`` : les items
    ``source='workflow'`` ne sont PLUS décidés un par un, ils passent par
    ``core.workflow.approuver_en_masse`` (garde de cohorte, voir
    ``_approuver_en_masse_workflow``). Un refus (``'refuser'``) garde le
    chemin historique — ``approuver_en_masse`` ne couvre que l'approbation."""
    company = _co(request.user)
    if company is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    items = request.data.get('items') or []
    decision = request.data.get('decision')
    motif = (request.data.get('motif') or '').strip()

    if decision == 'approuver':
        workflow_items = [it for it in items if it.get('source') == 'workflow']
        autres_items = [it for it in items if it.get('source') != 'workflow']
    else:
        workflow_items, autres_items = [], items

    resultats = []
    if workflow_items:
        resultats.extend(_approuver_en_masse_workflow(
            company, request.user, workflow_items, motif))

    for item in autres_items:
        status_code, body = _decider_approbation_core(
            company, request.user, item.get('source'), item.get('id'),
            decision, motif)
        resultats.append({
            'source': item.get('source'), 'id': item.get('id'),
            'ok': status_code == 200,
            'detail': body.get('detail'),
        })
    return Response({'resultats': resultats})


# ── NTMOB7 — approbation en un geste depuis une notification push ──────────
# Un item porte une source de ``_SOURCE_LOADERS`` — la remise devis excessive
# (garde synchrone ``_guard_discount_approval``) reste HORS PÉRIMÈTRE : elle
# ne produit aucun objet « en attente », donc rien à décider après coup depuis
# une notification (cf. docstring de tête du fichier).
def _decide_for_push(company, user, source, obj_id, decision):
    """Variante de ``_decider_approbation_core`` pour la décision via jeton de
    notification push : fournit un motif AUTOMATIQUE pour un refus — la
    notification EST l'action (NTMOB7), il n'existe aucune UI pour taper un
    motif à ce moment, contrairement à l'écran d'approbations qui l'exige."""
    motif = '' if decision == 'approuver' else 'Refusé depuis une notification push.'
    return _decider_approbation_core(company, user, source, obj_id, decision, motif)


class DecisionPushThrottle(SimpleRateThrottle):
    """Quota anonyme de la décision par jeton push, par IP.

    DURCISSEMENT (YRBAC9). L'endpoint est `AllowAny` ET MUTANT : il approuve
    des objets qui ENGAGENT DE L'ARGENT (demandes d'achat). Sans quota, un
    anonyme pouvait marteler l'endpoint
    indéfiniment — bourrage de jetons et charge gratuite sur la base à chaque
    tentative. La signature HMAC rend la devinette d'un jeton irréaliste ; le
    quota borne l'ABUS (volume) que la signature, elle, ne borne pas.

    60/heure par IP : très large pour un humain qui tape des actions de
    notification (même plusieurs collègues derrière un même NAT), dérisoire
    pour un script.
    """

    scope = 'reporting_decision_push'
    rate = '60/hour'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([DecisionPushThrottle])
def decider_approbation_via_push(request):
    """NTMOB7 — ``POST reporting/approbations-en-attente/decider-push/``.

    Corps : ``{token}`` — UNIQUEMENT le jeton signé embarqué dans l'action de
    la notification (``apps.notifications.approval_tokens``), jamais un
    ``source``/``id``/``decision`` lus du corps : tout est scellé dans le
    jeton au moment de l'émission. ``AllowAny`` DÉLIBÉRÉ : un push peut être
    tapé sur un appareil dont la session (cookie JWT) a expiré entre-temps —
    la preuve d'identité + de décision est le jeton lui-même (signé,
    court-vécu 24 h, une décision fixe par jeton), pas la session HTTP.
    Un jeton invalide/expiré/altéré ⇒ 401 sans aucune fuite d'information.
    Débit BORNÉ par `DecisionPushThrottle` (endpoint public et mutant)."""
    from apps.notifications.approval_tokens import read_approval_token
    data = read_approval_token(request.data.get('token'))
    if data is None:
        return Response({'detail': 'Jeton invalide ou expiré.'}, status=401)

    from authentication.models import CustomUser
    user = (
        CustomUser.objects
        .filter(pk=data['u'], is_active=True)
        .select_related('company', 'role')
        .first()
    )
    if user is None:
        return Response({'detail': 'Compte introuvable.'}, status=401)

    status_code, body = _decide_for_push(
        _co(user), user, data['s'], data['i'], data['d'])
    return Response(body, status=status_code)
