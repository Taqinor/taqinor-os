"""N91/F21 — synchronisation IDEMPOTENTE de la capture terrain hors-ligne.

Le terminal (PWA) file localement chaque action de la capture terrain quand le
réseau est mauvais, puis POST le lot au point de synchro à la reconnexion. Ce
module applique ce lot de façon SÛRE À REJOUER :

  * chaque opération porte une **clé d'idempotence** (`client_op_id`, un UUID
    généré côté client) ;
  * la 1re application enregistre son résultat dans ``FieldOp`` (journal de
    dédup, scopé société + utilisateur) ;
  * **rejouer la même clé est un no-op** : on renvoie le résultat mémorisé sans
    ré-appliquer l'effet ;
  * sur des opérations contradictoires (terminaux qui se reconnectent dans le
    désordre), la dernière appliquée gagne (**last-write-wins**) — c'est le
    comportement naturel des handlers, qui posent un état (cocher = bool, statut
    = horodatage), jamais un incrément.

Couvre TOUT le flux intervention (F21) + la checklist chantier et la signature
PV (N91) : préparation (cocher matériel/outil), check-in GPS, n° de série,
matériel consommé (ligne), réserves, sign-off sécurité, signature client, et la
checklist du chantier. Les PHOTOS et MÉMOS VOCAUX (binaires) ne transitent PAS
par ce lot JSON : l'outbox les téléverse via les endpoints multipart existants
quand le réseau revient (l'upload binaire est lui-même rejouable par sa propre
clé applicative). Ici on synchronise les DONNÉES de champ structurées.

Multi-tenant : la société est posée côté serveur depuis ``user.company`` ;
JAMAIS lue du corps. Une cible (intervention/chantier) hors-société est rejetée
proprement (l'op échoue mais ne casse pas le lot). Additif — la machine à états
de l'intervention n'est jamais touchée (séparée du chantier et de STAGES.py).
"""
from django.db import transaction
from django.utils import timezone

from .models import (
    ChantierChecklistItem, ComponentSerial, FieldOp, Installation,
    Intervention,
)
from . import field_capture, field_services, intervention_activity


# Plafond de lot : borne défensive contre un terminal qui aurait accumulé des
# milliers d'ops (poste hors-ligne plusieurs jours). Le terminal renverra le
# reste au prochain flush.
MAX_BATCH = 200


class FieldOpError(Exception):
    """Erreur applicative d'une opération (cible inconnue, corps invalide…).
    N'interrompt PAS le lot : l'op est marquée en échec et le terminal pourra
    la rejouer après correction (elle n'est jamais mémorisée comme succès)."""


# ── Résolution scopée société des cibles ─────────────────────────────────────
def _intervention(company, payload):
    iv_id = payload.get('intervention')
    iv = (Intervention.objects
          .filter(company=company, id=iv_id)
          .select_related('installation').first())
    if iv is None:
        raise FieldOpError('Intervention inconnue.')
    return iv


def _chantier(company, payload):
    inst = (Installation.objects
            .filter(company=company, id=payload.get('chantier')).first())
    if inst is None:
        raise FieldOpError('Chantier inconnu.')
    return inst


# ── Handlers — un par op_type. Chacun POSE un état (last-write-wins). ─────────
def _h_depart_depot(company, user, payload):
    iv = _intervention(company, payload)
    iv.depart_depot_le = timezone.now()
    iv.save(update_fields=['depart_depot_le'])
    intervention_activity.log_note(iv, user, 'Départ dépôt enregistré (synchro hors-ligne).')
    return {'intervention': iv.id, 'depart_depot_le': iv.depart_depot_le.isoformat()}


def _h_checkin(company, user, payload):
    iv = _intervention(company, payload)
    iv.arrivee_site_le = timezone.now()
    fields = ['arrivee_site_le']
    lat, lng = payload.get('lat'), payload.get('lng')
    if lat not in (None, '') and lng not in (None, ''):
        try:
            iv.arrivee_gps_lat = round(float(lat), 6)
            iv.arrivee_gps_lng = round(float(lng), 6)
            fields += ['arrivee_gps_lat', 'arrivee_gps_lng']
        except (TypeError, ValueError):
            raise FieldOpError('Coordonnées invalides.')
    iv.save(update_fields=fields)
    intervention_activity.log_note(iv, user, 'Arrivée sur site enregistrée (synchro hors-ligne).')
    return {'intervention': iv.id, 'arrivee_site_le': iv.arrivee_site_le.isoformat()}


def _h_retour(company, user, payload):
    iv = _intervention(company, payload)
    iv.retour_depot_le = timezone.now()
    iv.save(update_fields=['retour_depot_le'])
    intervention_activity.log_note(iv, user, 'Retour dépôt enregistré (synchro hors-ligne).')
    return {'intervention': iv.id, 'retour_depot_le': iv.retour_depot_le.isoformat()}


def _h_cocher_materiel(company, user, payload):
    iv = _intervention(company, payload)
    prep = field_services.ensure_preparation(iv)
    ligne = prep.materiel.filter(id=payload.get('ligne')).first()
    if ligne is None:
        raise FieldOpError('Ligne inconnue.')
    charge = bool(payload.get('charge', True))
    ligne.charge = charge
    ligne.save(update_fields=['charge'])
    if not charge and prep.tout_charge:
        prep.tout_charge = False
        prep.save(update_fields=['tout_charge'])
    return {'ligne': ligne.id, 'charge': ligne.charge}


def _h_cocher_outil(company, user, payload):
    iv = _intervention(company, payload)
    prep = field_services.ensure_preparation(iv)
    ligne = prep.outils.filter(id=payload.get('ligne')).first()
    if ligne is None:
        raise FieldOpError('Ligne inconnue.')
    coche = bool(payload.get('coche', True))
    ligne.coche = coche
    ligne.save(update_fields=['coche'])
    if not coche and prep.tout_charge:
        prep.tout_charge = False
        prep.save(update_fields=['tout_charge'])
    return {'ligne': ligne.id, 'coche': ligne.coche}


def _h_serial(company, user, payload):
    """F9 — relève un n° de série (sans photo : la plaque est téléversée à part
    par son endpoint multipart quand le réseau revient). N° vide accepté."""
    produit = None
    produit_id = payload.get('produit')
    if produit_id:
        from apps.stock.selectors import get_produit_scoped
        produit = get_produit_scoped(company, produit_id)
        if produit is None:
            raise FieldOpError('Produit inconnu.')
    iv = _intervention(company, payload)
    serial = ComponentSerial.objects.create(
        company=company, intervention=iv, produit=produit,
        designation=(payload.get('designation') or '').strip(),
        slot_cle=(payload.get('slot') or '').strip(),
        numero_serie=(payload.get('numero_serie') or '').strip(),
        created_by=user)
    return {'serial': serial.id, 'numero_serie': serial.numero_serie}


def _h_consommation_ligne(company, user, payload):
    """F11 — pose la quantité réellement utilisée d'une ligne de consommation
    (last-write-wins : on remplace, jamais d'incrément). Ne valide PAS la
    réconciliation (la validation reste une action en ligne explicite)."""
    iv = _intervention(company, payload)
    cons = field_capture.ensure_consommation(iv)
    ligne = cons.lignes.filter(id=payload.get('ligne')).first()
    if ligne is None:
        raise FieldOpError('Ligne de consommation inconnue.')
    from decimal import Decimal, InvalidOperation
    if 'quantite_utilisee' in payload:
        try:
            ligne.quantite_utilisee = Decimal(str(payload.get('quantite_utilisee')))
        except (InvalidOperation, TypeError, ValueError):
            raise FieldOpError('Quantité invalide.')
    if 'justification' in payload:
        ligne.justification = (payload.get('justification') or '').strip()
    ligne.save(update_fields=['quantite_utilisee', 'justification'])
    return {'ligne': ligne.id,
            'quantite_utilisee': str(ligne.quantite_utilisee)}


def _h_reserve(company, user, payload):
    """F16 — crée une réserve (punch-list). Idempotente par sa clé d'op."""
    iv = _intervention(company, payload)
    from .models import Reserve
    reserve = Reserve.objects.create(
        company=company, intervention=iv,
        description=(payload.get('description') or '').strip(),
        created_by=user)
    return {'reserve': reserve.id}


def _h_cocher_safety(company, user, payload):
    iv = _intervention(company, payload)
    signoff = field_capture.ensure_safety_signoff(iv)
    item = signoff.items.filter(cle=payload.get('cle')).first()
    if item is None:
        raise FieldOpError('Consigne inconnue.')
    coche = bool(payload.get('coche', True))
    item.coche = coche
    item.coche_par = user if coche else None
    item.coche_le = timezone.now() if coche else None
    item.save(update_fields=['coche', 'coche_par', 'coche_le'])
    return {'cle': item.cle, 'coche': item.coche}


def _h_signer_client(company, user, payload):
    """N91 — signature PV de réception / intervention. Last-write-wins : la
    dernière signature synchronisée écrase (le terminal n'en file qu'une)."""
    iv = _intervention(company, payload)
    sig = (payload.get('signature_client') or '').strip()
    if not sig:
        raise FieldOpError('Signature vide.')
    iv.signature_client = sig
    nom = (payload.get('signataire_nom') or '').strip()
    if nom:
        iv.signataire_nom = nom
    iv.signe_le = timezone.now()
    iv.save(update_fields=['signature_client', 'signataire_nom', 'signe_le'])
    intervention_activity.log_note(
        iv, user, f"Signature client enregistrée ({nom or 'anonyme'}, synchro hors-ligne).")
    return {'intervention': iv.id, 'signe_le': iv.signe_le.isoformat()}


def _h_cocher_checklist(company, user, payload):
    """N91 — coche/décoche une étape de la checklist CHANTIER (last-write-wins).
    Ne fait PAS la capture de série ici (les séries passent par op `serial`)."""
    from .services import ensure_checklist_items
    inst = _chantier(company, payload)
    ensure_checklist_items(inst)
    item = inst.checklist.filter(cle=payload.get('cle')).first()
    if item is None:
        raise FieldOpError('Étape inconnue.')
    fait = bool(payload.get('fait', True))
    item.fait = fait
    item.fait_par = user if fait else None
    item.fait_le = timezone.now() if fait else None
    item.save(update_fields=['fait', 'fait_par', 'fait_le'])
    return {'cle': item.cle, 'fait': item.fait}


# op_type → (handler, target_type, payload-key-pour-target_id)
FIELD_OP_HANDLERS = {
    'intervention.depart_depot': (_h_depart_depot, 'intervention', 'intervention'),
    'intervention.checkin': (_h_checkin, 'intervention', 'intervention'),
    'intervention.retour': (_h_retour, 'intervention', 'intervention'),
    'intervention.cocher_materiel': (_h_cocher_materiel, 'intervention', 'intervention'),
    'intervention.cocher_outil': (_h_cocher_outil, 'intervention', 'intervention'),
    'intervention.serial': (_h_serial, 'intervention', 'intervention'),
    'intervention.consommation_ligne': (_h_consommation_ligne, 'intervention', 'intervention'),
    'intervention.reserve': (_h_reserve, 'intervention', 'intervention'),
    'intervention.cocher_safety': (_h_cocher_safety, 'intervention', 'intervention'),
    'intervention.signer_client': (_h_signer_client, 'intervention', 'intervention'),
    'chantier.cocher_checklist': (_h_cocher_checklist, 'chantier', 'chantier'),
}


def _apply_one(company, user, op):
    """Applique UNE opération de façon idempotente. Renvoie un dict de statut :
    {client_op_id, op_type, status: applied|replayed|error, result|error}.

    La transaction par-op garantit qu'un échec n'écrit RIEN (ni effet métier ni
    journal FieldOp) → le terminal peut rejouer la même clé après correction."""
    op_id = (op.get('client_op_id') or '').strip()
    op_type = (op.get('op_type') or '').strip()
    if not op_id:
        return {'client_op_id': op_id, 'op_type': op_type,
                'status': 'error', 'error': 'client_op_id manquant.'}
    if op_type not in FIELD_OP_HANDLERS:
        return {'client_op_id': op_id, 'op_type': op_type,
                'status': 'error', 'error': f'op_type inconnu : {op_type}.'}

    # REJEU : la même clé d'un même locataire ne s'applique qu'une fois → on
    # renvoie le résultat mémorisé SANS rejouer l'effet (no-op idempotent).
    existing = FieldOp.objects.filter(
        company=company, client_op_id=op_id, ok=True).first()
    if existing is not None:
        return {'client_op_id': op_id, 'op_type': existing.op_type,
                'status': 'replayed', 'result': existing.result}

    handler, target_type, target_key = FIELD_OP_HANDLERS[op_type]
    payload = op.get('payload') or {}
    try:
        with transaction.atomic():
            result = handler(company, user, payload)
            FieldOp.objects.create(
                company=company, client_op_id=op_id, op_type=op_type,
                target_type=target_type,
                target_id=payload.get(target_key) if isinstance(
                    payload.get(target_key), int) else None,
                result=result, ok=True, created_by=user)
        return {'client_op_id': op_id, 'op_type': op_type,
                'status': 'applied', 'result': result}
    except FieldOpError as exc:
        # Erreur applicative attendue (cible inconnue, corps invalide) : l'op
        # n'est pas mémorisée → rejouable. Le lot CONTINUE.
        return {'client_op_id': op_id, 'op_type': op_type,
                'status': 'error', 'error': str(exc)}


def apply_batch(company, user, ops):
    """N91/F21 — applique un lot d'opérations de capture terrain, dans l'ordre,
    de façon idempotente et company-scopée. Renvoie un dict :
        {applied, replayed, errors, results: [<statut par op>]}.

    `company` est posé par l'appelant depuis `user.company` (jamais le corps).
    Lève ValueError si `ops` n'est pas une liste ou dépasse MAX_BATCH."""
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
    return {'applied': applied, 'replayed': replayed,
            'errors': errors, 'results': results}
