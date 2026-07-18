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
    'perdu': 'Perdu',
    'motif_perte': 'Motif de perte',
    'relance_date': 'Relance',
    'type_installation': "Type d'installation",
    'facture_hiver': 'Facture hiver',
    'facture_ete': 'Facture été',
    'ete_differente': 'Été différent',
    'conso_mensuelle_kwh': 'Conso mensuelle (kWh)',
    'tranche_onee': 'Tarif / tranche ONEE',
    'pompe_cv': 'Pompe (CV)',
    'pompe_hmt_m': 'HMT (m)',
    'pompe_debit_m3h': 'Débit souhaité (m³/h)',
    'raccordement': 'Raccordement',
    'regularisation_8221': 'Régularisation 82-21',
    'type_toiture': 'Type de toiture',
    'surface_toiture_m2': 'Surface toiture (m²)',
    'orientation': 'Orientation',
    'inclinaison_deg': 'Inclinaison (°)',
    'ombrage': 'Ombrage',
    'ombrage_notes': 'Notes ombrage',
    'nb_etages': 'Étages / hauteur',
    'structure_pref': 'Structure',
    'taille_souhaitee_kwc': 'Taille souhaitée (kWc)',
    'batterie_souhaitee': 'Batterie souhaitée',
    'gps_lat': 'GPS latitude',
    'gps_lng': 'GPS longitude',
    'visite_prevue_le': 'Visite prévue le',
    'visite_effectuee': 'Visite effectuée',
    'visite_notes': 'Notes de visite',
    # LW27 — champs de pilotage réel absents jusque-là de l'allowlist (~36
    # champs) : forecast pondéré (montant_estime/date_cloture_prevue),
    # qualification site QK1 (distributeur/roof_age/ownership/
    # project_timeline/financing_intent), champs site pro QW2 (facility_type/
    # site_count/visit_window_part/visit_window_week). JAMAIS utm/meta_ad/
    # custom_data — bruit système, volontairement exclus.
    'montant_estime': 'Montant estimé (MAD)',
    'date_cloture_prevue': 'Date de clôture prévue',
    'distributeur': "Distributeur d'électricité",
    'project_timeline': 'Horizon du projet',
    'financing_intent': 'Financement envisagé',
    'facility_type': 'Type de site (pro)',
    'site_count': 'Nombre de sites (pro)',
    'visit_window_part': 'Créneau de visite préféré',
    'visit_window_week': 'Semaine de visite préférée',
    'roof_age': 'Âge de la toiture (ans)',
    'ownership': "Statut d'occupation",
}

_CHOICE_FIELDS = {
    'stage', 'canal', 'priorite', 'type_installation', 'raccordement',
    'type_toiture', 'orientation', 'ombrage', 'structure_pref',
    'batterie_souhaitee',
    # LW27 — champs choices parmi les 11 nouveaux (montant_estime,
    # date_cloture_prevue et roof_age sont des valeurs libres, pas des choices).
    'distributeur', 'project_timeline', 'financing_intent', 'facility_type',
    'site_count', 'visit_window_part', 'visit_window_week', 'ownership',
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


def log_bulk_change(lead: Lead, user, field: str, old_val, new_val) -> LeadActivity:
    """Une entrée de modification issue d'une action EN MASSE (édition groupée).

    Identique à une modification normale (champ, ancienne → nouvelle valeur),
    mais marquée `bulk=True` pour que l'Historique affiche le badge « en masse ».
    Valeurs déjà affichables — ou brutes, alors mises en forme comme ailleurs.
    """
    label = TRACKED_FIELDS.get(field, field)
    return LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field=field, field_label=label,
        old_value=_display(lead, field, old_val),
        new_value=_display(lead, field, new_val),
        bulk=True,
    )


def log_bulk_note(lead: Lead, user, body: str) -> LeadActivity:
    """Note libre issue d'une action en masse (archivage groupé, etc.)."""
    return LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE, body=body, bulk=True,
    )


def log_archive(lead: Lead, user) -> LeadActivity:
    """Trace l'archivage dans le chatter (geste réversible)."""
    return LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Lead archivé par {getattr(user, 'username', '?')}",
    )


def log_restore(lead: Lead, user) -> LeadActivity:
    """Trace la restauration dans le chatter."""
    return LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Lead restauré par {getattr(user, 'username', '?')}",
    )
