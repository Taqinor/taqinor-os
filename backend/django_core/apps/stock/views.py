from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import ProtectedError, Count, Min, Max
from django.http import HttpResponse
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from apps.imports.exports import XlsxExportMixin
from .models import (
    Produit, Categorie, Fournisseur, MouvementStock, ProduitAuditLog, Marque,
    BonCommandeFournisseur,
)
from .serializers import (
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
)
from authentication.permissions import (
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)
from apps.ventes.utils.references import create_with_reference

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class ProduitViewSet(XlsxExportMixin, TenantMixin, viewsets.ModelViewSet):
    queryset = Produit.objects.select_related(
        'categorie', 'fournisseur'
    ).all()
    serializer_class = ProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description', 'categorie__nom']
    ordering_fields = [
        'nom', 'quantite_stock', 'prix_vente', 'date_creation'
    ]
    ordering = ['nom']

    # Export .xlsx au niveau liste (respecte recherche/tri/filtres courants).
    # JAMAIS de prix_achat / marge. Mêmes colonnes que l'export « en masse ».
    export_filename = 'catalogue.xlsx'
    export_sheet_title = 'Catalogue'
    export_columns = [
        ('sku', 'SKU'), ('nom', 'Nom'), ('marque', 'Marque'),
        ('categorie', 'Catégorie'), ('prix_vente', 'Prix vente HT'),
        ('tva', 'TVA %'), ('quantite_stock', 'Quantité'),
        ('seuil_alerte', 'Seuil alerte'), ('garantie_mois', 'Garantie (mois)'),
        ('garantie_production_mois', 'Garantie production (mois)'),
    ]

    def get_export_row(self, obj):
        return {
            'sku': obj.sku or '', 'nom': obj.nom, 'marque': obj.marque or '',
            'categorie': obj.categorie.nom if obj.categorie else '',
            'prix_vente': float(obj.prix_vente),
            'tva': float(obj.tva) if obj.tva is not None else '',
            'quantite_stock': obj.quantite_stock,
            'seuil_alerte': obj.seuil_alerte,
            'garantie_mois': (obj.garantie_mois
                              if obj.garantie_mois is not None else ''),
            'garantie_production_mois': (obj.garantie_production_mois
                                         if obj.garantie_production_mois
                                         is not None else ''),
        }

    def get_permissions(self):
        # Écritures Stock : permission ERP granulaire (rôles fins type
        # « Commerciale » = lecture seule) avec comportement historique
        # pour les comptes hérités sans rôle fin.
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'create':
            return [HasPermissionOrLegacy('stock_creer')()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'bulk':
            # Édition groupée (prix de vente, garantie, catégorie, marque,
            # export) = même droit que la modification unitaire.
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action in ('destroy', 'force_delete'):
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('show_archived') == 'true':
            return qs.annotate(
                nb_mouvements=Count('mouvements'),
                premiere_date_mouvement=Min('mouvements__date'),
                derniere_date_mouvement=Max('mouvements__date'),
            )
        if self.action in ('force_delete', 'unarchive'):
            return qs  # archived products must be visible for these actions
        return qs.filter(is_archived=False)

    def destroy(self, request, *args, **kwargs):
        produit = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            nb = produit.mouvements.count()
            produit.is_archived = True
            produit.save(update_fields=['is_archived'])
            return Response(
                {
                    'archived': True,
                    'detail': (
                        f'Ce produit a été archivé car il possède {nb} '
                        f'mouvement(s) de stock. L\'historique est conservé.'
                    ),
                    'nb_mouvements': nb,
                },
                status=status.HTTP_200_OK,
            )

    @action(detail=True, methods=['patch'], url_path='unarchive')
    def unarchive(self, request, *args, **kwargs):
        produit = self.get_object()
        if not produit.is_archived:
            return Response(
                {'detail': 'Ce produit n\'est pas archivé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        produit.is_archived = False
        produit.save(update_fields=['is_archived'])
        serializer = self.get_serializer(produit)
        return Response(serializer.data)

    # ── Édition groupée du catalogue ───────────────────────────────────────
    # Actions supportées (toutes confinées à request.user.company ; les ids
    # hors entreprise sont silencieusement ignorés) :
    #   - change_prix : variation du PRIX DE VENTE uniquement, en % ou montant
    #                   fixe (jamais prix_achat, jamais marge).
    #   - set_garantie : garantie_mois / garantie_production_mois.
    #   - set_categorie / set_marque : ré-affectation catégorie et/ou marque.
    #   - export_xlsx : export de la sélection en .xlsx.
    BULK_ACTIONS = (
        'change_prix', 'set_garantie', 'set_categorie', 'set_marque',
        'export_xlsx',
    )

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk(self, request, *args, **kwargs):
        action_name = request.data.get('action')
        ids = request.data.get('ids') or []
        params = request.data.get('params') or {}

        if action_name not in self.BULK_ACTIONS:
            return Response(
                {'detail': f"Action inconnue : {action_name!r}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'Aucun produit sélectionné.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Scope tenant : on ne touche QUE les produits de l'entreprise.
        # get_queryset() filtre déjà par company (TenantMixin) ; les ids
        # étrangers tombent d'eux-mêmes.
        produits = list(self.get_queryset().filter(id__in=ids))

        if action_name == 'export_xlsx':
            return self._bulk_export_xlsx(produits)

        if not produits:
            return Response(
                {'detail': 'Aucun produit valide dans votre entreprise.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handlers = {
            'change_prix': self._bulk_change_prix,
            'set_garantie': self._bulk_set_garantie,
            'set_categorie': self._bulk_set_categorie,
            'set_marque': self._bulk_set_marque,
        }
        try:
            with transaction.atomic():
                updated = handlers[action_name](request, produits, params)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'updated': updated, 'detail': f'{updated} produit(s) mis à jour.'})

    def _log(self, request, produit, action, champ=None, old=None, new=None, note=None):
        ProduitAuditLog.objects.create(
            company=produit.company,
            produit=produit,
            action=action,
            champ=champ,
            ancienne_valeur=None if old is None else str(old),
            nouvelle_valeur=None if new is None else str(new),
            note=note,
            created_by=request.user if request.user.is_authenticated else None,
        )

    def _bulk_change_prix(self, request, produits, params):
        mode = params.get('mode')   # 'percent' | 'fixed'
        raw = params.get('valeur')
        if mode not in ('percent', 'fixed'):
            raise ValueError("mode doit valoir 'percent' ou 'fixed'.")
        try:
            valeur = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError('valeur invalide.')

        updated = 0
        for p in produits:
            old = p.prix_vente
            if mode == 'percent':
                new = (old * (Decimal('1') + valeur / Decimal('100')))
            else:
                new = old + valeur
            new = new.quantize(Decimal('0.01'))
            if new < 0:
                new = Decimal('0.00')
            if new == old:
                continue
            # prix_achat n'est JAMAIS touché ici (vente uniquement).
            p.prix_vente = new
            p.save(update_fields=['prix_vente'])
            self._log(request, p, 'change_prix', champ='prix_vente', old=old, new=new,
                      note=f'{mode} {valeur}')
            updated += 1
        return updated

    def _bulk_set_garantie(self, request, produits, params):
        fields = {}
        for key in ('garantie_mois', 'garantie_production_mois'):
            if key in params:
                val = params[key]
                if val in ('', None):
                    fields[key] = None
                else:
                    try:
                        ival = int(val)
                    except (TypeError, ValueError):
                        raise ValueError(f'{key} doit être un entier.')
                    if ival < 0:
                        raise ValueError(f'{key} ne peut pas être négatif.')
                    fields[key] = ival
        if not fields:
            raise ValueError('Aucune garantie fournie.')
        updated = 0
        for p in produits:
            changed = []
            for key, val in fields.items():
                if getattr(p, key) != val:
                    old = getattr(p, key)
                    setattr(p, key, val)
                    changed.append((key, old, val))
            if changed:
                p.save(update_fields=[c[0] for c in changed])
                for key, old, val in changed:
                    self._log(request, p, 'set_garantie', champ=key, old=old, new=val)
                updated += 1
        return updated

    def _bulk_set_categorie(self, request, produits, params):
        cat_id = params.get('categorie_id')
        if cat_id in ('', None):
            categorie = None
        else:
            categorie = Categorie.objects.filter(
                id=cat_id, company=request.user.company).first()
            if categorie is None:
                raise ValueError('Catégorie introuvable dans votre entreprise.')
        updated = 0
        for p in produits:
            if p.categorie_id == (categorie.id if categorie else None):
                continue
            old = p.categorie.nom if p.categorie else None
            p.categorie = categorie
            p.save(update_fields=['categorie'])
            self._log(request, p, 'set_categorie', champ='categorie', old=old,
                      new=categorie.nom if categorie else None)
            updated += 1
        return updated

    def _bulk_set_marque(self, request, produits, params):
        if 'marque' not in params:
            raise ValueError('marque manquante.')
        marque = (params.get('marque') or '').strip() or None
        updated = 0
        for p in produits:
            if (p.marque or None) == marque:
                continue
            old = p.marque
            p.marque = marque
            p.save(update_fields=['marque'])
            self._log(request, p, 'set_marque', champ='marque', old=old, new=marque)
            updated += 1
        return updated

    def _bulk_export_xlsx(self, produits):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Catalogue'
        # JAMAIS de prix_achat / marge dans l'export client.
        headers = [
            'SKU', 'Nom', 'Marque', 'Catégorie', 'Prix vente HT', 'TVA %',
            'Quantité', 'Seuil alerte', 'Garantie (mois)',
            'Garantie production (mois)',
        ]
        ws.append(headers)
        for p in produits:
            ws.append([
                p.sku or '',
                p.nom,
                p.marque or '',
                p.categorie.nom if p.categorie else '',
                float(p.prix_vente),
                float(p.tva) if p.tva is not None else '',
                p.quantite_stock,
                p.seuil_alerte,
                p.garantie_mois if p.garantie_mois is not None else '',
                p.garantie_production_mois if p.garantie_production_mois is not None else '',
            ])
        from io import BytesIO
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = HttpResponse(
            buf.getvalue(),
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'
            ),
        )
        resp['Content-Disposition'] = 'attachment; filename="catalogue.xlsx"'
        return resp

    @action(detail=True, methods=['delete'], url_path='force-delete')
    def force_delete(self, request, *args, **kwargs):
        produit = self.get_object()
        if not produit.is_archived:
            return Response(
                {
                    'detail': (
                        'Seuls les produits archivés peuvent être '
                        'supprimés définitivement.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        nb = produit.mouvements.count()
        produit.mouvements.all().delete()
        produit.delete()
        return Response(
            {
                'detail': (
                    f'Produit et {nb} mouvement(s) supprimé(s) définitivement.'
                )
            },
            status=status.HTTP_200_OK,
        )


class CategorieViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class FournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email', 'contact_personne']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class MarqueViewSet(TenantMixin, viewsets.ModelViewSet):
    """Marques produit gérées — scopées société. SELECT avec création à la
    volée côté formulaire produit. Lecture tout rôle, écriture = droit stock."""
    queryset = Marque.objects.all()
    serializer_class = MarqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class MouvementStockViewSet(viewsets.ModelViewSet):
    queryset = MouvementStock.objects.select_related(
        'produit', 'created_by'
    ).all()
    serializer_class = MouvementStockSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'reference', 'note']
    ordering_fields = ['date', 'type_mouvement', 'quantite']
    ordering = ['-date']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'create':
            return [HasPermissionOrLegacy('stock_mouvement')()]
        else:
            return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            # Direct company filter + produit__company belt-and-braces guard
            # against cross-tenant produit references slipping in.
            return qs.filter(company=user.company, produit__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        produit = serializer.validated_data['produit']
        user = self.request.user
        # Reject cross-tenant produit references before touching stock.
        if user.company_id and produit.company_id != user.company_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Produit hors de votre entreprise.")
        produit.refresh_from_db()
        qte = serializer.validated_data['quantite']
        type_mv = serializer.validated_data['type_mouvement']
        qte_avant = produit.quantite_stock
        if type_mv == MouvementStock.TypeMouvement.ENTREE:
            qte_apres = qte_avant + qte
        elif type_mv == MouvementStock.TypeMouvement.SORTIE:
            qte_apres = qte_avant - qte
        else:
            qte_apres = qte
        serializer.save(
            created_by=user,
            company=produit.company,
            quantite_avant=qte_avant,
            quantite_apres=qte_apres,
        )
        produit.quantite_stock = qte_apres
        produit.save(update_fields=['quantite_stock'])


# ── Bon de commande FOURNISSEUR (approvisionnement / achat — N11/N12) ────────

class BonCommandeFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """Bons de commande fournisseur (achats). Distinct du BC CLIENT de ventes.

    - référence numérotée sans trou (préfixe BCF) via references.py ;
    - réceptions partielles : l'action `recevoir` incrémente le stock via
      MouvementStock (ENTREE) pour les quantités reçues uniquement ;
    - les prix d'ACHAT restent internes (jamais sur un document client).
    """
    queryset = BonCommandeFournisseur.objects.select_related(
        'fournisseur', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = BonCommandeFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'note']
    ordering_fields = ['date_creation', 'date_commande', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'envoyer', 'recevoir', 'annuler', 'generer_pdf',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(
            BonCommandeFournisseur, 'BCF', company, _save)

    @action(detail=True, methods=['post'], url_path='envoyer')
    def envoyer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommandeFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un BCF en brouillon peut être envoyé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ENVOYE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommandeFournisseur.Statut.RECU:
            return Response(
                {'detail': 'Un BCF entièrement reçu ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ANNULE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='recevoir')
    def recevoir(self, request, pk=None):
        """Réception (totale ou partielle) — incrémente le stock par ENTREE.

        Corps : {"receptions": [{"ligne": <id>, "quantite": <int>}, ...]}.
        Idempotent/sûr : on ne reçoit jamais plus que le reste dû ; le stock
        n'augmente que des quantités effectivement reçues.
        """
        bc = self.get_object()
        if bc.statut in (
            BonCommandeFournisseur.Statut.BROUILLON,
            BonCommandeFournisseur.Statut.ANNULE,
            BonCommandeFournisseur.Statut.RECU,
        ):
            return Response(
                {'detail': (
                    'Seul un BCF envoyé (non encore entièrement reçu) '
                    'peut recevoir des quantités.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receptions = request.data.get('receptions') or []
        if not isinstance(receptions, list) or not receptions:
            return Response(
                {'detail': 'Aucune réception fournie.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Index par id de ligne (scopé à ce BC uniquement).
        lignes = {ligne.id: ligne for ligne in bc.lignes.select_related(
            'produit')}
        plan = []
        for rec in receptions:
            try:
                ligne_id = int(rec.get('ligne'))
                qte = int(rec.get('quantite'))
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Réception invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ligne = lignes.get(ligne_id)
            if ligne is None:
                return Response(
                    {'detail': f'Ligne {ligne_id} introuvable sur ce BCF.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if qte <= 0:
                continue
            # Plafonnement au reste dû — jamais plus que commandé (idempotence).
            qte = min(qte, ligne.quantite_restante)
            if qte > 0:
                plan.append((ligne, qte))

        if not plan:
            return Response(
                {'detail': 'Rien à recevoir (quantités déjà reçues).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for ligne, qte in plan:
                produit = ligne.produit
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + qte
                MouvementStock.objects.create(
                    company=bc.company,
                    produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                    quantite=qte,
                    quantite_avant=qte_avant,
                    quantite_apres=qte_apres,
                    reference=bc.reference,
                    note=f'Réception BCF {bc.reference}',
                    created_by=request.user,
                )
                produit.quantite_stock = qte_apres
                produit.save(update_fields=['quantite_stock'])
                ligne.quantite_recue += qte
                ligne.save(update_fields=['quantite_recue'])
            bc.refresh_from_db()
            if bc.est_entierement_recu:
                bc.statut = BonCommandeFournisseur.Statut.RECU
                bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def generer_pdf(self, request, pk=None):
        """PDF fournisseur (INTERNE — montre les prix d'achat). Jamais un
        document client."""
        from .utils.pdf_fournisseur import generate_bcf_pdf
        bc = self.get_object()
        pdf_bytes = generate_bcf_pdf(bc)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{bc.reference}.pdf"')
        return response
