"""NTEXT16 — API CRUD des vues de liste personnalisées (``VuePersonnalisee``).

Scopée société par ``CompanyScopedModelViewSet`` (``company`` FORCÉE côté
serveur, jamais lue du corps) puis restreinte par
``core.vues.filtre_visibilite`` : ses propres vues + les vues de société + les
vues d'équipe des équipes dont l'utilisateur est membre.

``?cible=crm.lead`` filtre sur une liste donnée. ``core`` n'importe aucune app
métier : ``cible`` reste une chaîne.
"""
from rest_framework import serializers

from .models import VuePersonnalisee
from .viewsets import CompanyScopedModelViewSet
from .vues import filtre_visibilite


class VuePersonnaliseeSerializer(serializers.ModelSerializer):
    partage_label = serializers.CharField(
        source='get_partage_display', read_only=True)
    owner_username = serializers.CharField(
        source='owner.username', read_only=True, default='')

    class Meta:
        model = VuePersonnalisee
        # company + owner sont posés CÔTÉ SERVEUR — jamais lus du corps.
        fields = ['id', 'cible', 'nom', 'config', 'partage', 'partage_label',
                  'equipe', 'owner_username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'partage_label', 'owner_username',
                            'created_at', 'updated_at']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        partage = attrs.get(
            'partage',
            getattr(instance, 'partage', VuePersonnalisee.Partage.PRIVE))
        equipe = attrs.get('equipe', getattr(instance, 'equipe', ''))
        if partage == VuePersonnalisee.Partage.EQUIPE and not (equipe or '').strip():
            raise serializers.ValidationError(
                {'equipe': "Une vue partagée à l'équipe doit désigner une "
                           "équipe."})
        return attrs


class VuePersonnaliseeViewSet(CompanyScopedModelViewSet):
    """CRUD des vues personnalisées, bornées à la société ET à la visibilité."""

    serializer_class = VuePersonnaliseeSerializer
    queryset = VuePersonnalisee.objects.all()

    def get_queryset(self):
        qs = filtre_visibilite(super().get_queryset(), self.request.user)
        cible = self.request.query_params.get('cible')
        if cible:
            qs = qs.filter(cible=cible)
        return qs

    def perform_create(self, serializer):
        # company forcée côté serveur (socle) ; owner = utilisateur courant.
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)
