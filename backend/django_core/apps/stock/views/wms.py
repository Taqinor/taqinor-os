"""Groupe NTWMS — vues de la couche ENTREPÔT (vagues de prélèvement, unités
logistiques, quais, expéditions, comptage tournant).

Toutes les vues héritent de ``CompanyScopedModelViewSet`` (scoping société +
``perform_create`` côté serveur) — jamais un ``ModelViewSet`` nu.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import (
    IsAnyRole, IsAdminRole, IsResponsableOrAdmin,
)

from ..models_wms import (
    AlerteRappel, ExpeditionTransporteur, PlanComptageTournant, Quai,
    RendezVousTransporteur, UniteLogistique, VaguePicking,
)
from ..serializers_wms import (
    AlerteRappelSerializer, ExpeditionTransporteurSerializer,
    PlanComptageTournantSerializer, QuaiSerializer,
    RendezVousTransporteurSerializer, UniteLogistiqueSerializer,
    VaguePickingSerializer,
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
        if self.action in READ_ACTIONS + ['etiquette_pdf']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + [
                'sceller', 'ajouter_ligne', 'controler_scan']:
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
