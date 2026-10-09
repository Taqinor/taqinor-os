from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ContratMaintenance, PrestationContrat


class PrestationContratSerializer(serializers.ModelSerializer):
    """CIQ640 — prestation nommée (forme ``contract_samples/contrat_om.json``).

    Éditable (CIQ648) par le PATCH du contrat : ``incluse``, ``frequence_an``
    et ``prix_ht`` seulement ; ``id`` désigne la prestation du contrat,
    ``type`` / ``libelle`` restent ceux semés (prestations nommées)."""
    id = serializers.IntegerField(required=False)

    class Meta:
        model = PrestationContrat
        fields = ['id', 'type', 'libelle', 'incluse', 'frequence_an',
                  'prix_ht']
        read_only_fields = ['type', 'libelle']


class ContratMaintenanceSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    prochaine_visite = serializers.SerializerMethodField()
    due = serializers.SerializerMethodField()
    renouvellement_du = serializers.SerializerMethodField()
    # AUD502/D13 — expiration réelle du contrat (date_debut + duree_mois) et
    # sa fenêtre de grâce de 30 jours, exposées à l'écran de renouvellement.
    date_expiration = serializers.SerializerMethodField()
    expire = serializers.SerializerMethodField()
    en_periode_grace = serializers.SerializerMethodField()
    a_renouveler = serializers.SerializerMethodField()
    # ASAV73 (D-ASAV-3 a) — ``prochaine_facturation`` / ``facturation_due``
    # RETIRÉS : aucun écrivain ne facture plus les périodes (app contrats
    # parquée, SOLMVP14) ; le prix du contrat reste servi.
    # XCTR2 — registre des équipements couverts (lecture enrichie).
    equipements_detail = serializers.SerializerMethodField()
    # XCTR3 — droits inclus (entitlements), compteurs consommés/restants.
    droits_restants = serializers.SerializerMethodField()
    # CIQ640 — contrat O&M C&I : prestations nommées imbriquées (lecture) et
    # origine {devis_id, ligne_om} (contrat partagé ``contrat_om.json``).
    prestations = PrestationContratSerializer(many=True, required=False)
    origine = serializers.SerializerMethodField()

    class Meta:
        model = ContratMaintenance
        fields = ['id', 'client', 'client_nom', 'installation', 'periodicite',
                  'date_debut', 'derniere_visite', 'prix', 'actif', 'notes',
                  'duree_mois', 'date_renouvellement', 'renouvellement_du',
                  # AUD502 — échéance duree_mois + grâce 30 j.
                  'date_expiration', 'expire', 'en_periode_grace',
                  'a_renouveler',
                  'prochaine_visite', 'due',
                  # FG40
                  'facturation_active', 'derniere_facturation',
                  # XSAV7 — overrides SLA optionnels du contrat.
                  'sla_response_days', 'sla_resolution_days',
                  # XCTR2 — registre des équipements couverts.
                  'equipements', 'equipements_detail',
                  # XCTR3 — droits inclus (entitlements).
                  'visites_incluses_an', 'deplacements_inclus_an',
                  'pieces_couvertes_pct', 'droits_restants',
                  # CIQ640 — contrat O&M C&I (contrat_om.json).
                  'prestations', 'delai_intervention_heures', 'origine',
                  'date_creation']
        read_only_fields = ['derniere_visite', 'derniere_facturation', 'date_creation']

    def get_origine(self, obj) -> dict:
        return {'devis_id': obj.origine_devis_id,
                'ligne_om': obj.origine_ligne_om_id}

    def get_droits_restants(self, obj):
        from .selectors import droits_restants
        return droits_restants(obj)

    def get_equipements_detail(self, obj):
        return [
            {
                'id': e.id,
                'numero_serie': getattr(e, 'numero_serie', None),
                'produit_nom': getattr(e.produit, 'nom', None),
            }
            for e in obj.equipements.select_related('produit').all()
        ]

    # CIQ648 — prestations éditées par le PATCH du contrat (jamais créées ni
    # rattachées à un autre contrat : l'``id`` doit être une prestation de CE
    # contrat). Vide = « à renseigner » (NULL), jamais un nombre pré-rempli.
    _CHAMPS_PRESTATION = ('incluse', 'frequence_an', 'prix_ht')

    def create(self, validated_data):
        validated_data.pop('prestations', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        prestations = validated_data.pop('prestations', None)
        if prestations is not None:
            existantes = {p.pk: p for p in instance.prestations.all()}
            if any(e.get('id') not in existantes for e in prestations):
                raise ValidationError(
                    {'prestations': 'Prestation inconnue pour ce contrat.'})
            for entree in prestations:
                prestation = existantes[entree['id']]
                champs = [c for c in self._CHAMPS_PRESTATION if c in entree]
                for champ in champs:
                    setattr(prestation, champ, entree[champ])
                if champs:
                    prestation.save(update_fields=champs)
        return super().update(instance, validated_data)

    def validate_equipements(self, value):
        """XCTR2 — un équipement d'une autre société est refusé (400) : le
        registre de couverture ne doit jamais lier du matériel étranger."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        for equipement in value:
            if equipement.company_id != company.id:
                raise ValidationError('Équipement inconnu.')
        return value

    def get_prochaine_visite(self, obj):
        return obj.prochaine_visite().isoformat()

    def get_due(self, obj):
        return obj.is_due()

    def get_renouvellement_du(self, obj):
        return obj.renouvellement_du()

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_date_expiration(self, obj):
        """AUD502 — échéance = date_debut + duree_mois (None si sans durée)."""
        expiration = obj.date_expiration()
        return expiration.isoformat() if expiration else None

    @extend_schema_field(serializers.BooleanField())
    def get_expire(self, obj):
        """AUD502 — échéance dépassée (grâce non comprise)."""
        return obj.est_expire()

    @extend_schema_field(serializers.BooleanField())
    def get_en_periode_grace(self, obj):
        """AUD502 — expiré mais encore couvrant (grâce 30 j) : à renouveler
        d'urgence, la couverture tombe à la fin de la fenêtre."""
        return obj.en_periode_grace()

    @extend_schema_field(serializers.BooleanField())
    def get_a_renouveler(self, obj):
        """AUD502 — date de renouvellement atteinte OU échéance dépassée."""
        return obj.a_renouveler()
