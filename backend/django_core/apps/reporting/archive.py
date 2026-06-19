"""Archive documentaire (lecture seule) — N32.

Agrège tous les documents d'un client ou d'un chantier (devis, factures,
avoirs, bons de commande + documents post-vente du chantier) et renvoie, pour
chacun, l'URL de téléchargement de l'endpoint EXISTANT qui régénère le PDF à la
demande. Aucune écriture, aucun prix d'achat / marge n'est exposé.

Tout est filtré par société (multi-tenant) : un id d'une autre société renvoie
404.

Filtres (L862) : ?type=<type> restreint à un type de document, ?sort=asc|desc
trie par date (récent d'abord par défaut) — le compte reflète le filtre.
Export (L864) : ?export=xlsx renvoie la liste filtrée (type/référence/date) en
.xlsx, scopé société, sans aucun prix d'achat / marge.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm.models import Client
from apps.ventes.models import Devis, Facture, Avoir, BonCommande
from apps.installations.models import Installation
from apps.records.xlsx import build_xlsx_response

# Libellés FR des types de document (miroir de archiveDocs.js côté front).
TYPE_LABELS = {
    'devis': 'Devis',
    'facture': 'Facture',
    'avoir': 'Avoir',
    'bon_commande': 'Bon de commande',
    'pv_reception': 'PV de réception',
    'bon_livraison': 'Bon de livraison',
    'dossier_remise': 'Dossier de remise',
    'attestation': 'Attestation',
}


def _co(user):
    """Kwargs de filtre société, ou None si accès refusé."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _doc(type_, label, reference, dt, url):
    """Forme une entrée de document typée pour l'archive.

    ``has_pdf`` (L863) indique explicitement si un PDF téléchargeable existe —
    le front affiche « Pas de PDF » plutôt qu'une affordance morte quand non.
    """
    return {
        'type': type_,
        'label': label,
        'reference': reference or '',
        'date': dt.isoformat() if dt else None,
        'download_url': url,
        'has_pdf': bool(url),
    }


def _apply_filters(docs, request):
    """Filtre par ?type= et trie par ?sort=asc|desc (récent d'abord défaut)."""
    type_ = (request.query_params.get('type') or '').strip()
    if type_:
        docs = [d for d in docs if d['type'] == type_]
    sort = (request.query_params.get('sort') or 'desc').strip().lower()
    reverse = sort != 'asc'
    docs.sort(key=lambda d: (d['date'] or ''), reverse=reverse)
    return docs


def _xlsx_export(docs, filename):
    """Export .xlsx de la liste (type/référence/date) — sans prix d'achat."""
    headers = ['Type', 'Référence', 'Date']
    rows = [
        [TYPE_LABELS.get(d['type'], d['label'] or d['type']),
         d['reference'] or '', d['date'] or '']
        for d in docs
    ]
    return build_xlsx_response(
        filename, headers, rows, sheet_title='Documents')


def _devis_docs(devis_qs):
    return [
        _doc('devis', 'Devis', d.reference,
             getattr(d, 'date_creation', None),
             f'/api/django/ventes/devis/{d.id}/proposal/')
        for d in devis_qs
    ]


def _facture_docs(facture_qs):
    return [
        _doc('facture', 'Facture', f.reference,
             getattr(f, 'date_emission', None),
             f'/api/django/ventes/factures/{f.id}/telecharger-pdf/')
        for f in facture_qs
    ]


def _avoir_docs(avoir_qs):
    return [
        _doc('avoir', 'Avoir', a.reference,
             getattr(a, 'date_emission', None),
             f'/api/django/ventes/avoirs/{a.id}/telecharger-pdf/')
        for a in avoir_qs
    ]


def _bon_commande_docs(bc_qs):
    # Le bon de commande client n'a pas de PDF dédié ; on le liste tout de même
    # (référence + date) avec download_url=None → has_pdf=False, ce qui fait
    # afficher « Pas de PDF » au lieu d'une affordance morte (L863).
    return [
        _doc('bon_commande', 'Bon de commande', bc.reference,
             getattr(bc, 'date_creation', None), None)
        for bc in bc_qs
    ]


def _chantier_post_sale_docs(installation):
    """Documents post-vente d'un chantier (régénérés à la demande)."""
    iid = installation.id
    ref = installation.reference
    dt = getattr(installation, 'date_creation', None)
    base = f'/api/django/documents/chantiers/{iid}'
    return [
        _doc('pv_reception', 'PV de réception', ref, dt,
             f'{base}/pv-reception/'),
        _doc('bon_livraison', 'Bon de livraison', ref, dt,
             f'{base}/bon-livraison/'),
        _doc('dossier_remise', 'Dossier de remise', ref, dt,
             f'{base}/dossier-remise/'),
        _doc('attestation', 'Attestation', ref, dt,
             f'{base}/attestation/'),
    ]


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def archive_client(request, pk):
    """Tous les documents d'un client. Lecture seule, scopé société."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    try:
        client = Client.objects.get(pk=pk, **co)
    except Client.DoesNotExist:
        return Response({'detail': 'Client introuvable.'}, status=404)

    docs = []
    docs += _devis_docs(Devis.objects.filter(**co, client_id=client.id))
    docs += _facture_docs(Facture.objects.filter(**co, client_id=client.id))
    docs += _avoir_docs(Avoir.objects.filter(**co, client_id=client.id))
    docs += _bon_commande_docs(
        BonCommande.objects.filter(**co, client_id=client.id))
    for inst in Installation.objects.filter(**co, client_id=client.id):
        docs += _chantier_post_sale_docs(inst)

    docs = _apply_filters(docs, request)
    if (request.query_params.get('export') or '').lower() == 'xlsx':
        return _xlsx_export(docs, f'archive-client-{client.id}.xlsx')
    return Response({
        'client': {'id': client.id, 'nom': str(client)},
        'count': len(docs),
        'documents': docs,
    })


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def archive_chantier(request, pk):
    """Tous les documents d'un chantier. Lecture seule, scopé société."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    try:
        inst = Installation.objects.select_related('client').get(pk=pk, **co)
    except Installation.DoesNotExist:
        return Response({'detail': 'Chantier introuvable.'}, status=404)

    docs = []
    if inst.devis_id:
        docs += _devis_docs(Devis.objects.filter(**co, id=inst.devis_id))
        docs += _facture_docs(
            Facture.objects.filter(**co, devis_id=inst.devis_id))
    if inst.bon_commande_id:
        docs += _bon_commande_docs(
            BonCommande.objects.filter(**co, id=inst.bon_commande_id))
    if inst.devis_id:
        facture_ids = list(
            Facture.objects.filter(**co, devis_id=inst.devis_id)
            .values_list('id', flat=True))
        if facture_ids:
            docs += _avoir_docs(
                Avoir.objects.filter(**co, facture_id__in=facture_ids))
    docs += _chantier_post_sale_docs(inst)

    docs = _apply_filters(docs, request)
    if (request.query_params.get('export') or '').lower() == 'xlsx':
        return _xlsx_export(docs, f'archive-chantier-{inst.id}.xlsx')
    return Response({
        'chantier': {
            'id': inst.id, 'reference': inst.reference,
            'client': str(inst.client) if inst.client else '',
        },
        'count': len(docs),
        'documents': docs,
    })
