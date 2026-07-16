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
    ReverificationMesureSerializer,
    FicheInterventionReleveSerializer,
)
from ..services import (  # noqa: F401
    create_installation_from_devis, seed_checklist_etapes,
    ensure_checklist_items, ensure_default_template,
    enregistrer_reverification,
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


class InterventionViewSet(CompanyScopedModelViewSet):
    """Interventions (sorties chantier) rattachées à un chantier (F3). Chacune
    porte son propre statut (machine à états distincte du chantier et de
    STAGES.py), une équipe, une camionnette, et son propre chatter. Scopées à
    la société ; l'acteur et la société sont posés côté serveur."""
    queryset = Intervention.objects.select_related(
        'installation', 'installation__client', 'installation__devis',
        'technicien', 'camionnette').prefetch_related('equipe').all()
    serializer_class = InterventionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        'date_prevue', 'date_realisee', 'date_creation', 'statut',
        'priorite_rang']
    # XFSM4 — tri par défaut : priorité (urgente d'abord) PUIS date.
    ordering = ['priorite_rang', '-date_prevue']

    # XFSM4 — rang numérique de tri (urgente < haute < normale) pour trier
    # les 3 vues (kanban F4, calendrier FG68, « Ma journée » F22) par priorité
    # PUIS date, sans dépendre de l'ordre alphabétique des choix.
    _PRIORITE_RANG = {
        Intervention.Priorite.URGENTE: 0,
        Intervention.Priorite.HAUTE: 1,
        Intervention.Priorite.NORMALE: 2,
    }

    def get_queryset(self):
        from django.db.models import Case, When, IntegerField
        qs = super().get_queryset()
        qs = qs.annotate(priorite_rang=Case(
            *[When(priorite=val, then=rang)
              for val, rang in self._PRIORITE_RANG.items()],
            default=2, output_field=IntegerField()))
        # Portée de visibilité (Feature F) — interventions du technicien / de
        # son équipe. 'all' → inchangé.
        from authentication.scoping import scope_queryset
        qs = scope_queryset(qs, self.request.user, ['technicien', 'created_by'])
        params = self.request.query_params
        installation = params.get('installation')
        ticket = params.get('ticket')
        statut = params.get('statut')
        type_interv = params.get('type_intervention')
        priorite = params.get('priorite')
        if installation:
            qs = qs.filter(installation_id=installation)
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        if statut:
            qs = qs.filter(statut=statut)
        if type_interv:
            qs = qs.filter(type_intervention=type_interv)
        if priorite:
            qs = qs.filter(priorite=priorite)
        # FG68 — filtre plage de dates sur date_prevue (calendrier dispatch).
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from:
            qs = qs.filter(date_prevue__gte=date_from)
        if date_to:
            qs = qs.filter(date_prevue__lte=date_to)
        # YSERV6 — une intervention annulée (chantier annulé) sort des vues
        # kanban/calendrier/charge (list) par défaut ; `?annulee=true` la
        # réaffiche (audit/historique). Ne s'applique jamais aux actions
        # détail (retrieve/actions) — une intervention déjà annulée reste
        # consultable/gérable individuellement par son id.
        if self.action == 'list':
            annulee_param = params.get('annulee')
            if annulee_param is not None and annulee_param.lower() in (
                    '1', 'true', 'vrai', 'oui'):
                qs = qs.filter(annulee=True)
            else:
                qs = qs.filter(annulee=False)
        return qs

    def list(self, request, *args, **kwargs):
        """ZFSM7 — ``?export=xlsx`` télécharge la liste FILTRÉE (mêmes filtres
        `statut`/`type_intervention`/`priorite`/plage de dates) en xlsx
        (colonnes chantier/client/ville/type/statut/priorité/dates/technicien/
        équipe/durée réelle — SANS aucun coût interne ni marge). Le format
        DRF ``?format=`` reste réservé — jamais utilisé ici."""
        if request.query_params.get('export') == 'xlsx':
            role = getattr(request.user, 'role_legacy', None)
            if role not in ('responsable', 'admin') and not (
                    request.user.is_superuser):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    "Export réservé aux rôles responsable/admin.")
            from apps.records.xlsx import build_xlsx_response
            from .. import selectors as _selectors

            qs = self.filter_queryset(self.get_queryset())
            headers = [
                'Chantier', 'Client', 'Ville', 'Type', 'Statut', 'Priorité',
                'Date prévue', 'Date réalisée', 'Technicien', 'Équipe',
                'Durée réelle (min)',
            ]
            rows = [_selectors.intervention_export_row(interv)
                    for interv in qs]
            return build_xlsx_response(
                'interventions.xlsx', headers, rows,
                sheet_title='Interventions')
        return super().list(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in READ_ACTIONS + [
            'historique', 'preparation', 'photos',
            # Lectures du module de capture F9–F19 + F23.
            'serials', 'consommation', 'memos', 'reserves', 'tool_return',
            'safety', 'crew_time', 'compte_rendu', 'overage_review', 'code',
            'photo_qa',
            # FG68 — vue calendrier dispatch techniciens.
            'calendrier',
            # FG73 — tournée journalière du technicien.
            'ma_tournee',
            # FG299 — plan de charge des équipes (capacité vs affecté).
            'plan_de_charge',
            # FG300 — détection de conflits d'affectation.
            'conflits_affectation',
            # FG301 — nivellement de charge (resource levelling).
            'nivellement_charge',
            # XFSM5 — KPI taux d'arrivée à l'heure.
            'taux_ponctualite',
            # XFSM2 — assistant de planification (meilleur créneau).
            'suggerer_creneau',
            # FG303 — planning des camionnettes (capacité véhicule).
            'planning_camionnettes',
            # FG69 — signature client.
            'signer_client',
            # XFSM13 — historique des re-vérifications (lecture).
            'reverifications',
            # XFSM22 — durée & pièces suggérées par l'historique.
            'suggestions_creation',
            # ZFSM1 — lecture de la fiche d'intervention (relevé terrain).
            'fiche',
        ]:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'noter', 'cocher_materiel', 'cocher_outil', 'choisir_kit',
            'confirmer_charge', 'commander_manques', 'depart_depot', 'checkin',
            'retour', 'ajouter_photo', 'supprimer_photo',
            # Écritures du module de capture F9–F19.
            'ajouter_serial', 'modifier_serial', 'supprimer_serial',
            'annoter_photo', 'valider_consommation',
            'ajouter_ligne_consommation', 'modifier_ligne_consommation',
            'supprimer_ligne_consommation',
            'ajouter_memo', 'modifier_memo', 'supprimer_memo',
            'ajouter_reserve', 'modifier_reserve', 'resoudre_reserve',
            'cocher_tool_return', 'confirmer_tool_return',
            'cocher_safety', 'signer_safety',
            # FG78 — confirmation RDV.
            'confirmer_rdv',
            # XFSM3 — replanification en masse d'une journée.
            'replanifier_en_masse',
            # XFSM13 — enregistrement d'une re-vérification (écriture).
            'enregistrer_reverification_view',
            # XFSM18 — réserve → devis de réparation.
            'generer_devis_reserve',
            # XFSM7 — lien public « technicien en route ».
            'lien_client',
            # ZFSM2 — lien public tokenisé du compte-rendu signé.
            'lien_rapport',
            # ZFSM4 — facturation directe d'une intervention hors contrat.
            'generer_facture',
            # ZFSM5 — devis d'upsell créé sur place depuis l'intervention.
            'generer_devis',
            # ZFSM1 — renseigner la fiche d'intervention (relevé terrain).
            'renseigner_fiche',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        """Tenant safety : chantier, ticket SAV et camionnette ciblés doivent
        appartenir à la société du user."""
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        installation = serializer.validated_data.get('installation')
        ticket = serializer.validated_data.get('ticket')
        camionnette = serializer.validated_data.get('camionnette')
        if installation is not None and installation.company_id != cid:
            raise ValidationError({'installation': 'Chantier inconnu.'})
        if ticket is not None and ticket.company_id != cid:
            raise ValidationError({'ticket': 'Ticket inconnu.'})
        if camionnette is not None and camionnette.company_id != cid:
            raise ValidationError({'camionnette': 'Emplacement inconnu.'})

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            avertissements = getattr(self, '_yhire9_avertissements', None)
            if avertissements:
                response.data['avertissements'] = avertissements
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            avertissements = getattr(self, '_yhire9_avertissements', None)
            if avertissements:
                response.data['avertissements'] = avertissements
        return response

    def _verifier_habilitation_ou_lever(self, company, technicien,
                                        type_intervention):
        """YHIRE9 — garde d'habilitation à l'affectation : mémorise les
        avertissements pour la réponse (`create`/`update`) et lève en mode
        'block'."""
        from rest_framework.exceptions import ValidationError
        from ..services import verifier_habilitation_affectation
        bloquant, avertissements = verifier_habilitation_affectation(
            company, technicien, type_intervention)
        if avertissements:
            self._yhire9_avertissements = avertissements
        if bloquant:
            raise ValidationError({'technicien': avertissements})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        installation = serializer.validated_data.get('installation')
        # YSERV6 — un chantier annulé refuse toute nouvelle intervention.
        if installation is not None and installation.annule:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {'installation': 'Ce chantier est annulé — impossible de '
                                 'créer une nouvelle intervention.'})
        # YSERV1 — Gate « acompte encaissé » avant planification : une
        # Intervention de type POSE DATÉE sur un chantier dont l'acompte
        # n'est pas encaissé (toggle société ON) est refusée, sauf override
        # responsable/admin (seul rôle admis en écriture ici) avec `motif`.
        type_intervention = serializer.validated_data.get('type_intervention')
        date_prevue = serializer.validated_data.get('date_prevue')
        if (installation is not None
                and type_intervention == Intervention.Type.POSE
                and date_prevue):
            from rest_framework.exceptions import ValidationError
            from ..services import verifier_gate_acompte_planification
            raison = verifier_gate_acompte_planification(installation)
            if raison:
                motif_override = (
                    self.request.data.get('motif_override_acompte')
                    or '').strip()
                if not motif_override:
                    raise ValidationError({'date_prevue': [raison]})
                activity.log_note(
                    installation, self.request.user,
                    'Intervention de pose planifiée sans acompte — motif : '
                    f'{motif_override}')
        # YHIRE9 — garde d'habilitation à l'AFFECTATION (création) : un
        # technicien sans l'habilitation requise déclenche un avertissement
        # (mode 'warn', défaut) ou un refus (mode 'block').
        technicien = serializer.validated_data.get('technicien')
        if technicien is not None:
            self._verifier_habilitation_ou_lever(
                company, technicien, type_intervention)
        interv = serializer.save(company=company, created_by=self.request.user)
        # XFSM4 — priorité héritée du ticket SAV lié quand fournie explicitement
        # aucune priorité (défaut NORMALE côté modèle = « non fournie » ici).
        # sav.Ticket.Priorite a une valeur BASSE que Intervention n'a pas :
        # repli sur NORMALE (comportement le plus proche de l'existant).
        if interv.ticket_id is not None and \
                'priorite' not in serializer.validated_data:
            ticket_priorite = getattr(interv.ticket, 'priorite', None)
            mapped = ticket_priorite if ticket_priorite in (
                Intervention.Priorite.URGENTE, Intervention.Priorite.HAUTE,
                Intervention.Priorite.NORMALE) else Intervention.Priorite.NORMALE
            if mapped != interv.priorite:
                interv.priorite = mapped
                interv.save(update_fields=['priorite'])
        # Auto-tampon date_realisee : un compte rendu rempli (ou un statut
        # « Terminée »/« Validée ») sans date réalisée la pose à aujourd'hui,
        # côté serveur (miroir de _stamp_statut_dates du chantier).
        self._stamp_date_realisee(interv)
        # F3 — équipe par défaut = l'installateur du chantier quand aucune
        # équipe n'a été fournie (posé côté serveur).
        if not interv.equipe.exists() and installation is not None:
            installer = installation.technicien_responsable
            if installer is not None:
                interv.equipe.add(installer)
        # Chatter PROPRE de l'intervention + trace dans le chatter du chantier.
        intervention_activity.log_creation(interv, self.request.user)
        if installation is not None:
            activity.log_note(
                installation, self.request.user,
                f"Intervention ajoutée : "
                f"{interv.get_type_intervention_display()}")

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        self._check_tenant(serializer)
        old = Intervention.objects.get(pk=serializer.instance.pk)
        # F5/F8 — garde de transition de statut PROPRE à l'intervention :
        # quitter « À préparer » exige « Tout est chargé » (F5) ; atteindre
        # « Terminée » exige une photo par créneau obligatoire (F8). Ne lit/écrit
        # JAMAIS le statut chantier ni STAGES.py.
        new_statut = serializer.validated_data.get('statut', old.statut)
        if new_statut != old.statut:
            reason = field_services.transition_block_reason(old, new_statut)
            if reason:
                raise ValidationError({'statut': reason})
        # YHIRE9 — garde d'habilitation à l'AFFECTATION : seulement quand le
        # technicien CHANGE (pas de bruit sur une simple modification d'une
        # intervention déjà correctement affectée).
        new_technicien = serializer.validated_data.get(
            'technicien', old.technicien)
        if (new_technicien is not None
                and new_technicien.id != old.technicien_id):
            self._verifier_habilitation_ou_lever(
                self.request.user.company, new_technicien,
                serializer.validated_data.get(
                    'type_intervention', old.type_intervention))
        interv = serializer.save()
        # Auto-tampon date_realisee (compte rendu rempli / terminée) si vide.
        self._stamp_date_realisee(interv)
        # F3 — journalise les changements (dont le statut) dans le chatter
        # PROPRE de l'intervention. Ne touche JAMAIS le statut du chantier.
        intervention_activity.log_changes(old, interv, self.request.user)
        # Édition d'intervention → trace au chatter du CHANTIER (la création
        # l'était déjà ; l'édition ne l'était pas).
        if interv.installation_id:
            activity.log_note(
                interv.installation, self.request.user,
                f"Intervention modifiée : "
                f"{interv.get_type_intervention_display()}")
        # YSERV2 — passage à TERMINEE/VALIDEE (nouveau) : émet
        # intervention_completed sur le bus (core/events.py). sav s'y abonne
        # pour avancer un ticket lié — installations n'importe jamais sav.
        if (old.statut not in (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
                and interv.statut in (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)):
            from core.events import intervention_completed
            intervention_completed.send(
                sender=Intervention, intervention=interv,
                company=self.request.user.company, user=self.request.user)
        # ZFSM2 — génère le jeton du lien public « compte-rendu signé » à la
        # validation de l'intervention (lazy, idempotent : ne régénère jamais).
        if (old.statut != Intervention.Statut.VALIDEE
                and interv.statut == Intervention.Statut.VALIDEE):
            interv.ensure_lien_rapport_token()

    def perform_destroy(self, instance):
        # Suppression d'intervention → trace au chatter du CHANTIER.
        installation = instance.installation
        type_label = instance.get_type_intervention_display()
        super().perform_destroy(instance)
        if installation is not None:
            activity.log_note(
                installation, self.request.user,
                f"Intervention supprimée : {type_label}")

    @staticmethod
    def _stamp_date_realisee(interv):
        """Pose date_realisee à aujourd'hui si elle est vide alors qu'un compte
        rendu est renseigné OU que le statut est « Terminée »/« Validée »."""
        if interv.date_realisee is not None:
            return
        cr = (interv.compte_rendu or '').strip()
        done = interv.statut in (
            Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
        if cr or done:
            interv.date_realisee = timezone.localdate()
            interv.save(update_fields=['date_realisee'])

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        interv = self.get_object()
        return Response(
            InterventionActivitySerializer(
                interv.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        interv = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = intervention_activity.log_note(interv, request.user, body)
        return Response(InterventionActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    # ── F5 — Liste de préparation ───────────────────────────────────────────
    def _prep_response(self, interv):
        prep = field_services.ensure_preparation(interv)
        return Response(InterventionPreparationSerializer(
            prep, context={'request': self.request}).data)

    @action(detail=True, methods=['get'], url_path='preparation',
            permission_classes=[IsAnyRole])
    def preparation(self, request, pk=None):
        """F5 — liste de préparation : matériel (nomenclature gelée du chantier)
        + outils (kit). Matérialisée paresseusement à la première consultation,
        puis renvoyée avec le pourcentage de complétion."""
        return self._prep_response(self.get_object())

    @action(detail=True, methods=['post'], url_path='choisir-kit',
            permission_classes=[IsResponsableOrAdmin])
    def choisir_kit(self, request, pk=None):
        """F5 — sélectionne (ou retire) le kit d'outillage de la préparation et
        resynchronise les lignes outils. Corps : {"kit": <id|null>}."""
        from apps.outillage.models import KitOutillage
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        kit_id = request.data.get('kit')
        if kit_id in (None, '', 'null'):
            prep.kit = None
        else:
            kit = KitOutillage.objects.filter(
                id=kit_id, company=interv.company).first()
            if kit is None:
                return Response({'kit': 'Kit inconnu.'},
                                status=status.HTTP_400_BAD_REQUEST)
            prep.kit = kit
        # Changer de kit invalide la confirmation « Tout est chargé ».
        prep.tout_charge = False
        prep.confirme_par = None
        prep.confirme_le = None
        prep.save(update_fields=['kit', 'tout_charge', 'confirme_par',
                                 'confirme_le'])
        field_services._sync_outils(prep)
        return self._prep_response(interv)

    @action(detail=True, methods=['post'], url_path='cocher-materiel',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_materiel(self, request, pk=None):
        """F5 — coche/décoche une ligne matériel comme « chargée ».
        Corps : {"ligne": <id>, "charge": <bool>}."""
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        ligne = prep.materiel.filter(id=request.data.get('ligne')).first()
        if ligne is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        charge = bool(request.data.get('charge', True))
        ligne.charge = charge
        ligne.save(update_fields=['charge'])
        # Décocher une ligne retire la confirmation « Tout est chargé ».
        if not charge and prep.tout_charge:
            prep.tout_charge = False
            prep.save(update_fields=['tout_charge'])
        return self._prep_response(interv)

    @action(detail=True, methods=['post'], url_path='cocher-outil',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_outil(self, request, pk=None):
        """F5 — coche/décoche un outil comme « chargé ».
        Corps : {"ligne": <id>, "coche": <bool>}."""
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        ligne = prep.outils.filter(id=request.data.get('ligne')).first()
        if ligne is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        coche = bool(request.data.get('coche', True))
        ligne.coche = coche
        ligne.save(update_fields=['coche'])
        if not coche and prep.tout_charge:
            prep.tout_charge = False
            prep.save(update_fields=['tout_charge'])
        return self._prep_response(interv)

    @action(detail=True, methods=['post'], url_path='confirmer-charge',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_charge(self, request, pk=None):
        """F5 — confirmation « Tout est chargé » : requise avant de quitter
        « À préparer ». Refuse si toutes les lignes ne sont pas cochées."""
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        try:
            field_services.confirm_charge(prep, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        intervention_activity.log_note(
            interv, request.user,
            "Préparation confirmée — « Tout est chargé ».")
        return self._prep_response(interv)

    @action(detail=True, methods=['post'], url_path='commander-manques',
            permission_classes=[IsResponsableOrAdmin])
    def commander_manques(self, request, pk=None):
        """F5 — crée un bon de commande fournisseur BROUILLON pour les manques
        du chantier (réutilise le flux Besoin matériel existant). Corps :
        {"fournisseur": <id>} optionnel."""
        from apps.stock.services import (
            draft_bcf_for_shortfall, resolve_fournisseur,
        )
        from apps.stock.serializers import BonCommandeFournisseurSerializer
        interv = self.get_object()
        inst = interv.installation
        company = request.user.company
        fournisseur = resolve_fournisseur(
            company, request.data.get('fournisseur'), inst)
        if fournisseur is None:
            return Response(
                {'detail': ('Aucun fournisseur indiqué et aucun fournisseur '
                            'par défaut sur les produits manquants.')},
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

    # ── F6 — Trajet & check-in GPS sur site ─────────────────────────────────
    @action(detail=True, methods=['post'], url_path='depart-depot',
            permission_classes=[IsResponsableOrAdmin])
    def depart_depot(self, request, pk=None):
        """F6 — horodate le départ du dépôt (début du trajet). XFSM7 : si le
        navigateur fournit lat/lng, les pose aussi (sert uniquement à l'ETA du
        lien public « technicien en route » — aucune autre logique n'en
        dépend)."""
        interv = self.get_object()
        interv.depart_depot_le = timezone.now()
        fields = ['depart_depot_le']
        lat, lng = request.data.get('lat'), request.data.get('lng')
        if lat not in (None, '') and lng not in (None, ''):
            try:
                interv.depart_gps_lat = round(float(lat), 6)
                interv.depart_gps_lng = round(float(lng), 6)
                fields += ['depart_gps_lat', 'depart_gps_lng']
            except (TypeError, ValueError):
                pass
        interv.save(update_fields=fields)
        intervention_activity.log_note(
            interv, request.user, "Départ dépôt enregistré.")
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='lien-client',
            permission_classes=[IsResponsableOrAdmin])
    def lien_client(self, request, pk=None):
        """XFSM7 — génère (lazily) et renvoie l'URL publique « technicien en
        route » de cette intervention, à partager par WhatsApp/SMS (pattern
        FG86/liens WhatsApp)."""
        interv = self.get_object()
        token = interv.ensure_lien_client_token()
        return Response({'token': token, 'path': f'/public/installations/intervention/{token}/'})

    @action(detail=True, methods=['post'], url_path='checkin',
            permission_classes=[IsResponsableOrAdmin])
    def checkin(self, request, pk=None):
        """F6 — check-in à l'arrivée : horodatage + position GPS (du navigateur,
        aucun service externe). On en dérive une distance-au-site indicative.
        Corps : {"lat": <num>, "lng": <num>}."""
        interv = self.get_object()
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        now = timezone.now()
        interv.arrivee_site_le = now
        fields = ['arrivee_site_le']
        if lat not in (None, '') and lng not in (None, ''):
            try:
                interv.arrivee_gps_lat = round(float(lat), 6)
                interv.arrivee_gps_lng = round(float(lng), 6)
                fields += ['arrivee_gps_lat', 'arrivee_gps_lng']
            except (TypeError, ValueError):
                return Response({'detail': 'Coordonnées invalides.'},
                                status=status.HTTP_400_BAD_REQUEST)
        # XFSM5 — ponctualité : dérivée de l'arrivée réelle vs la fenêtre
        # promise (heure locale du serveur — cohérent avec `date_prevue`).
        # None si aucune fenêtre n'est promise (comportement actuel inchangé).
        if interv.fenetre_debut is not None and interv.fenetre_fin is not None:
            heure_arrivee = timezone.localtime(now).time()
            interv.arrivee_dans_fenetre = (
                interv.fenetre_debut <= heure_arrivee <= interv.fenetre_fin)
            fields.append('arrivee_dans_fenetre')
        interv.save(update_fields=fields)
        dist = field_services.distance_to_site(interv)
        intervention_activity.log_note(
            interv, request.user,
            "Arrivée sur site enregistrée"
            + (f" (≈ {dist} km du chantier)" if dist is not None else "") + ".")
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='retour',
            permission_classes=[IsResponsableOrAdmin])
    def retour(self, request, pk=None):
        """F6 — horodate le retour au dépôt (fin du trajet)."""
        interv = self.get_object()
        interv.retour_depot_le = timezone.now()
        interv.save(update_fields=['retour_depot_le'])
        intervention_activity.log_note(
            interv, request.user, "Retour dépôt enregistré.")
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    # ── F7/F8 — Photos guidées par shot list ────────────────────────────────
    @action(detail=True, methods=['get'], url_path='photos',
            permission_classes=[IsAnyRole])
    def photos(self, request, pk=None):
        """F7/F8 — galerie groupée avant/pendant/après + checklist des créneaux
        obligatoires manquants (garde « Terminée »)."""
        interv = self.get_object()
        field_services.seed_shotlist_slots(interv.company)
        slots = field_services.active_shotlist(interv.company)
        by_slot = field_services.photos_by_slot(interv)

        def photo_payload(att):
            return {
                'id': att.id,
                'filename': field_services.display_filename(att),
                'url': f'/api/django/records/attachments/{att.id}/download/',
                'mime': att.mime,
                'created_at': att.created_at,
                'uploaded_by_nom': getattr(att.uploaded_by, 'username', None),
            }

        groups = {'avant': [], 'pendant': [], 'apres': []}
        for slot in slots:
            entry = {
                'cle': slot.cle, 'libelle': slot.libelle, 'phase': slot.phase,
                'obligatoire': slot.obligatoire,
                'photos': [photo_payload(a) for a in by_slot.get(slot.cle, [])],
            }
            groups.setdefault(slot.phase, []).append(entry)
        # Photos hors créneau (créneau supprimé/désactivé) — regroupées à part.
        known = {s.cle for s in slots}
        autres = []
        for cle, atts in by_slot.items():
            if cle and cle not in known:
                autres.append({
                    'cle': cle, 'libelle': cle, 'phase': '',
                    'obligatoire': False,
                    'photos': [photo_payload(a) for a in atts]})
        sans_creneau = [photo_payload(a) for a in by_slot.get('', [])]
        manquants = field_services.missing_required_shots(interv)
        return Response({
            'intervention': interv.id,
            'groupes': groups,
            'autres': autres,
            'sans_creneau': sans_creneau,
            'obligatoires_manquants': [
                {'cle': s.cle, 'libelle': s.libelle, 'phase': s.phase}
                for s in manquants],
        })

    @action(detail=True, methods=['post'], url_path='ajouter-photo',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_photo(self, request, pk=None):
        """F7 — téléverse une photo, tagguée à un créneau de shot list, via le
        stockage objet GÉNÉRIQUE existant (records.store_attachment + le modèle
        records.Attachment). Le créneau est encodé dans le nom de fichier (pas
        de nouveau champ croisé). La photo reste en stockage objet — jamais
        commitée. Corps multipart : file, slot, phase."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import store_attachment
        interv = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        slot_cle = (request.data.get('slot') or '').strip()
        # La phase suit le créneau choisi quand il existe ; sinon le corps.
        phase = (request.data.get('phase') or '').strip().lower()
        if slot_cle:
            slot = ShotListSlot.objects.filter(
                company=interv.company, cle=slot_cle).first()
            if slot is not None:
                phase = slot.phase
        if phase not in ('avant', 'pendant', 'apres'):
            phase = ''
        meta, err = store_attachment(file)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)
        # Encode le créneau dans le filename pour réutiliser le modèle générique.
        meta = dict(meta)
        meta['filename'] = field_services.encode_slot_filename(
            slot_cle, meta['filename'])
        ct = ContentType.objects.get_for_model(Intervention)
        att = Attachment.objects.create(
            company=interv.company, content_type=ct, object_id=interv.id,
            uploaded_by=request.user, phase=phase, **meta)
        intervention_activity.log_note(
            interv, request.user,
            f"Photo ajoutée{(' — ' + slot_cle) if slot_cle else ''}.")
        return Response({
            'id': att.id,
            'filename': field_services.display_filename(att),
            'url': f'/api/django/records/attachments/{att.id}/download/',
            'slot': slot_cle, 'phase': phase,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='supprimer-photo',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_photo(self, request, pk=None):
        """F7 — supprime une photo de l'intervention (objet + enregistrement).
        Corps : {"photo": <attachment_id>}."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import delete_attachment
        interv = self.get_object()
        ct = ContentType.objects.get_for_model(Intervention)
        att = Attachment.objects.filter(
            id=request.data.get('photo'), content_type=ct,
            object_id=interv.id, company=interv.company).first()
        if att is None:
            return Response({'detail': 'Photo inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        delete_attachment(att.file_key)
        att.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── F9 — n° de série par composant (+ OCR swappable no-op) ───────────────
    def _serials_response(self, interv):
        return Response(ComponentSerialSerializer(
            interv.serials.all(), many=True,
            context={'request': self.request}).data)

    @action(detail=True, methods=['get'], url_path='serials',
            permission_classes=[IsAnyRole])
    def serials(self, request, pk=None):
        """F9 — liste des n° de série relevés sur l'intervention."""
        return self._serials_response(self.get_object())

    @action(detail=True, methods=['post'], url_path='ajouter-serial',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_serial(self, request, pk=None):
        """F9 — relève un n° de série de composant. Optionnellement une photo de
        plaque (multipart `file`) sur laquelle on TENTE une extraction OCR via
        l'interface SWAPPABLE (no-op par défaut → on garde la saisie manuelle).
        Le n° de série PEUT être vide : la saisie ne bloque jamais. Corps :
        produit, designation, slot, numero_serie, [file]."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import store_attachment
        from apps.stock.selectors import get_produit_scoped
        from .. import swappable
        interv = self.get_object()
        company = interv.company
        produit = None
        produit_id = request.data.get('produit')
        if produit_id:
            produit = get_produit_scoped(company, produit_id)
            if produit is None:
                return Response({'produit': 'Produit inconnu.'},
                                status=status.HTTP_400_BAD_REQUEST)
        numero = (request.data.get('numero_serie') or '').strip()
        serie_ocr = False
        plaque = None
        file = request.FILES.get('file')
        if file is not None:
            meta, err = store_attachment(file)
            if err:
                return Response({'detail': err},
                                status=status.HTTP_400_BAD_REQUEST)
            ct = ContentType.objects.get_for_model(Intervention)
            plaque = Attachment.objects.create(
                company=company, content_type=ct, object_id=interv.id,
                uploaded_by=request.user, phase='', **meta)
            # OCR SWAPPABLE : no-op par défaut (renvoie None) → on ne touche pas
            # au champ saisi à la main. Ne bloque jamais.
            if not numero:
                from apps.records.storage import fetch_attachment
                data, _ = fetch_attachment(plaque.file_key)
                extracted = swappable.extract_serial(company, data)
                if extracted:
                    numero = extracted.strip()
                    serie_ocr = True
        serial = ComponentSerial.objects.create(
            company=company, intervention=interv, produit=produit,
            designation=(request.data.get('designation') or '').strip(),
            slot_cle=(request.data.get('slot') or '').strip(),
            numero_serie=numero, plaque_attachment=plaque,
            serie_ocr=serie_ocr, created_by=request.user)
        return Response(ComponentSerialSerializer(
            serial, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='modifier-serial',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_serial(self, request, pk=None):
        """F9 — édite un n° de série relevé. Corps : serial, numero_serie,
        [designation]."""
        interv = self.get_object()
        serial = interv.serials.filter(id=request.data.get('serial')).first()
        if serial is None:
            return Response({'detail': 'Relevé inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        fields = []
        if 'numero_serie' in request.data:
            serial.numero_serie = (request.data.get('numero_serie') or '').strip()
            serial.serie_ocr = False
            fields += ['numero_serie', 'serie_ocr']
        if 'designation' in request.data:
            serial.designation = (request.data.get('designation') or '').strip()
            fields.append('designation')
        if fields:
            serial.save(update_fields=fields)
        return Response(ComponentSerialSerializer(
            serial, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='supprimer-serial',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_serial(self, request, pk=None):
        """F9 — supprime un relevé de n° de série. Corps : {"serial": <id>}."""
        interv = self.get_object()
        serial = interv.serials.filter(id=request.data.get('serial')).first()
        if serial is None:
            return Response({'detail': 'Relevé inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        serial.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── F10 — annotation d'une photo (dessin + légende) ─────────────────────
    @action(detail=True, methods=['post'], url_path='annoter-photo',
            permission_classes=[IsResponsableOrAdmin])
    def annoter_photo(self, request, pk=None):
        """F10 — marque une photo de l'intervention d'un calque de dessin
        (JSON) + légende, pour signaler un problème. Fait partie de la photo.
        Corps : {"photo": <attachment_id>, "drawing": [...], "caption": str,
        "probleme": bool}."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from ..models import PhotoAnnotation
        from ..serializers import PhotoAnnotationSerializer
        interv = self.get_object()
        ct = ContentType.objects.get_for_model(Intervention)
        att = Attachment.objects.filter(
            id=request.data.get('photo'), content_type=ct,
            object_id=interv.id, company=interv.company).first()
        if att is None:
            return Response({'detail': 'Photo inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        drawing = request.data.get('drawing')
        ann, _ = PhotoAnnotation.objects.get_or_create(
            attachment=att, defaults={'company': interv.company,
                                      'created_by': request.user})
        if ann.company_id is None:
            ann.company = interv.company
        if isinstance(drawing, list):
            ann.drawing = drawing
        ann.caption = request.data.get('caption', ann.caption) or ''
        ann.probleme = bool(request.data.get('probleme', ann.probleme))
        ann.save()
        return Response(PhotoAnnotationSerializer(ann).data,
                        status=status.HTTP_200_OK)

    # ── F11/F12 — réconciliation du matériel consommé ───────────────────────
    def _consommation_response(self, interv):
        cons = field_capture.ensure_consommation(interv)
        return Response(MaterielConsommationSerializer(
            cons, context={'request': self.request}).data)

    @action(detail=True, methods=['get'], url_path='consommation',
            permission_classes=[IsAnyRole])
    def consommation(self, request, pk=None):
        """F11 — réconciliation matériel : prévu (nomenclature) vs réellement
        utilisé, lignes hors-nomenclature, variances + dépassements (F12)."""
        return self._consommation_response(self.get_object())

    @action(detail=True, methods=['post'], url_path='ajouter-ligne-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_ligne_consommation(self, request, pk=None):
        """F11 — ajoute une ligne hors-nomenclature (câble, vis, MC4…). Corps :
        designation, quantite_utilisee, [produit], [justification]."""
        from apps.stock.selectors import get_produit_scoped
        interv = self.get_object()
        if getattr(interv, 'consommation', None) and interv.consommation.valide:
            return Response({'detail': 'Réconciliation déjà validée.'},
                            status=status.HTTP_400_BAD_REQUEST)
        cons = field_capture.ensure_consommation(interv)
        designation = (request.data.get('designation') or '').strip()
        if not designation:
            return Response({'designation': 'Désignation requise.'},
                            status=status.HTTP_400_BAD_REQUEST)
        produit = None
        if request.data.get('produit'):
            produit = get_produit_scoped(
                interv.company, request.data.get('produit'))
        from decimal import Decimal, InvalidOperation
        try:
            qte = Decimal(str(request.data.get('quantite_utilisee') or 0))
        except (InvalidOperation, TypeError, ValueError):
            qte = Decimal('0')
        ligne = ConsommationLigne.objects.create(
            company=interv.company, consommation=cons, produit=produit,
            designation=designation, quantite_prevue=Decimal('0'),
            quantite_utilisee=qte, hors_nomenclature=True,
            justification=(request.data.get('justification') or '').strip(),
            ordre=cons.lignes.count())
        return Response(ConsommationLigneSerializer(ligne).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'],
            url_path='modifier-ligne-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_ligne_consommation(self, request, pk=None):
        """F11 — édite une ligne : quantite_utilisee, justification,
        justification_memo. Corps : {"ligne": <id>, ...}."""
        from decimal import Decimal, InvalidOperation
        interv = self.get_object()
        cons = field_capture.ensure_consommation(interv)
        if cons.valide:
            return Response({'detail': 'Réconciliation déjà validée.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ligne = cons.lignes.filter(id=request.data.get('ligne')).first()
        if ligne is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        fields = []
        if 'quantite_utilisee' in request.data:
            try:
                ligne.quantite_utilisee = Decimal(
                    str(request.data.get('quantite_utilisee') or 0))
            except (InvalidOperation, TypeError, ValueError):
                return Response({'quantite_utilisee': 'Quantité invalide.'},
                                status=status.HTTP_400_BAD_REQUEST)
            fields.append('quantite_utilisee')
        if 'justification' in request.data:
            ligne.justification = (request.data.get('justification') or '').strip()
            fields.append('justification')
        if 'justification_memo' in request.data:
            memo = interv.voice_memos.filter(
                id=request.data.get('justification_memo')).first()
            ligne.justification_memo = memo
            fields.append('justification_memo')
        if fields:
            ligne.save(update_fields=fields)
        return Response(ConsommationLigneSerializer(ligne).data)

    @action(detail=True, methods=['post'],
            url_path='supprimer-ligne-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_ligne_consommation(self, request, pk=None):
        """F11 — supprime une ligne HORS-nomenclature. Corps : {"ligne": <id>}."""
        interv = self.get_object()
        cons = field_capture.ensure_consommation(interv)
        if cons.valide:
            return Response({'detail': 'Réconciliation déjà validée.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ligne = cons.lignes.filter(
            id=request.data.get('ligne'), hors_nomenclature=True).first()
        if ligne is None:
            return Response(
                {'detail': 'Seules les lignes hors-nomenclature sont supprimables.'},
                status=status.HTTP_400_BAD_REQUEST)
        ligne.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='valider-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def valider_consommation(self, request, pk=None):
        """F11 — valide la réconciliation : la consommation RÉELLE pilote les
        mouvements de stock (et la marge job-costing). Refuse si une variance
        n'est pas justifiée (texte ou mémo vocal)."""
        interv = self.get_object()
        cons = field_capture.ensure_consommation(interv)
        if cons.valide:
            return Response({'detail': 'Réconciliation déjà validée.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Pré-contrôle des justifications manquantes : on construit le message
        # utilisateur (libellés des lignes en écart) à partir des DONNÉES, sans
        # le faire transiter par un objet exception (évite toute fuite
        # d'information via une exception).
        missing = field_capture.consommation_missing_justifications(cons)
        if missing:
            return Response(
                {'detail': 'Justification requise sur les lignes en écart : '
                 + ', '.join(li.designation for li in missing) + '.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            nb = field_capture.validate_consommation(cons, request.user)
        except ValueError:
            # Garde défensive : message générique contrôlé, jamais le texte brut
            # de l'exception.
            return Response(
                {'detail': 'Validation impossible : vérifiez les lignes de '
                 'consommation.'},
                status=status.HTTP_400_BAD_REQUEST)
        intervention_activity.log_note(
            interv, request.user,
            f"Matériel consommé validé — {nb} référence(s) sortie(s) du stock.")
        return self._consommation_response(interv)

    # ── XFSM22 — durée & pièces suggérées par l'historique ──────────────────
    @action(detail=False, methods=['get'], url_path='suggestions-creation',
            permission_classes=[IsAnyRole])
    def suggestions_creation(self, request):
        """XFSM22 — suggestions affichées à la CRÉATION d'une intervention
        (jamais forcées) : durée médiane (F15) + pièces les plus consommées
        (F11) sur l'historique similaire. Query params : `type_intervention`
        (requis), `technicien` (id, optionnel), `type_installation` (optionnel).
        Silencieux sous le seuil d'historique."""
        from ..selectors import (
            suggestion_duree_intervention, suggestion_pieces_intervention,
        )
        company = request.user.company
        type_intervention = request.query_params.get('type_intervention')
        if not type_intervention:
            return Response(
                {'detail': 'type_intervention est requis.'}, status=400)
        technicien = None
        technicien_id = request.query_params.get('technicien')
        if technicien_id:
            from authentication.models import CustomUser
            technicien = CustomUser.objects.filter(
                id=technicien_id, company=company).first()
        duree = suggestion_duree_intervention(
            company, type_intervention, technicien=technicien)
        pieces = suggestion_pieces_intervention(
            company, type_intervention,
            type_installation=request.query_params.get('type_installation'))
        return Response({'duree': duree, 'pieces': pieces})

    @action(detail=False, methods=['get'], url_path='overage-review',
            permission_classes=[IsAnyRole])
    def overage_review(self, request):
        """F12 — interventions dont la consommation dépasse le devis au-delà du
        seuil % (éditable en Paramètres), avec justifications attachées. Aucun
        prix d'achat ni marge."""
        company = request.user.company
        rows = field_capture.interventions_en_revue(company)
        out = []
        for interv, overages in rows:
            inst = interv.installation
            out.append({
                'intervention': interv.id,
                'chantier': inst.reference if inst else '',
                'type': interv.get_type_intervention_display(),
                'overage': overages,
            })
        return Response({
            'seuil_pct': field_capture.overage_threshold_pct(company),
            'interventions': out,
        })

    # ── F13/F14 — mémos vocaux (+ transcription swappable no-op) ─────────────
    @action(detail=True, methods=['get'], url_path='memos',
            permission_classes=[IsAnyRole])
    def memos(self, request, pk=None):
        """F13 — mémos vocaux de l'intervention (audio + transcription F14)."""
        interv = self.get_object()
        return Response(VoiceMemoSerializer(
            interv.voice_memos.all(), many=True,
            context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='ajouter-memo',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_memo(self, request, pk=None):
        """F13 — enregistre un mémo vocal (multipart `file`, audio) stocké via le
        stockage objet GÉNÉRIQUE existant. F14 — tente une transcription via
        l'interface SWAPPABLE (no-op par défaut → « Non transcrit — service non
        configuré »). Corps multipart : file, [cible]."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import store_attachment
        interv = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier audio fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        meta, err = store_attachment(file, audio=True)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)
        ct = ContentType.objects.get_for_model(Intervention)
        att = Attachment.objects.create(
            company=interv.company, content_type=ct, object_id=interv.id,
            uploaded_by=request.user, phase='', **meta)
        cible = (request.data.get('cible') or VoiceMemo.Cible.GENERAL)
        if cible not in dict(VoiceMemo.Cible.choices):
            cible = VoiceMemo.Cible.GENERAL
        memo = VoiceMemo.objects.create(
            company=interv.company, intervention=interv, cible=cible,
            audio=att, created_by=request.user)
        # F14 — transcription via interface swappable (no-op pose le libellé).
        field_capture.transcribe_memo(memo)
        return Response(VoiceMemoSerializer(
            memo, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='modifier-memo',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_memo(self, request, pk=None):
        """F14 — édite la transcription d'un mémo (l'audio reste source de
        vérité). Corps : {"memo": <id>, "transcript": str}."""
        interv = self.get_object()
        memo = interv.voice_memos.filter(id=request.data.get('memo')).first()
        if memo is None:
            return Response({'detail': 'Mémo inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if 'transcript' in request.data:
            memo.transcript = request.data.get('transcript') or ''
            memo.transcrit = True
            memo.save(update_fields=['transcript', 'transcrit'])
        return Response(VoiceMemoSerializer(
            memo, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='supprimer-memo',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_memo(self, request, pk=None):
        """F13 — supprime un mémo vocal (objet audio + enregistrement). Corps :
        {"memo": <id>}."""
        from apps.records.storage import delete_attachment
        interv = self.get_object()
        memo = interv.voice_memos.filter(id=request.data.get('memo')).first()
        if memo is None:
            return Response({'detail': 'Mémo inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if memo.audio_id:
            delete_attachment(memo.audio.file_key)
            memo.audio.delete()
        memo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── F15 — temps d'équipe ─────────────────────────────────────────────────
    @action(detail=True, methods=['get'], url_path='crew-time',
            permission_classes=[IsAnyRole])
    def crew_time(self, request, pk=None):
        """F15 — durée sur site + temps de trajet, et jours-homme dérivés."""
        interv = self.get_object()
        data = field_capture.crew_time(interv)
        data['labour_jours'] = field_capture.labour_days_for_intervention(interv)
        return Response(data)

    # ── ZFSM1 — gabarit de fiche d'intervention (relevé matérialisé) ─────────
    @action(detail=True, methods=['get'], url_path='fiche',
            permission_classes=[IsAnyRole])
    def fiche(self, request, pk=None):
        """ZFSM1 — relevé de fiche d'intervention (mesures/cases/texte) selon
        le gabarit du type de l'intervention. Matérialisé paresseusement à la
        première consultation. `null` si aucun gabarit ne correspond au type."""
        interv = self.get_object()
        releve = field_services.ensure_fiche_releve(interv)
        if releve is None:
            return Response(None)
        return Response(FicheInterventionReleveSerializer(
            releve, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='renseigner-fiche',
            permission_classes=[IsResponsableOrAdmin])
    def renseigner_fiche(self, request, pk=None):
        """ZFSM1 — renseigne la valeur d'UN champ du relevé. Corps :
        {"valeur_id": <id>, "valeur": <str>}."""
        interv = self.get_object()
        releve = field_services.ensure_fiche_releve(interv)
        if releve is None:
            return Response({'detail': "Aucun gabarit pour ce type d'intervention."},
                            status=status.HTTP_400_BAD_REQUEST)
        valeur_obj = releve.valeurs.filter(
            id=request.data.get('valeur_id')).first()
        if valeur_obj is None:
            return Response({'detail': 'Champ de fiche inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        valeur_obj.valeur = str(request.data.get('valeur', '') or '').strip()
        valeur_obj.renseigne_le = timezone.now()
        valeur_obj.save(update_fields=['valeur', 'renseigne_le'])
        return Response(FicheInterventionReleveSerializer(
            releve, context={'request': request}).data)

    # ── F16 — réserves (punch-list) ──────────────────────────────────────────
    @action(detail=True, methods=['get'], url_path='reserves',
            permission_classes=[IsAnyRole])
    def reserves(self, request, pk=None):
        """F16 — réserves (punch-list) de l'intervention."""
        interv = self.get_object()
        return Response(ReserveSerializer(
            interv.reserves.all(), many=True,
            context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='ajouter-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_reserve(self, request, pk=None):
        """F16 — crée une réserve (description, photo, mémo, assigné). Peut
        engendrer une intervention de suivi OU un ticket SAV. Corps :
        description, [assignee], [photo], [memo], [creer_suivi], [creer_ticket]."""
        interv = self.get_object()
        company = interv.company
        assignee = None
        if request.data.get('assignee'):
            from authentication.models import CustomUser
            assignee = CustomUser.objects.filter(
                id=request.data.get('assignee'), company=company).first()
        photo = None
        if request.data.get('photo'):
            from apps.records.models import Attachment
            photo = Attachment.objects.filter(
                id=request.data.get('photo'), company=company).first()
        memo = None
        if request.data.get('memo'):
            memo = interv.voice_memos.filter(
                id=request.data.get('memo')).first()
        reserve = Reserve.objects.create(
            company=company, intervention=interv,
            description=(request.data.get('description') or '').strip(),
            assignee=assignee, photo=photo, memo=memo,
            created_by=request.user)
        # Suivi optionnel : intervention de suivi (même chantier) et/ou ticket.
        if request.data.get('creer_suivi'):
            suivi = Intervention.objects.create(
                company=company, installation=interv.installation,
                type_intervention=Intervention.Type.CONTROLE,
                created_by=request.user)
            intervention_activity.log_creation(suivi, request.user)
            reserve.suivi_intervention = suivi
            reserve.save(update_fields=['suivi_intervention'])
        if request.data.get('creer_ticket'):
            ticket = self._spawn_ticket_for_reserve(reserve, request.user)
            if ticket is not None:
                reserve.ticket = ticket
                reserve.save(update_fields=['ticket'])
        return Response(ReserveSerializer(
            reserve, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    def _spawn_ticket_for_reserve(self, reserve, user):
        """F16 — crée un ticket SAV correctif pour une réserve, selon le design
        SAV existant (référence sans collision)."""
        from apps.sav.services import create_corrective_ticket
        interv = reserve.intervention
        inst = interv.installation
        if inst is None or inst.client_id is None:
            return None
        company = reserve.company
        return create_corrective_ticket(
            company=company, client=inst.client, installation=inst,
            description=reserve.description or 'Réserve d\'intervention',
            created_by=user)

    # ── XFSM13 — re-vérification IEC 62446-2 vs baseline de recette ─────────
    @action(detail=True, methods=['post'], url_path='enregistrer-reverification',
            permission_classes=[IsResponsableOrAdmin])
    def enregistrer_reverification_view(self, request, pk=None):
        """XFSM13 — enregistre une re-vérification IEC 62446-2 (points
        électriques comparés à la baseline de recette du chantier). Corps :
        {"isolement_mohm": ..., "continuite_terre_ohm": ...,
        "voc_par_string": {"A": 620.5, ...}, "observations": ...,
        ["seuil_alerte_pct"]}. Un dépassement du seuil crée une Reserve."""
        interv = self.get_object()
        seuil = request.data.get('seuil_alerte_pct', 20)
        try:
            seuil = float(seuil)
        except (TypeError, ValueError):
            seuil = 20
        reverif = enregistrer_reverification(
            interv, request.data, user=request.user, seuil_alerte_pct=seuil)
        return Response(
            ReverificationMesureSerializer(reverif).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='reverifications',
            permission_classes=[IsAnyRole])
    def reverifications(self, request, pk=None):
        """XFSM13 — historique des re-vérifications de l'intervention."""
        interv = self.get_object()
        from ..models import ReverificationMesure
        qs = ReverificationMesure.objects.filter(
            intervention_id=interv.id).order_by('-date_creation')
        return Response(ReverificationMesureSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='modifier-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_reserve(self, request, pk=None):
        """F16 — édite une réserve (description, assignee). Corps : reserve, ..."""
        interv = self.get_object()
        reserve = interv.reserves.filter(id=request.data.get('reserve')).first()
        if reserve is None:
            return Response({'detail': 'Réserve inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        fields = []
        if 'description' in request.data:
            reserve.description = (request.data.get('description') or '').strip()
            fields.append('description')
        if 'assignee' in request.data:
            from authentication.models import CustomUser
            reserve.assignee = CustomUser.objects.filter(
                id=request.data.get('assignee'), company=interv.company).first()
            fields.append('assignee')
        if fields:
            reserve.save(update_fields=fields)
        return Response(ReserveSerializer(
            reserve, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='resoudre-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def resoudre_reserve(self, request, pk=None):
        """F16 — résout (ou ré-ouvre) une réserve. Corps : reserve, resolution,
        [statut]."""
        interv = self.get_object()
        reserve = interv.reserves.filter(id=request.data.get('reserve')).first()
        if reserve is None:
            return Response({'detail': 'Réserve inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        statut = request.data.get('statut', Reserve.Statut.RESOLUE)
        reserve.statut = statut
        reserve.resolution = (request.data.get('resolution') or '').strip()
        reserve.resolue_le = (timezone.now()
                              if statut == Reserve.Statut.RESOLUE else None)
        reserve.save(update_fields=['statut', 'resolution', 'resolue_le'])
        return Response(ReserveSerializer(
            reserve, context={'request': request}).data)

    # ── XFSM18 — réserve → devis de réparation ──────────────────────────────
    @action(detail=True, methods=['post'], url_path='generer-devis-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def generer_devis_reserve(self, request, pk=None):
        """XFSM18 — génère un devis brouillon de réparation à partir d'une
        réserve (client du chantier résolu côté serveur, description
        pré-remplie). Idempotent : si la réserve porte déjà un
        `devis_repare_id`, le renvoie sans en créer un second. Corps :
        {"reserve": <id>}."""
        interv = self.get_object()
        reserve = interv.reserves.filter(id=request.data.get('reserve')).first()
        if reserve is None:
            return Response({'detail': 'Réserve inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if reserve.devis_repare_id:
            return Response({
                'reserve': reserve.id, 'devis_id': reserve.devis_repare_id,
                'deja_existant': True,
            })
        from apps.ventes.services import create_devis_from_reserve
        try:
            devis = create_devis_from_reserve(reserve=reserve, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        reserve.devis_repare_id = devis.id
        reserve.save(update_fields=['devis_repare_id'])
        return Response({
            'reserve': reserve.id, 'devis_id': devis.id,
            'devis_reference': devis.reference, 'deja_existant': False,
        }, status=status.HTTP_201_CREATED)

    # ── F17 — réconciliation du retour d'outillage ──────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='tool-return',
            permission_classes=[IsAnyRole])
    def tool_return(self, request, pk=None):
        """F17 — état du retour d'outillage : les outils du kit de préparation,
        rendu/non rendu.

        ERR81 — la matérialisation des lignes (écriture) passe par POST et est
        IDEMPOTENTE/anti-course (get_or_create sur l'unique_together
        intervention+outil) ; le GET reste une simple lecture qui amorce les
        lignes manquantes sans jamais doublonner.
        ERR82 — un outil déjà sorti (réservé) sur une AUTRE intervention non
        confirmée n'est pas ajouté ici (anti double-réservation) ; il est
        signalé dans `conflits`."""
        interv = self.get_object()
        return self._tool_return_response(interv)

    def _checkout_conflicts(self, interv, outil_ids):
        """ERR82 — outils déjà « sortis » (réservés) sur une autre intervention :
        une ligne de retour NON confirmée et NON rendue ailleurs vaut une
        sortie en cours. Renvoie {outil_id: intervention_id} en conflit."""
        if not outil_ids:
            return {}
        busy = (ToolReturn.objects
                .filter(company=interv.company, outil_id__in=list(outil_ids),
                        rendu=False, confirme_le__isnull=True)
                .exclude(intervention=interv)
                .values_list('outil_id', 'intervention_id'))
        return {oid: iid for oid, iid in busy}

    def _tool_return_response(self, interv):
        # Amorce les lignes de retour depuis les outils de la préparation, de
        # façon IDEMPOTENTE (get_or_create) — pas de doublon même en course
        # (ERR81). Un outil déjà réservé sur une autre intervention non
        # confirmée est ÉCARTÉ (anti double-réservation, ERR82).
        prep = getattr(interv, 'preparation', None)
        conflicts = {}
        if prep is not None:
            existing = {tr.outil_id for tr in interv.tool_returns.all()}
            wanted = [ol.outil_id for ol in prep.outils.all()
                      if ol.outil_id and ol.outil_id not in existing]
            conflicts = self._checkout_conflicts(interv, wanted)
            for outil_id in wanted:
                if outil_id in conflicts:
                    continue
                ToolReturn.objects.get_or_create(
                    intervention=interv, outil_id=outil_id,
                    defaults={'company': interv.company})
        rows = ToolReturnSerializer(
            interv.tool_returns.select_related(
                'outil', 'emplacement_retour').all(), many=True).data
        if conflicts:
            return Response({'tool_returns': rows, 'conflits': [
                {'outil': oid, 'intervention': iid}
                for oid, iid in conflicts.items()]})
        return Response(rows)

    @action(detail=True, methods=['post'], url_path='cocher-tool-return',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_tool_return(self, request, pk=None):
        """F17 — marque un outil rendu/non rendu + emplacement de retour. Corps :
        {"ligne": <id>, "rendu": bool, "emplacement": <id|null>}."""
        interv = self.get_object()
        self._tool_return_response(interv)
        tr = interv.tool_returns.filter(id=request.data.get('ligne')).first()
        if tr is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        tr.rendu = bool(request.data.get('rendu', True))
        fields = ['rendu']
        if 'emplacement' in request.data:
            from apps.stock.selectors import get_emplacement_scoped
            emp_id = request.data.get('emplacement')
            tr.emplacement_retour = (
                get_emplacement_scoped(interv.company, emp_id)
                if emp_id else None)
            fields.append('emplacement_retour')
        tr.save(update_fields=fields)
        return Response(ToolReturnSerializer(tr).data)

    @action(detail=True, methods=['post'], url_path='confirmer-tool-return',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_tool_return(self, request, pk=None):
        """F17 — confirme le retour d'outillage à la clôture : met à jour le
        statut + l'emplacement de chaque outil rendu (Disponible) et signale les
        non rendus (statut maintenu « En intervention »)."""
        from apps.outillage.models import Outillage
        interv = self.get_object()
        self._tool_return_response(interv)
        non_rendus = []
        for tr in interv.tool_returns.select_related('outil').all():
            outil = tr.outil
            if outil is None:
                continue
            if tr.rendu:
                outil.statut = Outillage.Statut.DISPONIBLE
                if tr.emplacement_retour_id:
                    outil.emplacement = tr.emplacement_retour
                outil.save(update_fields=['statut', 'emplacement'])
            else:
                outil.statut = Outillage.Statut.EN_INTERVENTION
                outil.save(update_fields=['statut'])
                non_rendus.append(outil.nom)
            tr.confirme_par = request.user
            tr.confirme_le = timezone.now()
            tr.save(update_fields=['confirme_par', 'confirme_le'])
        msg = "Retour d'outillage confirmé."
        if non_rendus:
            msg += f" Non rendus : {', '.join(non_rendus)}."
        intervention_activity.log_note(interv, request.user, msg)
        return Response({
            'non_rendus': non_rendus,
            'tool_returns': ToolReturnSerializer(
                interv.tool_returns.all(), many=True).data,
        })

    # ── F18 — consignes de sécurité (sign-off) ──────────────────────────────
    @action(detail=True, methods=['get'], url_path='safety',
            permission_classes=[IsAnyRole])
    def safety(self, request, pk=None):
        """F18 — sign-off des consignes de sécurité (checklist configurable)."""
        interv = self.get_object()
        signoff = field_capture.ensure_safety_signoff(interv)
        return Response(SafetySignoffSerializer(signoff).data)

    @action(detail=True, methods=['post'], url_path='cocher-safety',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_safety(self, request, pk=None):
        """F18 — coche/décoche un point de consigne, avec qui + quand. Corps :
        {"cle": <str>, "coche": bool}."""
        interv = self.get_object()
        signoff = field_capture.ensure_safety_signoff(interv)
        item = signoff.items.filter(cle=request.data.get('cle')).first()
        if item is None:
            return Response({'detail': 'Consigne inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        coche = bool(request.data.get('coche', True))
        item.coche = coche
        item.coche_par = request.user if coche else None
        item.coche_le = timezone.now() if coche else None
        item.save(update_fields=['coche', 'coche_par', 'coche_le'])
        return Response(SafetySignoffSerializer(signoff).data)

    @action(detail=True, methods=['post'], url_path='signer-safety',
            permission_classes=[IsResponsableOrAdmin])
    def signer_safety(self, request, pk=None):
        """F18 — signe les consignes de sécurité (qui + quand)."""
        interv = self.get_object()
        signoff = field_capture.ensure_safety_signoff(interv)
        signoff.signe = True
        signoff.signe_par = request.user
        signoff.signe_le = timezone.now()
        signoff.save(update_fields=['signe', 'signe_par', 'signe_le'])
        intervention_activity.log_note(
            interv, request.user, "Consignes de sécurité signées.")
        return Response(SafetySignoffSerializer(signoff).data)

    # ── F19 — compte-rendu d'intervention PDF (client-facing) ───────────────
    @action(detail=True, methods=['get'], url_path='compte-rendu',
            permission_classes=[IsAnyRole])
    def compte_rendu(self, request, pk=None):
        """F19 — compte-rendu d'intervention en PDF. F9 serials, F11 consommation
        avec justifications, F16 réserves, photos avant/pendant/après, bloc
        signature « Bon pour accord ». Client-facing : aucun prix d'achat."""
        from django.http import HttpResponse
        from .. import intervention_pdf
        interv = self.get_object()
        # Pousse les n° de série relevés vers le parc installé (F9) avant le PDF.
        field_capture.push_serials_to_parc(interv, request.user)
        pdf_bytes = intervention_pdf.compte_rendu_pdf(interv)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="compte-rendu-intervention-{interv.id}.pdf"')
        return resp

    # ── ZFSM2 — lien public tokenisé du compte-rendu signé ──────────────────
    @action(detail=True, methods=['get'], url_path='lien-rapport',
            permission_classes=[IsResponsableOrAdmin])
    def lien_rapport(self, request, pk=None):
        """ZFSM2 — génère (lazily) et renvoie l'URL publique du compte-rendu
        signé de cette intervention, à partager par WhatsApp/SMS (pattern
        FG86/liens WhatsApp/XFSM7). Jeton DISTINCT du lien « en route »."""
        interv = self.get_object()
        token = interv.ensure_lien_rapport_token()
        return Response({
            'token': token,
            'path': f'/public/installations/intervention-rapport/{token}/'})

    # ── ZFSM4 — facturation directe d'une intervention hors contrat ─────────
    @action(detail=True, methods=['post'], url_path='generer-facture',
            permission_classes=[IsResponsableOrAdmin])
    def generer_facture(self, request, pk=None):
        """ZFSM4 — génère une facture brouillon depuis cette intervention
        (matériel réellement consommé au prix de VENTE catalogue + ligne
        main-d'œuvre au taux horaire paramétrable). Idempotent : si
        l'intervention porte déjà un `facture_id`, le renvoie sans en créer
        une seconde. Passe EXCLUSIVEMENT par apps.ventes.services (jamais
        d'import direct des models ventes — règle de modularité)."""
        interv = self.get_object()
        # ZFSM4 — capturer l'état AVANT l'appel : le service pose
        # ``intervention.facture_id`` en place sur cet objet, donc comparer
        # après renverrait TOUJOURS deja_existant=True (jamais 201 à la
        # première création). On mémorise le facture_id préexistant.
        prev_facture_id = interv.facture_id
        from apps.ventes.services import generer_facture_intervention
        try:
            facture = generer_facture_intervention(
                intervention=interv, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        deja_existant = (prev_facture_id == facture.id)
        return Response({
            'intervention': interv.id, 'facture_id': facture.id,
            'facture_reference': facture.reference,
            'deja_existant': deja_existant,
        }, status=status.HTTP_200_OK if deja_existant else status.HTTP_201_CREATED)

    # ── ZFSM5 — devis d'upsell créé sur place depuis l'intervention ─────────
    @action(detail=True, methods=['post'], url_path='generer-devis',
            permission_classes=[IsResponsableOrAdmin])
    def generer_devis(self, request, pk=None):
        """ZFSM5 — génère un devis brouillon d'upsell depuis cette
        intervention (client résolu server-side depuis le chantier,
        description pré-remplie). Idempotent : si l'intervention porte déjà
        un `devis_upsell_id`, le renvoie sans en créer un second. DISTINCT de
        `generer-devis-reserve` (XFSM18, réserve → devis de réparation)."""
        interv = self.get_object()
        # ZFSM5 — même correctif que generer_facture : mémoriser l'id AVANT
        # (le service pose ``devis_upsell_id`` en place → sinon toujours 200).
        prev_devis_id = interv.devis_upsell_id
        from apps.ventes.services import create_devis_upsell_from_intervention
        try:
            devis = create_devis_upsell_from_intervention(
                intervention=interv, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        deja_existant = (prev_devis_id == devis.id)
        return Response({
            'intervention': interv.id, 'devis_id': devis.id,
            'devis_reference': devis.reference,
            'deja_existant': deja_existant,
        }, status=status.HTTP_200_OK if deja_existant else status.HTTP_201_CREATED)

    # ── F23 — code court / QR de l'intervention ──────────────────────────────
    @action(detail=True, methods=['get'], url_path='code',
            permission_classes=[IsAnyRole])
    def code(self, request, pk=None):
        """F23 — jeton scannable de l'intervention (réutilise l'encodeur N20).
        Renvoie le jeton + un QR SVG inline ; scanner une étiquette chantier/
        matériel résout vers cette intervention via /stock/.../resolve."""
        from apps.stock import labels
        interv = self.get_object()
        token = labels.intervention_token(interv.id)
        return Response({
            'intervention': interv.id,
            'token': token,
            'qr_svg': labels.qr_svg(token),
        })

    # ── F20 — contrôle qualité IA des photos (interface vision swappable) ────
    @action(detail=True, methods=['get'], url_path='photo-qa',
            permission_classes=[IsAnyRole])
    def photo_qa(self, request, pk=None):
        """F20 — signale les photos obligatoires probablement manquantes ou de
        mauvaise qualité via l'interface de VISION SWAPPABLE (réutilise le patron
        Claude déjà dans la stack). N'ajoute aucun identifiant externe par
        défaut, no-op (liste vide) quand désactivé, et ne BLOQUE JAMAIS la
        complétion. Renvoie {actif, signalements}."""
        from .. import swappable
        interv = self.get_object()
        photos = []
        for slot in field_services.active_shotlist(interv.company):
            atts = field_services.photos_by_slot(interv).get(slot.cle, [])
            photos.append({
                'cle': slot.cle, 'libelle': slot.libelle,
                'obligatoire': slot.obligatoire, 'nb_photos': len(atts)})
        flags = swappable.review_photos(interv.company, photos)
        return Response({
            'actif': swappable.photo_qa_active(interv.company),
            'signalements': flags,
        })

    # ── FG78 — confirmation RDV + reschedule tracking ───────────────────────
    @action(detail=True, methods=['post'], url_path='confirmer-rdv',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_rdv(self, request, pk=None):
        """FG78 — marque le RDV client comme confirmé (ou le déconfirme si
        `confirme=false`). Incrémente `rdv_reschedule_count` quand une nouvelle
        date est fournie avec `date_prevue` (reschedule). Métadonnées only —
        ne touche JAMAIS le statut de l'intervention."""
        interv = self.get_object()
        confirme = bool(request.data.get('confirme', True))
        new_date = request.data.get('date_prevue')
        fields = ['rdv_confirme', 'rdv_confirme_le']
        interv.rdv_confirme = confirme
        interv.rdv_confirme_le = timezone.now() if confirme else None
        if new_date and new_date != str(interv.date_prevue or ''):
            interv.date_prevue = new_date
            interv.rdv_reschedule_count = (interv.rdv_reschedule_count or 0) + 1
            fields += ['date_prevue', 'rdv_reschedule_count']
        interv.save(update_fields=fields)
        msg = ("RDV confirmé." if confirme
               else "Confirmation RDV annulée.")
        if 'date_prevue' in fields:
            msg += f" Reporté au {new_date} (reschedule #{interv.rdv_reschedule_count})."
        intervention_activity.log_note(interv, request.user, msg)
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    # ── FG68 — calendrier dispatch techniciens ───────────────────────────────
    @action(detail=False, methods=['get'], url_path='calendrier',
            permission_classes=[IsAnyRole])
    def calendrier(self, request):
        """FG68 — vue calendrier des interventions groupées par technicien.
        Params : date_from, date_to (YYYY-MM-DD). Renvoie une liste de
        techniciens avec leurs interventions prévues sur la plage. Les
        interventions sans technicien sont groupées sous la clé `non_assigne`."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        company = request.user.company
        params = request.query_params
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        qs = Intervention.objects.filter(company=company, annulee=False)
        if date_from:
            qs = qs.filter(date_prevue__gte=date_from)
        if date_to:
            qs = qs.filter(date_prevue__lte=date_to)
        qs = qs.select_related(
            'technicien', 'installation', 'installation__client',
            'camionnette',
        ).order_by('date_prevue', 'id')
        # Regrouper par technicien
        from collections import defaultdict
        by_tech = defaultdict(list)
        for interv in qs:
            key = interv.technicien_id or 'non_assigne'
            by_tech[key].append(interv)
        # XFSM4 — au sein d'un même technicien, priorité (urgente d'abord)
        # PUIS date (le regroupement ci-dessus est déjà trié par date).
        from datetime import date as _date
        for intervs in by_tech.values():
            intervs.sort(key=lambda iv: (
                self._PRIORITE_RANG.get(iv.priorite, 2),
                iv.date_prevue or _date.min))
        result = []
        # Techniciens assignés
        tech_ids = [k for k in by_tech if k != 'non_assigne']
        if tech_ids:
            techs = {u.id: u for u in User.objects.filter(id__in=tech_ids)}
        else:
            techs = {}
        for tech_id, intervs in by_tech.items():
            if tech_id == 'non_assigne':
                tech_data = {'id': None, 'nom': 'Non assigné'}
            else:
                u = techs.get(tech_id)
                tech_data = {
                    'id': tech_id,
                    'nom': getattr(u, 'get_full_name', lambda: '')() or getattr(u, 'username', str(tech_id)),
                }
            result.append({
                'technicien': tech_data,
                'interventions': InterventionSerializer(
                    intervs, many=True, context={'request': request}).data,
            })
        # Trier : techniciens assignés d'abord (par nom), puis non assigné
        result.sort(key=lambda x: (x['technicien']['id'] is None,
                                   x['technicien'].get('nom', '')))
        return Response(result)

    # ── FG69 — signature client sur compte-rendu ─────────────────────────────
    @action(detail=True, methods=['post'], url_path='signer-client',
            permission_classes=[IsAnyRole])
    def signer_client(self, request, pk=None):
        """FG69 — enregistre la signature client sur une intervention.
        Corps : {"signature_client": <data_url_ou_vecteur>, "signataire_nom": <str>}.
        Pose `signe_le` côté serveur."""
        interv = self.get_object()
        sig = request.data.get('signature_client', '').strip()
        nom = request.data.get('signataire_nom', '').strip()
        if not sig:
            return Response({'signature_client': 'Signature vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        interv.signature_client = sig
        if nom:
            interv.signataire_nom = nom
        interv.signe_le = timezone.now()
        fields = ['signature_client', 'signataire_nom', 'signe_le']
        interv.save(update_fields=fields)
        intervention_activity.log_note(
            interv, request.user,
            f"Signature client enregistrée ({nom or 'anonyme'}).")
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    # ── FG73 — tournée journalière du technicien (ordre géographique) ─────────
    @action(detail=False, methods=['get'], url_path='ma-tournee',
            permission_classes=[IsAnyRole])
    def ma_tournee(self, request):
        """FG73 — interventions de la journée du technicien authentifié,
        ordonnées géographiquement (plus proche voisin depuis le dépôt /
        position actuelle). Chaque arrêt inclut un lien « Itinéraire » Google Maps.
        Param optionnel : date (YYYY-MM-DD, défaut=aujourd'hui)."""
        from django.utils.timezone import localdate
        company = request.user.company
        jour = request.query_params.get('date') or str(localdate())
        qs = (Intervention.objects
              .filter(company=company, technicien=request.user, date_prevue=jour)
              .select_related('installation', 'installation__client',
                              'technicien', 'camionnette')
              .prefetch_related('equipe'))
        intervs = list(qs)
        if not intervs:
            return Response({'date': jour, 'stops': []})
        # Nearest-neighbour depuis (0,0) si aucun dépôt GPS connu (dépôt = départ
        # du premier point disponible — on part de coordonnées nulles).
        depot_lat, depot_lng = 0.0, 0.0
        ordered = []
        remaining = intervs[:]
        current_lat, current_lng = depot_lat, depot_lng
        while remaining:
            best = None
            best_d = float('inf')
            for iv in remaining:
                lat = float(iv.installation.gps_lat or 0)
                lng = float(iv.installation.gps_lng or 0)
                d = field_services.haversine_km(
                    current_lat, current_lng, lat, lng) or 0
                if d < best_d:
                    best_d = d
                    best = iv
            ordered.append(best)
            current_lat = float(best.installation.gps_lat or 0)
            current_lng = float(best.installation.gps_lng or 0)
            remaining.remove(best)
        stops = []
        for iv in ordered:
            lat = iv.installation.gps_lat
            lng = iv.installation.gps_lng
            maps_link = None
            if lat and lng:
                maps_link = (
                    f'https://www.google.com/maps/dir/?api=1&destination='
                    f'{lat},{lng}')
            stops.append({
                **InterventionSerializer(
                    iv, context={'request': request}).data,
                'itineraire_url': maps_link,
            })
        return Response({'date': jour, 'stops': stops})

    # ── FG299 — plan de charge des équipes (capacité vs affecté) ─────────────
    @action(detail=False, methods=['get'], url_path='plan-de-charge',
            permission_classes=[IsAnyRole])
    def plan_de_charge(self, request):
        """FG299 — plan de charge des équipes terrain : capacité (jours ouvrés ×
        heures/jour) vs charge affectée (interventions où le technicien est
        principal ou membre d'équipe, prévues dans la fenêtre), avec drapeau de
        SUR-RÉSERVATION par technicien. Pure agrégation, scopée société.
        Params : ``debut``, ``fin`` (YYYY-MM-DD ; défaut = semaine en cours,
        lundi→dimanche), ``heures_par_jour`` (défaut 8). Aucun ``?format=`` —
        sortie JSON simple (export via ``?export=`` non requis ici)."""
        from datetime import date, datetime, timedelta
        from .. import selectors

        def _parse(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        params = request.query_params
        debut = _parse(params.get('debut'))
        fin = _parse(params.get('fin'))
        if debut is None:
            today = date.today()
            debut = today - timedelta(days=today.weekday())  # lundi
        if fin is None:
            fin = debut + timedelta(days=6)  # dimanche
        if fin < debut:
            return Response(
                {'detail': 'La fin de fenêtre précède le début.'},
                status=status.HTTP_400_BAD_REQUEST)
        heures = params.get('heures_par_jour')
        try:
            heures = float(heures) if heures not in (None, '') else 8.0
        except (TypeError, ValueError):
            heures = 8.0
        data = selectors.plan_de_charge_equipes(
            request.user.company, debut, fin, heures_par_jour=heures)
        return Response(data)

    # ── FG300 — détection de conflits d'affectation (double-booking) ─────────
    @action(detail=False, methods=['get'], url_path='conflits-affectation',
            permission_classes=[IsAnyRole])
    def conflits_affectation(self, request):
        """FG300 — liste les conflits d'affectation : une même ressource
        (technicien principal ou membre d'équipe, ou camionnette) affectée à ≥ 2
        interventions dont le créneau se chevauche. Les interventions n'ayant
        qu'une `date_prevue` (granularité jour), le chevauchement = même jour.
        Pure détection, scopée société, aucun nouveau modèle.
        Params : ``debut``, ``fin`` (YYYY-MM-DD ; défaut = semaine en cours,
        lundi→dimanche). Sortie JSON simple (aucun ``?format=``)."""
        from datetime import date, datetime, timedelta
        from .. import selectors

        def _parse(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        params = request.query_params
        debut = _parse(params.get('debut'))
        fin = _parse(params.get('fin'))
        if debut is None:
            today = date.today()
            debut = today - timedelta(days=today.weekday())  # lundi
        if fin is None:
            fin = debut + timedelta(days=6)  # dimanche
        if fin < debut:
            return Response(
                {'detail': 'La fin de fenêtre précède le début.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = selectors.conflits_affectation(
            request.user.company, debut, fin)
        return Response(data)

    # ── FG301 — nivellement de charge (resource levelling) ───────────────────
    @action(detail=False, methods=['get'], url_path='nivellement-charge',
            permission_classes=[IsAnyRole])
    def nivellement_charge(self, request):
        """FG301 — propose un rééquilibrage des interventions des techniciens
        SUR-CHARGÉS (affecté > capacité) vers les SOUS-CHARGÉS, en évitant de
        recréer un conflit FG300. Proposition LECTURE SEULE : rien n'est muté —
        on renvoie la liste des déplacements suggérés (quelle intervention → quel
        technicien). Construit sur FG299 (plan de charge) + FG300 (conflits).
        Pure agrégation, scopée société, aucun nouveau modèle.
        Params : ``debut``, ``fin`` (YYYY-MM-DD ; défaut = semaine en cours,
        lundi→dimanche), ``heures_par_jour`` (défaut 8). Sortie JSON simple
        (aucun ``?format=``)."""
        from datetime import date, datetime, timedelta
        from .. import selectors

        def _parse(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        params = request.query_params
        debut = _parse(params.get('debut'))
        fin = _parse(params.get('fin'))
        if debut is None:
            today = date.today()
            debut = today - timedelta(days=today.weekday())  # lundi
        if fin is None:
            fin = debut + timedelta(days=6)  # dimanche
        if fin < debut:
            return Response(
                {'detail': 'La fin de fenêtre précède le début.'},
                status=status.HTTP_400_BAD_REQUEST)
        heures = params.get('heures_par_jour')
        try:
            heures = float(heures) if heures not in (None, '') else 8.0
        except (TypeError, ValueError):
            heures = 8.0
        data = selectors.nivellement_charge(
            request.user.company, debut, fin, heures_par_jour=heures)
        return Response(data)

    # ── XFSM5 — KPI taux d'arrivée à l'heure (fenêtres de RDV promises) ──────
    @action(detail=False, methods=['get'], url_path='taux-ponctualite',
            permission_classes=[IsAnyRole])
    def taux_ponctualite(self, request):
        """XFSM5 — proportion des arrivées dans la fenêtre promise
        (`fenetre_debut`/`fenetre_fin`), calculée au check-in GPS F6. Filtrable
        par `debut`/`fin` (bornes de `arrivee_site_le`) et `technicien`."""
        from datetime import datetime
        from .. import selectors

        def _parse(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        params = request.query_params
        data = selectors.taux_ponctualite(
            request.user.company,
            debut=_parse(params.get('debut')),
            fin=_parse(params.get('fin')),
            technicien_id=params.get('technicien'))
        return Response(data)

    # ── XFSM2 — Assistant de planification (meilleur créneau + technicien) ──
    @action(detail=False, methods=['post'], url_path='suggerer-creneau',
            permission_classes=[IsAnyRole])
    def suggerer_creneau(self, request):
        """XFSM2 — les 3 meilleures propositions (technicien, date) pour un
        chantier/type/durée cible. Lecture seule, NE MUTE RIEN. Corps :
        {chantier, type_intervention, [duree_jours], [date_cible]}."""
        from datetime import datetime
        from rest_framework.exceptions import ValidationError
        from .. import selectors

        chantier_id = request.data.get('chantier')
        if not chantier_id:
            raise ValidationError({'chantier': 'Chantier requis.'})
        type_intervention = request.data.get('type_intervention') or ''
        duree_jours = request.data.get('duree_jours') or 1
        date_cible_raw = request.data.get('date_cible')
        date_cible = None
        if date_cible_raw:
            try:
                date_cible = datetime.strptime(
                    date_cible_raw, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                raise ValidationError({'date_cible': 'Date invalide.'})
        data = selectors.suggerer_creneau(
            request.user.company, chantier_id=chantier_id,
            type_intervention=type_intervention, duree_jours=duree_jours,
            date_cible=date_cible)
        return Response(data)

    # ── XFSM3 — Replanification en masse d'une journée ──────────────────────
    @action(detail=False, methods=['post'], url_path='replanifier-en-masse',
            permission_classes=[IsResponsableOrAdmin])
    def replanifier_en_masse(self, request):
        """XFSM3 — re-slotte en UN appel les interventions d'un jour (toutes
        celles d'un `technicien` absent, et/ou une liste `intervention_ids`).
        `?simuler=1` (ou body `simuler`) ne mute rien — dry-run des
        propositions XFSM2. Sans dry-run, applique + trace FG78 + notifie.
        Corps : {jour, [technicien], [intervention_ids], [motif]}."""
        from datetime import datetime
        from rest_framework.exceptions import ValidationError
        from .. import services

        jour_raw = request.data.get('jour')
        if not jour_raw:
            raise ValidationError({'jour': 'Jour requis.'})
        try:
            jour = datetime.strptime(jour_raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            raise ValidationError({'jour': 'Date invalide.'})

        technicien_id = request.data.get('technicien')
        intervention_ids = request.data.get('intervention_ids')
        simuler = str(
            request.data.get('simuler')
            or request.query_params.get('simuler') or '').lower() in (
            '1', 'true', 'yes')

        if simuler:
            data = services.previsualiser_replanification_masse(
                request.user.company, jour=jour, technicien_id=technicien_id,
                intervention_ids=intervention_ids)
            return Response(data)

        motif = request.data.get('motif')
        data = services.appliquer_replanification_masse(
            request.user.company, jour=jour, motif=motif, user=request.user,
            technicien_id=technicien_id, intervention_ids=intervention_ids)
        return Response(data)

    # ── FG303 — planning des camionnettes (capacité véhicule) ────────────────
    @action(detail=False, methods=['get'], url_path='planning-camionnettes',
            permission_classes=[IsAnyRole])
    def planning_camionnettes(self, request):
        """FG303 — planning PAR CAMIONNETTE : pour chaque véhicule
        (``Intervention.camionnette``) qui porte des interventions dans la
        fenêtre, la liste des interventions (date / chantier / technicien) + une
        charge journalière qui EXCLUT les jours d'indisponibilité du véhicule
        (FG302). Cohérent avec FG300 : deux interventions le même jour sur la
        même camionnette = sur-réservation. Pure agrégation, scopée société,
        aucun nouveau modèle.
        Params : ``debut``, ``fin`` (YYYY-MM-DD ; défaut = semaine en cours,
        lundi→dimanche), ``capacite_jour`` (défaut 1). Sortie JSON simple
        (aucun ``?format=``)."""
        from datetime import date, datetime, timedelta
        from .. import selectors

        def _parse(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        params = request.query_params
        debut = _parse(params.get('debut'))
        fin = _parse(params.get('fin'))
        if debut is None:
            today = date.today()
            debut = today - timedelta(days=today.weekday())  # lundi
        if fin is None:
            fin = debut + timedelta(days=6)  # dimanche
        if fin < debut:
            return Response(
                {'detail': 'La fin de fenêtre précède le début.'},
                status=status.HTTP_400_BAD_REQUEST)
        cap = params.get('capacite_jour')
        try:
            cap = int(cap) if cap not in (None, '') else 1
        except (TypeError, ValueError):
            cap = 1
        data = selectors.planning_camionnettes(
            request.user.company, debut, fin, capacite_jour=cap)
        return Response(data)
