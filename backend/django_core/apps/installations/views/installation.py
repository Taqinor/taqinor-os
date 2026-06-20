from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401

from authentication.mixins import TenantMixin  # noqa: F401
from authentication.permissions import (  # noqa: F401
    IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)
from django.utils import timezone  # noqa: F401

from .. import activity  # noqa: F401
from .. import intervention_activity  # noqa: F401
from ..models import (  # noqa: F401
    Installation, Intervention, TypeIntervention, ChecklistTemplate,
    ChecklistEtapeModele, ShotListSlot, ComponentSerial,
    ConsommationLigne, VoiceMemo, Reserve, ToolReturn, SafetyChecklistSlot,
)
from ..serializers import (  # noqa: F401
    InstallationSerializer, InterventionSerializer,
    InstallationActivitySerializer, InterventionActivitySerializer,
    TypeInterventionSerializer, ChecklistTemplateSerializer,
    ChecklistEtapeModeleSerializer, ChantierChecklistItemSerializer,
    ShotListSlotSerializer, InterventionPreparationSerializer,
    ComponentSerialSerializer, MaterielConsommationSerializer,
    ConsommationLigneSerializer, VoiceMemoSerializer, ReserveSerializer,
    ToolReturnSerializer, SafetyChecklistSlotSerializer, SafetySignoffSerializer,
)
from ..services import (  # noqa: F401
    create_installation_from_devis, seed_checklist_etapes,
    ensure_checklist_items, ensure_default_template,
)
from .. import field_services  # noqa: F401
from .. import field_capture  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# Types d'intervention par défaut (clés = Intervention.Type), tous « système ».
_DEFAULT_TYPES_INTERVENTION = [
    ('pose', 'Pose'),
    ('raccordement', 'Raccordement'),
    ('mise_en_service', 'Mise en service'),
    ('controle', 'Contrôle'),
    ('depannage', 'Dépannage'),
]


# Jalon de statut canonique → champ date à horodater (N6/N7) si vide.
_STATUT_DATE_FIELD = {
    Installation.Statut.SIGNE: 'date_signature',
    Installation.Statut.MATERIEL_COMMANDE: 'date_materiel_commande',
    Installation.Statut.PLANIFIE: 'date_pose_prevue',
    Installation.Statut.INSTALLE: 'date_pose_reelle',
    Installation.Statut.RECEPTIONNE: 'date_reception',
    Installation.Statut.CLOTURE: 'date_cloture',
}


def _stamp_statut_dates(inst, old_statut):
    """Pose la date du jalon atteint si elle est vide (jamais d'écrasement).
    Travaille sur le statut CANONIQUE pour couvrir aussi les statuts hérités."""
    canon = Installation.canonical_statut(inst.statut)
    if Installation.canonical_statut(old_statut) == canon:
        return
    field = _STATUT_DATE_FIELD.get(canon)
    if field and getattr(inst, field, None) is None:
        setattr(inst, field, timezone.localdate())
        inst.save(update_fields=[field])


def _apply_stock_statut_effects(inst, canon_old, canon_new, user):
    """N14 — effets STOCK d'un changement de statut canonique du chantier.

    À l'arrivée à « Installé », consomme les réservations (une SORTIE par SKU,
    idempotente côté service). À l'arrivée à « Clôturé », libère les
    réservations restantes non consommées. Le service est idempotent : il ne
    rejoue jamais une réservation déjà consommée."""
    from ..services import consume_reservations, release_reservations  # noqa: F401
    if canon_new == canon_old:
        return
    if canon_new == Installation.Statut.INSTALLE:
        nb = consume_reservations(inst, user)
        if nb:
            activity.log_note(
                inst, user,
                f"Stock consommé — {nb} référence(s) sortie(s) du stock "
                f"(chantier « Installé »).")
    elif canon_new == Installation.Statut.CLOTURE:
        nb = release_reservations(inst)
        if nb:
            activity.log_note(
                inst, user,
                f"Réservation de stock libérée — {nb} référence(s) "
                f"(chantier clôturé).")


def seed_types_intervention(company):
    if company is None or TypeIntervention.objects.filter(company=company).exists():
        return
    for i, (cle, libelle) in enumerate(_DEFAULT_TYPES_INTERVENTION):
        TypeIntervention.objects.get_or_create(
            company=company, cle=cle,
            defaults={'libelle': libelle, 'ordre': i, 'protege': True})

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class InstallationViewSet(TenantMixin, viewsets.ModelViewSet):
    """Chantiers + historique « chatter ». Tout est scopé à la société du
    user ; l'acteur et la société sont posés côté serveur, jamais lus du corps.
    """
    queryset = Installation.objects.select_related(
        'client', 'devis', 'lead', 'technicien_responsable',
    ).prefetch_related(
        # F3 — l'InterventionSerializer imbriqué lit l'installation liée (réf,
        # client, devis), la camionnette et l'équipe : on précharge pour éviter
        # un N+1 sur la liste des chantiers.
        'interventions__installation__client',
        'interventions__installation__devis',
        'interventions__camionnette',
        'interventions__equipe',
        # Parc — l'état de garantie agrégé (parc_garantie_etat) lit les
        # équipements posés du système : on précharge pour éviter un N+1.
        'equipements',
    ).all()
    serializer_class = InstallationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'site_ville',
        # N9 — recherche aussi par référence du devis lié et par installateur.
        'devis__reference', 'technicien_responsable__username',
    ]
    ordering_fields = ['reference', 'date_creation', 'date_pose_prevue', 'statut']
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que les
        # chantiers qu'il a créés ou dont il est le technicien responsable /
        # ceux de son équipe. 'all' → inchangé.
        from authentication.scoping import scope_queryset
        qs = scope_queryset(
            qs, self.request.user, ['technicien_responsable', 'created_by'])
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
        # N9 — « Mes chantiers » : ceux dont l'utilisateur courant est
        # l'installateur responsable (résolu côté serveur, jamais du corps).
        if params.get('mine') in ('1', 'true', 'only'):
            qs = qs.filter(technicien_responsable=self.request.user)
        # Annulé = drapeau, pas une étape (comme « Perdu »). Par défaut on
        # montre tout ; ?annule=only / ?annule=sans pour filtrer côté UI.
        annule = params.get('annule')
        if self.action == 'list':
            if annule == 'only':
                qs = qs.filter(annule=True)
            elif annule == 'sans':
                qs = qs.filter(annule=False)
        # N41/N42 — filtres dossier réglementaire loi 82-21 / Article 33.
        if params.get('regime'):
            qs = qs.filter(regime_8221=params.get('regime'))
        if params.get('dossier_statut'):
            qs = qs.filter(dossier_statut=params.get('dossier_statut'))
        if params.get('art33') in ('1', 'true', 'only'):
            qs = qs.filter(art33_regularisation=True)
        # N8 — parc installé : systèmes réceptionnés/clôturés, actifs, non
        # annulés (statuts hérités « mise_en_service » inclus via la map).
        if params.get('parc') in ('1', 'true', 'only'):
            parc_statuts = [
                Installation.Statut.RECEPTIONNE,
                Installation.Statut.CLOTURE,
                Installation.Statut.MISE_EN_SERVICE,
            ]
            qs = qs.filter(statut__in=parc_statuts, parc_actif=True, annule=False)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS + [
            'historique', 'besoin_materiel', 'checklist', 'regime_suggestion',
            'rapport_energie',
        ]:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'creer_depuis_devis', 'noter', 'mise_en_service',
            'annuler', 'reactiver', 'commander_besoin', 'cocher_checklist',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        inst = serializer.instance
        inst.created_by = self.request.user
        fields = ['created_by']
        # N66 — installateur par défaut configuré, si aucun n'a été fourni.
        if not inst.technicien_responsable_id:
            from ..services import default_installer_for
            default = default_installer_for(inst.company)
            if default is not None:
                inst.technicien_responsable = default
                fields.append('technicien_responsable')
        inst.save(update_fields=fields)
        activity.log_creation(inst, self.request.user)

    def perform_update(self, serializer):
        old = Installation.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        inst = serializer.instance
        _stamp_statut_dates(inst, old.statut)
        activity.log_changes(old, inst, self.request.user)
        # N7 — au passage à « Réceptionné », le chantier devient un système
        # installé actif (parc) : on trace l'événement dans le chatter.
        canon_old = Installation.canonical_statut(old.statut)
        canon_new = Installation.canonical_statut(inst.statut)
        if (canon_new == Installation.Statut.RECEPTIONNE
                and canon_old != Installation.Statut.RECEPTIONNE):
            activity.log_note(
                inst, self.request.user,
                "Chantier réceptionné — système ajouté au parc installé.")
        # N14 — applique les effets stock du changement de statut (consomme à
        # « Installé », libère à la clôture). Idempotent côté service.
        _apply_stock_statut_effects(
            inst, canon_old, canon_new, self.request.user)

    @action(detail=False, methods=['post'], url_path='creer-depuis-devis',
            permission_classes=[IsResponsableOrAdmin])
    def creer_depuis_devis(self, request):
        """Crée un chantier pré-rempli depuis un devis accepté. Si un chantier
        existe déjà pour ce devis, le RETOURNE (jamais de doublon)."""
        from apps.ventes.selectors import get_devis_by_pk, is_devis_accepte
        company = request.user.company
        devis_id = request.data.get('devis')
        devis = get_devis_by_pk(devis_id)
        if devis is None or devis.company_id != company.id:
            return Response({'detail': 'Devis inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not is_devis_accepte(devis):
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

    @action(detail=False, methods=['get'], url_path='regime-suggestion',
            permission_classes=[IsAnyRole])
    def regime_suggestion(self, request):
        """N43 — régime loi 82-21 suggéré pour une puissance (kWc), via les
        seuils éditables de la société. ?kwc=<nombre>. Défaut modifiable."""
        from ..regime import suggest_for_company, regime_thresholds
        from ..models import Installation
        kwc = request.query_params.get('kwc')
        company = request.user.company
        code = suggest_for_company(kwc, company)
        label = dict(Installation.Regime8221.choices).get(code, code)
        seuil_decl, seuil_anre = regime_thresholds(company)
        return Response({
            'code': code, 'label': label,
            'seuil_declaration_kwc': seuil_decl,
            'seuil_anre_kwc': seuil_anre,
        })

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        inst = self.get_object()
        return Response(
            InstallationActivitySerializer(inst.activites.all(), many=True).data)

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
        canon_old = Installation.canonical_statut(old.statut)
        inst.statut = Installation.Statut.MISE_EN_SERVICE
        inst.save()
        canon_new = Installation.canonical_statut(inst.statut)
        # ERR40 — route le changement de statut par les MÊMES aides que
        # `perform_update` : horodate le jalon (« Mise en service » se rabat sur
        # « Réceptionné » → `date_reception`) et applique les effets stock du
        # changement (consommation des réservations). Sans cela le chantier
        # comptait au parc sans `date_reception` ni sortie de stock.
        _stamp_statut_dates(inst, old.statut)
        _apply_stock_statut_effects(inst, canon_old, canon_new, request.user)
        activity.log_changes(old, inst, request.user)
        # Note de chatter explicite incluant les valeurs mesurées (production /
        # tension) quand elles sont renseignées — pas seulement la date.
        mesures = []
        if inst.mes_production_test not in (None, ''):
            mesures.append(f"production test {inst.mes_production_test}")
        if inst.mes_tension not in (None, ''):
            mesures.append(f"tension {inst.mes_tension}")
        activity.log_note(
            inst, request.user,
            "Mise en service enregistrée"
            + (f" le {inst.date_mise_en_service}" if inst.date_mise_en_service else "")
            + (f" — {', '.join(mesures)}" if mesures else ""))
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
            # N14 — libère la réservation de stock restante (non consommée).
            from ..services import release_reservations
            nb = release_reservations(inst)
            if nb:
                activity.log_note(
                    inst, request.user,
                    f"Réservation de stock libérée — {nb} référence(s) "
                    f"(chantier annulé).")
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

    @action(detail=True, methods=['get'], url_path='checklist',
            permission_classes=[IsAnyRole])
    def checklist(self, request, pk=None):
        """Checklist d'exécution du chantier (N4). Matérialise les étapes
        depuis les modèles à la première consultation, puis renvoie l'état +
        le pourcentage d'avancement."""
        inst = self.get_object()
        items = ensure_checklist_items(inst)
        done = sum(1 for it in items if it.fait)
        return Response({
            'installation': inst.id,
            'items': ChantierChecklistItemSerializer(items, many=True).data,
            'completion': round(100 * done / len(items)) if items else None,
        })

    @action(detail=True, methods=['post'], url_path='cocher-checklist',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_checklist(self, request, pk=None):
        """Coche/décoche une étape (N4) et, optionnellement, enregistre des
        n° de série pour l'étape concernée (N9). La saisie de série ne bloque
        JAMAIS la complétion : `equipements` vide est accepté.

        Corps : {"cle": <str>, "fait": <bool>,
                 "equipements": [{"produit": <id>, "numero_serie": <str>}]}
        """
        inst = self.get_object()
        ensure_checklist_items(inst)
        cle = request.data.get('cle')
        item = inst.checklist.filter(cle=cle).first()
        if item is None:
            return Response({'detail': 'Étape inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        fait = bool(request.data.get('fait', True))
        item.fait = fait
        item.fait_par = request.user if fait else None
        item.fait_le = timezone.now() if fait else None
        item.save(update_fields=['fait', 'fait_par', 'fait_le'])

        # N9 — saisie optionnelle de n° de série → équipements du parc.
        created_equip = 0
        captures = []  # libellés « produit (n° série) » des relevés créés.
        for eq in (request.data.get('equipements') or []):
            produit_id = eq.get('produit')
            serie = (eq.get('numero_serie') or '').strip()
            if not produit_id:
                continue
            from apps.stock.selectors import get_produit_scoped
            from apps.sav.services import create_equipement_from_serial
            produit = get_produit_scoped(inst.company, produit_id)
            if produit is None:
                continue
            create_equipement_from_serial(
                company=inst.company, produit=produit, installation=inst,
                numero_serie=serie or None,
                date_pose=inst.date_pose_reelle or timezone.localdate(),
                created_by=request.user)
            created_equip += 1
            captures.append(
                f"{produit.nom}"
                + (f" (n° {serie})" if serie else " (sans n° de série)"))

        # N16 — la note liste les produits/séries capturés (pas juste un compte).
        capture_txt = (f" — {', '.join(captures)}" if captures
                       else (f" (+{created_equip} équipement(s))" if created_equip else ""))
        activity.log_note(
            inst, request.user,
            f"Checklist : « {item.libelle} » {'cochée' if fait else 'décochée'}"
            + capture_txt)
        items = list(inst.checklist.all())
        done = sum(1 for it in items if it.fait)
        return Response({
            'items': ChantierChecklistItemSerializer(items, many=True).data,
            'completion': round(100 * done / len(items)) if items else None,
            'equipements_crees': created_equip,
        })

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
                # N14 — quantité engagée-mais-non-consommée (toutes réservations
                # actives de la société, ce chantier inclus).
                'reserve': b.get('reserve', 0),
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

    @action(detail=True, methods=['get'], url_path='rapport-energie',
            permission_classes=[IsAnyRole])
    def rapport_energie(self, request, pk=None):
        """Rapport de production énergétique ESTIMÉE (PDF client-facing, FR).

        Estimation à partir de la puissance nominale du système (kWc) et
        d'hypothèses surchargeables (rendement spécifique, tarif, facteur CO₂),
        ou d'une production annuelle saisie manuellement. AUCune donnée mesurée.
        Le chantier est résolu via la société de l'utilisateur (404 sinon).
        Strictement client-facing : aucun prix d'achat. Paramètres de requête :
        nb_mois, date_debut, date_fin (AAAA-MM-JJ), production_annuelle_kwh,
        rendement, tarif, co2.
        """
        from django.http import HttpResponse
        from datetime import datetime
        from .. import energy_report
        inst = self.get_object()

        def _parse_date(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        qp = request.query_params
        params = {
            'nb_mois': qp.get('nb_mois'),
            'date_debut': _parse_date(qp.get('date_debut')),
            'date_fin': _parse_date(qp.get('date_fin')),
            'production_annuelle_kwh': qp.get('production_annuelle_kwh'),
            'rendement_kwh_par_kwc_an': qp.get('rendement'),
            'tarif_mad_par_kwh': qp.get('tarif'),
            'co2_kg_par_kwh': qp.get('co2'),
        }
        pdf_bytes = energy_report.render_energy_report_pdf(inst, params)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="rapport-production-{inst.reference}.pdf"')
        return resp
