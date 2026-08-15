"""NTMOB1 — moteur de rejeu IDEMPOTENT d'un lot d'opérations hors-ligne.

Point d'entrée unique et multi-module (`POST /offlinesync/operations/batch/`).
Le contrat de réponse est EXACTEMENT celui déjà validé par l'outbox du terminal
(`installations/sync/`) — c'est ce qui permet à la MÊME classe `Outbox` côté
frontend de vider n'importe quelle file sans le moindre code spécifique :

    {"ops": [{client_op_id, op_type, payload, queued_at?}, …]}
    → {applied, replayed, errors,
       results: [{client_op_id, op_type, module, status, result|error}, …]}

`status` vaut ``applied`` (1re application), ``replayed`` (clé déjà appliquée →
no-op, résultat mémorisé) ou ``error``. Le terminal ne retire de sa file QUE
``applied``/``replayed`` ; une op ``error`` reste chez lui, marquée, jusqu'à un
abandon EXPLICITE (VX119) — et reste journalisée ici en `rejetee`.

Multi-tenant : `company` est posée par l'appelant depuis ``request.user.company``
— jamais lue du corps. Chaque handler résout sa cible bornée société : une op
visant l'enregistrement d'une autre société est refusée comme « inconnue ».
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import registry
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
    if queued_at is not None:
        obj.date_creation = queued_at
    obj.save(update_fields=['user', 'module', 'op_type', 'payload', 'erreur',
                            'statut', 'date_creation', 'updated_at'])
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

    try:
        with transaction.atomic():
            resultat = handler(company, user, payload)
    except _ERREURS_APPLICATIVES as exc:
        # L'effet métier est intégralement annulé (point de sauvegarde), la
        # ligne de journal SURVIT avec son motif : rien ne disparaît en silence.
        obj.statut = OfflineOperation.Statut.REJETEE
        obj.erreur = _message(exc)
        obj.date_traitement = timezone.now()
        obj.save(update_fields=['statut', 'erreur', 'date_traitement',
                                'updated_at'])
        return {'client_op_id': op_id, 'op_type': op_type, 'module': module,
                'status': 'error', 'error': obj.erreur}

    obj.statut = OfflineOperation.Statut.APPLIQUEE
    obj.resultat = resultat if isinstance(resultat, dict) else {}
    obj.erreur = ''
    obj.date_traitement = timezone.now()
    obj.save(update_fields=['statut', 'resultat', 'erreur', 'date_traitement',
                            'updated_at'])
    return {'client_op_id': op_id, 'op_type': op_type, 'module': module,
            'status': 'applied', 'result': obj.resultat}


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
    applied = replayed = errors = 0
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
        else:
            errors += 1
    return {'applied': applied, 'replayed': replayed, 'errors': errors,
            'results': results}
