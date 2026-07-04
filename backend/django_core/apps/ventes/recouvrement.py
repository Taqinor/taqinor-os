"""Recouvrement (workstream E) : niveaux de relance, liste des impayés, balance
âgée, relevé de compte client. VUE / CONSIGNE / IMPRESSION uniquement — aucun
envoi (email/SMS/courrier). L'envoi reste pour une session future.
"""
from decimal import Decimal

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.crm.selectors import client_base_qs
from authentication.permissions import IsAdminRole, IsAnyRole

from .models import Facture, FollowupLevel, PromessePaiement
from .serializers import FollowupLevelSerializer, PromessePaiementSerializer


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


def _current_level(jours_retard, levels, montant_du=None):
    """Niveau de relance courant : le plus haut seuil atteint, ou None.

    XFAC6 — quand ``montant_du`` est fourni, le dict porte aussi la pénalité
    de retard calculée pour ce niveau (indicative, taux 0 → 0.00)."""
    current = None
    for lvl in levels:
        if jours_retard >= lvl.delai_jours:
            current = lvl
    if current is None:
        return None
    out = {'ordre': current.ordre, 'nom': current.nom,
           'delai_jours': current.delai_jours,
           'message': current.message or ''}
    if montant_du is not None:
        out['penalite'] = str(current.calcul_penalite(montant_du, jours_retard))
    return out


def _next_level(jours_retard, levels):
    """Prochain niveau non encore atteint (seuil strictement supérieur), ou None.

    Sert à proposer une date de prochaine relance (aujourd'hui + son délai).
    """
    for lvl in levels:
        if lvl.delai_jours > jours_retard:
            return {'ordre': lvl.ordre, 'nom': lvl.nom,
                    'delai_jours': lvl.delai_jours}
    return None


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

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        """Crée les niveaux de relance par défaut (J+7 / J+15 / J+30) quand la
        société n'en a aucun (L768). Idempotent : ne fait rien si des niveaux
        existent déjà. Réservé à l'admin (mêmes permissions que l'écriture)."""
        company = request.user.company if request.user.company_id else None
        if FollowupLevel.objects.filter(company=company).exists():
            return Response(
                {'detail': 'Des niveaux de relance existent déjà.'},
                status=status.HTTP_409_CONFLICT)
        defaults = [
            (0, 'Rappel', 7,
             'Rappel amiable : la facture {reference} est échue. '
             'Merci de procéder au règlement.'),
            (1, 'Relance', 15,
             'Relance : la facture {reference} reste impayée à ce jour.'),
            (2, 'Mise en demeure', 30,
             'Mise en demeure : la facture {reference} est en retard de '
             'paiement. Un règlement immédiat est attendu.'),
        ]
        for ordre, nom, delai, message in defaults:
            FollowupLevel.objects.create(
                company=company, ordre=ordre, nom=nom,
                delai_jours=delai, message=message)
        levels = FollowupLevel.objects.filter(company=company).order_by(
            'delai_jours')
        return Response(
            FollowupLevelSerializer(levels, many=True).data,
            status=status.HTTP_201_CREATED)


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
    from .selectors import comportement_paiement
    scores_cache = {}
    rows = []
    for f in _facture_due_rows(request.user):
        jr = f.jours_retard
        # XFAC5 — promesse de paiement active/rompue (priorité haute).
        promesse = f.promesses_paiement.filter(
            statut__in=[PromessePaiement.Statut.EN_COURS,
                        PromessePaiement.Statut.ROMPUE]).order_by('-id').first()
        # XFAC15 — score comportemental agrégé du client (mis en cache par
        # client sur la durée de la requête : plusieurs factures partagent le
        # même client).
        if f.client_id not in scores_cache:
            scores_cache[f.client_id] = comportement_paiement(f.client)
        score = scores_cache[f.client_id]
        rows.append({
            'id': f.id, 'reference': f.reference,
            'client_id': f.client_id,
            'client_nom': f"{f.client.nom} {f.client.prenom or ''}".strip(),
            # L853 — téléphone client pour valider/désactiver le bouton WhatsApp
            # côté front (aucun envoi ici ; affichage/validation seulement).
            'client_telephone': f.client.telephone if f.client_id else None,
            'date_echeance': f.date_echeance.isoformat() if f.date_echeance else None,
            'montant_du': _s(f.montant_du),
            'jours_retard': jr,
            'niveau': _current_level(jr, levels, montant_du=f.montant_du),
            'niveau_suivant': _next_level(jr, levels),
            'prochaine_relance': (f.prochaine_relance.isoformat()
                                  if f.prochaine_relance else None),
            'nb_relances': f.relances.count(),
            'promesse': ({
                'id': promesse.id, 'statut': promesse.statut,
                'montant_promis': _s(promesse.montant_promis),
                'date_promise': promesse.date_promise.isoformat(),
            } if promesse else None),
            # XFAC15 — badge de comportement de paiement (lettre A–E).
            'score_comportement': score['lettre'],
        })
    rows.sort(key=lambda r: (
        r['promesse'] is not None and r['promesse']['statut'] == 'rompue',
        r['jours_retard']), reverse=True)
    return Response(rows)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def balance_agee(request):
    """Balance âgée : encours par client, bucketé 0–30/31–60/61–90/90+ jours."""
    from .selectors import comportement_paiement
    by_client = {}
    for f in _facture_due_rows(request.user):
        cid = f.client_id
        entry = by_client.setdefault(cid, {
            'client_id': cid,
            'client_nom': f"{f.client.nom} {f.client.prenom or ''}".strip(),
            'b0_30': Decimal('0'), 'b31_60': Decimal('0'),
            'b61_90': Decimal('0'), 'b90_plus': Decimal('0'),
            'total': Decimal('0'),
            # XFAC15 — score comportemental agrégé du client (priorise les
            # clients à risque dans la balance).
            'score_comportement': comportement_paiement(f.client)['lettre'],
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


def _releve_data(client, user=None):
    """Relevé de compte : factures (payé/avoir/dû), paiements, avoirs, soldes.

    ERR73 — applique la portée de visibilité (Feature F) : un rôle restreint ne
    voit que les factures créées par soi / son équipe, exactement comme la liste
    des impayés et la balance âgée. L'isolation société tient déjà (le client est
    scopé) ; on ajoute la portée propriétaire. ``user=None`` (chemin interne) →
    aucun filtre de portée, comportement historique préservé.
    """
    qs = Facture.objects.filter(client=client).exclude(statut='annulee')
    if user is not None:
        from authentication.scoping import scope_queryset
        qs = scope_queryset(qs, user, ['created_by'])
    factures = list(
        qs.prefetch_related('lignes', 'paiements', 'avoirs')
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
    client = _scope(client_base_qs(), request.user).filter(
        pk=client_id).first()
    if client is None:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(_releve_data(client, request.user))


@api_view(['GET'])
@permission_classes([IsAnyRole])
def client_score_comportement(request, client_id):
    """XFAC15 — badge de comportement de paiement d'un client (fiche client).

    Agrège FG365 (``core.payment_delay``) sur les factures ouvertes du client
    + son retard moyen réel. Client sans historique → score neutre."""
    client = _scope(client_base_qs(), request.user).filter(
        pk=client_id).first()
    if client is None:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    from .selectors import comportement_paiement
    return Response(comportement_paiement(client))


@api_view(['GET'])
@permission_classes([IsAnyRole])
def client_releve_pdf(request, client_id):
    client = _scope(client_base_qs(), request.user).filter(
        pk=client_id).first()
    if client is None:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    from .utils.pdf import generate_releve_pdf
    try:
        pdf_bytes = generate_releve_pdf(client, _releve_data(client, request.user))
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
    niveau = _current_level(
        facture.jours_retard, levels, montant_du=facture.montant_du)
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


# ── XFAC5 — Promesse de paiement (promise-to-pay) ──────────────────────────

class PromessePaiementViewSet(viewsets.ModelViewSet):
    """Promesses de paiement client — suspendent la relance auto jusqu'à
    ``date_promise``. Écriture réservée aux rôles responsable/admin."""
    serializer_class = PromessePaiementSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return _scope(
            PromessePaiement.objects.select_related('facture').all(),
            self.request.user,
        )

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAnyRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = (self.request.user.company
                   if self.request.user.company_id else None)
        facture = serializer.validated_data.get('facture')
        if facture is not None and company is not None and \
                facture.company_id != company.id:
            raise ValidationError({'facture': 'Facture inconnue.'})
        promesse = serializer.save(
            company=company, created_by=self.request.user,
            statut=PromessePaiement.Statut.EN_COURS,
        )
        # Une promesse active SUSPEND les relances automatiques jusqu'à sa
        # date : on pousse ``prochaine_relance`` après la promesse (repris par
        # le scheduler à expiration) et on pose l'exclusion EXPIRANTE (XFAC5),
        # jamais l'exclusion éternelle (comportement historique inchangé).
        facture = promesse.facture
        facture.exclu_relances_jusquau = promesse.date_promise
        facture.save(update_fields=['exclu_relances_jusquau'])
