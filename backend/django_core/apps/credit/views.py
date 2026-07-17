"""apps.credit.views — peuplé tâche par tâche."""
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    ConditionPaiementSegment, DerogationCredit, EncoursGarantiClient,
    LimiteCredit, PoliceAssuranceCredit, ReglageCredit, SegmentClientCredit,
)
from .serializers import (
    ConditionPaiementSegmentSerializer, DerogationCreditSerializer,
    EncoursGarantiClientSerializer, LimiteCreditSerializer,
    PoliceAssuranceCreditSerializer, ReglageCreditSerializer,
    SegmentClientCreditSerializer,
)


class IsDirecteurOrAdmin(BasePermission):
    """NTCRD9 — décision de dérogation réservée Directeur/Administrateur.

    Passe pour un superuser, le palier admin (``is_admin_role``), ou un rôle
    fin nommé « Directeur »/« Administrateur ». Un Commercial (même avec des
    permissions d'écriture) est REFUSÉ — c'est une garde de restriction, pas
    de compatibilité."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, 'is_superuser', False) or getattr(u, 'is_admin_role', False):
            return True
        role = getattr(u, 'role', None)
        return bool(role and role.nom in ('Directeur', 'Administrateur'))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ping(request):
    """NTCRD1 — vérifie que l'app ``credit`` est montée et répond."""
    return Response({'app': 'credit', 'status': 'ok'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fiche_credit_client(request, client_id):
    """NTCRD10 — fiche crédit consolidée d'un client (limite, encours,
    disponible, score, mode de hold, dérogations). Client borné société via
    ``crm.selectors.get_company_client`` (jamais un import de ``crm.models``).
    404 propre si le client n'existe pas / appartient à une autre société."""
    from apps.crm.selectors import get_company_client

    from .selectors import fiche_credit

    client = get_company_client(request.user.company, client_id)
    if client is None:
        return Response(
            {'detail': 'Client introuvable.'},
            status=status.HTTP_404_NOT_FOUND)
    return Response(fiche_credit(client))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def badges_credit_view(request):
    """NTCRD23 — pastilles d'état crédit pour une liste d'ids clients
    (``?client_ids=1,2,3``), company-scopé. Lecture seule/léger."""
    from .selectors import badges_credit

    raw = request.query_params.get('client_ids', '')
    ids = [int(x) for x in raw.split(',') if x.strip().isdigit()]
    return Response(badges_credit(request.user.company, ids))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exposition_credit(request):
    """NTCRD19 — rapport d'exposition consolidée (trié par risque). ``?format=
    xlsx`` renvoie un classeur .xlsx (jamais de ``prix_achat``/marge)."""
    from django.http import HttpResponse

    from .selectors import rapport_exposition

    lignes = rapport_exposition(request.user.company)

    if request.query_params.get('format') == 'xlsx':
        from apps.records.xlsx import workbook_bytes

        header = [
            'Client', 'Encours', 'Limite', 'Disponible', '% utilisé',
            'Dépasse', 'Score', 'Mode hold', 'Garantie assurance',
            'Dépasse garantie',
        ]
        rows = [
            [
                ligne['client_nom'], ligne['encours'], ligne['limite'],
                ligne['disponible'], ligne['pct_utilise'], ligne['depasse'],
                ligne['lettre_score'], ligne['mode_hold'],
                ligne['garantie_assurance'], ligne['depasse_garantie'],
            ]
            for ligne in lignes
        ]
        content = workbook_bytes(header, rows, sheet_title='exposition_credit')
        resp = HttpResponse(
            content,
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'))
        resp['Content-Disposition'] = (
            'attachment; filename="exposition_credit.xlsx"')
        return resp

    return Response({'count': len(lignes), 'resultats': lignes})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def position_credit_pdf(request, client_id):
    """NTCRD25 — PDF interne « Position crédit client » (filigrane USAGE
    INTERNE, réservé Direction/Finance). Company-scopé ; 503 propre si le
    moteur PDF est indisponible."""
    from django.http import HttpResponse

    from apps.crm.selectors import get_company_client

    from .services import generer_pdf_position_credit

    client = get_company_client(request.user.company, client_id)
    if client is None:
        return Response(
            {'detail': 'Client introuvable.'},
            status=status.HTTP_404_NOT_FOUND)
    try:
        pdf = generer_pdf_position_credit(client)
    except RuntimeError:
        return Response(
            {'detail': 'Moteur PDF indisponible.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="position_credit_{client_id}.pdf"')
    return resp


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def score_credit_client(request, client_id):
    """NTCRD12 — score crédit d'un client (lettre A-E + position vs limite +
    recommandation lisible). Company-scopé, 404 propre hors société."""
    from apps.crm.selectors import get_company_client

    from .selectors import score_credit

    client = get_company_client(request.user.company, client_id)
    if client is None:
        return Response(
            {'detail': 'Client introuvable.'},
            status=status.HTTP_404_NOT_FOUND)
    return Response(score_credit(client))


class LimiteCreditViewSet(CompanyScopedModelViewSet):
    """NTCRD2 — CRUD limite de crédit par client, company-scopé.

    NTCRD22 — tout changement de ``montant_limite``/``mode_hold`` est journalisé
    dans le chatter générique ``records`` (ancien→nouveau + acteur côté
    serveur), consultable via ``historique``."""
    queryset = LimiteCredit.objects.select_related('client', 'cree_par').all()
    serializer_class = LimiteCreditSerializer

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, cree_par=self.request.user)

    def perform_update(self, serializer):
        # NTCRD22 — capture l'ancien état AVANT sauvegarde pour journaliser le
        # diff (montant + mode de hold) côté chatter records (best-effort).
        instance = serializer.instance
        ancien_montant = instance.montant_limite
        ancien_mode = instance.mode_hold
        super().perform_update(serializer)
        nouvel = serializer.instance
        try:
            from apps.records.services import log_field_change
            if ancien_montant != nouvel.montant_limite:
                log_field_change(
                    nouvel, 'montant_limite', ancien_montant,
                    nouvel.montant_limite, user=self.request.user,
                    field_label='Limite de crédit')
            if ancien_mode != nouvel.mode_hold:
                log_field_change(
                    nouvel, 'mode_hold', ancien_mode, nouvel.mode_hold,
                    user=self.request.user, field_label='Mode de hold')
        except Exception:  # pragma: no cover - journalisation best-effort
            pass

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """NTCRD22 — timeline des changements de cette limite (chatter records)."""
        from apps.records.services import chatter_qs
        limite = self.get_object()
        entries = [
            {
                'id': a.id, 'kind': a.kind, 'field': a.field,
                'field_label': a.field_label, 'old_value': a.old_value,
                'new_value': a.new_value, 'body': a.body,
                'created_at': a.created_at,
                'acteur': getattr(a.created_by, 'username', None),
            }
            for a in chatter_qs(limite, company=request.user.company)
        ]
        return Response({'count': len(entries), 'entries': entries})


class ReglageCreditView(APIView):
    """NTCRD3 — réglage crédit société (singleton get-or-default/PATCH).

    Lecture ouverte à tout authentifié ; écriture réservée Directeur/
    Administrateur (les réglages de hold impactent toute la société)."""
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT', 'POST'):
            return [IsResponsableOrAdmin()]
        return super().get_permissions()

    def get(self, request):
        reglage = ReglageCredit.get_or_default(request.user.company)
        return Response(ReglageCreditSerializer(reglage).data)

    def patch(self, request):
        reglage, _ = ReglageCredit.objects.get_or_create(
            company=request.user.company)
        serializer = ReglageCreditSerializer(
            reglage, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DerogationCreditViewSet(CompanyScopedModelViewSet):
    """NTCRD9 — dérogations crédit : tout authentifié peut DEMANDER
    (``create``) ; seul Directeur/Administrateur peut approuver/rejeter."""
    queryset = DerogationCredit.objects.select_related(
        'client', 'demandeur', 'approuvee_par', 'devis').all()
    serializer_class = DerogationCreditSerializer

    def get_permissions(self):
        if self.action in ('approuver', 'rejeter'):
            return [IsDirecteurOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, demandeur=self.request.user)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        from .services import approuver_derogation
        derogation = self.get_object()
        approuver_derogation(derogation, request.user)
        return Response(self.get_serializer(derogation).data)

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        from .services import rejeter_derogation
        derogation = self.get_object()
        rejeter_derogation(derogation, request.user)
        return Response(
            self.get_serializer(derogation).data, status=status.HTTP_200_OK)


class ConditionPaiementSegmentViewSet(CompanyScopedModelViewSet):
    """NTCRD13/15 — CRUD des conditions de paiement par segment. Lecture
    ouverte à tout authentifié ; écriture réservée Directeur/Administrateur."""
    queryset = ConditionPaiementSegment.objects.all()
    serializer_class = ConditionPaiementSegmentSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsDirecteurOrAdmin()]
        return super().get_permissions()


class SegmentClientCreditViewSet(CompanyScopedModelViewSet):
    """NTCRD13 — affectation d'un client à un segment crédit. Écriture réservée
    Directeur/Administrateur."""
    queryset = SegmentClientCredit.objects.select_related('client').all()
    serializer_class = SegmentClientCreditSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsDirecteurOrAdmin()]
        return super().get_permissions()


class PoliceAssuranceCreditViewSet(CompanyScopedModelViewSet):
    """NTCRD16 — CRUD registre déclaratif des polices d'assurance-crédit.
    Écriture réservée Directeur/Administrateur (aucun appel externe)."""
    queryset = PoliceAssuranceCredit.objects.all()
    serializer_class = PoliceAssuranceCreditSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsDirecteurOrAdmin()]
        return super().get_permissions()


class EncoursGarantiClientViewSet(CompanyScopedModelViewSet):
    """NTCRD17 — encours garantis par police + client (filtrable par
    ``police``/``client``). Écriture réservée Directeur/Administrateur."""
    queryset = EncoursGarantiClient.objects.select_related(
        'police', 'client').all()
    serializer_class = EncoursGarantiClientSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsDirecteurOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        police = self.request.query_params.get('police')
        client = self.request.query_params.get('client')
        if police:
            qs = qs.filter(police_id=police)
        if client:
            qs = qs.filter(client_id=client)
        return qs
