"""
Journal d'activité (chatter) d'un chantier — strictement le même patron que
apps/crm/activity.py. Une entrée par champ suivi modifié, libellés français,
utilisateur et société posés côté serveur.
"""
from .models import Installation, InstallationActivity

# Champ suivi → libellé français affiché dans l'Historique du chantier.
TRACKED_FIELDS = {
    'statut': 'Statut',
    'technicien_responsable': 'Technicien responsable',
    'site_adresse': 'Adresse du site',
    'site_ville': 'Ville du site',
    'puissance_installee_kwc': 'Puissance installée (kWc)',
    'raccordement': 'Raccordement',
    'type_installation': "Type d'installation",
    'date_pose_prevue': 'Date de pose prévue',
    'date_pose_reelle': 'Date de pose réelle',
    'date_mise_en_service': 'Date de mise en service',
    'date_reception': 'Date de réception',
    'date_cloture': 'Date de clôture',
    'labour_jours_estimes': 'Jours-homme estimés',
    'labour_jours_reels': 'Jours-homme réels',
    'parc_actif': 'Système actif (parc)',
    'regime_8221': 'Régime loi 82-21',
    'dossier_statut': 'Statut dossier réglementaire',
    'art33_regularisation': 'Régularisation Article 33',
    'annule': 'Annulé',
    'motif_annulation': "Motif d'annulation",
}

_CHOICE_FIELDS = {'statut', 'raccordement', 'type_installation',
                  'regime_8221', 'dossier_statut'}
_BOOL_LABELS = {True: 'Oui', False: 'Non'}


def _display(inst: Installation, field: str, value):
    """Valeur lisible pour la timeline."""
    if value is None or value == '':
        return '—'
    if field in _CHOICE_FIELDS:
        choices = dict(Installation._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if isinstance(value, bool):
        return _BOOL_LABELS[value]
    if field == 'technicien_responsable':
        return getattr(value, 'username', str(value))
    return str(value)


def log_creation(inst: Installation, user):
    InstallationActivity.objects.create(
        company=inst.company, installation=inst, user=user,
        kind=InstallationActivity.Kind.CREATION,
        body=f"Chantier créé par {getattr(user, 'username', '?')}",
    )


def log_changes(old: Installation, new: Installation, user):
    """Compare les champs suivis avant/après et écrit une ligne par changement."""
    for field, label in TRACKED_FIELDS.items():
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val == new_val:
            continue
        InstallationActivity.objects.create(
            company=new.company, installation=new, user=user,
            kind=InstallationActivity.Kind.MODIFICATION,
            field=field, field_label=label,
            old_value=_display(old, field, old_val),
            new_value=_display(new, field, new_val),
        )


def log_note(inst: Installation, user, body: str) -> InstallationActivity:
    return InstallationActivity.objects.create(
        company=inst.company, installation=inst, user=user,
        kind=InstallationActivity.Kind.NOTE, body=body,
    )
