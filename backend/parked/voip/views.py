from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from . import services
from .models import Appel, VoipIdentifiantUtilisateur
from .serializers import (
    AppelSerializer, VoipIdentifiantUtilisateurSerializer,
    VoipParametresSerializer,
)


class VoipParametresView(APIView):
    """XPLT21 — Configuration VoIP DE LA société (singleton). Lecture tout
    rôle (pour savoir si le softphone est actif) ; écriture réservée
    responsable/admin (fournisseur + serveur SIP + activation)."""

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT'):
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    def get(self, request):
        parametres = services.get_or_create_parametres(request.user.company)
        return Response(VoipParametresSerializer(parametres).data)

    def patch(self, request):
        parametres = services.get_or_create_parametres(request.user.company)
        serializer = VoipParametresSerializer(
            parametres, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MesIdentifiantsVoipView(APIView):
    """XPLT21 — Identifiants SIP DE l'utilisateur courant (Paramètres). Un
    utilisateur ne peut JAMAIS lire/modifier les identifiants d'un collègue —
    strictement les siens (posés côté serveur, jamais du corps de requête)."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        identifiant, _ = VoipIdentifiantUtilisateur.objects.get_or_create(
            company=request.user.company, utilisateur=request.user)
        return Response(VoipIdentifiantUtilisateurSerializer(identifiant).data)

    def patch(self, request):
        identifiant, _ = VoipIdentifiantUtilisateur.objects.get_or_create(
            company=request.user.company, utilisateur=request.user)
        serializer = VoipIdentifiantUtilisateurSerializer(
            identifiant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AppelViewSet(viewsets.ReadOnlyModelViewSet):
    """XPLT21 — Journal des appels VoIP de la société (scopé tenant).

    Écriture uniquement via les actions dédiées ci-dessous (jamais un
    create/update REST générique — la journalisation est TOUJOURS
    orchestrée côté serveur par `services.py`)."""
    serializer_class = AppelSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        user = self.request.user
        qs = Appel.objects.select_related('content_type').all()
        if user.company_id:
            return qs.filter(company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    @action(detail=False, methods=['post'], url_path='sortant',
            permission_classes=[IsAnyRole])
    def sortant(self, request):
        """Amorce un appel SORTANT. Corps : `{"numero": "..."}`. Renvoie 409
        si le softphone n'est pas configuré/actif pour cette société (sans
        config rien ne change)."""
        numero = (request.data.get('numero') or '').strip()
        if not numero:
            return Response(
                {'numero': 'Numéro requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        appel = services.demarrer_appel_sortant(
            request.user.company, request.user, numero)
        if appel is None:
            return Response(
                {'detail': "Softphone VoIP non configuré/actif."},
                status=status.HTTP_409_CONFLICT)
        return Response(
            AppelSerializer(appel).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='entrant',
            permission_classes=[IsAnyRole])
    def entrant(self, request):
        """Enregistre un appel ENTRANT (simulateur/notification fournisseur
        factice — un vrai webhook fournisseur sera branché avec le connecteur
        réel). Corps : `{"numero": "...", "external_call_id": "..."}`.
        Renvoie la fiche résolue (lead/client) pour le call-pop."""
        numero = (request.data.get('numero') or '').strip()
        if not numero:
            return Response(
                {'numero': 'Numéro requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        appel = services.recevoir_appel_entrant(
            request.user.company, numero,
            external_call_id=request.data.get('external_call_id') or '')
        if appel is None:
            return Response(
                {'detail': "Softphone VoIP non configuré/actif."},
                status=status.HTTP_409_CONFLICT)
        return Response(
            AppelSerializer(appel).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='terminer',
            permission_classes=[IsAnyRole])
    def terminer(self, request, pk=None):
        """Clôture l'appel : `{"duree_secondes": N, "issue": "..."}`. Pose la
        durée/issue et journalise le chatter de la fiche résolue."""
        appel = self.get_object()
        duree = request.data.get('duree_secondes') or 0
        try:
            duree = int(duree)
        except (TypeError, ValueError):
            return Response(
                {'duree_secondes': 'Entier requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        appel = services.terminer_appel(
            appel, duree_secondes=duree, issue=request.data.get('issue') or '')
        return Response(AppelSerializer(appel).data)
