"""NTEXT16 — API CRUD des vues de liste personnalisées (``VuePersonnalisee``).

Scopée société par ``CompanyScopedModelViewSet`` (``company`` FORCÉE côté
serveur, jamais lue du corps) puis restreinte par
``core.vues.filtre_visibilite`` : ses propres vues + les vues de société + les
vues d'équipe des équipes dont l'utilisateur est membre.

``?cible=crm.lead`` filtre sur une liste donnée. ``core`` n'importe aucune app
métier : ``cible`` reste une chaîne.
"""
from rest_framework import serializers
from rest_framework.response import Response

from authentication.role_tiers import (
    ROLE_ADMIN, ROLE_NORMAL, ROLE_RESPONSABLE,
)

from .models import VuePersonnalisee
from .viewsets import CompanyScopedModelViewSet
from .vues import (
    demarquer_defauts_concurrents, filtre_visibilite, resoudre_vue_defaut,
)


#: NTEXT17 — paliers de rôle acceptés pour un défaut de rôle. Source unique de
#: vérité : ``authentication.role_tiers`` (module PUR, aucun modèle importé).
TIERS_VALIDES = frozenset({ROLE_ADMIN, ROLE_NORMAL, ROLE_RESPONSABLE})


class VuePersonnaliseeSerializer(serializers.ModelSerializer):
    partage_label = serializers.CharField(
        source='get_partage_display', read_only=True)
    owner_username = serializers.CharField(
        source='owner.username', read_only=True, default='')

    class Meta:
        model = VuePersonnalisee
        # company + owner sont posés CÔTÉ SERVEUR — jamais lus du corps.
        fields = ['id', 'cible', 'nom', 'config', 'partage', 'partage_label',
                  'equipe', 'est_defaut', 'role_tier', 'owner_username',
                  'created_at', 'updated_at']
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
        # NTEXT17 — un défaut de RÔLE doit désigner un palier connu.
        role_tier = (attrs.get(
            'role_tier', getattr(instance, 'role_tier', '')) or '').strip()
        if role_tier and role_tier not in TIERS_VALIDES:
            raise serializers.ValidationError(
                {'role_tier': 'Palier de rôle inconnu : '
                              f'{", ".join(sorted(TIERS_VALIDES))}.'})
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

    def list(self, request, *args, **kwargs):
        """NTEXT17 — ``?cible=<x>&defaut=1`` résout LA vue par défaut.

        Réponse littérale ``{'vue': <objet ou null>}`` (jamais une liste) : la
        liste appelante n'a qu'UNE vue à charger à l'ouverture. Sans ``defaut``,
        le comportement de liste historique est strictement inchangé.
        """
        if not _vrai(request.query_params.get('defaut')):
            return super().list(request, *args, **kwargs)
        cible = (request.query_params.get('cible') or '').strip()
        if not cible:
            return Response(
                {'detail': 'Le paramètre « cible » est requis pour résoudre '
                           'la vue par défaut.'},
                status=400)
        # get_queryset applique déjà société + visibilité + filtre cible.
        vue = resoudre_vue_defaut(self.get_queryset(), request.user, cible)
        return Response({
            'vue': self.get_serializer(vue).data if vue is not None else None,
        })

    def perform_create(self, serializer):
        # company forcée côté serveur (socle) ; owner = utilisateur courant.
        vue = serializer.save(company=self.request.user.company,
                              owner=self.request.user)
        demarquer_defauts_concurrents(vue)

    def perform_update(self, serializer):
        vue = serializer.save()
        demarquer_defauts_concurrents(vue)


def _vrai(valeur):
    """Le paramètre de requête vaut-il « vrai » ? (1/true/oui/on)"""
    return str(valeur or '').strip().lower() in ('1', 'true', 'vrai', 'oui',
                                                 'on')
