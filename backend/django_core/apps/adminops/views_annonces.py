"""NTADM18 — centre de notifications PRODUIT (annonces de l'éditeur).

Trois endpoints :

* ``GET  /api/django/adminops/annonces/`` — mes annonces, NON LUES D'ABORD ;
* ``POST /api/django/adminops/annonces/{id}/marquer-lu/`` — accusé de lecture ;
* ``POST /api/django/adminops/annonces/`` — publication (éditeur uniquement).

Garde de publication — DURCIE par rapport à un simple « Administrateur » : une
annonce produit est GLOBALE (elle atteint toutes les sociétés), donc la publier
est une action d'ÉDITEUR (superuser / `is_taqinor_support`). Laisser un
Administrateur de tenant diffuser vers les autres sociétés serait une
escalade de privilège inter-tenants. La LECTURE, elle, est ouverte à tout
utilisateur interne authentifié.

Aucun canal parallèle : la diffusion réutilise `notifications.notify` avec le
type `PRODUCT_ANNOUNCEMENT`, donc la cloche existante et les préférences
utilisateur s'appliquent telles quelles.
"""
from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AnnonceProduit, LectureAnnonce
from .serializers import AnnonceProduitSerializer
from .views_impersonation import IsTaqinorSupport

logger = logging.getLogger(__name__)

#: Garde-fou de taille : « corps markdown COURT » (NTADM18).
LONGUEUR_MAX_CORPS = 4000


def destinataires_annonce(annonce):
    """Utilisateurs internes actifs ciblés par `annonce`.

    `cible_roles` vide = TOUT LE MONDE (comportement par défaut). Les comptes
    de portail (client/fournisseur/partenaire) sont toujours exclus : une
    nouveauté de l'ERP ne les concerne pas."""
    from authentication.models import CustomUser

    qs = CustomUser.objects.filter(
        is_active=True, portee=CustomUser.PORTEE_INTERNE)
    roles = list(annonce.cible_roles.values_list('pk', flat=True))
    if roles:
        qs = qs.filter(role_id__in=roles)
    return qs


def diffuser_annonce(annonce):
    """Notifie chaque destinataire (best-effort, isolé par destinataire)."""
    lien = f'/admin/annonces/{annonce.pk}'
    envoyees = 0
    for user in destinataires_annonce(annonce):
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
            notify(user, EventType.PRODUCT_ANNOUNCEMENT, annonce.titre,
                   body=annonce.corps, link=lien,
                   company=getattr(user, 'company', None))
            envoyees += 1
        except Exception:  # noqa: BLE001 — un destinataire KO n'arrête pas les autres
            logger.warning('adminops: notification annonce produit échouée '
                           '(user %s)', getattr(user, 'pk', None))
    return envoyees


class AnnonceProduitListView(APIView):
    """GET — mes annonces (non lues d'abord) ; POST — publication (éditeur)."""

    permission_classes = [IsAuthenticated]
    serializer_class = AnnonceProduitSerializer

    def get(self, request):
        lues = set(LectureAnnonce.objects.filter(
            utilisateur=request.user).values_list('annonce_id', flat=True))
        # Seules les annonces déjà publiées (date de publication atteinte).
        annonces = AnnonceProduit.objects.filter(
            date_publication__lte=timezone.now()).prefetch_related('cible_roles')

        role_id = getattr(request.user, 'role_id', None)
        visibles = [
            a for a in annonces
            if not a.cible_roles.exists()
            or (role_id is not None
                and a.cible_roles.filter(pk=role_id).exists())
        ]
        # Non lues d'abord, puis les plus récentes.
        visibles.sort(
            key=lambda a: (a.pk in lues, -a.date_publication.timestamp()))

        donnees = AnnonceProduitSerializer(
            visibles, many=True, context={'lues': lues}).data
        return Response({
            'results': donnees,
            'non_lues': sum(1 for a in visibles if a.pk not in lues),
        })

    def post(self, request):
        # Garde de publication : éditeur uniquement (portée globale).
        if not IsTaqinorSupport().has_permission(request, self):
            return Response(
                {'detail': "La publication d'une annonce produit est réservée "
                           "à l'éditeur."},
                status=status.HTTP_403_FORBIDDEN)

        titre = (request.data.get('titre') or '').strip()
        if not titre:
            return Response({'detail': 'Le titre est obligatoire.'},
                            status=status.HTTP_400_BAD_REQUEST)
        corps = (request.data.get('corps') or '').strip()
        if len(corps) > LONGUEUR_MAX_CORPS:
            return Response(
                {'detail': f'Le corps dépasse {LONGUEUR_MAX_CORPS} caractères.'},
                status=status.HTTP_400_BAD_REQUEST)

        annonce = AnnonceProduit.objects.create(
            titre=titre[:200], corps=corps, auteur=request.user)

        roles = request.data.get('cible_roles') or []
        if isinstance(roles, list) and roles:
            annonce.cible_roles.set(roles)

        diffuser_annonce(annonce)
        return Response(AnnonceProduitSerializer(annonce).data,
                        status=status.HTTP_201_CREATED)


class AnnonceProduitMarquerLuView(APIView):
    """POST — accusé de lecture (idempotent : deux appels = un seul accusé)."""

    permission_classes = [IsAuthenticated]
    serializer_class = AnnonceProduitSerializer

    def post(self, request, pk):
        annonce = AnnonceProduit.objects.filter(pk=pk).first()
        if annonce is None:
            return Response({'detail': 'Annonce introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        LectureAnnonce.objects.get_or_create(
            annonce=annonce, utilisateur=request.user)
        return Response(AnnonceProduitSerializer(
            annonce, context={'lues': {annonce.pk}}).data)
