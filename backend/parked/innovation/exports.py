"""Export Excel (.xlsx) — idées (NTIDE12).

Le classeur est construit par le builder PARTAGÉ ``apps.records.xlsx``
(en-têtes en gras, largeurs, neutralisation anti-injection de formule) — le
même format que tous les autres exports .xlsx du dépôt (voir
``apps.crm.exports``).
"""
from apps.records.xlsx import build_xlsx_response

IDEE_EXPORT_HEADERS = [
    'Titre', 'Auteur', 'Contexte', 'Statut', 'Votes', 'Créée le', 'Notes',
]


def _derniere_note(idee):
    """Dernière note manuelle du chatter de l'idée (ou chaîne vide)."""
    from apps.records.models import Activity
    from apps.records.services import chatter_qs

    note = chatter_qs(idee, company=idee.company).filter(
        kind=Activity.Kind.NOTE).first()
    return note.body if note else ''


def idee_row(idee):
    """Une ligne d'export pour une idée (valeurs FR lisibles)."""
    return [
        idee.titre or '',
        getattr(idee.auteur, 'username', '') if idee.auteur_id else '',
        idee.contexte or '',
        idee.get_statut_display(),
        idee.votes_count,
        idee.created_at.strftime('%Y-%m-%d %H:%M') if idee.created_at else '',
        _derniere_note(idee),
    ]


def export_idees_xlsx(idees):
    """Réponse .xlsx pour une sélection/filtre d'idées (NTIDE12)."""
    rows = [idee_row(idee) for idee in idees]
    return build_xlsx_response(
        'idees.xlsx', IDEE_EXPORT_HEADERS, rows, sheet_title='Idées')
