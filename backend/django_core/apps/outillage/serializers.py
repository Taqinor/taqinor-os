from rest_framework import serializers

from .models import Outillage, KitOutillage, KitOutillageItem


class OutillageSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    emplacement_nom = serializers.CharField(
        source='emplacement.nom', read_only=True, default=None)

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

    def validate_emplacement(self, value):
        # Un emplacement ne peut appartenir qu'à la société de l'utilisateur.
        request = self.context.get('request')
        if value is not None and request is not None:
            if value.company_id != request.user.company_id:
                raise serializers.ValidationError("Emplacement inconnu.")
        return value


class KitOutillageItemSerializer(serializers.ModelSerializer):
    outil_nom = serializers.CharField(source='outil.nom', read_only=True)

    class Meta:
        model = KitOutillageItem
        # `company` n'est jamais exposée/écrite : posée côté serveur depuis le kit.
        fields = ['id', 'kit', 'outil', 'outil_nom', 'ordre']

    def validate(self, attrs):
        # Le kit ET l'outil doivent appartenir à la société de l'utilisateur.
        request = self.context.get('request')
        kit = attrs.get('kit') or getattr(self.instance, 'kit', None)
        outil = attrs.get('outil') or getattr(self.instance, 'outil', None)
        if request is not None:
            cid = request.user.company_id
            if kit is not None and kit.company_id != cid:
                raise serializers.ValidationError({'kit': "Kit inconnu."})
            if outil is not None and outil.company_id != cid:
                raise serializers.ValidationError({'outil': "Outil inconnu."})
        return attrs


class KitOutillageSerializer(serializers.ModelSerializer):
    items = KitOutillageItemSerializer(many=True, read_only=True)
    type_intervention_label = serializers.SerializerMethodField()

    class Meta:
        model = KitOutillage
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = [
            'id', 'nom', 'type_intervention', 'type_intervention_label',
            'ordre', 'actif', 'items',
        ]

    def get_type_intervention_label(self, obj):
        if not obj.type_intervention:
            return None
        # Libellé géré du type d'intervention (référentiel installations).
        from apps.installations.models import TypeIntervention
        t = TypeIntervention.objects.filter(
            company=obj.company, cle=obj.type_intervention).first()
        return t.libelle if t else obj.type_intervention
