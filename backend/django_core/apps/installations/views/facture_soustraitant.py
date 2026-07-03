"""Vues DC34 — AP sous-traitant PAR LA CHAÎNE STANDARD (plus de modèle parallèle).

Les factures & règlements des sous-traitants ne vivent plus dans un modèle
dédié : ils passent par la chaîne comptes-à-payer standard de l'app stock
(``FactureFournisseur`` / ``PaiementFournisseur``), filtrée aux fournisseurs de
type « service ». Ces deux vues restent les endpoints ``factures-sous-traitant/``
et ``paiements-sous-traitant/`` (contrat d'API FG306 préservé) mais orchestrent
les objets stock à travers ses SÉLECTEURS et SERVICES — jamais par import de
``apps.stock.models`` (contrat de découplage M1).

Lecture & écriture responsable/admin — montants INTERNES (jamais client-facing).
Multi-tenant : société + ``created_by`` posés côté serveur ; le sous-traitant
ciblé est validé tenant ET de type « service ».
"""
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from apps.stock import selectors as stock_selectors
from apps.stock import services as stock_services


class _FactureSousTraitantSerializer(serializers.Serializer):
    """DC34 — vue à plat d'une facture sous-traitant AU-DESSUS d'une
    ``stock.FactureFournisseur``. Le champ ``sous_traitant`` mappe le
    ``fournisseur`` (type=service) ; les montants et le solde sont INTERNES."""
    id = serializers.IntegerField(read_only=True)
    sous_traitant = serializers.IntegerField()
    sous_traitant_nom = serializers.SerializerMethodField()
    numero = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    reference = serializers.CharField(read_only=True)
    montant_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0)
    montant_tva = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0)
    montant_ttc = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0)
    date_facture = serializers.DateField(required=False, allow_null=True)
    date_echeance = serializers.DateField(required=False, allow_null=True)
    statut = serializers.CharField(read_only=True)
    statut_display = serializers.SerializerMethodField()
    total_paye = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    reste_a_payer = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    note = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    date_creation = serializers.DateTimeField(read_only=True)

    def get_sous_traitant_nom(self, obj):
        return obj.fournisseur.nom if obj.fournisseur_id else None

    def get_statut_display(self, obj):
        return obj.get_statut_display()

    def to_representation(self, obj):
        return {
            'id': obj.id,
            'sous_traitant': obj.fournisseur_id,
            'sous_traitant_nom': self.get_sous_traitant_nom(obj),
            'numero': obj.ref_fournisseur,
            'reference': obj.reference,
            'montant_ht': obj.montant_ht,
            'montant_tva': obj.montant_tva,
            'montant_ttc': obj.montant_ttc,
            'date_facture': obj.date_facture,
            'date_echeance': obj.date_echeance,
            'statut': obj.statut,
            'statut_display': obj.get_statut_display(),
            'total_paye': obj.total_paye,
            'reste_a_payer': obj.solde_du,
            'note': obj.note,
            'date_creation': obj.date_creation,
        }

    def validate_montant_ttc(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant TTC ne peut pas être négatif.')
        return value


class _PaiementSousTraitantSerializer(serializers.Serializer):
    """DC34 — vue à plat d'un règlement sous-traitant AU-DESSUS d'un
    ``stock.PaiementFournisseur``."""
    id = serializers.IntegerField(read_only=True)
    facture = serializers.IntegerField()
    montant = serializers.DecimalField(max_digits=14, decimal_places=2)
    date_paiement = serializers.DateField(required=False, allow_null=True)
    mode = serializers.CharField(required=False, default='virement')
    note = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    date_creation = serializers.DateTimeField(read_only=True)

    def to_representation(self, obj):
        return {
            'id': obj.id,
            'facture': obj.facture_id,
            'montant': obj.montant,
            'date_paiement': obj.date_paiement,
            'mode': obj.mode,
            'note': obj.note,
            'date_creation': obj.date_creation,
        }

    def validate_montant(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                'Le montant du paiement doit être strictement positif.')
        return value


class FactureSousTraitantViewSet(viewsets.ViewSet):
    """DC34 — factures entrantes sous-traitant via la chaîne AP standard
    (stock.FactureFournisseur, fournisseur type=service). Lecture & écriture
    responsable/admin. Société + `created_by` posés serveur ; `sous_traitant`
    validé tenant + type service. Filtrable par `sous_traitant`, `statut`.
    Action `annuler` = suppression d'une facture non réglée."""
    permission_classes = [IsResponsableOrAdmin]
    serializer_class = _FactureSousTraitantSerializer

    def _company(self):
        return self.request.user.company

    def _resolve_sous_traitant(self, st_id):
        st = stock_selectors.get_sous_traitant(self._company(), st_id)
        if st is None:
            raise ValidationError(
                {'sous_traitant': 'Sous-traitant inconnu pour cette société.'})
        return st

    def list(self, request):
        params = request.query_params
        qs = list(stock_selectors.factures_sous_traitant_qs(
            self._company(),
            fournisseur_id=params.get('sous_traitant') or None,
            statut=params.get('statut') or None))
        data = _FactureSousTraitantSerializer(qs, many=True).data
        return Response({'count': len(data), 'next': None, 'previous': None,
                         'results': data})

    def retrieve(self, request, pk=None):
        facture = stock_selectors.facture_fournisseur_scoped(
            self._company(), pk)
        if facture is None or facture.fournisseur.type != 'service':
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_FactureSousTraitantSerializer(facture).data)

    def create(self, request):
        serializer = _FactureSousTraitantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        st = self._resolve_sous_traitant(vd['sous_traitant'])
        facture = stock_services.create_facture_sous_traitant(
            company=self._company(), user=request.user, fournisseur=st,
            ref_fournisseur=vd.get('numero'),
            date_facture=vd.get('date_facture'),
            date_echeance=vd.get('date_echeance'),
            montant_ht=vd.get('montant_ht') or 0,
            montant_tva=vd.get('montant_tva') or 0,
            montant_ttc=vd.get('montant_ttc') or 0,
            note=vd.get('note'))
        return Response(_FactureSousTraitantSerializer(facture).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """DC34 — annule (supprime) une facture sous-traitant NON réglée. Une
        facture déjà réglée ne peut pas être annulée."""
        facture = stock_selectors.facture_fournisseur_scoped(
            self._company(), pk)
        if facture is None or facture.fournisseur.type != 'service':
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if facture.total_paye > 0:
            return Response(
                {'detail': "Une facture déjà réglée ne peut pas être annulée."},
                status=status.HTTP_400_BAD_REQUEST)
        facture.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaiementSousTraitantViewSet(viewsets.ViewSet):
    """DC34 — règlements sous-traitant via la chaîne AP standard
    (stock.PaiementFournisseur). Lecture & écriture responsable/admin. Société +
    `created_by` posés serveur ; la facture ciblée est validée tenant + service.
    Le statut de la facture est rafraîchi à chaque création/suppression.
    Filtrable par `facture`."""
    permission_classes = [IsResponsableOrAdmin]
    serializer_class = _PaiementSousTraitantSerializer

    def _company(self):
        return self.request.user.company

    def list(self, request):
        qs = list(stock_selectors.paiements_sous_traitant_qs(
            self._company(),
            facture_id=request.query_params.get('facture') or None))
        data = _PaiementSousTraitantSerializer(qs, many=True).data
        return Response({'count': len(data), 'next': None, 'previous': None,
                         'results': data})

    def retrieve(self, request, pk=None):
        paiement = stock_selectors.paiement_fournisseur_scoped(
            self._company(), pk)
        if paiement is None or paiement.facture.fournisseur.type != 'service':
            return Response({'detail': 'Règlement introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_PaiementSousTraitantSerializer(paiement).data)

    def create(self, request):
        serializer = _PaiementSousTraitantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        facture = stock_selectors.facture_fournisseur_scoped(
            self._company(), vd['facture'])
        if facture is None or facture.fournisseur.type != 'service':
            raise ValidationError(
                {'facture': 'Facture inconnue pour cette société.'})
        try:
            paiement = stock_services.add_paiement_sous_traitant(
                company=self._company(), user=request.user, facture=facture,
                montant=vd['montant'], date_paiement=vd.get('date_paiement'),
                mode=vd.get('mode', 'virement'), note=vd.get('note'))
        except ValueError as exc:
            raise ValidationError({'montant': str(exc)})
        return Response(_PaiementSousTraitantSerializer(paiement).data,
                        status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        paiement = stock_selectors.paiement_fournisseur_scoped(
            self._company(), pk)
        if paiement is None or paiement.facture.fournisseur.type != 'service':
            return Response({'detail': 'Règlement introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        stock_services.delete_paiement_sous_traitant(paiement)
        return Response(status=status.HTTP_204_NO_CONTENT)
