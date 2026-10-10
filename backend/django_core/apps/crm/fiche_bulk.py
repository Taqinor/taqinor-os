"""Actions en masse sur les leads (SPL3, extrait de crm/services.py : déplacement pur).

Module RACINE de la scission : il importe ``.services`` au niveau module ;
aucun module de type (a) ne l'importe et ``services`` ne le réexporte pas.
"""
from django.utils import timezone

from . import activity, stages
from .models import Canal, Lead
from .services import raison_refus_suppression
from .cadence_touche import reprendre_cadence_apres_reouverture
from .cadence_filet import assurer_prochaine_etape_apres_succes
from .cadence_plan import arreter_cadence, sync_relance_activity
from .fiche_funnel import (
    SortieSigneBloquee,
    _bulk_stage_allowed,
    _corps_whatsapp_en_masse,
    _resolve_owner,
    appliquer_stage_lead,
    desaccepter_devis_du_lead,
)
from .cadence_reponses import reattribuer_lead
from .leads_socle import MOTIF_BULK_CADENCE_ACTIVE, leads_avec_cadence_active


BULK_ACTIONS = {
    'reassign', 'add_tag', 'remove_tag', 'set_stage', 'set_canal',
    'set_priorite', 'set_relance', 'clear_relance', 'set_perdu',
    'unset_perdu', 'archive', 'unarchive', 'delete', 'plan_activity',
    'prepare_whatsapp',  # FG33 — file de click-through WhatsApp en masse
}

# Priorités valides (clés du modèle Lead.Priorite).
_PRIORITES = {'basse', 'normale', 'haute'}
# Actions réservées à l'admin (la suppression définitive l'est déjà partout).
BULK_ADMIN_ONLY = {'delete'}


def _parse_date(value):
    from datetime import date
    if isinstance(value, date):
        return value
    if not value:
        return None
    from django.utils.dateparse import parse_date
    return parse_date(str(value))


def _resolve_activity_type(company, type_id, type_nom):
    """Type d'activité cible pour une planification en masse : par id (société
    courante) sinon par nom (créé à la volée s'il manque), repli sur « À faire ».
    """
    from apps.records.models import ActivityType
    if type_id not in (None, '', 'null'):
        atype = ActivityType.objects.filter(id=type_id, company=company).first()
        if atype is not None:
            return atype
    nom = (type_nom or 'À faire').strip() or 'À faire'
    atype = ActivityType.objects.filter(company=company, nom=nom).first()
    if atype is None:
        atype = ActivityType.objects.create(company=company, nom=nom, ordre=50)
    return atype


def coerce_id_list(raw):
    """Normalise une liste d'ids reçue du client en entiers uniques.

    Accepte ints et chaînes numériques ; déduplique en préservant l'ordre.
    Lève ValueError sur un élément non entier — la vue le traduit en 400 propre
    au lieu de laisser un 500 remonter du `id__in` (PostgreSQL refuse un id
    non numérique). Sert aux endpoints en masse + WhatsApp.
    """
    if not isinstance(raw, (list, tuple)):
        raise ValueError("Liste d'identifiants invalide.")
    out = []
    seen = set()
    for item in raw:
        if isinstance(item, bool):
            raise ValueError("Identifiant invalide.")
        try:
            value = int(item)
        except (TypeError, ValueError):
            raise ValueError("Identifiant invalide.")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def apply_bulk_action(*, company, user, lead_ids, op, params, queryset=None):
    """Applique une action en masse à une sélection de leads de la société.

    Renvoie un récapitulatif : nombre mis à jour, nombre inchangés, et la liste
    des leads ignorés avec leur raison (en français). Chaque modification écrit
    une entrée Historique marquée « en masse ».

    ALEA27 — ``queryset`` (BORNÉ) : l'action HTTP ``leads/bulk/`` transmet la
    portée du viewset (société + équipe/sous-arbre) ; un id hors portée est
    IGNORÉ en silence, exactement comme un id absent (aucune fuite
    d'existence). ``None`` = la société entière (aucun appelant HTTP).
    """
    from django.db import transaction

    if op not in BULK_ACTIONS:
        raise ValueError("Action en masse inconnue.")

    lead_ids = coerce_id_list(lead_ids)
    base = queryset if queryset is not None else Lead.objects.all()
    leads = list(
        base.filter(company=company, id__in=lead_ids).order_by('id'))
    updated, unchanged, skipped = 0, 0, []

    def skip(lead, reason):
        skipped.append({'id': lead.id, 'nom': str(lead), 'reason': reason})

    # Pré-validation des paramètres dépendant de l'action.
    target_stage = None
    owner_obj = None
    tag = (params.get('tag') or '').strip() if op in ('add_tag', 'remove_tag') else None
    relance = None
    target_canal = None
    target_priorite = None
    activity_type = None
    activity_due = None
    activity_summary = None
    if op == 'set_stage':
        target_stage = params.get('stage')
        if target_stage not in stages.STAGES:
            raise ValueError("Étape cible invalide.")
    elif op == 'set_canal':
        target_canal = (params.get('canal') or '').strip()
        if not target_canal:
            raise ValueError("Canal cible vide.")
        # Le canal doit appartenir au référentiel géré (s'il existe).
        if (Canal.objects.filter(company=company).exists()
                and not Canal.objects.filter(
                    company=company, cle=target_canal, archived=False).exists()):
            raise ValueError("Canal inconnu.")
    elif op == 'set_priorite':
        target_priorite = params.get('priorite')
        if target_priorite not in _PRIORITES:
            raise ValueError("Priorité invalide.")
    elif op == 'reassign':
        owner_obj = _resolve_owner(company, params.get('owner'))
        if params.get('owner') not in (None, '', 'null') and owner_obj is None:
            raise ValueError("Responsable introuvable dans cette société.")
    elif op in ('add_tag', 'remove_tag') and not tag:
        raise ValueError("Étiquette vide.")
    elif op == 'set_relance':
        relance = _parse_date(params.get('relance_date'))
        if relance is None:
            raise ValueError("Date de relance invalide.")
    elif op == 'plan_activity':
        activity_due = _parse_date(params.get('due_date'))
        if activity_due is None:
            raise ValueError("Date d'échéance invalide.")
        activity_summary = (params.get('summary') or '').strip()
        if not activity_summary:
            raise ValueError("Intitulé de l'activité vide.")
        activity_type = _resolve_activity_type(
            company, params.get('activity_type_id'), params.get('type_nom'))

    # CAD49 — quels leads de la sélection ont une CADENCE ACTIVE ? Une seule
    # requête, avant la boucle : le bulk traite des centaines de dossiers.
    leads_a_cadence = (
        leads_avec_cadence_active(company, lead_ids)
        if op in ('set_relance', 'clear_relance') else frozenset())

    with transaction.atomic():
        for lead in leads:
            if op == 'reassign':
                if lead.owner_id == (owner_obj.id if owner_obj else None):
                    unchanged += 1
                    continue
                old = lead.owner
                # CAD54 — la réattribution a des EFFETS : le nouveau
                # responsable apprend ce qu'il hérite, et le client est
                # prévenu du changement de conseiller. `reattribuer_lead`
                # pose l'owner lui-même ; le journal « en masse » reste écrit
                # ici, comme pour les autres champs.
                reattribuer_lead(lead, user, owner_obj)
                if owner_obj is None:
                    lead.owner = None
                    lead.save(update_fields=['owner'])
                activity.log_bulk_change(lead, user, 'owner', old, owner_obj)
                sync_relance_activity(lead, user)
                updated += 1

            elif op in ('add_tag', 'remove_tag'):
                current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
                has = tag in current
                if op == 'add_tag' and has:
                    unchanged += 1
                    continue
                if op == 'remove_tag' and not has:
                    unchanged += 1
                    continue
                old = lead.tags or ''
                if op == 'add_tag':
                    current.append(tag)
                else:
                    current = [t for t in current if t != tag]
                lead.tags = ', '.join(current)[:500]
                lead.save(update_fields=['tags'])
                activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
                updated += 1

            elif op == 'set_stage':
                if lead.perdu:
                    skip(lead, "lead Perdu — étape non modifiée")
                    continue
                if not _bulk_stage_allowed(lead.stage, target_stage):
                    skip(lead, "étape déjà atteinte ou recul non autorisé")
                    continue
                old = lead.stage
                # Décision fondateur 08/10/2026 — sortir de « Signé » en
                # masse dés-accepte le devis, PAR LEAD, dans son propre point
                # de sauvegarde : un lead bloqué (facture émise, chantier
                # avancé…) est sauté avec la raison, les autres passent.
                try:
                    with transaction.atomic():
                        if old == stages.SIGNED:
                            desaccepter_devis_du_lead(lead, user)
                        # CRX20 — chemin canonique : le bulk émet enfin
                        # ``lead_stage_changed`` (playbooks NTCRM12 +
                        # séquences compta XMKT1 partaient pour un PATCH
                        # unitaire, jamais pour un bulk).
                        appliquer_stage_lead(lead, target_stage, user=user)
                        activity.log_bulk_change(
                            lead, user, 'stage', old, target_stage)
                except SortieSigneBloquee as exc:
                    lead.stage = old
                    skip(lead, exc.message)
                    continue
                # QJ9 — entrée manuelle en masse dans SIGNED : pas de CAPI ici
                # (pas de devis accepté associé ni d'attribution UTM disponible).
                updated += 1

            elif op == 'set_canal':
                if lead.canal == target_canal:
                    unchanged += 1
                    continue
                old = lead.canal
                lead.canal = target_canal
                lead.save(update_fields=['canal'])
                activity.log_bulk_change(lead, user, 'canal', old, target_canal)
                updated += 1

            elif op == 'set_priorite':
                if (lead.priorite or 'normale') == target_priorite:
                    unchanged += 1
                    continue
                old = lead.priorite
                lead.priorite = target_priorite
                lead.save(update_fields=['priorite'])
                activity.log_bulk_change(lead, user, 'priorite', old, target_priorite)
                updated += 1

            elif op == 'set_relance':
                # CAD49 — REFUSÉ sur un lead à cadence active : la date serait
                # écrasée au premier geste du plan (voir le motif).
                if lead.id in leads_a_cadence:
                    skip(lead, MOTIF_BULK_CADENCE_ACTIVE)
                    continue
                if lead.relance_date == relance:
                    unchanged += 1
                    continue
                old = lead.relance_date
                lead.relance_date = relance
                lead.save(update_fields=['relance_date'])
                activity.log_bulk_change(lead, user, 'relance_date', old, relance)
                sync_relance_activity(lead, user)
                updated += 1

            elif op == 'clear_relance':
                # CAD49 — même refus : effacer la date ne retire pas la
                # touche, elle reviendrait au premier geste du plan.
                if lead.id in leads_a_cadence:
                    skip(lead, MOTIF_BULK_CADENCE_ACTIVE)
                    continue
                if not lead.relance_date:
                    unchanged += 1
                    continue
                old = lead.relance_date
                lead.relance_date = None
                lead.save(update_fields=['relance_date'])
                activity.log_bulk_change(lead, user, 'relance_date', old, None)
                sync_relance_activity(lead, user)
                updated += 1

            elif op == 'set_perdu':
                motif = (params.get('motif') or '').strip() or None
                if not motif:
                    # MRY22 — même exigence qu'à l'unité : perdre 40 leads
                    # d'un coup SANS raison est pire, pas plus acceptable.
                    raise ValueError(
                        'Motif de perte obligatoire pour une mise en perte '
                        'en masse.')
                if lead.perdu and lead.motif_perte == motif:
                    unchanged += 1
                    continue
                old_perdu, old_motif = lead.perdu, lead.motif_perte
                lead.perdu = True
                lead.motif_perte = motif
                lead.save(update_fields=['perdu', 'motif_perte'])
                if not old_perdu:
                    activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
                    # MRY9 (c) — un lead perdu EN MASSE arrête ses relances
                    # exactement comme un lead perdu à l'unité : sans cela,
                    # une purge de 40 leads laissait 40 cadences vivantes.
                    arreter_cadence(lead, user=user,
                                    motif=motif or 'lead perdu')
                if old_motif != motif:
                    activity.log_bulk_change(lead, user, 'motif_perte', old_motif, motif)
                updated += 1

            elif op == 'unset_perdu':
                if not lead.perdu:
                    unchanged += 1
                    continue
                lead.perdu = False
                old_motif = lead.motif_perte
                lead.motif_perte = None
                lead.save(update_fields=['perdu', 'motif_perte'])
                activity.log_bulk_change(lead, user, 'perdu', True, False)
                if old_motif:
                    activity.log_bulk_change(lead, user, 'motif_perte', old_motif, None)
                # CAD107 — un lead REPRIS (dé-perdu) redevient actif : ses
                # cadences avaient été arrêtées au marquage. Les TROIS
                # chemins de réouverture passent désormais par la MÊME
                # fonction (cadence de REPRISE, filet en repli) — avant, ce
                # lot appelait le filet, le PATCH ne faisait rien et la
                # nouvelle touche entrante ne créait aucune relance.
                reprendre_cadence_apres_reouverture(
                    lead, user, origine='reprise en masse')
                updated += 1

            elif op == 'archive':
                if lead.is_archived:
                    unchanged += 1
                    continue
                lead.is_archived = True
                lead.archived_by = user
                lead.archived_at = timezone.now()
                lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
                activity.log_bulk_note(
                    lead, user,
                    f"Lead archivé en masse par {getattr(user, 'username', '?')}")
                updated += 1

            elif op == 'unarchive':
                if not lead.is_archived:
                    unchanged += 1
                    continue
                lead.is_archived = False
                lead.archived_by = None
                lead.archived_at = None
                lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
                activity.log_bulk_note(
                    lead, user,
                    f"Lead restauré en masse par {getattr(user, 'username', '?')}")
                # QJ-INVARIANT — même filet qu'au dé-perdu ci-dessus.
                assurer_prochaine_etape_apres_succes(lead, user)
                updated += 1

            elif op == 'plan_activity':
                # Crée UNE activité ouverte (records.Activity) par lead, échéance
                # + intitulé communs, assignée au responsable du lead (repli sur
                # l'acteur). Aucune dédup : planifier deux fois crée deux rappels.
                from django.contrib.contenttypes.models import ContentType
                from apps.records.models import Activity
                ct = ContentType.objects.get_for_model(lead.__class__)
                Activity.objects.create(
                    company=company, content_type=ct, object_id=lead.id,
                    activity_type=activity_type, summary=activity_summary[:255],
                    due_date=activity_due,
                    assigned_to=lead.owner or user, created_by=user)
                activity.log_bulk_note(
                    lead, user,
                    f"Activité « {activity_summary} » planifiée en masse "
                    f"pour le {activity_due.isoformat()}")
                updated += 1

            elif op == 'delete':
                # ACAL177 — la MÊME garde que la suppression unitaire.
                refus = raison_refus_suppression(lead)
                if refus is not None:
                    skip(lead, refus['detail'])
                    continue
                # VX96 — soft-delete réversible (corbeille 30 min), cohérent avec
                # la suppression unitaire : plus de destruction définitive ici.
                import logging
                logging.getLogger('crm.audit').warning(
                    'BULK SOFT DELETE lead id=%s "%s" par user=%s (company=%s)',
                    lead.id, lead, getattr(user, 'username', '?'), company.id)
                lead.soft_delete(user)
                updated += 1

            # FG33 — Préparer la file WhatsApp en masse (pas d'envoi auto)
            elif op == 'prepare_whatsapp':
                # Pas de décompte updated/unchanged — cette action retourne
                # directement en dehors de la boucle (pas de side-effect).
                pass

    # FG33 — Résultat spécial : file de click-through WhatsApp ordonné
    if op == 'prepare_whatsapp':
        from apps.ventes.utils.whatsapp import build_wa_url
        template_id = params.get('template_id')
        body_tpl = params.get('body') or ''
        tpl = None
        if template_id:
            try:
                from .models import MessageTemplate
                tpl = MessageTemplate.objects.filter(
                    company=company, id=template_id).first()
            except Exception:  # noqa: BLE001 — id illisible : corps direct
                tpl = None
        queue = []
        for lead in leads:
            # ACRM15 (C-ACRM-010) — LES gardes des relances (celles de
            # ``message_pour_etape`` / ``_lead_relancable``) : une personne
            # qui a demandé à ne plus être contactée, un lead perdu ou
            # archivé ne reçoit AUCUN message — sortis avec leur motif.
            if getattr(lead, 'ne_plus_contacter', False):
                skip(lead, 'ne plus contacter')
                continue
            if getattr(lead, 'perdu', False) or getattr(
                    lead, 'is_archived', False):
                skip(lead, 'perdu/archivé')
                continue
            phone = lead.whatsapp or lead.telephone
            if not phone:
                continue
            corps = _corps_whatsapp_en_masse(lead, tpl, body_tpl)
            wa_url = build_wa_url(phone, corps)
            queue.append({
                'lead_id': lead.id,
                'nom': str(lead),
                'phone': phone,
                'wa_url': wa_url,
            })
        return {
            'ok': True,
            'op': 'prepare_whatsapp',
            'queue': queue,
            'count': len(queue),
            'skipped': skipped,
        }

    return {
        'ok': True,
        'updated': updated,
        'unchanged': unchanged,
        'skipped': skipped,
        'total': len(leads),
    }
