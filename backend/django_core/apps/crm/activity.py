"""
Automatic lead activity logging (chatter) — server-side only.

Tracks changes to a curated set of Lead fields: on every API update the old
instance is compared to the validated new values and one LeadActivity row is
written per changed field, with human-readable labels and display values.
The acting user and the company are taken from the request, never the body.
"""
from .models import Lead, LeadActivity

# Champ suivi → libellé français affiché dans l'Historique.
TRACKED_FIELDS = {
    'stage': 'Étape',
    'owner': 'Responsable',
    'nom': 'Nom',
    'prenom': 'Prénom',
    'societe': 'Société',
    'email': 'Email',
    'telephone': 'Téléphone',
    'whatsapp': 'WhatsApp',
    'adresse': 'Adresse',
    'ville': 'Ville',
    'canal': 'Canal',
    'priorite': 'Priorité',
    'tags': 'Tags',
    'motif_perte': 'Motif de perte',
    'relance_date': 'Relance',
    'type_installation': "Type d'installation",
    'facture_hiver': 'Facture hiver',
    'facture_ete': 'Facture été',
    'ete_differente': 'Été différent',
    'conso_mensuelle_kwh': 'Conso mensuelle (kWh)',
    'pompe_cv': 'Pompe (CV)',
    'pompe_hmt_m': 'HMT (m)',
    'pompe_debit_m3h': 'Débit souhaité (m³/h)',
    'raccordement': 'Raccordement',
    'regularisation_8221': 'Régularisation 82-21',
    'type_toiture': 'Type de toiture',
    'surface_toiture_m2': 'Surface toiture (m²)',
    'orientation': 'Orientation',
    'ombrage': 'Ombrage',
    'taille_souhaitee_kwc': 'Taille souhaitée (kWc)',
    'batterie_souhaitee': 'Batterie souhaitée',
    'visite_prevue_le': 'Visite prévue le',
    'visite_effectuee': 'Visite effectuée',
}

_CHOICE_FIELDS = {
    'stage', 'canal', 'priorite', 'type_installation', 'raccordement',
    'type_toiture', 'orientation', 'ombrage', 'structure_pref',
    'batterie_souhaitee',
}

_BOOL_LABELS = {True: 'Oui', False: 'Non'}


def _display(lead: Lead, field: str, value):
    """Human-readable value for the timeline."""
    if value is None or value == '':
        return '—'
    if field in _CHOICE_FIELDS:
        choices = dict(Lead._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if isinstance(value, bool):
        return _BOOL_LABELS[value]
    if field == 'owner':
        return getattr(value, 'username', str(value))
    return str(value)


def log_creation(lead: Lead, user):
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.CREATION,
        body=f"Lead créé par {getattr(user, 'username', '?')}",
    )


def log_changes(old: Lead, new: Lead, user):
    """Compare tracked fields between the pre-save and post-save instances."""
    for field, label in TRACKED_FIELDS.items():
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val == new_val:
            continue
        LeadActivity.objects.create(
            company=new.company, lead=new, user=user,
            kind=LeadActivity.Kind.MODIFICATION,
            field=field, field_label=label,
            old_value=_display(old, field, old_val),
            new_value=_display(new, field, new_val),
        )


def log_note(lead: Lead, user, body: str) -> LeadActivity:
    return LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE, body=body,
    )
