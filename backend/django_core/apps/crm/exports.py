"""Export Excel (.xlsx) — leads CRM.

`openpyxl` est une dépendance pré-approuvée (voir docs/PLAN.md). L'import est
fait À LA DEMANDE dans la fonction pour que l'app démarre même si la lib n'est
pas présente dans un contexte qui n'exporte jamais.

Le helper `build_xlsx_response` est volontairement générique (en-têtes + lignes)
pour être réutilisé par les autres exports à venir (clients, produits…).

L879 : la construction du classeur vit désormais dans le builder PARTAGÉ
``apps.records.xlsx`` ; cette fonction n'est qu'un alias mince pour préserver
tous les appelants existants. Un seul format (en-têtes en gras, largeurs,
coercition fr-MA) pour TOUS les exports de listes.
"""
from apps.records.xlsx import build_xlsx_response as _build_xlsx_response

from .stages import STAGE_LABELS

# Caractères qui, en tête d'une cellule, déclenchent une FORMULE quand le
# classeur est ouvert dans Excel/LibreOffice (injection CSV/Excel). On les
# neutralise en préfixant une apostrophe : la cellule reste lisible (texte) et
# n'exécute jamais de formule. Ne concerne QUE les cellules texte — nombres,
# booléens et dates passent intacts.
_RISKY_LEADING = ('=', '+', '-', '@')


def _neutralize_cell(value):
    """Préfixe une apostrophe aux chaînes commençant par un caractère à risque."""
    if isinstance(value, str) and value[:1] in _RISKY_LEADING:
        return "'" + value
    return value


def build_xlsx_response(filename, headers, rows, sheet_title='Export'):
    """Réponse .xlsx avec neutralisation de l'injection de formules.

    Enveloppe le builder partagé (apps.records.xlsx) en assainissant CHAQUE
    cellule texte des lignes : une valeur commençant par ``= + - @`` est
    préfixée d'une apostrophe pour qu'Excel l'affiche comme du texte au lieu
    d'évaluer une formule. Les nombres/dates/booléens restent inchangés. Ce
    helper est partagé par tous les exports xlsx du module.
    """
    safe_rows = [[_neutralize_cell(v) for v in row] for row in rows]
    return _build_xlsx_response(
        filename, headers, safe_rows, sheet_title=sheet_title)

# Libellés FR des canaux/priorités — alignés sur le modèle Lead. On lit les
# choices du modèle quand c'est possible pour ne jamais diverger.


LEAD_EXPORT_HEADERS = [
    'Nom', 'Prénom', 'Société', 'Email', 'Téléphone', 'WhatsApp',
    'Ville', 'Étape', 'Canal', 'Priorité', 'Responsable', 'Tags',
    'Perdu', 'Motif de perte', 'Relance', 'Archivé', 'Créé le',
    'Modifié le', 'Dernier devis (TTC)', 'Statut devis',
]

_PRIORITE_LABELS = {'basse': 'Basse', 'normale': 'Normale', 'haute': 'Haute'}

# Libellés FR des statuts de devis (miroir d'apps.ventes — gardé local pour
# que l'export ne dépende pas du module ventes au chargement).
_DEVIS_STATUT_LABELS = {
    'brouillon': 'Brouillon', 'envoye': 'Envoyé', 'accepte': 'Accepté',
    'refuse': 'Refusé', 'expire': 'Expiré',
}


def lead_row(lead):
    """Une ligne d'export pour un lead (valeurs FR lisibles)."""
    canal_label = dict(
        lead._meta.get_field('canal').choices or []
    ).get(lead.canal, lead.canal or '')
    # Dernier devis du lead (le plus récent) — montant TTC + statut. Aucun prix
    # d'achat ni marge : uniquement le total client-facing.
    dernier = lead.devis.order_by('-date_creation').first()
    devis_total = str(dernier.total_ttc) if dernier else ''
    devis_statut = (
        _DEVIS_STATUT_LABELS.get(dernier.statut, dernier.statut)
        if dernier else '')
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
        lead.date_modification.strftime('%Y-%m-%d %H:%M')
        if lead.date_modification else '',
        devis_total,
        devis_statut,
    ]


def export_leads_xlsx(leads):
    """Réponse .xlsx pour une sélection de leads."""
    rows = [lead_row(lead) for lead in leads]
    return build_xlsx_response(
        'leads.xlsx', LEAD_EXPORT_HEADERS, rows, sheet_title='Leads')


_TYPE_CLIENT_LABELS = {'particulier': 'Particulier', 'entreprise': 'Entreprise'}

CLIENT_EXPORT_HEADERS = [
    'Nom', 'Prénom', 'Type', 'Email', 'Téléphone', 'Adresse',
    'ICE', 'IF', 'RC', 'CIN', 'RIB', 'Créé le',
]


def export_clients_xlsx(clients):
    """Export .xlsx clients avec les identifiants légaux marocains (ICE/IF/RC/
    CIN/RIB). Aucun prix d'achat ni marge — données d'identité uniquement.
    RIB lu via getattr (champ optionnel/à venir) → vide s'il n'existe pas."""
    rows = [[
        c.nom or '', c.prenom or '',
        _TYPE_CLIENT_LABELS.get(
            getattr(c, 'type_client', ''), getattr(c, 'type_client', '') or ''),
        c.email or '', c.telephone or '', c.adresse or '',
        getattr(c, 'ice', '') or '', getattr(c, 'if_fiscal', '') or '',
        getattr(c, 'rc', '') or '', getattr(c, 'cin', '') or '',
        getattr(c, 'rib', '') or '',
        c.date_creation.strftime('%Y-%m-%d') if getattr(c, 'date_creation', None) else '',
    ] for c in clients]
    return build_xlsx_response(
        'clients.xlsx', CLIENT_EXPORT_HEADERS, rows, sheet_title='Clients')
