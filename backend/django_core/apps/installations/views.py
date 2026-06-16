from django.db import models
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import (
    IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)
from apps.imports.exports import XlsxExportMixin
from . import activity
from .models import (
    ChecklistItem, Installation, Intervention, TypeIntervention,
)
from .serializers import (
    ChecklistItemSerializer, InstallationSerializer, InterventionSerializer,
    InstallationActivitySerializer, ParcInstalleSerializer,
    TypeInterventionSerializer,
)
from .services import create_installation_from_devis, ensure_checklist
from .parc import mark_received

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class InstallationViewSet(XlsxExportMixin, TenantMixin, viewsets.ModelViewSet):
    """Chantiers + historique « chatter ». Tout est scopé à la société du
    user ; l'acteur et la société sont posés côté serveur, jamais lus du corps.
    """
    queryset = Installation.objects.select_related(
        'client', 'devis', 'lead', 'technicien_responsable',
    ).prefetch_related('interventions', 'checklist').all()
    serializer_class = InstallationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'site_ville',
    ]
    ordering_fields = ['reference', 'date_creation', 'date_pose_prevue', 'statut']
    ordering = ['-date_creation']

    # Export .xlsx (respecte statut/technicien/type/annule + recherche/tri).
    export_filename = 'chantiers.xlsx'
    export_sheet_title = 'Chantiers'
    export_columns = [
        ('reference', 'Référence'), ('client', 'Client'),
        ('statut', 'Statut'), ('type_installation', 'Type'),
        ('puissance', 'Puissance (kWc)'), ('site_ville', 'Ville'),
        ('technicien', 'Technicien'),
        ('date_pose_prevue', 'Pose prévue'),
        ('date_mise_en_service', 'Mise en service'),
    ]

    def get_export_row(self, obj):
        return {
            'reference': obj.reference,
            'client': str(obj.client) if obj.client else '',
            'statut': obj.get_statut_display(),
            'type_installation': (obj.get_type_installation_display()
                                  if obj.type_installation else ''),
            'puissance': (float(obj.puissance_installee_kwc)
                          if obj.puissance_installee_kwc is not None else ''),
            'site_ville': obj.site_ville or '',
            'technicien': (getattr(obj.technicien_responsable, 'username', '')
                           or ''),
            'date_pose_prevue': (str(obj.date_pose_prevue)
                                 if obj.date_pose_prevue else ''),
            'date_mise_en_service': (str(obj.date_mise_en_service)
                                     if obj.date_mise_en_service else ''),
        }

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        technicien = params.get('technicien')
        type_inst = params.get('type_installation')
        if statut:
            qs = qs.filter(statut=statut)
        if technicien:
            qs = qs.filter(technicien_responsable_id=technicien)
        if type_inst:
            qs = qs.filter(type_installation=type_inst)
        # Annulé = drapeau, pas une étape (comme « Perdu »). Par défaut on
        # montre tout ; ?annule=only / ?annule=sans pour filtrer côté UI.
        annule = params.get('annule')
        if self.action == 'list':
            if annule == 'only':
                qs = qs.filter(annule=True)
            elif annule == 'sans':
                qs = qs.filter(annule=False)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS + [
            'historique', 'export', 'checklist', 'equipements',
            'besoin_materiel',
        ]:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'creer_depuis_devis', 'noter', 'mise_en_service',
            'annuler', 'reactiver', 'toggle_checklist', 'set_serials',
            'commander_besoin',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.created_by = self.request.user
        serializer.instance.save(update_fields=['created_by'])
        ensure_checklist(serializer.instance)
        activity.log_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        old = Installation.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        inst = serializer.instance
        activity.log_changes(old, inst, self.request.user)
        # N7 — réception au fil de l'eau : si le statut vient de passer à un état
        # réceptionné (mise en service / clôture), matérialise le système
        # installé (date de réception + équipements auto). Idempotent.
        if (old.statut not in Installation.RECEIVED_STATUTS
                and inst.statut in Installation.RECEIVED_STATUTS):
            self._mark_received(inst)

    def _mark_received(self, inst):
        """Matérialise le système installé (N7) et journalise les équipements
        auto-créés dans le chatter du chantier."""
        created = mark_received(inst, user=self.request.user)
        if created:
            noms = ', '.join(eq.produit.nom for eq in created)
            activity.log_note(
                inst, self.request.user,
                f"Système installé : {len(created)} équipement(s) "
                f"auto-créé(s) ({noms})")

    @action(detail=False, methods=['post'], url_path='creer-depuis-devis',
            permission_classes=[IsResponsableOrAdmin])
    def creer_depuis_devis(self, request):
        """Crée un chantier pré-rempli depuis un devis accepté. Si un chantier
        existe déjà pour ce devis, le RETOURNE (jamais de doublon)."""
        from apps.ventes.models import Devis
        company = request.user.company
        devis_id = request.data.get('devis')
        devis = Devis.objects.filter(pk=devis_id).first()
        if devis is None or devis.company_id != company.id:
            return Response({'detail': 'Devis inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if devis.statut != Devis.Statut.ACCEPTE:
            return Response(
                {'detail': 'Le devis doit être « Accepté » pour créer le chantier.'},
                status=status.HTTP_400_BAD_REQUEST)
        inst, created = create_installation_from_devis(
            devis, request.user, company)
        if created:
            activity.log_creation(inst, request.user)
        data = InstallationSerializer(inst, context={'request': request}).data
        data['created'] = created
        return Response(
            data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='besoin-materiel',
            permission_classes=[IsAnyRole])
    def besoin_materiel(self, request, pk=None):
        """Besoin matériel du chantier vs stock disponible (N13).

        Lecture seule : dérive du devis source du chantier, confronte au
        stock (Produit.quantite_stock) et signale les manques (manque > 0)."""
        from apps.stock.services import compute_besoin_materiel
        inst = self.get_object()
        besoins = compute_besoin_materiel(inst)
        items = [
            {
                'produit_id': b['produit_id'],
                'sku': b['sku'],
                'designation': b['designation'],
                'requis': b['requis'],
                'disponible': b['disponible'],
                'manque': b['manque'],
                'fournisseur_id': b['fournisseur_id'],
                'fournisseur_nom': b['fournisseur_nom'],
            }
            for b in besoins
        ]
        return Response({
            'installation': inst.id,
            'reference': inst.reference,
            'items': items,
            'nb_manques': sum(1 for it in items if it['manque'] > 0),
        })

    @action(detail=True, methods=['post'], url_path='commander-besoin',
            permission_classes=[IsResponsableOrAdmin])
    def commander_besoin(self, request, pk=None):
        """Crée un BonCommandeFournisseur BROUILLON pour les manques (N13).

        Corps : {"fournisseur": <id>} (optionnel : sinon le fournisseur du
        premier produit en pénurie). Renvoie le BCF brouillon créé."""
        from apps.stock.services import (
            draft_bcf_for_shortfall, resolve_fournisseur,
        )
        from apps.stock.serializers import BonCommandeFournisseurSerializer
        inst = self.get_object()
        company = request.user.company
        fournisseur = resolve_fournisseur(
            company, request.data.get('fournisseur'), inst)
        if fournisseur is None:
            return Response(
                {'detail': (
                    'Aucun fournisseur indiqué et aucun fournisseur par '
                    'défaut sur les produits manquants.'
                )},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            bon, nb = draft_bcf_for_shortfall(
                inst, fournisseur, request.user, company)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        data = BonCommandeFournisseurSerializer(
            bon, context={'request': request}).data
        data['nb_lignes'] = nb
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        inst = self.get_object()
        return Response(
            InstallationActivitySerializer(inst.activites.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='checklist',
            permission_classes=[IsAnyRole])
    def checklist(self, request, pk=None):
        """Checklist d'exécution du chantier (auto-remplie si vide)."""
        inst = self.get_object()
        items = ensure_checklist(inst)
        return Response(ChecklistItemSerializer(items, many=True).data)

    @action(detail=True, methods=['post'],
            url_path=r'checklist/(?P<item_id>\d+)/toggle',
            permission_classes=[IsResponsableOrAdmin])
    def toggle_checklist(self, request, pk=None, item_id=None):
        """Bascule une étape de la checklist : enregistre fait/par-qui/quand et
        journalise la bascule dans l'Historique du chantier."""
        from django.utils import timezone
        inst = self.get_object()
        ensure_checklist(inst)
        item = ChecklistItem.objects.filter(
            installation=inst, pk=item_id).first()
        if item is None:
            return Response({'detail': 'Étape inconnue.'},
                            status=status.HTTP_404_NOT_FOUND)
        # Bascule, ou force la valeur si 'done' est fourni explicitement.
        if 'done' in request.data:
            new_done = bool(request.data.get('done'))
        else:
            new_done = not item.done
        item.done = new_done
        if new_done:
            item.done_by = request.user
            item.done_at = timezone.now()
        else:
            item.done_by = None
            item.done_at = None
        item.save(update_fields=['done', 'done_by', 'done_at'])
        verbe = 'cochée' if new_done else 'décochée'
        activity.log_note(
            inst, request.user, f"Étape « {item.label} » {verbe}")
        return Response(ChecklistItemSerializer(item).data)

    @action(detail=True, methods=['get'], url_path='equipements',
            permission_classes=[IsAnyRole])
    def equipements(self, request, pk=None):
        """Composants installés du chantier (système installé / parc) — n° de
        série + horloges de garantie. Lecture seule ici ; la saisie des n° de
        série passe par `set-serials`."""
        from apps.sav.serializers import EquipementSerializer
        inst = self.get_object()
        qs = inst.equipements.select_related('produit').all()
        return Response(EquipementSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='set-serials',
            permission_classes=[IsResponsableOrAdmin])
    def set_serials(self, request, pk=None):
        """Saisit les n° de série des composants du chantier (N9).

        Corps : {"serials": {"<equipement_id>": "SN123", ...}}. NE BLOQUE JAMAIS
        rien si un n° est vide — un n° vide remet simplement le champ à None.
        Les équipements visés doivent appartenir au chantier (scope société via
        get_object). Retourne la liste des équipements à jour.
        """
        from apps.sav.models import Equipement
        from apps.sav.serializers import EquipementSerializer
        inst = self.get_object()
        serials = request.data.get('serials') or {}
        if not isinstance(serials, dict):
            return Response({'serials': 'Format attendu : objet id→n° série.'},
                            status=status.HTTP_400_BAD_REQUEST)
        updated = []
        for eq_id, serie in serials.items():
            eq = Equipement.objects.filter(
                installation=inst, pk=eq_id).first()
            if eq is None:
                continue
            valeur = (serie or '').strip() or None
            if eq.numero_serie != valeur:
                eq.numero_serie = valeur
                eq.save(update_fields=['numero_serie', 'date_modification'])
            updated.append(eq)
        return Response(EquipementSerializer(updated, many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        inst = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(inst, request.user, body)
        return Response(InstallationActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='mise-en-service',
            permission_classes=[IsResponsableOrAdmin])
    def mise_en_service(self, request, pk=None):
        """Enregistre la mise en service : date, PV/notes, valeurs mesurées
        optionnelles, et passe le statut à « Mise en service ».

        NOTE — point d'accroche FUTUR : c'est ici que démarrera la garantie
        une fois qu'un registre d'équipements (n° de série) existera. Aucune
        logique de garantie n'est construite maintenant (modèle absent).
        """
        inst = self.get_object()
        old = Installation.objects.get(pk=inst.pk)
        data = request.data
        if data.get('date_mise_en_service'):
            inst.date_mise_en_service = data['date_mise_en_service']
        if 'mes_pv_notes' in data:
            inst.mes_pv_notes = data.get('mes_pv_notes')
        if data.get('mes_production_test') not in (None, ''):
            inst.mes_production_test = data['mes_production_test']
        if data.get('mes_tension') not in (None, ''):
            inst.mes_tension = data['mes_tension']
        was_received = old.statut in Installation.RECEIVED_STATUTS
        inst.statut = Installation.Statut.MISE_EN_SERVICE
        inst.save()
        activity.log_changes(old, inst, request.user)
        activity.log_note(
            inst, request.user,
            "Mise en service enregistrée"
            + (f" le {inst.date_mise_en_service}" if inst.date_mise_en_service else ""))
        # N7 — la mise en service réceptionne le système installé (équipements
        # auto + date de réception). Idempotent si déjà réceptionné.
        if not was_received:
            self._mark_received(inst)
        return Response(
            InstallationSerializer(inst, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        """Annule le chantier (DRAPEAU avec motif — pas une étape)."""
        inst = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not inst.annule:
            inst.annule = True
            inst.motif_annulation = motif or None
            inst.save(update_fields=['annule', 'motif_annulation'])
            activity.log_note(
                inst, request.user,
                f"Chantier annulé{(' : ' + motif) if motif else ''}")
        return Response(
            InstallationSerializer(inst, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reactiver',
            permission_classes=[IsResponsableOrAdmin])
    def reactiver(self, request, pk=None):
        inst = self.get_object()
        if inst.annule:
            inst.annule = False
            inst.motif_annulation = None
            inst.save(update_fields=['annule', 'motif_annulation'])
            activity.log_note(inst, request.user, "Chantier réactivé")
        return Response(
            InstallationSerializer(inst, context={'request': request}).data)


class ParcInstalleViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Parc installé (N8/N10) — systèmes installés = chantiers RÉCEPTIONNÉS et
    actifs au parc. Lecture seule, scopé à la société. Orienté client-asset :
    jamais de prix d'achat / marge.

    Liste filtrable (client / ville / marque de composant / bande de puissance
    kWc / année de réception) + données GPS pour la carte. L'action `hub`
    agrège pour UN système : composants (équipements + n° série), garanties,
    tickets SAV liés, contrats de maintenance, et un placeholder de monitoring.
    """
    queryset = Installation.objects.select_related(
        'client', 'devis', 'technicien_responsable',
    ).prefetch_related('equipements__produit').filter(
        parc_actif=True,
        statut__in=Installation.RECEIVED_STATUTS,
    )
    serializer_class = ParcInstalleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'site_ville',
        'site_adresse',
    ]
    ordering_fields = [
        'reference', 'date_reception', 'date_mise_en_service',
        'puissance_installee_kwc',
    ]
    ordering = ['-date_reception', '-date_mise_en_service']

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        client = params.get('client')
        ville = params.get('ville')
        marque = params.get('marque')
        type_inst = params.get('type_installation')
        annee = params.get('annee')
        kwc_min = params.get('kwc_min')
        kwc_max = params.get('kwc_max')
        if client:
            qs = qs.filter(client_id=client)
        if ville:
            qs = qs.filter(site_ville__icontains=ville)
        if marque:
            qs = qs.filter(
                equipements__produit__marque__icontains=marque).distinct()
        if type_inst:
            qs = qs.filter(type_installation=type_inst)
        if annee:
            try:
                an = int(annee)
                # Année de réception (sinon mise en service comme repli).
                qs = qs.filter(
                    models.Q(date_reception__year=an)
                    | (models.Q(date_reception__isnull=True)
                       & models.Q(date_mise_en_service__year=an)))
            except (ValueError, TypeError):
                pass
        for bound, lookup in ((kwc_min, 'gte'), (kwc_max, 'lte')):
            if bound not in (None, ''):
                try:
                    qs = qs.filter(
                        **{f'puissance_installee_kwc__{lookup}': float(bound)})
                except (ValueError, TypeError):
                    pass
        return qs

    @action(detail=False, methods=['get'], url_path='carte',
            permission_classes=[IsAnyRole])
    def carte(self, request):
        """Points GPS des systèmes installés pour la vue carte (N8).

        Renvoie uniquement les systèmes géolocalisés (gps_lat/lng non nuls),
        respecte les filtres de la liste. Léger : pas de dépendance carto."""
        qs = self.get_queryset().filter(
            gps_lat__isnull=False, gps_lng__isnull=False)
        points = [{
            'id': obj.id,
            'reference': obj.reference,
            'client_nom': (f"{obj.client.nom} {obj.client.prenom or ''}".strip()
                           if obj.client else None),
            'site_ville': obj.site_ville,
            'gps_lat': obj.gps_lat,
            'gps_lng': obj.gps_lng,
            'puissance_installee_kwc': obj.puissance_installee_kwc,
            'type_installation': obj.type_installation,
        } for obj in qs]
        return Response(points)

    @action(detail=True, methods=['get'], url_path='hub',
            permission_classes=[IsAnyRole])
    def hub(self, request, pk=None):
        """Hub d'UN système installé (N10) — agrège ses relations existantes :
        composants (équipements + garanties), tickets SAV, contrats de
        maintenance, et un placeholder de monitoring. Lecture seule."""
        from apps.sav.serializers import (
            EquipementSerializer, TicketSerializer, ContratMaintenanceSerializer,
        )
        inst = self.get_object()
        equipements = inst.equipements.select_related('produit').all()
        tickets = inst.tickets.select_related(
            'client', 'equipement', 'equipement__produit',
            'technicien_responsable').all()
        contrats = inst.contrats_maintenance.select_related('client').all()
        ctx = {'request': request}
        data = ParcInstalleSerializer(inst, context=ctx).data
        data['equipements'] = EquipementSerializer(
            equipements, many=True, context=ctx).data
        data['tickets'] = TicketSerializer(
            tickets, many=True, context=ctx).data
        data['contrats_maintenance'] = ContratMaintenanceSerializer(
            contrats, many=True, context=ctx).data
        # Placeholder monitoring : aucune intégration de supervision n'existe.
        data['monitoring'] = {'statut': 'non_configure',
                              'statut_display': 'Non configuré'}
        return Response(data)


def _slugify_type_key(label):
    """Clé stable (a-z0-9_) dérivée d'un libellé, pour un nouveau type."""
    import re
    import unicodedata
    norm = unicodedata.normalize('NFKD', label or '')
    norm = norm.encode('ascii', 'ignore').decode('ascii').lower()
    norm = re.sub(r'[^a-z0-9]+', '_', norm).strip('_')
    return norm or 'type'


class TypeInterventionViewSet(TenantMixin, viewsets.ModelViewSet):
    """Types d'intervention gérés (Paramètres → Chantiers).

    Lecture tout rôle, écriture admin. Un type utilisé par un ordre de travail
    ne peut pas être supprimé (message français clair).
    """
    queryset = TypeIntervention.objects.all()
    serializer_class = TypeInterventionSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company
        label = serializer.validated_data.get('label', '')
        base = _slugify_type_key(label)
        key = base
        i = 2
        while TypeIntervention.objects.filter(company=company, key=key).exists():
            key = f'{base}_{i}'
            i += 1
        serializer.save(company=company, key=key)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if 'key' in request.data and request.data.get('key') != instance.key:
            return Response(
                {'detail': "La clé d'un type ne peut pas être modifiée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        in_use = Intervention.objects.filter(
            company=instance.company,
            type_intervention=instance.key).exists()
        if in_use:
            return Response(
                {'detail': "Ce type est utilisé par des ordres de travail — "
                           "il ne peut pas être supprimé. Archivez-le plutôt."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class InterventionViewSet(TenantMixin, viewsets.ModelViewSet):
    """Ordres de travail rattachés à un chantier. Scopés à la société."""
    queryset = Intervention.objects.select_related(
        'installation', 'technicien').all()
    serializer_class = InterventionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_prevue', 'date_realisee', 'date_creation']
    ordering = ['-date_prevue']

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        ticket = self.request.query_params.get('ticket')
        if installation:
            qs = qs.filter(installation_id=installation)
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        # Tenant safety : le chantier ciblé doit appartenir à la société.
        from rest_framework.exceptions import ValidationError
        installation = serializer.validated_data.get('installation')
        ticket = serializer.validated_data.get('ticket')
        company = self.request.user.company
        if installation is not None and installation.company_id != company.id:
            raise ValidationError({'installation': 'Chantier inconnu.'})
        # Tenant safety : le ticket SAV lié doit aussi appartenir à la société.
        if ticket is not None and ticket.company_id != company.id:
            raise ValidationError({'ticket': 'Ticket inconnu.'})
        serializer.save(company=company, created_by=self.request.user)
        # Trace l'ajout d'intervention dans le chatter du chantier.
        if installation is not None:
            activity.log_note(
                installation, self.request.user,
                f"Intervention ajoutée : "
                f"{serializer.instance.get_type_intervention_display()}")
