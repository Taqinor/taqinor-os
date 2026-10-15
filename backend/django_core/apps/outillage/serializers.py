from django.db import models
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import (
    ChampsStrictsEntiersMixin, DateStricte, IdInconnu404Mixin, TexteLie)
from core.conflit_etat import ConflitEtat
from core.mixins import SameCompanyFKSerializerMixin

from .models import Outillage, KitOutillage, KitOutillageItem


#: Champs typés STRICTS d'un ``ModelSerializer`` outillage : texte, booléen et
#: ENTIER de modèle n'acceptent que leur type JSON déclaré (``0`` pour un texte,
#: ``"5"`` pour un entier → 400) et les dates sont ``AAAA-MM-JJ`` exactes
#: (DRF lisait aussi ``20000101``).
_MAPPING_STRICT = {
    **ChampsStrictsEntiersMixin.serializer_field_mapping,
    models.DateField: DateStricte,
}


class OutillageSerializer(IdInconnu404Mixin, ChampsStrictsEntiersMixin,
                          SameCompanyFKSerializerMixin,
                          serializers.ModelSerializer):
    # ENF11 (api-fuzz) : emplacement inconnu OU d'une autre société = 404
    # (même réponse, aucun oracle) ; champs stricts.
    serializer_field_mapping = _MAPPING_STRICT
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

    def validate(self, attrs):
        # La prochaine échéance = dernière calibration + N mois : une date en
        # fin de calendrier (9999) + un grand intervalle sort du calendrier
        # (OverflowError au save → 500). Combinaison que le schéma, champ par
        # champ, ne sait pas exclure : refus d'ÉTAT (409), jamais un 400.
        attrs = super().validate(attrs)
        derniere = attrs.get(
            'date_derniere_calibration',
            getattr(self.instance, 'date_derniere_calibration', None))
        intervalle = attrs.get(
            'intervalle_calibration_mois',
            getattr(self.instance, 'intervalle_calibration_mois', 0))
        if derniere is not None and intervalle:
            from dateutil.relativedelta import relativedelta
            try:
                derniere + relativedelta(months=intervalle)
            except (OverflowError, ValueError):
                raise ConflitEtat(
                    'La prochaine calibration sortirait du calendrier : '
                    "réduisez l'intervalle ou avancez la dernière date.")
        return attrs

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


class KitOutillageItemSerializer(IdInconnu404Mixin, ChampsStrictsEntiersMixin,
                                 SameCompanyFKSerializerMixin,
                                 serializers.ModelSerializer):
    # ENF17 — le kit ET l'outil d'une AUTRE société = id absent (400 « objet
    # inexistant », plus de message propre qui trahissait leur existence).
    same_company_fields = ('kit', 'outil')
    outil_nom = serializers.CharField(source='outil.nom', read_only=True)

    class Meta:
        model = KitOutillageItem
        # `company` n'est jamais exposée/écrite : posée côté serveur depuis le kit.
        fields = ['id', 'kit', 'outil', 'outil_nom', 'ordre']


class KitOutillageSerializer(ChampsStrictsEntiersMixin,
                             serializers.ModelSerializer):
    # ENF11 — texte, booléen et entier STRICTS : `type_intervention: 0` était
    # coercé en "0" (accepté alors que le schéma exige une chaîne), `actif`
    # 0 / "oui" aussi.
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
