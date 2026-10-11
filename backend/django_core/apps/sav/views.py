from datetime import date as _date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import filters, serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import (
    APIException, NotFound, ValidationError,
)
from rest_framework.response import Response

from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.permissions import declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference

from . import activity
from .models import (
    Equipement, Ticket, TicketActivity, PieceConsommee,
    SavSlaSettings, MaintenanceChecklistTemplate, TicketChecklistItem,
    WarrantyClaim, KbArticle, AlarmeOnduleur,
    CauseDefaillance, RemedeDefaillance, EquipementDowntime,
    ReleveCompteurEquipement, ReponseType, CompatibilitePiece, PieceRetiree,
    CategorieTicket, EquipeMaintenance, CategorieEquipement,
    TicketActiviteAFaire, TicketFollower,
    WorksheetMaintenanceModele, TicketWorksheet, Probleme, ProblemeIncident,
)
from .services import add_months
from .pdf import fiche_synthese_ticket_pdf, rapport_intervention_pdf
from .serializers import (
    EquipementSerializer, TicketSerializer, TicketActivitySerializer,
    PieceConsommeeSerializer, PieceRetireeSerializer, PretEquipementSerializer,
    EXPIRING_SOON_DAYS,
    SavSlaSettingsSerializer,
    MaintenanceChecklistTemplateSerializer, TicketChecklistItemSerializer,
    WarrantyClaimSerializer,
    KbArticleSerializer,
    AlarmeOnduleurSerializer,
    CauseDefaillanceSerializer, RemedeDefaillanceSerializer,
    EquipementDowntimeSerializer,
    ReleveCompteurEquipementSerializer,
    ReponseTypeSerializer,
    CompatibilitePieceSerializer,
    CategorieTicketSerializer,
    EquipeMaintenanceSerializer,
    CategorieEquipementSerializer,
    TicketActiviteAFaireSerializer, ProblemeSerializer,
    WorksheetMaintenanceModeleSerializer, TicketWorksheetSerializer,
)


def _qr_data_uri(target):
    """NTMOB23 — encode ``target`` en QR PNG (data-URI), ou ``None``.

    Même patron que le QR de signalement QHSE (``apps.qhse.services``) : la lib
    ``qrcode`` est DÉJÀ épinglée pour la cérémonie de signature devis — aucune
    nouvelle dépendance. Absente ou en échec → ``None``, jamais une exception :
    le partage dégrade sur le lien en clair."""
    try:
        import base64
        import io as _io

        import qrcode
    except ImportError:  # pragma: no cover - défensif
        return None
    try:
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8, border=2)
        qr.add_data(target)
        qr.make(fit=True)
        buf = _io.BytesIO()
        qr.make_image().save(buf, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(
            buf.getvalue()).decode()
    except Exception:  # pragma: no cover - défensif
        return None


READ_ACTIONS = ['list', 'retrieve']

# ENF9 — petits schémas inline partagés par les @extend_schema des actions.
_CharF = drf_serializers.CharField


def _sch(name, fields, extra=False, null=False, many=False):
    """Sérialiseur inline pour la documentation OpenAPI (``extra`` : objet
    à propriétés libres, ``fields`` ne liste alors que le minimum)."""
    return inline_serializer(name, fields, many=many, allow_null=null)


_CreerLeadReponse = _sch('SavCreerLeadReponse', {
    'lead_id': drf_serializers.IntegerField(),
    'created': drf_serializers.BooleanField(),
})

_RegistreGaranties = _sch('SavRegistreGaranties', {
    'today': drf_serializers.DateField(),
    'expiring_soon_days': drf_serializers.IntegerField(),
    'parcs': _sch('SavRegistreParc', {
        'installation': drf_serializers.IntegerField(allow_null=True),
        'installation_nom': _CharF(allow_blank=True),
        'client_nom': _CharF(allow_blank=True),
        'prochaine_echeance': drf_serializers.DateField(allow_null=True),
        'items': drf_serializers.ListField(child=drf_serializers.DictField()),
        'alertes': drf_serializers.DictField(
            child=drf_serializers.IntegerField()),
    }, many=True),
    'totaux': drf_serializers.DictField(child=drf_serializers.IntegerField()),
})

WRITE_ACTIONS = ['create', 'update', 'partial_update']


@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('produit', OpenApiTypes.INT, required=False),
        OpenApiParameter('marque', OpenApiTypes.STR, required=False),
        OpenApiParameter('installation', OpenApiTypes.INT, required=False),
        OpenApiParameter('client', OpenApiTypes.INT, required=False),
        OpenApiParameter('statut', OpenApiTypes.STR, required=False),
        OpenApiParameter('garantie', OpenApiTypes.STR, required=False, enum=['non_renseignee', 'hors_garantie', 'expire_bientot', 'sous_garantie', 'legale_uniquement']),
        OpenApiParameter('categorie', OpenApiTypes.INT, required=False),
        OpenApiParameter('rebut', OpenApiTypes.STR, required=False, enum=['only', 'tous']),
    ]))
class EquipementViewSet(CompanyScopedModelViewSet):
    """Parc d'équipements (n° de série + horloges de garantie). Tout est scopé
    à la société ; les dates de fin de garantie sont CALCULÉES côté serveur."""
    queryset = Equipement.objects.select_related(
        'produit', 'installation', 'installation__client', 'client_vente',
        'categorie', 'created_by', 'remplace_par_ticket',
    ).all()
    serializer_class = EquipementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_serie', 'produit__nom', 'produit__marque']
    ordering_fields = [
        'date_fin_garantie', 'date_pose', 'date_creation', 'numero_serie',
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # APRF30 — compteurs de tickets annotés (une seule requête pour la
        # page) ; le serializer les lit et retombe sur ``.count()`` hors liste.
        if self.action == 'list':
            from datetime import timedelta
            depuis = timezone.localdate() - timedelta(days=365)
            qs = qs.annotate(
                nb_tickets_ouverts_annote=Count(
                    'tickets', distinct=True,
                    filter=Q(tickets__statut__in=Ticket.OPEN_STATUTS,
                             tickets__annule=False)),
                nb_tickets_12m_annote=Count(
                    'tickets', distinct=True,
                    filter=Q(tickets__type=Ticket.Type.CORRECTIF,
                             tickets__date_creation__date__gte=depuis)),
            )
        # Portée de visibilité (Feature F) — équipements créés par soi / l'équipe.
        from authentication.scoping import scope_queryset
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        params = self.request.query_params
        produit = params.get('produit')
        marque = params.get('marque')
        installation = params.get('installation')
        client = params.get('client')
        statut = params.get('statut')
        garantie = params.get('garantie')
        categorie = params.get('categorie')
        if produit:
            qs = qs.filter(produit_id=produit)
        if marque:
            qs = qs.filter(produit__marque__icontains=marque)
        if installation:
            qs = qs.filter(installation_id=installation)
        if categorie:
            qs = qs.filter(categorie_id=categorie)
        # ZMFG12 — parc actif par défaut : exclut les équipements au rebut.
        # ?rebut=tous pour tout voir ; ?rebut=only pour ne voir que le rebut.
        rebut = params.get('rebut')
        if self.action == 'list':
            if rebut == 'only':
                qs = qs.filter(mis_au_rebut=True)
            elif rebut != 'tous':
                qs = qs.filter(mis_au_rebut=False)
        if client:
            # XPOS9 — un équipement vendu au comptoir (sans chantier) est
            # rattaché via `client_vente` plutôt que `installation__client`.
            qs = qs.filter(
                Q(installation__client_id=client)
                | Q(client_vente_id=client))
        if statut:
            qs = qs.filter(statut=statut)
        if garantie:
            today = timezone.localdate()
            soon = today + timedelta(days=EXPIRING_SOON_DAYS)
            if garantie == 'non_renseignee':
                qs = qs.filter(date_fin_garantie__isnull=True)
            elif garantie == 'hors_garantie':
                qs = qs.filter(date_fin_garantie__lt=today)
            elif garantie == 'expire_bientot':
                qs = qs.filter(
                    date_fin_garantie__gte=today, date_fin_garantie__lte=soon)
            elif garantie == 'sous_garantie':
                qs = qs.filter(date_fin_garantie__gt=soon)
            elif garantie == 'legale_uniquement':
                # XSAV13 — SEULE la garantie légale (loi 31-08, 12 mois à
                # compter de la pose) couvre encore l'équipement : commerciale
                # absente/expirée, mais date_pose < 12 mois (donc légale
                # toujours active). Seuil calculé via le même helper de date
                # (add_months, -12) que les autres horloges de garantie.
                seuil_legal = add_months(today, -Equipement.GARANTIE_LEGALE_MOIS)
                qs = qs.filter(
                    date_pose__isnull=False, date_pose__gt=seuil_legal,
                ).filter(
                    Q(date_fin_garantie__isnull=True)
                    | Q(date_fin_garantie__lt=today))
        return qs

    def get_permissions(self):
        if self.action == 'fiabilite':
            # XSAV15 — MTBF/MTTR restent visibles à tout rôle authentifié de
            # la société ; le coût cumulé (sensible) est gated en interne sur
            # `prix_achat_voir` (voir plus bas), jamais au niveau de l'action.
            return [IsAnyRole()]
        if self.action in READ_ACTIONS + [
                # NTMOB23 — QR de partage : une LECTURE (le jeton public
                # existait déjà pour les étiquettes imprimées).
                'partage_qr',
                'etiquettes', 'registre_garanties',
                'estimations_maintenance', 'disponibilite']:
            return [HasPermissionOrLegacy('equipement_voir')()]
        elif self.action in WRITE_ACTIONS + [
                # ZMFG12 — mise au rebut / réactivation, réservé responsable/
                # admin (spec : action motivée, pas une simple écriture de
                # champ).
                'mettre_au_rebut', 'reactiver_rebut']:
            if self.action in ('mettre_au_rebut', 'reactiver_rebut'):
                return [IsResponsableOrAdmin()]
            return [HasPermissionOrLegacy('equipement_gerer')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        company = self.request.user.company
        installation = serializer.validated_data.get('installation')
        produit = serializer.validated_data.get('produit')
        ticket = serializer.validated_data.get('remplace_par_ticket')
        categorie = serializer.validated_data.get('categorie')
        if installation is not None and installation.company_id != company.id:
            raise ValidationError({'installation': 'Chantier inconnu.'})
        if produit is not None and produit.company_id not in (company.id, None):
            raise ValidationError({'produit': 'Produit inconnu.'})
        if ticket is not None and ticket.company_id != company.id:
            raise ValidationError({'remplace_par_ticket': 'Ticket inconnu.'})
        if categorie is not None and categorie.company_id != company.id:
            raise ValidationError({'categorie': 'Catégorie inconnue.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        try:
            serializer.save(company=company, created_by=self.request.user)
        except IntegrityError:
            # L636 — filet de course si la contrainte d'unicité DB se déclenche
            # entre la validation serializer et l'écriture.
            raise ValidationError(
                {'numero_serie':
                 'Ce numéro de série existe déjà dans votre société.'})
        # Calcul des horloges de garantie après la pose des FK.
        inst = serializer.instance
        inst.recompute_garanties()
        # FG85 — jeton QR EQUIP:<id> posé à la création.
        inst.equipement_token = f'EQUIP:{inst.pk}'
        inst.save(update_fields=[
            'date_fin_garantie', 'date_fin_garantie_production',
            'equipement_token'])

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        # ASAV7 — horloges figées : on ne recalcule la garantie que si la
        # pose ou le produit CHANGENT réellement, et jamais au rebut (sinon
        # éditer une note réalignait la fin sur la durée COURANTE du
        # catalogue et deux jumeaux divergeaient).
        avant = serializer.instance
        pose_avant, produit_avant = avant.date_pose, avant.produit_id
        try:
            super().perform_update(serializer)
        except IntegrityError:
            raise ValidationError(
                {'numero_serie':
                 'Ce numéro de série existe déjà dans votre société.'})
        inst = serializer.instance
        update_fields = []
        if not inst.mis_au_rebut and (
                inst.date_pose != pose_avant
                or inst.produit_id != produit_avant):
            inst.recompute_garanties()
            update_fields = [
                'date_fin_garantie', 'date_fin_garantie_production']
        # FG85 — assure que le jeton est toujours présent (migration d'équipements existants).
        token = f'EQUIP:{inst.pk}'
        if inst.equipement_token != token:
            inst.equipement_token = token
            update_fields.append('equipement_token')
        if update_fields:
            inst.save(update_fields=update_fields)

    @extend_schema(
        request=_sch('SavMettreAuRebutRequete', {'motif': _CharF()}),
        responses=EquipementSerializer)
    @action(detail=True, methods=['post'], url_path='mettre-au-rebut',
            permission_classes=[IsResponsableOrAdmin])
    def mettre_au_rebut(self, request, pk=None):
        """ZMFG12 — Mise au rebut motivée (motif obligatoire, réservé
        responsable/admin). Fige les horloges de garantie (aucun recalcul
        futur) et exclut l'équipement du parc actif ET des générations de
        visites préventives (XSAV17 — voir `enregistrer_releve_compteur`)."""
        equipement = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'motif': 'Le motif de mise au rebut est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not equipement.mis_au_rebut:
            equipement.mis_au_rebut = True
            equipement.date_rebut = timezone.localdate()
            equipement.motif_rebut = motif
            equipement.save(update_fields=[
                'mis_au_rebut', 'date_rebut', 'motif_rebut'])
        return Response(
            EquipementSerializer(
                equipement, context={'request': request}).data)

    @extend_schema(request=None, responses=EquipementSerializer)
    @action(detail=True, methods=['post'], url_path='reactiver-rebut',
            permission_classes=[IsResponsableOrAdmin])
    def reactiver_rebut(self, request, pk=None):
        """ZMFG12 — Réactivation d'un équipement au rebut (retour au parc
        actif et aux générations de visites préventives)."""
        equipement = self.get_object()
        if equipement.mis_au_rebut:
            equipement.mis_au_rebut = False
            equipement.date_rebut = None
            equipement.motif_rebut = ''
            equipement.save(update_fields=[
                'mis_au_rebut', 'date_rebut', 'motif_rebut'])
        return Response(
            EquipementSerializer(
                equipement, context={'request': request}).data)

    @extend_schema(responses=_sch('SavPartageQrReponse', {
        'url': _CharF(), 'qr': _CharF(allow_null=True)}))
    @action(detail=True, methods=['get'], url_path='partage-qr',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def partage_qr(self, request, pk=None):
        """NTMOB23 — QR de partage rapide d'une fiche équipement.

        Renvoie le lien de partage TOKENISÉ DÉJÀ EXISTANT (``/e/<public_token>``,
        XSAV19 — le même que les étiquettes imprimées, jamais un second canal)
        plus son encodage QR en data-URI PNG, pour qu'un technicien puisse le
        faire scanner à un collègue sur site sans taper d'URL. Aucune nouvelle
        infrastructure de partage : ni modèle, ni jeton, ni route publique.

        La lib ``qrcode`` est déjà épinglée (cérémonie de signature devis,
        QR QHSE) ; absente, on dégrade proprement en renvoyant ``qr`` à
        ``null`` — le lien reste affichable et copiable."""
        equipement = self.get_object()
        url = request.build_absolute_uri(
            f'/e/{equipement.ensure_public_token()}')
        return Response({'url': url, 'qr': _qr_data_uri(url)})

    @extend_schema(
        parameters=[
            OpenApiParameter('ids', OpenApiTypes.STR, required=False,
                             description='Identifiants séparés par des virgules.'),
            OpenApiParameter('public', OpenApiTypes.STR, required=False,
                             enum=['0', '1', 'true', 'false'],
                             description="'1'/'true' : QR de l'URL publique."),
            OpenApiParameter('symbology', OpenApiTypes.STR, required=False,
                             enum=['qr', 'code128']),
        ],
        responses={(200, 'text/html'): OpenApiTypes.STR})
    @action(detail=False, methods=['get'], url_path='etiquettes',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def etiquettes(self, request):
        """FG85 — Étiquettes QR pour les équipements du parc.

        ?ids=1,2,3 pour un sous-ensemble ; sans filtre = tous les équipements
        de la société (limité à 200 pour WeasyPrint). Symbologie : qr (défaut)
        ou code128. Renvoie HTML prêt pour impression / conversion PDF."""
        from apps.stock.labels import render_labels_html
        from django.http import HttpResponse as HR

        qs = self.get_queryset()
        ids_param = request.query_params.get('ids', '')
        if ids_param:
            try:
                ids = [int(i) for i in ids_param.split(',') if i.strip()]
            except ValueError:
                return Response({'detail': 'ids invalides.'}, status=400)
            qs = qs.filter(pk__in=ids)
        qs = qs[:200]

        # XSAV19 — ?public=1 encode l'URL publique « Signaler un problème »
        # (/e/<public_token>) au lieu du jeton interne EQUIP:<id> (scan
        # interne inchangé par défaut). Le jeton public est généré lazily.
        public = request.query_params.get('public') in ('1', 'true')

        # AGR621 — étiquette PUBLIQUE (coffret d'un forage isolé) : pied
        # « SAV : <téléphone société> · Chantier <référence> », chaque partie
        # omise si vide. Jamais un délai d'intervention (aucun engagement
        # décidé). L'étiquette interne reste octet-identique.
        telephone = ''
        if public:
            from apps.parametres.models import CompanyProfile
            try:
                profil = CompanyProfile.get(company=request.user.company)
                telephone = (getattr(profil, 'telephone', '') or '').strip()
            except Exception:
                telephone = ''

        items = []
        for eq in qs:
            if public:
                token = request.build_absolute_uri(
                    f'/e/{eq.ensure_public_token()}')
            else:
                # Assure le jeton présent (rétro-compat équipements sans token).
                token = eq.equipement_token or f'EQUIP:{eq.pk}'
            titre = eq.produit.nom if eq.produit_id else '—'
            sous_titre = eq.numero_serie or '(sans série)'
            item = {'token': token, 'titre': titre, 'sous_titre': sous_titre}
            if public:
                parties = []
                if telephone:
                    parties.append(f'SAV : {telephone}')
                reference = (getattr(eq.installation, 'reference', '') or ''
                             if eq.installation_id else '')
                if reference:
                    parties.append(f'Chantier {reference}')
                if parties:
                    item['pied'] = ' · '.join(parties)
            items.append(item)

        if not items:
            return Response({'detail': 'Aucun équipement.'}, status=404)

        symbology = request.query_params.get('symbology', 'qr')
        html = render_labels_html(items, symbology=symbology)
        return HR(html, content_type='text/html; charset=utf-8')

    @extend_schema(
        parameters=[OpenApiParameter(
            'jours', OpenApiTypes.INT, required=False,
            description="Seuil « expire bientôt » en jours.")],
        responses=_RegistreGaranties)
    @action(detail=False, methods=['get'], url_path='registre-garanties',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def registre_garanties(self, request):
        """FG290 — Registre des garanties matériel & échéancier PAR PARC.

        Renvoie le parc regroupé par installation, chaque unité avec ses dates
        de fin de garantie (matériel + production, CALCULÉES) et un statut
        d'alerte (expirée / expire bientôt / sous garantie / non renseignée),
        trié par échéance la plus proche. Respecte le scoping société +
        visibilité et TOUS les filtres de `get_queryset` (produit, marque,
        installation, client, statut, garantie). Le seuil « expire bientôt »
        est paramétrable via ?jours=N (défaut EXPIRING_SOON_DAYS)."""
        from .selectors import warranty_registry
        try:
            jours = int(request.query_params.get('jours', EXPIRING_SOON_DAYS))
        except (TypeError, ValueError):
            jours = EXPIRING_SOON_DAYS
        jours = max(0, jours)
        data = warranty_registry(self.get_queryset(), expiring_soon_days=jours)
        return Response(data)

    @extend_schema(responses=_sch('SavFiabiliteEquipement', {}, extra=True))
    @action(detail=True, methods=['get'], url_path='fiabilite',
            permission_classes=[IsAnyRole])
    def fiabilite(self, request, pk=None):
        """XSAV15 — MTBF / MTTR / coût cumulé de CET équipement.

        Le coût cumulé (Ticket.cout + pièces valorisées prix d'achat) et
        l'indicateur réparer-vs-remplacer ne sont inclus QUE si l'utilisateur
        porte la permission `prix_achat_voir` — jamais exposés autrement
        (admin-only, jamais client-facing ni dans un PDF). Gated en interne
        (et non au niveau de l'action) via `HasPermissionOrLegacy` pour que
        les comptes légacy SANS rôle fin suivent le même repli que
        `IsResponsableOrAdmin` (responsable/admin uniquement) plutôt que le
        repli toujours-vrai de `can_view_buy_prices` — trop large ici."""
        from .selectors import fiabilite_equipement
        equipement = self.get_object()
        include_couts = HasPermissionOrLegacy('prix_achat_voir')().has_permission(
            request, self)
        data = fiabilite_equipement(equipement, include_couts=include_couts)
        return Response(data)

    @extend_schema(responses=_sch('SavEstimationsMaintenance', {}, extra=True))
    @action(detail=True, methods=['get'], url_path='estimations-maintenance',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def estimations_maintenance(self, request, pk=None):
        """ZMFG11 — Prochaine défaillance estimée (MTBF) + prochain entretien
        dû (contrat de maintenance ou seuil compteur) pour CET équipement."""
        from .selectors import estimations_maintenance as _estimations_maintenance

        equipement = self.get_object()
        data = _estimations_maintenance(equipement)
        # Le sélecteur renvoie des `date` Python brutes (utile aux appelants
        # internes, ex. comparaison directe à `contrat.prochaine_visite()`) —
        # la frontière API suit ici la même convention que le reste du
        # module (`.isoformat()` explicite) plutôt que de compter sur
        # `Response.data` pour les convertir (il ne le fait pas).
        for champ in ('prochaine_defaillance_estimee', 'prochain_entretien_du'):
            if data.get(champ) is not None:
                data[champ] = data[champ].isoformat()
        return Response(data)

    @extend_schema(
        methods=['GET'], request=None,
        responses=EquipementDowntimeSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=_sch('SavDowntimeRequete', {
            'debut': drf_serializers.DateTimeField(required=False),
            'ticket': drf_serializers.IntegerField(required=False),
            'motif': _CharF(required=False, allow_blank=True),
        }),
        responses={201: EquipementDowntimeSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='downtime',
            permission_classes=[IsAdminRole])
    def downtime(self, request, pk=None):
        """XSAV16 — Journal d'immobilisation de cet équipement.

        GET : liste les fenêtres (en cours + closes). POST : ouvre une
        nouvelle fenêtre (body : ``debut`` ISO8601 optionnel — défaut
        maintenant, ``ticket`` id optionnel, ``motif`` optionnel). Refuse tout
        chevauchement avec une fenêtre existante (400 explicite, jamais une
        seconde fenêtre concurrente créée par erreur)."""
        equipement = self.get_object()
        if request.method == 'GET':
            qs = equipement.downtimes.select_related('ticket')
            return Response(EquipementDowntimeSerializer(qs, many=True).data)

        from .services import DowntimeOverlapError, ouvrir_downtime

        debut_raw = request.data.get('debut')
        if debut_raw:
            from django.utils.dateparse import parse_datetime
            debut = parse_datetime(debut_raw)
            if debut is None:
                return Response({'detail': 'Date invalide.'}, status=400)
        else:
            debut = timezone.now()

        ticket = None
        ticket_id = request.data.get('ticket')
        if ticket_id:
            ticket = Ticket.objects.filter(
                id=ticket_id, company=equipement.company_id).first()
            if ticket is None:
                return Response({'detail': 'Ticket inconnu.'}, status=400)

        try:
            dt = ouvrir_downtime(
                company=equipement.company, equipement=equipement,
                debut=debut, ticket=ticket,
                motif=(request.data.get('motif') or '').strip(),
                created_by=request.user)
        except DowntimeOverlapError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(
            EquipementDowntimeSerializer(dt).data, status=201)

    @extend_schema(
        request=_sch('SavCloturerDowntimeRequete', {
            'fin': drf_serializers.DateTimeField(required=False)}),
        responses=EquipementDowntimeSerializer)
    @action(detail=True, methods=['post'],
            url_path=r'downtime/(?P<downtime_id>[^/.]+)/cloturer',
            permission_classes=[IsAdminRole])
    def cloturer_downtime(self, request, pk=None, downtime_id=None):
        """XSAV16 — Ferme une fenêtre d'immobilisation en cours (idempotent)."""
        equipement = self.get_object()
        try:
            dt = equipement.downtimes.get(pk=downtime_id)
        except (EquipementDowntime.DoesNotExist, ValueError):
            return Response({'detail': 'Immobilisation introuvable.'}, status=404)
        fin_raw = request.data.get('fin')
        fin = None
        if fin_raw:
            from django.utils.dateparse import parse_datetime
            fin = parse_datetime(fin_raw)
        dt.clore(fin=fin)
        return Response(EquipementDowntimeSerializer(dt).data)

    @extend_schema(
        parameters=[
            OpenApiParameter('debut', OpenApiTypes.DATE, required=False),
            OpenApiParameter('fin', OpenApiTypes.DATE, required=False),
        ],
        responses=_sch('SavDisponibiliteEquipement', {}, extra=True))
    @action(detail=True, methods=['get'], url_path='disponibilite',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def disponibilite(self, request, pk=None):
        """XSAV16 — Disponibilité % de cet équipement sur une période.

        ``?debut=AAAA-MM-JJ&fin=AAAA-MM-JJ`` (défaut : les 30 derniers jours).
        """
        from datetime import datetime as _dt, timedelta as _td
        from .services import disponibilite_equipement

        equipement = self.get_object()

        def _parse_date(name, default):
            raw = (request.query_params.get(name) or '').strip()
            if not raw:
                return default
            try:
                from datetime import date as _date
                d = _date.fromisoformat(raw)
                return timezone.make_aware(_dt(d.year, d.month, d.day))
            except ValueError:
                return default

        fin_periode = _parse_date('fin', timezone.now())
        debut_periode = _parse_date(
            'debut', fin_periode - _td(days=30))

        data = disponibilite_equipement(
            equipement, debut_periode=debut_periode, fin_periode=fin_periode)
        return Response(data)

    @extend_schema(
        methods=['GET'], request=None,
        responses=ReleveCompteurEquipementSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=_sch('SavReleveCompteurRequete', {
            'type': _CharF(),
            'valeur': drf_serializers.DecimalField(
                max_digits=14, decimal_places=2),
            'date': drf_serializers.DateField(required=False),
        }),
        responses={201: _sch('SavReleveCompteurReponse', {
            'ticket_genere': _sch('SavReleveTicketGenere', {
                'id': drf_serializers.IntegerField(),
                'reference': _CharF()}, null=True)}, extra=True)})
    @action(detail=True, methods=['get', 'post'], url_path='releves-compteur',
            permission_classes=[IsAdminRole])
    def releves_compteur(self, request, pk=None):
        """XSAV17 — Relevés compteur (heures/kWh) de cet équipement.

        GET : historique des relevés (plus récent d'abord). POST : enregistre
        un relevé (body : ``type`` heures|kwh, ``valeur``, ``date`` AAAA-MM-JJ
        optionnel — défaut aujourd'hui). Au franchissement du seuil
        (`entretien_toutes_les_heures`), génère idempotemment UN ticket
        préventif — renvoyé dans la réponse (``ticket_genere``)."""
        equipement = self.get_object()
        if request.method == 'GET':
            qs = equipement.releves_compteur.all()
            return Response(ReleveCompteurEquipementSerializer(qs, many=True).data)

        from datetime import date as _date
        from .services import ReleveDecroissantError, enregistrer_releve_compteur

        type_releve = request.data.get('type')
        # AGR615 — le compteur d'eau d'une pompe (m³) est accepté.
        if type_releve not in (
                ReleveCompteurEquipement.Type.HEURES,
                ReleveCompteurEquipement.Type.KWH,
                ReleveCompteurEquipement.Type.M3):
            return Response(
                {'detail': 'type invalide (heures|kwh|m3).'}, status=400)
        try:
            valeur = Decimal(str(request.data.get('valeur')))
        except (InvalidOperation, TypeError):
            return Response({'detail': 'valeur invalide.'}, status=400)

        date_raw = (request.data.get('date') or '').strip()
        try:
            date_releve = _date.fromisoformat(date_raw) if date_raw else timezone.localdate()
        except ValueError:
            return Response({'detail': 'date invalide.'}, status=400)

        try:
            releve, ticket = enregistrer_releve_compteur(
                company=equipement.company, equipement=equipement,
                type_releve=type_releve, valeur=valeur,
                date_releve=date_releve, created_by=request.user)
        except ReleveDecroissantError as exc:
            return Response({'detail': str(exc)}, status=400)

        payload = ReleveCompteurEquipementSerializer(releve).data
        payload['ticket_genere'] = (
            {'id': ticket.id, 'reference': ticket.reference}
            if ticket is not None else None)
        return Response(payload, status=201)


def _tickets_visibles(request):
    """ASAV25 — tickets de la société VISIBLES par l'utilisateur : la même
    portée (``scope_queryset`` : créés par soi / dont on est technicien /
    équipe ; « tous » inchangé) que la liste ``TicketViewSet``. Toute action
    qui reçoit des ids de tickets dans son corps les résout ICI — jamais par
    ``Ticket.objects.filter(company=…)`` nu."""
    from authentication.scoping import scope_queryset
    return scope_queryset(
        Ticket.objects.filter(company=request.user.company), request.user,
        ['technicien_responsable', 'created_by'])


def _ticket_visible_du_corps(request, brut, champ='ticket'):
    """ASAV25 — ticket du corps : inconnu de la société → 400 sous ``champ``
    (inchangé) ; de la société mais HORS portée → 404 (introuvable)."""
    try:
        ticket_id = int(brut)
    except (TypeError, ValueError):
        raise ValidationError({champ: 'Ticket inconnu.'})
    ticket = _tickets_visibles(request).filter(pk=ticket_id).first()
    if ticket is not None:
        return ticket
    if Ticket.objects.filter(
            pk=ticket_id, company=request.user.company).exists():
        raise NotFound({champ: 'Ticket introuvable.'})
    raise ValidationError({champ: 'Ticket inconnu.'})


class _ProduitNeufInconnu(Exception):
    """ASAV9 — ``produit_neuf`` introuvable (annule le remplacement)."""


class TicketEnDoubleError(APIException):
    """ASAV23 — création d'un ticket identique dans la fenêtre anti-doublon."""
    status_code = 409
    default_detail = 'Ticket en double.'
    default_code = 'ticket_en_double'


@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('statut', OpenApiTypes.STR, required=False),
        OpenApiParameter('type', OpenApiTypes.STR, required=False),
        OpenApiParameter('priorite', OpenApiTypes.STR, required=False),
        OpenApiParameter('technicien', OpenApiTypes.INT, required=False),
        OpenApiParameter('client', OpenApiTypes.INT, required=False),
        OpenApiParameter('installation', OpenApiTypes.INT, required=False),
        OpenApiParameter('equipement', OpenApiTypes.INT, required=False),
        OpenApiParameter('categorie', OpenApiTypes.INT, required=False),
        OpenApiParameter('equipe', OpenApiTypes.INT, required=False),
        OpenApiParameter('ouvert', OpenApiTypes.STR, required=False, enum=['tous']),
        OpenApiParameter('annule', OpenApiTypes.STR, required=False, enum=['only', 'sans']),
    ]))
class TicketViewSet(CompanyScopedModelViewSet):
    """Tickets SAV + historique « chatter ». Cycle de vie propre (liste fermée
    en ordre d'entonnoir), indépendant des étapes lead / statuts de document.
    Tout est scopé à la société ; acteur et société posés côté serveur."""
    queryset = Ticket.objects.select_related(
        'client', 'installation', 'equipement', 'equipement__produit',
        'technicien_responsable', 'cause', 'remede', 'categorie', 'equipe',
        'categorie_equipement',
    ).prefetch_related('interventions__technicien').all()
    serializer_class = TicketSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'description', 'client__nom', 'client__prenom',
        'installation__reference',
    ]
    ordering_fields = [
        'reference', 'date_creation', 'date_ouverture', 'priorite', 'statut',
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # ASAV39 — « suis-je abonné ? » préchargé (1 requête pour la page).
        if getattr(self.request.user, 'pk', None):
            from django.db.models import Prefetch
            qs = qs.prefetch_related(Prefetch(
                'followers',
                queryset=TicketFollower.objects.filter(
                    user=self.request.user),
                to_attr='_suivis_de_moi'))
        # Portée de visibilité (Feature F) — tickets créés par soi / dont on est
        # le technicien responsable / ceux de l'équipe. 'all' → inchangé.
        from authentication.scoping import scope_queryset
        qs = scope_queryset(
            qs, self.request.user, ['technicien_responsable', 'created_by'])
        params = self.request.query_params
        statut = params.get('statut')
        type_ = params.get('type')
        priorite = params.get('priorite')
        technicien = params.get('technicien')
        client = params.get('client')
        installation = params.get('installation')
        equipement = params.get('equipement')
        categorie = params.get('categorie')
        equipe = params.get('equipe')
        if statut:
            qs = qs.filter(statut=statut)
        if type_:
            qs = qs.filter(type=type_)
        if priorite:
            qs = qs.filter(priorite=priorite)
        if technicien:
            qs = qs.filter(technicien_responsable_id=technicien)
        if client:
            qs = qs.filter(client_id=client)
        if installation:
            qs = qs.filter(installation_id=installation)
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        if categorie:
            qs = qs.filter(categorie_id=categorie)
        if equipe:
            qs = qs.filter(equipe_id=equipe)
        # File de service par défaut = tickets OUVERTS non annulés. ?ouvert=tous
        # pour tout voir ; un filtre ?statut explicite l'emporte.
        if self.action == 'list' and not statut:
            ouvert = params.get('ouvert')
            if ouvert != 'tous':
                qs = qs.filter(statut__in=Ticket.OPEN_STATUTS, annule=False)
        # Drapeau d'annulation (comme « Perdu »).
        annule = params.get('annule')
        if self.action == 'list':
            if annule == 'only':
                qs = qs.filter(annule=True)
            elif annule == 'sans':
                qs = qs.filter(annule=False)
        return qs

    def get_permissions(self):
        # Une garde déclarée par l'@action elle-même (permission_classes= sur
        # le décorateur @action) PRIME sur le tiering ci-dessous — sinon le
        # kwarg du décorateur devient du code mort et l'action retombe sur
        # IsAdminRole. Le reste de cette surcharge NE lit PAS
        # self.permission_classes ; le tier de chaque @action SANS garde
        # déclarée doit donc être listé EXPLICITEMENT ci-dessous — tenu par
        # apps/sav/tests_ticket_action_permissions.py.
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        if self.action in READ_ACTIONS + [
                'historique', 'rapport_pdf', 'lien_client', 'similaires',
                'triage_ia',
                # ZSAV9 — suivre/ne plus suivre est ouvert à tout rôle voyant
                # le ticket (pas seulement sav_gerer).
                'suivre', 'ne_plus_suivre']:
            return [HasPermissionOrLegacy('sav_voir')()]
        elif self.action in WRITE_ACTIONS + [
                'noter', 'annuler', 'reactiver', 'creer_devis',
                'attente_client', 'reprendre', 'fusionner',
                'facturer', 'planifier_intervention',
                'pieces_compatibles', 'premier_reponse', 'pieces',
                'supprimer_piece', 'pieces_retirees', 'generer_facture',
                'prets_equipement', 'retourner_pret', 'creer_lead',
                'checklist',
                # YDOCF1 — actions guardées de la machine d'états.
                'planifier', 'demarrer', 'resoudre', 'cloturer', 'reouvrir',
                # ZMFG3 — replanification calendrier (date_tournee, un ticket).
                'replanifier',
                # ZSAV3 — activités planifiées à échéance.
                'activites', 'cocher_activite',
                # ZSAV10 — endpoint d'actions groupées.
                'actions_groupees',
                # ZSAV6 — pièces unifiées (vue fusionnée) + fiche d'intervention.
                'pieces_unifiees', 'worksheet']:
            return [HasPermissionOrLegacy('sav_gerer')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        company = self.request.user.company
        for field in ('client', 'installation', 'equipement', 'cause',
                      'remede', 'equipe'):
            obj = serializer.validated_data.get(field)
            if obj is not None and obj.company_id != company.id:
                raise ValidationError({field: 'Référence inconnue.'})

    @staticmethod
    def _interventions_ouvertes(ticket):
        """YSERV2 — liste (id, statut) des interventions liées à ce ticket
        PAS ENCORE terminées/validées. Lecture cross-app via
        ``installations.selectors`` (jamais un import du modèle) ; liste vide
        = comportement historique (aucune intervention liée)."""
        from apps.installations.selectors import interventions_ouvertes_pour_ticket
        return interventions_ouvertes_pour_ticket(ticket.id)

    def _resolve_from_equipement(self, serializer):
        """Quand un ticket est ouvert depuis le parc (un équipement lié) sans
        client ni chantier explicite, déduire l'installation et le client de
        l'équipement — ainsi un ticket créé depuis un équipement porte
        client + installation + equipement sans sélection manuelle."""
        equipement = serializer.validated_data.get('equipement')
        if equipement is None:
            return
        installation = getattr(equipement, 'installation', None)
        if installation is None:
            # ASAV40 — équipement vendu au comptoir (XPOS9) : pas de chantier,
            # mais un client de vente.
            if (serializer.validated_data.get('client') is None
                    and equipement.client_vente_id):
                serializer.validated_data['client'] = equipement.client_vente
            return
        if serializer.validated_data.get('installation') is None:
            serializer.validated_data['installation'] = installation
        if serializer.validated_data.get('client') is None:
            client = getattr(installation, 'client', None)
            if client is not None:
                serializer.validated_data['client'] = client

    def _resolve_resolution_days(self, company, client, priorite):
        """XSAV7 — Résout le délai de résolution (jours) avec précédence :
        contrat de maintenance ACTIF du client avec override > sla_par_priorite
        > défauts société (premier match gagne). Sans contrat/override, la
        résolution retombe exactement sur le comportement FG81 d'origine.

        AUD519 — l'implémentation vit désormais dans ``services`` (une seule
        copie, partagée avec les 7 autres producteurs de tickets)."""
        from .services import resolution_days_pour
        return resolution_days_pour(company, client, priorite)

    def _compute_sla_due_at(self, company, client, priorite, date_ouverture):
        """FG81 — Calcule sla_due_at depuis les réglages société (ou None).

        XSAV5 — quand ``sla_jours_ouvres`` est activé, l'échéance avance de
        ``resolution_days`` JOURS OUVRÉS (via ``core.calendar``, jours ouvrés +
        fériés marocains) plutôt qu'en jours calendaires. OFF (défaut) =
        comportement calendaire byte-identique à avant XSAV5.

        XSAV7 — ``resolution_days`` peut venir d'un contrat de maintenance actif
        du client (override), avant repli sur ``sla_par_priorite``/défauts.

        AUD519 — délègue à ``services.compute_sla_due_at`` : ce chemin manuel
        n'est plus le seul à poser l'échéance, la logique est partagée."""
        from .services import compute_sla_due_at
        return compute_sla_due_at(company, client, priorite, date_ouverture)

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        self._resolve_from_equipement(serializer)
        # client est optionnel au niveau sérialiseur (peut venir de l'équipement) ;
        # s'il n'a pas pu être résolu, on rétablit l'exigence ici.
        if not serializer.validated_data.get('client'):
            raise ValidationError({'client': 'Ce champ est obligatoire.'})
        date_ouverture = (
            serializer.validated_data.get('date_ouverture')
            or timezone.localdate())
        # FG81 — SLA : calcul de l'échéance cible à la création.
        # XSAV7 — le client résolu alimente l'override contrat éventuel.
        priorite = serializer.validated_data.get('priorite', 'normale')
        client = serializer.validated_data.get('client')
        # ASAV23 — un double clic ne crée qu'un ticket.
        self._refuser_doublon_recent(company, serializer.validated_data)
        sla_due_at = self._compute_sla_due_at(
            company, client, priorite, date_ouverture)
        # ASAV19 — échéance de PREMIÈRE RÉPONSE, même service.
        from .services import compute_sla_echeance, compute_sla_reponse_due_at
        sla_reponse_due_at = compute_sla_reponse_due_at(
            company, client, priorite, date_ouverture)
        # ASAV21 — horodatage de l'échéance (chemin heures ouvrées seulement).
        sla_echeance_at = compute_sla_echeance(
            company, client, priorite, date_ouverture)[1]
        create_with_reference(
            Ticket, 'SAV', company,
            lambda ref: serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
                date_ouverture=date_ouverture,
                sla_due_at=sla_due_at,
                sla_echeance_at=sla_echeance_at,
                sla_reponse_due_at=sla_reponse_due_at),
        )
        # XSAV9 — affectation automatique si aucun technicien n'a été choisi
        # à la création et que la société l'a activée (défaut OFF = inchangé).
        inst = serializer.instance
        if not inst.technicien_responsable_id:
            sla = SavSlaSettings.get(company)
            if sla.affectation_auto_sav:
                from .services import assign_technicien_auto
                technicien = assign_technicien_auto(company=company)
                if technicien is not None:
                    inst.technicien_responsable = technicien
                    inst.save(update_fields=['technicien_responsable'])
        # XFSM15 — suggestion de récidive : une intervention TERMINÉE/VALIDÉE
        # récente sur le MÊME chantier marque le ticket récidive + non
        # facturable par défaut (override responsable possible ensuite).
        if inst.installation_id and not inst.est_recidive:
            from .services import suggerer_recidive
            interv_id, motif = suggerer_recidive(
                company=company, installation_id=inst.installation_id,
                exclure_ticket_id=inst.id, a_la_date=date_ouverture)
            if interv_id is not None:
                inst.est_recidive = True
                inst.intervention_origine_id = interv_id
                inst.motif_recidive = motif
                inst.non_facturable = True
                inst.save(update_fields=[
                    'est_recidive', 'intervention_origine_id',
                    'motif_recidive', 'non_facturable'])
        # XSAV24 — la trace de création (CREATION) est désormais posée
        # automatiquement par le récepteur `post_save` de `receivers.py`
        # (voir `_log_creation_on_ticket_created`), pour TOUT chemin de
        # création (API, WhatsApp, e-mail...) — jamais seulement celui-ci.
        # ZSAV9 — abonne automatiquement les suiveurs globaux (réglage
        # société, liste vide par défaut = no-op).
        from .services import abonner_suiveurs_globaux
        abonner_suiveurs_globaux(inst)
        # XCTR2 — avertissement NON BLOQUANT si l'équipement lié n'est pas
        # couvert par le contrat de maintenance actif du client (registre
        # XCTR2). Un client sans contrat, ou un ticket sans équipement, ne
        # déclenche rien (comportement historique inchangé).
        if inst.equipement_id and inst.client_id:
            from .models import ContratMaintenance
            # ASAV26 — contrat VALIDE (expiration + grâce), pas le seul drapeau.
            contrat = ContratMaintenance.valide_pour_client(inst.client_id)
            if contrat is not None and not contrat.couvre_equipement(inst.equipement):
                activity.log_note(
                    inst, self.request.user,
                    'Avertissement : équipement non couvert par le '
                    "registre des équipements du contrat de maintenance "
                    f'#{contrat.pk}.')
        # XCTR3 — avertissement NON BLOQUANT si ce ticket dépasse le quota de
        # visites/déplacements inclus au contrat (droits_restants). NULL sur le
        # contrat = illimité : aucun avertissement possible dans ce cas.
        if inst.client_id and inst.type in (Ticket.Type.PREVENTIF, Ticket.Type.CORRECTIF):
            from .models import ContratMaintenance
            from .selectors import droits_restants
            # ASAV26 — contrat VALIDE (expiration + grâce), pas le seul drapeau.
            contrat = ContratMaintenance.valide_pour_client(inst.client_id)
            if contrat is not None:
                droits = droits_restants(contrat, inst.date_ouverture.year)
                if (inst.type == Ticket.Type.PREVENTIF
                        and droits['visites_restantes'] == 0):
                    activity.log_note(
                        inst, self.request.user,
                        'Avertissement : quota de visites incluses au '
                        f'contrat #{contrat.pk} déjà atteint pour '
                        f"{droits['annee']}.")
                elif (inst.type == Ticket.Type.CORRECTIF
                        and droits['deplacements_restants'] == 0):
                    activity.log_note(
                        inst, self.request.user,
                        'Avertissement : quota de déplacements inclus au '
                        f'contrat #{contrat.pk} déjà atteint pour '
                        f"{droits['annee']}.")

    # XSAV11 — statuts « clos » depuis lesquels revenir à un statut ouvert
    # compte comme une réouverture.
    _CLOTURE_STATUTS = (Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE)

    #: ASAV23 — fenêtre (secondes) dans laquelle un ticket identique est un
    #: double envoi (double clic, retry réseau), pas une nouvelle demande.
    FENETRE_DOUBLON_SECONDES = 60

    @classmethod
    def _refuser_doublon_recent(cls, company, data):
        """ASAV23 — 409 si un ticket OUVERT identique (même société, client,
        chantier, équipement, description normalisée) a été créé il y a
        moins de 60 s ; le corps nomme la référence existante."""
        def _normaliser(texte):
            return ' '.join((texte or '').split()).casefold()

        client = data.get('client')
        installation = data.get('installation')
        equipement = data.get('equipement')
        description = _normaliser(data.get('description'))
        depuis = timezone.now() - timedelta(
            seconds=cls.FENETRE_DOUBLON_SECONDES)
        candidats = Ticket.objects.filter(
            company=company, client=client,
            installation_id=getattr(installation, 'pk', None),
            equipement_id=getattr(equipement, 'pk', None),
            statut__in=Ticket.OPEN_STATUTS, annule=False,
            date_creation__gte=depuis,
        ).only('reference', 'description').order_by('-date_creation')
        for existant in candidats:
            if _normaliser(existant.description) == description:
                raise TicketEnDoubleError({
                    'detail': (f"Ce ticket vient déjà d'être créé "
                               f'({existant.reference}).'),
                    'reference_existante': existant.reference,
                })

    @staticmethod
    def _cle_sla(ticket):
        """ASAV15 — les entrées de l'échéance SLA d'un ticket."""
        return (ticket.priorite, ticket.date_ouverture, ticket.client_id)

    @staticmethod
    def _recalculer_sla(ticket):
        """ASAV15 — recalcule l'échéance SLA (override contrat compris, même
        ``compute_sla_due_at`` que la création) et ouvre un nouveau cycle :
        pré-alerte, escalade (paliers compris) et ``sla_breach`` remis à
        zéro puis ``sla_breach`` recalculé sur la nouvelle échéance."""
        from .services import compute_sla_echeance, compute_sla_reponse_due_at
        ouverture = ticket.date_ouverture or timezone.localdate()
        ticket.sla_due_at, ticket.sla_echeance_at = compute_sla_echeance(
            ticket.company, ticket.client, ticket.priorite, ouverture)
        # ASAV19 — l'échéance de première réponse suit les mêmes entrées.
        ticket.sla_reponse_due_at = compute_sla_reponse_due_at(
            ticket.company, ticket.client, ticket.priorite, ouverture)
        ticket.sla_pre_alert_notifiee = False
        ticket.sla_escalade_notifiee = False
        ticket.sla_escalade_paliers_notifies = None
        ticket.sla_breach = False
        ticket.recompute_sla_breach()
        ticket.save(update_fields=[
            'sla_due_at', 'sla_echeance_at', 'sla_reponse_due_at',
            'sla_pre_alert_notifiee',
            'sla_escalade_notifiee', 'sla_escalade_paliers_notifies',
            'sla_breach'])

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        # YDOCF1 — `statut` est désormais read-only sur le sérialiseur : plus
        # aucune transition n'arrive ici via PATCH direct. Les transitions
        # passent exclusivement par les actions guardées ci-dessous
        # (`planifier`/`demarrer`/`resoudre`/`cloturer`), qui appliquent la
        # même chaîne d'effets (SLA/chatter/notification/downtime) via
        # `_appliquer_transition_statut`.
        # CIQ642 — passage « installation à l'arrêt » : vrai maintenant, faux
        # avant → l'action « notifier le distributeur » est posée sur le
        # dossier 82-21 (no-op hors site professionnel sous accord /
        # autorisation).
        etait_a_l_arret = bool(serializer.instance.arret_installation)
        # ASAV15 — l'échéance SLA dépend de la priorité, de l'ouverture et du
        # client (override contrat) : capturés AVANT la mise à jour.
        avant = self._cle_sla(serializer.instance)
        # ASAV22 — instantané AVANT la correction, pour l'historique.
        ancien = Ticket.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        if self._cle_sla(serializer.instance) != avant:
            self._recalculer_sla(serializer.instance)
        # ASAV22 — chaque champ suivi corrigé par PATCH laisse une ligne
        # avant → après au chatter (aucune ligne sans changement réel).
        activity.log_changes(ancien, serializer.instance, self.request.user)
        if serializer.instance.arret_installation and not etait_a_l_arret:
            from . import services as sav_services
            sav_services.notifier_arret_installation(serializer.instance)

    def _appliquer_transition_statut(self, ticket, statut_cible):
        """ASAV12 — délégué d'une ligne vers LE service unique
        ``services.appliquer_transition_ticket`` (même chaîne d'effets pour la
        vue et le récepteur d'intervention terminée). Une transition refusée
        lève ``ValidationError`` (400) avec le détail du service."""
        from . import services as sav_services
        try:
            return sav_services.appliquer_transition_ticket(
                ticket, statut_cible, self.request.user, request=self.request)
        except sav_services.TransitionTicketRefusee as exc:
            raise ValidationError(exc.detail)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='planifier',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def planifier(self, request, pk=None):
        """YDOCF1 — Transition gardée NOUVEAU/... → PLANIFIE."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.PLANIFIE)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='demarrer',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def demarrer(self, request, pk=None):
        """YDOCF1 — Transition gardée → EN_COURS."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.EN_COURS)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=_sch('SavResoudreRequete', {
        'canal_resolution': _CharF(required=False)}))
    @action(detail=True, methods=['post'], url_path='resoudre',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def resoudre(self, request, pk=None):
        """YDOCF1 — Transition gardée → RESOLU.

        YSERV12 — ``canal_resolution`` optionnel dans le corps : posé
        explicitement AVANT la transition pour ne jamais être écrasé par la
        proposition automatique (même règle qu'avant YDOCF1)."""
        ticket = self.get_object()
        canal = request.data.get('canal_resolution')
        if canal:
            valid = {c for c, _ in Ticket.CanalResolution.choices}
            if canal not in valid:
                return Response(
                    {'canal_resolution': 'Valeur invalide.'}, status=400)
            ticket.canal_resolution = canal
        self._appliquer_transition_statut(ticket, Ticket.Statut.RESOLU)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='cloturer',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def cloturer(self, request, pk=None):
        """YDOCF1 — Transition gardée → CLOTURE (garde YSERV2 conservée)."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.CLOTURE)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='reouvrir',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def reouvrir(self, request, pk=None):
        """XSAV11/YDOCF1 — Réouverture GARDÉE → NOUVEAU depuis PLANIFIE/RESOLU/
        CLOTURE (le graphe machine_etats l'autorise ; EN_COURS → NOUVEAU est
        refusé et renvoie 400). C'est l'unique point d'entrée pour ramener un
        ticket à « nouveau » depuis l'UI (le PATCH direct de statut est
        read-only depuis YDOCF1). ``_appliquer_transition_statut`` incrémente
        ``reopen_count`` quand on rouvre depuis un statut clôturé/résolu."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.NOUVEAU)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=_sch('SavReplanifierRequete', {
        'date_tournee': drf_serializers.DateField()}))
    @action(detail=True, methods=['post'], url_path='replanifier',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def replanifier(self, request, pk=None):
        """ZMFG3 — Replanifie CE ticket (préventif ou correctif) à une nouvelle
        ``date_tournee`` — glisser-déposer d'une carte du calendrier vers un
        autre jour. Contrairement à ``planifier_tournee`` (FG88, bulk et
        restreint aux PREVENTIF pour la tournée groupée), cette action porte
        sur UN SEUL ticket, quel que soit son type, et ne force aucun
        changement de statut ni de technicien. Scopée société via
        ``get_object`` (TenantMixin) ; jamais de PATCH direct (date_tournee
        reste read-only sur le serializer)."""
        ticket = self.get_object()
        raw_date = (request.data.get('date_tournee') or '').strip()
        try:
            new_date = _date.fromisoformat(raw_date)
        except (ValueError, TypeError):
            return Response(
                {'date_tournee': 'Date invalide (AAAA-MM-JJ).'}, status=400)
        ticket.date_tournee = new_date
        ticket.save(update_fields=['date_tournee'])
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    # ZSAV10 — opérations groupées supportées + leur validation d'entrée.
    _ACTIONS_GROUPEES_VALEURS = {
        'technicien': None,  # validé/résolu séparément (FK utilisateur).
        'priorite': {c for c, _ in Ticket.Priorite.choices},
        'statut': {c for c, _ in Ticket.Statut.choices},
        'annuler': None,  # pas de valeur — motif optionnel.
    }

    @extend_schema(
        request=_sch('SavActionsGroupeesRequete', {
            'ids': drf_serializers.ListField(
                child=drf_serializers.IntegerField(), allow_empty=False),
            'operation': _CharF(),
            'statut': _CharF(required=False),
            'technicien': drf_serializers.IntegerField(
                required=False, allow_null=True),
            'priorite': _CharF(required=False),
            'motif': _CharF(required=False, allow_blank=True),
        }),
        responses=_sch('SavActionsGroupeesReponse', {
            'traites': drf_serializers.ListField(
                child=drf_serializers.IntegerField()),
            'echecs': drf_serializers.ListField(child=drf_serializers.DictField()),
            'nb_traites': drf_serializers.IntegerField(),
            'nb_echecs': drf_serializers.IntegerField(),
        }))
    @action(detail=False, methods=['post'], url_path='actions-groupees',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def actions_groupees(self, request):
        """ZSAV10 — Applique UNE opération (statut/technicien/priorite/
        annuler) à un LOT de tickets en une seule requête, atomiquement PAR
        TICKET (chaque ticket journalisé) mais tolérante : les ids d'une
        autre société sont silencieusement ignorés (jamais un 404/500 qui
        casserait tout le lot). ``statut`` respecte la machine d'états
        gardée (YDOCF1) — un ticket dont la transition est illégale est
        rapporté dans ``echecs`` plutôt que de faire échouer le lot entier.
        """
        ids = request.data.get('ids') or []
        operation = request.data.get('operation')
        if not isinstance(ids, list) or not ids:
            return Response({'ids': 'Liste d\'identifiants requise.'},
                            status=400)
        if operation not in self._ACTIONS_GROUPEES_VALEURS:
            return Response(
                {'operation': 'Opération inconnue.'}, status=400)

        # ASAV25 — seuls les tickets VISIBLES (portée de l'utilisateur) sont
        # traités ; les autres ids sortent en échec « introuvable », sans
        # dire s'ils existent.
        company = request.user.company
        tickets = list(_tickets_visibles(request).filter(id__in=ids))
        traites = []
        echecs = []
        vus = {t.id for t in tickets}
        for brut in ids:
            try:
                ident = int(brut)
            except (TypeError, ValueError):
                ident = brut
            if ident not in vus:
                echecs.append({'id': ident, 'raison': 'Ticket introuvable.'})

        if operation == 'statut':
            statut_cible = request.data.get('statut')
            if statut_cible not in self._ACTIONS_GROUPEES_VALEURS['statut']:
                return Response({'statut': 'Statut inconnu.'}, status=400)
            from . import machine_etats
            for ticket in tickets:
                try:
                    self._appliquer_transition_statut(ticket, statut_cible)
                    traites.append(ticket.id)
                except (ValidationError, machine_etats.TransitionInterdite) \
                        as exc:
                    echecs.append({'id': ticket.id, 'raison': str(exc)})

        elif operation == 'technicien':
            technicien_id = request.data.get('technicien')
            technicien = None
            if technicien_id:
                technicien = get_user_model().objects.filter(
                    id=technicien_id, company=company).first()
                if technicien is None:
                    return Response(
                        {'technicien': 'Technicien inconnu.'}, status=400)
            for ticket in tickets:
                old = Ticket.objects.get(pk=ticket.pk)
                ticket.technicien_responsable = technicien
                ticket.save(update_fields=['technicien_responsable'])
                activity.log_changes(old, ticket, request.user)
                traites.append(ticket.id)

        elif operation == 'priorite':
            priorite = request.data.get('priorite')
            if priorite not in self._ACTIONS_GROUPEES_VALEURS['priorite']:
                return Response({'priorite': 'Priorité inconnue.'}, status=400)
            for ticket in tickets:
                old = Ticket.objects.get(pk=ticket.pk)
                ticket.priorite = priorite
                ticket.save(update_fields=['priorite'])
                # ASAV15 — même recalcul d'échéance que le PATCH.
                if old.priorite != priorite:
                    self._recalculer_sla(ticket)
                activity.log_changes(old, ticket, request.user)
                traites.append(ticket.id)

        elif operation == 'annuler':
            motif = (request.data.get('motif') or '').strip()
            for ticket in tickets:
                if not ticket.annule:
                    ticket.annule = True
                    ticket.motif_annulation = motif or None
                    ticket.save(update_fields=['annule', 'motif_annulation'])
                    activity.log_note(
                        ticket, request.user,
                        f"Ticket annulé{(' : ' + motif) if motif else ''}")
                traites.append(ticket.id)

        return Response({
            'traites': traites, 'echecs': echecs,
            'nb_traites': len(traites), 'nb_echecs': len(echecs),
        })

    @extend_schema(responses=TicketActivitySerializer(many=True))
    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def historique(self, request, pk=None):
        ticket = self.get_object()
        return Response(
            TicketActivitySerializer(ticket.activites.all(), many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter('limit', OpenApiTypes.INT, required=False)],
        responses=_sch('SavSimilairesReponse', {
            'results': drf_serializers.ListField(child=drf_serializers.DictField())}))
    @action(detail=True, methods=['get'], url_path='similaires',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def similaires(self, request, pk=None):
        """XSAV21 — Tickets RÉSOLUS similaires (même produit > même cause >
        similarité texte), pour le panneau « Résolutions similaires »."""
        from .selectors import tickets_similaires
        ticket = self.get_object()
        try:
            limit = int(request.query_params.get('limit', 5))
        except (TypeError, ValueError):
            limit = 5
        data = tickets_similaires(ticket, limit=max(1, limit))
        return Response({'results': data})

    @extend_schema(responses=_sch('SavPiecesCompatiblesReponse', {
        'results': drf_serializers.ListField(child=drf_serializers.DictField())}))
    @action(detail=True, methods=['get'], url_path='pieces-compatibles',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def pieces_compatibles(self, request, pk=None):
        """XSAV25 — Pièces catalogue compatibles avec le produit de
        l'équipement lié à ce ticket, pour que le picker de pièces les
        propose EN PREMIER. Liste vide (jamais une erreur) si le ticket
        n'a pas d'équipement lié ou si aucune compatibilité n'est mappée."""
        from .selectors import pieces_compatibles as _pieces_compatibles
        ticket = self.get_object()
        if not ticket.equipement_id or not ticket.equipement.produit_id:
            return Response({'results': []})
        data = _pieces_compatibles(
            ticket.company, ticket.equipement.produit_id)
        return Response({'results': data})

    @extend_schema(
        methods=['GET'], request=None,
        responses=TicketActiviteAFaireSerializer(many=True))
    @extend_schema(
        methods=['POST'], request=TicketActiviteAFaireSerializer,
        responses={201: TicketActiviteAFaireSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='activites',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def activites(self, request, pk=None):
        """ZSAV3 — Activités planifiées à échéance du ticket. GET liste
        (triées par échéance), POST crée une nouvelle activité (société et
        ticket posés côté serveur)."""
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.activites_a_faire.select_related('assigne')
            return Response(
                TicketActiviteAFaireSerializer(qs, many=True).data)
        # ENF17 — la requête en contexte borne ``assigne`` à la société
        # (``same_company_fields``) : un id d'ailleurs = un id absent (400).
        serializer = TicketActiviteAFaireSerializer(
            data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        assigne = serializer.validated_data.get('assigne')
        if assigne is not None and assigne.company_id != ticket.company_id:
            return Response(
                {'assigne': 'Utilisateur inconnu.'}, status=400)
        instance = serializer.save(
            company=ticket.company, ticket=ticket,
            created_by=request.user)
        return Response(
            TicketActiviteAFaireSerializer(instance).data,
            status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=TicketActiviteAFaireSerializer)
    @action(detail=True, methods=['post'],
            url_path=r'activites/(?P<activite_id>[^/.]+)/cocher',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def cocher_activite(self, request, pk=None, activite_id=None):
        """ZSAV3 — Marque une activité à faire comme faite (idempotent)."""
        ticket = self.get_object()
        try:
            act = ticket.activites_a_faire.get(pk=activite_id)
        except (TicketActiviteAFaire.DoesNotExist, ValueError):
            return Response({'detail': 'Activité introuvable.'}, status=404)
        if not act.fait:
            act.fait = True
            act.fait_le = timezone.now()
            act.save(update_fields=['fait', 'fait_le'])
        return Response(TicketActiviteAFaireSerializer(act).data)

    @extend_schema(
        request=_sch('SavNoterRequete', {
            'body': _CharF(required=False, allow_blank=True),
            'reponse_type_id': drf_serializers.IntegerField(required=False),
            'visible_client': drf_serializers.BooleanField(required=False),
        }),
        responses={201: TicketActivitySerializer})
    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def noter(self, request, pk=None):
        """Ajoute une note au chatter du ticket.

        XSAV23 — ``reponse_type_id`` (optionnel) insère en un clic le corps
        d'une réponse type (macro), placeholders whitelistés rendus
        (``{client}{reference}{technicien}{date}``) ; ``body`` explicite,
        s'il est fourni, est utilisé TEL QUEL en plus/à la place (le body
        gagne si les deux sont fournis — la macro reste une aide au
        pré-remplissage, pas une contrainte). Si la macro porte un
        ``nouveau_statut``, il est appliqué au ticket (idempotent : ignoré
        si le ticket est déjà dans ce statut)."""
        ticket = self.get_object()
        body = (request.data.get('body') or '').strip()
        reponse_type_id = request.data.get('reponse_type_id')
        statut_macro = None

        if not body and reponse_type_id:
            try:
                macro = ReponseType.objects.get(
                    pk=reponse_type_id, company=ticket.company)
            except (ReponseType.DoesNotExist, ValueError):
                return Response(
                    {'detail': 'Réponse type introuvable.'}, status=400)
            # NTSRV34 — une macro restreinte à d'autres canaux n'est pas
            # seulement masquée du sélecteur : elle est refusée côté serveur
            # (une macro SANS restriction reste acceptée partout — défaut).
            canal_ticket = ReponseType.canal_de_ticket(ticket)
            if not macro.autorise_canal(canal_ticket):
                return Response(
                    {'detail': 'Cette réponse type n\'est pas autorisée sur '
                               'le canal de ce ticket.'}, status=400)
            body = macro.rendu(
                client=str(ticket.client) if ticket.client_id else '',
                reference=ticket.reference,
                technicien=getattr(
                    ticket.technicien_responsable, 'username', ''),
                date=timezone.localdate().strftime('%d/%m/%Y'),
            ).strip()
            if macro.nouveau_statut and ticket.statut != macro.nouveau_statut:
                statut_macro = macro.nouveau_statut

        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if statut_macro:
            # ASAV13 — le statut d'une macro passe par LE service gardé
            # (graphe, YSERV2, effets complets d'ASAV12) ; un refus renvoie
            # 400 SANS note ni changement de statut.
            from . import services as sav_services
            try:
                sav_services.appliquer_transition_ticket(
                    ticket, statut_macro, request.user, request=request)
            except sav_services.TransitionTicketRefusee as exc:
                return Response(exc.detail, status=400)
        # NTPRT12 — opt-in EXPLICITE : sans `visible_client` vrai dans le
        # corps, la note reste interne et le portail client ne la voit jamais.
        visible_client = request.data.get('visible_client') in (
            True, 'true', 'True', '1', 1, 'on')
        act = activity.log_note(
            ticket, request.user, body, visible_client=visible_client)
        # ASAV19 — une note VISIBLE CLIENT est une réponse au client ; une
        # note interne ne l'est pas.
        if visible_client:
            from .services import poser_premiere_reponse
            poser_premiere_reponse(ticket)
        # ZSAV9 — notifie les suiveurs du ticket (jamais l'auteur de la note).
        from .services import notify_followers
        from apps.notifications.types_evenements import EventType
        notify_followers(
            ticket, event_type=EventType.SAV_TICKET_FOLLOWED_UPDATE,
            title=f'Nouvelle note — {ticket.reference}',
            body=body, link=f'/sav/tickets/{ticket.pk}',
            exclude_user=request.user)
        return Response(TicketActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def annuler(self, request, pk=None):
        """Annule le ticket (DRAPEAU avec motif — pas une étape)."""
        ticket = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not ticket.annule:
            ticket.annule = True
            ticket.motif_annulation = motif or None
            ticket.save(update_fields=['annule', 'motif_annulation'])
            activity.log_note(
                ticket, request.user,
                f"Ticket annulé{(' : ' + motif) if motif else ''}")
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='reactiver',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def reactiver(self, request, pk=None):
        ticket = self.get_object()
        if ticket.annule:
            ticket.annule = False
            ticket.motif_annulation = None
            ticket.save(update_fields=['annule', 'motif_annulation'])
            activity.log_note(ticket, request.user, "Ticket réactivé")
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=None, responses=_sch('SavSuivreReponse', {
        'suivi': drf_serializers.BooleanField()}))
    @action(detail=True, methods=['post'], url_path='suivre',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def suivre(self, request, pk=None):
        """ZSAV9 — S'abonner aux notifications de ce ticket (idempotent)."""
        ticket = self.get_object()
        TicketFollower.objects.get_or_create(
            company=ticket.company, ticket=ticket, user=request.user)
        return Response({'suivi': True})

    @suivre.mapping.delete
    @extend_schema(request=None, responses=_sch('SavNePlusSuivreReponse', {
        'suivi': drf_serializers.BooleanField()}))
    def ne_plus_suivre(self, request, pk=None):
        """ZSAV9 — Se désabonner des notifications de ce ticket (idempotent)."""
        ticket = self.get_object()
        TicketFollower.objects.filter(
            ticket=ticket, user=request.user).delete()
        return Response({'suivi': False})

    @extend_schema(request=_sch('SavPremierReponseRequete', {
        'at': drf_serializers.DateTimeField(required=False)}))
    @action(detail=True, methods=['post'], url_path='premier-reponse',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def premier_reponse(self, request, pk=None):
        """FG81 — Enregistre la date de première réponse (horloge de réponse SLA).

        Idempotent : si déjà posée, renvoie la valeur existante. La date peut
        être fournie en body (`at` ISO8601) sinon utilise now()."""
        ticket = self.get_object()
        if ticket.date_premiere_reponse is None:
            at_raw = request.data.get('at')
            if at_raw:
                from django.utils.dateparse import parse_datetime
                at = parse_datetime(at_raw)
                if at is None:
                    return Response({'detail': 'Date invalide.'}, status=400)
            else:
                at = timezone.now()
            from .services import poser_premiere_reponse
            poser_premiere_reponse(ticket, at)
            activity.log_note(
                ticket, request.user,
                f'Première réponse enregistrée le {at.strftime("%d/%m/%Y %H:%M")}')
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=_sch('SavReaffecterEquipeRequete', {
        'equipe': drf_serializers.IntegerField(required=False, allow_null=True),
        'equipe_id': drf_serializers.IntegerField(required=False, allow_null=True),
    }))
    @action(detail=True, methods=['post'], url_path='reaffecter-equipe',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def reaffecter_equipe(self, request, pk=None):
        """NTSRV8 — Réaffecte le ticket à une autre équipe de maintenance.

        SEUL chemin d'écriture du débordement : la file d'attente
        (``sav/file-attente/``) ne fait que PROPOSER — elle ne réaffecte
        jamais en silence. ``equipe: null`` détache le ticket de son équipe."""
        ticket = self.get_object()
        from .services import reaffecter_equipe as _reaffecter

        equipe_id = request.data.get('equipe', request.data.get('equipe_id'))
        equipe = None
        if equipe_id not in (None, ''):
            equipe = EquipeMaintenance.objects.filter(
                pk=equipe_id, company=request.user.company).first()
            if equipe is None:
                return Response({'equipe': 'Équipe inconnue.'}, status=400)
        try:
            _reaffecter(ticket, equipe, user=request.user)
        except ValueError as exc:
            champ, _, detail = str(exc).partition(': ')
            return Response({champ: detail or str(exc)}, status=400)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(
        request=_sch('SavLogAppelRequete', {
            'issue': _CharF(required=False, allow_blank=True),
            'duree_minutes': drf_serializers.IntegerField(
                required=False, min_value=0),
            'notes': _CharF(required=False, allow_blank=True),
        }),
        responses={201: _sch('SavLogAppelReponse', {
            'id': drf_serializers.IntegerField(),
            'kind': _CharF(),
            'body': _CharF(),
            'issue': _CharF(allow_blank=True, allow_null=True),
            'duree_minutes': drf_serializers.IntegerField(allow_null=True),
            'created_at': drf_serializers.DateTimeField(),
        })})
    @action(detail=True, methods=['post'], url_path='log-appel',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def log_appel(self, request, pk=None):
        """NTSRV5 — Enregistre un APPEL SAV au chatter (durée, notes, issue).

        Trace MANUELLE structurée — aucune intégration PBX dans ce lot (elle
        exigerait un fournisseur tiers, GATED). La liste d'issues est celle
        de ``crm.LeadActivity`` (joint / non joint / à rappeler / refus /
        intéressé). Erreurs en français, nommant le champ fautif."""
        ticket = self.get_object()

        issue = (request.data.get('issue')
                 or request.data.get('outcome') or '').strip()
        issues_valides = {code for code, _ in TicketActivity.OUTCOMES}
        if issue not in issues_valides:
            return Response(
                {'issue': 'Issue inconnue (joint, non_joint, rappel, refuse, '
                          'interesse, ou vide).'}, status=400)

        duree_brute = request.data.get('duree_minutes',
                                       request.data.get('duree'))
        duree = None
        if duree_brute not in (None, ''):
            try:
                duree = int(duree_brute)
            except (TypeError, ValueError):
                duree = -1
            if duree < 0:
                return Response(
                    {'duree_minutes': 'Durée invalide : un nombre de minutes '
                                      '(entier positif) est attendu.'},
                    status=400)

        notes = (request.data.get('notes') or '').strip()[:4000]
        libelle = dict(TicketActivity.OUTCOMES).get(issue, issue)
        corps = 'Appel téléphonique'
        if duree is not None:
            corps += f' — {duree} min'
        if issue:
            corps += f' — issue : {libelle}'
        if notes:
            corps += f'\n\n{notes}'

        entree = activity.log_appel(
            ticket, request.user, corps, outcome=issue, duree_minutes=duree)
        # ASAV19 — un appel journalisé (hors « non joint ») est une réponse
        # réelle au client : pose la première réponse (une seule fois).
        if issue != 'non_joint':
            from .services import poser_premiere_reponse
            poser_premiere_reponse(ticket)
        return Response({
            'id': entree.pk, 'kind': entree.kind, 'body': entree.body,
            'issue': entree.outcome, 'duree_minutes': entree.duree_minutes,
            'created_at': entree.created_at,
        }, status=201)

    @extend_schema(
        request=_sch('SavRepondreEmailRequete', {
            'corps': _CharF(),
            'sujet': _CharF(required=False, allow_blank=True),
            'destinataire': _CharF(required=False, allow_blank=True),
        }),
        responses={201: _sch('SavRepondreEmailReponse', {
            'id': drf_serializers.IntegerField(),
            'message_id': _CharF(allow_blank=True, allow_null=True),
            'thread_root': _CharF(allow_blank=True, allow_null=True),
            'destinataire': _CharF(allow_blank=True, allow_null=True),
            'sujet': _CharF(allow_blank=True, allow_null=True),
        })})
    @action(detail=True, methods=['post'], url_path='repondre-email',
            permission_classes=[
                HasPermissionOrLegacy('sav_repondre_client_externe')])
    def repondre_email(self, request, pk=None):
        """NTSRV1 — Répond au client par e-mail DEPUIS le ticket.

        NTSRV40 — écrire AU CLIENT est un geste distinct de « travailler le
        ticket » : la garde est ``sav_repondre_client_externe``, pas
        ``sav_gerer``. Un agent en formation garde l'assignation et les notes
        INTERNES (``noter``) mais ne peut rien envoyer à l'extérieur. Le code
        est accordé par défaut à tous les rôles système qui portaient déjà
        ``sav_gerer`` : aucun accès existant n'est retiré. Le futur envoi
        WhatsApp (NTSRV3) devra porter la MÊME garde.

        Le message sortant reprend les en-têtes de fil (``In-Reply-To`` /
        ``References``) du dernier e-mail entrant : la réponse du client
        revient sur le MÊME ticket. Sans clé fournisseur configurée, l'envoi
        retombe sur le backend console (no-op réseau silencieux) — le fil est
        journalisé dans tous les cas."""
        ticket = self.get_object()
        from .services import repondre_par_email

        try:
            ligne = repondre_par_email(
                ticket,
                corps=request.data.get('corps'),
                sujet=(request.data.get('sujet') or '').strip(),
                destinataire=(request.data.get('destinataire') or '').strip(),
                user=request.user)
        except ValueError as exc:
            champ, _, detail = str(exc).partition(': ')
            return Response({champ: detail or str(exc)}, status=400)
        # ASAV19 — un e-mail envoyé au client pose la première réponse.
        from .services import poser_premiere_reponse
        poser_premiere_reponse(ticket)
        return Response({
            'id': ligne.pk, 'message_id': ligne.message_id,
            'thread_root': ligne.thread_root,
            'destinataire': ligne.destinataire, 'sujet': ligne.sujet,
        }, status=201)

    @extend_schema(responses=_sch('SavEmailLigne', {
        'id': drf_serializers.IntegerField(),
        'direction': _CharF(),
        'message_id': _CharF(allow_blank=True, allow_null=True),
        'thread_root': _CharF(allow_blank=True, allow_null=True),
        'expediteur': _CharF(allow_blank=True, allow_null=True),
        'destinataire': _CharF(allow_blank=True, allow_null=True),
        'sujet': _CharF(allow_blank=True, allow_null=True),
        'corps': _CharF(allow_blank=True, allow_null=True),
        'date_reception': drf_serializers.DateTimeField(allow_null=True),
    }, many=True))
    @action(detail=True, methods=['get'], url_path='emails',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def emails(self, request, pk=None):
        """NTSRV1 — Fil e-mail complet du ticket (entrants + sortants),
        ordonné du plus ancien au plus récent. Aucun champ interne (coût,
        prix d'achat) n'y figure."""
        ticket = self.get_object()
        lignes = ticket.emails.all().order_by('date_reception', 'id')
        return Response([{
            'id': ligne.pk, 'direction': ligne.direction,
            'message_id': ligne.message_id, 'thread_root': ligne.thread_root,
            'expediteur': ligne.expediteur, 'destinataire': ligne.destinataire,
            'sujet': ligne.sujet, 'corps': ligne.corps_brut,
            'date_reception': ligne.date_reception,
        } for ligne in lignes])

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def rapport_pdf(self, request, pk=None):
        """Rapport d'intervention SAV (N45) — PDF régénéré à la demande.

        Aucun prix d'achat / marge n'y figure. Disponible sur tout ticket."""
        ticket = self.get_object()
        pdf_bytes = rapport_intervention_pdf(ticket)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="rapport-intervention-{ticket.reference}.pdf"')
        return resp

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'], url_path='fiche-pdf',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def fiche_pdf(self, request, pk=None):
        """NTSRV28 — Fiche de synthèse INTERNE du ticket (PDF WeasyPrint).

        Historique complet (chatter), feuille de maintenance, cause/remède,
        pièces utilisées et signature client si présente. Destinée au
        classeur d'intervention et à la transmission assurance/garantie —
        JAMAIS un document commercial : aucun prix d'achat, aucune marge,
        aucun coût interne n'y figure (verrouillé par un test)."""
        ticket = self.get_object()
        pdf_bytes = fiche_synthese_ticket_pdf(ticket)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="fiche-ticket-{ticket.reference}.pdf"')
        return resp

    @extend_schema(
        methods=['GET'], request=None,
        responses=PieceConsommeeSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=_sch('SavPieceConsommeeRequete', {
            'produit': drf_serializers.IntegerField(),
            'quantite': drf_serializers.DecimalField(
                max_digits=12, decimal_places=2, required=False),
            'decrement': drf_serializers.BooleanField(required=False),
        }),
        responses={201: PieceConsommeeSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='pieces',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def pieces(self, request, pk=None):
        """N46 — pièces consommées sur le ticket. GET liste, POST ajoute.

        Sur ajout, `decrement` (vrai) décrémente le stock (MouvementStock
        SORTIE, jamais en double). Les prix d'achat restent internes : ils
        n'apparaissent jamais ici ni sur le rapport d'intervention."""
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.pieces.select_related('produit')
            return Response(PieceConsommeeSerializer(qs, many=True).data)
        from apps.stock.selectors import (
            get_produit_or_raise, produit_does_not_exist,
        )
        from apps.stock.services import (
            mouvement_type_sortie, record_stock_movement,
        )
        try:
            quantite = Decimal(str(request.data.get('quantite') or '1'))
        except (InvalidOperation, TypeError):
            return Response({'detail': 'Quantité invalide.'}, status=400)
        if quantite <= 0:
            return Response({'detail': 'Quantité invalide.'}, status=400)
        try:
            produit = get_produit_or_raise(
                ticket.company, request.data.get('produit'))
        except (produit_does_not_exist(), ValueError, TypeError):
            return Response({'detail': 'Produit inconnu.'}, status=404)
        decrement = str(request.data.get('decrement') or '') in (
            '1', 'true', 'True', 'on')
        if decrement:
            # ERR80 — garde plancher : ne jamais piloter le stock en négatif.
            # On bloque le décrément qui dépasserait le stock en main.
            produit.refresh_from_db()
            if quantite > produit.quantite_stock:
                return Response(
                    {'detail': 'Stock insuffisant : '
                     f'{produit.quantite_stock} en main, {quantite} demandé(s).'},
                    status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            piece = PieceConsommee.objects.create(
                company=ticket.company, ticket=ticket, produit=produit,
                quantite=quantite, created_by=request.user)
            if decrement:
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant - quantite
                record_stock_movement(
                    company=ticket.company, produit=produit,
                    type_mouvement=mouvement_type_sortie(),
                    quantite=quantite, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=ticket.reference,
                    note=f'Consommation SAV {ticket.reference}',
                    created_by=request.user)
                piece.stock_decremente = True
                piece.save(update_fields=['stock_decremente'])
            # L310 — journaliser l'ajout (et le décrément éventuel) à l'Historique.
            suffixe = ' (stock −)' if decrement else ''
            activity.log_note(
                ticket, request.user,
                f'Pièce {produit.nom} ×{quantite} consommée{suffixe}')
        return Response(
            PieceConsommeeSerializer(piece).data, status=201)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=['delete'],
            url_path=r'pieces/(?P<piece_id>[^/.]+)',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def supprimer_piece(self, request, pk=None, piece_id=None):
        """Retire une pièce du ticket ; si le stock avait été décrémenté, le
        ré-incrémente (MouvementStock ENTRÉE) pour rester cohérent."""
        ticket = self.get_object()
        from apps.stock.services import (
            mouvement_type_entree, record_stock_movement,
        )
        try:
            piece = ticket.pieces.select_related('produit').get(pk=piece_id)
        except (PieceConsommee.DoesNotExist, ValueError):
            return Response({'detail': 'Introuvable.'}, status=404)
        with transaction.atomic():
            if piece.stock_decremente:
                produit = piece.produit
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + piece.quantite
                record_stock_movement(
                    company=ticket.company, produit=produit,
                    type_mouvement=mouvement_type_entree(),
                    quantite=piece.quantite, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=ticket.reference,
                    note=f'Annulation pièce SAV {ticket.reference}',
                    created_by=request.user)
            # L310 — journaliser le retrait (et la ré-incrémentation éventuelle).
            suffixe = ' (stock +)' if piece.stock_decremente else ''
            nom = getattr(piece.produit, 'nom', '?')
            qte = piece.quantite
            activity.log_note(
                ticket, request.user,
                f'Pièce {nom} ×{qte} retirée{suffixe}')
            piece.delete()
        return Response(status=204)

    @extend_schema(
        methods=['GET'], request=None,
        responses=PieceRetireeSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=_sch('SavPieceRetireeRequete', {
            'produit': drf_serializers.IntegerField(),
            'quantite': drf_serializers.DecimalField(
                max_digits=12, decimal_places=2, required=False),
            'numero_serie': _CharF(required=False, allow_blank=True),
            'destination': _CharF(required=False),
            'operation': _CharF(required=False),
            'serie_neuve': _CharF(required=False, allow_blank=True),
            'produit_neuf': drf_serializers.IntegerField(required=False),
        }),
        responses={201: PieceRetireeSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='pieces-retirees',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def pieces_retirees(self, request, pk=None):
        """XMFG10 — pièces RETIRÉES du ticket (onduleur remplacé, pompe HS…).

        GET liste, POST trace un retrait avec sa `destination` (rebut /
        retour_fournisseur / stock_occasion) via `services.retirer_piece`."""
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.pieces_retirees.select_related('produit')
            return Response(PieceRetireeSerializer(qs, many=True).data)
        from apps.stock.selectors import (
            get_produit_or_raise, produit_does_not_exist,
        )
        from .services import (
            EquipementDejaRemplaceError, OperationDestinationIncoherenteError,
            RetraitHorsPerimetreError, RetraitProduitIncoherentError,
            SerieNeuveDejaAuParcError, retirer_piece,
        )
        try:
            quantite = Decimal(str(request.data.get('quantite') or '1'))
        except (InvalidOperation, TypeError):
            return Response({'detail': 'Quantité invalide.'}, status=400)
        if quantite <= 0:
            return Response({'detail': 'Quantité invalide.'}, status=400)
        try:
            produit = get_produit_or_raise(
                ticket.company, request.data.get('produit'))
        except (produit_does_not_exist(), ValueError, TypeError):
            return Response({'detail': 'Produit inconnu.'}, status=404)
        destination = request.data.get('destination') or PieceRetiree.Destination.REBUT
        if destination not in PieceRetiree.Destination.values:
            return Response({'detail': 'Destination invalide.'}, status=400)
        # ZMFG8 — typage opérationnel explicite (retrait/recyclage).
        operation = request.data.get('operation') or PieceRetiree.Operation.RETRAIT
        if operation not in PieceRetiree.Operation.values:
            return Response({'detail': 'Opération invalide.'}, status=400)
        numero_serie = (request.data.get('numero_serie') or '').strip()
        # ASAV9 — ``serie_neuve`` (optionnel) : l'appareil neuf entre au parc.
        serie_neuve = (request.data.get('serie_neuve') or '').strip()
        if serie_neuve:
            from .models import Equipement
            if Equipement.objects.filter(
                    company=ticket.company,
                    numero_serie=serie_neuve).exists():
                return Response(
                    {'serie_neuve': ['Ce numéro de série est déjà au parc.']},
                    status=400)
            if not numero_serie or not Equipement.objects.filter(
                    company=ticket.company,
                    numero_serie=numero_serie).exists():
                return Response(
                    {'serie_neuve': ["Le numéro de série de l'appareil "
                                     'remplacé doit exister au parc.']},
                    status=400)
        equipement_neuf = None
        try:
            with transaction.atomic():
                piece = retirer_piece(
                    company=ticket.company, ticket=ticket, produit=produit,
                    quantite=quantite, numero_serie=numero_serie,
                    destination=destination, operation=operation,
                    user=request.user)
                if serie_neuve and piece.equipement_remplace is not None:
                    from .services import remplacer_equipement
                    produit_neuf = produit
                    if request.data.get('produit_neuf'):
                        try:
                            produit_neuf = get_produit_or_raise(
                                ticket.company,
                                request.data.get('produit_neuf'))
                        except (produit_does_not_exist(), ValueError,
                                TypeError):
                            raise _ProduitNeufInconnu()
                    equipement_neuf = remplacer_equipement(
                        ticket=ticket, ancien=piece.equipement_remplace,
                        produit_neuf=produit_neuf, serie_neuve=serie_neuve,
                        date_pose=timezone.localdate(), user=request.user)
        except _ProduitNeufInconnu:
            return Response({'produit_neuf': ['Produit inconnu.']},
                            status=404)
        except SerieNeuveDejaAuParcError as exc:
            return Response({'serie_neuve': [str(exc)]}, status=400)
        except OperationDestinationIncoherenteError as exc:
            return Response({'detail': str(exc)}, status=400)
        # ASAV8 — retrait borné au périmètre du ticket, une fois par équipement.
        except RetraitHorsPerimetreError as exc:
            return Response({'numero_serie': [str(exc)]}, status=400)
        except RetraitProduitIncoherentError as exc:
            return Response({'produit': [str(exc)]}, status=400)
        except EquipementDejaRemplaceError as exc:
            return Response({'detail': str(exc)}, status=409)
        suffixe = {
            PieceRetiree.Destination.STOCK_OCCASION: ' (stock occasion +)',
            PieceRetiree.Destination.RETOUR_FOURNISSEUR: ' (RMA)',
            PieceRetiree.Destination.REBUT: ' (rebut)',
        }.get(destination, '')
        activity.log_note(
            ticket, request.user,
            f'Pièce {produit.nom} ×{quantite} retirée{suffixe}')
        data = dict(PieceRetireeSerializer(piece).data)
        data['equipement_neuf'] = None if equipement_neuf is None else {
            'id': equipement_neuf.id,
            'numero_serie': equipement_neuf.numero_serie,
            'statut': equipement_neuf.statut,
            'installation': equipement_neuf.installation_id,
            'client': equipement_neuf.client_vente_id,
        }
        return Response(data, status=201)

    @extend_schema(responses=_sch('SavPiecesUnifiees', {}, extra=True))
    @action(detail=True, methods=['get'], url_path='pieces-unifiees',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def pieces_unifiees(self, request, pk=None):
        """ZMFG8 — Affichage unifié Ajout/Retrait/Recyclage des pièces du
        ticket (`PieceConsommee` + `PieceRetiree`), avec sous-totaux."""
        from .selectors import pieces_unifiees as _pieces_unifiees

        ticket = self.get_object()
        return Response(_pieces_unifiees(ticket))

    @extend_schema(
        request=_sch('SavFacturerRequeteA', {
            'override': drf_serializers.BooleanField(required=False)}),
        responses={201: _sch('SavFacturerReponseA', {
            'facture_id': drf_serializers.IntegerField(),
            'facture_reference': _CharF(),
            'couverture': _CharF(),
            'sous_garantie': drf_serializers.BooleanField(),
        })})
    @action(detail=True, methods=['post'], url_path='generer-facture',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def generer_facture(self, request, pk=None):
        """XFSM1 — génère une facture BROUILLON depuis un ticket SAV hors
        garantie : lignes pièces (PieceConsommee, prix de vente catalogue) +
        ligne main-d'œuvre (heures_main_oeuvre × taux_horaire_sav société).

        Un ticket sous garantie (calculé ou couvert par un contrat actif)
        génère les mêmes lignes mais à 0 DH, marquées « couvert ». Idempotent
        (réutilise ``facture_id_ext`` si déjà posé) — jamais de double
        facture. Facture = PDF legacy (jamais /proposal, réservé aux devis
        client-facing — règle #4 CLAUDE.md)."""
        # ASAV2 — alias de ``facturer`` : même service de décision.
        return self._facturer_ticket(request, self.get_object())

    @extend_schema(
        request=_sch('SavFacturerRequeteB', {
            'override': drf_serializers.BooleanField(required=False)}),
        responses={201: _sch('SavFacturerReponseB', {
            'facture_id': drf_serializers.IntegerField(),
            'facture_reference': _CharF(),
            'couverture': _CharF(),
            'sous_garantie': drf_serializers.BooleanField(),
        })})
    @action(detail=True, methods=['post'], url_path='facturer',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def facturer(self, request, pk=None):
        """XCTR4 — Facture CE ticket selon le routage de couverture calculé
        (garantie/contrat de maintenance/facturable).

        POST /sav/tickets/{id}/facturer/

        Réutilise EXACTEMENT ``generer_facture_ticket_sav`` (XFSM1) : garantie
        et contrat (avec quota non épuisé) produisent une facture à 0 DH
        (« couvert »), facturable produit la facture réelle au prix de vente
        catalogue (jamais ``prix_achat`` — pièces au prix VENTE uniquement).
        Idempotent (réutilise ``facture_id_ext`` si déjà posé). Renvoie aussi
        la couverture retenue pour cette facturation."""
        return self._facturer_ticket(request, self.get_object())

    def _facturer_ticket(self, request, ticket):
        """ASAV2 — corps commun de ``facturer`` et ``generer-facture`` : la
        décision « qui paie » vient de ``services.decision_facturation``."""
        from apps.ventes.services import generer_facture_ticket_sav
        from .services import decision_facturation

        # XFSM15 — récidive : refus 403 sans ``override`` d'un responsable.
        override = str(request.data.get('override') or '') in (
            '1', 'true', 'True', 'on')
        decision = decision_facturation(ticket, request.user, override)
        if decision['refuse']:
            return Response({'detail': decision['detail']},
                            status=decision['http'])
        couverture = decision['couverture']
        sous_garantie = decision['couvert']
        pieces = list(ticket.pieces.select_related('produit'))
        facture = generer_facture_ticket_sav(
            ticket=ticket, sous_garantie=sous_garantie, pieces=pieces,
            user=request.user)
        activity.log_note(
            ticket, request.user,
            f'Facture {facture.reference} générée depuis le ticket '
            f'(couverture : {couverture}).')
        return Response({
            'facture_id': facture.id,
            'facture_reference': facture.reference,
            'couverture': couverture,
            'sous_garantie': sous_garantie,
        }, status=201)

    @extend_schema(
        request=_sch('SavPlanifierInterventionRequete', {
            'type_intervention': _CharF(required=False)}),
        responses={201: _sch('SavPlanifierInterventionReponse', {
            'intervention_id': drf_serializers.IntegerField(),
            'ticket_statut': _CharF(),
        })})
    @action(detail=True, methods=['post'], url_path='planifier-intervention',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def planifier_intervention(self, request, pk=None):
        """YSERV2 — crée une Intervention pré-remplie (apps.installations)
        depuis ce ticket, EN UN CLIC, et passe le ticket en PLANIFIE.

        POST /sav/tickets/{id}/planifier-intervention/
        body optionnel : {type_intervention: 'depanning'|'controle'|...}

        Refuse proprement (400) si le ticket n'a pas de chantier lié — rien
        à planifier sans installation. Écrit via
        ``apps.installations.services`` (frontière cross-app, jamais un
        import du modèle ``Intervention``)."""
        ticket = self.get_object()
        from apps.installations.services import (
            TicketSansInstallationError, creer_intervention_depuis_ticket,
        )
        try:
            interv = creer_intervention_depuis_ticket(
                ticket=ticket, user=request.user, company=ticket.company,
                type_intervention=request.data.get('type_intervention'))
        except TicketSansInstallationError as exc:
            return Response({'detail': str(exc)}, status=400)
        # AUD514 — le passage NOUVEAU → PLANIFIE passe par la machine d'états
        # gardée (``machine_etats``), plus par une écriture directe qui
        # court-circuitait le graphe. La transition est dans le graphe normal ;
        # un refus (statut inattendu) laisse simplement le ticket en l'état —
        # l'intervention, elle, est déjà créée.
        if ticket.statut == Ticket.Statut.NOUVEAU:
            # ASAV12 — même service unique que les actions de statut.
            from .services import (
                TransitionTicketRefusee, appliquer_transition_ticket,
            )
            try:
                appliquer_transition_ticket(
                    ticket, Ticket.Statut.PLANIFIE, request.user,
                    request=request)
            except TransitionTicketRefusee:
                import logging
                logging.getLogger(__name__).warning(
                    'sav: planifier_intervention — transition NOUVEAU → '
                    'PLANIFIE refusée sur le ticket #%s', ticket.pk)
        activity.log_note(
            ticket, request.user,
            f'Intervention #{interv.id} planifiée depuis le ticket.')
        return Response({
            'intervention_id': interv.id,
            'ticket_statut': ticket.statut,
        }, status=201)

    @extend_schema(
        methods=['GET'], request=None,
        responses=PretEquipementSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=_sch('SavPretEquipementRequete', {
            'produit': drf_serializers.IntegerField(),
            'date_sortie': drf_serializers.DateField(required=False),
            'date_retour_prevue': drf_serializers.DateField(required=False),
            'numero_serie': _CharF(required=False, allow_blank=True),
        }),
        responses={201: PretEquipementSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='prets-equipement',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def prets_equipement(self, request, pk=None):
        """XSAV27 — prêt/échange anticipé d'équipement (loaner). GET liste,
        POST sort une unité du stock immédiatement (`services.
        creer_pret_equipement`, jamais de stock négatif)."""
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.prets_equipement.select_related('produit')
            return Response(PretEquipementSerializer(qs, many=True).data)
        from datetime import date as _date

        from apps.stock.selectors import (
            get_produit_or_raise, produit_does_not_exist,
        )
        from .services import PretEquipementError, creer_pret_equipement
        try:
            produit = get_produit_or_raise(
                ticket.company, request.data.get('produit'))
        except (produit_does_not_exist(), ValueError, TypeError):
            return Response({'detail': 'Produit inconnu.'}, status=404)

        def _parse_date(raw):
            if not raw:
                return None
            if isinstance(raw, _date):
                return raw
            try:
                return _date.fromisoformat(str(raw))
            except ValueError:
                return None

        date_sortie = _parse_date(request.data.get('date_sortie')) or (
            timezone.localdate())
        date_retour_prevue = _parse_date(
            request.data.get('date_retour_prevue'))
        numero_serie = (request.data.get('numero_serie') or '').strip()
        try:
            with transaction.atomic():
                pret = creer_pret_equipement(
                    company=ticket.company, ticket=ticket, produit=produit,
                    numero_serie=numero_serie, date_sortie=date_sortie,
                    date_retour_prevue=date_retour_prevue, user=request.user)
        except PretEquipementError as exc:
            return Response({'detail': str(exc)}, status=400)
        activity.log_note(
            ticket, request.user,
            f'Prêt équipement {produit.nom} sorti (retour prévu : '
            f'{date_retour_prevue or "non renseigné"}).')
        return Response(PretEquipementSerializer(pret).data, status=201)

    @extend_schema(
        request=_sch('SavRetournerPretRequete', {
            'date_retour_reelle': drf_serializers.DateField(required=False)}),
        responses=PretEquipementSerializer)
    @action(detail=True, methods=['post'],
            url_path=r'prets-equipement/(?P<pret_id>[^/.]+)/retourner',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def retourner_pret(self, request, pk=None, pret_id=None):
        """XSAV27 — clôture un prêt : réintègre le stock (idempotent)."""
        ticket = self.get_object()
        from .models import PretEquipement
        from .services import retourner_pret_equipement
        try:
            pret = ticket.prets_equipement.select_related('produit').get(
                pk=pret_id)
        except (PretEquipement.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Introuvable.'}, status=404)
        from datetime import date as _date
        raw_date_retour = request.data.get('date_retour_reelle')
        if raw_date_retour and not isinstance(raw_date_retour, _date):
            try:
                raw_date_retour = _date.fromisoformat(str(raw_date_retour))
            except ValueError:
                raw_date_retour = None
        date_retour = raw_date_retour or timezone.localdate()
        with transaction.atomic():
            pret = retourner_pret_equipement(
                pret=pret, date_retour_reelle=date_retour, user=request.user)
        activity.log_note(
            ticket, request.user,
            f'Prêt équipement {pret.produit.nom} retourné.')
        return Response(PretEquipementSerializer(pret).data, status=200)

    @extend_schema(responses=_sch('SavTriageIa', {}, extra=True))
    @action(detail=True, methods=['get'], url_path='triage-ia',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def triage_ia(self, request, pk=None):
        """XSAV28 — triage IA du ticket (clé-gated, propose→confirme).
        Suggestions JAMAIS auto-appliquées : GET pur, rien n'est écrit sur le
        ticket. Sans GROQ_API_KEY, renvoie ``{'disponible': False}`` (200,
        comportement actuel byte-identique)."""
        ticket = self.get_object()
        from .services import suggerer_triage_ticket
        result = suggerer_triage_ticket(
            company=ticket.company, description=ticket.description)
        return Response(result)

    @extend_schema(
        request=None,
        responses={200: _CreerLeadReponse, 201: _CreerLeadReponse})
    @action(detail=True, methods=['post'], url_path='creer-lead',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def creer_lead(self, request, pk=None):
        """ZSAV8 — convertit un ticket en opportunité CRM (upsell/
        remplacement). Écrit via `apps.crm.services.create_lead_depuis_ticket`
        (jamais un import direct des modèles crm). Idempotent : réutilise un
        lead OUVERT existant du même client plutôt que d'en créer un second."""
        ticket = self.get_object()
        from apps.crm.services import create_lead_depuis_ticket
        # Le contexte (référence + description du ticket) est tracé sur le
        # chatter du lead. `create_lead_depuis_ticket` attribue cette note au
        # SYSTÈME (user=None), donc le récepteur QJ7 ne fait PAS avancer le
        # lead hors du stade NEW attendu par ZSAV8.
        contexte = (
            f'Créé depuis le ticket SAV {ticket.reference}'
            + (f' : {ticket.description}' if ticket.description else ''))
        lead, created = create_lead_depuis_ticket(
            company=ticket.company, user=request.user, client=ticket.client,
            contexte=contexte)
        if ticket.lead_id_ext != lead.id:
            ticket.lead_id_ext = lead.id
            ticket.save(update_fields=['lead_id_ext'])
        suffixe = 'créé' if created else 'existant réutilisé'
        activity.log_note(
            ticket, request.user, f'Lead CRM #{lead.id} {suffixe}.')
        return Response(
            {'lead_id': lead.id, 'created': created},
            status=201 if created else 200)

    @extend_schema(
        methods=['GET'], request=None,
        responses=TicketChecklistItemSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=_sch('SavChecklistInitRequete', {
            'template_id': drf_serializers.IntegerField()}),
        responses={
            200: TicketChecklistItemSerializer(many=True),
            201: TicketChecklistItemSerializer(many=True)})
    @extend_schema(
        methods=['PATCH'],
        request=_sch('SavChecklistMajRequete', {
            'cle': _CharF(),
            'coche': drf_serializers.BooleanField(required=False),
            'note': _CharF(required=False, allow_blank=True, allow_null=True),
        }),
        responses=TicketChecklistItemSerializer)
    @action(detail=True, methods=['get', 'post', 'patch'],
            url_path='checklist',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def checklist(self, request, pk=None):
        """FG82 — Checklist de visite de maintenance sur le ticket.

        GET : liste les items cochés/non cochés.
        POST : initialise depuis un template (body: {template_id: N}) ;
               idempotent (ne duplique pas si déjà initialisée).
        PATCH : met à jour un item (body: {cle: 'X', coche: true, note: '…'}).
        """
        ticket = self.get_object()
        if request.method == 'GET':
            items = ticket.checklist_items.order_by('ordre', 'cle')
            return Response(TicketChecklistItemSerializer(items, many=True).data)

        if request.method == 'POST':
            template_id = request.data.get('template_id')
            if not template_id:
                return Response({'detail': 'template_id requis.'}, status=400)
            try:
                tmpl = MaintenanceChecklistTemplate.objects.get(
                    pk=template_id, company=ticket.company)
            except MaintenanceChecklistTemplate.DoesNotExist:
                return Response({'detail': 'Template introuvable.'}, status=404)
            created = 0
            for item in tmpl.items.filter(actif=True):
                _, is_new = TicketChecklistItem.objects.get_or_create(
                    ticket=ticket, cle=item.cle,
                    defaults={
                        'company': ticket.company,
                        'libelle': item.libelle,
                        'ordre': item.ordre,
                    })
                if is_new:
                    created += 1
            items = ticket.checklist_items.order_by('ordre', 'cle')
            return Response(TicketChecklistItemSerializer(items, many=True).data,
                            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        # PATCH — mise à jour d'un item
        cle = request.data.get('cle')
        if not cle:
            return Response({'detail': 'cle requis.'}, status=400)
        try:
            item = ticket.checklist_items.get(cle=cle)
        except TicketChecklistItem.DoesNotExist:
            return Response({'detail': 'Item introuvable.'}, status=404)
        if 'coche' in request.data:
            item.coche = bool(request.data['coche'])
            if item.coche:
                item.coche_par = request.user
                item.date_coche = timezone.now()
            else:
                item.coche_par = None
                item.date_coche = None
        if 'note' in request.data:
            item.note = request.data['note'] or ''
        item.save()
        return Response(TicketChecklistItemSerializer(item).data)

    @extend_schema(
        methods=['GET'], request=None, responses=TicketWorksheetSerializer)
    @extend_schema(
        methods=['POST'],
        request=_sch('SavWorksheetInitRequete', {
            'modele_id': drf_serializers.IntegerField()}),
        responses={200: TicketWorksheetSerializer, 201: TicketWorksheetSerializer})
    @extend_schema(
        methods=['PATCH'],
        request=_sch('SavWorksheetMajRequete', {
            'valeurs': drf_serializers.DictField(required=False),
            'complete': drf_serializers.BooleanField(required=False),
        }),
        responses=TicketWorksheetSerializer)
    @action(detail=True, methods=['get', 'post', 'patch'],
            url_path='worksheet',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def worksheet(self, request, pk=None):
        """ZMFG6 — Feuille de maintenance (worksheet) remplie sur le ticket.

        GET : renvoie la feuille existante (404 si aucune).
        POST : crée la feuille depuis un modèle (body: {modele_id: N}) ;
               idempotent (renvoie l'existante si déjà créée, jamais deux
               feuilles sur le même ticket — OneToOne).
        PATCH : met à jour les valeurs (body: {valeurs: {...}}) et/ou
               marque complétée (body: {complete: true}) — refuse (400) si
               un champ requis du modèle manque encore.
        Gaté par ``SavSlaSettings.worksheets_maintenance_actifs`` (défaut
        OFF) : 404 tant que la société n'a pas activé la fonctionnalité."""
        ticket = self.get_object()
        sla = SavSlaSettings.get(ticket.company)
        if not sla.worksheets_maintenance_actifs:
            return Response(
                {'detail': 'Feuilles de maintenance non activées pour cette société.'},
                status=404)

        if request.method == 'GET':
            worksheet = getattr(ticket, 'worksheet', None)
            if worksheet is None:
                return Response({'detail': 'Aucune feuille sur ce ticket.'}, status=404)
            return Response(TicketWorksheetSerializer(worksheet).data)

        if request.method == 'POST':
            existing = getattr(ticket, 'worksheet', None)
            if existing is not None:
                return Response(TicketWorksheetSerializer(existing).data, status=200)
            modele_id = request.data.get('modele_id')
            if not modele_id:
                return Response({'detail': 'modele_id requis.'}, status=400)
            try:
                modele = WorksheetMaintenanceModele.objects.get(
                    pk=modele_id, company=ticket.company)
            except WorksheetMaintenanceModele.DoesNotExist:
                return Response({'detail': 'Modèle introuvable.'}, status=404)
            worksheet = TicketWorksheet.objects.create(
                company=ticket.company, ticket=ticket, modele=modele)
            return Response(
                TicketWorksheetSerializer(worksheet).data, status=201)

        # PATCH — mise à jour des valeurs / complétion.
        worksheet = getattr(ticket, 'worksheet', None)
        if worksheet is None:
            return Response({'detail': 'Aucune feuille sur ce ticket.'}, status=404)
        if 'valeurs' in request.data:
            valeurs = dict(worksheet.valeurs or {})
            valeurs.update(request.data['valeurs'] or {})
            worksheet.valeurs = valeurs
            worksheet.save(update_fields=['valeurs'])
        if request.data.get('complete'):
            try:
                worksheet.marquer_complete(request.user)
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=400)
        return Response(TicketWorksheetSerializer(worksheet).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='attente-client',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def attente_client(self, request, pk=None):
        """XSAV5 — Démarre la pause « en attente client » (idempotent).

        Pendant la pause, l'échéance SLA effective (``sla_due_at_effectif``)
        avance d'autant de jours — l'horloge SLA ignore le temps d'attente."""
        ticket = self.get_object()
        if not ticket.en_attente_client:
            ticket.mettre_en_attente_client()
            ticket.save(update_fields=['en_attente_client', 'attente_depuis'])
            activity.log_note(ticket, request.user, 'Mis en attente client')
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='reprendre',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def reprendre(self, request, pk=None):
        """XSAV5 — Clôt la pause « en attente client » (idempotent).

        Cumule la durée de la pause dans ``jours_pause`` puis recalcule
        ``sla_breach`` avec la nouvelle échéance effective."""
        ticket = self.get_object()
        if ticket.en_attente_client:
            ticket.reprendre_apres_attente()
            ticket.save(update_fields=[
                'en_attente_client', 'attente_depuis', 'jours_pause'])
            ticket.recompute_sla_breach()
            ticket.save(update_fields=['sla_breach'])
            activity.log_note(ticket, request.user, "Reprise après attente client")
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @extend_schema(request=_sch('SavFusionnerRequete', {
        'doublon_id': drf_serializers.IntegerField()}), responses=_sch(
            'SavFusionnerReponse', {}, extra=True))
    @action(detail=True, methods=['post'], url_path='fusionner',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def fusionner(self, request, pk=None):
        """XSAV12 — Fusionne un ticket doublon dans ce ticket (principal).

        Body : ``{'doublon_id': N}`` — même société obligatoire (cross-tenant
        → 404 comme le reste de l'API, via ``get_object``/filtre société).
        Déplace vers le PRINCIPAL : activités (TicketActivity), pièces
        consommées (PieceConsommee), items de checklist (TicketChecklistItem)
        et pièces jointes (records.Attachment via ContentType). Le doublon
        est marqué ``annule`` avec motif « Doublon de {reference} » et des
        notes croisées sont ajoutées aux DEUX chatters : celle du principal
        avant le déplacement, celle du doublon APRÈS (sinon elle repartirait
        elle-même vers le principal avec le reste de ses activités
        déplacées, et le chatter du doublon perdrait toute trace de la
        fusion)."""
        principal = self.get_object()
        doublon_id = request.data.get('doublon_id')
        if not doublon_id:
            return Response({'detail': 'doublon_id requis.'}, status=400)
        try:
            doublon_id = int(doublon_id)
        except (TypeError, ValueError):
            return Response({'detail': 'doublon_id invalide.'}, status=400)
        if doublon_id == principal.pk:
            return Response(
                {'detail': "Un ticket ne peut pas être fusionné avec lui-même."},
                status=status.HTTP_400_BAD_REQUEST)

        # ASAV25 — le doublon doit être VISIBLE par l'utilisateur (sinon sa
        # fusion transférerait son chatter vers un ticket qu'il voit).
        doublon = _tickets_visibles(request).filter(
            pk=doublon_id, company=principal.company).first()
        if doublon is None:
            return Response({'detail': 'Ticket doublon introuvable.'}, status=404)

        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from .models import TicketChecklistItem

        with transaction.atomic():
            # Note sur le principal AVANT le déplacement (elle doit rester
            # dans le chatter du principal, ce qui est trivialement le cas).
            activity.log_note(
                principal, request.user,
                f'Fusion : ticket {doublon.reference} fusionné dans celui-ci')

            doublon.activites.update(ticket=principal, company=principal.company)
            doublon.pieces.update(ticket=principal, company=principal.company)
            TicketChecklistItem.objects.filter(ticket=doublon).update(
                ticket=principal, company=principal.company)
            ct = ContentType.objects.get_for_model(Ticket)
            Attachment.objects.filter(
                content_type=ct, object_id=doublon.pk,
            ).update(object_id=principal.pk, company=principal.company)

            # Note sur le doublon APRÈS le déplacement de ses activités
            # (sinon elle partirait elle-même vers le principal et le
            # chatter du doublon perdrait toute trace de la fusion).
            activity.log_note(
                doublon, request.user,
                f'Ce ticket a été fusionné dans {principal.reference}')

            doublon.annule = True
            doublon.motif_annulation = f'Doublon de {principal.reference}'
            doublon.save(update_fields=['annule', 'motif_annulation'])

        return Response(
            TicketSerializer(principal, context={'request': request}).data)

    @staticmethod
    def _produits_lignes_hors_societe(company, lignes):
        """ASEC35 — résout dans la société du ticket chaque ``produit_id``
        reçu par ``creer-devis`` AVANT le domaine ventes (via le sélecteur
        stock borné société). Renvoie ``{index: {'produit_id': [msg]}}`` —
        un produit d'une autre société et un id inexistant reçoivent la MÊME
        réponse (aucun oracle d'existence) ; ``{}`` si tout est valide."""
        from apps.stock.selectors import valid_produit_ids

        message = "Produit introuvable pour votre société."
        if not isinstance(lignes, list):
            return {'non_field_errors': ['Liste de lignes attendue.']}
        erreurs, a_verifier = {}, {}
        for i, ligne in enumerate(lignes):
            if not isinstance(ligne, dict):
                erreurs[i] = {'non_field_errors': ['Ligne invalide.']}
                continue
            brut = ligne.get('produit_id')
            if brut in (None, ''):
                continue
            try:
                a_verifier[i] = int(brut)
            except (TypeError, ValueError):
                erreurs[i] = {'produit_id': [message]}
        valides = valid_produit_ids(company, set(a_verifier.values()))
        for i, pid in a_verifier.items():
            if pid not in valides:
                erreurs[i] = {'produit_id': [message]}
        return erreurs

    @extend_schema(
        request=_sch('SavCreerDevisRequete', {
            'client_id': drf_serializers.IntegerField(required=False),
            'lignes': drf_serializers.ListField(
                child=drf_serializers.DictField(), required=False),
        }),
        responses={201: _sch('SavCreerDevisReponse', {
            'devis_id': drf_serializers.IntegerField(),
            'devis_reference': _CharF(),
        })})
    @action(detail=True, methods=['post'], url_path='creer-devis',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def creer_devis(self, request, pk=None):
        """XSAV3 — Crée un devis de réparation hors garantie depuis le ticket.

        Refusé si le ticket est sous garantie (constructeur/légale calculée)
        ou couvert par un contrat de maintenance actif — le travail couvert
        ne se facture pas. Pré-rempli depuis les PieceConsommee du ticket,
        valorisées au prix de VENTE catalogue (jamais prix_achat). Écrit via
        ``apps.ventes.services.create_devis_pour_ticket`` (cross-app write,
        jamais d'import direct du modèle ventes)."""
        ticket = self.get_object()
        # ASAV2 — même décision que les deux portes de facture.
        from .services import decision_facturation
        override = str(request.data.get('override') or '') in (
            '1', 'true', 'True', 'on')
        decision = decision_facturation(ticket, request.user, override)
        if decision['refuse']:
            return Response({'detail': decision['detail']},
                            status=decision['http'])
        if decision['couvert']:
            return Response(
                {'detail': 'Ticket couvert (garantie ou contrat) : aucun '
                           "devis de réparation n'est nécessaire."},
                status=status.HTTP_400_BAD_REQUEST)

        from apps.ventes.services import create_devis_pour_ticket

        client_id = request.data.get('client_id') or ticket.client_id
        if not client_id:
            return Response({'detail': 'client_id requis.'}, status=400)

        lignes = request.data.get('lignes')
        if lignes is None:
            # Pré-remplissage depuis les pièces consommées du ticket,
            # valorisées au prix de VENTE catalogue (jamais prix_achat).
            lignes = []
            for piece in ticket.pieces.select_related('produit'):
                produit = piece.produit
                lignes.append({
                    'produit_id': produit.id,
                    'designation': produit.nom,
                    'quantite': piece.quantite,
                    'prix_unitaire': produit.prix_vente,
                })
        else:
            erreurs = self._produits_lignes_hors_societe(ticket.company, lignes)
            if erreurs:
                return Response({'lignes': erreurs},
                                status=status.HTTP_400_BAD_REQUEST)

        try:
            devis = create_devis_pour_ticket(
                company=ticket.company, user=request.user,
                client_id=client_id, lignes=lignes,
                note=f'Devis de réparation SAV — ticket {ticket.reference}')
        except Exception:
            return Response(
                {'detail': 'Client introuvable pour votre société.'},
                status=status.HTTP_404_NOT_FOUND)

        ticket.devis_id_ext = devis.id
        ticket.save(update_fields=['devis_id_ext'])
        activity.log_note(
            ticket, request.user,
            f'Devis de réparation {devis.reference} créé (brouillon)')
        return Response(
            {'devis_id': devis.id, 'devis_reference': devis.reference},
            status=status.HTTP_201_CREATED)

    @extend_schema(responses=_sch('SavLienClientReponse', {
        'token': _CharF(), 'url': _CharF()}))
    @action(detail=True, methods=['get'], url_path='lien-client',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def lien_client(self, request, pk=None):
        """FG86 — Génère (lazily) le lien de suivi public du ticket.

        Retourne l'URL absolue du lien client tokenisé + le jeton brut.
        Le jeton est créé à la première demande ; les appels suivants renvoient
        le même jeton sans régénérer. Aucun cout ni chatter n'est exposé.

        XSAV10/XSAV19 — l'URL pointe vers la page FRONTEND ``/suivi/<token>``
        (statut + CSAT), pas directement l'API JSON (même origine, même
        patron que XSAL17 ``public_booking_url``)."""
        ticket = self.get_object()
        token = ticket.ensure_share_token()
        url = request.build_absolute_uri(f'/suivi/{token}')
        return Response({'token': token, 'url': url})


# ── FG81 — Réglages SLA ────────────────────────────────────────────────────────

@extend_schema_view(list=extend_schema(responses=SavSlaSettingsSerializer))
class SavSlaSettingsViewSet(CompanyScopedModelViewSet):
    """Réglages SLA SAV par société (FG81). Singleton : list renvoie l'unique
    enregistrement ; écriture responsable/admin."""
    queryset = SavSlaSettings.objects.all()
    serializer_class = SavSlaSettingsSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def list(self, request, *args, **kwargs):
        company = request.user.company
        if company is None:
            return Response({})
        obj = SavSlaSettings.get(company)
        return Response(self.get_serializer(obj).data)

    @extend_schema(responses={200: SavSlaSettingsSerializer})
    def create(self, request, *args, **kwargs):
        """Upsert du singleton (PATCH-like via POST)."""
        company = request.user.company
        obj = SavSlaSettings.get(company)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── FG82 — Checklist templates ────────────────────────────────────────────────

class MaintenanceChecklistTemplateViewSet(CompanyScopedModelViewSet):
    """Templates de checklist de maintenance (FG82). Lecture tout rôle."""
    queryset = MaintenanceChecklistTemplate.objects.prefetch_related('items').all()
    serializer_class = MaintenanceChecklistTemplateSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        if getattr(self, 'action', None) == 'list':
            # AGR619 — sème une seule fois « Entretien pompage solaire » à
            # l'affichage des modèles (même patron que seed_checklist_etapes).
            from .services import (
                ensure_modele_entretien_ci, ensure_modele_entretien_pompage,
            )
            company = getattr(self.request.user, 'company', None)
            ensure_modele_entretien_pompage(company)
            # CIQ641 — et « Entretien site professionnel » (C&I), même patron.
            ensure_modele_entretien_ci(company)
        qs = super().get_queryset()
        return qs.filter(actif=True)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def perform_destroy(self, instance):
        if instance.protege:
            raise ValidationError('Ce template est protégé et ne peut être supprimé.')
        instance.delete()


# ── FG83 — Réclamation garantie fournisseur ───────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('equipement', OpenApiTypes.INT, required=False),
        OpenApiParameter('ticket', OpenApiTypes.INT, required=False),
        OpenApiParameter('statut', OpenApiTypes.STR, required=False),
    ]))
class WarrantyClaimViewSet(CompanyScopedModelViewSet):
    """Réclamations garantie fournisseur / flux RMA (FG83).
    Lecture tout rôle ; écriture responsable/admin."""
    queryset = WarrantyClaim.objects.select_related(
        'equipement', 'equipement__produit', 'ticket',
    ).all()
    serializer_class = WarrantyClaimSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['rma_ref', 'description', 'fournisseur_nom_cache']
    ordering_fields = ['date_creation', 'date_signalement', 'statut']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        equipement = self.request.query_params.get('equipement')
        ticket = self.request.query_params.get('ticket')
        statut = self.request.query_params.get('statut')
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        equipement = serializer.validated_data.get('equipement')
        ticket = serializer.validated_data.get('ticket')
        if equipement and equipement.company_id != company.id:
            raise ValidationError({'equipement': 'Équipement inconnu.'})
        if ticket and ticket.company_id != company.id:
            raise ValidationError({'ticket': 'Ticket inconnu.'})

    def _resolve_fournisseur(self, serializer):
        """Résout le nom du fournisseur via stock.selectors (cross-app)."""
        fid = serializer.validated_data.get('fournisseur_id_ext')
        if fid:
            try:
                from apps.stock.selectors import get_fournisseur_by_id
                f = get_fournisseur_by_id(self.request.user.company, fid)
                if f:
                    serializer.validated_data['fournisseur_nom_cache'] = f.nom
            except Exception:
                pass

    @staticmethod
    def _poser_dates_statut(claim):
        """ASAV37 — le serveur pose ``date_envoi_fournisseur`` (envoi) et
        ``date_resolution`` (résolu / refusé) à la transition, si vides
        (date locale Maroc). Éditer un autre champ ne les touche jamais."""
        champs = []
        aujourdhui = timezone.localdate()
        if (claim.statut == WarrantyClaim.Statut.ENVOYE
                and not claim.date_envoi_fournisseur):
            claim.date_envoi_fournisseur = aujourdhui
            champs.append('date_envoi_fournisseur')
        if (claim.statut in (WarrantyClaim.Statut.RESOLU,
                             WarrantyClaim.Statut.REFUSE)
                and not claim.date_resolution):
            claim.date_resolution = aujourdhui
            champs.append('date_resolution')
        if champs:
            claim.save(update_fields=champs)

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        self._resolve_fournisseur(serializer)
        claim = serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)
        self._poser_dates_statut(claim)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        self._resolve_fournisseur(serializer)
        super().perform_update(serializer)
        self._poser_dates_statut(serializer.instance)


# ── FG87 — Base de connaissances SAV ─────────────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('produit', OpenApiTypes.INT, required=False),
        OpenApiParameter('categorie', OpenApiTypes.STR, required=False),
    ]))
class KbArticleViewSet(CompanyScopedModelViewSet):
    """Articles de la base de connaissances SAV (FG87).
    Cherchables par texte libre + filtrables par produit/catégorie."""
    queryset = KbArticle.objects.select_related('produit').all()
    serializer_class = KbArticleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'corps', 'categorie', 'tags']
    ordering_fields = ['date_modification', 'date_creation', 'titre']
    ordering = ['-date_modification']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(actif=True)
        produit = self.request.query_params.get('produit')
        categorie = self.request.query_params.get('categorie')
        if produit:
            qs = qs.filter(produit_id=produit)
        if categorie:
            qs = qs.filter(categorie__icontains=categorie)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)


# ── FG280 — Alarmes / défauts onduleur ────────────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('gravite', OpenApiTypes.STR, required=False),
        OpenApiParameter('statut', OpenApiTypes.STR, required=False),
        OpenApiParameter('equipement', OpenApiTypes.INT, required=False),
    ]))
class AlarmeOnduleurViewSet(CompanyScopedModelViewSet):
    """Alarmes / défauts onduleur (FG280) — DISTINCTES du ticket SAV.

    Cycle de vie propre (active → acquittée → escaladée/résolue) avec
    acquittement (utilisateur + horodatage posés côté serveur) et escalade
    (ouvre/relie un ticket SAV). Lecture tout rôle ; écriture + actions
    responsable/admin. Tout est scopé à la société."""
    queryset = AlarmeOnduleur.objects.select_related(
        'equipement', 'equipement__produit', 'ticket', 'acquittee_par',
    ).all()
    serializer_class = AlarmeOnduleurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle', 'description']
    ordering_fields = [
        'date_creation', 'date_detection', 'gravite', 'statut', 'code',
    ]
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        gravite = params.get('gravite')
        statut = params.get('statut')
        equipement = params.get('equipement')
        if gravite:
            qs = qs.filter(gravite=gravite)
        if statut:
            qs = qs.filter(statut=statut)
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        equipement = serializer.validated_data.get('equipement')
        if equipement is not None and equipement.company_id != company.id:
            raise ValidationError({'equipement': 'Équipement inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        # date_detection par défaut = maintenant si non fournie.
        date_detection = (
            serializer.validated_data.get('date_detection') or timezone.now())
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
            date_detection=date_detection)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)

    @extend_schema(request=None, responses=AlarmeOnduleurSerializer)
    @action(detail=True, methods=['post'], url_path='acquitter',
            permission_classes=[IsResponsableOrAdmin])
    def acquitter(self, request, pk=None):
        """Acquitte l'alarme (« j'ai vu ») — acteur + horodatage côté serveur.

        Idempotent : si déjà acquittée/escaladée/résolue, ne ré-écrit pas
        l'auteur d'acquittement. Ne touche PAS au cycle de vie du ticket."""
        alarme = self.get_object()
        if alarme.statut == AlarmeOnduleur.Statut.ACTIVE:
            alarme.statut = AlarmeOnduleur.Statut.ACQUITTEE
            alarme.acquittee_par = request.user
            alarme.date_acquittement = timezone.now()
            alarme.save(update_fields=[
                'statut', 'acquittee_par', 'date_acquittement',
                'date_modification'])
        return Response(AlarmeOnduleurSerializer(alarme).data)

    @extend_schema(
        request=_sch('SavEscaladerRequete', {
            'ticket': drf_serializers.IntegerField(required=False)}),
        responses=AlarmeOnduleurSerializer)
    @action(detail=True, methods=['post'], url_path='escalader',
            permission_classes=[IsResponsableOrAdmin])
    def escalader(self, request, pk=None):
        """Escalade l'alarme : relie un ticket SAV existant (`ticket` en body)
        ou en ouvre un nouveau (correctif) pour traiter le défaut.

        L'alarme reste l'enregistrement source : son statut passe à
        « escaladée » et porte le lien `ticket`. Le cycle de vie du ticket
        reste indépendant. Idempotent : une alarme déjà escaladée renvoie son
        ticket existant sans en créer un second."""
        alarme = self.get_object()
        company = request.user.company
        if alarme.ticket_id:
            return Response(AlarmeOnduleurSerializer(alarme).data)

        ticket_id = request.data.get('ticket')
        if ticket_id:
            # ASAV25 — résolu par la portée de l'utilisateur.
            ticket = _ticket_visible_du_corps(request, ticket_id)
        else:
            # Ouvre un ticket correctif. Le client/chantier sont déduits de
            # l'équipement lié à l'alarme quand c'est possible.
            equipement = alarme.equipement
            installation = getattr(equipement, 'installation', None)
            client = (getattr(installation, 'client', None)
                      if installation is not None
                      else getattr(equipement, "client_vente", None))  # ASAV40
            if client is None:
                raise ValidationError({
                    'ticket': "Aucun ticket fourni et l'alarme n'a pas "
                              "d'équipement rattaché à un client — précisez "
                              "un ticket existant."})
            description = (
                f'Escalade alarme onduleur {alarme.code} '
                f'({alarme.get_gravite_display()})'
                + (f' : {alarme.libelle}' if alarme.libelle else ''))
            # AUD519 — l'escalade d'alarme pose la même échéance SLA que le
            # chemin manuel (sans quoi le ticket était invisible aux scans).
            from .services import poser_sla_due_at
            ticket = poser_sla_due_at(create_with_reference(
                Ticket, 'SAV', company,
                lambda ref: Ticket.objects.create(
                    reference=ref, company=company,
                    client=client, installation=installation,
                    equipement=equipement,
                    type=Ticket.Type.CORRECTIF,
                    priorite=(
                        Ticket.Priorite.URGENTE
                        if alarme.gravite == AlarmeOnduleur.Gravite.CRITIQUE
                        else Ticket.Priorite.NORMALE),
                    description=description,
                    date_ouverture=timezone.localdate(),
                    created_by=request.user),
            ))
        alarme.ticket = ticket
        alarme.statut = AlarmeOnduleur.Statut.ESCALADEE
        alarme.save(update_fields=['ticket', 'statut', 'date_modification'])
        return Response(AlarmeOnduleurSerializer(alarme).data)


# ── XSAV14 — Taxonomie panne / cause / remède ─────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('archived', OpenApiTypes.STR, required=False, enum=['1']),
    ]))
class CauseDefaillanceViewSet(CompanyScopedModelViewSet):
    """Référentiel des causes de panne (XSAV14). Lecture tout rôle, écriture
    responsable/admin (édité dans Paramètres).

    ARC2 — pilote : base transverse unique (TenantMixin + ModelViewSet). Le
    get_queryset (filtre archived) et perform_create (company forcée serveur)
    SURCHARGENT la base : réponses inchangées."""
    queryset = CauseDefaillance.objects.all()
    serializer_class = CauseDefaillanceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get(
                'archived') != '1':
            qs = qs.filter(archived=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('archived', OpenApiTypes.STR, required=False, enum=['1']),
    ]))
class RemedeDefaillanceViewSet(CompanyScopedModelViewSet):
    """Référentiel des remèdes de panne (XSAV14). Lecture tout rôle, écriture
    responsable/admin (édité dans Paramètres)."""
    queryset = RemedeDefaillance.objects.all()
    serializer_class = RemedeDefaillanceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get(
                'archived') != '1':
            qs = qs.filter(archived=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('actif', OpenApiTypes.STR, required=False, enum=['0']),
    ]))
class CategorieTicketViewSet(CompanyScopedModelViewSet):
    """ZSAV2 — Référentiel de catégorie de ticket (au-delà de correctif/
    préventif). Lecture tout rôle, écriture responsable/admin (édité dans
    Paramètres). Même patron que CauseDefaillance/RemedeDefaillance."""
    queryset = CategorieTicket.objects.all()
    serializer_class = CategorieTicketSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get(
                'actif') == '0':
            qs = qs.filter(actif=False)
        elif self.action == 'list':
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── ZMFG1 — Équipes de maintenance ────────────────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('actif', OpenApiTypes.STR, required=False, enum=['0']),
    ]))
class EquipeMaintenanceViewSet(CompanyScopedModelViewSet):
    """ZMFG1 — CRUD équipe de maintenance, company-scopé. Lecture tout rôle,
    écriture responsable/admin (édité dans Paramètres SAV)."""
    queryset = EquipeMaintenance.objects.prefetch_related('membres').all()
    serializer_class = EquipeMaintenanceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get(
                'actif') == '0':
            qs = qs.filter(actif=False)
        elif self.action == 'list':
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── ZMFG2 — Catégories d'équipement ───────────────────────────────────────────

class CategorieEquipementViewSet(CompanyScopedModelViewSet):
    """ZMFG2 — CRUD catégorie d'équipement, company-scopé. Lecture tout rôle,
    écriture responsable/admin (édité dans Paramètres SAV)."""
    queryset = CategorieEquipement.objects.select_related(
        'responsable', 'equipe_responsable',
    ).annotate(nb_equipements_annote=Count('equipements', distinct=True))
    serializer_class = CategorieEquipementSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── ZMFG6 — Feuilles de maintenance (worksheets) ──────────────────────────────

class WorksheetMaintenanceModeleViewSet(CompanyScopedModelViewSet):
    """ZMFG6 — CRUD modèle de feuille de maintenance, company-scopé (édité
    dans Paramètres SAV). Lecture tout rôle, écriture responsable/admin."""
    queryset = WorksheetMaintenanceModele.objects.all()
    serializer_class = WorksheetMaintenanceModeleSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── XSAV23 — Réponses types (macros) SAV ──────────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('archived', OpenApiTypes.STR, required=False, enum=['1']),
        OpenApiParameter('canal', OpenApiTypes.STR, required=False),
        OpenApiParameter('ticket', OpenApiTypes.INT, required=False),
    ]))
class ReponseTypeViewSet(CompanyScopedModelViewSet):
    """CRUD des réponses types (macros) SAV, company-scoped (Paramètres)."""
    queryset = ReponseType.objects.all()
    serializer_class = ReponseTypeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get(
                'archived') != '1':
            qs = qs.filter(archived=False)
        if self.action == 'list':
            qs = self._filtrer_par_canal(qs)
        return qs

    def _filtrer_par_canal(self, qs):
        """NTSRV34 — restreint la liste au canal demandé (sélecteur de macro).

        Deux façons de le demander, l'une ou l'autre :
        ``?canal=whatsapp`` (canal de réponse direct) ou ``?ticket=<id>``
        (le canal est alors DÉDUIT du ``canal_ouverture`` du ticket, jamais
        lu du corps de la requête). Sans paramètre : liste complète, donc le
        comportement XSAV23 est strictement inchangé pour tout appelant
        existant.

        Le filtre est appliqué en Python sur les ids (les macros d'une société
        se comptent en dizaines) : une macro sans restriction reste visible
        partout, et une valeur héritée mal formée ne fait jamais disparaître
        une macro."""
        params = self.request.query_params
        canal = (params.get('canal') or '').strip().lower()
        ticket_id = (params.get('ticket') or '').strip()
        if not canal and ticket_id:
            ticket = Ticket.objects.filter(
                pk=ticket_id,
                company=self.request.user.company).first() \
                if ticket_id.isdigit() else None
            if ticket is None:
                return qs
            canal = ReponseType.canal_de_ticket(ticket)
        if not canal:
            return qs
        if canal not in ReponseType.CANAUX:
            # Canal inconnu : on ne devine pas, on ne masque rien.
            return qs
        autorisees = [m.pk for m in qs if m.autorise_canal(canal)]
        return qs.filter(pk__in=autorisees)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── XSAV25 — Compatibilité pièces ─────────────────────────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('produit_equipement', OpenApiTypes.INT, required=False),
    ]))
class CompatibilitePieceViewSet(CompanyScopedModelViewSet):
    """CRUD du mapping pièce compatible <-> modèle d'équipement (XSAV25)."""
    queryset = CompatibilitePiece.objects.select_related(
        'produit_equipement', 'piece', 'remplace_par').all()
    serializer_class = CompatibilitePieceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_equipement = self.request.query_params.get('produit_equipement')
        if produit_equipement:
            qs = qs.filter(produit_equipement_id=produit_equipement)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        for field in ('produit_equipement', 'piece', 'remplace_par'):
            obj = serializer.validated_data.get(field)
            if obj is not None and obj.company_id not in (company.id, None):
                raise ValidationError({field: 'Produit inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)


# ── NTSRV16 — Gestion Problème (Problem Management) ─────────────────────────

@extend_schema_view(list=extend_schema(
    parameters=[
        OpenApiParameter('statut', OpenApiTypes.STR, required=False),
        OpenApiParameter('ordering', OpenApiTypes.STR, required=False, enum=['impact', '-impact']),
    ]))
class ProblemeViewSet(CompanyScopedModelViewSet):
    """NTSRV16 — CRUD des problèmes + rattachement/détachement des incidents.

    Un « problème » regroupe N tickets qui partagent UNE cause racine. Les
    deux machines d'états restent INDÉPENDANTES : passer un problème à
    « résolu » ne touche jamais le statut des tickets liés (garanti par un
    test). Le tri ``?ordering=impact`` classe par nb de tickets × ancienneté.
    """
    queryset = Probleme.objects.all()
    serializer_class = ProblemeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'description', 'cause_racine']
    ordering_fields = ['reference', 'titre', 'statut', 'created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        # Une garde déclarée par l'@action elle-même PRIME (sinon le kwarg du
        # décorateur devient du code mort — même motif que TicketViewSet).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        if self.action in READ_ACTIONS:
            return [HasPermissionOrLegacy('sav_voir')()]
        # NTSRV39 — l'ÉCRITURE d'un problème est un geste de responsable,
        # distinct de `sav_gerer` (traiter ses tickets). Un technicien de base
        # lit les problèmes (`sav_voir`) mais n'en crée/modifie aucun. Les
        # comptes hérités SANS rôle fin gardent le comportement historique
        # (repli `is_responsable` de HasPermissionOrLegacy).
        return [HasPermissionOrLegacy('sav_probleme_gerer')()]

    def get_queryset(self):
        from django.db.models import Case, Count, IntegerField, Value, When

        qs = super().get_queryset().annotate(
            nb_tickets_annote=Count('incidents', distinct=True))
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        # Tri par IMPACT (nb tickets × ancienneté) : le produit se calcule en
        # Python sur une table de taille référentielle (quelques dizaines de
        # lignes par société), puis l'ordre est REPROJETÉ en SQL via
        # Case/When — la pagination DRF reste donc exacte, et aucune
        # arithmétique de durée (non portable) n'est envoyée à la base.
        ordering = (self.request.query_params.get('ordering') or '').strip()
        if ordering in ('impact', '-impact'):
            maintenant = timezone.now()
            lignes = []
            for probleme in qs:
                jours = 1
                if probleme.created_at:
                    jours = max(1, (maintenant - probleme.created_at).days)
                lignes.append(
                    (probleme.pk, (probleme.nb_tickets_annote or 0) * jours))
            lignes.sort(key=lambda ligne: (ligne[1], ligne[0]),
                        reverse=ordering == '-impact')
            if not lignes:
                return qs
            rang = Case(
                *[When(pk=pk, then=Value(index))
                  for index, (pk, _) in enumerate(lignes)],
                default=Value(len(lignes)), output_field=IntegerField())
            return qs.annotate(rang_impact=rang).order_by('rang_impact')
        return qs

    def perform_create(self, serializer):
        """Référence ``PRB-YYYYMM-NNNN`` posée côté serveur, race-safe."""
        company = self.request.user.company
        create_with_reference(
            Probleme, 'PRB', company,
            lambda ref: serializer.save(reference=ref, company=company),
        )

    def _ticket_de_la_societe(self, request):
        """Résout le ticket du corps, scopé société. Erreur FRANÇAISE qui
        NOMME le champ fautif (jamais un « non enregistré » générique)."""
        brut = request.data.get('ticket')
        if brut in (None, ''):
            raise ValidationError({'ticket': 'Indiquez le ticket à rattacher.'})
        # ASAV25 — résolu par la portée de l'utilisateur (404 hors portée).
        return _ticket_visible_du_corps(request, brut)

    @extend_schema(
        request=inline_serializer('SavProblemeLierTicketRequest', {
            'ticket': drf_serializers.IntegerField(),
        }),
        responses=inline_serializer('SavProblemeLierTicketResponse', {
            'lien_id': drf_serializers.IntegerField(allow_null=True),
            'cree': drf_serializers.BooleanField(),
            'probleme': drf_serializers.CharField(),
            'ticket': drf_serializers.CharField(),
            'nb_tickets': drf_serializers.IntegerField(),
        }))
    @action(detail=True, methods=['post'], url_path='lier-ticket',
            permission_classes=[HasPermissionOrLegacy('sav_probleme_gerer')])
    def lier_ticket(self, request, pk=None):
        """Rattache UN ticket au problème. Idempotent : un second appel
        renvoie le lien existant sans doublon (contrainte unique en base).

        Le STATUT du ticket n'est jamais touché — seule une note de chatter
        trace le rattachement."""
        probleme = self.get_object()
        ticket = self._ticket_de_la_societe(request)
        lien = ProblemeIncident.objects.filter(
            probleme=probleme, ticket=ticket).first()
        cree = False
        if lien is None:
            try:
                with transaction.atomic():
                    lien = ProblemeIncident.objects.create(
                        company=probleme.company, probleme=probleme,
                        ticket=ticket)
                cree = True
            except IntegrityError:
                # Course : un autre appel a créé le même lien entre-temps.
                lien = ProblemeIncident.objects.filter(
                    probleme=probleme, ticket=ticket).first()
        if cree:
            activity.log_note(
                ticket, request.user,
                f'Rattaché au problème {probleme.reference} — '
                f'{probleme.titre}')
        return Response({
            'lien_id': lien.pk if lien else None,
            'cree': cree,
            'probleme': probleme.reference,
            'ticket': ticket.reference,
            'nb_tickets': probleme.incidents.count(),
        })

    @extend_schema(
        request=inline_serializer('SavProblemeDelierTicketRequest', {
            'ticket': drf_serializers.IntegerField(),
        }),
        responses=inline_serializer('SavProblemeDelierTicketResponse', {
            'delie': drf_serializers.BooleanField(),
            'probleme': drf_serializers.CharField(),
            'ticket': drf_serializers.CharField(),
            'nb_tickets': drf_serializers.IntegerField(),
        }))
    @action(detail=True, methods=['post'], url_path='delier-ticket',
            permission_classes=[HasPermissionOrLegacy('sav_probleme_gerer')])
    def delier_ticket(self, request, pk=None):
        """Détache un ticket du problème : supprime la LIGNE DE LIAISON,
        jamais le ticket. Idempotent (détacher deux fois ne casse rien)."""
        probleme = self.get_object()
        ticket = self._ticket_de_la_societe(request)
        supprimes, _ = ProblemeIncident.objects.filter(
            probleme=probleme, ticket=ticket).delete()
        return Response({
            'delie': bool(supprimes),
            'probleme': probleme.reference,
            'ticket': ticket.reference,
            'nb_tickets': probleme.incidents.count(),
        })

    @extend_schema(
        responses=inline_serializer('SavProblemeTicketsResponse', {
            'results': inline_serializer('SavProblemeTicketLigne', {
                'id': drf_serializers.IntegerField(),
                'reference': drf_serializers.CharField(),
                'statut': drf_serializers.CharField(),
                'priorite': drf_serializers.CharField(),
                'client': drf_serializers.CharField(),
                'date_ouverture': drf_serializers.DateField(allow_null=True),
                'lie_le': drf_serializers.DateTimeField(),
            }, many=True),
        }))
    @action(detail=True, methods=['get'], url_path='tickets',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def tickets(self, request, pk=None):
        """Tous les tickets rattachés à ce problème, en UN appel (« voir en
        un clic tous les tickets concernés »)."""
        probleme = self.get_object()
        lignes = (ProblemeIncident.objects
                  .filter(probleme=probleme)
                  .select_related('ticket', 'ticket__client')
                  .order_by('-created_at', '-id'))
        return Response({'results': [{
            'id': ligne.ticket_id,
            'reference': ligne.ticket.reference,
            'statut': ligne.ticket.statut,
            'priorite': ligne.ticket.priorite,
            'client': getattr(ligne.ticket.client, 'nom', '') or '',
            'date_ouverture': ligne.ticket.date_ouverture,
            'lie_le': ligne.created_at,
        } for ligne in lignes]})

    @extend_schema(
        parameters=[
            OpenApiParameter('fenetre_jours', OpenApiTypes.INT, required=False,
                             description='Fenêtre en jours (défaut 30).'),
            OpenApiParameter('seuil', OpenApiTypes.INT, required=False,
                             description="Nombre d'occurrences (défaut 3)."),
        ],
        responses=inline_serializer('SavProblemeRegroupementsResponse', {
            'fenetre_jours': drf_serializers.IntegerField(),
            'seuil': drf_serializers.IntegerField(),
            'results': inline_serializer('SavProblemeRegroupement', {
                'produit_id': drf_serializers.IntegerField(),
                'produit_nom': drf_serializers.CharField(),
                'cause_id': drf_serializers.IntegerField(allow_null=True),
                'cause_libelle': drf_serializers.CharField(),
                'titre_suggere': drf_serializers.CharField(),
                'nb_tickets': drf_serializers.IntegerField(),
                'tickets': inline_serializer('SavProblemeRegroupementTicket', {
                    'id': drf_serializers.IntegerField(),
                    'reference': drf_serializers.CharField(),
                    'statut': drf_serializers.CharField(),
                    'priorite': drf_serializers.CharField(),
                    'date_ouverture': drf_serializers.DateField(
                        allow_null=True),
                    'client': drf_serializers.CharField(),
                }, many=True),
            }, many=True),
        }))
    @action(detail=False, methods=['get'], url_path='regroupements-suggeres',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def regroupements_suggeres(self, request):
        """NTSRV17 — « Regroupements suggérés » : tickets ouverts qui
        partagent produit + cause dans la fenêtre, ≥ seuil occurrences.

        LECTURE PURE : aucun ``Probleme`` n'est créé ici — l'agent valide
        ensuite dans l'assistant (NTSRV31)."""
        from .selectors import tickets_candidats_probleme

        params = request.query_params
        try:
            fenetre = int(params.get('fenetre_jours') or 30)
        except (TypeError, ValueError):
            raise ValidationError(
                {'fenetre_jours': 'Indiquez un nombre de jours (ex. 30).'})
        try:
            seuil = int(params.get('seuil') or 3)
        except (TypeError, ValueError):
            raise ValidationError(
                {'seuil': 'Indiquez un nombre d’occurrences (ex. 3).'})
        groupes = tickets_candidats_probleme(
            request.user.company, fenetre, seuil=seuil)
        return Response({
            'fenetre_jours': fenetre,
            'seuil': seuil,
            'results': groupes,
        })

    @extend_schema(
        request=inline_serializer('SavProblemeDepuisRegroupementRequest', {
            'titre': drf_serializers.CharField(),
            'description': drf_serializers.CharField(required=False),
            'cause_racine': drf_serializers.CharField(required=False),
            'ticket_ids': drf_serializers.ListField(
                child=drf_serializers.IntegerField()),
        }),
        responses=inline_serializer('SavProblemeDepuisRegroupementResponse', {
            'id': drf_serializers.IntegerField(),
            'reference': drf_serializers.CharField(),
            'titre': drf_serializers.CharField(),
            'nb_tickets': drf_serializers.IntegerField(),
        }))
    @action(detail=False, methods=['post'],
            url_path='creer-depuis-regroupement',
            permission_classes=[
                HasPermissionOrLegacy('sav_probleme_gerer')])  # NTSRV39
    def creer_depuis_regroupement(self, request):
        """NTSRV31 — crée le problème ET rattache les tickets COCHÉS en UN
        SEUL appel transactionnel.

        Décocher un ticket dans l'assistant l'exclut réellement : seuls les
        ids reçus sont rattachés (aucun « tout le groupe » implicite côté
        serveur). Tout ou rien : si un id est inconnu, RIEN n'est créé."""
        company = request.user.company
        titre = str(request.data.get('titre') or '').strip()
        if not titre:
            raise ValidationError(
                {'titre': 'Le titre du problème est obligatoire.'})
        bruts = request.data.get('ticket_ids')
        if not isinstance(bruts, (list, tuple)) or not bruts:
            raise ValidationError(
                {'ticket_ids': 'Cochez au moins un ticket à rattacher.'})
        try:
            demandes = [int(valeur) for valeur in bruts]
        except (TypeError, ValueError):
            raise ValidationError({'ticket_ids': 'Ticket inconnu.'})

        # ASAV76 — bornés à la portée de l'utilisateur (comme lier-ticket).
        tickets = list(_tickets_visibles(request).filter(
            pk__in=demandes, company=company))
        if len(tickets) != len(set(demandes)):
            raise ValidationError(
                {'ticket_ids': 'Ticket inconnu (il appartient à une autre '
                               'société ou a été supprimé).'})

        with transaction.atomic():
            probleme = create_with_reference(
                Probleme, 'PRB', company,
                lambda ref: Probleme.objects.create(
                    company=company, reference=ref, titre=titre,
                    description=str(request.data.get('description') or ''),
                    cause_racine=str(request.data.get('cause_racine') or '')),
            )
            ProblemeIncident.objects.bulk_create([
                ProblemeIncident(company=company, probleme=probleme,
                                 ticket=ticket)
                for ticket in tickets])
        for ticket in tickets:
            activity.log_note(
                ticket, request.user,
                f'Rattaché au problème {probleme.reference} — '
                f'{probleme.titre}')
        return Response({
            'id': probleme.pk,
            'reference': probleme.reference,
            'titre': probleme.titre,
            'nb_tickets': len(tickets),
        }, status=status.HTTP_201_CREATED)


def _bornes_periode(request):
    """Bornes ``?date_debut=`` / ``?date_fin=`` (AAAA-MM-JJ), optionnelles.

    Une date mal formée est REFUSÉE en NOMMANT le champ fautif — jamais
    ignorée en silence (un rapport calculé sur une autre période que celle
    demandée est pire qu'une erreur)."""
    bornes = {}
    for champ in ('date_debut', 'date_fin'):
        brut = (request.query_params.get(champ) or '').strip()
        if not brut:
            bornes[champ] = None
            continue
        try:
            bornes[champ] = _date.fromisoformat(brut)
        except ValueError:
            raise ValidationError(
                {champ: 'Date invalide (format attendu : AAAA-MM-JJ).'})
    return bornes


def sav_fcr_insight(request):
    """NTSRV24 — Taux de résolution au premier contact (FCR).

    ``?date_debut=&date_fin=`` (bornes inclusives, optionnelles) et
    ``?export=xlsx`` pour la liste ticket par ticket. Réservé au tier
    responsable/admin (vérifié côté urls.py)."""
    from .selectors import taux_resolution_premier_contact

    bornes = _bornes_periode(request)
    data = taux_resolution_premier_contact(
        request.user.company,
        date_debut=bornes['date_debut'], date_fin=bornes['date_fin'])

    if (request.query_params.get('export') or '').lower() == 'xlsx':
        from apps.records.xlsx import build_xlsx_response

        entetes = ['Référence', 'Premier contact', 'Motif',
                   'Réouvertures', 'Échanges client']
        lignes = [[
            ligne['reference'],
            'Oui' if ligne['fcr'] else 'Non',
            ligne['motif'],
            ligne['reopen_count'],
            ligne['nb_echanges_client'],
        ] for ligne in data['tickets']]
        return build_xlsx_response(
            'sav-fcr.xlsx', entetes, lignes, sheet_title='FCR')

    return Response(data)


def sav_performance_agent_insight(request):
    """NTSRV27 — Charge et performance par agent.

    ``?date_debut=&date_fin=`` (bornes inclusives, optionnelles) et
    ``?export=xlsx``. JAMAIS un classement public/gamifié : la liste arrive
    triée alphabétiquement du sélecteur, et l'accès est réservé au tier
    responsable/admin (vérifié côté urls.py)."""
    from .selectors import performance_agent

    bornes = _bornes_periode(request)
    data = performance_agent(
        request.user.company,
        date_debut=bornes['date_debut'], date_fin=bornes['date_fin'])

    if (request.query_params.get('export') or '').lower() == 'xlsx':
        from apps.records.xlsx import build_xlsx_response

        entetes = ['Agent', 'Tickets traités', 'Résolution moyenne (jours)',
                   'CSAT moyen', 'Respect SLA (%)']
        lignes = [[
            ligne['agent_nom'],
            ligne['nb_tickets_traites'],
            ligne['delai_resolution_moyen_jours'],
            ligne['csat_moyen'],
            ligne['taux_respect_sla'],
        ] for ligne in data['agents']]
        return build_xlsx_response(
            'sav-performance-agent.xlsx', entetes, lignes,
            sheet_title='Performance agent')

    return Response(data)


def sav_pareto_pannes(request):
    """XSAV14 — Pareto des pannes par modèle de produit (ou fournisseur).

    ``?group_by=produit`` (défaut) ou ``?group_by=fournisseur`` ;
    ``?date_debut=AAAA-MM-JJ&date_fin=AAAA-MM-JJ`` optionnels. Alimente les
    réclamations garantie FG83 avec des preuves chiffrées (récurrence par
    modèle/fournisseur)."""
    from datetime import date as _date
    from .selectors import pareto_pannes

    company = request.user.company
    group_by = request.query_params.get('group_by', 'produit')
    if group_by not in ('produit', 'fournisseur'):
        group_by = 'produit'

    def _parse(name):
        raw = (request.query_params.get(name) or '').strip()
        if not raw:
            return None
        try:
            return _date.fromisoformat(raw)
        except ValueError:
            return None

    data = pareto_pannes(
        company, group_by=group_by,
        date_debut=_parse('date_debut'), date_fin=_parse('date_fin'))
    return Response({'group_by': group_by, 'results': data})


# ── XSAV15 — MTBF/MTTR/coût cumulé — vue d'ensemble parc ──────────────────────

def sav_fiabilite_insight(request):
    """XSAV15 — Fiabilité (MTBF/MTTR/coût) de tout le parc, triée pour
    identifier les « citrons ». Le coût cumulé n'est inclus que pour les
    utilisateurs avec `prix_achat_voir` (jamais exposé sinon)."""
    from .selectors import fiabilite_equipements
    company = request.user.company
    include_couts = bool(request.user.can_view_buy_prices)
    try:
        limit = int(request.query_params.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50
    data = fiabilite_equipements(
        company, include_couts=include_couts, limit=max(1, limit))
    return Response({'results': data, 'couts_inclus': include_couts})


# ── ZMFG4 — Tableau de bord maintenance par équipe/statut ────────────────────

def sav_resume_par_equipe(request):
    """ZMFG4 — Résumé du dashboard SAV groupé par équipe de maintenance
    (ZMFG1). Réservé au tier responsable/admin (vérifié côté urls.py)."""
    from .selectors import resume_par_equipe
    company = request.user.company
    data = resume_par_equipe(company)
    return Response({'results': data})


# ── NTSRV8 — File d'attente par équipe + PROPOSITION de débordement ─────────

def sav_file_attente(request):
    """NTSRV8 — File d'attente par équipe de maintenance et, quand une équipe
    dépasse sa capacité déclarée, la PROPOSITION de transfert associée.

    LECTURE PURE : aucune réaffectation n'est jamais exécutée ici. Le
    transfert passe par l'action explicite
    ``tickets/{id}/reaffecter-equipe/``. Réservé au tier responsable/admin
    (vérifié côté urls.py)."""
    from .selectors import charges_equipes, file_attente_equipe
    from .services import debordement_equipe

    company = request.user.company
    charges = charges_equipes(company)
    equipes = (EquipeMaintenance.objects
               .filter(company=company, actif=True)
               .order_by('nom'))
    resultats = []
    for equipe in equipes:
        file_attente = list(file_attente_equipe(equipe))
        proposition = debordement_equipe(equipe)
        resultats.append({
            'equipe_id': equipe.pk,
            'equipe_nom': equipe.nom,
            'capacite': equipe.capacite_max_tickets_ouverts,
            'charge': charges.get(equipe.pk, 0),
            'file_attente': [{
                'id': t.pk, 'reference': t.reference,
                'client': getattr(t.client, 'nom', '') or '',
                'statut': t.statut, 'priorite': t.priorite,
                'date_ouverture': t.date_ouverture,
                'sla_due_at': t.sla_due_at,
            } for t in file_attente],
            # Toujours présent : `excedent=0` = rien à proposer.
            'debordement': proposition,
        })
    return Response({'results': resultats})


# ── ZSAV6 — Vue « activité » : file d'action suivante par ticket ────────────

def sav_file_action(request):
    """ZSAV6 — Regroupe les tickets ouverts par action attendue (à répondre/
    à planifier/à relancer/à clôturer). Réservé au tier responsable/admin
    (vérifié côté urls.py)."""
    from .selectors import file_action
    company = request.user.company
    data = file_action(company)
    return Response(data)


# ── FG89 — Prévision pièces SAV ───────────────────────────────────────────────

def sav_parts_forecast(request):
    """FG89 — Aperçu consommation de pièces SAV sur une fenêtre glissante.

    Agrège PieceConsommee par produit sur les N derniers mois, calcule la
    consommation mensuelle moyenne et suggère une quantité de réapprovisionnement.
    Interne uniquement — aucun prix d'achat n'est exposé.
    """
    from apps.sav.models import PieceConsommee
    from django.db.models import Sum

    company = request.user.company
    months = int(request.query_params.get('months', 12))
    since = timezone.localdate() - timedelta(days=months * 30)

    qs = (PieceConsommee.objects
          .filter(company=company, date_creation__date__gte=since)
          .values('produit', 'produit__nom', 'produit__marque', 'produit__sku')
          .annotate(total_consomme=Sum('quantite'))
          .order_by('-total_consomme'))

    results = []
    for row in qs:
        mensuel_moyen = float(row['total_consomme']) / max(months, 1)
        results.append({
            'produit': row['produit'],
            'nom': row['produit__nom'],
            'marque': row['produit__marque'] or '',
            'sku': row['produit__sku'] or '',
            'total_consomme': float(row['total_consomme']),
            'mois_fenetre': months,
            'consommation_mensuelle_moy': round(mensuel_moyen, 2),
            # Suggestion : 2 mois de stock de sécurité.
            'qte_suggere_reappro': round(mensuel_moyen * 2, 1),
        })

    return Response(results)


# ── ASAV33 — les balayages SAV vivent dans ``apps/sav/tasks.py`` ───────────
# (bornés aux sociétés actives, verrou, entrées beat). Les noms historiques
# restent ici en DÉLÉGUÉS d'une ligne pour les appelants existants.

def scan_sla_breaches():
    """FG81 — délégué de ``tasks.scan_sla_breaches`` (ASAV33)."""
    from .tasks import scan_sla_breaches as _scan
    return _scan()


def scan_sla_pre_alerts_and_escalations():
    """XSAV6 — délégué de ``tasks.scan_sla_pre_alerts_and_escalations``."""
    from .tasks import scan_sla_pre_alerts_and_escalations as _scan
    return _scan()


def scan_auto_cloture_tickets_resolus():
    """XSAV24 — délégué de ``tasks.scan_auto_cloture_tickets_resolus``."""
    from .tasks import scan_auto_cloture_tickets_resolus as _scan
    return _scan()
