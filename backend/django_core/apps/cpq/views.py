"""Vues (API) de l'app CPQ.

Tous les ViewSets héritent de ``CompanyScopedModelViewSet`` (ARC2) : le
queryset est scopé société et ``perform_create`` force ``company`` côté
serveur. La liste des produits n'est jamais lue du corps pour le scope."""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import IsResponsableOrAdmin, IsAnyRole

from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ, OffreGroupee,
    PrixContractuel, QuestionConfigurateur, SessionConfigurateur,
    ReponseConfigurateur,
)
from .serializers import (
    OptionProduitSerializer, ContrainteCompatibiliteSerializer,
    RegleProduitCPQSerializer, OffreGroupeeSerializer,
    PrixContractuelSerializer, QuestionConfigurateurSerializer,
)
from . import selectors, services


class OptionProduitViewSet(CompanyScopedModelViewSet):
    queryset = OptionProduit.objects.all()
    serializer_class = OptionProduitSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ContrainteCompatibiliteViewSet(CompanyScopedModelViewSet):
    queryset = ContrainteCompatibilite.objects.all()
    serializer_class = ContrainteCompatibiliteSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class RegleProduitCPQViewSet(CompanyScopedModelViewSet):
    queryset = RegleProduitCPQ.objects.all()
    serializer_class = RegleProduitCPQSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'evaluer'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['post'], url_path='evaluer')
    def evaluer(self, request):
        """NTCPQ2 — Évalue les règles actives contre un contexte fourni.

        Corps : ``{"context": {...}}`` (dict plat construit depuis les lignes
        candidates du devis, ex. ``{"kwc": 12}``). Renvoie les actions
        déclenchées."""
        context = request.data.get('context')
        if context is None:
            # Repli : tout champ hors "context" est traité comme le contexte.
            context = {k: v for k, v in request.data.items() if k != 'context'}
        declenchees = selectors.evaluer_regles_produit(
            company=request.user.company, context=context)
        return Response({'actions_declenchees': declenchees})


class OffreGroupeeViewSet(CompanyScopedModelViewSet):
    queryset = OffreGroupee.objects.prefetch_related('lignes').all()
    serializer_class = OffreGroupeeSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['post'], url_path='appliquer',
            permission_classes=[IsResponsableOrAdmin])
    def appliquer(self, request, pk=None):
        """NTCPQ3 — Applique le bundle au devis ``?devis_id=`` : insère les
        LigneDevis correspondantes en respectant le mode de prix."""
        offre = self.get_object()
        devis_id = request.query_params.get('devis_id') or request.data.get('devis_id')
        if not devis_id:
            return Response({'detail': 'devis_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.ventes.models import Devis
        try:
            devis = Devis.objects.get(pk=devis_id, company=request.user.company)
        except Devis.DoesNotExist:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        lignes = services.appliquer_offre_groupee(
            offre=offre, devis=devis, user=request.user)
        return Response({
            'detail': f'Offre « {offre.nom} » appliquée.',
            'lignes_creees': [li.id for li in lignes],
            'sous_total_ht': str(devis.total_ht),
        }, status=status.HTTP_201_CREATED)


class PrixContractuelViewSet(CompanyScopedModelViewSet):
    queryset = PrixContractuel.objects.select_related(
        'client', 'produit').all()
    serializer_class = PrixContractuelSerializer
    # NTCPQ5 — CRUD réservé Directeur / Commercial responsable.
    permission_classes = [IsResponsableOrAdmin]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        client = serializer.validated_data.get('client')
        produit = serializer.validated_data.get('produit')
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
        if produit is not None and produit.company_id != company.id:
            raise ValidationError({'produit': 'Produit inconnu.'})
        serializer.save(company=company, created_by=self.request.user)


class QuestionConfigurateurViewSet(CompanyScopedModelViewSet):
    queryset = QuestionConfigurateur.objects.all()
    serializer_class = QuestionConfigurateurSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ConfigurateurDemarrerView(APIView):
    """NTCPQ9 — POST cpq/configurateur/demarrer/. Crée une session et renvoie
    le token + les questions actives de la société."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        session = SessionConfigurateur.objects.create(company=company)
        questions = QuestionConfigurateur.objects.filter(
            company=company, actif=True).order_by('ordre', 'id')
        return Response({
            'session': str(session.token),
            'questions': QuestionConfigurateurSerializer(
                questions, many=True).data,
        }, status=status.HTTP_201_CREATED)


def _get_session(request, token):
    return SessionConfigurateur.objects.filter(
        token=token, company=request.user.company).first()


class ConfigurateurRepondreView(APIView):
    """NTCPQ9 — POST cpq/configurateur/{session}/repondre/. Enregistre une ou
    plusieurs réponses (upsert par question)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        session = _get_session(request, token)
        if session is None:
            return Response({'detail': 'Session introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        reponses = request.data.get('reponses')
        if reponses is None:
            reponses = [{
                'question': request.data.get('question')
                or request.data.get('question_id'),
                'valeur': request.data.get('valeur'),
            }]
        for r in reponses:
            qid = r.get('question')
            question = QuestionConfigurateur.objects.filter(
                id=qid, company=session.company).first()
            if question is None:
                continue
            ReponseConfigurateur.objects.update_or_create(
                session=session, question=question,
                defaults={'valeur': r.get('valeur')})
        session.save(update_fields=['updated_at'])
        return Response({'detail': 'Réponses enregistrées.'})


class ConfigurateurResultatView(APIView):
    """NTCPQ9 — GET cpq/configurateur/{session}/resultat/. Résout les produits/
    bundles correspondant aux réponses via le moteur de règles NTCPQ2."""
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        session = _get_session(request, token)
        if session is None:
            return Response({'detail': 'Session introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(selectors.resoudre_configurateur(session))


class ConfigurateurGenererDevisView(APIView):
    """NTCPQ10 — POST cpq/configurateur/{session}/generer-devis/.

    Transforme le résultat résolu en Devis brouillon (lignes + lead/client si
    fournis). Ne génère jamais le PDF. Corps : ``{lead?, client?}``."""
    permission_classes = [IsResponsableOrAdmin]

    def post(self, request, token):
        session = SessionConfigurateur.objects.filter(
            token=token, company=request.user.company).first()
        if session is None:
            return Response({'detail': 'Session introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        company = request.user.company
        lead = None
        client = None
        lead_id = request.data.get('lead')
        client_id = request.data.get('client')
        if lead_id:
            from apps.crm.selectors import get_company_lead
            lead = get_company_lead(company, lead_id)
            if lead is None:
                return Response({'detail': 'Lead introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
        if client_id:
            from apps.crm.selectors import get_company_client
            client = get_company_client(company, client_id)
            if client is None:
                return Response({'detail': 'Client introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
        devis = services.generer_devis_depuis_configurateur(
            session, user=request.user, lead=lead, client=client)
        return Response({
            'detail': 'Devis brouillon créé.',
            'devis_id': devis.id,
            'reference': devis.reference,
        }, status=status.HTTP_201_CREATED)


class ValiderCompatibiliteView(APIView):
    """NTCPQ1 — POST cpq/valider-compatibilite/.

    Corps : ``{"produit_ids": [1, 2, 3]}``. Renvoie les violations, séparées en
    ``bloquantes`` (INCOMPATIBLE / REQUIERT) et ``avertissements`` (RECOMMANDE)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        produit_ids = request.data.get('produit_ids') or []
        if not isinstance(produit_ids, (list, tuple)):
            return Response(
                {'detail': 'produit_ids doit être une liste.'},
                status=status.HTTP_400_BAD_REQUEST)
        violations = selectors.violations_compatibilite(
            company=company, produit_ids=produit_ids)
        bloquantes = [v for v in violations if v['bloquante']]
        avertissements = [v for v in violations if not v['bloquante']]
        return Response({
            'valide': not bloquantes,
            'violations': violations,
            'bloquantes': bloquantes,
            'avertissements': avertissements,
        })
