"""NTMOB1 — moteur de rejeu IDEMPOTENT d'un lot d'opérations hors-ligne.

Point d'entrée unique et multi-module (`POST /offlinesync/operations/batch/`).
Le contrat de réponse est EXACTEMENT celui déjà validé par l'outbox du terminal
(`installations/sync/`) — c'est ce qui permet à la MÊME classe `Outbox` côté
frontend de vider n'importe quelle file sans le moindre code spécifique :

    {"ops": [{client_op_id, op_type, payload, queued_at?}, …]}
    → {applied, replayed, errors, conflicts,
       results: [{client_op_id, op_type, module, status, result|error}, …]}

`status` vaut ``applied`` (1re application), ``replayed`` (clé déjà appliquée →
no-op, résultat mémorisé), ``conflict`` (NTMOB2 — la cible a bougé, rien n'a été
appliqué) ou ``error``. Le terminal ne retire de sa file QUE
``applied``/``replayed`` ; une op ``error`` reste chez lui, marquée, jusqu'à un
abandon EXPLICITE (VX119) — et reste journalisée ici en `rejetee`.

NTMOB2 — un ``conflict`` porte AUSSI une clé ``error`` (le message FR) : un
terminal antérieur, qui ne connaît que applied/replayed, garde donc l'op dans sa
file avec ce message au lieu de la perdre. L'arbitrage, lui, se fait côté
serveur (``services.resoudre_conflit``) et n'écrase JAMAIS en silence.

Multi-tenant : `company` est posée par l'appelant depuis ``request.user.company``
— jamais lue du corps. Chaque handler résout sa cible bornée société : une op
visant l'enregistrement d'une autre société est refusée comme « inconnue ».
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import conflicts, registry
from .models import OfflineOperation
from .registry import OfflineOpError

# Plafond de lot — borne défensive contre un terminal resté hors-ligne des
# jours. Identique au `maxBatch` par défaut de l'outbox côté frontend : le
# terminal renvoie le reste au flush suivant.
MAX_BATCH = 200

# Erreurs applicatives ATTENDUES d'un handler : elles refusent l'op proprement
# (journalisée `rejetee`, rejouable) sans jamais interrompre le lot. Une panne
# réelle (bug, base indisponible) continue de remonter en 500 — on ne maquille
# pas un défaut serveur en « op refusée ».
_ERREURS_APPLICATIVES = (
    OfflineOpError, DjangoValidationError, ValueError, TypeError, KeyError)


def _horodatage_terminal(op):
    """Date de mise en file côté terminal (facultative), toujours en aware."""
    brut = op.get('queued_at') or op.get('date_creation')
    if not brut:
        return None
    try:
        dt = parse_datetime(brut) if isinstance(brut, str) else None
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt


def _message(exc):
    """Message FR prêt à afficher, quel que soit le type d'erreur applicative."""
    if isinstance(exc, DjangoValidationError):
        return ' '.join(exc.messages) or 'Opération refusée.'
    return str(exc) or 'Opération refusée.'


def _journaliser(company, user, op_id, module, op_type, payload, queued_at):
    """Crée (ou reprend) la ligne de journal de cette clé d'idempotence.

    Une clé déjà APPLIQUÉE est renvoyée telle quelle (le rejeu ne réécrit
    jamais un résultat mémorisé). Une clé refusée/en attente est REPRISE : son
    corps est rafraîchi et son motif de refus effacé, car le terminal a pu la
    corriger avant de la rejouer."""
    obj = OfflineOperation.objects.filter(
        company=company, client_op_id=op_id).first()
    if obj is None:
        try:
            with transaction.atomic():
                obj = OfflineOperation.objects.create(
                    company=company, user=user, module=module, op_type=op_type,
                    payload=payload, client_op_id=op_id,
                    statut=OfflineOperation.Statut.EN_ATTENTE,
                    date_creation=queued_at)
        except IntegrityError:
            # Course entre deux flushs concurrents du même terminal : l'autre a
            # gagné, on reprend SA ligne (la contrainte d'unicité par société
            # garantit qu'il n'y en a qu'une).
            obj = OfflineOperation.objects.filter(
                company=company, client_op_id=op_id).first()
        return obj
    if obj.statut == OfflineOperation.Statut.APPLIQUEE:
        return obj
    obj.user = user
    obj.module = module
    obj.op_type = op_type
    obj.payload = payload
    obj.erreur = ''
    obj.statut = OfflineOperation.Statut.EN_ATTENTE
    # NTMOB2 — une op REPRISE repart d'une page blanche : le conflit et
    # l'arbitrage d'une tentative précédente ne doivent pas rester collés à un
    # corps qui a changé (l'audit de l'ancienne décision vit dans l'historique
    # de la ligne, pas dans un champ devenu faux).
    obj.conflit = {}
    obj.resolution = ''
    obj.date_resolution = None
    if queued_at is not None:
        obj.date_creation = queued_at
    obj.save(update_fields=['user', 'module', 'op_type', 'payload', 'erreur',
                            'statut', 'conflit', 'resolution',
                            'date_resolution', 'date_creation', 'updated_at'])
    return obj


def _apply_one(company, user, op):
    """Applique UNE opération. Ne lève jamais sur une erreur applicative."""
    op_id = str(op.get('client_op_id') or '').strip()
    op_type = str(op.get('op_type') or '').strip()
    if not op_id:
        return {'client_op_id': op_id, 'op_type': op_type, 'module': '',
                'status': 'error', 'error': 'client_op_id manquant.'}
    entree = registry.get(op_type)
    if entree is None:
        # `op_type` inconnu : pas de module à journaliser (et rien n'a été
        # tenté). L'op reste chez le terminal, marquée — jamais perdue.
        return {'client_op_id': op_id, 'op_type': op_type, 'module': '',
                'status': 'error',
                'error': f'op_type inconnu : {op_type}.'}
    module, handler = entree
    payload = op.get('payload') or {}
    if not isinstance(payload, dict):
        return {'client_op_id': op_id, 'op_type': op_type, 'module': module,
                'status': 'error', 'error': '« payload » doit être un objet.'}

    obj = _journaliser(company, user, op_id, module, op_type, payload,
                       _horodatage_terminal(op))
    if obj is None:  # pragma: no cover — course perdue ET ligne introuvable
        return {'client_op_id': op_id, 'op_type': op_type, 'module': module,
                'status': 'error', 'error': 'Opération non journalisable.'}
    if obj.statut == OfflineOperation.Statut.APPLIQUEE:
        # REJEU : on renvoie le résultat mémorisé SANS ré-appliquer l'effet.
        return {'client_op_id': op_id, 'op_type': obj.op_type,
                'module': obj.module, 'status': 'replayed',
                'result': obj.resultat}

    # ── NTMOB2 — LA CIBLE A-T-ELLE BOUGÉ DEPUIS LA MISE EN FILE ? ──────────
    # Garde OPT-IN : elle ne s'arme que si l'op_type déclare un resolveur ET
    # que le terminal a transmis la version qu'il avait lue. Sans cela, rien ne
    # change (comportement NTMOB1 au bit près).
    divergence = _detecter_conflit(company, op_type, payload)
    if divergence is not None:
        obj.statut = OfflineOperation.Statut.CONFLIT
        obj.conflit = divergence
        obj.erreur = conflicts.MESSAGE
        obj.date_traitement = timezone.now()
        obj.save(update_fields=['statut', 'conflit', 'erreur',
                                'date_traitement', 'updated_at'])
        # `error` est renseignée EN PLUS de `status` : un terminal antérieur à
        # NTMOB2 ne connaît que applied/replayed, garde donc l'op dans sa file
        # avec ce message — jamais une disparition silencieuse.
        return {'client_op_id': op_id, 'op_type': op_type, 'module': module,
                'status': 'conflict', 'error': obj.erreur,
                'conflit': divergence}

    return _executer(company, user, obj)


def _detecter_conflit(company, op_type, payload):
    """``{champ, base, serveur}`` si la cible de l'op a été modifiée ailleurs.

    ``None`` dès qu'un maillon manque : pas de resolveur déclaré, pas de version
    de base transmise, cible introuvable (le handler la refusera avec SON
    message), ou resolveur en erreur — un conflit ne se DEVINE jamais."""
    resolveur = registry.resolveur(op_type)
    if resolveur is None:
        return None
    if conflicts.version_base(payload) is None:
        return None
    try:
        cible = resolveur(company, payload)
    except _ERREURS_APPLICATIVES:
        return None
    return conflicts.detecter(cible, payload)


def _executer(company, user, obj):
    """Applique (ou refuse) l'opération journalisée ``obj`` et la met à jour.

    Chemin d'application UNIQUE : le rejeu de lot et l'arbitrage explicite d'un
    conflit (NTMOB2) passent tous deux par ici — un seul endroit décide de ce
    que devient une op."""
    entree = registry.get(obj.op_type)
    if entree is None:  # pragma: no cover — op_type retiré entre-temps
        return {'client_op_id': obj.client_op_id, 'op_type': obj.op_type,
                'module': obj.module, 'status': 'error',
                'error': f'op_type inconnu : {obj.op_type}.'}
    _module, handler = entree
    try:
        with transaction.atomic():
            resultat = handler(company, user, obj.payload or {})
    except _ERREURS_APPLICATIVES as exc:
        # L'effet métier est intégralement annulé (point de sauvegarde), la
        # ligne de journal SURVIT avec son motif : rien ne disparaît en silence.
        obj.statut = OfflineOperation.Statut.REJETEE
        obj.erreur = _message(exc)
        obj.date_traitement = timezone.now()
        obj.save(update_fields=['statut', 'erreur', 'date_traitement',
                                'updated_at'])
        return {'client_op_id': obj.client_op_id, 'op_type': obj.op_type,
                'module': obj.module, 'status': 'error', 'error': obj.erreur}

    obj.statut = OfflineOperation.Statut.APPLIQUEE
    obj.resultat = resultat if isinstance(resultat, dict) else {}
    obj.erreur = ''
    obj.date_traitement = timezone.now()
    obj.save(update_fields=['statut', 'resultat', 'erreur', 'date_traitement',
                            'updated_at'])
    return {'client_op_id': obj.client_op_id, 'op_type': obj.op_type,
            'module': obj.module, 'status': 'applied', 'result': obj.resultat}


def apply_batch(company, user, ops):
    """Applique un lot d'opérations hors-ligne, dans l'ordre, idempotemment.

    Renvoie ``{applied, replayed, errors, results}``. Lève ``ValueError`` si
    `ops` n'est pas une liste ou dépasse ``MAX_BATCH`` (le terminal renverra le
    reste au flush suivant)."""
    if not isinstance(ops, list):
        raise ValueError('« ops » doit être une liste.')
    if len(ops) > MAX_BATCH:
        raise ValueError(
            f'Lot trop grand ({len(ops)} > {MAX_BATCH}). '
            'Renvoyez le reste au prochain flush.')
    results = []
    applied = replayed = errors = conflicts_n = 0
    for op in ops:
        if not isinstance(op, dict):
            results.append({'status': 'error', 'error': 'Opération invalide.'})
            errors += 1
            continue
        res = _apply_one(company, user, op)
        results.append(res)
        if res['status'] == 'applied':
            applied += 1
        elif res['status'] == 'replayed':
            replayed += 1
        elif res['status'] == 'conflict':
            # NTMOB2 — compté À PART d'un refus : un conflit n'est pas une
            # erreur du terminal, c'est un arbitrage qui attend un humain.
            conflicts_n += 1
        else:
            errors += 1
    return {'applied': applied, 'replayed': replayed, 'errors': errors,
            'conflicts': conflicts_n, 'results': results}


# Arbitrages acceptés (NTMOB2) — aucun autre mot n'ouvre le chemin d'écriture.
CHOIX_CONFLIT = ('mienne', 'serveur', 'fusion')


def resoudre_conflit(company, user, operation, choix, payload=None):
    """NTMOB2 — tranche EXPLICITEMENT un conflit et applique la décision.

    ``choix`` :
      * ``mienne``  — la version du terminal l'emporte : l'op est appliquée
        telle quelle (elle écrase la version serveur, mais parce qu'un humain
        l'a demandé) ;
      * ``serveur`` — la version du serveur est conservée : l'op N'EST PAS
        appliquée et reste au journal, motif à l'appui ;
      * ``fusion``  — un ``payload`` fusionné à la main remplace celui de l'op,
        puis l'op est appliquée.

    Lève ``ValueError`` (message FR) sur un choix inconnu, une op qui n'est pas
    en conflit, ou une fusion sans corps. La garde de version n'est PAS rejouée :
    c'est tout l'objet de l'arbitrage."""
    if choix not in CHOIX_CONFLIT:
        raise ValueError(
            f'Arbitrage inconnu « {choix} » '
            f'(attendus : {", ".join(CHOIX_CONFLIT)}).')
    if operation.statut != OfflineOperation.Statut.CONFLIT:
        raise ValueError("Cette opération n'est pas en conflit.")
    maintenant = timezone.now()

    if choix == 'serveur':
        operation.statut = OfflineOperation.Statut.REJETEE
        operation.erreur = ('Version du serveur conservée '
                            '(arbitrage explicite).')
        operation.resolution = OfflineOperation.Resolution.SERVEUR
        operation.date_resolution = maintenant
        operation.resolu_par = user
        operation.date_traitement = maintenant
        operation.save(update_fields=[
            'statut', 'erreur', 'resolution', 'date_resolution', 'resolu_par',
            'date_traitement', 'updated_at'])
        return {'client_op_id': operation.client_op_id,
                'op_type': operation.op_type, 'module': operation.module,
                'status': 'error', 'error': operation.erreur}

    if choix == 'fusion':
        if not isinstance(payload, dict) or not payload:
            raise ValueError('Une fusion manuelle exige un corps fusionné.')
        operation.payload = payload
        operation.save(update_fields=['payload', 'updated_at'])

    operation.resolution = (OfflineOperation.Resolution.FUSION
                            if choix == 'fusion'
                            else OfflineOperation.Resolution.MIENNE)
    operation.date_resolution = maintenant
    operation.resolu_par = user
    operation.save(update_fields=['resolution', 'date_resolution',
                                  'resolu_par', 'updated_at'])
    # L'application peut encore ÉCHOUER (cible supprimée entre-temps, corps
    # invalide) : ``_executer`` la journalise alors ``rejetee`` avec son motif,
    # l'arbitrage restant tracé. Jamais un succès annoncé sans effet.
    return _executer(company, user, operation)
