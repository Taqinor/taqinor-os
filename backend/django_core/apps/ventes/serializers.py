from django.utils import timezone
from rest_framework import serializers
from .models import (
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir,
)


class LigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        fields = '__all__'

    def create(self, validated_data):
        # Réforme TVA 2024–2026 : toute NOUVELLE ligne porte son propre taux,
        # copié du produit (10 % panneaux PV, 20 % le reste) quand il n'est pas
        # fourni. Les lignes historiques (taux NULL) restent rendues au taux
        # global de leur devis — jamais réécrites.
        if validated_data.get('taux_tva') is None:
            from decimal import Decimal
            produit = validated_data.get('produit')
            produit_tva = getattr(produit, 'tva', None)
            validated_data['taux_tva'] = (
                produit_tva if produit_tva is not None else Decimal('20.00'))
        return super().create(validated_data)


class DevisSerializer(serializers.ModelSerializer):
    lignes = LigneDevisSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # Total d'AFFICHAGE canonique : pour un devis à deux options, le total de
    # l'option 1 (remise incluse) — jamais la somme des deux options.
    total_affiche = serializers.SerializerMethodField()
    nb_options = serializers.SerializerMethodField()
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    lead_nom = serializers.SerializerMethodField()

    def _display(self, obj):
        if not hasattr(obj, '_display_totals_cache'):
            from .quote_engine.builder import display_totals
            obj._display_totals_cache = display_totals(obj)
        return obj._display_totals_cache

    def get_total_affiche(self, obj):
        return self._display(obj)['total']

    def get_nb_options(self, obj):
        return self._display(obj)['nb_options']

    # Solde du devis : total TTC, montant facturé, payé, restant + avancement
    # de l'échéancier. Calculé par l'unique helper apps.ventes.utils.echeancier.
    solde = serializers.SerializerMethodField()

    def get_lead_nom(self, obj):
        if not obj.lead_id:
            return None
        return f"{obj.lead.nom} {obj.lead.prenom or ''}".strip()

    def get_solde(self, obj):
        from .utils.echeancier import solde_devis
        s = solde_devis(obj)
        return {k: str(v) for k, v in s.items()}

    # Chantier lié (s'il existe) — pour le lien devis ↔ chantier dans l'UI.
    chantier = serializers.SerializerMethodField()

    def get_chantier(self, obj):
        from apps.installations.models import Installation
        inst = Installation.objects.filter(devis=obj).first()
        if inst is None:
            return None
        return {'id': inst.id, 'reference': inst.reference,
                'statut': inst.statut}

    class Meta:
        model = Devis
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_creation']


class DevisWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées.

    Le client devient optionnel À LA CRÉATION quand un lead est fourni : il est
    alors résolu côté serveur depuis le lead (apps.crm.services), jamais déduit
    côté navigateur. La vue garantit qu'au moins l'un des deux est présent et
    que lead/client appartiennent à la société de l'utilisateur.
    """
    class Meta:
        model = Devis
        exclude = ['reference', 'fichier_pdf']
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = ['created_by', 'date_creation', 'company']
        extra_kwargs = {'client': {'required': False}}


class BonCommandeSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    has_facture = serializers.SerializerMethodField()

    class Meta:
        model = BonCommande
        fields = '__all__'
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = ['reference', 'date_creation', 'company']

    def get_has_facture(self, obj):
        return Facture.objects.filter(bon_commande=obj).exists()


class LigneFactureSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneFacture
        fields = '__all__'

    def create(self, validated_data):
        # Réforme TVA 2024–2026 : toute NOUVELLE ligne porte son propre taux,
        # copié du produit (10 % panneaux PV, 20 % le reste) quand il n'est pas
        # fourni — exactement comme LigneDevis. Les lignes historiques (taux
        # NULL) restent rendues au taux global de leur facture.
        if validated_data.get('taux_tva') is None:
            from decimal import Decimal
            produit = validated_data.get('produit')
            produit_tva = getattr(produit, 'tva', None)
            validated_data['taux_tva'] = (
                produit_tva if produit_tva is not None else Decimal('20.00'))
        return super().create(validated_data)


class PaiementSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = Paiement
        fields = '__all__'
        # company/created_by forcés côté serveur — jamais depuis le corps.
        read_only_fields = ['company', 'created_by', 'date_creation', 'facture']


class FactureSerializer(serializers.ModelSerializer):
    lignes = LigneFactureSerializer(many=True, read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    montant_paye = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    montant_du = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    avoirs_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    avoirs = serializers.SerializerMethodField()
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    type_facture_display = serializers.CharField(source='get_type_facture_display', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    # Ventilation TVA par taux (10 %/20 %), réconciliée au centime.
    tva_par_taux = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    jours_retard = serializers.IntegerField(read_only=True)

    def get_tva_par_taux(self, obj):
        return [
            {'taux': str(b['taux']), 'base_ht': str(b['base_ht']),
             'montant': str(b['montant'])}
            for b in obj.tva_par_taux
        ]

    def get_avoirs(self, obj):
        return [
            {'id': a.id, 'reference': a.reference, 'statut': a.statut,
             'total_ttc': str(a.total_ttc), 'motif': a.motif}
            for a in obj.avoirs.all()
        ]

    class Meta:
        model = Facture
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_emission']

    def get_is_overdue(self, obj):
        return (
            obj.statut == Facture.Statut.EMISE
            and obj.date_echeance is not None
            and obj.date_echeance < timezone.now().date()
        )


class FactureWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées."""
    class Meta:
        model = Facture
        exclude = ['reference', 'fichier_pdf']
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = ['created_by', 'date_emission', 'company']


class LigneAvoirSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LigneAvoir
        fields = ['id', 'produit', 'designation', 'quantite', 'prix_unitaire',
                  'remise', 'taux_tva', 'total_ht']


class AvoirSerializer(serializers.ModelSerializer):
    lignes = LigneAvoirSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    tva_par_taux = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)
    client_nom = serializers.SerializerMethodField()

    class Meta:
        model = Avoir
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf',
                            'date_emission', 'company']

    def get_tva_par_taux(self, obj):
        return [
            {'taux': str(b['taux']), 'base_ht': str(b['base_ht']),
             'montant': str(b['montant'])}
            for b in obj.tva_par_taux
        ]

    def get_client_nom(self, obj):
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip() if c else None


class FollowupLevelSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import FollowupLevel
        model = FollowupLevel
        fields = ['id', 'ordre', 'nom', 'delai_jours', 'message']


class RelanceLogSerializer(serializers.ModelSerializer):
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        from .models import RelanceLog
        model = RelanceLog
        fields = ['id', 'facture', 'niveau', 'niveau_nom', 'note', 'date',
                  'created_by_nom']
        read_only_fields = fields
