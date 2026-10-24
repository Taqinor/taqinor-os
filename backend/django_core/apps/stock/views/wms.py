"""Groupe NTWMS — vues de la couche ENTREPÔT (vagues de prélèvement, unités
logistiques, quais, expéditions, comptage tournant).

Toutes les vues héritent de ``CompanyScopedModelViewSet`` (scoping société +
``perform_create`` côté serveur) — jamais un ``ModelViewSet`` nu.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework.parsers import JSONParser
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..openapi_helpers import (
    BINARY, BOOL, DATE, DATE_OU_VIDE, ID_OU_VIDE, INT, OBJET, P, PDF, STR, choix_ou_vide, corps,
)
from core.champs_stricts import MOTIF_SANS_NUL, ChaineStricte, IdInconnu404Mixin, _ids_inconnus_seulement
from core.viewsets import CompanyScopedModelViewSet
from ..utils.params import (
    ID_MAX, booleen_requete_ou_400, choix_ou_400, corps_objet, date_ou_400, entier_ou_400, id_corps,
    id_requete_ou_400, statut_requete_ou_400, texte_sans_nul_ou_400, types_corps_ou_400, valeur_unique_ou_400,
)
from ..erreurs_achats import ConflitEtat, EtatIncompatible
from authentication.permissions import (
    IsAnyRole, IsAdminRole, IsResponsableOrAdmin,
)

from ..models_wms import (
    AlerteRappel, BlocageQualite, ExpeditionTransporteur, LigneRetourClient, MouvementRebut,
    PlanChargement, PlanComptageTournant, PortailTiersToken, Quai,
    RendezVousTransporteur, RetourClient, UniteLogistique, VaguePicking,
)
from ..serializers_wms import (
    AlerteRappelSerializer, BlocageQualiteSerializer,
    ExpeditionTransporteurSerializer, MouvementRebutSerializer,
    PlanChargementSerializer, PlanComptageTournantSerializer,
    PortailTiersTokenSerializer, QuaiSerializer,
    RendezVousTransporteurSerializer, RetourClientSerializer,
    UniteLogistiqueSerializer, VaguePickingSerializer,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

CORPS_IMPORT_ASN = corps('UniteImportAsnCorps', version=ChaineStricte(required=False),
                         unite=serializers.DictField(required=False),
                         lignes=serializers.ListField(child=serializers.DictField(), required=False),
                         totaux=serializers.DictField(required=False))


_ID_CORPS = {'min_value': 1, 'max_value': ID_MAX}

#: Début des deux refus de ``creer_vague_depuis_besoins`` qui disent « rien à regrouper »
#: (« Aucun besoin à regrouper… », « Aucun besoin valide à regrouper… ») : un état, pas une saisie.
AUCUN_BESOIN = 'Aucun besoin'

#: CI #997 fuzz (4) — corps de création d'une vague : des besoins explicites
#: et/ou des chantiers dont on reprend les réservations ; ni l'un ni l'autre (ou
#: rien de servable) est un état « aucun besoin à regrouper » (409).
CORPS_VAGUE = corps(
    'VagueCreerCorps',
    besoins=serializers.ListField(required=False, child=corps(
        'VagueBesoinCorps', produit_id=serializers.IntegerField(**_ID_CORPS),
        quantite=serializers.IntegerField(**_ID_CORPS),
        installation_id=serializers.IntegerField(required=False, allow_null=True, **_ID_CORPS),
        bon_commande_id=serializers.IntegerField(required=False, allow_null=True, **_ID_CORPS))),
    installations=serializers.ListField(required=False, child=serializers.IntegerField(**_ID_CORPS)),
    note=ChaineStricte(required=False, allow_blank=True, allow_null=True))

#: Corps de création d'un retour client : un client, au moins une ligne.
CORPS_RETOUR_CLIENT = corps(
    'RetourClientCreerCorps',
    client=serializers.IntegerField(**_ID_CORPS),
    chantier=serializers.IntegerField(required=False, allow_null=True, **_ID_CORPS),
    ticket=serializers.IntegerField(required=False, allow_null=True, **_ID_CORPS),
    motif=ChaineStricte(required=False, allow_blank=True, allow_null=True),
    lignes=serializers.ListField(min_length=1, child=corps(
        'RetourClientLigneCorps', produit=serializers.IntegerField(**_ID_CORPS),
        quantite=serializers.IntegerField(**_ID_CORPS),
        etat_constate=serializers.ChoiceField(choices=LigneRetourClient.EtatConstate.choices, required=False),
        bin=serializers.IntegerField(required=False, allow_null=True, **_ID_CORPS))))


def _liste_d_objets_ou_400(valeur, champ, **types):
    """Liste de ``champ`` dont CHAQUE élément est un objet typé par
    ``types_corps_ou_400`` ; l'erreur nomme l'élément (``{champ: {rang: …}}``)."""
    if valeur is None:
        return []
    if not isinstance(valeur, list):
        raise ValidationError({champ: ['Liste attendue.']})
    for rang, element in enumerate(valeur):
        if not isinstance(element, dict):
            raise ValidationError({champ: {str(rang): ['Objet attendu.']}})
        try:
            types_corps_ou_400(element, **types)
        except ValidationError as exc:
            raise ValidationError({champ: {str(rang): exc.detail}})
    return valeur


def _relations_scopees(view, request, noms, inconnu_en_404=False):
    """ASTK6 — résout les FK d'un ``create`` maison par les champs SCOPÉS
    société du sérialiseur de la vue (``CompanyScopedRelationsMixin``).

    Un id d'une autre société lève la même ``ValidationError`` « objet
    inexistant » (400) qu'un id qui n'existe pas — au lieu d'être
    silencieusement ignoré. Renvoie ``{nom: instance ou None}``.

    ``inconnu_en_404`` (CI #997 fuzz 4) : quand TOUTES les erreurs sont « objet
    inexistant », la réponse est un 404 de même corps — le corps était conforme
    au schéma, c'est la ressource qui manque.
    """
    from rest_framework.exceptions import NotFound, ValidationError

    champs = view.get_serializer().fields
    resolues, erreurs = {}, {}
    donnees = corps_objet(request)  # corps non objet -> 400 (ERR fuzz)
    for nom in noms:
        valeur = donnees.get(nom)
        if valeur in (None, ''):
            resolues[nom] = None
            continue
        try:
            resolues[nom] = champs[nom].to_internal_value(valeur)
        except ValidationError as exc:
            erreurs[nom] = exc.detail
    if erreurs:
        if inconnu_en_404 and _ids_inconnus_seulement(erreurs, champs):
            raise NotFound(erreurs)
        raise ValidationError(erreurs)
    return resolues


class _ExpeditionCorps404(IdInconnu404Mixin, ExpeditionTransporteurSerializer):
    """Corps de création d'expédition : le sérialiseur publié, un id inconnu
    seul -> 404 (comportement historique de la création)."""


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR)]))
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

    parser_classes = [JSONParser]

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

    @extend_schema(request=CORPS_VAGUE, responses={201: VaguePickingSerializer})
    def create(self, request, *args, **kwargs):
        """Crée la vague à partir des besoins fournis (multi-source) — le
        service pose la référence, résout les casiers et TRIE par parcours."""
        from ..services import creer_vague_depuis_besoins
        donnees = corps_objet(request)  # corps non objet -> 400 (jamais « aucun besoin »)
        # CI #997 fuzz (4) — corps typé comme le schéma publié (un besoin non
        # objet, une quantité texte, une note numérique faisaient un 500 ou
        # passaient en silence) ; ni besoin ni chantier servable : 409.
        types_corps_ou_400(donnees, textes=('note',), nuls=('note',))
        besoins = _liste_d_objets_ou_400(
            donnees.get('besoins'), 'besoins', entiers=('quantite',),
            ids=('produit_id', 'installation_id', 'bon_commande_id'), nuls=('installation_id', 'bon_commande_id'))
        installations = donnees.get('installations')
        if installations is not None and (not isinstance(installations, list) or any(
                id_corps(i) is None or isinstance(i, str) for i in installations)):
            raise ValidationError({'installations': ['Liste d\'identifiants entiers attendue.']})
        if '\x00' in (donnees.get('note') or ''):
            raise ValidationError({'note': ['Le caractère nul n’est pas autorisé.']})
        try:
            vague = creer_vague_depuis_besoins(
                company=request.user.company, user=request.user,
                besoins=besoins, installations=installations,
                note=donnees.get('note') or '')
        except ValueError as exc:
            # « Aucun besoin (valide) à regrouper » : le corps est conforme, c'est l'état
            # des réservations / du catalogue qui ne donne rien à servir (409) ; les
            # autres refus du service (source « objet inexistant »…) restent des 400.
            etat = str(exc).startswith(AUCUN_BESOIN)
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT if etat else status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(vague).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=VaguePickingSerializer)
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

    @extend_schema(request=corps('VagueConfigurerLiberationCorps', mode=serializers.CharField(),
                                 seuil_lignes=serializers.IntegerField(required=False, allow_null=True)),
                   responses=VaguePickingSerializer)
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

    @extend_schema(request=corps('VaguePreleverCorps', quantite=serializers.IntegerField()),
                   responses=VaguePickingSerializer)
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


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR), P('type_unite', STR)]))
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

    parser_classes = [JSONParser]

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
        # ASTK6 — parent et vague bornés par les champs scopés du sérialiseur
        # (une vague étrangère n'est plus silencieusement ignorée).
        if not isinstance(request.data, dict):
            return Response({'detail': 'Corps JSON objet attendu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Types / longueurs des champs simples validés par le sérialiseur
        # (une `dimensions` trop longue levait une 500 en base).
        # CI #997 fuzz (2) : valeurs TELLES QUE REÇUES (un `null` n'est plus
        # remplacé par le défaut — type/dimensions ne sont pas nullables).
        simples = self.get_serializer(data={
            cle: request.data[cle] for cle in ('type_unite', 'poids_kg', 'dimensions')
            if cle in request.data})
        simples.is_valid(raise_exception=True)
        # CI #1004 — puis parent/vague : id étranger ou absent → 404 de même
        # corps, comme le PATCH (IdInconnu404Mixin du sérialiseur).
        liens = _relations_scopees(self, request, ['parent', 'vague'], inconnu_en_404=True)
        try:
            unite = creer_unite_logistique(
                company=company,
                type_unite=simples.validated_data.get('type_unite', 'colis'),
                parent=liens['parent'], vague=liens['vague'],
                poids_kg=simples.validated_data.get('poids_kg'),
                dimensions=simples.validated_data.get('dimensions') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(unite).data,
                        status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """ASTK31 — une unité SCELLÉE (ou expédiée) est immuable : parent,
        vague, type, poids et dimensions ne bougent plus (l'étiquette SSCC
        déjà imprimée doit toujours correspondre au contenu). Même prédicat
        ``est_figee`` que l'ajout de ligne."""
        from rest_framework.exceptions import ValidationError
        if serializer.instance.est_figee:
            raise ValidationError({'detail': (
                'Unité scellée : elle ne peut plus être modifiée.')})
        super().perform_update(serializer)

    @extend_schema(request=corps('UniteAjouterLigneCorps', produit=serializers.IntegerField(),
                                 quantite=serializers.IntegerField(), lot=serializers.IntegerField(required=False,
                                                                                                   allow_null=True)),
                   responses={201: UniteLogistiqueSerializer})
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

    @extend_schema(request=corps('UniteControlerScanCorps', produit=serializers.IntegerField(),
                                 quantite=serializers.IntegerField(required=False)),
                   responses={201: UniteLogistiqueSerializer})
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

    @extend_schema(request=corps('UniteDeplacerCorps', bin_destination=serializers.IntegerField()),
                   parameters=[P('bin_destination', INT, False, 'Casier de destination (ou dans le corps)')],
                   responses={
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

    @extend_schema(parameters=[P('telecharger', BOOL, False, 'Renvoyer en pièce jointe')], responses={
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

    @extend_schema(request=CORPS_IMPORT_ASN, responses={
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
        # ENF11 : la STRUCTURE déclarée (version texte, unite/totaux objets,
        # lignes = liste d'objets) est exigée en 400 ; le CONTENU incohérent
        # reste rendu en 200 `valide: false` (import miroir).
        entree = CORPS_IMPORT_ASN.__class__(data=request.data)
        entree.is_valid(raise_exception=True)
        return Response(importer_asn(request.user.company, request.data))

    @extend_schema(request=None, responses=UniteLogistiqueSerializer)
    @action(detail=True, methods=['post'], url_path='sceller')
    def sceller(self, request, pk=None):
        """Fige le contenu de l'unité et rend son étiquette imprimable."""
        from ..services import sceller_unite_logistique
        unite = self.get_object()
        try:
            sceller_unite_logistique(unite=unite, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)  # seul refus : unité vide (état)
        unite.refresh_from_db()
        return Response(self.get_serializer(unite).data)

    @extend_schema(parameters=[P('sortie', STR, False, 'html ou pdf', ['html', 'pdf']), P('symbology', STR, False,
                                                                                          'Symbologie', ['qr',
                                                                                                         'code128'])],
                   responses={PDF: BINARY, (200, 'text/html'): STR})
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


@extend_schema_view(list=extend_schema(parameters=[P('type_quai', STR), P('actif', BOOL)]))
class QuaiViewSet(CompanyScopedModelViewSet):
    """NTWMS7 — quais de réception/expédition. Lecture tout rôle, écriture
    admin (c'est un paramétrage d'entrepôt)."""
    queryset = Quai.objects.select_related('emplacement').all()
    serializer_class = QuaiSerializer
    ordering = ['nom']

    parser_classes = [JSONParser]

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
        actif = booleen_requete_ou_400(self.request, 'actif')  # CI #997 : `null` -> 400
        if actif is not None:
            qs = qs.filter(actif=actif)
        return qs

    @extend_schema(parameters=[P('date', DATE, True), P('vue', STR, False, 'Vue', ['jour', 'semaine']),
                               P('quai', ID_OU_VIDE)],
                   responses=OBJET)
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
                quai_id=id_requete_ou_400(request, 'quai'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(donnees)


@extend_schema_view(list=extend_schema(parameters=[P('quai', ID_OU_VIDE), P('date', DATE_OU_VIDE), P('statut', STR)]))
class RendezVousTransporteurViewSet(CompanyScopedModelViewSet):
    """NTWMS7 — créneaux transporteur sur un quai.

    Le CHEVAUCHEMENT est refusé côté serveur (garde dans
    ``RendezVousTransporteur.save()``) : deux rendez-vous ne peuvent jamais
    occuper le même quai au même moment.
    """
    queryset = RendezVousTransporteur.objects.select_related(
        'quai', 'transporteur', 'fournisseur', 'bon_commande').all()
    serializer_class = RendezVousTransporteurSerializer
    ordering = ['date_heure_debut', 'id']

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        # CI #997 fuzz — filtres stricts (``?quai=null`` était ignoré en silence).
        quai = id_requete_ou_400(self.request, 'quai')
        if quai is not None:
            qs = qs.filter(quai_id=quai)
        date = date_ou_400(params.get('date'), 'date')
        if date:
            qs = qs.filter(date_heure_debut__date=date)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _sauver(self, serializer):
        """Traduit le refus de chevauchement en 409 lisible plutôt qu'en 500.

        Deux refus possibles, un seul message : la garde Python de ``save()``
        (``ValueError``) sur le chemin courant, et — AUD214 — l'
        ``ExclusionConstraint`` de la base (``IntegrityError``) quand deux
        requêtes concurrentes ont lu AVANT que l'autre n'insère. La sauvegarde
        est enveloppée dans son propre bloc atomique pour que l'
        ``IntegrityError`` n'empoisonne pas la transaction courante.
        """
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                serializer.save(company=self.request.user.company)
        except ValueError as exc:
            # Chevauchement d'un rendez-vous déjà posé : l'état du quai
            # s'oppose à un corps conforme (409, plus 400).
            raise ConflitEtat(str(exc))
        except IntegrityError:
            raise ConflitEtat(
                'Ce créneau vient d\'être réservé sur ce quai, '
                'choisissez-en un autre.')

    def perform_create(self, serializer):
        self._sauver(serializer)

    def perform_update(self, serializer):
        self._sauver(serializer)


@extend_schema_view(list=extend_schema(parameters=[
    P('statut', choix_ou_vide(ExpeditionTransporteur.Statut.values))]))
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

    parser_classes = [JSONParser]

    def get_permissions(self):
        # NTWMS43 — la lettre de voiture est une LECTURE (elle n'écrit rien
        # et ne stocke pas le PDF).
        if self.action in READ_ACTIONS + ['tracking', 'tarifs', 'cmr_pdf']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['generer_etiquette']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    @extend_schema(responses={(200, 'application/pdf'): bytes})
    @action(detail=True, methods=['get'], url_path='cmr-pdf',
            permission_classes=[IsAnyRole])
    def cmr_pdf(self, request, pk=None):
        """NTWMS43 — lettre de voiture (CMR simplifiée) de cette expédition.

        Expéditeur (profil de la SOCIÉTÉ — white-label, jamais une marque en
        dur), destinataire, nature des marchandises, poids total, nombre de
        colis et références SSCC (NTWMS6). Document INTERNE/transporteur :
        aucun rapport avec le moteur de devis vendorisé (règle #4).
        """
        from django.http import HttpResponse

        from ..utils.pdf_cmr import generate_cmr_pdf

        expedition = self.get_object()
        pdf = generate_cmr_pdf(expedition)
        reponse = HttpResponse(pdf, content_type='application/pdf')
        nom = (expedition.numero_suivi or f'expedition-{expedition.id}')
        reponse['Content-Disposition'] = (
            f'inline; filename="lettre-de-voiture-{nom}.pdf"')
        return reponse

    def get_queryset(self):
        qs = super().get_queryset()
        statut = statut_requete_ou_400(
            self.request, ExpeditionTransporteur.Statut.values)
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import creer_expedition_transporteur
        # CI #997 fuzz (2) : le corps est validé par le sérialiseur PUBLIÉ
        # (types, énumération, longueurs, FK bornées société) ; une unité ou
        # un transporteur inconnus (seule erreur) répondent 404.
        corps = _ExpeditionCorps404(data=corps_objet(request),
                                    context=self.get_serializer_context())
        corps.is_valid(raise_exception=True)
        valides = corps.validated_data
        try:
            expedition = creer_expedition_transporteur(
                company=request.user.company, unite=valides['unite_logistique'],
                provider_code=valides.get('transporteur_provider', 'aucun'),
                transporteur=valides.get('transporteur'),
                destination=valides.get('destination', ''),
                cout_reel=valides.get('cout_reel'))
        except ValueError as exc:
            # Unité encore en préparation : l'état s'oppose, corps conforme.
            raise ConflitEtat(str(exc))
        return Response(self.get_serializer(expedition).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=ExpeditionTransporteurSerializer)
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

    @extend_schema(responses=OBJET)
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

    @extend_schema(parameters=[P('unite_logistique', INT, True, 'Unité logistique (id)', mini=1, maxi=2147483647),
                               P('destination', STR)],
                   responses=corps('ExpeditionTarifsReponse', unite_logistique=serializers.IntegerField(),
                                   offres=serializers.ListField(child=serializers.DictField())))
    @action(detail=False, methods=['get'], url_path='tarifs')
    def tarifs(self, request):
        """NTWMS10 — comparatif coût/délai pour une unité logistique
        (``?unite_logistique=<id>&destination=``), AVANT de sceller le choix du
        transporteur. Sans connecteur configuré, renvoie le tarif de base du
        référentiel interne (repli gracieux). LECTURE SEULE."""
        from ..selectors import comparer_tarifs_transporteurs
        unite_id = entier_ou_400(
            request.query_params.get('unite_logistique'),
            'unite_logistique', None, 1, 2147483647)
        if unite_id is None:
            return Response(
                {'detail': 'Précisez l\'unité logistique.'},
                status=status.HTTP_400_BAD_REQUEST)
        unite = UniteLogistique.objects.filter(
            id=unite_id, company=request.user.company).first()
        if unite is None:
            return Response(
                {'detail': 'Unité logistique introuvable dans cette société.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response({
            'unite_logistique': unite.id,
            'offres': comparer_tarifs_transporteurs(
                unite, destination=request.query_params.get('destination')
                or ''),
        })


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR), P('produit', INT)]))
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

    parser_classes = [JSONParser]

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
        produit = entier_ou_400(
            params.get('produit'), 'produit', None, 1, 2147483647)
        if produit is not None:
            qs = qs.filter(produit_id=produit)
        return qs

    def perform_create(self, serializer):
        """Déclenche le rappel : auteur posé côté serveur + notification
        best-effort aux responsables (jamais bloquante).

        ASTK199 — le stock restant du lot (ou du produit) rappelé est MIS EN
        QUARANTAINE dans la même transaction : il sort du picking FEFO et
        sa sortie est refusée jusqu'à la clôture."""
        from django.db import transaction

        from ..services import appliquer_quarantaine_rappel, notifier_rappel
        with transaction.atomic():
            alerte = serializer.save(
                company=self.request.user.company,
                declenchee_par=self.request.user)
            appliquer_quarantaine_rappel(alerte, user=self.request.user)
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

    @extend_schema(request=None, responses=AlerteRappelSerializer)
    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôt le rappel (idempotent)."""
        from ..services import cloturer_alerte_rappel
        alerte = self.get_object()
        cloturer_alerte_rappel(alerte, user=request.user)
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

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        from ..services import assurer_plans_comptage_tournant
        if request.user.company_id:
            assurer_plans_comptage_tournant(request.user.company)
        return super().list(request, *args, **kwargs)

    @extend_schema(request=None, responses={201: OBJET})
    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """Génère MAINTENANT les sessions de comptage dues de cette société."""
        from ..services import generer_comptages_tournants
        resultat = generer_comptages_tournants(company=request.user.company)
        return Response(resultat, status=status.HTTP_201_CREATED)


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR), P('produit', ID_OU_VIDE), P('bin', ID_OU_VIDE)]))
class BlocageQualiteViewSet(CompanyScopedModelViewSet):
    """NTWMS31 — quarantaine qualité : ce qui est physiquement là mais
    qualitativement bloqué.

    La LEVÉE est réservée aux responsables/admins : c'est elle qui rend la
    marchandise à nouveau disponible pour une vague de prélèvement.
    """
    queryset = BlocageQualite.objects.select_related(
        'produit', 'bin', 'lot', 'reception', 'bloque_par', 'leve_par').all()
    serializer_class = BlocageQualiteSerializer
    ordering = ['-created_at']
    # CI #997 fuzz — JSON seul (corps lu à la main) : un multipart portait
    # ``reception=None`` en TEXTE, refusé alors que le schéma l'autorisait.
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        if self.action in ['lever', 'lever_quarantaine_bin']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        # CI #997 fuzz — filtres stricts (``?produit=null`` était ignoré).
        produit = id_requete_ou_400(self.request, 'produit')
        if produit is not None:
            qs = qs.filter(produit_id=produit)
        bin_id = id_requete_ou_400(self.request, 'bin')
        if bin_id is not None:
            qs = qs.filter(bin_id=bin_id)
        return qs

    def create(self, request, *args, **kwargs):
        """``{produit, quantite, bin?, lot?, reception?,
        motif?}`` — met une quantité en quarantaine (aucun mouvement de stock :
        la marchandise est là, elle n'est plus disponible)."""
        from ..services import mettre_en_quarantaine
        company = request.user.company
        # CI #997 fuzz — `motif: 5` faisait un 500 (.strip()), `quantite: "5"` passait.
        types_corps_ou_400(corps_objet(request), textes=('motif',), entiers=('quantite',), nuls=())
        # ASTK6 / CI #1004 — FK bornées société ; id étranger ou absent → 404
        # de même corps, comme le PATCH (IdInconnu404Mixin du sérialiseur).
        liens = _relations_scopees(
            self, request, ['produit', 'bin', 'lot', 'reception'], inconnu_en_404=True)
        try:
            blocage = mettre_en_quarantaine(
                company=company, produit=liens['produit'],
                quantite=request.data.get('quantite'), user=request.user,
                bin_quarantaine=liens['bin'],
                lot=liens['lot'],
                reception=liens['reception'],
                motif=request.data.get('motif') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(blocage).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=BlocageQualiteSerializer)
    @action(detail=True, methods=['post'], url_path='lever')
    def lever(self, request, pk=None):
        """Lève la quarantaine (idempotent) : la quantité redevient
        disponible."""
        from ..services import lever_quarantaine
        blocage = self.get_object()
        lever_quarantaine(blocage=blocage, user=request.user)
        blocage.refresh_from_db()
        return Response(self.get_serializer(blocage).data)

    @extend_schema(request=corps('QuarantaineLeverCasierCorps', bin=serializers.IntegerField(
        min_value=1, max_value=ID_MAX)), responses={
        200: inline_serializer('StockQuarantaineLeveeCasier', {
            'bin': serializers.IntegerField(),
            'blocages_leves': serializers.IntegerField(),
        }),
        400: inline_serializer('StockQuarantaineLeveeErreur', {
            'detail': serializers.CharField(),
        }),
    })
    @action(detail=False, methods=['post'], url_path='lever-quarantaine')
    def lever_quarantaine_bin(self, request):
        """Lève TOUS les blocages d'un casier de quarantaine
        (``{bin}``) — le geste du poste qualité, en un seul appel."""
        from ..services import lever_quarantaine_bin
        # CI #997 fuzz — corps non objet (``[null, null]``) : 400 déclaré, pas 500.
        donnees = request.data if hasattr(request.data, 'get') else {}
        bin_id = id_corps(donnees.get('bin'))
        if bin_id is None:
            return Response({'detail': 'Casier requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        leves = lever_quarantaine_bin(
            company=request.user.company, bin_id=bin_id,
            user=request.user)
        return Response({'bin': int(bin_id), 'blocages_leves': leves})


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR)]))
class PlanChargementViewSet(CompanyScopedModelViewSet):
    """NTWMS26 — plans de chargement camion et taux de remplissage.

    ``{id}/unites/`` ajoute une palette ET renvoie l'avertissement de
    dépassement ; ``{id}/verifier-capacite/`` recalcule le contrôle à tout
    moment (lecture seule).
    """
    queryset = PlanChargement.objects.select_related(
        'livraison', 'expedition', 'cree_par'
    ).prefetch_related('unites_logistiques').all()
    serializer_class = PlanChargementSerializer
    ordering = ['-created_at']

    parser_classes = [JSONParser]

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
        # ENF11 — corps validé par le sérialiseur strict (texte/booléens) :
        # une note entière répond 400 au lieu d'un 500 sur .strip().
        corps = self.get_serializer(data=request.data, partial=True)
        corps.is_valid(raise_exception=True)
        valides = corps.validated_data
        # ASTK6 / CI #1004 — FK bornées société ; id étranger ou absent → 404
        # de même corps, comme le PATCH (IdInconnu404Mixin du sérialiseur).
        liens = _relations_scopees(self, request, ['livraison', 'expedition'], inconnu_en_404=True)

        plan = creer_plan_chargement(
            company=company, user=request.user,
            livraison=liens['livraison'],
            expedition=liens['expedition'],
            capacite_kg=valides.get('capacite_kg') or None,
            capacite_m3=valides.get('capacite_m3') or None,
            note=valides.get('note') or '')
        return Response(self.get_serializer(plan).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses={
        200: inline_serializer('StockPlanChargementCapacite', {
            'plan': serializers.IntegerField(),
            'nb_unites': serializers.IntegerField(),
            'poids_kg': serializers.FloatField(),
            'volume_m3': serializers.FloatField(),
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

    @extend_schema(request=corps('PlanChargementAjoutCorps', unite_logistique=serializers.IntegerField()), responses={
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
        # ENF11 (nocturne 15/10) — forme du corps (400) ≠ unité inconnue de la
        # société (404) ≠ plan déjà chargé (409, état).
        brut = corps_objet(request).get('unite_logistique')
        if isinstance(brut, bool) or not isinstance(brut, int):
            raise ValidationError({'unite_logistique': ['Entier attendu.']})
        unite = UniteLogistique.objects.filter(
            id=id_corps(brut), company=request.user.company).first()
        if unite is None:
            return Response({'detail': 'Plan ou unité logistique introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if plan.statut == PlanChargement.Statut.CHARGE:
            return Response({'detail': 'Ce plan est déjà chargé : il ne bouge plus.'},
                            status=status.HTTP_409_CONFLICT)
        try:
            controle = ajouter_unite_plan_chargement(plan=plan, unite=unite)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(controle, status=status.HTTP_201_CREATED)


@extend_schema_view(list=extend_schema(parameters=[P('motif', STR), P('produit', INT)]))
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

    parser_classes = [JSONParser]

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
        produit = entier_ou_400(
            params.get('produit'), 'produit', None, 1, 2147483647)
        if produit is not None:
            qs = qs.filter(produit_id=produit)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import declarer_mouvement_rebut
        company = request.user.company
        # ASTK6 — produit et casier bornés société ; un id étranger → 400.
        liens = _relations_scopees(self, request, ['produit', 'bin'])
        # CI #997 fuzz — `note: 5` faisait un 500 (.strip()), `quantite: "5"` passait.
        types_corps_ou_400(request.data, textes=('note', 'motif'), entiers=('quantite',), nuls=())
        try:
            rebut = declarer_mouvement_rebut(
                company=company, user=request.user, produit=liens['produit'],
                quantite=request.data.get('quantite'),
                motif=request.data.get('motif'), bin_source=liens['bin'],
                note=request.data.get('note') or '')
        except EtatIncompatible as exc:
            # Stock insuffisant : l'état s'oppose, le corps était conforme (409).
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(rebut).data,
                        status=status.HTTP_201_CREATED)


@extend_schema_view(list=extend_schema(parameters=[
    P('statut', choix_ou_vide(RetourClient.Statut.values)), P('client', ID_OU_VIDE)]))
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

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['receptionner', 'inspecter']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = statut_requete_ou_400(self.request, RetourClient.Statut.values)
        if statut:
            qs = qs.filter(statut=statut)
        client = id_requete_ou_400(self.request, 'client')  # CI #997 : `null` -> 400
        if client is not None:
            qs = qs.filter(client_id=client)
        return qs

    @extend_schema(request=CORPS_RETOUR_CLIENT, responses={201: RetourClientSerializer})
    def create(self, request, *args, **kwargs):
        """``{client, chantier?, ticket?, motif?, lignes: [{produit,
        quantite, etat_constate?, bin?}]}`` — la référence est posée côté
        serveur."""
        from ..services import creer_retour_client
        company = request.user.company
        # CI #997 fuzz (4) — corps typé comme le schéma publié, AVANT toute
        # résolution : lignes objets (produit, quantité entiers, état connu).
        donnees = corps_objet(request)
        types_corps_ou_400(donnees, textes=('motif',), ids=('client', 'chantier', 'ticket'),
                           nuls=('chantier', 'ticket', 'motif'))
        lignes = _liste_d_objets_ou_400(
            donnees.get('lignes'), 'lignes', entiers=('quantite',), ids=('produit', 'bin'), nuls=('bin',))
        etats = LigneRetourClient.EtatConstate.values
        if any('etat_constate' in ligne and ligne['etat_constate'] not in etats for ligne in lignes):
            raise ValidationError({'lignes': ['État constaté inconnu (' + ', '.join(etats) + ').']})
        if '\x00' in (donnees.get('motif') or ''):
            raise ValidationError({'motif': ['Le caractère nul n’est pas autorisé.']})
        # ASTK6 — client, chantier et ticket bornés société ; id étranger ou
        # absent → 404 « objet inexistant » de même corps (les casiers des
        # lignes sont bornés par le service).
        liens = _relations_scopees(
            self, request, ['client', 'chantier', 'ticket'], inconnu_en_404=True)
        try:
            retour = creer_retour_client(
                company=company, user=request.user, client=liens['client'],
                chantier=liens['chantier'], ticket=liens['ticket'],
                motif=donnees.get('motif') or '',
                lignes=lignes)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(retour).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=RetourClientSerializer)
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

    @extend_schema(request=corps('RetourClientInspecterCorps',
                                 lignes=serializers.ListField(child=serializers.DictField())),
                   responses=RetourClientSerializer)
    @action(detail=True, methods=['post'], url_path='inspecter')
    def inspecter(self, request, pk=None):
        """Acte le contrôle qualité : ``{lignes: [{ligne, etat_constate,
        bin?, note?}]}``."""
        from ..services import inspecter_retour_client
        retour = self.get_object()
        if retour.statut not in (RetourClient.Statut.RECEPTIONNE,
                                 RetourClient.Statut.INSPECTE):
            # ENF11 (nocturne 15/10) — refus d'ÉTAT : 409, plus 400.
            return Response(
                {'detail': "Le retour doit être réceptionné avant d'être inspecté."},
                status=status.HTTP_409_CONFLICT)
        try:
            inspecter_retour_client(
                retour=retour, lignes=request.data.get('lignes'),
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        retour.refresh_from_db()
        return Response(self.get_serializer(retour).data)


@extend_schema_view(list=extend_schema(parameters=[P('tiers_nom', STR, pattern=MOTIF_SANS_NUL)]))
class PortailTiersTokenViewSet(CompanyScopedModelViewSet):
    """NTWMS20 — jetons du portail 3PL (lecture seule côté dépositaire).

    Administration RÉSERVÉE à l'admin : distribuer un lien de stock est une
    décision d'accès. Le jeton est généré côté serveur ; la révocation se fait
    en passant ``revoked=true``.
    """
    queryset = PortailTiersToken.objects.select_related('cree_par').all()
    serializer_class = PortailTiersTokenSerializer
    ordering = ['-created_at']

    parser_classes = [JSONParser]

    def get_permissions(self):
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        tiers = texte_sans_nul_ou_400(
            self.request.query_params.get('tiers_nom'), 'tiers_nom')
        if tiers:
            qs = qs.filter(tiers_nom__icontains=tiers)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company,
                        cree_par=self.request.user)


#: NTWMS18 — description OpenAPI d'une date de période tolérante.
_DATE_TOLEREE = 'Date AAAA-MM-JJ ; ignoré si illisible (période ouverte)'


def _date_param(valeur, nom='date', *, ignorer_illisible=False):
    """Convertit ``YYYY-MM-DD`` en date ; ``None`` si absente ; 400 nommant
    ``nom`` si illisible (ENF11 : plus d'entrée invalide ignorée) — sauf
    ``ignorer_illisible`` (tolérance DÉCLARÉE de NTWMS18 : ``None``)."""
    import datetime
    from rest_framework.exceptions import ValidationError

    valeur = (valeur or '').strip()
    if not valeur:
        return None
    try:
        return datetime.date.fromisoformat(valeur)
    except ValueError:
        if ignorer_illisible:
            return None
        raise ValidationError({nom: ['Date AAAA-MM-JJ attendue.']})


@extend_schema(parameters=[P('emplacement', INT, True, 'Emplacement (id)', mini=1, maxi=2147483647),
                           P('symbology', STR, False, 'Symbologie', ['qr', 'code128']),
                           P('sortie', STR, False, 'html ou pdf', ['html', 'pdf'])],
               responses={
    (200, 'application/pdf'): bytes, (200, 'text/html'): STR,
    400: inline_serializer('StockEtiquettesCasiersErreur', {
        # Deux corps servis : ``{detail}`` (emplacement absent) ou l'erreur de
        # validation DRF ``{emplacement: [...], error: {...}}`` (valeur hors
        # plage / illisible) — aucun des deux n'est systématique.
        'detail': serializers.CharField(required=False),
        'emplacement': serializers.ListField(
            child=serializers.CharField(), required=False),
        'error': serializers.DictField(required=False),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def casiers_etiquettes_pdf_view(request):
    """NTWMS32 — planche A4 d'étiquettes de CASIER, prête à coller.

    ``?emplacement=<id>`` (obligatoire) ; ``?symbology=qr|code128`` ;
    ``?sortie=html`` pour l'aperçu navigateur. Le code encodé est celui que le
    poste scanner NTWMS5 résout directement. Réutilise le moteur d'étiquettes
    existant (``labels.py``) — aucun second moteur d'impression.
    """
    from django.http import HttpResponse

    from .. import labels
    from ..models_wms import LignePicking

    emplacement_id = entier_ou_400(
        valeur_unique_ou_400(request, 'emplacement'), 'emplacement', None, 1,
        2147483647)
    # CI #997 fuzz (2) : symbologie / sortie hors énumération (ou répétées)
    # -> 400 ; elles retombaient en silence sur qr / pdf.
    symbology = choix_ou_400(valeur_unique_ou_400(request, 'symbology'),
                             'symbology', ('qr', 'code128')) or 'qr'
    sortie = choix_ou_400(valeur_unique_ou_400(request, 'sortie'),
                          'sortie', ('html', 'pdf'))
    if emplacement_id is None:
        return Response(
            {'detail': 'Précisez l\'emplacement dont vous voulez les '
                       'étiquettes de casier.'},
            status=status.HTTP_400_BAD_REQUEST)

    # Le modèle de casier est atteint par l'accesseur de NOTRE string-FK :
    # aucun import de `apps.installations.models`.
    modele_bin = LignePicking._meta.get_field('bin').related_model
    casiers = (modele_bin.objects
               .filter(company=request.user.company,
                       emplacement_id=emplacement_id, archived=False)
               .select_related('emplacement')
               .order_by('ordre', 'code'))
    if not casiers:
        return Response(
            {'detail': 'Aucun casier à imprimer pour cet emplacement.'},
            status=status.HTTP_404_NOT_FOUND)

    html = labels.render_etiquettes_casiers_html([{
        'code': casier.code,
        'zone': casier.zone or '',
        'allee': casier.allee or '',
        'casier': casier.casier or '',
        'emplacement': (casier.emplacement.nom
                        if casier.emplacement_id else ''),
    } for casier in casiers], symbology=symbology)
    if sortie == 'html':
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    from apps.ventes.utils.pdf import _html_to_pdf
    reponse = HttpResponse(_html_to_pdf(html), content_type='application/pdf')
    reponse['Content-Disposition'] = (
        f'inline; filename="etiquettes-casiers-{emplacement_id}.pdf"')
    return reponse


@extend_schema(parameters=[P('debut', DATE_OU_VIDE), P('fin', DATE_OU_VIDE)], responses={
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

    fin = _date_param(request.query_params.get('fin'), 'fin') or timezone.localdate()
    debut = (_date_param(request.query_params.get('debut'), 'debut')
             or fin - datetime.timedelta(days=365))
    return Response({
        'suggestions': suggerer_reslotting(
            request.user.company, depuis=debut, jusqu_a=fin),
    })


@extend_schema(parameters=[P('debut', DATE_OU_VIDE), P('fin', DATE_OU_VIDE)], responses={
    200: inline_serializer('StockEntrepotPertes', {
        'debut': serializers.CharField(allow_null=True),
        'fin': serializers.CharField(allow_null=True),
        'total_valeur': serializers.FloatField(),
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

    debut = _date_param(request.query_params.get('debut'), 'debut')
    fin = _date_param(request.query_params.get('fin'), 'fin')
    rapport = rapport_pertes_entrepot(
        request.user.company, debut=debut, fin=fin)
    # ERR-STK-PRIX-ACHAT-SUITE — valeurs au coût d'achat : prix_achat_voir ;
    # sans lui, les quantités restent (l'écran Picking n'affiche qu'elles).
    from ..permissions import PeutVoirPrixAchat
    if not PeutVoirPrixAchat().has_permission(request, None):
        rapport.pop('total_valeur', None)
        for ligne in rapport.get('par_motif', []):
            ligne.pop('valeur', None)
    rapport.update({
        'debut': debut.isoformat() if debut else None,
        'fin': fin.isoformat() if fin else None,
    })
    return Response(rapport)


@extend_schema(parameters=[P('debut', STR, False, _DATE_TOLEREE), P('fin', STR, False, _DATE_TOLEREE)], responses={
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

    # NTWMS18 — une date illisible est IGNORÉE (période ouverte), jamais un
    # 400 : tolérance déclarée dans l'OpenAPI (``_DATE_TOLEREE``).
    debut = _date_param(request.query_params.get('debut'), 'debut',
                        ignorer_illisible=True)
    fin = _date_param(request.query_params.get('fin'), 'fin',
                      ignorer_illisible=True)
    return Response({
        'debut': debut.isoformat() if debut else None,
        'fin': fin.isoformat() if fin else None,
        'operateurs': productivite_operateur(
            request.user.company, debut=debut, fin=fin),
    })
