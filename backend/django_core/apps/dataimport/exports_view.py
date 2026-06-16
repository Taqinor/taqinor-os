"""T9 — export Excel générique pour les listes restantes (devis, factures,
chantiers, équipements, tickets SAV). Lecture seule, borné à la société.
Leads/clients/produits ont leurs propres exports dédiés."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from apps.crm.exports import build_xlsx_response


def _co_qs(model, user):
    qs = model.objects.all()
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


def _devis_rows(user, ids):
    from apps.ventes.models import Devis
    qs = _co_qs(Devis, user).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Statut', 'Total TTC', 'Créé le', 'Validité']
    rows = [[
        d.reference, getattr(d.client, 'nom', '') or '', d.get_statut_display(),
        str(d.total_ttc or 0),
        d.date_creation.strftime('%Y-%m-%d') if d.date_creation else '',
        d.date_validite.isoformat() if d.date_validite else '',
    ] for d in qs.order_by('-id')]
    return 'devis.xlsx', headers, rows, 'Devis'


def _factures_rows(user, ids):
    from apps.ventes.models import Facture
    qs = _co_qs(Facture, user).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Statut', 'Échéance', 'Créée le']
    rows = [[
        f.reference, getattr(f.client, 'nom', '') or '', f.get_statut_display(),
        f.date_echeance.isoformat() if f.date_echeance else '',
        f.date_creation.strftime('%Y-%m-%d') if f.date_creation else '',
    ] for f in qs.order_by('-id')]
    return 'factures.xlsx', headers, rows, 'Factures'


def _chantiers_rows(user, ids):
    from apps.installations.models import Installation
    qs = _co_qs(Installation, user).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Statut', 'Pose prévue', 'Mise en service']
    rows = [[
        i.reference, getattr(i.client, 'nom', '') or '', i.get_statut_display(),
        i.date_pose_prevue.isoformat() if i.date_pose_prevue else '',
        i.date_mise_en_service.isoformat() if i.date_mise_en_service else '',
    ] for i in qs.order_by('-id')]
    return 'chantiers.xlsx', headers, rows, 'Chantiers'


def _equipements_rows(user, ids):
    from apps.sav.models import Equipement
    qs = _co_qs(Equipement, user).select_related('produit')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['N° série', 'Produit', 'Pose', 'Fin garantie', 'Statut']
    rows = [[
        e.numero_serie or '', getattr(e.produit, 'nom', '') or '',
        e.date_pose.isoformat() if e.date_pose else '',
        e.date_fin_garantie.isoformat() if e.date_fin_garantie else '',
        e.get_statut_display() if hasattr(e, 'get_statut_display') else e.statut,
    ] for e in qs.order_by('-id')]
    return 'equipements.xlsx', headers, rows, 'Équipements'


def _tickets_rows(user, ids):
    from apps.sav.models import Ticket
    qs = _co_qs(Ticket, user).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Type', 'Statut', 'Ouverture', 'Résolution']
    rows = [[
        t.reference, getattr(t.client, 'nom', '') or '',
        t.get_type_display() if hasattr(t, 'get_type_display') else t.type,
        t.get_statut_display(),
        t.date_ouverture.isoformat() if t.date_ouverture else '',
        t.date_resolution.isoformat() if t.date_resolution else '',
    ] for t in qs.order_by('-id')]
    return 'tickets.xlsx', headers, rows, 'Tickets SAV'


_BUILDERS = {
    'devis': _devis_rows, 'factures': _factures_rows, 'chantiers': _chantiers_rows,
    'equipements': _equipements_rows, 'tickets': _tickets_rows,
}


@api_view(['POST'])
@permission_classes([IsAnyRole])
def export_list(request, entity):
    """POST /imports/export/<entity>/ {ids?: [...]} → .xlsx (société courante)."""
    builder = _BUILDERS.get(entity)
    if builder is None:
        return Response({'detail': 'Entité inconnue.'}, status=400)
    ids = request.data.get('ids') or []
    filename, headers, rows, title = builder(request.user, ids)
    return build_xlsx_response(filename, headers, rows, sheet_title=title)
