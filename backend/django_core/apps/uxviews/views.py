from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import SavedView
from .serializers import SavedViewSerializer


class SavedViewViewSet(CompanyScopedModelViewSet):
    """NTUX1/2 — CRUD des vues sauvegardées, filtré par `?ecran=`. Une vue est
    visible si l'appelant en est le propriétaire, OU si elle est partagée à
    l'équipe (`visibilite=EQUIPE`) — la société est déjà bornée par
    `TenantMixin.get_queryset`. Lecture ouverte à tout rôle authentifié ;
    écriture limitée au propriétaire (une vue d'un autre utilisateur n'est
    modifiable/supprimable que si elle est la vue par défaut d'un rôle ET que
    l'appelant a le droit de la définir — cf. `IsResponsableOrAdmin`)."""
    queryset = SavedView.objects.select_related('owner', 'role').all()
    serializer_class = SavedViewSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ecran = self.request.query_params.get('ecran')
        if ecran:
            qs = qs.filter(ecran=ecran)
        user = self.request.user
        return qs.filter(
            Q(owner=user) | Q(visibilite=SavedView.Visibilite.EQUIPE),
        )

    def get_permissions(self):
        if self.action == 'definir_par_defaut_role':
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    def perform_create(self, serializer):
        # NTUX28 (limites anti-abus) reste hors périmètre de ce lot — posé ici
        # comme garde-fou de base minimal : owner/company toujours serveur.
        serializer.save(company=self.request.user.company, owner=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        # Garde-fou NTUX2 : une vue par défaut de rôle n'est modifiable que par
        # son propriétaire OU par qui a le droit de la (re)définir.
        if instance.owner_id != self.request.user.id and not (
            instance.est_defaut_role and IsResponsableOrAdmin().has_permission(self.request, self)
        ):
            raise PermissionDenied("Vous ne pouvez modifier que vos propres vues.")
        serializer.save()

    def perform_destroy(self, instance):
        # Garde-fou NTUX2 : une vue par défaut de rôle ne peut être supprimée
        # que par qui a le droit de la définir (jamais un simple propriétaire
        # accidentel — la vue peut appartenir à quelqu'un d'autre après un
        # transfert de portefeuille).
        if instance.est_defaut_role and not IsResponsableOrAdmin().has_permission(self.request, self):
            raise PermissionDenied(
                "Seul un Directeur/Admin peut supprimer une vue par défaut de rôle.",
            )
        if instance.owner_id != self.request.user.id and not instance.est_defaut_role:
            raise PermissionDenied("Vous ne pouvez supprimer que vos propres vues.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='definir-par-defaut-role')
    def definir_par_defaut_role(self, request, pk=None):
        """NTUX2 — Directeur/Admin uniquement. Définit CETTE vue comme vue par
        défaut du rôle (celui déjà porté par la vue, ou fourni dans le corps
        `{role: <id>}`). Un seul défaut actif par (company, ecran, role) : les
        autres vues du même rôle+écran perdent `est_defaut_role`."""
        instance = self.get_object()
        role_id = request.data.get('role', instance.role_id)
        if not role_id:
            raise ValidationError({'role': 'Un rôle est requis pour définir une vue par défaut.'})
        SavedView.objects.filter(
            company=instance.company, ecran=instance.ecran, role_id=role_id,
            est_defaut_role=True,
        ).exclude(pk=instance.pk).update(est_defaut_role=False)
        instance.role_id = role_id
        instance.est_defaut_role = True
        instance.visibilite = SavedView.Visibilite.EQUIPE
        instance.save(update_fields=['role', 'est_defaut_role', 'visibilite', 'updated_at'])
        return Response(SavedViewSerializer(instance).data)
