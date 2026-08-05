"""NTADM22/NTADM32 — endpoints des sessions d'impersonation sous consentement.

Deux populations, deux gardes STRICTES :

* le **support éditeur** (`is_taqinor_support`, ou superuser) DEMANDE, DÉMARRE
  et TERMINE — il ne peut jamais consentir à sa propre demande ;
* l'**Administrateur du tenant cible** AUTORISE ou REFUSE — et lui seul.

Toute la journalisation part de la COUCHE VUE (jamais d'un service métier) :
`apps.audit.recorder.record` est appelé ici, comme le fait déjà
`authentication/views_console.py`. Le marquage systématique des lignes d'audit
écrites PENDANT une session vit dans `receivers.py`.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import impersonation_service
from .models import SessionImpersonation
from .serializers import SessionImpersonationSerializer

logger = logging.getLogger(__name__)


class IsTaqinorSupport(BasePermission):
    """Réservé au staff support de l'éditeur (NTADM22). Superuser = support."""
    message = "Réservé au staff support de l'éditeur."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(getattr(user, 'is_superuser', False)
                    or getattr(user, 'is_taqinor_support', False))


def _est_administrateur(user):
    """True si `user` peut CONSENTIR pour sa société (Administrateur)."""
    if not (user and user.is_authenticated):
        return False
    return bool(getattr(user, 'is_superuser', False)
                or getattr(user, 'is_admin_role', False)
                or getattr(user, 'role_legacy', '') == 'admin')


def _journaliser(demande, user, action, detail):
    """Trace d'audit posée depuis la VUE (jamais depuis un service métier)."""
    try:
        from apps.audit.recorder import record
        record(action, instance=demande, company=demande.company, user=user,
               detail=detail)
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('adminops: audit impersonation échoué', exc_info=True)


class ImpersonationDemandeView(APIView):
    """POST — le support DEMANDE une session (NTADM32) ; GET — ses demandes.

    Le motif est obligatoire : sans lui, 400 et AUCUNE ligne créée."""

    permission_classes = [IsTaqinorSupport]
    serializer_class = SessionImpersonationSerializer

    def get(self, request):
        qs = SessionImpersonation.objects.filter(
            initiee_par=request.user).order_by('-created_at', '-id')
        return Response(SessionImpersonationSerializer(qs, many=True).data)

    def post(self, request):
        from authentication.models import CustomUser

        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response({'detail': 'Le motif est obligatoire.'},
                            status=status.HTTP_400_BAD_REQUEST)

        cible_id = request.data.get('utilisateur_cible')
        cible = CustomUser.objects.filter(pk=cible_id).first() if cible_id else None
        if cible is None:
            return Response({'detail': 'Utilisateur cible introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            demande = impersonation_service.demander_impersonation(
                utilisateur_cible=cible, initiee_par=request.user, motif=motif)
        except impersonation_service.ImpersonationRefusee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        _journaliser(
            demande, request.user, 'create',
            f"Demande de session support sur « {cible} » — motif : {motif}")
        return Response(SessionImpersonationSerializer(demande).data,
                        status=status.HTTP_201_CREATED)


class ImpersonationEnAttenteView(APIView):
    """GET — demandes visant MA société, à autoriser (Administrateur)."""

    permission_classes = [IsAuthenticated]
    serializer_class = SessionImpersonationSerializer

    def get(self, request):
        if not _est_administrateur(request.user):
            return Response({'detail': "Réservé à l'Administrateur."},
                            status=status.HTTP_403_FORBIDDEN)
        qs = SessionImpersonation.objects.filter(
            company=request.user.company).order_by('-created_at', '-id')
        return Response(SessionImpersonationSerializer(qs, many=True).data)


class _ActionConsentementView(APIView):
    """Socle commun : seul un Administrateur DU TENANT CIBLE peut décider."""

    permission_classes = [IsAuthenticated]
    serializer_class = SessionImpersonationSerializer

    def _charger(self, request, pk):
        demande = SessionImpersonation.objects.filter(pk=pk).first()
        if demande is None:
            return None, Response({'detail': 'Demande introuvable.'},
                                  status=status.HTTP_404_NOT_FOUND)
        if not _est_administrateur(request.user):
            return None, Response({'detail': "Réservé à l'Administrateur."},
                                  status=status.HTTP_403_FORBIDDEN)
        # Isolation stricte : un Administrateur ne décide QUE pour sa société.
        if demande.company_id != getattr(request.user, 'company_id', None) \
                and not request.user.is_superuser:
            return None, Response({'detail': 'Demande introuvable.'},
                                  status=status.HTTP_404_NOT_FOUND)
        return demande, None


class ImpersonationConsentirView(_ActionConsentementView):
    """POST — « Autoriser » : SEULE porte vers une session exploitable."""

    def post(self, request, pk):
        demande, erreur = self._charger(request, pk)
        if erreur is not None:
            return erreur
        try:
            demande = impersonation_service.donner_consentement(
                demande, par=request.user)
        except impersonation_service.ImpersonationRefusee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        _journaliser(
            demande, request.user, 'update',
            'Consentement DONNÉ à une session support '
            f'(motif : {demande.motif}).')
        return Response(SessionImpersonationSerializer(demande).data)


class ImpersonationRefuserView(_ActionConsentementView):
    """POST — « Refuser » : définitif, plus aucun consentement possible."""

    def post(self, request, pk):
        demande, erreur = self._charger(request, pk)
        if erreur is not None:
            return erreur
        try:
            demande = impersonation_service.refuser(demande, par=request.user)
        except impersonation_service.ImpersonationRefusee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        _journaliser(demande, request.user, 'update',
                     'Session support REFUSÉE par le tenant.')
        return Response(SessionImpersonationSerializer(demande).data)


class ImpersonationDemarrerView(APIView):
    """POST — le support ouvre la session et reçoit un jeton BORNÉ.

    Échoue tant que le consentement n'est pas donné : c'est le point où
    l'invariant « pas de consentement ⇒ pas de session » est vérifié."""

    permission_classes = [IsTaqinorSupport]
    serializer_class = SessionImpersonationSerializer

    def post(self, request, pk):
        demande = SessionImpersonation.objects.filter(pk=pk).first()
        if demande is None:
            return Response({'detail': 'Demande introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if demande.initiee_par_id != request.user.pk \
                and not request.user.is_superuser:
            return Response({'detail': 'Demande introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            jeton = impersonation_service.emettre_jeton_impersonation(demande)
        except impersonation_service.ImpersonationRefusee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_403_FORBIDDEN)
        _journaliser(demande, request.user, 'login',
                     'Session support DÉMARRÉE.')
        return Response({
            'access': jeton,
            'session': SessionImpersonationSerializer(demande).data,
        })


class ImpersonationTerminerView(APIView):
    """POST — clôt la session (support OU Administrateur du tenant cible)."""

    permission_classes = [IsAuthenticated]
    serializer_class = SessionImpersonationSerializer

    def post(self, request, pk):
        demande = SessionImpersonation.objects.filter(pk=pk).first()
        if demande is None:
            return Response({'detail': 'Demande introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        autorise = (
            demande.initiee_par_id == request.user.pk
            or request.user.is_superuser
            or (_est_administrateur(request.user)
                and demande.company_id == getattr(
                    request.user, 'company_id', None))
        )
        if not autorise:
            return Response({'detail': 'Demande introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        demande = impersonation_service.terminer(demande)
        _journaliser(demande, request.user, 'logout',
                     'Session support TERMINÉE.')
        return Response(SessionImpersonationSerializer(demande).data)


class ImpersonationSessionActiveView(APIView):
    """GET — bandeau permanent : « Session support active — {nom} vous assiste ».

    Renvoie toujours 200 ; `active=False` pour une requête ordinaire."""

    permission_classes = [IsAuthenticated]
    serializer_class = SessionImpersonationSerializer

    def get(self, request):
        session = impersonation_service.session_depuis_requete(request)
        if session is None:
            return Response({'active': False})
        support = session.initiee_par
        nom = (getattr(support, 'get_full_name', lambda: '')() or '').strip() \
            or getattr(support, 'username', '') or 'Support'
        return Response({
            'active': True,
            'id': session.pk,
            'support_nom': nom,
            'motif': session.motif,
            'expire_le': session.expire_le,
            'message': f'Session support active — {nom} vous assiste',
        })
