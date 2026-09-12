"""
Journal d'activité (chatter) d'un ticket SAV — strictement le même patron que
apps/installations/activity.py et apps/crm/activity.py. Une entrée par champ
suivi modifié, libellés français, utilisateur et société posés côté serveur.
"""
from .models import Ticket, TicketActivity

# Champ suivi → libellé français affiché dans l'Historique du ticket.
TRACKED_FIELDS = {
    'statut': 'Statut',
    'type': 'Type',
    'priorite': 'Priorité',
    'technicien_responsable': 'Technicien responsable',
    'equipement': 'Équipement',
    'sous_garantie': 'Sous garantie',
    'date_resolution': 'Date de résolution',
    'cout': 'Coût',
    'description': 'Description',
    'annule': 'Annulé',
    'motif_annulation': "Motif d'annulation",
    # XSAV14 — taxonomie panne / cause / remède, codifiés à la résolution.
    'cause': 'Cause',
    'remede': 'Remède',
}

_CHOICE_FIELDS = {'statut', 'type', 'priorite', 'sous_garantie'}
_BOOL_LABELS = {True: 'Oui', False: 'Non'}


def _display(ticket: Ticket, field: str, value):
    """Valeur lisible pour la timeline."""
    if value is None or value == '':
        return '—'
    if field in _CHOICE_FIELDS:
        choices = dict(Ticket._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if isinstance(value, bool):
        return _BOOL_LABELS[value]
    if field == 'technicien_responsable':
        return getattr(value, 'username', str(value))
    if field == 'equipement':
        return getattr(value, 'numero_serie', None) or str(value)
    if field in ('cause', 'remede'):
        return getattr(value, 'nom', str(value))
    return str(value)


def log_creation(ticket: Ticket, user):
    TicketActivity.objects.create(
        company=ticket.company, ticket=ticket, user=user,
        kind=TicketActivity.Kind.CREATION,
        body=f"Ticket créé par {getattr(user, 'username', '?')}",
    )


def log_changes(old: Ticket, new: Ticket, user):
    """Compare les champs suivis avant/après et écrit une ligne par changement."""
    for field, label in TRACKED_FIELDS.items():
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val == new_val:
            continue
        TicketActivity.objects.create(
            company=new.company, ticket=new, user=user,
            kind=TicketActivity.Kind.MODIFICATION,
            field=field, field_label=label,
            old_value=_display(old, field, old_val),
            new_value=_display(new, field, new_val),
        )


def log_note(ticket: Ticket, user, body: str) -> TicketActivity:
    return TicketActivity.objects.create(
        company=ticket.company, ticket=ticket, user=user,
        kind=TicketActivity.Kind.NOTE, body=body,
    )


def log_appel(ticket: Ticket, user, body: str, *, outcome='',
              duree_minutes=None) -> TicketActivity:
    """NTSRV5 — journalise un APPEL SAV (durée + issue) comme interaction
    typée du chatter (``kind='appel'``). Trace MANUELLE structurée : aucune
    intégration PBX (elle exigerait un fournisseur tiers — GATED)."""
    return TicketActivity.objects.create(
        company=ticket.company, ticket=ticket, user=user,
        kind=TicketActivity.Kind.APPEL, body=body,
        outcome=outcome or '', duree_minutes=duree_minutes,
    )


def log_whatsapp(ticket: Ticket, user, body: str) -> TicketActivity:
    """NTSRV3 — journalise un message WhatsApp (canal SAV) comme interaction
    TYPÉE du chatter (``kind='whatsapp'``)."""
    return TicketActivity.objects.create(
        company=ticket.company, ticket=ticket, user=user,
        kind=TicketActivity.Kind.WHATSAPP, body=body,
    )


def log_email(ticket: Ticket, user, body: str) -> TicketActivity:
    """NTSRV1 — journalise un e-mail (entrant ou sortant) comme interaction
    TYPÉE du chatter (``kind='email'``), jamais comme note libre : l'inbox
    omnicanale distingue ainsi un échange e-mail d'un commentaire interne."""
    return TicketActivity.objects.create(
        company=ticket.company, ticket=ticket, user=user,
        kind=TicketActivity.Kind.EMAIL, body=body,
    )
