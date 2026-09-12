"""ViewSets du module GRC & Conformité (NTGRC).

Tout viewset hérite de ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) :
queryset filtré sur ``request.user.company`` et ``company`` imposée côté
serveur dans ``perform_create``/``perform_update``, jamais lue du corps.
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    JournalDestruction, PolitiqueRetentionObjet, ViolationDonnees,
)
from .serializers import (
    JournalDestructionSerializer, PolitiqueRetentionObjetSerializer,
    ViolationDonneesSerializer,
)


class PolitiqueRetentionObjetViewSet(CompanyScopedModelViewSet):
    """NTGRC4 — CRUD des politiques de rétention par type d'objet.

    Donnée de CONFORMITÉ : réservée au palier admin/responsable, comme les
    registres RGPD de ``core`` (consentement, DSR, traitements CNDP). Pas de
    nouveau code de permission inventé — la même classe que ces registres.
    """

    queryset = PolitiqueRetentionObjet.objects.all()
    serializer_class = PolitiqueRetentionObjetSerializer
    permission_classes = [IsAdminOrResponsableTier]


class JournalDestructionViewSet(CompanyScopedModelViewSet):
    """NTGRC5 — journal APPEND-ONLY des destructions/anonymisations.

    ``http_method_names`` n'expose QUE la lecture et la création : aucune
    route d'update ni de delete n'existe. La garde d'immuabilité vit aussi au
    niveau du modèle, pour qu'aucun autre chemin de code ne puisse réécrire
    une ligne.

    Filtres : ``?type_objet=`` et ``?depuis=`` / ``?jusqu_a=`` (dates ISO).
    """

    queryset = JournalDestruction.objects.all()
    serializer_class = JournalDestructionSerializer
    permission_classes = [IsAdminOrResponsableTier]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        type_objet = (params.get('type_objet') or '').strip()
        if type_objet:
            qs = qs.filter(type_objet=type_objet)
        depuis = (params.get('depuis') or '').strip()
        if depuis:
            qs = qs.filter(created_at__date__gte=depuis)
        jusqu_a = (params.get('jusqu_a') or '').strip()
        if jusqu_a:
            qs = qs.filter(created_at__date__lte=jusqu_a)
        return qs

    def perform_create(self, serializer):
        """``company`` ET l'acteur sont posés CÔTÉ SERVEUR, jamais lus du corps."""
        serializer.save(
            company=self.request.user.company,
            executee_par=getattr(self.request.user, 'username', '') or '')


class ViolationDonneesViewSet(CompanyScopedModelViewSet):
    """NTGRC6 — registre des violations de données + délai légal de 72 h.

    Le statut et la date de notification CNDP ne s'écrivent pas au champ :
    ils bougent ENSEMBLE par les actions dédiées, sous garde de transition.
    """

    queryset = ViolationDonnees.objects.all()
    serializer_class = ViolationDonneesSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def perform_create(self, serializer):
        """Référence VD race-safe + société imposée côté serveur."""
        from .services import creer_violation

        champs = dict(serializer.validated_data)
        champs.pop('company', None)
        champs.pop('reference', None)
        serializer.instance = creer_violation(
            self.request.user.company, **champs)

    @action(detail=False, methods=['get'], url_path='echeance-depassee')
    def echeance_depassee(self, request):
        """Violations dont le délai de 72 h est dépassé sans notification."""
        from .selectors import violations_echeance_72h_depassee

        qs = violations_echeance_72h_depassee(request.user.company)
        return Response({'results': self.get_serializer(qs, many=True).data})

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer la violation (``{"statut": "en_analyse"}``)."""
        from .services import (
            TransitionViolationInterdite, changer_statut_violation,
        )

        violation = self.get_object()
        cible = (request.data.get('statut') or '').strip()
        try:
            changer_statut_violation(violation, cible)
        except TransitionViolationInterdite as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(self.get_serializer(violation).data)

    @action(detail=True, methods=['post'], url_path='notifier-cndp')
    def notifier_cndp(self, request, pk=None):
        """Enregistre la notification CNDP (date + statut, ensemble)."""
        from .services import TransitionViolationInterdite
        from .services import notifier_cndp as _notifier

        violation = self.get_object()
        try:
            _notifier(violation)
        except TransitionViolationInterdite as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(self.get_serializer(violation).data)
