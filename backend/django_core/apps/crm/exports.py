"""Export Excel (.xlsx) — leads CRM.

`openpyxl` est une dépendance pré-approuvée (voir docs/PLAN.md). L'import est
fait À LA DEMANDE dans la fonction pour que l'app démarre même si la lib n'est
pas présente dans un contexte qui n'exporte jamais.

Le helper `build_xlsx_response` est volontairement générique (en-têtes + lignes)
pour être réutilisé par les autres exports à venir (clients, produits…).
"""
from django.http import HttpResponse

from .stages import STAGE_LABELS

# Libellés FR des canaux/priorités — alignés sur le modèle Lead. On lit les
# choices du modèle quand c'est possible pour ne jamais diverger.


def build_xlsx_response(filename, headers, rows, sheet_title='Export'):
    """Construit une réponse HTTP .xlsx à partir d'en-têtes + lignes.

    headers : liste de chaînes (1re ligne, en gras).
    rows    : liste de listes (valeurs déjà mises en forme, str/num/None).
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31] or 'Export'

    ws.append(list(headers))
    bold = Font(bold=True)
    for cell in ws[1]:
        cell.font = bold

    for row in rows:
        ws.append(['' if v is None else v for v in row])

    # Largeurs lisibles : on borne à la valeur la plus longue par colonne.
    for idx, _ in enumerate(headers, start=1):
        longest = len(str(headers[idx - 1]))
        for row in rows:
            if idx - 1 < len(row) and row[idx - 1] is not None:
                longest = max(longest, len(str(row[idx - 1])))
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = \
            min(max(longest + 2, 10), 50)

    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet'
        ),
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


LEAD_EXPORT_HEADERS = [
    'Nom', 'Prénom', 'Société', 'Email', 'Téléphone', 'WhatsApp',
    'Ville', 'Étape', 'Canal', 'Priorité', 'Responsable', 'Tags',
    'Perdu', 'Motif de perte', 'Relance', 'Archivé', 'Créé le',
]

_PRIORITE_LABELS = {'basse': 'Basse', 'normale': 'Normale', 'haute': 'Haute'}


def lead_row(lead):
    """Une ligne d'export pour un lead (valeurs FR lisibles)."""
    canal_label = dict(
        lead._meta.get_field('canal').choices or []
    ).get(lead.canal, lead.canal or '')
    return [
        lead.nom or '',
        lead.prenom or '',
        lead.societe or '',
        lead.email or '',
        lead.telephone or '',
        lead.whatsapp or '',
        lead.ville or '',
        STAGE_LABELS.get(lead.stage, lead.stage),
        canal_label,
        _PRIORITE_LABELS.get(lead.priorite, lead.priorite or ''),
        getattr(lead.owner, 'username', '') if lead.owner_id else '',
        lead.tags or '',
        'Oui' if lead.perdu else 'Non',
        lead.motif_perte or '',
        lead.relance_date.isoformat() if lead.relance_date else '',
        'Oui' if lead.is_archived else 'Non',
        lead.date_creation.strftime('%Y-%m-%d %H:%M') if lead.date_creation else '',
    ]


def export_leads_xlsx(leads):
    """Réponse .xlsx pour une sélection de leads."""
    rows = [lead_row(lead) for lead in leads]
    return build_xlsx_response(
        'leads.xlsx', LEAD_EXPORT_HEADERS, rows, sheet_title='Leads')


CLIENT_EXPORT_HEADERS = [
    'Nom', 'Prénom', 'Email', 'Téléphone', 'Adresse', 'ICE', 'Créé le',
]


def export_clients_xlsx(clients):
    rows = [[
        c.nom or '', c.prenom or '', c.email or '', c.telephone or '',
        c.adresse or '', getattr(c, 'ice', '') or '',
        c.date_creation.strftime('%Y-%m-%d') if getattr(c, 'date_creation', None) else '',
    ] for c in clients]
    return build_xlsx_response(
        'clients.xlsx', CLIENT_EXPORT_HEADERS, rows, sheet_title='Clients')
