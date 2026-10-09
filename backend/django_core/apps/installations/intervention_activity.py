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
    # ACHT28 — la signature client de l'intervention est une PREUVE : une
    # signature ou une re-signature apparaît dans l'Historique (patron AUD305
    # du chantier).
    'signature_client': 'Signature client',
    'signataire_nom': 'Nom du signataire',
    'signe_le': 'Date de signature',
    # ACHT35 — champs de planification / terrain jusque-là non tracés.
    'priorite': 'Priorité',
    'equipe_ref': 'Équipe terrain',
    'fenetre_debut': 'Début de fenêtre',
    'fenetre_fin': 'Fin de fenêtre',
    'compte_rendu': 'Compte-rendu',
}

# ACHT35 — M2M `equipe` : l'état « avant » doit être CAPTURÉ avant la
# sauvegarde (voir `capturer_equipe`), le M2M n'étant pas lu sur l'instance.
M2M_TRACKED_FIELDS = {'equipe': 'Équipe'}

_CHOICE_FIELDS = {'statut', 'type_intervention', 'priorite'}
# ACHT28 — on ne journalise que la PRÉSENCE de la signature (data-URL base64).
_PRESENCE_ONLY_FIELDS = {'signature_client'}


def _display(field: str, value):
    """Valeur lisible pour la timeline."""
    if value is None or value == '':
        return '—'
    if field in _PRESENCE_ONLY_FIELDS:
        return 'Signature enregistrée'
    if field in _CHOICE_FIELDS:
        choices = dict(Intervention._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if field == 'technicien':
        return getattr(value, 'username', str(value))
    if field in ('camionnette', 'equipe_ref'):
        return getattr(value, 'nom', str(value))
    return str(value)


def capturer_equipe(interv: Intervention) -> Intervention:
    """ACHT35 — fige sur `interv` (l'état « avant ») les noms de l'équipe M2M,
    à appeler AVANT `serializer.save()` ; `log_changes` compare ensuite."""
    interv._equipe_avant = sorted(
        interv.equipe.values_list('username', flat=True))
    return interv


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
    avant = getattr(old, '_equipe_avant', None)
    if avant is not None:
        apres = sorted(new.equipe.values_list('username', flat=True))
        if avant != apres:
            InterventionActivity.objects.create(
                company=new.company, intervention=new, user=user,
                kind=InterventionActivity.Kind.MODIFICATION,
                field='equipe', field_label=M2M_TRACKED_FIELDS['equipe'],
                old_value=', '.join(avant) or '—',
                new_value=', '.join(apres) or '—',
            )


def log_note(interv: Intervention, user, body: str) -> InterventionActivity:
    return InterventionActivity.objects.create(
        company=interv.company, intervention=interv, user=user,
        kind=InterventionActivity.Kind.NOTE, body=body,
    )
