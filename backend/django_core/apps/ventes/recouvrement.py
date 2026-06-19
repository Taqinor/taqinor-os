"""Recouvrement (workstream E) : niveaux de relance, liste des impayés, balance
âgée, relevé de compte client. VUE / CONSIGNE / IMPRESSION uniquement — aucun
envoi (email/SMS/courrier). L'envoi reste pour une session future.
"""
from decimal import Decimal

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.crm.models import Client
from authentication.permissions import IsAdminRole, IsAnyRole

from .models import Facture, FollowupLevel
from .serializers import FollowupLevelSerializer


def _s(x):
    """Decimal → chaîne au centime (2 décimales)."""
    return str(Decimal(x).quantize(Decimal('0.01')))


def _scope(qs, user):
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


def _levels(company):
    return list(FollowupLevel.objects.filter(company=company).order_by('delai_jours'))


def _current_level(jours_retard, levels):
    """Niveau de relance courant : le plus haut seuil atteint, ou None."""
    current = None
    for lvl in levels:
        if jours_retard >= lvl.delai_jours:
            current = lvl
    if current is None:
        return None
    return {'ordre': current.ordre, 'nom': current.nom,
            'delai_jours': current.delai_jours}


class FollowupLevelViewSet(viewsets.ModelViewSet):
    """Configuration des niveaux de relance (Paramètres). Lecture tout rôle,
    écriture admin."""
    serializer_class = FollowupLevelSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        return _scope(FollowupLevel.objects.all(), self.request.user)

    def perform_create(self, serializer):
        company = self.request.user.company if self.request.user.company_id else None
        serializer.save(company=company)


def _facture_due_rows(user):
    """Factures ouvertes (dues) de la société, non exclues."""
    from authentication.scoping import scope_queryset
    qs = _scope(
        Facture.objects.select_related('client').prefetch_related(
            'lignes', 'paiements', 'avoirs'),
        user
    ).exclude(statut__in=['payee', 'annulee', 'brouillon']).filter(
        exclu_relances=False)
    # Portée de visibilité (Feature F) : relances/balance restreintes aux
    # factures créées par soi / l'équipe pour un rôle restreint. 'all' → inchangé.
    qs = scope_queryset(qs, user, ['created_by'])
    return [f for f in qs if f.montant_du > 0]


@api_view(['GET'])
@permission_classes([IsAnyRole])
def relances_list(request):
    """Impayés à relancer : factures dues, jours de retard, niveau courant."""
    levels = _levels(request.user.company if request.user.company_id else None)
    rows = []
    for f in _facture_due_rows(request.user):
        jr = f.jours_retard
        rows.append({
            'id': f.id, 'reference': f.reference,
            'client_id': f.client_id,
            'client_nom': f"{f.client.nom} {f.client.prenom or ''}".strip(),
            'date_echeance': f.date_echeance.isoformat() if f.date_echeance else None,
            'montant_du': _s(f.montant_du),
            'jours_retard': jr,
            'niveau': _current_level(jr, levels),
            'prochaine_relance': (f.prochaine_relance.isoformat()
                                  if f.prochaine_relance else None),
            'nb_relances': f.relances.count(),
        })
    rows.sort(key=lambda r: r['jours_retard'], reverse=True)
    return Response(rows)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def balance_agee(request):
    """Balance âgée : encours par client, bucketé 0–30/31–60/61–90/90+ jours."""
    by_client = {}
    for f in _facture_due_rows(request.user):
        cid = f.client_id
        entry = by_client.setdefault(cid, {
            'client_id': cid,
            'client_nom': f"{f.client.nom} {f.client.prenom or ''}".strip(),
            'b0_30': Decimal('0'), 'b31_60': Decimal('0'),
            'b61_90': Decimal('0'), 'b90_plus': Decimal('0'),
            'total': Decimal('0'),
        })
        jr = f.jours_retard
        due = f.montant_du
        if jr <= 30:
            entry['b0_30'] += due
        elif jr <= 60:
            entry['b31_60'] += due
        elif jr <= 90:
            entry['b61_90'] += due
        else:
            entry['b90_plus'] += due
        entry['total'] += due
    out = []
    for e in by_client.values():
        out.append({k: (_s(v) if isinstance(v, Decimal) else v)
                    for k, v in e.items()})
    out.sort(key=lambda r: Decimal(r['total']), reverse=True)
    return Response(out)


def _releve_data(client):
    """Relevé de compte : factures (payé/avoir/dû), paiements, avoirs, soldes."""
    factures = list(
        Facture.objects.filter(client=client).exclude(statut='annulee')
        .prefetch_related('lignes', 'paiements', 'avoirs')
        .order_by('date_emission'))
    lignes = []
    paiements = []
    avoirs = []
    total_facture = total_paye = total_avoir = total_du = Decimal('0')
    for f in factures:
        paye = f.montant_paye
        avo = f.avoirs_total
        du = f.montant_du
        total_facture += f.total_ttc
        total_paye += paye
        total_avoir += avo
        total_du += du
        lignes.append({
            'reference': f.reference,
            'date': f.date_emission.isoformat(),
            'statut': f.get_statut_display(),
            'total_ttc': _s(f.total_ttc),
            'paye': _s(paye), 'avoirs': _s(avo), 'du': _s(du),
        })
        # Détail des encaissements (date / mode / montant) par facture.
        for p in f.paiements.all():
            paiements.append({
                'facture': f.reference,
                'date': (p.date_paiement.isoformat()
                         if p.date_paiement else None),
                'mode': p.get_mode_display(),
                'montant': _s(p.montant),
            })
        # Détail des avoirs actifs (date / référence / montant) par facture.
        for a in f.avoirs.all():
            if a.statut == 'annulee':
                continue
            avoirs.append({
                'facture': f.reference,
                'reference': a.reference,
                'date': (a.date_emission.isoformat()
                         if a.date_emission else None),
                'motif': a.motif,
                'total_ttc': _s(a.total_ttc),
            })
    paiements.sort(key=lambda r: r['date'] or '')
    avoirs.sort(key=lambda r: r['date'] or '')
    return {
        'client': {'id': client.id,
                   'nom': f"{client.nom} {client.prenom or ''}".strip(),
                   'email': client.email, 'telephone': client.telephone,
                   'adresse': client.adresse},
        'lignes': lignes,
        'paiements': paiements,
        'avoirs': avoirs,
        'totaux': {
            'facture': _s(total_facture), 'paye': _s(total_paye),
            'avoirs': _s(total_avoir), 'du': _s(total_du),
        },
    }


@api_view(['GET'])
@permission_classes([IsAnyRole])
def client_releve(request, client_id):
    client = _scope(Client.objects.all(), request.user).filter(
        pk=client_id).first()
    if client is None:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(_releve_data(client))


@api_view(['GET'])
@permission_classes([IsAnyRole])
def client_releve_pdf(request, client_id):
    client = _scope(Client.objects.all(), request.user).filter(
        pk=client_id).first()
    if client is None:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    from .utils.pdf import generate_releve_pdf
    try:
        pdf_bytes = generate_releve_pdf(client, _releve_data(client))
    except Exception as exc:
        return Response({'detail': f'PDF indisponible : {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'inline; filename="Releve_{client.nom}.pdf"')
    return resp


@api_view(['GET'])
@permission_classes([IsAnyRole])
def lettre_relance_pdf(request, facture_id):
    facture = _scope(
        Facture.objects.select_related('client'), request.user).filter(
        pk=facture_id).first()
    if facture is None:
        return Response({'detail': 'Facture introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    levels = _levels(facture.company)
    niveau = _current_level(facture.jours_retard, levels)
    message = ''
    if niveau:
        lvl = next((x for x in levels if x.ordre == niveau['ordre']), None)
        message = lvl.message if lvl else ''
    from .utils.pdf import generate_lettre_relance_pdf
    try:
        pdf_bytes = generate_lettre_relance_pdf(facture, niveau, message)
    except Exception as exc:
        return Response({'detail': f'PDF indisponible : {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'inline; filename="Relance_{facture.reference}.pdf"')
    return resp
