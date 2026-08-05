"""N101(b) — inscription self-service des installateurs pilotes (PARQUÉE).

Deux surfaces bien séparées :

* PUBLIQUE — ``POST /api/django/auth/signup-demande/`` : dépose une demande.
  Parquée par défaut (``TENANT_SIGNUP_ENABLED``) : éteinte, l'endpoint est
  traité comme INEXISTANT (404) et n'enregistre rien, exactement comme le
  formulaire de contact. Anti-abus : throttle par IP + champ « pot de miel ».
  **Elle ne crée JAMAIS ni compte ni société** — seulement une intention.

* CONSOLE — réservée au superuser : file d'approbation. C'est l'approbation du
  fondateur qui déclenche la création réelle du tenant (flux N100b), jamais
  l'endpoint public. Cela garde la surface d'authentification minimale tout en
  permettant des partenaires pilotes.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from authentication.views_console import IsSuperuserConsole

from .models import DemandeInscription
from .serializers import DemandeInscriptionSerializer

logger = logging.getLogger(__name__)


class SignupDemandeThrottle(AnonRateThrottle):
    """Même esprit que ``authentication.throttles`` : borne par IP."""
    rate = '5/hour'


class SignupDemandeView(APIView):
    """POST public — dépose une demande d'inscription (aucun compte créé)."""

    permission_classes = [AllowAny]
    throttle_classes = [SignupDemandeThrottle]
    serializer_class = DemandeInscriptionSerializer

    def post(self, request):
        # Interrupteur PARKED : éteint, l'endpoint n'existe pas.
        if not getattr(settings, 'TENANT_SIGNUP_ENABLED', False):
            raise Http404("L'inscription self-service est désactivée.")

        # Pot de miel : un vrai navigateur laisse ce champ vide. Rempli = bot →
        # on répond 201 sans rien enregistrer (ne pas informer l'attaquant).
        if (request.data.get('site_web') or '').strip():
            return Response({'detail': 'Demande enregistrée.'},
                            status=status.HTTP_201_CREATED)

        societe = (request.data.get('societe') or '').strip()[:200]
        nom = (request.data.get('nom') or '').strip()[:150]
        email = (request.data.get('email') or '').strip()[:254]
        telephone = (request.data.get('telephone') or '').strip()[:30]

        if not all([societe, nom, email]):
            return Response(
                {'detail': 'Société, nom et email sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        if '@' not in email or '.' not in email.split('@')[-1]:
            return Response({'detail': 'Adresse email invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Idempotence douce : un double clic ne dépose pas deux demandes pour
        # le même email tant que la première est en attente. Volontairement un
        # filter+create explicite (et non `get_or_create`) : il n'existe pas de
        # contrainte d'unicité derrière ce couple, donc autant ne pas faire
        # croire à une garantie de course qu'on n'a pas. Une éventuelle demande
        # en double est de toute façon inoffensive — le fondateur tranche.
        demande = DemandeInscription.objects.filter(
            email__iexact=email,
            statut=DemandeInscription.Statut.EN_ATTENTE).first()
        if demande is None:
            demande = DemandeInscription.objects.create(
                societe=societe, nom=nom, email=email, telephone=telephone)
        return Response({'detail': 'Demande enregistrée.', 'id': demande.pk},
                        status=status.HTTP_201_CREATED)


class DemandeInscriptionListView(APIView):
    """GET — file d'approbation du fondateur (superuser)."""

    permission_classes = [IsSuperuserConsole]
    serializer_class = DemandeInscriptionSerializer

    def get(self, request):
        qs = DemandeInscription.objects.all()
        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return Response({
            'results': DemandeInscriptionSerializer(qs, many=True).data,
            'en_attente': DemandeInscription.objects.filter(
                statut=DemandeInscription.Statut.EN_ATTENTE).count(),
        })


class DemandeInscriptionDecisionView(APIView):
    """POST — approuver (crée le tenant, N100b) ou refuser une demande."""

    permission_classes = [IsSuperuserConsole]
    serializer_class = DemandeInscriptionSerializer

    def post(self, request, pk, action=None):
        demande = DemandeInscription.objects.filter(pk=pk).first()
        if demande is None:
            return Response({'detail': 'Demande introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if demande.statut != DemandeInscription.Statut.EN_ATTENTE:
            return Response(
                {'detail': 'Cette demande a déjà été traitée.'},
                status=status.HTTP_400_BAD_REQUEST)

        if action == 'refuser':
            demande.statut = DemandeInscription.Statut.REFUSEE
            demande.traite_le = timezone.now()
            demande.traite_par = request.user
            demande.notes = (request.data.get('notes') or demande.notes)
            demande.save()
            return Response(DemandeInscriptionSerializer(demande).data)

        # Approbation : c'est ICI, et seulement ici, que le tenant est créé.
        resultat, erreur = _creer_tenant_depuis_demande(demande, request)
        if erreur is not None:
            return erreur

        demande.statut = DemandeInscription.Statut.APPROUVEE
        demande.traite_le = timezone.now()
        demande.traite_par = request.user
        demande.company_creee_id = resultat.get('id')
        demande.save()
        return Response({
            **DemandeInscriptionSerializer(demande).data,
            'tenant': resultat,
        })


def _creer_tenant_depuis_demande(demande, request):
    """Rejoue le flux N100(b) — jamais une création de société hand-roulée."""
    from authentication.views_console_create import TenantConsoleCreateView

    vue = TenantConsoleCreateView()
    fausse_requete = _RequeteCreation(
        user=request.user,
        data={'nom': demande.societe, 'email': demande.email})
    reponse = vue.post(fausse_requete)
    if reponse.status_code not in (200, 201):
        return None, Response(reponse.data, status=reponse.status_code)
    return reponse.data, None


class _RequeteCreation:
    """Adaptateur minimal : réutiliser la vue N100b sans dupliquer sa logique."""

    def __init__(self, user, data):
        self.user = user
        self.data = data
