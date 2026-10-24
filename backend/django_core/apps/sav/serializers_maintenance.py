from django.db import models
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError

from core.champs_stricts import (
    ChampsStrictsSansDecimalMixin, DecimalSouple, EntierStrict,
    ListesStrictesMixin)
from core.mixins import SameCompanyFKSerializerMixin

from .models import ContratMaintenance, PrestationContrat


#: Bornes publiées des entiers du contrat (CI #997) : 50 ans, 10 ans en jours,
#: 1000 visites ou déplacements par an, un an en heures.
DUREE_MOIS_MAX = 600
JOURS_MAX = 3650
QUOTA_AN_MAX = 1000
HEURES_MAX = 8760


class _DecimalSansVide(DecimalSouple):
    """Décimal nullable où ``""`` N'EST PAS « non renseigné » (seul ``null`` l'est).

    ``DecimalField(allow_null=True)`` lit une chaîne vide comme ``None`` alors que le
    schéma publié (motif décimal non vide) la déclare invalide : api-fuzz « accepted
    schema-violating request » sur ``prestations[].prix_ht``. Les nombres JSON restent
    acceptés (l'écran envoie ``null`` pour un prix à renseigner) ET le schéma le dit
    (``DecimalSouple`` : chaîne OU nombre ; CI #997, ``prix_ht: 0`` était « invalide »
    au schéma mais accepté)."""

    def validate_empty_values(self, data):
        if isinstance(data, str) and not data.strip():
            self.fail('invalid')
        return serializers.Field.validate_empty_values(self, data)


#: Texte et booléens stricts (``0`` pour un booléen → 400), décimaux en chaîne
#: OU nombre publiés comme tels ; les entiers restent souples (l'écran de
#: contrat envoie des chaînes numériques issues de ses champs de saisie).
_MAPPING_CONTRAT = {
    **ChampsStrictsSansDecimalMixin.serializer_field_mapping,
    models.DecimalField: DecimalSouple,
}


class PrestationContratSerializer(serializers.ModelSerializer):
    """CIQ640 — prestation nommée (forme ``contract_samples/contrat_om.json``).

    Éditable (CIQ648) par le PATCH du contrat : ``incluse``, ``frequence_an``
    et ``prix_ht`` seulement ; ``id`` désigne la prestation du contrat,
    ``type`` / ``libelle`` restent ceux semés (prestations nommées)."""
    serializer_field_mapping = _MAPPING_CONTRAT
    id = EntierStrict(required=False)
    prix_ht = _DecimalSansVide(
        max_digits=10, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = PrestationContrat
        fields = ['id', 'type', 'libelle', 'incluse', 'frequence_an',
                  'prix_ht']
        read_only_fields = ['type', 'libelle']


class ContratMaintenanceSerializer(ListesStrictesMixin,
                                   SameCompanyFKSerializerMixin,
                                   serializers.ModelSerializer):
    serializer_field_mapping = _MAPPING_CONTRAT
    # ENF17 — client et chantier bornés à la société (les équipements le sont
    # par ``validate_equipements``).
    same_company_fields = ('client', 'installation')
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
        # CI #997 (api-fuzz) — bornes PUBLIÉES : ``duree_mois: 2147483646``
        # faisait déborder l'échéance (date_debut + durée → an > 9999, 500) ;
        # les délais SLA en jours alimentent un ``timedelta`` (débordement
        # au-delà de ~2,7 M d'années) ; ``pieces_couvertes_pct`` est un
        # pourcentage (0-100, l'aide du champ le disait déjà).
        extra_kwargs = {
            'duree_mois': {'max_value': DUREE_MOIS_MAX},
            'sla_response_days': {'max_value': JOURS_MAX},
            'sla_resolution_days': {'max_value': JOURS_MAX},
            'visites_incluses_an': {'max_value': QUOTA_AN_MAX},
            'deplacements_inclus_an': {'max_value': QUOTA_AN_MAX},
            'pieces_couvertes_pct': {'max_value': 100},
            'delai_intervention_heures': {'max_value': HEURES_MAX},
        }

    def get_origine(self, obj) -> dict:
        return {'devis_id': obj.origine_devis_id,
                'ligne_om': obj.origine_ligne_om_id}

    @extend_schema_field(serializers.DictField())
    def get_droits_restants(self, obj):
        from .droits_contrat import droits_restants
        return droits_restants(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
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
                # ENF11 : un id bien formé qui ne désigne aucune prestation de
                # CE contrat = ressource absente (404), pas un corps invalide.
                raise NotFound(
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

    @extend_schema_field(serializers.CharField())
    def get_prochaine_visite(self, obj):
        return obj.prochaine_visite().isoformat()

    @extend_schema_field(serializers.BooleanField())
    def get_due(self, obj):
        return obj.is_due()

    @extend_schema_field(serializers.BooleanField())
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
