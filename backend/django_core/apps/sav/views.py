from datetime import date as _date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference

from . import activity
from .models import (
    Equipement, Ticket, PieceConsommee,
    SavSlaSettings, MaintenanceChecklistTemplate, TicketChecklistItem,
    WarrantyClaim, KbArticle, AlarmeOnduleur,
    CauseDefaillance, RemedeDefaillance, EquipementDowntime,
    ReleveCompteurEquipement, ReponseType, CompatibilitePiece, PieceRetiree,
    CategorieTicket, EquipeMaintenance, CategorieEquipement,
    TicketActiviteAFaire, TicketFollower,
    WorksheetMaintenanceModele, TicketWorksheet,
)
from .services import add_months
from .pdf import rapport_intervention_pdf
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
    TicketActiviteAFaireSerializer,
    WorksheetMaintenanceModeleSerializer, TicketWorksheetSerializer,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class EquipementViewSet(CompanyScopedModelViewSet):
    """Parc d'équipements (n° de série + horloges de garantie). Tout est scopé
    à la société ; les dates de fin de garantie sont CALCULÉES côté serveur."""
    queryset = Equipement.objects.select_related(
        'produit', 'installation', 'installation__client', 'client_vente',
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
        try:
            super().perform_update(serializer)
        except IntegrityError:
            raise ValidationError(
                {'numero_serie':
                 'Ce numéro de série existe déjà dans votre société.'})
        inst = serializer.instance
        inst.recompute_garanties()
        # FG85 — assure que le jeton est toujours présent (migration d'équipements existants).
        token = f'EQUIP:{inst.pk}'
        update_fields = ['date_fin_garantie', 'date_fin_garantie_production']
        if inst.equipement_token != token:
            inst.equipement_token = token
            update_fields.append('equipement_token')
        inst.save(update_fields=update_fields)

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
            items.append({'token': token, 'titre': titre, 'sous_titre': sous_titre})

        if not items:
            return Response({'detail': 'Aucun équipement.'}, status=404)

        symbology = request.query_params.get('symbology', 'qr')
        html = render_labels_html(items, symbology=symbology)
        return HR(html, content_type='text/html; charset=utf-8')

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

    @action(detail=True, methods=['get', 'post'], url_path='downtime',
            permission_classes=[HasPermissionOrLegacy('equipement_gerer')])
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

    @action(detail=True, methods=['post'],
            url_path=r'downtime/(?P<downtime_id>[^/.]+)/cloturer',
            permission_classes=[HasPermissionOrLegacy('equipement_gerer')])
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

    @action(detail=True, methods=['get', 'post'], url_path='releves-compteur',
            permission_classes=[HasPermissionOrLegacy('equipement_gerer')])
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
        if type_releve not in (
                ReleveCompteurEquipement.Type.HEURES,
                ReleveCompteurEquipement.Type.KWH):
            return Response({'detail': 'type invalide (heures|kwh).'}, status=400)
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
        # NOTE : cette surcharge NE lit PAS self.permission_classes ; le tier de
        # chaque @action doit donc être listé EXPLICITEMENT ci-dessous pour
        # correspondre au kwarg permission_classes de son décorateur. Toute
        # @action absente retombe sur IsAdminRole (plus restrictif que voulu) —
        # tenu par apps/sav/tests_ticket_action_permissions.py.
        if self.action in READ_ACTIONS + [
                'historique', 'rapport_pdf', 'lien_client', 'similaires',
                'triage_ia', 'instructions_suggestions',
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
        résolution retombe exactement sur le comportement FG81 d'origine."""
        from .models import ContratMaintenance
        sla = SavSlaSettings.get(company)
        contrat = ContratMaintenance.actif_pour_client(client)
        if contrat is not None and contrat.sla_resolution_days is not None:
            return contrat.sla_resolution_days
        _, resolution_days = sla.days_for(priorite)
        return resolution_days

    def _compute_sla_due_at(self, company, client, priorite, date_ouverture):
        """FG81 — Calcule sla_due_at depuis les réglages société (ou None).

        XSAV5 — quand ``sla_jours_ouvres`` est activé, l'échéance avance de
        ``resolution_days`` JOURS OUVRÉS (via ``core.calendar``, jours ouvrés +
        fériés marocains) plutôt qu'en jours calendaires. OFF (défaut) =
        comportement calendaire byte-identique à avant XSAV5.

        XSAV7 — ``resolution_days`` peut venir d'un contrat de maintenance actif
        du client (override), avant repli sur ``sla_par_priorite``/défauts."""
        sla = SavSlaSettings.get(company)
        if not sla.sla_breach_enabled:
            return None
        resolution_days = self._resolve_resolution_days(
            company, client, priorite)
        if sla.sla_jours_ouvres:
            from core.calendar import add_working_days
            return add_working_days(date_ouverture, resolution_days)
        return date_ouverture + timedelta(days=resolution_days)

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
        sla_due_at = self._compute_sla_due_at(
            company, client, priorite, date_ouverture)
        create_with_reference(
            Ticket, 'SAV', company,
            lambda ref: serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
                date_ouverture=date_ouverture,
                sla_due_at=sla_due_at),
        )
        # XSAV9 — affectation automatique si aucun technicien n'a été choisi
        # à la création et que la société l'a activée (défaut OFF = inchangé).
        inst = serializer.instance
        if not inst.technicien_responsable_id:
            sla = SavSlaSettings.get(company)
            if sla.affectation_auto_sav:
                from .services import assign_technicien_auto
                technicien = assign_technicien_auto(
                    company=company, jour=date_ouverture)
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
            contrat = (ContratMaintenance.objects
                       .filter(client_id=inst.client_id, actif=True)
                       .order_by('-date_creation').first())
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
            contrat = (ContratMaintenance.objects
                       .filter(client_id=inst.client_id, actif=True)
                       .order_by('-date_creation').first())
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

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        # YDOCF1 — `statut` est désormais read-only sur le sérialiseur : plus
        # aucune transition n'arrive ici via PATCH direct. Les transitions
        # passent exclusivement par les actions guardées ci-dessous
        # (`planifier`/`demarrer`/`resoudre`/`cloturer`), qui appliquent la
        # même chaîne d'effets (SLA/chatter/notification/downtime) via
        # `_appliquer_transition_statut`.
        super().perform_update(serializer)

    def _appliquer_transition_statut(self, ticket, statut_cible):
        """YDOCF1 — Applique une transition de statut GARDÉE (via
        ``machine_etats.changer_statut``) et rejoue exactement la même chaîne
        d'effets qu'avant YDOCF1 (SLA/réouverture/chatter/notification client/
        clôture des downtimes). Lève ``ValidationError`` (400) nommant le
        statut courant + les cibles permises sur une transition interdite."""
        from . import machine_etats

        old = Ticket.objects.get(pk=ticket.pk)
        # YSERV2 — garde de clôture : refuse CLOTURE tant qu'une intervention
        # liée (apps.installations) n'est pas TERMINEE/VALIDEE.
        if (statut_cible == Ticket.Statut.CLOTURE
                and old.statut != Ticket.Statut.CLOTURE):
            ouvertes = self._interventions_ouvertes(old)
            if ouvertes:
                raise ValidationError({
                    'statut': (
                        'Impossible de clôturer : intervention(s) encore '
                        'ouverte(s) sur ce ticket.'),
                    'interventions_ouvertes': ouvertes,
                })
        try:
            machine_etats.changer_statut(ticket, statut_cible, persister=False)
        except machine_etats.TransitionInterdite as exc:
            raise ValidationError({'statut': str(exc)})
        # YSERV12 — à la transition vers RESOLU, propose canal_resolution si
        # l'appelant n'en a pas déjà posé un explicitement (jamais écrasé).
        # Dans les deux cas (posé explicitement par l'appelant AVANT cet
        # appel, ou proposé automatiquement ici), le champ doit figurer dans
        # `update_fields` sous peine d'être silencieusement perdu (un
        # `save(update_fields=...)` n'écrit QUE les colonnes listées).
        update_fields = ['statut']
        if statut_cible == Ticket.Statut.RESOLU and old.statut != Ticket.Statut.RESOLU:
            if not ticket.canal_resolution:
                ticket.canal_resolution = old.canal_resolution_propose()
            update_fields.append('canal_resolution')
        ticket.save(update_fields=update_fields)
        # ARC37 — sav devient émetteur du bus (core.events.ticket_resolu) sur
        # le FRANCHISSEMENT gardé par la condition ci-dessus. No-op si la
        # transition n'atteint pas RESOLU (garde interne au service).
        from . import services as sav_services
        sav_services.emettre_ticket_resolu(
            ticket, company=ticket.company, user=self.request.user,
            ancien_statut=old.statut)
        # ARC34 — déclencheur automation générique RECORD_STATE_CHANGE sur
        # TOUTE transition de statut réussie (whitelist registre plateforme ;
        # no-op sans règle). Émission via le service (frontière respectée).
        sav_services.emettre_changement_statut_ticket(
            ticket, company=ticket.company, user=self.request.user,
            ancien_statut=old.statut)
        # FG81 — recalcule sla_breach après toute mise à jour de statut.
        ticket.recompute_sla_breach()
        save_fields = ['sla_breach']
        # XSAV11 — réouverture : résolu/clôturé → statut OUVERT. Compté côté
        # serveur, jamais décrémenté. La transition est déjà tracée par
        # TicketActivity (activity.log_changes ci-dessous).
        if (old.statut in self._CLOTURE_STATUTS
                and ticket.statut in Ticket.OPEN_STATUTS):
            ticket.reopen_count += 1
            save_fields.append('reopen_count')
        ticket.save(update_fields=save_fields)
        activity.log_changes(old, ticket, self.request.user)
        # XSAV4 — notification client best-effort sur transition de statut
        # (reçu/planifié/résolu). Toggle OFF par défaut = aucun effet.
        if old.statut != ticket.statut:
            from .notifications_client import notify_ticket_transition
            notify_ticket_transition(
                ticket, ticket.statut, request=self.request)
            # ZSAV9 — notifie les suiveurs de la transition (best-effort).
            from .services import notify_followers
            from apps.notifications.models import EventType
            notify_followers(
                ticket, event_type=EventType.SAV_TICKET_FOLLOWED_UPDATE,
                title=f'Statut changé — {ticket.reference}',
                body=f'Nouveau statut : {ticket.get_statut_display()}.',
                link=f'/sav/tickets/{ticket.pk}',
                exclude_user=self.request.user)
        # XSAV16 — la clôture du ticket propose (= referme automatiquement,
        # idempotent) toute immobilisation EN COURS liée à ce ticket. Ne
        # ferme jamais une fenêtre déjà close, et n'affecte que les
        # downtimes du même ticket (pas ceux d'autres tickets sur le même
        # équipement).
        if (old.statut != ticket.statut
                and ticket.statut in self._CLOTURE_STATUTS):
            for dt in ticket.downtimes.filter(fin__isnull=True):
                dt.clore()
        return ticket

    @action(detail=True, methods=['post'], url_path='planifier',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def planifier(self, request, pk=None):
        """YDOCF1 — Transition gardée NOUVEAU/... → PLANIFIE."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.PLANIFIE)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='demarrer',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def demarrer(self, request, pk=None):
        """YDOCF1 — Transition gardée → EN_COURS."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.EN_COURS)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

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

    @action(detail=True, methods=['post'], url_path='cloturer',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def cloturer(self, request, pk=None):
        """YDOCF1 — Transition gardée → CLOTURE (garde YSERV2 conservée)."""
        ticket = self.get_object()
        self._appliquer_transition_statut(ticket, Ticket.Statut.CLOTURE)
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

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

        company = request.user.company
        tickets = list(
            Ticket.objects.filter(company=company, id__in=ids))
        traites = []
        echecs = []

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

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def historique(self, request, pk=None):
        ticket = self.get_object()
        return Response(
            TicketActivitySerializer(ticket.activites.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='instructions-suggestions',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def instructions_suggestions(self, request, pk=None):
        """ZMFG5 — Suggestions d'articles KB pour pré-remplir l'onglet
        « Instructions », à partir du type de panne (cause) du ticket, ou du
        libellé de la catégorie/description si aucune cause n'est codifiée.
        Lecture seule (aucune écriture) — l'utilisateur applique lui-même la
        suggestion via un PATCH `instructions` explicite."""
        from apps.kb.selectors import article_pour_mot_cle
        ticket = self.get_object()
        texte = (
            getattr(ticket.cause, 'nom', None)
            or getattr(ticket.categorie, 'libelle', None)
            or ticket.description or '')
        data = article_pour_mot_cle(
            ticket.company, request.user, texte, limit=3)
        return Response({'results': data})

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
        serializer = TicketActiviteAFaireSerializer(data=request.data)
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

        if not body and reponse_type_id:
            try:
                macro = ReponseType.objects.get(
                    pk=reponse_type_id, company=ticket.company)
            except (ReponseType.DoesNotExist, ValueError):
                return Response(
                    {'detail': 'Réponse type introuvable.'}, status=400)
            body = macro.rendu(
                client=str(ticket.client) if ticket.client_id else '',
                reference=ticket.reference,
                technicien=getattr(
                    ticket.technicien_responsable, 'username', ''),
                date=timezone.localdate().strftime('%d/%m/%Y'),
            ).strip()
            if macro.nouveau_statut and ticket.statut != macro.nouveau_statut:
                old = Ticket.objects.get(pk=ticket.pk)
                ticket.statut = macro.nouveau_statut
                ticket.save(update_fields=['statut'])
                activity.log_changes(old, ticket, request.user)

        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(ticket, request.user, body)
        # ZSAV9 — notifie les suiveurs du ticket (jamais l'auteur de la note).
        from .services import notify_followers
        from apps.notifications.models import EventType
        notify_followers(
            ticket, event_type=EventType.SAV_TICKET_FOLLOWED_UPDATE,
            title=f'Nouvelle note — {ticket.reference}',
            body=body, link=f'/sav/tickets/{ticket.pk}',
            exclude_user=request.user)
        return Response(TicketActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

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

    @action(detail=True, methods=['post'], url_path='suivre',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def suivre(self, request, pk=None):
        """ZSAV9 — S'abonner aux notifications de ce ticket (idempotent)."""
        ticket = self.get_object()
        TicketFollower.objects.get_or_create(
            company=ticket.company, ticket=ticket, user=request.user)
        return Response({'suivi': True})

    @suivre.mapping.delete
    def ne_plus_suivre(self, request, pk=None):
        """ZSAV9 — Se désabonner des notifications de ce ticket (idempotent)."""
        ticket = self.get_object()
        TicketFollower.objects.filter(
            ticket=ticket, user=request.user).delete()
        return Response({'suivi': False})

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
            ticket.date_premiere_reponse = at
            ticket.save(update_fields=['date_premiere_reponse'])
            activity.log_note(
                ticket, request.user,
                f'Première réponse enregistrée le {at.strftime("%d/%m/%Y %H:%M")}')
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

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
        from .services import OperationDestinationIncoherenteError, retirer_piece
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
        try:
            with transaction.atomic():
                piece = retirer_piece(
                    company=ticket.company, ticket=ticket, produit=produit,
                    quantite=quantite, numero_serie=numero_serie,
                    destination=destination, operation=operation,
                    user=request.user)
        except OperationDestinationIncoherenteError as exc:
            return Response({'detail': str(exc)}, status=400)
        suffixe = {
            PieceRetiree.Destination.STOCK_OCCASION: ' (stock occasion +)',
            PieceRetiree.Destination.RETOUR_FOURNISSEUR: ' (RMA)',
            PieceRetiree.Destination.REBUT: ' (rebut)',
        }.get(destination, '')
        activity.log_note(
            ticket, request.user,
            f'Pièce {produit.nom} ×{quantite} retirée{suffixe}')
        return Response(PieceRetireeSerializer(piece).data, status=201)

    @action(detail=True, methods=['get'], url_path='pieces-unifiees',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def pieces_unifiees(self, request, pk=None):
        """ZMFG8 — Affichage unifié Ajout/Retrait/Recyclage des pièces du
        ticket (`PieceConsommee` + `PieceRetiree`), avec sous-totaux."""
        from .selectors import pieces_unifiees as _pieces_unifiees

        ticket = self.get_object()
        return Response(_pieces_unifiees(ticket))

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
        ticket = self.get_object()
        from apps.ventes.services import generer_facture_ticket_sav

        # XFSM15 — un ticket récidive est non-facturable PAR DÉFAUT ; un
        # responsable/admin peut lever l'exclusion via `override=true`
        # explicite (l'un ne dispense jamais de l'autre : sans override,
        # MÊME un admin reste bloqué ; avec override, seul un responsable/
        # admin peut effectivement lever l'exclusion).
        override = str(request.data.get('override') or '') in (
            '1', 'true', 'True', 'on')
        if ticket.non_facturable:
            is_responsable = (
                getattr(request.user, 'is_admin_role', False)
                or getattr(request.user, 'is_responsable', False))
            if not override or not is_responsable:
                return Response({
                    'detail': ('Ticket récidive marqué non-facturable — '
                               'override responsable requis.'),
                }, status=403)

        sous_garantie = ticket.sous_garantie_calcule == Ticket.SousGarantie.OUI
        pieces = list(ticket.pieces.select_related('produit'))
        facture = generer_facture_ticket_sav(
            ticket=ticket, sous_garantie=sous_garantie, pieces=pieces,
            user=request.user)
        activity.log_note(
            ticket, request.user,
            f'Facture {facture.reference} générée depuis le ticket '
            f'(hors garantie : {not sous_garantie}).')
        return Response({
            'facture_id': facture.id,
            'facture_reference': facture.reference,
            'sous_garantie': sous_garantie,
        }, status=201)

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
        ticket = self.get_object()
        from apps.ventes.services import generer_facture_ticket_sav

        couverture = ticket.couverture
        if couverture == Ticket.Couverture.A_DETERMINER:
            couverture = ticket.couverture_calculee()

        sous_garantie = couverture in (
            Ticket.Couverture.GARANTIE, Ticket.Couverture.CONTRAT)
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
        }, status=201)

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
        if ticket.statut == Ticket.Statut.NOUVEAU:
            ticket.statut = Ticket.Statut.PLANIFIE
            ticket.save(update_fields=['statut'])
        activity.log_note(
            ticket, request.user,
            f'Intervention #{interv.id} planifiée depuis le ticket.')
        return Response({
            'intervention_id': interv.id,
            'ticket_statut': ticket.statut,
        }, status=201)

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

        doublon = Ticket.objects.filter(
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
        if ticket.sous_garantie_calcule == Ticket.SousGarantie.OUI:
            return Response(
                {'detail': 'Ticket sous garantie : aucun devis de '
                           "réparation n'est nécessaire."},
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
        qs = super().get_queryset()
        return qs.filter(actif=True)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def perform_destroy(self, instance):
        if instance.protege:
            raise ValidationError('Ce template est protégé et ne peut être supprimé.')
        instance.delete()


# ── FG83 — Réclamation garantie fournisseur ───────────────────────────────────

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

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        self._resolve_fournisseur(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        self._resolve_fournisseur(serializer)
        super().perform_update(serializer)


# ── FG87 — Base de connaissances SAV ─────────────────────────────────────────

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
            ticket = Ticket.objects.filter(
                id=ticket_id, company=company).first()
            if ticket is None:
                raise ValidationError({'ticket': 'Ticket inconnu.'})
        else:
            # Ouvre un ticket correctif. Le client/chantier sont déduits de
            # l'équipement lié à l'alarme quand c'est possible.
            equipement = alarme.equipement
            installation = getattr(equipement, 'installation', None)
            client = getattr(installation, 'client', None)
            if client is None:
                raise ValidationError({
                    'ticket': "Aucun ticket fourni et l'alarme n'a pas "
                              "d'équipement rattaché à un client — précisez "
                              "un ticket existant."})
            description = (
                f'Escalade alarme onduleur {alarme.code} '
                f'({alarme.get_gravite_display()})'
                + (f' : {alarme.libelle}' if alarme.libelle else ''))
            ticket = create_with_reference(
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
            )
        alarme.ticket = ticket
        alarme.statut = AlarmeOnduleur.Statut.ESCALADEE
        alarme.save(update_fields=['ticket', 'statut', 'date_modification'])
        return Response(AlarmeOnduleurSerializer(alarme).data)


# ── XSAV14 — Taxonomie panne / cause / remède ─────────────────────────────────

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
    queryset = CategorieEquipement.objects.all()
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
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── XSAV25 — Compatibilité pièces ─────────────────────────────────────────────

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


# ── FG81 — Scan journalier de breach (appelé par Celery-beat ou management cmd) ──

def scan_sla_breaches():
    """FG81 — Parcourt tous les tickets ouverts avec sla_due_at dépassé, met à
    jour sla_breach et notifie le technicien responsable. Idempotent.

    Appelé par le scan journalier (management command ou Celery-beat).
    Aucune modification si sla_breach_enabled est False pour la société."""
    from apps.notifications.services import notify
    from apps.notifications.models import EventType

    today = timezone.localdate()
    breached = Ticket.objects.filter(
        statut__in=Ticket.OPEN_STATUTS,
        annule=False,
        sla_due_at__lt=today,
        sla_breach=False,
    ).select_related('company', 'technicien_responsable')

    updated = 0
    for ticket in breached:
        # Vérifie que la société a activé les notifications SLA.
        sla = SavSlaSettings.get(ticket.company)
        if not sla.sla_breach_enabled:
            continue
        ticket.sla_breach = True
        ticket.save(update_fields=['sla_breach'])
        updated += 1
        if ticket.technicien_responsable_id:
            notify(
                user=ticket.technicien_responsable,
                event_type=EventType.SAV_TICKET_BREACHING,
                title=f'SLA dépassé — {ticket.reference}',
                body=(f'Le ticket {ticket.reference} a dépassé son délai SLA '
                      f'({ticket.sla_due_at.strftime("%d/%m/%Y")}).'),
                link=f'/sav/tickets/{ticket.pk}',
                company=ticket.company,
            )
    return updated


# ── XSAV6 — Pré-alerte SLA (J-x) + escalade à la violation ────────────────────

def scan_sla_pre_alerts_and_escalations():
    """XSAV6 — Pré-alerte à J-x + escalade au tier responsable à la violation.

    DISTINCT de ``scan_sla_breaches`` (FG81, notifie le technicien À la
    violation) et de ``notifications.sweeps._sweep_sav_breaching`` (âge du
    ticket, repli managers). Ici : pré-alerte configurable AVANT l'échéance
    (``sla_warning_days`` jours avant ``sla_due_at_effectif``), puis escalade
    au tier responsable/direction (``resolve_recipients``, mute-aware via
    ``notify()``) une fois l'échéance dépassée — si ``escalade_activee``.

    IDEMPOTENT : un ticket déjà notifié pour un niveau (pré-alerte ou
    escalade) ne l'est plus les jours suivants — flag posé sur le ticket.
    OFF par défaut (``sla_warning_days=0`` et ``escalade_activee=False``) :
    aucun effet, aucune notification supplémentaire.
    """
    from apps.notifications.services import notify, resolve_recipients
    from apps.notifications.models import EventType

    today = timezone.localdate()
    qs = Ticket.objects.filter(
        statut__in=Ticket.OPEN_STATUTS,
        annule=False,
        sla_due_at__isnull=False,
    ).select_related('company', 'technicien_responsable')

    pre_alerts = 0
    escalations = 0
    for ticket in qs:
        sla = SavSlaSettings.get(ticket.company)
        due_effectif = ticket.sla_due_at_effectif(today=today)

        # ── Pré-alerte J-x au technicien assigné ──
        if (sla.sla_warning_days > 0
                and not ticket.sla_pre_alert_notifiee
                and not ticket.sla_escalade_notifiee
                and ticket.technicien_responsable_id
                and due_effectif is not None):
            seuil = due_effectif - timedelta(days=sla.sla_warning_days)
            if today >= seuil and today <= due_effectif:
                notify(
                    user=ticket.technicien_responsable,
                    event_type=EventType.SAV_TICKET_BREACHING,
                    title=f'SLA bientôt dépassé — {ticket.reference}',
                    body=(f'Le ticket {ticket.reference} approche son '
                          f'échéance SLA ({due_effectif.strftime("%d/%m/%Y")}).'),
                    link=f'/sav/tickets/{ticket.pk}',
                    company=ticket.company,
                )
                ticket.sla_pre_alert_notifiee = True
                ticket.save(update_fields=['sla_pre_alert_notifiee'])
                pre_alerts += 1

        # ── Escalade au tier responsable/direction à la violation ──
        if (sla.escalade_activee
                and not ticket.sla_escalade_notifiee
                and due_effectif is not None
                and today > due_effectif):
            recipients = resolve_recipients(
                ticket.company, EventType.SAV_TICKET_BREACHING)
            for user in recipients:
                notify(
                    user=user,
                    event_type=EventType.SAV_TICKET_BREACHING,
                    title=f'Escalade SLA — {ticket.reference}',
                    body=(f'Le ticket {ticket.reference} a dépassé son '
                          f'échéance SLA ({due_effectif.strftime("%d/%m/%Y")}) '
                          'et requiert une attention immédiate.'),
                    link=f'/sav/tickets/{ticket.pk}',
                    company=ticket.company,
                )
            ticket.sla_escalade_notifiee = True
            ticket.save(update_fields=['sla_escalade_notifiee'])
            escalations += 1

    return {'pre_alerts': pre_alerts, 'escalations': escalations}


# ── XSAV24 — Auto-clôture des tickets résolus dormants ───────────────────────

def scan_auto_cloture_tickets_resolus():
    """XSAV24 — Clôture automatiquement les tickets RÉSOLU sans activité
    depuis ``SavSlaSettings.auto_cloture_jours`` jours (0 = OFF, comportement
    actuel inchangé — AUCUN ticket n'est jamais touché tant qu'une société ne
    fixe pas explicitement une valeur > 0).

    « Sans activité » = aucun ``TicketActivity`` (note ou changement de champ
    suivi, y compris le passage à RÉSOLU lui-même) depuis N jours — donc un
    ticket tout juste résolu, ou avec un échange récent, n'est jamais fermé
    par erreur. IDEMPOTENT : un ticket déjà CLÔTURÉ n'est plus repris par le
    sweep suivant (il ne filtre que sur ``statut=RESOLU``).

    Notification client optionnelle réutilisée via XSAV4
    (``notify_ticket_transition``, best-effort, n'envoie rien sans le toggle
    société ``notifications_client_sav`` — indépendant du toggle
    ``auto_cloture_jours``)."""
    from .models import SavSlaSettings, TicketActivity

    today = timezone.localdate()
    cloture = 0

    tickets = (Ticket.objects
               .filter(statut=Ticket.Statut.RESOLU, annule=False)
               .select_related('company'))

    for ticket in tickets:
        sla = SavSlaSettings.get(ticket.company)
        if not sla.auto_cloture_jours:
            continue

        derniere_activite = (
            TicketActivity.objects.filter(ticket=ticket)
            .order_by('-created_at').values_list('created_at', flat=True)
            .first())
        reference_dt = derniere_activite or ticket.date_modification
        if reference_dt is None:
            continue
        jours_ecoules = (today - timezone.localtime(reference_dt).date()).days
        if jours_ecoules < sla.auto_cloture_jours:
            continue

        old = Ticket.objects.get(pk=ticket.pk)
        ticket.statut = Ticket.Statut.CLOTURE
        ticket.save(update_fields=['statut'])
        activity.log_changes(old, ticket, None)
        activity.log_note(
            ticket, None,
            f'Clôturé automatiquement après {sla.auto_cloture_jours} jours '
            "sans activité.")
        cloture += 1

        try:
            from .notifications_client import notify_ticket_transition
            notify_ticket_transition(ticket, Ticket.Statut.CLOTURE)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            pass

    return cloture
