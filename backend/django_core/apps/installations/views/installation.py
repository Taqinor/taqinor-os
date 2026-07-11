from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401

from authentication.mixins import TenantMixin  # noqa: F401
from authentication.permissions import (  # noqa: F401
    IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)
from core.viewsets import CompanyScopedModelViewSet
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
    notifier_reception_solde_a_facturer,
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


def _apply_reception_handover(inst, canon_old, canon_new, user):
    """FG70 — remise de garantie automatique au passage à « Réceptionné ».

    Balaye la nomenclature gelée du chantier (`inst.bom`) et garantit un
    équipement de parc (sans n° de série) par ligne de BoM ayant un produit
    catalogue — la couverture de garantie ne dépend plus d'une saisie manuelle
    de chaque n° de série. CROSS-APP : l'écriture passe par
    `apps.sav.services` (jamais d'import direct des modèles SAV). Idempotent :
    un re-passage à « Réceptionné » ne crée aucun doublon. Ajoute une note de
    remise au chatter listant les équipements couverts."""
    if canon_new == canon_old or canon_new != Installation.Statut.RECEPTIONNE:
        return
    from apps.sav.services import sweep_bom_to_parc
    from apps.stock.selectors import get_produit_scoped

    def _resolve(produit_id):
        return get_produit_scoped(inst.company, produit_id)

    date_pose = inst.date_reception or inst.date_pose_reelle or timezone.localdate()
    resume = sweep_bom_to_parc(
        installation=inst, company=inst.company, date_pose=date_pose,
        created_by=user, resolve_produit=_resolve)
    crees = resume['crees']
    existants = resume['existants']
    if crees or existants:
        couverts = ', '.join(
            ligne['designation'] for ligne in resume['lignes']
            if ligne['designation'])
        detail = f" — {couverts}" if couverts else ''
        activity.log_note(
            inst, user,
            "Remise de garantie : "
            f"{crees} équipement(s) ajouté(s) au parc"
            + (f", {existants} déjà couvert(s)" if existants else "")
            + detail + ".")
    # CH4 — au passage à « Réceptionné » (gate de remise), assemble le pack de
    # remise client (idempotent, dégrade proprement). Le pack RÉFÉRENCE l'état
    # réel du chantier ; sa génération n'échoue jamais.
    from ..services import generer_handover_pack
    pack = generer_handover_pack(inst, user)
    activity.log_note(
        inst, user,
        "Pack de remise "
        + ("assemblé (complet)." if pack.complet
           else "assemblé (pièces manquantes — voir le détail)."))
    return resume


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


class InstallationViewSet(CompanyScopedModelViewSet):
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
            # FG74 — Gantt multi-chantier (lecture seule).
            'gantt',
            # FG75 — relevés de toiture / drone (lecture).
            'releves',
            # FG70 — fiche de remise de garantie (lecture).
            'remise_garantie',
            # FG77 — contrôle de préparation avant pose (lecture).
            'readiness',
            # CH2 — parcours d'étapes + état des gates (lecture).
            'etapes',
            # CH3 — fiche de recette IEC 62446-1 (lecture ; POST auto-gardé).
            'recette',
            # CH4 — pack de remise client (lecture ; POST auto-gardé).
            'pack_remise',
        ]:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'creer_depuis_devis', 'noter', 'mise_en_service',
            'annuler', 'reactiver', 'commander_besoin', 'cocher_checklist',
            # CH2 — avancement d'étape (gates appliqués côté service).
            'avancer_etape',
            # FG75 — ajout / suppression de relevés.
            'ajouter_releve', 'supprimer_releve',
            # FG79 — scaffold interventions standard.
            'creer_interventions_standard',
            # ZSTK11 — réservation stock explicite (mode manuel).
            'reserver_stock',
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
        # CH2 — GATES BLOQUANTS : un changement de statut qui franchit une
        # étape bloquante aux exigences non réunies (checklist/photos/séries/
        # essais/matériel/dossier 82-21 + points d'arrêt QHSE) est REJETÉ avec
        # les raisons en français. Interrupteur : une société sans étapes
        # configurées garde exactement le comportement historique.
        nouveau_statut = serializer.validated_data.get('statut')
        franchit_vers_planifie = (
            nouveau_statut == Installation.Statut.PLANIFIE
            and nouveau_statut != old.statut)
        if nouveau_statut and nouveau_statut != old.statut:
            from rest_framework.exceptions import ValidationError
            from ..services import verifier_transition_statut
            raisons = verifier_transition_statut(old, nouveau_statut)
            if raisons:
                raise ValidationError({'statut': raisons})
        # YSERV1 — Gate « acompte encaissé » avant planification. Toggle OFF
        # (défaut) = comportement byte-identique. ON : un responsable/admin
        # (seul rôle admis en écriture ici) peut forcer avec un `motif`
        # obligatoire, journalisé au chatter.
        motif_override = (self.request.data.get('motif_override_acompte')
                          or '').strip()
        if franchit_vers_planifie:
            from rest_framework.exceptions import ValidationError
            from ..services import verifier_gate_acompte_planification
            raison = verifier_gate_acompte_planification(old)
            if raison:
                if not motif_override:
                    raise ValidationError({'statut': [raison]})
        super().perform_update(serializer)
        inst = serializer.instance
        _stamp_statut_dates(inst, old.statut)
        activity.log_changes(old, inst, self.request.user)
        # VX213 (b) — handoff AVAL : réassigner un chantier à un NOUVEAU
        # technicien le notifie (diff pré/post sur technicien_responsable_id).
        # `_notifier_chantier_assigne` no-op si absent ; best-effort (ne lève
        # jamais). On ne notifie QUE sur un vrai changement de titulaire.
        if (inst.technicien_responsable_id
                and inst.technicien_responsable_id != old.technicien_responsable_id):
            from ..services import _notifier_chantier_assigne
            _notifier_chantier_assigne(inst, inst.technicien_responsable)
        if franchit_vers_planifie and motif_override:
            activity.log_note(
                inst, self.request.user,
                f'Planifié sans acompte — motif : {motif_override}')
        # N7 — au passage à « Réceptionné », le chantier devient un système
        # installé actif (parc) : on trace l'événement dans le chatter.
        canon_old = Installation.canonical_statut(old.statut)
        canon_new = Installation.canonical_statut(inst.statut)
        if (canon_new == Installation.Statut.RECEPTIONNE
                and canon_old != Installation.Statut.RECEPTIONNE):
            activity.log_note(
                inst, self.request.user,
                "Chantier réceptionné — système ajouté au parc installé.")
            # YSERV7 — rappel de facturation pour la tranche SOLDE restante
            # (best-effort, idempotent, jamais de facture créée).
            try:
                notifier_reception_solde_a_facturer(inst, self.request.user)
            except Exception:  # pragma: no cover - défensif
                pass
        # FG70 — remise de garantie automatique : balaye le BoM gelé vers le
        # parc SAV (un équipement par ligne, série optionnelle). Idempotent.
        _apply_reception_handover(
            inst, canon_old, canon_new, self.request.user)
        # YSERV4 — événement bus au franchissement vers RECEPTIONNE (best-
        # effort, ne modifie aucun statut). Abonné : compta (enquête NPS).
        if (canon_new == Installation.Statut.RECEPTIONNE
                and canon_old != Installation.Statut.RECEPTIONNE):
            from core.events import chantier_receptionne
            chantier_receptionne.send(
                sender=Installation, installation=inst,
                user=self.request.user, ancien_statut=old.statut)
        # N14 — applique les effets stock du changement de statut (consomme à
        # « Installé », libère à la clôture). Idempotent côté service.
        _apply_stock_statut_effects(
            inst, canon_old, canon_new, self.request.user)
        # CH2 — aligne le pointeur d'étape sur le statut hérité (no-op tant
        # que la société n'a pas configuré ses étapes).
        if canon_new != canon_old:
            from ..services import sync_etape_from_statut
            sync_etape_from_statut(inst)

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
        # CH2 — « Mise en service » se rabat sur « Réceptionné » : le passage
        # est soumis aux mêmes gates bloquants que n'importe quel changement
        # de statut (no-op tant que la société n'a pas configuré ses étapes).
        from ..services import verifier_transition_statut
        raisons = verifier_transition_statut(
            old, Installation.Statut.MISE_EN_SERVICE)
        if raisons:
            return Response(
                {'detail': 'Étape bloquée par un gate.', 'raisons': raisons},
                status=status.HTTP_400_BAD_REQUEST)
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
        # FG70 — « Mise en service » se rabat sur « Réceptionné » : la remise de
        # garantie balaie le BoM gelé vers le parc SAV (idempotente côté service).
        _apply_reception_handover(inst, canon_old, canon_new, request.user)
        # YSERV4 — événement bus au franchissement vers RECEPTIONNE (best-
        # effort, ne modifie aucun statut). Abonné : compta (enquête NPS).
        if (canon_new == Installation.Statut.RECEPTIONNE
                and canon_old != Installation.Statut.RECEPTIONNE):
            from core.events import chantier_receptionne
            chantier_receptionne.send(
                sender=Installation, installation=inst,
                user=request.user, ancien_statut=old.statut)
        _apply_stock_statut_effects(inst, canon_old, canon_new, request.user)
        # CH2 — aligne le pointeur d'étape sur le nouveau statut.
        from ..services import sync_etape_from_statut
        sync_etape_from_statut(inst)
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
            # YSERV6 — solde les interventions non terminées (drapeau
            # orthogonal, jamais un statut supplémentaire), notifie les
            # techniciens assignés et les sort des vues kanban/calendrier.
            from ..services import annuler_interventions_ouvertes
            nb_interv = annuler_interventions_ouvertes(inst, request.user)
            if nb_interv:
                activity.log_note(
                    inst, request.user,
                    f"{nb_interv} intervention(s) ouverte(s) annulée(s) "
                    "(chantier annulé).")
            # YSERV9 — événement d'exception (best-effort, jamais de statut
            # devis/facture changé) : ventes peut signaler le devis/acompte
            # au responsable pour décider avoir vs retenue.
            try:
                from core.events import chantier_annule
                chantier_annule.send(
                    sender=inst.__class__, installation=inst,
                    user=request.user, company=inst.company)
            except Exception:  # pragma: no cover - défensif, best-effort
                pass
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
            # YSERV6 — lève le drapeau uniquement sur les interventions
            # annulées PAR cette annulation (traçabilité de provenance).
            from ..services import reactiver_interventions_annulees
            reactiver_interventions_annulees(inst, request.user)
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

    # ── FG74 — Gantt multi-chantier (lecture seule) ──────────────────────────
    @action(detail=False, methods=['get'], url_path='gantt',
            permission_classes=[IsAnyRole])
    def gantt(self, request):
        """FG74 — vue Gantt multi-chantier : une ligne par chantier avec les barres
        issues des jalons (date_signature → date_cloture). Lecture seule. Renvoie
        chantiers actifs (non clôturés, non annulés) avec leurs jalons datés pour
        un rendu recharts/Gantt côté frontend."""
        company = request.user.company
        qs = (Installation.objects
              .filter(company=company, annule=False)
              .exclude(statut=Installation.Statut.CLOTURE)
              .select_related('client', 'technicien_responsable')
              .order_by('date_pose_prevue', 'date_creation'))
        rows = []
        for inst in qs:
            rows.append({
                'id': inst.id,
                'reference': inst.reference,
                'client_nom': (f'{inst.client.prenom or ""} {inst.client.nom}'.strip()
                               if inst.client_id else None),
                'statut': inst.statut,
                'technicien_responsable': getattr(
                    inst.technicien_responsable, 'username', None),
                'jalons': {
                    'signature': str(inst.date_signature) if inst.date_signature else None,
                    'materiel_commande': str(inst.date_materiel_commande) if inst.date_materiel_commande else None,
                    'pose_prevue': str(inst.date_pose_prevue) if inst.date_pose_prevue else None,
                    'pose_fin_prevue': str(inst.date_pose_fin_prevue) if inst.date_pose_fin_prevue else None,
                    'pose_reelle': str(inst.date_pose_reelle) if inst.date_pose_reelle else None,
                    'mise_en_service': str(inst.date_mise_en_service) if inst.date_mise_en_service else None,
                    'reception': str(inst.date_reception) if inst.date_reception else None,
                    'cloture': str(inst.date_cloture) if inst.date_cloture else None,
                },
                'duree_pose_jours': inst.duree_pose_jours,
            })
        return Response(rows)

    # ── FG75 — relevés de toiture / drone (attachments chantier-level) ───────
    # Les relevés sont des Attachment generics liés à l'Installation avec
    # `phase` = 'releve_toiture' ou 'drone' (réutilise le champ phase existant
    # plutôt qu'un nouveau champ pour rester additif).
    _RELEVE_PHASES = ('releve', 'drone')

    @action(detail=True, methods=['get'], url_path='releves',
            permission_classes=[IsAnyRole])
    def releves(self, request, pk=None):
        """FG75 — liste les relevés de toiture / drone attachés au chantier."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        inst = self.get_object()
        ct = ContentType.objects.get_for_model(Installation)
        qs = Attachment.objects.filter(
            company=inst.company, content_type=ct, object_id=inst.id,
            phase__in=self._RELEVE_PHASES,
        ).order_by('-created_at')
        from apps.records.serializers import AttachmentSerializer
        return Response(AttachmentSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='ajouter-releve',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_releve(self, request, pk=None):
        """FG75 — attache un relevé de toiture ou drone (photo/PDF) au chantier.
        Multipart : `file` (fichier), `phase` (`releve_toiture`|`drone`)."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import store_attachment
        inst = self.get_object()
        file = request.FILES.get('file')
        if file is None:
            return Response({'file': 'Fichier requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        phase = (request.data.get('phase') or 'releve').strip()
        if phase not in self._RELEVE_PHASES:
            return Response(
                {'phase': 'Valeur invalide (releve ou drone).'},
                status=status.HTTP_400_BAD_REQUEST)
        meta, err = store_attachment(file)
        if err:
            return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
        ct = ContentType.objects.get_for_model(Installation)
        att = Attachment.objects.create(
            company=inst.company, content_type=ct, object_id=inst.id,
            uploaded_by=request.user, phase=phase, **meta)
        label = 'drone' if phase == 'drone' else 'relevé'
        activity.log_note(inst, request.user,
                          f"Relevé {label} ajouté : {att.filename}")
        from apps.records.serializers import AttachmentSerializer
        return Response(AttachmentSerializer(att).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='supprimer-releve',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_releve(self, request, pk=None):
        """FG75 — supprime un relevé de toiture / drone du chantier.
        Corps : {"releve": <attachment_id>}."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import delete_attachment
        inst = self.get_object()
        ct = ContentType.objects.get_for_model(Installation)
        att = Attachment.objects.filter(
            id=request.data.get('releve'), content_type=ct, object_id=inst.id,
            company=inst.company, phase__in=self._RELEVE_PHASES,
        ).first()
        if att is None:
            return Response({'detail': 'Relevé introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        delete_attachment(att.file_key)
        activity.log_note(inst, request.user,
                          f"Relevé supprimé : {att.filename}")
        att.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── FG79 — scaffold chaîne d'interventions standard ──────────────────────
    @action(detail=True, methods=['post'], url_path='creer-interventions-standard',
            permission_classes=[IsResponsableOrAdmin])
    def creer_interventions_standard(self, request, pk=None):
        """FG79 — matérialise la chaîne d'interventions standard depuis le
        TypeInterventionPlan du type d'installation du chantier. Idempotent :
        ne recrée pas un type déjà présent. Renvoie la liste des interventions
        créées + celles déjà existantes."""
        from ..models import TypeInterventionPlan
        inst = self.get_object()
        company = request.user.company
        type_inst = inst.type_installation
        if not type_inst:
            return Response({'detail': "Le chantier n'a pas de type d'installation."},
                            status=status.HTTP_400_BAD_REQUEST)
        plan_items = (TypeInterventionPlan.objects
                      .filter(company=company, type_installation=type_inst)
                      .order_by('ordre'))
        if not plan_items.exists():
            return Response({'detail': 'Aucun plan standard défini pour ce type.',
                             'created': [], 'existants': []})
        existing_types = set(
            inst.interventions.values_list('type_intervention', flat=True))
        created = []
        existants = []
        for item in plan_items:
            if item.type_intervention_cle in existing_types:
                existants.append(item.type_intervention_cle)
            else:
                interv = Intervention.objects.create(
                    company=company,
                    installation=inst,
                    type_intervention=item.type_intervention_cle,
                    compte_rendu=item.libelle_contexte or '',
                    created_by=request.user,
                )
                # Chatter de l'intervention + trace sur le chantier.
                from .. import intervention_activity as ia
                ia.log_creation(interv, request.user)
                activity.log_note(
                    inst, request.user,
                    f"Intervention standard créée : {item.type_intervention_cle}")
                created.append(InterventionSerializer(
                    interv, context={'request': request}).data)
                existing_types.add(item.type_intervention_cle)
        return Response({'created': created, 'existants': existants},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # ── FG70 — fiche de remise de garantie (handover summary / section PDF) ──
    @action(detail=True, methods=['get'], url_path='remise-garantie',
            permission_classes=[IsAnyRole])
    def remise_garantie(self, request, pk=None):
        """FG70 — résumé de remise de garantie du chantier réceptionné : la liste
        des équipements de parc couverts (produit, n° de série optionnel, date de
        pose, dates de fin de garantie matériel/production), pour la section de
        remise du PV / d'un PDF client. Lecture seule. Aucun prix d'achat.

        Les équipements sont matérialisés automatiquement au passage à
        « Réceptionné » (un par ligne de BoM gelée, série optionnelle)."""
        inst = self.get_object()
        equipements = [
            eq for eq in inst.equipements.all() if eq.statut != 'remplace'
        ]
        items = []
        for eq in equipements:
            produit = getattr(eq, 'produit', None)
            items.append({
                'equipement_id': eq.id,
                'produit_id': eq.produit_id,
                'produit_nom': getattr(produit, 'nom', None),
                'marque': getattr(produit, 'marque', None),
                'numero_serie': eq.numero_serie or None,
                'date_pose': str(eq.date_pose) if eq.date_pose else None,
                'date_fin_garantie': (
                    str(eq.date_fin_garantie) if eq.date_fin_garantie else None),
                'date_fin_garantie_production': (
                    str(eq.date_fin_garantie_production)
                    if eq.date_fin_garantie_production else None),
            })
        items.sort(key=lambda it: (it['produit_nom'] or '').lower())
        return Response({
            'installation': inst.id,
            'reference': inst.reference,
            'date_reception': (
                str(inst.date_reception) if inst.date_reception else None),
            'nb_equipements': len(items),
            'equipements': items,
        })

    # ── FG71 — synthèse coût / marge par chantier (INTERNE, admin-only) ──────
    @action(detail=True, methods=['get'], url_path='cout',
            permission_classes=[IsAdminRole])
    def cout(self, request, pk=None):
        """FG71 — synthèse de coût / marge du chantier : main-d'œuvre
        (jours estimés/réels, coût si `?tarif_jour=` fourni), coût matériel prévu
        (BoM gelé) vs réel (consommation terrain validée), total du devis et
        marge résultante. STRICTEMENT INTERNE — réservé admin : s'appuie sur les
        prix d'achat, qui ne doivent JAMAIS apparaître sur un document client."""
        from ..services import compute_chantier_cout
        inst = self.get_object()
        tarif = request.query_params.get('tarif_jour')
        return Response(compute_chantier_cout(inst, tarif_jour=tarif))

    @action(detail=False, methods=['get'], url_path='a-facturer',
            permission_classes=[IsResponsableOrAdmin])
    def a_facturer(self, request):
        """YSERV7 — chantiers à tranche d'échéancier due (jalon atteint ou
        réceptionné, non facturé). Liste plate, une entrée par tranche due."""
        from ..services import chantiers_a_facturer
        return Response(chantiers_a_facturer(request.user.company))

    @action(detail=True, methods=['post'], url_path='reserver-stock',
            permission_classes=[IsResponsableOrAdmin])
    def reserver_stock(self, request, pk=None):
        """ZSTK11 — réserve explicitement le stock du chantier (réutilise le
        même service N14 `seed_reservations`). Utile en mode
        `methode_reservation_stock='manuelle'`, où la création du chantier ne
        sème plus la réservation automatiquement — reste utilisable aussi en
        mode `confirmation` (idempotent, sans effet de bord supplémentaire)."""
        from ..services import seed_reservations
        inst = self.get_object()
        reservations = seed_reservations(inst)
        return Response({
            'installation': inst.id,
            'reservations_actives': len(reservations),
        })

    # ── CH2 — parcours d'étapes configurables + gates appliqués ─────────────
    @action(detail=True, methods=['get'], url_path='etapes',
            permission_classes=[IsAnyRole])
    def etapes(self, request, pk=None):
        """CH2 — parcours d'étapes du chantier (cycle de vie configurable CH1)
        avec, pour CHAQUE étape, l'état de son gate (exigences réunies ou non +
        raisons en français). Amorce le cycle international de la société à la
        première consultation. Les étapes non bloquantes sont consultatives ;
        les bloquantes sont appliquées à l'avancement."""
        from ..services import etape_courante, stage_gate_status, stages_actifs
        inst = self.get_object()
        stages = stages_actifs(inst.company)
        courante = etape_courante(inst)
        etapes = []
        for s in stages:
            st = stage_gate_status(inst, s)
            st['id'] = s.id
            st['statut_legacy'] = s.statut_legacy
            st['courante'] = courante is not None and s.id == courante.id
            etapes.append(st)
        return Response({
            'installation': inst.id,
            'reference': inst.reference,
            'etape_courante': courante.cle if courante else None,
            'etapes': etapes,
        })

    # ── CH3 — fiche de recette IEC 62446-1 (mise en service structurée) ─────
    @action(detail=True, methods=['get', 'post'], url_path='recette',
            permission_classes=[IsAnyRole])
    def recette(self, request, pk=None):
        """CH3 — fiche de recette IEC 62446-1 du chantier. GET lit la fiche
        (None si aucune) ; POST l'ouvre (idempotent, réservé Responsable/Admin).
        Une fiche PASSÉE (conforme / conforme avec réserves) débloque le gate
        « Mise en service »."""
        from ..services import ensure_commissioning_record
        from ..serializers_commissioning import CommissioningRecordSerializer
        inst = self.get_object()
        if request.method == 'POST':
            if not request.user.is_responsable:
                return Response(status=status.HTTP_403_FORBIDDEN)
            record = ensure_commissioning_record(inst, request.user)
            return Response(
                CommissioningRecordSerializer(record).data,
                status=status.HTTP_201_CREATED)
        record = getattr(inst, 'commissioning_record', None)
        if record is None:
            return Response({'installation': inst.id, 'record': None})
        return Response(CommissioningRecordSerializer(record).data)

    # ── CH4 — pack de remise client (handover) ──────────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='pack-remise',
            permission_classes=[IsAnyRole])
    def pack_remise(self, request, pk=None):
        """CH4 — pack de remise client du chantier. GET assemble à blanc l'état
        des pièces (dégrade proprement, sans persister) ; POST (Responsable/
        Admin) assemble ET persiste le pack (idempotent). Le pack RÉFÉRENCE les
        pièces réelles : as-built/schémas, datasheets, garanties (parc FG70),
        certificat de recette IEC 62446-1 (CH3), dossier 82-21, accès
        monitoring — une pièce manquante apparaît `present=False`."""
        from ..services import (
            assemble_handover_pieces, generer_handover_pack,
        )
        from ..serializers_commissioning import HandoverPackSerializer
        inst = self.get_object()
        if request.method == 'POST':
            if not request.user.is_responsable:
                return Response(status=status.HTTP_403_FORBIDDEN)
            pack = generer_handover_pack(inst, request.user)
            return Response(
                HandoverPackSerializer(pack).data,
                status=status.HTTP_201_CREATED)
        # GET — aperçu à blanc (ou le pack persisté s'il existe).
        pack = getattr(inst, 'handover_pack', None)
        if pack is not None:
            return Response(HandoverPackSerializer(pack).data)
        resume = assemble_handover_pieces(inst)
        return Response({
            'installation': inst.id,
            'reference': inst.reference,
            'pieces': resume['pieces'],
            'complet': resume['complet'],
            'persiste': False,
        })

    @action(detail=True, methods=['post'], url_path='avancer-etape',
            permission_classes=[IsResponsableOrAdmin])
    def avancer_etape(self, request, pk=None):
        """CH2 — avance le chantier à l'étape demandée (corps {"etape": cle})
        ou à la suivante. Une étape BLOQUANTE ne se franchit pas tant que ses
        exigences (checklist/photos/séries/essais/matériel/dossier 82-21) et
        les points d'arrêt QHSE ne sont pas levés — rejet 400 avec les raisons
        en français. Les étapes non bloquantes s'avancent librement. Le statut
        hérité est synchronisé, donc les effets de bord existants (stock à
        « Installé », garantie/parc à « Réceptionné ») tirent inchangés."""
        from ..services import (
            etape_courante, stages_actifs, verifier_avancement_etape,
        )
        inst = self.get_object()
        stages = stages_actifs(inst.company)
        if not stages:
            return Response({'detail': 'Aucune étape configurée.'},
                            status=status.HTTP_400_BAD_REQUEST)
        cle = request.data.get('etape')
        if cle:
            cible = next((s for s in stages if s.cle == cle), None)
            if cible is None:
                return Response({'detail': 'Étape inconnue.'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            courante = etape_courante(inst)
            idx = next((k for k, s in enumerate(stages)
                        if courante is not None and s.id == courante.id), -1)
            if idx + 1 >= len(stages):
                return Response({'detail': 'Dernière étape déjà atteinte.'},
                                status=status.HTTP_400_BAD_REQUEST)
            cible = stages[idx + 1]
        raisons = verifier_avancement_etape(inst, cible)
        if raisons:
            return Response(
                {'detail': 'Étape bloquée par un gate.', 'raisons': raisons},
                status=status.HTTP_400_BAD_REQUEST)
        old = Installation.objects.get(pk=inst.pk)
        canon_old = Installation.canonical_statut(old.statut)
        inst.etape = cible
        fields = ['etape']
        if (cible.statut_legacy
                and Installation.canonical_statut(cible.statut_legacy)
                != canon_old):
            inst.statut = cible.statut_legacy
            fields.append('statut')
        inst.save(update_fields=fields)
        canon_new = Installation.canonical_statut(inst.statut)
        # Mêmes aides que perform_update : jalon horodaté + effets de bord
        # préservés sur les gates mappés (garantie/parc FG70, stock N14).
        _stamp_statut_dates(inst, old.statut)
        _apply_reception_handover(inst, canon_old, canon_new, request.user)
        _apply_stock_statut_effects(inst, canon_old, canon_new, request.user)
        activity.log_changes(old, inst, request.user)
        activity.log_note(
            inst, request.user, f"Étape avancée : « {cible.libelle} ».")
        return Response(
            InstallationSerializer(inst, context={'request': request}).data)

    # ── FG77 — contrôle de préparation avant pose (advisory) ────────────────
    @action(detail=True, methods=['get'], url_path='readiness',
            permission_classes=[IsAnyRole])
    def readiness(self, request, pk=None):
        """FG77 — état de préparation avant pose : manque matériel (besoin vs
        stock), état du dossier réglementaire loi 82-21 et date de pose
        planifiée, agrégés en une checklist + un verdict « prêt / non prêt » pour
        une bannière. AVISORY (lecture seule) — n'empêche aucun changement de
        statut ; le frontend peut proposer un override-à-confirmer."""
        from ..services import compute_chantier_readiness
        inst = self.get_object()
        return Response(compute_chantier_readiness(inst))
