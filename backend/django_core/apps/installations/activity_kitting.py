"""
XMFG4 — Journal d'activité (chatter) d'un ordre d'assemblage — même patron que
apps/installations/activity.py (chantiers) / apps/crm/activity.py (leads). Une
entrée par champ suivi modifié, libellés français, utilisateur et société posés
côté serveur.
"""
from .models import OrdreAssemblage, OrdreAssemblageActivity

TRACKED_FIELDS = {
    'statut': 'Statut',
    'date_prevue': 'Date prévue',
    'responsable': 'Responsable',
    'quantite': 'Quantité',
    'quantite_produite': 'Quantité produite',
    'motif_annulation': "Motif d'annulation",
}

_CHOICE_FIELDS = {'statut'}


def _display(ordre: OrdreAssemblage, field: str, value):
    if value is None or value == '':
        return '—'
    if field in _CHOICE_FIELDS:
        choices = dict(OrdreAssemblage._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if field == 'responsable':
        return getattr(value, 'username', str(value))
    return str(value)


def log_creation(ordre: OrdreAssemblage, user):
    OrdreAssemblageActivity.objects.create(
        company=ordre.company, ordre=ordre, user=user,
        kind=OrdreAssemblageActivity.Kind.CREATION,
        body=f"Ordre créé par {getattr(user, 'username', '?')}",
    )


def log_changes(old: OrdreAssemblage, new: OrdreAssemblage, user):
    """Compare les champs suivis avant/après et écrit une ligne par changement."""
    for field, label in TRACKED_FIELDS.items():
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val == new_val:
            continue
        OrdreAssemblageActivity.objects.create(
            company=new.company, ordre=new, user=user,
            kind=OrdreAssemblageActivity.Kind.MODIFICATION,
            field=field, field_label=label,
            old_value=_display(old, field, old_val),
            new_value=_display(new, field, new_val),
        )


def log_note(ordre: OrdreAssemblage, user, body: str) -> OrdreAssemblageActivity:
    return OrdreAssemblageActivity.objects.create(
        company=ordre.company, ordre=ordre, user=user,
        kind=OrdreAssemblageActivity.Kind.NOTE, body=body,
    )
