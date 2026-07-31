"""NTEXT10 — API du report-builder : définitions de rapport croisé sauvegardées.

CRUD scopé société (``core.viewsets.CompanyScopedModelViewSet``) + un
``POST …/rapport-definitions/<id>/executer/`` qui REJOUE la définition :

  1. ``core.data_explorer.run_query(dataset, company, user, spec)`` — la portée
     société est portée par le ``queryset_provider`` du dataset (déjà scopé),
     jamais reconstruite ici ;
  2. si la définition porte un ``pivot_spec``, ``core.pivot.build_pivot`` croise
     le résultat plat (transformation PURE, sans accès base).

Aucune importation d'app métier : le lien au domaine est le NOM du dataset,
résolu par le noyau — même frontière que ``core.SavedQuery``.
"""
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import RapportDefinition


class RapportDefinitionSerializer(serializers.ModelSerializer):
    partage_label = serializers.CharField(
        source='get_partage_display', read_only=True)
    owner_username = serializers.CharField(
        source='owner.username', read_only=True, default='')

    class Meta:
        model = RapportDefinition
        # company + owner sont posés CÔTÉ SERVEUR — jamais lus du corps.
        fields = [
            'id', 'titre', 'dataset', 'spec', 'pivot_spec', 'partage',
            'partage_label', 'owner_username', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'partage_label', 'owner_username', 'created_at',
            'updated_at',
        ]

    def validate_dataset(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le dataset est requis.')
        return value


class RapportDefinitionViewSet(CompanyScopedModelViewSet):
    """CRUD + exécution des définitions de rapport, bornés à la société.

    Visibilité : ses propres rapports + ceux partagés à la société (même
    modèle personnel/société que ``core.SavedQuery``). Le filtre société de
    ``CompanyScopedModelViewSet`` reste appliqué en premier — un rapport
    ``societe`` ne franchit JAMAIS la frontière du tenant.
    """
    serializer_class = RapportDefinitionSerializer
    queryset = RapportDefinition.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        return qs.filter(
            Q(owner=user)
            | Q(partage=RapportDefinition.Partage.SOCIETE)
            | Q(owner__isnull=True)
        ).distinct()

    def perform_create(self, serializer):
        # company forcée côté serveur (socle) ; owner = utilisateur courant.
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='executer')
    def executer(self, request, pk=None):
        """Rejoue la définition et renvoie ``{rows}`` (+ ``pivot`` si demandé)."""
        from core import data_explorer
        from core.formula import FormulaError
        from core.pivot import PivotSpec, build_pivot

        obj = self.get_object()
        try:
            rows = data_explorer.run_query(
                obj.dataset, request.user.company, request.user,
                obj.spec or {})
        except data_explorer.DatasetInconnu as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except (data_explorer.ChampNonAutorise, FormulaError) as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        payload = {'rows': rows}
        pivot_spec = obj.pivot_spec or {}
        if pivot_spec:
            try:
                spec = PivotSpec(**pivot_spec)
            except (TypeError, ValueError) as exc:
                return Response({'detail': str(exc)},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                payload['pivot'] = build_pivot(rows, spec)
            except FormulaError as exc:
                return Response({'detail': str(exc)},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)
