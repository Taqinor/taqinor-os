from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max, Prefetch  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur, RegleCodeBarres,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
    HasPermissionAndRole,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.

# QG4 — la CRÉATION de produits est restreinte partout (REST, import de
# données, OCR — qui réutilise ce create) aux rôles Directeur et Commercial
# responsable (décision Reda). Seule l'action `create` est durcie : lecture,
# modification et suppression gardent leurs règles historiques.
PRODUIT_CREATE_PERMISSION = HasPermissionAndRole(
    'stock_creer', 'Directeur', 'Commercial responsable')


class ProduitViewSet(CompanyScopedModelViewSet):
    # YOPSB13 — le FournisseurSerializer imbriqué (ProduitSerializer.fournisseur)
    # lit contacts.all() + nb_produits/nb_bons_commande (repli .count()) PAR
    # ligne : N+1. On précharge le fournisseur avec les mêmes annotations que
    # FournisseurViewSet + ses contacts → nombre de requêtes fixe quel que soit
    # le nombre de produits.
    queryset = Produit.objects.select_related('categorie').prefetch_related(
        Prefetch(
            'fournisseur',
            queryset=Fournisseur.objects.annotate(
                nb_produits_annot=Count('produits', distinct=True),
                nb_bons_commande_annot=Count('bons_commande', distinct=True),
            ).prefetch_related('contacts'),
        ),
    ).all()
    serializer_class = ProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description', 'categorie__nom']
    ordering_fields = [
        'nom', 'quantite_stock', 'prix_vente', 'date_creation'
    ]
    ordering = ['nom']

    def get_permissions(self):
        # Écritures Stock : permission ERP granulaire (rôles fins type
        # « Commerciale » = lecture seule) avec comportement historique
        # pour les comptes hérités sans rôle fin.
        if self.action in READ_ACTIONS + [
                'export_xlsx', 'resolve', 'previsionnel', 'tracer',
                'etiquettes_showroom']:
            # XSTK3/XSTK4 — `resolve` (scan code-barres/GS1) est LECTURE
            # SEULE, accessible à tout rôle authentifié — même garde que
            # `@action(permission_classes=[IsAnyRole])` sur l'action
            # (`get_permissions` prime sur le `permission_classes` de
            # l'@action, d'où ce cas explicite — sinon repli IsAdminRole).
            # ZSTK3 — `previsionnel` est LECTURE SEULE, même garde.
            # XSTK7 — `tracer` (rapport de traçabilité) est LECTURE SEULE,
            # même garde.
            # XPOS17 — `etiquettes-showroom` (impression) est LECTURE SEULE,
            # même garde que l'action `etiquettes` N20.
            return [IsAnyRole()]
        elif self.action in ('create', 'dupliquer'):
            # QG4 — création réservée à Directeur + Commercial responsable.
            # QP2 — le clone (`dupliquer`) EST une création : même garde. Ce
            # `get_permissions` prime sur le `permission_classes` de l'action,
            # donc la garde DOIT être posée ici (sinon repli IsAdminRole).
            return [PRODUIT_CREATE_PERMISSION()]
        elif self.action in WRITE_ACTIONS + ['bulk', 'rebuter', 'decoupes']:
            # XSTK16 — la découpe/reconditionnement modifie le stock, même
            # garde que les autres écritures Stock (`get_permissions` prime
            # sur le `permission_classes` de l'@action, d'où ce cas explicite
            # — sinon repli IsAdminRole).
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action in ('destroy', 'force_delete'):
            return [IsAdminRole()]
        elif self.action in (
                'analyse_achats', 'analyse_achats_export_xlsx',
                'analyse_achats_pdf'):
            # XPUR24/ZPUR9 — tableau de bord + rapport imprimable achats :
            # Admin/Responsable uniquement (get_permissions prime sur le
            # permission_classes de l'@action, d'où ce cas explicite —
            # sinon repli IsAdminRole).
            return [IsResponsableOrAdmin()]
        # XSTK10 — `rapport_pertes` reste admin-only (valeur d'achat
        # interne, jamais client-facing) via le repli ci-dessous.
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

    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[HasPermissionOrLegacy('stock_modifier')])
    def bulk(self, request):
        """Édition en masse d'une sélection de produits (prix %/fixe, garantie,
        catégorie, marque). Le prix d'achat n'est jamais modifié."""
        from ..services import BULK_ACTIONS, apply_product_bulk
        op = request.data.get('action')
        ids = request.data.get('ids') or []
        if op not in BULK_ACTIONS:
            return Response({'detail': 'Action en masse inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = apply_product_bulk(
                company=request.user.company, user=request.user,
                ids=ids, op=op, params=request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='inventaire',
            permission_classes=[IsAdminRole])
    def inventaire(self, request):
        """N16 — inventaire physique : pose un comptage par produit et publie
        l'écart en ajustement de stock (audité). Réservé admin.

        Corps : {"motif": <str>, "lignes": [{"produit": <id>,
                 "quantite_comptee": <int>}]}.
        """
        from ..services import apply_inventory_count
        lignes = request.data.get('lignes') or []
        if not isinstance(lignes, list) or not lignes:
            return Response({'detail': 'Aucune ligne de comptage fournie.'},
                            status=status.HTTP_400_BAD_REQUEST)
        result = apply_inventory_count(
            company=request.user.company, user=request.user,
            motif=request.data.get('motif'), lignes=lignes)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """Exporte une sélection de produits en .xlsx (prix d'achat exclu)."""
        from ..services import export_products_xlsx
        ids = request.data.get('ids') or []
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)
        produits = (Produit.objects.filter(company=request.user.company, id__in=ids)
                    .select_related('categorie').order_by('nom'))
        return export_products_xlsx(produits)

    @action(detail=False, methods=['get'], url_path='valorisation',
            permission_classes=[IsAdminRole])
    def valorisation(self, request):
        """N18 — valorisation du stock par emplacement au coût moyen d'achat.
        INTERNE (admin) — les prix d'achat ne sont jamais client-facing."""
        from ..services import stock_valuation_by_location
        return Response(stock_valuation_by_location(request.user.company))

    @action(detail=False, methods=['get'], url_path='valorisation-xlsx',
            permission_classes=[IsAdminRole])
    def valorisation_xlsx(self, request):
        """Export Excel de la valorisation du stock (admin/INTERNE) —
        les prix d'achat/coûts ne sont jamais client-facing."""
        from ..services import export_valorisation_xlsx
        return export_valorisation_xlsx(request.user.company)

    @action(detail=False, methods=['get'], url_path='valorisation-a-date',
            permission_classes=[IsAdminRole])
    def valorisation_date(self, request):
        """XSTK13 — valorisation du stock reconstruite à une date passée
        (CGNC). Paramètre requis : ``date`` (YYYY-MM-DD). INTERNE (admin)."""
        from datetime import datetime
        from ..services import valorisation_a_date
        raw = request.query_params.get('date')
        if not raw:
            return Response({'detail': 'Paramètre "date" requis (YYYY-MM-DD).'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            date = datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu YYYY-MM-DD).'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(valorisation_a_date(request.user.company, date))

    @action(detail=False, methods=['post'], url_path='decoupes',
            permission_classes=[HasPermissionOrLegacy('stock_modifier')])
    def decoupes(self, request):
        """XSTK16 — découpe/reconditionnement : débite `produit_source` et
        crédite `produit_cible` (peut être le même SKU) en transférant la
        valeur au coût moyen. Corps : {"produit_source", "quantite_consommee",
        "produit_cible", "quantite_produite", "emplacement" (optionnel),
        "lot_source" (optionnel, id LotEntrepot)}."""
        from ..services import decouper_produit
        company = request.user.company
        source = Produit.objects.filter(
            company=company, id=request.data.get('produit_source')).first()
        cible = Produit.objects.filter(
            company=company, id=request.data.get('produit_cible')).first()
        if source is None or cible is None:
            return Response(
                {'detail': 'Produit source ou cible introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            quantite_consommee = int(request.data.get('quantite_consommee'))
            quantite_produite = int(request.data.get('quantite_produite'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Quantités invalides.'},
                status=status.HTTP_400_BAD_REQUEST)
        lot_source = None
        lot_source_id = request.data.get('lot_source')
        if lot_source_id:
            from ..models import LotEntrepot
            lot_source = LotEntrepot.objects.filter(
                company=company, id=lot_source_id).first()
            if lot_source is None:
                return Response(
                    {'detail': 'Lot source introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
        emplacement = None
        emplacement_id = request.data.get('emplacement')
        if emplacement_id:
            emplacement = EmplacementStock.objects.filter(
                company=company, id=emplacement_id).first()
        try:
            result = decouper_produit(
                company=company, produit_source=source,
                quantite_consommee=quantite_consommee, produit_cible=cible,
                quantite_produite=quantite_produite, user=request.user,
                emplacement=emplacement, lot_source=lot_source)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'reference': result['reference'],
            'valeur_transferee': str(result['valeur_transferee']),
            'cout_unitaire': str(result['cout_unitaire']),
            'produit_source_quantite_stock': result['produit_source'].quantite_stock,
            'produit_cible_quantite_stock': result['produit_cible'].quantite_stock,
            'numero_lot': result['numero_lot'],
        })

    @action(detail=True, methods=['get'], url_path='prix-fournisseurs',
            permission_classes=[IsAnyRole])
    def prix_fournisseurs(self, request, *args, **kwargs):
        """N17 — liste de prix multi-fournisseurs de ce produit (INTERNE),
        triée du moins cher au plus cher."""
        produit = self.get_object()
        qs = produit.prix_fournisseurs.select_related('fournisseur').order_by(
            'prix_achat')
        return Response(PrixFournisseurSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='emplacements',
            permission_classes=[IsAnyRole])
    def emplacements(self, request, *args, **kwargs):
        """N15 — ventilation du stock de ce produit par emplacement (le dépôt
        principal détient le reste = total − somme des autres)."""
        from ..services import stock_breakdown
        produit = self.get_object()
        return Response(stock_breakdown(produit))

    @action(detail=False, methods=['get'], url_path='etiquettes',
            permission_classes=[IsAnyRole])
    def etiquettes(self, request):
        """N20 — Étiquettes imprimables (QR/CODE128) pour une sélection de SKU.

        Encode un jeton stable `PRODUIT:<id>` + un texte LISIBLE (nom + SKU).
        Le jeton scanné est résolu par `resolve` (lecture seule). On n'imprime
        JAMAIS de prix d'achat / marge — uniquement nom + SKU + jeton.

        Paramètres :
          - ``ids`` : liste d'identifiants (répétée ou séparée par virgules) ;
          - ``symbology`` : ``qr`` (défaut) | ``code128`` ;
          - ``sortie`` : ``html`` (aperçu) | ``pdf`` (défaut). On utilise
            ``sortie`` et non ``format`` (réservé par DRF).
        """
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

        ids = request.query_params.getlist('ids')
        if len(ids) == 1 and ',' in ids[0]:
            ids = ids[0].split(',')
        ids = [i for i in (str(x).strip() for x in ids) if i.isdigit()]
        if not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)

        symbology = request.query_params.get('symbology', 'qr')
        if symbology not in ('qr', 'code128'):
            symbology = 'qr'

        produits = (Produit.objects
                    .filter(company=request.user.company, id__in=ids)
                    .order_by('nom'))
        items = [{
            'token': labels.produit_token(p.id),
            'titre': p.nom,
            'sous_titre': p.sku or '',
        } for p in produits]
        if not items:
            return Response({'detail': 'Aucun produit correspondant.'},
                            status=status.HTTP_404_NOT_FOUND)

        html = labels.render_labels_html(items, symbology=symbology)
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        pdf_bytes = _html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            'inline; filename="etiquettes-produits.pdf"')
        return response

    @action(detail=False, methods=['get'], url_path='etiquettes-showroom')
    def etiquettes_showroom(self, request):
        """XPOS17 — Étiquettes « showroom » : le QR encode l'URL de la fiche
        produit PUBLIQUE de l'e-catalogue tokenisé (FG214) — le client scanne
        en magasin et atterrit sur la fiche (prix TTC, garantie, dispo
        indicative, CTA devis/rappel). JAMAIS de prix d'achat/marge.

        Paramètres :
          - ``ids`` : produits (répétés ou séparés par virgules) ;
          - ``catalogue_token`` : jeton de l'e-catalogue de la société
            (validé actif/non expiré ET appartenant à la société — un jeton
            d'une autre société est refusé) ; seuls les produits EXPOSÉS par
            ce catalogue sont imprimés ;
          - ``sortie`` : ``html`` (aperçu) | ``pdf`` (défaut).
        """
        from django.conf import settings
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf
        from apps.compta.selectors import ecatalogue_public_par_token

        token = (request.query_params.get('catalogue_token') or '').strip()
        if not token:
            return Response(
                {'detail': "Le jeton de l'e-catalogue est requis "
                           '(catalogue_token).'},
                status=status.HTTP_400_BAD_REQUEST)
        cat = ecatalogue_public_par_token(token)
        if cat is None or cat.company_id != request.user.company_id:
            return Response(
                {'detail': 'E-catalogue introuvable pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)

        ids = request.query_params.getlist('ids')
        if len(ids) == 1 and ',' in ids[0]:
            ids = ids[0].split(',')
        ids = [int(i) for i in (str(x).strip() for x in ids) if i.isdigit()]
        if not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)
        exposes = set(cat.produit_ids or [])
        ids = [i for i in ids if i in exposes]

        produits = (Produit.objects
                    .filter(company=request.user.company, id__in=ids)
                    .order_by('nom'))
        base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
        if not base:
            base = request.build_absolute_uri('/')
        items = [{
            'token': labels.showroom_url(base, cat.token, p.id),
            'titre': p.nom,
            'sous_titre': 'Scannez pour la fiche & le prix',
        } for p in produits]
        if not items:
            return Response(
                {'detail': 'Aucun produit correspondant exposé par cet '
                           'e-catalogue.'},
                status=status.HTTP_404_NOT_FOUND)

        html = labels.render_labels_html(items, symbology='qr')
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        pdf_bytes = _html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            'inline; filename="etiquettes-showroom.pdf"')
        return response

    @action(detail=False, methods=['get'], url_path='a-reapprovisionner',
            permission_classes=[IsAnyRole])
    def a_reapprovisionner(self, request):
        """FG54 — Liste des produits dont le stock est <= seuil_alerte,
        avec fournisseur le moins cher et quantité suggérée. INTERNE."""
        from ..services import produits_a_reapprovisionner
        return Response(produits_a_reapprovisionner(request.user.company))

    @action(detail=False, methods=['post'], url_path='generer-bcf-reappro',
            permission_classes=[IsResponsableOrAdmin])
    def generer_bcf_reappro(self, request):
        """FG54 — Génère un BCF BROUILLON pour tous les produits sous seuil.
        Réutilise create_with_reference('BCF'). INTERNE."""
        from ..services import generer_bcf_reappro
        fournisseur_id = request.data.get('fournisseur_id')
        try:
            result = generer_bcf_reappro(
                company=request.user.company,
                user=request.user,
                fournisseur_id=fournisseur_id)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='rotation',
            permission_classes=[IsAdminRole])
    def rotation(self, request):
        """FG57 — Rapport de rotation / dead-stock (admin). Indique le dernier
        mouvement SORTIE, les jours sans mouvement, et le bucket de rotation."""
        from ..services import rotation_report
        try:
            jours = int(request.query_params.get('jours', 180))
        except (TypeError, ValueError):
            jours = 180
        return Response(rotation_report(request.user.company, jours=jours))

    @action(detail=True, methods=['get'], url_path='comparer-fournisseurs',
            permission_classes=[IsAdminRole])
    def comparer_fournisseurs(self, request, *args, **kwargs):
        """FG58 — Comparaison des prix multi-fournisseurs d'un produit (admin).
        Trié du moins cher au plus cher. INTERNE."""
        from ..services import comparer_fournisseurs
        produit = self.get_object()
        return Response(comparer_fournisseurs(request.user.company, produit))

    @action(detail=False, methods=['get'], url_path='expirant-bientot',
            permission_classes=[IsAdminRole])
    def expirant_bientot(self, request):
        """FG64 — Rapport des produits expirant bientôt (admin). Paramètre
        ?jours=90 (défaut 90 jours). INTERNE."""
        from ..services import produits_expirant_bientot
        try:
            jours = int(request.query_params.get('jours', 90))
        except (TypeError, ValueError):
            jours = 90
        return Response(produits_expirant_bientot(request.user.company, jours=jours))

    @action(detail=False, methods=['get'], url_path='previsions-reappro',
            permission_classes=[IsAdminRole])
    def previsions_reappro(self, request):
        """FG65 — Prévisions de réapprovisionnement basées sur la consommation
        historique (SORTIE) des `nb_mois` derniers mois. Admin-only. INTERNE."""
        from ..services import previsions_reappro
        try:
            nb_mois = int(request.query_params.get('nb_mois', 6))
        except (TypeError, ValueError):
            nb_mois = 6
        return Response(previsions_reappro(request.user.company, nb_mois=nb_mois))

    @action(detail=False, methods=['get'], url_path='analyse-achats',
            permission_classes=[IsResponsableOrAdmin])
    def analyse_achats(self, request):
        """XPUR24 — tableau de bord achats : dépenses par fournisseur/
        catégorie/mois, dérive de prix moyen par SKU, engagements ouverts,
        top produits achetés, temps de cycle DA→BCF→réception→facture.
        Admin/Responsable uniquement — JAMAIS client-facing. INTERNE."""
        from ..services import analyse_achats_dashboard
        try:
            nb_mois = int(request.query_params.get('nb_mois', 6))
        except (TypeError, ValueError):
            nb_mois = 6
        return Response(analyse_achats_dashboard(
            request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'),
            nb_mois=nb_mois))

    @action(detail=False, methods=['get'], url_path='analyse-achats/export-xlsx',
            permission_classes=[IsResponsableOrAdmin])
    def analyse_achats_export_xlsx(self, request):
        """XPUR24 — export xlsx du tableau de bord achats. Admin/Responsable
        uniquement — un non-autorisé reçoit 403."""
        from ..services import export_analyse_achats_xlsx
        try:
            nb_mois = int(request.query_params.get('nb_mois', 6))
        except (TypeError, ValueError):
            nb_mois = 6
        return export_analyse_achats_xlsx(
            request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'),
            nb_mois=nb_mois)

    @action(detail=False, methods=['get'], url_path='analyse-achats/pdf',
            permission_classes=[IsResponsableOrAdmin])
    def analyse_achats_pdf(self, request):
        """ZPUR9 — rapport imprimable « analyse d'achats » (PDF, au-delà du
        dashboard écran XPUR24) : dépenses par fournisseur/catégorie, top
        produits, engagements ouverts, identité société (ICE/IF/RC).
        Admin/Responsable uniquement — document INTERNE, jamais côté client.
        Réutilise `analyse_achats_dashboard` (jamais recalculé)."""
        from django.http import HttpResponse
        from ..utils.pdf_analyse_achats import generate_analyse_achats_pdf
        try:
            nb_mois = int(request.query_params.get('nb_mois', 6))
        except (TypeError, ValueError):
            nb_mois = 6
        pdf_bytes = generate_analyse_achats_pdf(
            request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'),
            nb_mois=nb_mois)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            'inline; filename="analyse-achats.pdf"')
        return response

    @action(detail=True, methods=['get'], url_path='previsionnel',
            permission_classes=[IsAnyRole])
    def previsionnel(self, request, pk=None):
        """ZSTK3 — rapport prévisionnel (Forecasted report) : disponible +
        entrées attendues (BCF ouverts) + sorties attendues (réservations
        chantier/assemblage) → solde projeté daté. INTERNE, lecture seule."""
        from ..services import forecast_produit
        produit = self.get_object()
        return Response(forecast_produit(request.user.company, produit))

    @action(detail=False, methods=['get'], url_path='tracer',
            permission_classes=[IsAnyRole])
    def tracer(self, request):
        """XSTK7 — rapport de traçabilité bout-en-bout (rappel fabricant) :
        `?serie=<numero>` ou `?lot=<numero>`. Remonte réception fournisseur
        → emplacement entrepôt → équipement installé/client en un appel.
        Numéro inconnu / hors société → 404. INTERNE, lecture seule."""
        from ..selectors import trace_serie

        numero_serie = (request.query_params.get('serie') or '').strip()
        numero_lot = (request.query_params.get('lot') or '').strip()
        if not numero_serie and not numero_lot:
            return Response(
                {'detail': 'Paramètre serie ou lot requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        result = trace_serie(
            request.user.company,
            numero_serie=numero_serie or None,
            numero_lot=numero_lot or None)
        if result is None:
            return Response(
                {'detail': 'Aucune traçabilité trouvée pour ce numéro.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(result)

    @action(detail=False, methods=['get'], url_path='resolve',
            permission_classes=[IsAnyRole])
    def resolve(self, request):
        """N20 — Résout un code scanné (`PRODUIT:<id>` / `SYSTEME:<id>`) vers
        l'enregistrement correspondant, STRICTEMENT scopé à la société.

        Lecture seule : ne modifie JAMAIS d'installation (import paresseux,
        aucune écriture). Renvoie ``{type, id, label, route}`` pour que le
        front navigue vers la bonne fiche, ou 404 si le code est inconnu /
        hors société."""
        from .. import labels

        code = (request.query_params.get('code') or '').strip()
        if not code:
            return Response(
                {'detail': 'Code illisible.'},
                status=status.HTTP_400_BAD_REQUEST)

        # ZSTK12 — la nomenclature de code-barres ACTIVE de la société (s'il
        # y en a une) est consultée AVANT tout parsing GS1/EAN en dur. Sans
        # nomenclature définie, ce bloc est un no-op total (repli byte-
        # identique au comportement historique ci-dessous).
        from ..selectors import resolve_via_nomenclature
        matched = resolve_via_nomenclature(request.user.company, code)
        if matched is not None:
            encode, regle = matched
            remainder = (
                code[len(regle.motif):] if not regle.est_regex else code)
            remainder = remainder.strip(':').strip()
            if encode == RegleCodeBarres.Encode.EMPLACEMENT and \
                    remainder.isdigit():
                emplacement = (EmplacementStock.objects
                               .filter(company=request.user.company,
                                       id=int(remainder))
                               .first())
                if emplacement is not None:
                    return Response({
                        'type': 'emplacement',
                        'id': emplacement.id,
                        'label': emplacement.nom,
                        'route': '/stock',
                    })
            elif encode == RegleCodeBarres.Encode.PRODUIT and \
                    remainder.isdigit():
                produit = (Produit.objects
                           .filter(company=request.user.company,
                                   id=int(remainder))
                           .first())
                if produit is not None:
                    return Response({
                        'type': 'produit',
                        'id': produit.id,
                        'label': produit.nom,
                        'sku': produit.sku or '',
                        'route': '/stock',
                    })
            # Une règle a matché mais la cible n'existe pas (ou le type
            # encode/lot/série n'a pas encore de résolveur dédié) : repli
            # sur le comportement historique ci-dessous plutôt qu'un 404
            # prématuré — un futur module peut compléter ce routage.

        # XSTK3 — un EAN/UPC/GTIN imprimé par le FABRICANT n'a pas de ':'
        # (contrairement aux jetons internes `PRODUIT:<id>`). On matche
        # d'abord les jetons internes (ci-dessous) puis, si le code ne suit
        # pas ce format, `Produit.code_barres` — scopé société.
        if ':' not in code:
            # XSTK4 — un composite GS1-128/DataMatrix commence par l'AI '01'
            # (GTIN, 14 chiffres) suivi d'autres AI (lot/péremption/série) :
            # plus long qu'un simple EAN/GTIN nu. On décompose d'abord et on
            # résout par GTIN (= code_barres) ; sinon repli sur un match
            # direct du code brut (EAN/UPC simple, comportement XSTK3).
            gtin = None
            gs1_extra = {}
            if code[:2] == '01' and len(code) > 16 and code[2:16].isdigit():
                from ..gs1 import parse_gs1
                parsed = parse_gs1(code)
                gtin = parsed.get('gtin')
                if gtin:
                    gs1_extra = {
                        'numero_lot': parsed.get('lot'),
                        'date_peremption': (
                            parsed['date_peremption'].isoformat()
                            if parsed.get('date_peremption') else None),
                        'numero_serie': parsed.get('serie'),
                    }
            lookup_code = gtin or code
            produit = (Produit.objects
                       .filter(company=request.user.company,
                               code_barres=lookup_code)
                       .first())
            if produit is None:
                return Response(
                    {'detail': 'Produit introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            data = {
                'type': 'produit',
                'id': produit.id,
                'label': produit.nom,
                'sku': produit.sku or '',
                'route': '/stock',
            }
            if gs1_extra:
                data['gs1'] = gs1_extra
            return Response(data)

        # ZSTK6 — jetons LOT:<produit_id>:<valeur> / SERIE:<produit_id>:
        # <valeur> (3 segments, contrairement aux jetons internes à 2
        # segments type PRODUIT:<id>) : traités AVANT le split générique
        # ci-dessous car leur second segment n'est pas un simple entier.
        first_prefix = code.split(':', 1)[0].strip().upper()
        if first_prefix in (labels.LOT_PREFIX, labels.SERIE_PREFIX):
            parts = code.split(':', 2)
            if len(parts) != 3 or not parts[1].strip().isdigit():
                return Response(
                    {'detail': 'Code illisible.'},
                    status=status.HTTP_400_BAD_REQUEST)
            produit_id = int(parts[1].strip())
            valeur = parts[2].strip()
            if first_prefix == labels.LOT_PREFIX:
                from ..models import LotEntrepot
                lot = (LotEntrepot.objects
                       .filter(company=request.user.company,
                               produit_id=produit_id, numero_lot=valeur)
                       .select_related('produit', 'emplacement')
                       .first())
                if lot is None:
                    return Response(
                        {'detail': 'Lot introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
                return Response({
                    'type': 'lot',
                    'id': lot.id,
                    'label': f'{lot.produit.nom} — lot {lot.numero_lot}',
                    'numero_lot': lot.numero_lot,
                    'quantite_restante': lot.quantite_restante,
                    'date_peremption': (
                        lot.date_peremption.isoformat()
                        if lot.date_peremption else None),
                    'route': '/stock',
                })
            # SERIE — lecture seule via installations.selectors (jamais son
            # modèle importé directement).
            from apps.installations.selectors import (
                serie_entrepot_scoped_by_serial,
            )
            serie = serie_entrepot_scoped_by_serial(
                request.user.company, produit_id, valeur)
            if serie is None:
                return Response(
                    {'detail': 'Série introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            return Response({
                'type': 'serie_entrepot',
                'id': serie.id,
                'label': f'N° série {serie.numero_serie}',
                'numero_serie': serie.numero_serie,
                'statut': serie.statut,
                'route': '/chantiers' if serie.installation_id else '/stock',
            })

        # XSTK20 — jeton KANBAN:<produit_id>:<emplacement_id> (3 segments,
        # même raison que LOT/SERIE ci-dessus). Le scan (bac vide) CRÉE — de
        # façon idempotente — une DemandeTransfert préremplie depuis le dépôt
        # principal ; jamais d'import du modèle installations (services).
        if first_prefix == labels.KANBAN_PREFIX:
            parts = code.split(':', 2)
            if len(parts) != 3 or not parts[1].strip().isdigit() \
                    or not parts[2].strip().isdigit():
                return Response(
                    {'detail': 'Code illisible.'},
                    status=status.HTTP_400_BAD_REQUEST)
            produit_id = int(parts[1].strip())
            emplacement_id = int(parts[2].strip())
            from apps.installations.services import (
                demande_transfert_depuis_kanban,
            )
            try:
                demande, created = demande_transfert_depuis_kanban(
                    company=request.user.company, user=request.user,
                    produit_id=produit_id,
                    emplacement_destination_id=emplacement_id)
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            return Response({
                'type': 'demande_transfert',
                'id': demande.id,
                'label': f'Demande {demande.reference}',
                'reference': demande.reference,
                'quantite': demande.quantite,
                'statut': demande.statut,
                'created': created,
                'route': '/stock',
            })

        prefix, _, raw_id = code.partition(':')
        prefix = prefix.strip().upper()
        raw_id = raw_id.strip()
        if not raw_id.isdigit():
            return Response(
                {'detail': 'Code illisible.'},
                status=status.HTTP_400_BAD_REQUEST)
        obj_id = int(raw_id)

        if prefix == labels.PRODUIT_PREFIX:
            produit = (Produit.objects
                       .filter(company=request.user.company, id=obj_id)
                       .first())
            if produit is None:
                return Response(
                    {'detail': 'Produit introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            return Response({
                'type': 'produit',
                'id': produit.id,
                'label': produit.nom,
                'sku': produit.sku or '',
                'route': '/stock',
            })

        if prefix == labels.SYSTEME_PREFIX:
            # Import paresseux : résolution en LECTURE SEULE, jamais d'écriture.
            from apps.installations.selectors import installation_scoped
            inst = installation_scoped(request.user.company, obj_id)
            if inst is None:
                return Response(
                    {'detail': 'Système installé introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            client_nom = getattr(inst.client, 'nom', '') if inst.client_id \
                else ''
            return Response({
                'type': 'systeme',
                'id': inst.id,
                'label': inst.reference,
                'client': client_nom,
                'statut': inst.statut,
                'route': '/chantiers',
            })

        if prefix == labels.INTERVENTION_PREFIX:
            # F23 — résolution LECTURE SEULE vers une intervention (sortie
            # chantier), scopée société. Import paresseux, aucune écriture.
            from apps.installations.selectors import intervention_scoped
            itv = intervention_scoped(request.user.company, obj_id)
            if itv is None:
                return Response(
                    {'detail': 'Intervention introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            inst = itv.installation
            client_nom = (getattr(inst.client, 'nom', '')
                          if inst and inst.client_id else '')
            return Response({
                'type': 'intervention',
                'id': itv.id,
                'label': itv.get_type_intervention_display(),
                'chantier': inst.reference if inst else '',
                'client': client_nom,
                'statut': itv.statut,
                'route': '/interventions',
            })

        if prefix == labels.EQUIP_PREFIX:
            # FG85 — résolution LECTURE SEULE vers un équipement SAV, scopé société.
            # Import paresseux, aucune écriture.
            from apps.sav.models import Equipement, Ticket
            equip = Equipement.objects.select_related(
                'produit', 'installation', 'installation__client',
            ).filter(company=request.user.company, id=obj_id).first()
            if equip is None:
                return Response(
                    {'detail': 'Équipement introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            produit_nom = equip.produit.nom if equip.produit_id else '—'
            client_nom = ''
            if equip.installation_id and equip.installation.client_id:
                c = equip.installation.client
                client_nom = f'{c.nom} {c.prenom or ""}'.strip()
            nb_tickets_ouverts = equip.tickets.filter(
                statut__in=Ticket.OPEN_STATUTS, annule=False).count()
            return Response({
                'type': 'equipement',
                'id': equip.id,
                'label': produit_nom,
                'serie': equip.numero_serie or '',
                'statut': equip.statut,
                'date_fin_garantie': (
                    equip.date_fin_garantie.isoformat()
                    if equip.date_fin_garantie else None),
                'client': client_nom,
                'nb_tickets_ouverts': nb_tickets_ouverts,
                'route': '/sav/equipements',
            })

        if prefix == labels.COLIS_PREFIX:
            # ZSTK5 — résolution LECTURE SEULE vers un colis de préparation
            # (FG322), scopé société. Import paresseux, aucune écriture.
            from apps.installations.selectors import colis_scoped
            colis = colis_scoped(request.user.company, obj_id)
            if colis is None:
                return Response(
                    {'detail': 'Colis introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            inst = colis.installation
            client_nom = (getattr(inst.client, 'nom', '')
                          if inst and inst.client_id else '')
            return Response({
                'type': 'colis',
                'id': colis.id,
                'label': colis.reference,
                'chantier': inst.reference if inst else '',
                'client': client_nom,
                'statut': colis.statut,
                'route': '/stock',
            })

        return Response(
            {'detail': 'Type de code inconnu.'},
            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='rebuter')
    def rebuter(self, request, *args, **kwargs):
        """XSTK10 — met au rebut une quantité de ce produit (casse/obsolète/
        périmé/vol…). Corps : ``{"quantite": int, "motif": "casse"|
        "obsolete"|"perime"|"vol"|"defaut"|"erreur"|"autre",
        "emplacement": id (optionnel), "reference_chantier": str
        (optionnel)}``. Motif obligatoire ; respecte le garde de stock
        négatif (XSTK8)."""
        produit = self.get_object()
        try:
            quantite = int(request.data.get('quantite'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Quantité invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'Le motif est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)

        emplacement = None
        emplacement_id = request.data.get('emplacement')
        if emplacement_id:
            emplacement = EmplacementStock.objects.filter(
                company=request.user.company, id=emplacement_id).first()
            if emplacement is None:
                return Response(
                    {'detail': 'Emplacement introuvable.'},
                    status=status.HTTP_400_BAD_REQUEST)

        from ..services import rebuter_produit
        try:
            result = rebuter_produit(
                company=request.user.company, produit=produit,
                quantite=quantite, motif=motif, user=request.user,
                emplacement=emplacement,
                reference_chantier=request.data.get('reference_chantier'))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'mouvement_id': result['mouvement'].id,
            'valeur_perdue': str(result['valeur_perdue']),
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='rapport-pertes')
    def rapport_pertes_view(self, request):
        """XSTK10 — rapport « pertes de la période » (quantités + valeur au
        coût moyen, par motif). Admin-only, jamais client-facing."""
        from ..services import rapport_pertes
        rapport = rapport_pertes(
            request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'))
        return Response([
            {
                'produit_id': e['produit_id'],
                'produit_nom': e['produit_nom'],
                'quantite_totale': e['quantite_totale'],
                'valeur_totale': str(e['valeur_totale']),
                'par_motif': {
                    motif: {'quantite': v['quantite'],
                            'valeur': str(v['valeur'])}
                    for motif, v in e['par_motif'].items()
                },
            }
            for e in rapport
        ])

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, *args, **kwargs):
        """QP2 — Clone ce produit sous un nouveau nom (rename → « créer un
        nouveau produit dans le stock »).

        Copie SERVEUR de tous les champs commerciaux/techniques (dont
        ``prix_achat`` — jamais transmis/accepté depuis le corps de la
        requête), ``company`` forcée à celle de l'utilisateur, SKU réinitialisé
        (le SKU d'origine n'est jamais dupliqué — évite un doublon
        (company, sku)). Réservé Directeur + Commercial responsable, comme
        toute création de produit (QG4).

        Corps : {"nom": "<nouveau nom>"} (requis).
        """
        source = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'detail': 'Le nom du nouveau produit est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        clone = Produit(
            company=request.user.company,
            nom=nom,
            description=source.description,
            sku=None,  # jamais dupliqué : évite un doublon (company, sku)
            prix_achat=source.prix_achat,
            prix_vente=source.prix_vente,
            quantite_stock=0,  # un clone démarre sans stock physique propre
            seuil_alerte=source.seuil_alerte,
            categorie=source.categorie,
            fournisseur=source.fournisseur,
            tva=source.tva,
            marque=source.marque,
            garantie=source.garantie,
            garantie_mois=source.garantie_mois,
            garantie_production_mois=source.garantie_production_mois,
            pompe_cv=source.pompe_cv,
            hmt_m=source.hmt_m,
            debit_m3j=source.debit_m3j,
            pompe_kw=source.pompe_kw,
            tension_v=source.tension_v,
            courbe_pompe=source.courbe_pompe,
        )
        clone.full_clean(exclude=['sku'])
        clone.save()
        serializer = self.get_serializer(clone)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
