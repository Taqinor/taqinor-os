"""XRH6 — journalisation automatique du chatter d'un ``DossierEmploye``.

Compare les champs SUIVIS entre l'instance pré-sauvegarde et post-sauvegarde ;
une ligne ``DossierActivity`` (type=log) est écrite par champ modifié, avec
libellé lisible et valeurs affichables. L'auteur et la société viennent
toujours de la requête/du dossier, jamais du corps.

Pattern aligné sur ``crm.activity`` (même structure ``TRACKED_FIELDS`` +
``log_changes``) et ``contrats.services.journaliser_transition`` (mêmes noms
de champs ``DossierActivity``).
"""
from .models import DossierActivity, DossierEmploye

# Champ suivi → libellé français affiché dans l'Historique (XRH6 : poste,
# département, statut, type de contrat, dates de contrat — le manager n'existe
# pas encore comme champ dédié, ajouté ici le jour où il apparaît).
TRACKED_FIELDS = {
    'poste_ref': 'Poste',
    'departement': 'Département',
    'statut': 'Statut',
    'type_contrat': 'Type de contrat',
    'contrat_date_debut': 'Début de contrat',
    'contrat_date_fin': 'Fin de contrat',
}

_CHOICE_FIELDS = {'statut', 'type_contrat'}
_FK_FIELDS = {'poste_ref', 'departement'}


def _display(dossier, field, value):
    """Valeur lisible pour la timeline."""
    if value is None or value == '':
        return '—'
    if field in _CHOICE_FIELDS:
        choices = dict(DossierEmploye._meta.get_field(field).choices or [])
        return str(choices.get(value, value))
    if field in _FK_FIELDS:
        return str(value)
    return str(value)


def log_changes(old, new, user):
    """Compare les champs suivis entre l'instance AVANT et APRÈS sauvegarde."""
    for field, label in TRACKED_FIELDS.items():
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val == new_val:
            continue
        DossierActivity.objects.create(
            company=new.company, employe=new, auteur=user,
            type=DossierActivity.Kind.LOG,
            field=field,
            old_value=_display(old, field, old_val),
            new_value=_display(new, field, new_val),
        )


def log_note(dossier, user, message):
    return DossierActivity.objects.create(
        company=dossier.company, employe=dossier, auteur=user,
        type=DossierActivity.Kind.NOTE, message=message,
    )
