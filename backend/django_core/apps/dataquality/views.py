"""NTDATA14/15 — surface HTTP de la qualité de données.

* ``/dataquality/regles/``   — CRUD des règles (company forcée serveur) ;
* ``/dataquality/rapport/``  — dernier taux de conformité par règle
  (``?entite=`` pour restreindre à un dataset ; ``?evaluer=1`` recalcule
  maintenant plutôt que d'attendre le job quotidien).

Toutes les lectures sont bornées à ``request.user.company`` par ``TenantMixin``
et par le queryset DÉJÀ scopé des datasets. Réservé au palier
responsable/admin : un rapport de qualité expose des identifiants de fiches
non conformes.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin
from core.mixins import TenantMixin

from . import selectors, services
from .models import RegleQualite, ResultatQualite


class RegleQualiteSerializer(serializers.ModelSerializer):
    type_regle_label = serializers.CharField(
        source='get_type_regle_display', read_only=True)
    severite_label = serializers.CharField(
        source='get_severite_display', read_only=True)

    class Meta:
        model = RegleQualite
        # `company` posée côté serveur — jamais lue du corps.
        fields = [
            'id', 'libelle', 'entite', 'champ', 'type_regle',
            'type_regle_label', 'parametres', 'severite', 'severite_label',
            'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'type_regle_label', 'severite_label',
                            'created_at', 'updated_at']

    def validate(self, attrs):
        """Fait remonter la validation du modèle AU CHAMP fautif."""
        from django.core.exceptions import ValidationError as DjangoValidation

        instance = self.instance or RegleQualite()
        for champ, valeur in attrs.items():
            setattr(instance, champ, valeur)
        try:
            instance.clean()
        except DjangoValidation as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class ResultatQualiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultatQualite
        fields = ['id', 'regle', 'entite', 'nb_lignes', 'nb_violations',
                  'taux_conformite', 'echantillon', 'evalue_le']
        read_only_fields = fields


class RegleQualiteViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des règles de qualité, bornées à la société."""
    serializer_class = RegleQualiteSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = RegleQualite.objects.all()


class RapportQualiteView(APIView):
    """NTDATA15 — taux de conformité par règle (dernière évaluation).

    ``?entite=<dataset>`` restreint à une entité. ``?evaluer=1`` lance
    l'évaluation MAINTENANT (utile après avoir créé une règle) au lieu
    d'attendre le job quotidien ``dataquality.evaluer_qualite_donnees``.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('RapportQualiteReponse', {
            'entite': serializers.CharField(allow_null=True),
            'regles': serializers.JSONField(),
        }))
    def get(self, request):
        entite = request.query_params.get('entite') or None
        if request.query_params.get('evaluer') in ('1', 'true', 'True'):
            services.evaluer_regles(request.user.company, entite,
                                    user=request.user)
        return Response({
            'entite': entite,
            'regles': services.rapport_qualite(request.user.company, entite),
        })


class CompletudeView(APIView):
    """NTDATA16 — part des champs CRITIQUES renseignés, par entité métier.

    ``GET /dataquality/completude/`` rend un score par entité (clients,
    pistes, produits, factures) + le détail champ par champ, et la moyenne
    des entités réellement mesurables. Une entité sans fiche n'a pas de score
    (jamais 100 %) et n'entre pas dans la moyenne.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('CompletudeReponse', {
            'entites': serializers.JSONField(),
            'score_global': serializers.FloatField(allow_null=True),
        }))
    def get(self, request):
        return Response(selectors.completude_module(
            request.user.company, request.user))
