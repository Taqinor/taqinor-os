from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AvoirSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


def _reserver_stock_bc_actif(company):
    """YDOCF7 — état du toggle société `reserver_stock_bc` (défaut OFF).

    Lecture robuste : société absente/config absente ⇒ False (comportement
    actuel intact), jamais d'exception."""
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        return bool(CompanyProfile.get(company=company).reserver_stock_bc)
    except Exception:  # pragma: no cover - défensif
        return False

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class BonCommandeViewSet(viewsets.ModelViewSet):
    queryset = BonCommande.objects.select_related('client', 'devis').all()
    serializer_class = BonCommandeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'client__nom', 'client__email']
    ordering_fields = [
        'date_creation', 'date_livraison_prevue', 'statut'
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'confirmer', 'marquer_livre', 'annuler', 'creer_facture'
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        # ERR13 — client/devis du corps doivent appartenir à la société (refuse
        # de lier un BC au client/devis d'un autre tenant).
        if company is not None:
            client = serializer.validated_data.get('client')
            devis = serializer.validated_data.get('devis')
            if client is not None and client.company_id != company.id:
                raise ValidationError({'client': 'Client inconnu.'})
            if devis is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
        create_numbered(
            BonCommande, company, 'bon_commande',
            lambda ref: serializer.save(reference=ref, company=company),
        )

    @action(detail=True, methods=['post'], url_path='confirmer',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.EN_ATTENTE:
            return Response(
                {'detail': 'Seul un BC en attente peut être confirmé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommande.Statut.CONFIRME
        bc.save()
        # YDOCF7 — toggle société (défaut OFF = comportement actuel intact) :
        # réserve le stock des lignes du BC (StockReservation N14, via
        # installations.services — jamais d'import de son modèle ici).
        if _reserver_stock_bc_actif(bc.company):
            from apps.installations.services import reserver_stock_depuis_bc
            reserver_stock_depuis_bc(bc)
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='marquer-livre',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_livre(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.CONFIRME:
            return Response(
                {'detail': (
                    'Le BC doit être confirmé avant d\'être livré.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # FG51 — capture optionnelle de la preuve de livraison (PV/signature).
        # Le signataire, une note et une pièce jointe (bon signé) peuvent être
        # joints à la livraison. Tout est optionnel : un BC peut être livré sans
        # preuve (la facturation n'est jamais bloquée), mais la preuve lève
        # l'avertissement doux au moment de facturer.
        from django.utils import timezone as _tz
        signataire = (request.data.get('signataire') or '').strip()
        note_pv = (request.data.get('note_pv') or '').strip()
        upload = request.FILES.get('pv') or request.FILES.get('file')
        pv = {}
        if signataire:
            pv['signataire'] = signataire[:150]
        if note_pv:
            pv['note'] = note_pv[:1000]
        if upload is not None:
            from apps.records.storage import store_attachment
            meta, err = store_attachment(upload)
            if err is not None:
                return Response(
                    {'detail': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pv['file_key'] = meta['file_key']
            pv['filename'] = meta['filename']
        if pv:
            pv['signed_at'] = _tz.now().isoformat()
        from decimal import Decimal, ROUND_HALF_UP
        # YDOCF7 — toggle ON : la réservation créée à `confirmer` est SOLDÉE
        # (consommée) ici au lieu d'un second décrément direct — jamais les
        # deux (double décompte). Toggle OFF : chemin historique inchangé.
        toggle_bc_stock = _reserver_stock_bc_actif(bc.company)
        with transaction.atomic():
            if bc.devis and not toggle_bc_stock:
                for ligne in bc.devis.lignes.select_related('produit'):
                    produit = ligne.produit
                    produit.refresh_from_db()
                    # ERR15 — ne PAS tronquer la quantité décimale (int() perdait
                    # la partie fractionnaire : 3,5 → 3, dérive silencieuse du
                    # stock sur les lignes au mètre/câble). Le ledger de stock
                    # est en entiers (IntegerField) : on arrondit au plus proche
                    # (HALF_UP) au lieu de tronquer, donc 3,5 → 4.
                    qte = int(Decimal(ligne.quantite).quantize(
                        Decimal('1'), rounding=ROUND_HALF_UP))
                    qte_avant = produit.quantite_stock
                    qte_apres = qte_avant - qte
                    if qte_apres < 0:
                        return Response(
                            {'detail': (
                                f'Stock insuffisant pour '
                                f'« {produit.nom} » '
                                f'(disponible : {qte_avant}, '
                                f'requis : {qte}).'
                            )},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    record_stock_movement(
                        company=bc.company,
                        produit=produit,
                        type_mouvement=mouvement_type_sortie(),
                        quantite=qte,
                        quantite_avant=qte_avant,
                        quantite_apres=qte_apres,
                        reference=bc.reference,
                        note=f'Livraison BC {bc.reference}',
                        created_by=request.user,
                    )
            bc.statut = BonCommande.Statut.LIVRE
            from django.utils import timezone as _tz2
            bc.date_livraison_reelle = _tz2.now().date()
            if pv:
                bc.pv_livraison = pv
            bc.save()
        if toggle_bc_stock:
            from apps.installations.services import consommer_reservation_bc
            consommer_reservation_bc(bc, request.user)
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommande.Statut.LIVRE:
            return Response(
                {'detail': 'Un BC livré ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommande.Statut.ANNULE
        bc.save()
        # YDOCF7 — toggle ON : libère la réservation posée à `confirmer`
        # (no-op si le BC n'avait pas encore été confirmé/réservé).
        if _reserver_stock_bc_actif(bc.company):
            from apps.installations.services import liberer_reservation_bc
            liberer_reservation_bc(bc)
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='creer-facture',
            permission_classes=[IsResponsableOrAdmin])
    def creer_facture(self, request, pk=None):
        bc = self.get_object()
        if bc.statut not in [
            BonCommande.Statut.CONFIRME, BonCommande.Statut.LIVRE
        ]:
            return Response(
                {'detail': 'Le BC doit être confirmé ou livré.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Facture.objects.filter(bon_commande=bc).exists():
            return Response(
                {'detail': 'Une facture existe déjà pour ce BC.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = request.user.company

        def _create_facture(ref):
            facture = Facture.objects.create(
                reference=ref,
                bon_commande=bc,
                client=bc.client,
                statut=Facture.Statut.BROUILLON,
                created_by=request.user,
                company=company,
            )
            if bc.devis:
                # ERR16 — n'inclure QUE les lignes de l'option retenue à
                # l'acceptation (« Sans batterie » / « Avec batterie »), comme
                # l'échéancier. Sans vraie deuxième option (option unique,
                # pompage, liste libre), option_lines renvoie TOUTES les lignes
                # → comportement historique strictement inchangé.
                from ..utils.options import option_lines
                for ligne in option_lines(bc.devis):
                    LigneFacture.objects.create(
                        facture=facture,
                        produit=ligne.produit,
                        designation=ligne.designation,
                        quantite=ligne.quantite,
                        prix_unitaire=ligne.prix_unitaire,
                        remise=ligne.remise,
                        # Reporte le taux TVA de la ligne de devis (10/20),
                        # pour que la facture reproduise fidèlement la TVA.
                        taux_tva=ligne.taux_tva,
                    )
            return facture

        # create_with_reference runs _create_facture inside a transaction, so
        # the facture and its copied lines stay atomic like before.
        facture = create_numbered(
            Facture, company, 'facture', _create_facture)
        data = FactureSerializer(facture).data
        # FG51 — avertissement DOUX (jamais bloquant) : on facture la livraison
        # de matériel sans preuve de livraison (PV/signature). Le facturier voit
        # le message mais la facture est bien créée (201).
        if not bc.has_proof_of_delivery:
            data['warnings'] = [
                'Aucune preuve de livraison (PV / signature) n\'est attachée '
                'à ce bon de commande. Vous facturez sans bon de livraison '
                'signé.'
            ]
        return Response(
            data,
            status=status.HTTP_201_CREATED,
        )
