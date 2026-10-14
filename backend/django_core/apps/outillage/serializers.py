from django.db import models
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import (
    BooleenStrict, ChampsStrictsMixin, IdInconnu404Mixin, TexteLie)
from core.mixins import SameCompanyFKSerializerMixin

from .models import Outillage, KitOutillage, KitOutillageItem


class OutillageSerializer(IdInconnu404Mixin, ChampsStrictsMixin,
                          SameCompanyFKSerializerMixin,
                          serializers.ModelSerializer):
    # ENF11 (api-fuzz) : emplacement inconnu OU d'une autre société = 404
    # (même réponse, aucun oracle) ; textes stricts.
    same_company_fields = ('emplacement',)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # ENF11 — TexteLie : la clé reste servie (null) dans une réponse PATCH, que
    # DRF saute sinon sur un sérialiseur partiel alors que le schéma l'exige.
    emplacement_nom = TexteLie(
        source='emplacement.nom', read_only=True, allow_null=True, default=None)

    # FG80 — badge « à calibrer » : intervalle > 0 ET date dépassée.
    a_calibrer = serializers.SerializerMethodField()

    class Meta:
        model = Outillage
        fields = [
            'id', 'nom', 'categorie', 'asset_tag', 'numero_serie',
            'emplacement', 'emplacement_nom', 'statut', 'statut_display',
            'date_achat', 'note',
            # FG80 — suivi calibration.
            'date_derniere_calibration', 'intervalle_calibration_mois',
            'date_prochaine_calibration', 'a_calibrer',
            'date_creation', 'date_modification',
        ]
        # company posée côté serveur — jamais lue du corps de requête.
        read_only_fields = ['date_creation', 'date_modification',
                            'date_prochaine_calibration']

    @extend_schema_field(serializers.BooleanField())
    def get_a_calibrer(self, obj):
        """FG80 — True si une calibration est due (date passée ou pas encore faite
        alors que l'intervalle est défini)."""
        if not obj.intervalle_calibration_mois:
            return False
        if obj.date_prochaine_calibration is None:
            # Intervalle défini mais jamais calibré → à calibrer.
            return True
        import datetime
        return obj.date_prochaine_calibration <= datetime.date.today()


class KitOutillageItemSerializer(IdInconnu404Mixin, SameCompanyFKSerializerMixin,
                                 serializers.ModelSerializer):
    # ENF17 — le kit ET l'outil d'une AUTRE société = id absent (400 « objet
    # inexistant », plus de message propre qui trahissait leur existence).
    same_company_fields = ('kit', 'outil')
    outil_nom = serializers.CharField(source='outil.nom', read_only=True)

    class Meta:
        model = KitOutillageItem
        # `company` n'est jamais exposée/écrite : posée côté serveur depuis le kit.
        fields = ['id', 'kit', 'outil', 'outil_nom', 'ordre']


class KitOutillageSerializer(serializers.ModelSerializer):
    # ENF11 — `actif` strictement booléen (0 / "oui" étaient coercés en silence).
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.BooleanField: BooleenStrict,
    }
    items = KitOutillageItemSerializer(many=True, read_only=True)
    type_intervention_label = serializers.SerializerMethodField()

    class Meta:
        model = KitOutillage
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = [
            'id', 'nom', 'type_intervention', 'type_intervention_label',
            'ordre', 'actif', 'items',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_type_intervention_label(self, obj):
        if not obj.type_intervention:
            return None
        # Libellé géré du type d'intervention (référentiel installations).
        from apps.installations.models import TypeIntervention
        t = TypeIntervention.objects.filter(
            company=obj.company, cle=obj.type_intervention).first()
        return t.libelle if t else obj.type_intervention
