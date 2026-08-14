"""Groupe NTWMS — vues de la couche ENTREPÔT (vagues de prélèvement, unités
logistiques, quais, expéditions, comptage tournant).

Toutes les vues héritent de ``CompanyScopedModelViewSet`` (scoping société +
``perform_create`` côté serveur) — jamais un ``ModelViewSet`` nu.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import (
    IsAnyRole, IsAdminRole, IsResponsableOrAdmin,
)

from ..models_wms import (
    AlerteRappel, DemandeTransfert, ExpeditionTransporteur, MouvementRebut,
    PlanChargement, PlanComptageTournant, PortailTiersToken, Quai,
    RendezVousTransporteur, RetourClient, UniteLogistique, VaguePicking,
)
from ..serializers_wms import (
    AlerteRappelSerializer, DemandeTransfertSerializer,
    ExpeditionTransporteurSerializer, MouvementRebutSerializer,
    PlanChargementSerializer, PlanComptageTournantSerializer,
    PortailTiersTokenSerializer, QuaiSerializer,
    RendezVousTransporteurSerializer, RetourClientSerializer,
    UniteLogistiqueSerializer, VaguePickingSerializer,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class VaguePickingViewSet(CompanyScopedModelViewSet):
    """NTWMS4 — vagues de prélèvement MULTI-SOURCE.

    Lecture tout rôle (le magasinier doit voir sa tournée) ; création/lancement
    responsable ou admin ; suppression admin. La création se fait par
    ``POST vagues-picking/`` avec ``{besoins: [...], installations: [...]}`` —
    la référence est posée côté serveur.
    """
    queryset = VaguePicking.objects.prefetch_related(
        'lignes__produit', 'lignes__bin', 'lignes__lot',
    ).select_related('cree_par').all()
    serializer_class = VaguePickingSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        # `get_permissions` prime sur le `permission_classes` d'une @action :
        # chaque action est donc listée explicitement ici.
        if self.action in READ_ACTIONS + ['lignes']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + [
                'lancer', 'prelever', 'configurer_liberation']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        """Crée la vague à partir des besoins fournis (multi-source) — le
        service pose la référence, résout les casiers et TRIE par parcours."""
        from ..services import creer_vague_depuis_besoins
        try:
            vague = creer_vague_depuis_besoins(
                company=request.user.company, user=request.user,
                besoins=request.data.get('besoins'),
                installations=request.data.get('installations'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(vague).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lancer')
    def lancer(self, request, pk=None):
        """Passe la vague en LANCÉE (idempotent)."""
        from ..services import lancer_vague
        vague = self.get_object()
        try:
            lancer_vague(vague)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        vague.refresh_from_db()
        return Response(self.get_serializer(vague).data)

    @action(detail=True, methods=['post'], url_path='configurer-liberation')
    def configurer_liberation(self, request, pk=None):
        """NTWMS12 — règle de libération de la vague
        (``{mode: manuel|auto_heure|auto_seuil, seuil_lignes?}``). Seule une
        vague en brouillon est reconfigurable."""
        from ..services import configurer_liberation_vague
        vague = self.get_object()
        try:
            configurer_liberation_vague(
                vague=vague, mode=request.data.get('mode'),
                seuil_lignes=request.data.get('seuil_lignes'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        vague.refresh_from_db()
        return Response(self.get_serializer(vague).data)

    @action(detail=True, methods=['post'],
            url_path=r'lignes/(?P<ligne_id>[0-9]+)/prelever')
    def prelever(self, request, pk=None, ligne_id=None):
        """Enregistre un prélèvement sur une ligne de CETTE vague
        (``{quantite: n}``). Refuse un dépassement du reste à prélever et
        clôture la vague quand tout est servi."""
        from ..services import prelever_ligne_picking
        vague = self.get_object()
        ligne = vague.lignes.filter(id=ligne_id).first()
        if ligne is None:
            return Response({'detail': 'Ligne introuvable dans cette vague.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            prelever_ligne_picking(
                ligne=ligne, quantite=request.data.get('quantite'),
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        vague.refresh_from_db()
        return Response(self.get_serializer(vague).data)


class UniteLogistiqueViewSet(CompanyScopedModelViewSet):
    """NTWMS6 — colis et palettes adressables (SSCC GS1).

    Le SSCC est attribué côté serveur à la création (jamais accepté du corps
    de requête). ``{id}/sceller/`` fige le contenu ; ``{id}/etiquette-pdf/``
    imprime l'étiquette SSCC scannable.
    """
    queryset = UniteLogistique.objects.prefetch_related(
        'lignes__produit', 'lignes__lot', 'enfants',
    ).select_related('parent', 'vague', 'scelle_par').all()
    serializer_class = UniteLogistiqueSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['etiquette_pdf', 'export_asn']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + [
                'sceller', 'ajouter_ligne', 'controler_scan', 'deplacer',
                'import_asn']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_unite = params.get('type_unite')
        if type_unite:
            qs = qs.filter(type_unite=type_unite)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import creer_unite_logistique
        company = request.user.company
        parent = None
        if request.data.get('parent'):
            parent = UniteLogistique.objects.filter(
                id=request.data.get('parent'), company=company).first()
            if parent is None:
                return Response(
                    {'detail': 'Palette introuvable dans cette société.'},
                    status=status.HTTP_400_BAD_REQUEST)
        vague = None
        if request.data.get('vague'):
            vague = VaguePicking.objects.filter(
                id=request.data.get('vague'), company=company).first()
        try:
            unite = creer_unite_logistique(
                company=company,
                type_unite=request.data.get('type_unite') or 'colis',
                parent=parent, vague=vague,
                poids_kg=request.data.get('poids_kg') or None,
                dimensions=request.data.get('dimensions') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(unite).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lignes')
    def ajouter_ligne(self, request, pk=None):
        """Ajoute une ligne de contenu (``{produit, quantite, lot?}``).
        Refusée si l'unité est déjà scellée."""
        from ..models import LotEntrepot, Produit
        from ..services import ajouter_ligne_unite_logistique
        unite = self.get_object()
        company = request.user.company
        produit = Produit.objects.filter(
            id=request.data.get('produit'), company=company).first()
        lot = None
        if request.data.get('lot'):
            lot = LotEntrepot.objects.filter(
                id=request.data.get('lot'), company=company).first()
        try:
            ajouter_ligne_unite_logistique(
                company=company, unite=unite, produit=produit,
                quantite=request.data.get('quantite'), lot=lot)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        unite.refresh_from_db()
        return Response(self.get_serializer(unite).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='controler-scan')
    def controler_scan(self, request, pk=None):
        """NTWMS11 — poste d'EMBALLAGE : contrôle bloquant d'un produit scanné.

        ``{produit, quantite}``. Un produit qui n'appartient pas à la vague en
        cours d'emballage (ou une quantité supérieure au prélevé) est REFUSÉ en
        400 — l'écran doit afficher l'alerte avant toute validation du colis.
        En cas de succès, la ligne est horodatée (audit `scanne_le`)."""
        from ..models import Produit
        from ..services import controler_scan_emballage
        unite = self.get_object()
        company = request.user.company
        produit = Produit.objects.filter(
            id=request.data.get('produit'), company=company).first()
        try:
            controler_scan_emballage(
                company=company, unite=unite, produit=produit,
                quantite=request.data.get('quantite') or 1,
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        unite.refresh_from_db()
        return Response(self.get_serializer(unite).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses={
        200: inline_serializer('StockUniteDeplacement', {
            'unite_logistique': serializers.IntegerField(),
            'sscc': serializers.CharField(),
            'bin_destination': serializers.IntegerField(),
            'bin_code': serializers.CharField(),
            'lignes_deplacees': serializers.IntegerField(),
            'unites_deplacees': serializers.ListField(
                child=serializers.IntegerField()),
        }),
        400: inline_serializer('StockUniteDeplacementErreur', {
            'detail': serializers.CharField(),
        }),
    })
    @action(detail=True, methods=['post'], url_path='deplacer')
    def deplacer(self, request, pk=None):
        """NTWMS25 — déplace l'unité ENTIÈRE vers un casier
        (``?bin_destination=<id>`` ou ``{bin_destination}``).

        Un seul scan : tout le contenu (et, pour une palette, ses colis
        enfants) suit, chaque ligne recevant un mouvement tracé
        casier→casier."""
        from ..services import deplacer_unite_logistique
        unite = self.get_object()
        modele_bin = UniteLogistique._meta.get_field('bin_actuel').related_model
        cible = (request.data.get('bin_destination')
                 or request.query_params.get('bin_destination'))
        bin_destination = modele_bin.objects.filter(
            id=cible, company=request.user.company).first()
        try:
            resultat = deplacer_unite_logistique(
                unite=unite, bin_destination=bin_destination,
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat)

    @extend_schema(responses={
        200: inline_serializer('StockUniteAsn', {
            'version': serializers.CharField(),
            'unite': serializers.DictField(),
            'lignes': serializers.ListField(child=serializers.DictField()),
            'totaux': serializers.DictField(),
        }),
        400: inline_serializer('StockUniteAsnErreur', {
            'detail': serializers.CharField(),
        }),
    })
    @action(detail=True, methods=['get'], url_path='export-asn')
    def export_asn(self, request, pk=None):
        """NTWMS27 — bordereau ASN (avis d'expédition anticipé) de l'unité.

        Fichier structuré JSON, prêt pour un futur mapping EDI ; aucune
        connexion EDI n'existe (export/import manuel). ``?telecharger=1``
        renvoie le même contenu en pièce jointe."""
        from ..services import exporter_asn
        unite = self.get_object()
        try:
            bordereau = exporter_asn(unite)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        reponse = Response(bordereau)
        if request.query_params.get('telecharger'):
            reponse['Content-Disposition'] = (
                f'attachment; filename="asn-{unite.sscc}.json"')
        return reponse

    @extend_schema(responses={
        200: inline_serializer('StockUniteAsnImport', {
            'valide': serializers.BooleanField(),
            'erreurs': serializers.ListField(child=serializers.CharField()),
            'unite_connue': serializers.BooleanField(),
            'sscc': serializers.CharField(),
            'lignes': serializers.ListField(child=serializers.DictField()),
        }),
    })
    @action(detail=False, methods=['post'], url_path='import-asn')
    def import_asn(self, request):
        """NTWMS27 — import MIROIR d'un bordereau ASN : valide et rapproche,
        n'écrit RIEN (contrôle de cohérence, pas une intégration EDI)."""
        from ..services import importer_asn
        return Response(importer_asn(request.user.company, request.data))

    @action(detail=True, methods=['post'], url_path='sceller')
    def sceller(self, request, pk=None):
        """Fige le contenu de l'unité et rend son étiquette imprimable."""
        from ..services import sceller_unite_logistique
        unite = self.get_object()
        try:
            sceller_unite_logistique(unite=unite, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        unite.refresh_from_db()
        return Response(self.get_serializer(unite).data)

    @action(detail=True, methods=['get'], url_path='etiquette-pdf')
    def etiquette_pdf(self, request, pk=None):
        """Étiquette SSCC scannable (GS1-128 ``(00)<sscc>``) en PDF.
        ``?sortie=html`` renvoie le HTML (debug/impression navigateur)."""
        from django.http import HttpResponse
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

        unite = self.get_object()
        contenu = ', '.join(
            f'{ligne.produit.nom} × {ligne.quantite}'
            for ligne in unite.lignes.select_related('produit')[:4]) or 'Vide'
        html = labels.render_etiquettes_sscc_html([{
            'sscc': unite.sscc,
            'titre': f'{unite.get_type_unite_display()} {unite.sscc}',
            'sous_titre': contenu,
        }])
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        response = HttpResponse(_html_to_pdf(html),
                                content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="sscc-{unite.sscc}.pdf"')
        return response


class QuaiViewSet(CompanyScopedModelViewSet):
    """NTWMS7 — quais de réception/expédition. Lecture tout rôle, écriture
    admin (c'est un paramétrage d'entrepôt)."""
    queryset = Quai.objects.select_related('emplacement').all()
    serializer_class = QuaiSerializer
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['planning']:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        type_quai = params.get('type_quai')
        if type_quai:
            qs = qs.filter(type_quai=type_quai)
        actif = params.get('actif')
        if actif in ('true', 'false'):
            qs = qs.filter(actif=(actif == 'true'))
        return qs

    @action(detail=False, methods=['get'], url_path='planning')
    def planning(self, request):
        """Planning JOUR (``?date=YYYY-MM-DD``) ou SEMAINE (``?date=`` +
        ``?vue=semaine``) de TOUS les quais, ou d'un seul (``?quai=<id>``).
        LECTURE SEULE."""
        from ..selectors import planning_quais
        try:
            donnees = planning_quais(
                request.user.company, date_str=request.query_params.get('date'),
                vue=request.query_params.get('vue') or 'jour',
                quai_id=request.query_params.get('quai'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(donnees)


class RendezVousTransporteurViewSet(CompanyScopedModelViewSet):
    """NTWMS7 — créneaux transporteur sur un quai.

    Le CHEVAUCHEMENT est refusé côté serveur (garde dans
    ``RendezVousTransporteur.save()``) : deux rendez-vous ne peuvent jamais
    occuper le même quai au même moment.
    """
    queryset = RendezVousTransporteur.objects.select_related(
        'quai', 'transporteur').all()
    serializer_class = RendezVousTransporteurSerializer
    ordering = ['date_heure_debut', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        quai = params.get('quai')
        if quai and str(quai).isdigit():
            qs = qs.filter(quai_id=int(quai))
        date = params.get('date')
        if date:
            qs = qs.filter(date_heure_debut__date=date)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _sauver(self, serializer):
        """Traduit le refus de chevauchement (ValueError posée dans
        ``save()``) en 400 lisible plutôt qu'en 500."""
        try:
            serializer.save(company=self.request.user.company)
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': str(exc)})

    def perform_create(self, serializer):
        self._sauver(serializer)

    def perform_update(self, serializer):
        self._sauver(serializer)


class ExpeditionTransporteurViewSet(CompanyScopedModelViewSet):
    """NTWMS9 — expéditions transporteur (étiquette réelle GATED, NoOp sinon).

    ``{id}/generer-etiquette/`` demande au connecteur configuré son numéro de
    suivi + son étiquette ; sans intégration configurée pour la société, le
    connecteur NoOp produit une étiquette INTERNE sans aucun appel externe.
    ``{id}/tracking/`` renvoie l'état de suivi connu.
    """
    queryset = ExpeditionTransporteur.objects.select_related(
        'unite_logistique', 'transporteur').all()
    serializer_class = ExpeditionTransporteurSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['tracking', 'tarifs']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['generer_etiquette']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import creer_expedition_transporteur
        company = request.user.company
        unite = UniteLogistique.objects.filter(
            id=request.data.get('unite_logistique'), company=company).first()
        try:
            expedition = creer_expedition_transporteur(
                company=company, unite=unite,
                provider_code=(request.data.get('transporteur_provider')
                               or 'aucun'),
                destination=request.data.get('destination') or '',
                cout_reel=request.data.get('cout_reel') or None)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(expedition).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='generer-etiquette')
    def generer_etiquette(self, request, pk=None):
        """Numéro de suivi + étiquette du connecteur (réel si gated, sinon
        interne). Idempotent."""
        from ..services import generer_etiquette_expedition
        expedition = self.get_object()
        try:
            generer_etiquette_expedition(
                expedition=expedition, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        expedition.refresh_from_db()
        return Response(self.get_serializer(expedition).data)

    @action(detail=True, methods=['get'], url_path='tracking')
    def tracking(self, request, pk=None):
        """État de suivi connu de cette expédition. LECTURE SEULE ; la clé
        MinIO de l'étiquette n'est JAMAIS exposée."""
        expedition = self.get_object()
        return Response({
            'numero_suivi': expedition.numero_suivi,
            'transporteur_provider': expedition.transporteur_provider,
            'statut': expedition.statut,
            'destination': expedition.destination,
            'date_expedition': expedition.date_expedition,
            'a_une_etiquette': bool(expedition.etiquette_pdf_key),
        })

    @action(detail=False, methods=['get'], url_path='tarifs')
    def tarifs(self, request):
        """NTWMS10 — comparatif coût/délai pour une unité logistique
        (``?unite_logistique=<id>&destination=``), AVANT de sceller le choix du
        transporteur. Sans connecteur configuré, renvoie le tarif de base du
        référentiel interne (repli gracieux). LECTURE SEULE."""
        from ..selectors import comparer_tarifs_transporteurs
        unite = UniteLogistique.objects.filter(
            id=request.query_params.get('unite_logistique'),
            company=request.user.company).first()
        if unite is None:
            return Response(
                {'detail': 'Unité logistique introuvable dans cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'unite_logistique': unite.id,
            'offres': comparer_tarifs_transporteurs(
                unite, destination=request.query_params.get('destination')
                or ''),
        })


class AlerteRappelViewSet(CompanyScopedModelViewSet):
    """NTWMS17 — rappels produit/lot (recall).

    ``{id}/impact/`` liste EN UN CLIC le stock restant en casier ET les
    chantiers/colis déjà servis avec le lot rappelé (réutilise la traçabilité
    NTWMS16). ``{id}/cloturer/`` clôt le rappel.
    """
    queryset = AlerteRappel.objects.select_related(
        'produit', 'lot', 'declenchee_par').all()
    serializer_class = AlerteRappelSerializer
    ordering = ['-date_declenchement', '-id']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['impact']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['cloturer']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        produit = params.get('produit')
        if produit and str(produit).isdigit():
            qs = qs.filter(produit_id=int(produit))
        return qs

    def perform_create(self, serializer):
        """Déclenche le rappel : auteur posé côté serveur + notification
        best-effort aux responsables (jamais bloquante)."""
        from ..services import notifier_rappel
        alerte = serializer.save(
            company=self.request.user.company,
            declenchee_par=self.request.user)
        notifier_rappel(alerte)

    @extend_schema(responses={
        200: inline_serializer('StockRappelImpact', {
            'alerte': serializers.IntegerField(),
            'produit': serializers.DictField(),
            'lots': serializers.ListField(child=serializers.DictField()),
            'stock_restant': serializers.IntegerField(),
            'casiers': serializers.ListField(child=serializers.DictField()),
            'chantiers': serializers.ListField(child=serializers.DictField()),
            'colis': serializers.ListField(child=serializers.DictField()),
        }),
    })
    @action(detail=True, methods=['get'], url_path='impact')
    def impact(self, request, pk=None):
        """Portée du rappel : stock encore en casier + chantiers/colis
        déjà servis. LECTURE SEULE."""
        from ..services import impact_rappel
        return Response(impact_rappel(self.get_object()))

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôt le rappel (idempotent)."""
        from ..services import cloturer_alerte_rappel
        alerte = self.get_object()
        cloturer_alerte_rappel(alerte)
        alerte.refresh_from_db()
        return Response(self.get_serializer(alerte).data)


class PlanComptageTournantViewSet(CompanyScopedModelViewSet):
    """NTWMS13 — plans de comptage tournant ABC.

    La liste AMORCE les trois plans par défaut (A=30 j, B=90 j, C=180 j) au
    premier accès — idempotent, jamais d'écrasement d'une fréquence déjà
    personnalisée. ``generer/`` déclenche la génération des sessions dues (la
    même que la commande plannifiable).
    """
    queryset = PlanComptageTournant.objects.all()
    serializer_class = PlanComptageTournantSerializer
    ordering = ['classe_abc']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        from ..services import assurer_plans_comptage_tournant
        if request.user.company_id:
            assurer_plans_comptage_tournant(request.user.company)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """Génère MAINTENANT les sessions de comptage dues de cette société."""
        from ..services import generer_comptages_tournants
        resultat = generer_comptages_tournants(company=request.user.company)
        return Response(resultat, status=status.HTTP_201_CREATED)


class PlanChargementViewSet(CompanyScopedModelViewSet):
    """NTWMS26 — plans de chargement camion et taux de remplissage.

    ``{id}/unites/`` ajoute une palette ET renvoie l'avertissement de
    dépassement ; ``{id}/verifier-capacite/`` recalcule le contrôle à tout
    moment (lecture seule).
    """
    queryset = PlanChargement.objects.select_related(
        'livraison', 'expedition', 'vehicule', 'cree_par'
    ).prefetch_related('unites_logistiques').all()
    serializer_class = PlanChargementSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['verifier_capacite']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['ajouter_unite']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import creer_plan_chargement
        company = request.user.company

        def _lie(nom, valeur):
            if not valeur:
                return None
            modele = PlanChargement._meta.get_field(nom).related_model
            return modele.objects.filter(id=valeur, company=company).first()

        plan = creer_plan_chargement(
            company=company, user=request.user,
            livraison=_lie('livraison', request.data.get('livraison')),
            expedition=_lie('expedition', request.data.get('expedition')),
            vehicule=_lie('vehicule', request.data.get('vehicule')),
            capacite_kg=request.data.get('capacite_kg') or None,
            capacite_m3=request.data.get('capacite_m3') or None,
            note=request.data.get('note') or '')
        return Response(self.get_serializer(plan).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses={
        200: inline_serializer('StockPlanChargementCapacite', {
            'plan': serializers.IntegerField(),
            'nb_unites': serializers.IntegerField(),
            'poids_kg': serializers.DecimalField(
                max_digits=12, decimal_places=3),
            'volume_m3': serializers.DecimalField(
                max_digits=12, decimal_places=3),
            'capacite_kg': serializers.DecimalField(
                max_digits=12, decimal_places=2, allow_null=True),
            'capacite_m3': serializers.DecimalField(
                max_digits=12, decimal_places=3, allow_null=True),
            'poids_utilise_pct': serializers.DecimalField(
                max_digits=8, decimal_places=2, allow_null=True),
            'volume_utilise_pct': serializers.DecimalField(
                max_digits=8, decimal_places=2, allow_null=True),
            'depassement': serializers.BooleanField(),
            'avertissement': serializers.CharField(),
        }),
    })
    @action(detail=True, methods=['get'], url_path='verifier-capacite')
    def verifier_capacite(self, request, pk=None):
        """Poids/volume embarqués vs capacité déclarée. LECTURE SEULE."""
        from ..services import verifier_capacite_plan
        return Response(verifier_capacite_plan(self.get_object()))

    @extend_schema(responses={
        201: inline_serializer('StockPlanChargementAjout', {
            'plan': serializers.IntegerField(),
            'nb_unites': serializers.IntegerField(),
            'depassement': serializers.BooleanField(),
            'avertissement': serializers.CharField(),
        }),
        400: inline_serializer('StockPlanChargementErreur', {
            'detail': serializers.CharField(),
        }),
    })
    @action(detail=True, methods=['post'], url_path='unites')
    def ajouter_unite(self, request, pk=None):
        """Ajoute une unité (``{unite_logistique}``) et renvoie le contrôle
        de capacité — l'avertissement AVANT validation."""
        from ..services import ajouter_unite_plan_chargement
        plan = self.get_object()
        unite = UniteLogistique.objects.filter(
            id=request.data.get('unite_logistique'),
            company=request.user.company).first()
        try:
            controle = ajouter_unite_plan_chargement(plan=plan, unite=unite)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(controle, status=status.HTTP_201_CREATED)


class MouvementRebutViewSet(CompanyScopedModelViewSet):
    """NTWMS24 — déclarations de casse / freinte / rebut MOTIVÉES.

    La déclaration pose elle-même le mouvement de stock (service de rebut
    existant) : ce viewset est en création seule côté écriture — une perte
    déclarée ne se modifie pas, elle se corrige par un ajustement tracé.
    """
    queryset = MouvementRebut.objects.select_related(
        'produit', 'bin', 'declare_par', 'mouvement').all()
    serializer_class = MouvementRebutSerializer
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action == 'create':
            # Le magasinier déclare ce qu'il casse : la déclaration doit être
            # à sa portée, sinon elle n'est jamais faite.
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        motif = params.get('motif')
        if motif:
            qs = qs.filter(motif=motif)
        produit = params.get('produit')
        if produit and str(produit).isdigit():
            qs = qs.filter(produit_id=int(produit))
        return qs

    def create(self, request, *args, **kwargs):
        from ..models import Produit
        from ..services import declarer_mouvement_rebut
        company = request.user.company
        produit = Produit.objects.filter(
            id=request.data.get('produit'), company=company).first()
        bin_source = None
        if request.data.get('bin'):
            modele_bin = MouvementRebut._meta.get_field('bin').related_model
            bin_source = modele_bin.objects.filter(
                id=request.data.get('bin'), company=company).first()
        try:
            rebut = declarer_mouvement_rebut(
                company=company, user=request.user, produit=produit,
                quantite=request.data.get('quantite'),
                motif=request.data.get('motif'), bin_source=bin_source,
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(rebut).data,
                        status=status.HTTP_201_CREATED)


class RetourClientViewSet(CompanyScopedModelViewSet):
    """NTWMS23 — retours client (RMA) côté entrepôt.

    ``{id}/receptionner/`` acte l'arrivée physique (seules les lignes
    REVENDABLE réintègrent le stock vendable) ; ``{id}/inspecter/`` acte le
    contrôle qualité ligne par ligne.
    """
    queryset = RetourClient.objects.select_related(
        'client', 'chantier', 'ticket', 'cree_par').prefetch_related(
            'lignes__produit', 'lignes__bin').all()
    serializer_class = RetourClientSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['receptionner', 'inspecter']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        client = params.get('client')
        if client and str(client).isdigit():
            qs = qs.filter(client_id=int(client))
        return qs

    def create(self, request, *args, **kwargs):
        """``{client, chantier?, ticket?, motif?, lignes: [{produit,
        quantite, etat_constate?, bin?}]}`` — la référence est posée côté
        serveur."""
        from ..services import creer_retour_client
        company = request.user.company
        modele_client = RetourClient._meta.get_field('client').related_model
        client = modele_client.objects.filter(
            id=request.data.get('client'), company=company).first()
        chantier = None
        if request.data.get('chantier'):
            modele_chantier = (
                RetourClient._meta.get_field('chantier').related_model)
            chantier = modele_chantier.objects.filter(
                id=request.data.get('chantier'), company=company).first()
        ticket = None
        if request.data.get('ticket'):
            modele_ticket = RetourClient._meta.get_field('ticket').related_model
            ticket = modele_ticket.objects.filter(
                id=request.data.get('ticket'), company=company).first()
        try:
            retour = creer_retour_client(
                company=company, user=request.user, client=client,
                chantier=chantier, ticket=ticket,
                motif=request.data.get('motif') or '',
                lignes=request.data.get('lignes'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(retour).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='receptionner')
    def receptionner(self, request, pk=None):
        """Acte l'arrivée : seules les lignes REVENDABLE entrent en stock."""
        from ..services import receptionner_retour_client
        retour = self.get_object()
        try:
            receptionner_retour_client(retour=retour, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        retour.refresh_from_db()
        return Response(self.get_serializer(retour).data)

    @action(detail=True, methods=['post'], url_path='inspecter')
    def inspecter(self, request, pk=None):
        """Acte le contrôle qualité : ``{lignes: [{ligne, etat_constate,
        bin?, note?}]}``."""
        from ..services import inspecter_retour_client
        retour = self.get_object()
        try:
            inspecter_retour_client(
                retour=retour, lignes=request.data.get('lignes'),
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        retour.refresh_from_db()
        return Response(self.get_serializer(retour).data)


class DemandeTransfertViewSet(CompanyScopedModelViewSet):
    """NTWMS21 — demandes de transfert soumises à approbation.

    Création : tout rôle autorisé à demander (le magasinier constate le
    besoin). Approbation/rejet/exécution : responsable ou admin — c'est la
    garde qui donne son sens au seuil.
    """
    queryset = DemandeTransfert.objects.select_related(
        'produit', 'emplacement_source', 'emplacement_destination',
        'demande_par', 'approuve_par').all()
    serializer_class = DemandeTransfertSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsAnyRole()]
        if self.action in ['approuver', 'rejeter', 'executer']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        from ..models import EmplacementStock, Produit
        from ..services import creer_demande_transfert
        company = request.user.company
        produit = Produit.objects.filter(
            id=request.data.get('produit'), company=company).first()
        emplacements = {
            e.id: e for e in EmplacementStock.objects.filter(company=company)}
        try:
            demande = creer_demande_transfert(
                company=company, user=request.user, produit=produit,
                quantite=request.data.get('quantite'),
                emplacement_source=emplacements.get(
                    _entier(request.data.get('emplacement_source'))),
                emplacement_destination=emplacements.get(
                    _entier(request.data.get('emplacement_destination'))),
                motif=request.data.get('motif') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(demande).data,
                        status=status.HTTP_201_CREATED)

    def _decider(self, request, approuver):
        from ..services import decider_demande_transfert
        demande = self.get_object()
        try:
            decider_demande_transfert(
                demande=demande, user=request.user, approuver=approuver)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        demande.refresh_from_db()
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """Approuve la demande (responsable/admin)."""
        return self._decider(request, True)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """Rejette la demande (responsable/admin)."""
        return self._decider(request, False)

    @action(detail=True, methods=['post'], url_path='executer')
    def executer(self, request, pk=None):
        """Crée le TransfertStock réel d'une demande APPROUVÉE."""
        from ..services import executer_demande_transfert
        demande = self.get_object()
        try:
            executer_demande_transfert(demande=demande, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        demande.refresh_from_db()
        return Response(self.get_serializer(demande).data)


def _entier(valeur):
    """Id numérique, ou ``None`` (jamais une exception sur une saisie libre)."""
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


class PortailTiersTokenViewSet(CompanyScopedModelViewSet):
    """NTWMS20 — jetons du portail 3PL (lecture seule côté dépositaire).

    Administration RÉSERVÉE à l'admin : distribuer un lien de stock est une
    décision d'accès. Le jeton est généré côté serveur ; la révocation se fait
    en passant ``revoked=true``.
    """
    queryset = PortailTiersToken.objects.select_related('cree_par').all()
    serializer_class = PortailTiersTokenSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        tiers = self.request.query_params.get('tiers_nom')
        if tiers:
            qs = qs.filter(tiers_nom__icontains=tiers)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company,
                        cree_par=self.request.user)


def _date_param(valeur):
    """Convertit ``YYYY-MM-DD`` en date, ou ``None`` (jamais une exception)."""
    import datetime

    valeur = (valeur or '').strip()
    if not valeur:
        return None
    try:
        return datetime.date.fromisoformat(valeur)
    except ValueError:
        return None


@extend_schema(responses={
    200: inline_serializer('StockReslottingSuggestions', {
        'suggestions': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def reslotting_suggestions_view(request):
    """NTWMS30 — produits à forte rotation rangés loin de l'expédition.

    LECTURE SEULE, aucune action automatique : le magasinier valide chaque
    déplacement par le transfert existant. ``?debut=&fin=`` bornent la fenêtre
    de rotation (12 derniers mois par défaut).
    """
    import datetime

    from django.utils import timezone

    from ..selectors import suggerer_reslotting

    fin = _date_param(request.query_params.get('fin')) or timezone.localdate()
    debut = (_date_param(request.query_params.get('debut'))
             or fin - datetime.timedelta(days=365))
    return Response({
        'suggestions': suggerer_reslotting(
            request.user.company, depuis=debut, jusqu_a=fin),
    })


@extend_schema(responses={
    200: inline_serializer('StockEntrepotPertes', {
        'debut': serializers.CharField(allow_null=True),
        'fin': serializers.CharField(allow_null=True),
        'total_valeur': serializers.DecimalField(
            max_digits=14, decimal_places=2),
        'total_quantite': serializers.IntegerField(),
        'par_motif': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def entrepot_pertes_view(request):
    """NTWMS24 — valeur de perte par motif et par période (``?debut=&fin=``).

    Ne compte QUE les déclarations de rebut motivées : les ajustements
    d'inventaire normaux n'y entrent jamais. Valeurs INTERNES (coût d'achat)
    — réservé aux responsables/admins, jamais client-facing.
    """
    from ..services import rapport_pertes_entrepot

    debut = _date_param(request.query_params.get('debut'))
    fin = _date_param(request.query_params.get('fin'))
    rapport = rapport_pertes_entrepot(
        request.user.company, debut=debut, fin=fin)
    rapport.update({
        'debut': debut.isoformat() if debut else None,
        'fin': fin.isoformat() if fin else None,
    })
    return Response(rapport)


@extend_schema(responses={
    200: inline_serializer('StockEntrepotProductivite', {
        'debut': serializers.CharField(allow_null=True),
        'fin': serializers.CharField(allow_null=True),
        'operateurs': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def entrepot_productivite_view(request):
    """NTWMS18 — classement de productivité entrepôt (``?debut=&fin=``).

    Lignes traitées par opérateur et par type d'opération sur la période.
    Réservé aux responsables/admins. LECTURE SEULE — c'est un INDICATEUR de
    charge, jamais un instrument de sanction automatisée.
    """
    from ..selectors import productivite_operateur

    debut = _date_param(request.query_params.get('debut'))
    fin = _date_param(request.query_params.get('fin'))
    return Response({
        'debut': debut.isoformat() if debut else None,
        'fin': fin.isoformat() if fin else None,
        'operateurs': productivite_operateur(
            request.user.company, debut=debut, fin=fin),
    })
