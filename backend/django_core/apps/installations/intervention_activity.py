"""
Journal d'activité (chatter) d'une intervention — strictement le même patron
que apps/installations/activity.py (chantier). Une entrée par champ suivi
modifié, libellés français, utilisateur et société posés côté serveur.

Le statut suivi ici est celui PROPRE de l'intervention (Intervention.Statut) ;
il n'a aucun lien avec le statut chantier ni avec STAGES.py.
"""
from .models import Intervention, InterventionActivity

# Champ suivi → libellé français affiché dans l'Historique de l'intervention.
TRACKED_FIELDS = {
    'statut': 'Statut',
    'type_intervention': "Type d'intervention",
    'date_prevue': 'Date prévue',
    'date_realisee': 'Date réalisée',
    'technicien': 'Technicien',
    'camionnette': 'Camionnette',
}

_CHOICE_FIELDS = {'statut', 'type_intervention'}


def _display(field: str, value):
    """Valeur lisible pour la timeline."""
    if value is None or value == '':
        return '—'
    if field in _CHOICE_FIELDS:
        choices = dict(Intervention._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if field == 'technicien':
        return getattr(value, 'username', str(value))
    if field == 'camionnette':
        return getattr(value, 'nom', str(value))
    return str(value)


def log_creation(interv: Intervention, user):
    InterventionActivity.objects.create(
        company=interv.company, intervention=interv, user=user,
        kind=InterventionActivity.Kind.CREATION,
        body=f"Intervention créée par {getattr(user, 'username', '?')}",
    )


def log_changes(old: Intervention, new: Intervention, user):
    """Compare les champs suivis avant/après, une ligne par changement."""
    for field, label in TRACKED_FIELDS.items():
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val == new_val:
            continue
        InterventionActivity.objects.create(
            company=new.company, intervention=new, user=user,
            kind=InterventionActivity.Kind.MODIFICATION,
            field=field, field_label=label,
            old_value=_display(field, old_val),
            new_value=_display(field, new_val),
        )


def log_note(interv: Intervention, user, body: str) -> InterventionActivity:
    return InterventionActivity.objects.create(
        company=interv.company, intervention=interv, user=user,
        kind=InterventionActivity.Kind.NOTE, body=body,
    )
