"""Actions « en masse » sur les leads (multi-sélection liste + kanban).

Un seul endpoint POST /crm/leads/bulk/ {action, ids, params}. Toutes les
actions :
  - sont strictement scopées à la société de l'utilisateur (les ids étrangers
    sont silencieusement ignorés) ;
  - journalisent CHAQUE changement dans l'Historique chatter (LeadActivity),
    avec le marqueur « en masse » sur le corps de l'entrée ;
  - réutilisent les règles existantes (funnel « jamais en arrière », relance,
    perte) plutôt que de les redéclarer.

L'export .xlsx renvoie un fichier (openpyxl) — il ne modifie rien.
"""
from django.utils import timezone

from . import stages
from .activity import TRACKED_FIELDS, _display
from .models import LeadActivity
from .services import can_move_to_stage, sync_relance_activity

# Marqueur ajouté au corps de chaque entrée d'historique produite en masse.
BULK_TAG = '« en masse »'


def _log_field(lead, user, field, old_value, new_value, suffix=''):
    """Une entrée Historique de modification d'un champ, marquée en masse."""
    label = TRACKED_FIELDS.get(field, field)
    body = f"Modification {BULK_TAG}"
    if suffix:
        body = f"{body} — {suffix}"
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field=field, field_label=label,
        old_value=_display(lead, field, old_value),
        new_value=_display(lead, field, new_value),
        body=body,
    )


def _log_note(lead, user, body):
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"{body} {BULK_TAG}",
    )


def _tag_set(value):
    return [t.strip() for t in (value or '').split(',') if t.strip()]


# ─────────────────────────── actions individuelles ──────────────────────────

def _act_reassign(lead, user, params):
    from authentication.models import CustomUser
    owner_id = params.get('owner')
    new_owner = None
    if owner_id not in (None, '', 0):
        new_owner = CustomUser.objects.filter(
            id=owner_id, company=lead.company).first()
        if new_owner is None:
            return False, "Responsable inconnu."
    if lead.owner_id == (new_owner.id if new_owner else None):
        return False, None
    old = lead.owner
    lead.owner = new_owner
    lead.save(update_fields=['owner'])
    _log_field(lead, user, 'owner', old, new_owner)
    return True, None


def _act_add_tag(lead, user, params):
    tag = (params.get('tag') or '').strip()
    if not tag:
        return False, "Tag vide."
    current = _tag_set(lead.tags)
    if tag in current:
        return False, None
    old = lead.tags
    current.append(tag)
    lead.tags = ', '.join(current)[:500]
    lead.save(update_fields=['tags'])
    _log_field(lead, user, 'tags', old, lead.tags, suffix=f"ajout « {tag} »")
    return True, None


def _act_remove_tag(lead, user, params):
    tag = (params.get('tag') or '').strip()
    if not tag:
        return False, "Tag vide."
    current = _tag_set(lead.tags)
    if tag not in current:
        return False, None
    old = lead.tags
    current = [t for t in current if t != tag]
    lead.tags = ', '.join(current)[:500]
    lead.save(update_fields=['tags'])
    _log_field(lead, user, 'tags', old, lead.tags, suffix=f"retrait « {tag} »")
    return True, None


def _act_change_stage(lead, user, params):
    stage = params.get('stage')
    ok, reason = can_move_to_stage(lead, stage)
    if not ok:
        # « déjà à cette étape » n'est pas une erreur, juste un no-op.
        return False, (None if reason in (
            "Déjà à cette étape.",) else reason)
    old = lead.stage
    lead.stage = stage
    lead.save(update_fields=['stage'])
    _log_field(lead, user, 'stage', old, stage)
    return True, None


def _act_set_relance(lead, user, params):
    date = params.get('relance_date') or None
    if lead.relance_date and str(lead.relance_date) == str(date):
        return False, None
    if not lead.relance_date and not date:
        return False, None
    old = lead.relance_date
    lead.relance_date = date
    lead.save(update_fields=['relance_date'])
    _log_field(lead, user, 'relance_date', old, lead.relance_date)
    sync_relance_activity(lead, user)
    return True, None


def _act_clear_relance(lead, user, params):
    if not lead.relance_date:
        return False, None
    old = lead.relance_date
    lead.relance_date = None
    lead.save(update_fields=['relance_date'])
    _log_field(lead, user, 'relance_date', old, None)
    sync_relance_activity(lead, user)
    return True, None


def _act_flag_perdu(lead, user, params):
    motif = (params.get('motif_perte') or '').strip()
    if lead.perdu and lead.motif_perte == (motif or None):
        return False, None
    changed = []
    if not lead.perdu:
        _log_field(lead, user, 'perdu', lead.perdu, True)
        lead.perdu = True
        changed.append('perdu')
    if motif and lead.motif_perte != motif:
        _log_field(lead, user, 'motif_perte', lead.motif_perte, motif)
        lead.motif_perte = motif
        changed.append('motif_perte')
    if changed:
        lead.save(update_fields=changed)
        return True, None
    return False, None


def _act_unflag_perdu(lead, user, params):
    if not lead.perdu:
        return False, None
    _log_field(lead, user, 'perdu', lead.perdu, False)
    lead.perdu = False
    lead.save(update_fields=['perdu'])
    return True, None


def _act_archive(lead, user, params):
    if lead.is_archived:
        return False, None
    lead.is_archived = True
    lead.archived_by = user
    lead.archived_at = timezone.now()
    lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
    _log_note(lead, user, "Lead archivé")
    return True, None


def _act_unarchive(lead, user, params):
    if not lead.is_archived:
        return False, None
    lead.is_archived = False
    lead.archived_by = None
    lead.archived_at = None
    lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
    _log_note(lead, user, "Lead restauré")
    return True, None


# Actions qui modifient un lead en place : (fonction, libellé).
MUTATING_ACTIONS = {
    'reassign': _act_reassign,
    'add_tag': _act_add_tag,
    'remove_tag': _act_remove_tag,
    'change_stage': _act_change_stage,
    'set_relance': _act_set_relance,
    'clear_relance': _act_clear_relance,
    'flag_perdu': _act_flag_perdu,
    'unflag_perdu': _act_unflag_perdu,
    'archive': _act_archive,
    'unarchive': _act_unarchive,
}


def run_mutating_action(action, leads, user, params):
    """Applique une action sur une liste de leads (déjà scopés société).

    Renvoie un dict de synthèse : combien modifiés, ignorés, et les messages
    d'avertissement par lead (étape qui recule, etc.)."""
    fn = MUTATING_ACTIONS[action]
    updated, skipped, warnings = 0, 0, []
    for lead in leads:
        changed, reason = fn(lead, user, params or {})
        if changed:
            updated += 1
        else:
            skipped += 1
            if reason:
                warnings.append({'id': lead.id, 'detail': reason})
    return {'updated': updated, 'skipped': skipped, 'warnings': warnings}


# ─────────────────────────── suppression admin ──────────────────────────────

def delete_leads(leads, user):
    """Suppression DÉFINITIVE en masse (admin). Bloquée GLOBALEMENT si un seul
    lead a des devis liés — on n'orpheline jamais de pièces financières."""
    import logging
    bloquants = [le for le in leads if le.devis.exists()]
    if bloquants:
        refs = ', '.join(str(le.id) for le in bloquants[:10])
        return False, (
            "Suppression refusée : des leads sélectionnés ont des devis ou "
            f"factures liés (#{refs}). Archivez-les plutôt — rien n'est "
            "supprimé.")
    audit = logging.getLogger('crm.audit')
    count = 0
    for lead in leads:
        audit.warning(
            'BULK HARD DELETE lead id=%s "%s" par user=%s (company=%s)',
            lead.id, lead, getattr(user, 'username', '?'),
            getattr(lead, 'company_id', None))
        lead.delete()
        count += 1
    return True, count


# ─────────────────────────────── export xlsx ────────────────────────────────

_EXPORT_COLUMNS = [
    ('id', 'ID'),
    ('nom', 'Nom'),
    ('prenom', 'Prénom'),
    ('societe', 'Société'),
    ('email', 'Email'),
    ('telephone', 'Téléphone'),
    ('ville', 'Ville'),
    ('stage', 'Étape'),
    ('owner', 'Responsable'),
    ('canal', 'Canal'),
    ('priorite', 'Priorité'),
    ('tags', 'Tags'),
    ('perdu', 'Perdu'),
    ('relance_date', 'Relance'),
    ('date_creation', 'Créé le'),
]


def export_leads_xlsx(leads):
    """Construit un classeur openpyxl avec la sélection de leads. Renvoie les
    octets du fichier .xlsx. Ne modifie rien."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = 'Leads'
    ws.append([label for _, label in _EXPORT_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for lead in leads:
        row = []
        for field, _ in _EXPORT_COLUMNS:
            if field == 'stage':
                row.append(stages.STAGE_LABELS.get(lead.stage, lead.stage))
            elif field == 'owner':
                row.append(getattr(lead.owner, 'username', '') or '')
            elif field == 'perdu':
                row.append('Oui' if lead.perdu else 'Non')
            elif field == 'date_creation':
                row.append(lead.date_creation.strftime('%Y-%m-%d %H:%M')
                           if lead.date_creation else '')
            elif field == 'relance_date':
                row.append(str(lead.relance_date) if lead.relance_date else '')
            else:
                val = getattr(lead, field, '')
                row.append('' if val is None else str(val))
        ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
