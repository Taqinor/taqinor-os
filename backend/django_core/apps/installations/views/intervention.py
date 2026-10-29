from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    HasPermissionOrLegacy, IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)
from apps.roles.permissions import DroitDeLaGrille, droits_de_la_grille  # ASEC50
from core.champs_stricts import (
    MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL, date_ou_400, non_blanc)
from core.conflit_etat import ConflitEtat
from core.viewsets import CompanyScopedModelViewSet
from django.utils import timezone

from .. import activity, intervention_activity
from ..listes_prechargees import PhotosPrechargeesListeMixin  # APRF40
from ..models import (
    Installation,
    Intervention,
    TypeIntervention,
    ShotListSlot,
    ComponentSerial,
    ConsommationLigne,
    VoiceMemo,
    Reserve,
    ToolReturn,
)
from ..serializers import (
    InterventionSerializer,
    InterventionActivitySerializer,
    InterventionPreparationSerializer,
    ComponentSerialSerializer,
    MaterielConsommationSerializer,
    ConsommationLigneSerializer,
    VoiceMemoSerializer,
    ReserveSerializer,
    ToolReturnSerializer,
    SafetySignoffSerializer,
    ReverificationMesureSerializer,
    FicheInterventionReleveSerializer,
)
from ..services import enregistrer_reverification
from .. import field_services
from .. import field_capture
from .. import field_sync
from . import _openapi as oa
from ..serializers import PhotoAnnotationSerializer

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


# AUD324 — préchargements communs aux écrans de DISPATCH d'intervention
# (kanban, calendrier FG68, « Ma tournée » FG73).
#
# `InterventionSerializer` porte 5 `SerializerMethodField` sans eager-loading :
# `equipe_noms` (M2M), `preparation_completion` / `preparation_confirmee`
# (OneToOne inverse, jamais préchargé), `reserves_ouvertes` (COUNT sur FK
# inverse) et `photos_obligatoires_manquantes` (shot-list — mémoïsée côté
# serializer). Sans ces préchargements, charger ~50 interventions déclenchait
# 150-250 requêtes additionnelles sur l'écran de dispatch quotidien le plus
# consulté. Le `Prefetch` des réserves est déjà FILTRÉ sur OUVERTE et déposé
# sur un attribut dédié : le serializer en lit la longueur au lieu de refaire
# un COUNT par intervention.
RESERVES_OUVERTES_ATTR = '_reserves_ouvertes_prefetch'


# ``prefixe`` (avec son séparateur final, ex. ``'interventions__'``) rend ces
# préchargements utilisables depuis le chantier qui imbrique ses interventions
# (liste des chantiers) : mêmes définitions, aucune copie.
def dispatch_prefetches(prefixe=''):
    from django.db.models import Prefetch
    return (
        f'{prefixe}equipe',
        f'{prefixe}preparation__materiel',
        f'{prefixe}preparation__outils',
        Prefetch(
            f'{prefixe}reserves',
            queryset=Reserve.objects.filter(statut=Reserve.Statut.OUVERTE),
            to_attr=RESERVES_OUVERTES_ATTR),
    )


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
    from ..services import consume_reservations, release_reservations
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


@oa.listing(
    p0=oa.qs('annulee'),
    p1=oa.qs('priorite'),
    p2=oa.qs('statut'),
    p3=oa.qs('type_intervention'),
    p4=oa.qs('export'),
    p5=oa.qd('date_from'),
    p6=oa.qd('date_to'),
    p7=oa.qi('installation'),
    p8=oa.qi('ticket'),
    p9=oa.qd('date_prevue', desc='Interventions prévues ce jour exact (AAAA-MM-JJ).'),
)
class InterventionViewSet(PhotosPrechargeesListeMixin, oa.CorpsObjetMixin, oa.JsonOnlyMixin, CompanyScopedModelViewSet):
    """Interventions (sorties chantier) rattachées à un chantier (F3). Chacune
    porte son propre statut (machine à états distincte du chantier et de
    STAGES.py), une équipe, une camionnette, et son propre chatter. Scopées à
    la société ; l'acteur et la société sont posés côté serveur."""
    # AUD324 — le kanban/la liste sérialisent l'InterventionSerializer complet :
    # les préchargements de dispatch (préparation, réserves ouvertes) rejoignent
    # `equipe`, sinon chaque intervention tirait ses propres requêtes.
    queryset = Intervention.objects.select_related(
        'installation', 'installation__client', 'installation__devis',
        'technicien', 'camionnette').prefetch_related(
            *dispatch_prefetches()).all()
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
        # ACHT27 — même sélecteur que la synchro terrain (`field_sync`).
        from ..selectors import scoper_interventions
        qs = scoper_interventions(qs, self.request.user)
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
        # Jour exact (« Ma journée » équipe) ; valeur invalide : 400 en amont (oa.listing).
        from django.utils.dateparse import parse_date
        try:
            jour_prevu = parse_date(params.get('date_prevue') or '')
        except ValueError:
            jour_prevu = None
        if jour_prevu:
            qs = qs.filter(date_prevue=jour_prevu)
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
        # ACHT56 — `tool-return` : GET lecture, POST matérialise des lignes.
        if (self.action == 'tool_return'
                and self.request.method not in ('GET', 'HEAD', 'OPTIONS')):
            return [IsResponsableOrAdmin()]
        if self.action == 'commander_manques':
            # ACHT54 — crée un BCF : `achats_commander` en plus du module.
            return [IsResponsableOrAdmin(),
                    HasPermissionOrLegacy('achats_commander')()]
        if self.action in READ_ACTIONS + [
            'historique', 'preparation', 'photos',
            # Lectures du module de capture F9–F19 + F23.
            'serials', 'serials_attendus',
            'consommation', 'memos', 'reserves', 'tool_return',
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
            # XFSM13 — historique des re-vérifications (lecture).
            'reverifications',
            # XFSM22 — durée & pièces suggérées par l'historique.
            'suggestions_creation',
            # ZFSM1 — lecture de la fiche d'intervention (relevé terrain).
            'fiche',
        ]:
            # D-ASEC-50 — la liste ``?export=xlsx`` exige ``installation_export``.
            return [IsAnyRole()] + droits_de_la_grille(
                self, list=[DroitDeLaGrille('installation_export', export=('xlsx',))])
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
            # ACHT56 — FG69 signature client : une ÉCRITURE (un Viewer ne pose
            # plus de signature), jamais rangée dans les lectures.
            'signer_client',
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
            # Suppression : même palier que les écritures.
            'destroy',
        ]:
            # ASEC50 / D-ASEC-4 — affecter un technicien (créer une
            # intervention déjà affectée, changer le ``technicien`` au
            # PUT/PATCH, ou re-slotter une journée sur d'autres techniciens)
            # exige ``technicien_assign``.
            return [IsResponsableOrAdmin()] + droits_de_la_grille(
                self,
                create=[DroitDeLaGrille('technicien_assign', champ='technicien')],
                update=[DroitDeLaGrille('technicien_assign', champ='technicien')],
                partial_update=[
                    DroitDeLaGrille('technicien_assign', champ='technicien')],
                replanifier_en_masse=[DroitDeLaGrille('technicien_assign')])
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

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        installation = serializer.validated_data.get('installation')
        # YSERV6 — un chantier annulé refuse toute nouvelle intervention.
        if installation is not None and installation.annule:
            raise ConflitEtat(
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
            from ..services import verifier_gate_acompte_planification
            raison = verifier_gate_acompte_planification(installation)
            if raison:
                motif_override = (
                    self.request.data.get('motif_override_acompte')
                    or '').strip()
                if not motif_override:
                    raise ConflitEtat({'date_prevue': [raison]})
                activity.log_note(
                    installation, self.request.user,
                    'Intervention de pose planifiée sans acompte — motif : '
                    f'{motif_override}')
        technicien = serializer.validated_data.get('technicien')
        # AUD317 — `statut` était directement ÉCRIVABLE au corps
        # (`fields='__all__'`) SANS aucune garde ni effet : créer une
        # intervention directement en « terminee » contournait la garde F8
        # (photo obligatoire par créneau) et n'émettait jamais
        # `intervention_completed` — le ticket SAV lié restait OUVERT alors que
        # le webhook public `intervention.completed` partait quand même. On
        # crée donc TOUJOURS au statut par défaut, puis on route la transition
        # demandée par le service unique.
        statut_demande = serializer.validated_data.pop('statut', None)
        interv = serializer.save(company=company, created_by=self.request.user)
        # CHT9 — le technicien affecté à la création est notifié (sa propre
        # clé INTERVENTION_ASSIGNEE — jusqu'ici silencieux).
        if technicien is not None:
            from ..services import _notifier_intervention_assignee
            _notifier_intervention_assignee(interv, self.request.user)
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
        # Auto-tampon date_realisee : seul un statut « Terminée »/« Validée »
        # sans date réalisée la pose à aujourd'hui, côté serveur (miroir de
        # _stamp_statut_dates du chantier — ERR-QAH-…-DATE-REALISEE-AUTO).
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
        # AUD317 — la transition demandée à la création passe par le service
        # unique : mêmes gardes et MÊME cascade que le PATCH.
        if statut_demande is not None and statut_demande != interv.statut:
            from ..services import (
                TransitionRefusee, changer_statut_intervention,
            )
            try:
                changer_statut_intervention(
                    interv, statut_demande, self.request.user)
            except TransitionRefusee as exc:
                raise ConflitEtat({'statut': exc.raisons})

    def perform_update(self, serializer):
        """ADAPTATEUR (AUD317) — le statut passe par le service unique.

        Le statut est RETIRÉ du payload validé et confié à
        `services.changer_statut_intervention`, seul porteur de la garde
        F5/F8/ZFSM1 ET de la chaîne d'effets (`_stamp_date_realisee`, chatter
        chantier, `intervention_completed` YSERV2, `ensure_lien_rapport_token`
        ZFSM2) — la même que la création et la synchro terrain obtiennent
        désormais."""
        from ..services import (
            TransitionRefusee, changer_statut_intervention,
        )
        self._check_tenant(serializer)
        old = Intervention.objects.get(pk=serializer.instance.pk)
        intervention_activity.capturer_equipe(old)  # ACHT35
        nouveau_statut = serializer.validated_data.pop('statut', None)
        # Notification CHT9 : seulement quand le technicien CHANGE (pas de
        # bruit sur une simple modification d'une intervention déjà
        # correctement affectée).
        new_technicien = serializer.validated_data.get(
            'technicien', old.technicien)
        technicien_change = (
            new_technicien is not None
            and new_technicien.id != old.technicien_id)
        from django.db import transaction
        with transaction.atomic():
            interv = serializer.save()
            # CHT9 — le technicien RÉAFFECTÉ est notifié (sa propre clé
            # INTERVENTION_ASSIGNEE).
            if technicien_change:
                from ..services import _notifier_intervention_assignee
                _notifier_intervention_assignee(interv, self.request.user)
            # ACHT38 — un PATCH qui DÉPLACE une date déjà fixée est un report :
            # compteur +1, confirmation remise à zéro (service unique).
            if (old.date_prevue is not None
                    and interv.date_prevue is not None
                    and interv.date_prevue != old.date_prevue):
                from ..services import enregistrer_report_rdv
                enregistrer_report_rdv(
                    interv, old.date_prevue, None, self.request.user)
            if nouveau_statut is None or nouveau_statut == old.statut:
                # Pas de transition : effets « édition » inchangés.
                self._stamp_date_realisee(interv)
                intervention_activity.log_changes(
                    old, interv, self.request.user)
                if interv.installation_id:
                    activity.log_note(
                        interv.installation, self.request.user,
                        f"Intervention modifiée : "
                        f"{interv.get_type_intervention_display()}")
                return
            try:
                changer_statut_intervention(
                    interv, nouveau_statut, self.request.user,
                    etat_avant=old)
            except TransitionRefusee as exc:
                corps = {'statut': exc.raisons}
                # Revue chantier 26/10/2026 — séries manquantes (consultatif)
                # à côté des raisons, sans changer le code HTTP.
                if getattr(exc, 'avertissements', None):
                    corps['avertissements'] = exc.avertissements
                # api-fuzz-full 27/10 (ENF11) : la garde F5/F8/ZFSM1/EZ7 (et
                # l'intervention annulée) refuse selon l'ÉTAT stocké — le
                # corps est conforme au schéma → 409 (mêmes clés de corps),
                # comme la création (`perform_create`). Une valeur de statut
                # hors choix reste un 400 du sérialiseur.
                raise ConflitEtat(corps)

    def destroy_guard_message(self, interv):
        """AUD302 — message FR de blocage de la suppression, ou None.

        Une intervention SIGNÉE par le client ou VALIDÉE est une pièce de
        preuve (compte-rendu signé servi par le lien public ZFSM2, base de la
        facturation ZFSM4) : elle ne se détruit plus."""
        if (interv.signature_client or '').strip():
            return ("Cette intervention porte la signature du client : le "
                    "compte-rendu signé ne peut plus être supprimé.")
        if interv.statut == Intervention.Statut.VALIDEE:
            return ("Cette intervention est VALIDÉE : elle ne peut plus être "
                    "supprimée. Reprenez-la en « Terminée » si elle doit être "
                    "corrigée.")
        return None

    def destroy(self, request, *args, **kwargs):
        """AUD302 — garde de suppression (patron ``UsageGuardedDestroyMixin``).

        Le mixin lui-même n'est PAS appliqué ici : il écrirait une SECONDE
        ligne ``AuditLog`` DELETE, car ``('installations', 'Intervention')``
        EST déjà dans ``apps.audit.signals.TRACKED_MODELS`` (contrairement à
        ``CommissioningRecord`` et ``PreuveLivraison``) — le signal générique
        `post_delete` journalise donc déjà toute suppression autorisée. Seule
        la garde manquait."""
        message = self.destroy_guard_message(self.get_object())
        if message:
            return Response({'detail': message},
                            status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

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
        """Pose date_realisee à aujourd'hui si elle est vide et que le statut
        est « Terminée »/« Validée ».

        ERR-QAH-CHANTIERS-INTERVENTION-DATE-REALISEE-AUTO — un `compte_rendu`
        rempli ne suffit PLUS à tamponner : le mini-formulaire du chantier
        n'offre QUE ce champ pour toute note, donc une intervention créée
        « À préparer » avec un simple commentaire se retrouvait marquée
        réalisée aujourd'hui alors qu'elle est encore planifiée. Seul le
        STATUT canonique de complétion fait foi (même esprit que
        `_stamp_statut_dates` côté chantier, qui n'horodate jamais sur du
        contenu de champ)."""
        if interv.date_realisee is not None:
            return
        done = interv.statut in (
            Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
        if done:
            interv.date_realisee = timezone.localdate()
            interv.save(update_fields=['date_realisee'])

    @oa.extend_schema(responses=InterventionActivitySerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        interv = self.get_object()
        return Response(
            InterventionActivitySerializer(
                interv.activites.all(), many=True).data)

    @oa.extend_schema(request=oa.NoterRequete, responses={201: InterventionActivitySerializer})
    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        interv = self.get_object()
        body = oa.corps_valide(oa.NoterRequete, request)['body'].strip()
        act = intervention_activity.log_note(interv, request.user, body)
        return Response(InterventionActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    # ── F5 — Liste de préparation ───────────────────────────────────────────
    def _prep_response(self, interv):
        prep = field_services.ensure_preparation(interv)
        return Response(InterventionPreparationSerializer(
            prep, context={'request': self.request}).data)

    @oa.extend_schema(responses=InterventionPreparationSerializer)
    @action(detail=True, methods=['get'], url_path='preparation',
            permission_classes=[IsAnyRole])
    def preparation(self, request, pk=None):
        """F5 — liste de préparation : matériel (nomenclature gelée du chantier)
        + outils (kit). Matérialisée paresseusement à la première consultation,
        puis renvoyée avec le pourcentage de complétion."""
        return self._prep_response(self.get_object())

    @oa.extend_schema(request=oa.body('ChoisirKitRequete', kit=oa.i(True, null=True)),
                      responses=InterventionPreparationSerializer)
    @action(detail=True, methods=['post'], url_path='choisir-kit',
            permission_classes=[IsResponsableOrAdmin])
    def choisir_kit(self, request, pk=None):
        """F5 — sélectionne (ou retire) le kit d'outillage de la préparation et
        resynchronise les lignes outils. Corps : {"kit": <id|null>}."""
        from apps.outillage.models import KitOutillage
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        # api-fuzz-full 27/10 : `kit` OBLIGATOIRE et nullable (null = retirer le
        # kit), comme publié — absent était accepté (retrait muet du kit).
        kit_id = oa.champ_requis(request, 'kit')
        if kit_id is None:
            prep.kit = None
        else:
            kit = KitOutillage.objects.filter(
                id=oa.id_ou_none(kit_id), company=interv.company).first()
            if kit is None:
                return Response({'kit': 'Kit inconnu.'},
                                status=oa.statut_inconnu(kit_id))
            prep.kit = kit
        # Changer de kit invalide la confirmation « Tout est chargé ».
        prep.tout_charge = False
        prep.confirme_par = None
        prep.confirme_le = None
        prep.save(update_fields=['kit', 'tout_charge', 'confirme_par',
                                 'confirme_le'])
        field_services._sync_outils(prep)
        return self._prep_response(interv)

    @oa.extend_schema(
        request=oa.body('CocherMaterielRequete', ligne=oa.i(True), charge=oa.b()),
        responses=InterventionPreparationSerializer,
    )
    @action(detail=True, methods=['post'], url_path='cocher-materiel',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_materiel(self, request, pk=None):
        """F5 — coche/décoche une ligne matériel comme « chargée ».
        Corps : {"ligne": <id>, "charge": <bool>}."""
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        ligne = prep.materiel.filter(id=oa.id_ou_none(request.data.get('ligne'))).first()
        if ligne is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=oa.statut_inconnu(request.data.get('ligne')))
        charge = bool(request.data.get('charge', True))
        ligne.charge = charge
        ligne.save(update_fields=['charge'])
        # Décocher une ligne retire la confirmation « Tout est chargé ».
        if not charge and prep.tout_charge:
            prep.tout_charge = False
            prep.save(update_fields=['tout_charge'])
        return self._prep_response(interv)

    @oa.extend_schema(
        request=oa.body('CocherOutilRequete', ligne=oa.i(True), coche=oa.b()),
        responses=InterventionPreparationSerializer,
    )
    @action(detail=True, methods=['post'], url_path='cocher-outil',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_outil(self, request, pk=None):
        """F5 — coche/décoche un outil comme « chargé ».
        Corps : {"ligne": <id>, "coche": <bool>}."""
        interv = self.get_object()
        prep = field_services.ensure_preparation(interv)
        ligne = prep.outils.filter(id=oa.id_ou_none(request.data.get('ligne'))).first()
        if ligne is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=oa.statut_inconnu(request.data.get('ligne')))
        coche = bool(request.data.get('coche', True))
        # ACHT72 — cocher = sortir l'outil du parc (409 si perdu / en
        # réparation / déjà sorti).
        try:
            field_services.cocher_outil_ligne(ligne, coche)
        except field_services.OutilIndisponible as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        if not coche and prep.tout_charge:
            prep.tout_charge = False
            prep.save(update_fields=['tout_charge'])
        return self._prep_response(interv)

    @oa.extend_schema(request=None, responses=InterventionPreparationSerializer)
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
            # api-fuzz-full 27/10 (ENF11) : lignes non cochées = refus d'ÉTAT.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        intervention_activity.log_note(
            interv, request.user,
            "Préparation confirmée — « Tout est chargé ».")
        return self._prep_response(interv)

    @oa.extend_schema(request=oa.body('CommanderManquesRequete', fournisseur=oa.i()), responses={201: oa.OBJ})
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
            # api-fuzz-full 27/10 (ENF11) : un fournisseur CITÉ qui ne désigne
            # rien = 404 ; aucun fournisseur par défaut sur les manques = refus
            # d'ÉTAT (le corps vide est valide) = 409.
            return Response(
                {'detail': 'Fournisseur inconnu.' if request.data.get('fournisseur') else (
                    'Aucun fournisseur indiqué et aucun fournisseur '
                    'par défaut sur les produits manquants.')},
                status=oa.statut_inconnu(request.data.get('fournisseur'))
                if request.data.get('fournisseur') else status.HTTP_409_CONFLICT)
        try:
            bon, nb = draft_bcf_for_shortfall(
                inst, fournisseur, request.user, company)
        except ValueError as exc:
            # api-fuzz-full 27/10 (ENF11) : rien à commander / BCF ouvert qui
            # couvre déjà les manques = refus d'ÉTAT.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        data = BonCommandeFournisseurSerializer(
            bon, context={'request': request}).data
        data['nb_lignes'] = nb
        return Response(data, status=status.HTTP_201_CREATED)

    # ── F6 — Trajet & check-in GPS sur site ─────────────────────────────────
    @oa.extend_schema(
        # api-fuzz-full 27/10 (ENF11) : bornes lat/lng publiées ET appliquées.
        request=oa.PositionRequete,
        responses=InterventionSerializer,
    )
    @action(detail=True, methods=['post'], url_path='depart-depot',
            permission_classes=[IsResponsableOrAdmin])
    def depart_depot(self, request, pk=None):
        """F6 — horodate le départ du dépôt (début du trajet). XFSM7 : si le
        navigateur fournit lat/lng, les pose aussi (sert uniquement à l'ETA du
        lien public « technicien en route » — aucune autre logique n'en
        dépend)."""
        interv = self.get_object()
        # Fondateur 27/10/2026 — accord géolocalisation requis (terrain seul).
        if refus := field_services.refus_sans_accord_geoloc(request.user):
            return Response({'detail': refus}, status=status.HTTP_403_FORBIDDEN)
        # ACHT43 — geste unique partagé avec la synchro terrain. Position
        # validée (400) : hors bornes, elle débordait la colonne (500).
        field_services.enregistrer_depart_depot(
            interv, timezone.now(), *oa.position(request), request.user)
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    @oa.extend_schema(responses=oa.OBJ)
    @action(detail=True, methods=['get'], url_path='lien-client',
            permission_classes=[IsResponsableOrAdmin])
    def lien_client(self, request, pk=None):
        """XFSM7 — génère (lazily) et renvoie l'URL publique « technicien en
        route » de cette intervention, à partager par WhatsApp/SMS (pattern
        FG86/liens WhatsApp).

        WIR264 — le `path` renvoyé était `/public/installations/intervention/
        <token>/` : ni une page, ni même un chemin d'API valide (le préfixe
        `/api/django` manquait). Il pointe désormais vers la PAGE publique
        `/intervention/<token>`, et l'`url` absolue est servie comme pour le
        suivi de ticket SAV (`sav.views.lien_client`, FG86)."""
        interv = self.get_object()
        if interv.annulee:  # ACHT51
            return Response(
                {'detail': field_services.MESSAGE_INTERVENTION_ANNULEE},
                status=status.HTTP_409_CONFLICT)
        token = interv.ensure_lien_client_token()
        path = f'/intervention/{token}'
        return Response({
            'token': token,
            'path': path,
            'url': request.build_absolute_uri(path),
        })

    @oa.extend_schema(
        request=oa.PositionRequete,  # même corps validé que le départ dépôt
        responses=InterventionSerializer,
    )
    @action(detail=True, methods=['post'], url_path='checkin',
            permission_classes=[IsResponsableOrAdmin])
    def checkin(self, request, pk=None):
        """F6 — check-in à l'arrivée : horodatage + position GPS (du navigateur,
        aucun service externe). On en dérive une distance-au-site indicative.
        Corps : {"lat": <num>, "lng": <num>}."""
        interv = self.get_object()
        if refus := field_services.refus_sans_accord_geoloc(request.user):  # idem départ
            return Response({'detail': refus}, status=status.HTTP_403_FORBIDDEN)
        # ACHT43 — geste unique partagé avec la synchro terrain (XFSM5 :
        # ponctualité dérivée de l'instant vs la fenêtre promise).
        try:
            field_services.enregistrer_arrivee(
                interv, timezone.now(), *oa.position(request), request.user)
        except field_services.CoordonneesInvalides as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    @oa.extend_schema(request=None, responses=InterventionSerializer)
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
    @oa.extend_schema(responses=oa.OBJ)
    @action(detail=True, methods=['get'], url_path='photos',
            permission_classes=[IsAnyRole])
    def photos(self, request, pk=None):
        """F7/F8 — galerie groupée avant/pendant/après + checklist des créneaux
        obligatoires manquants (garde « Terminée »)."""
        interv = self.get_object()
        field_services.seed_shotlist_slots(interv.company)
        slots = field_services.active_shotlist(interv.company)
        by_slot = field_services.photos_by_slot(interv)
        metas = field_services.metas_photos_intervention(interv)

        def photo_payload(att):
            # Revue chantier 26/10/2026 — géoloc + horodatages (additif).
            geo = field_services.meta_photo_payload(metas.get(att.id))
            return {
                'id': att.id,
                'filename': field_services.display_filename(att),
                'url': f'/api/django/records/attachments/{att.id}/download/',
                'mime': att.mime,
                'created_at': att.created_at,
                'uploaded_by_nom': getattr(att.uploaded_by, 'username', None),
                'lat': geo['lat'], 'lng': geo['lng'],
                'accuracy_m': geo['accuracy_m'],
                'horodatage_serveur': geo['horodatage_serveur'],
                'client_ts': geo['client_ts'],
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

    @oa.extend_schema(
        request=oa.body('AjouterPhotoRequete', file=oa.serializers.FileField(), slot=oa.s(), phase=oa.s(),
                        lat=oa.f(null=True), lng=oa.f(null=True),
                        accuracy_m=oa.f(null=True), client_ts=oa.s(null=True)),
        responses={201: oa.OBJ},
    )
    @action(parser_classes=oa.UPLOAD_PARSERS, detail=True, methods=['post'], url_path='ajouter-photo',
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
        # AUD311 (SCA42) — CLE SCOPEE SOCIETE. `store_attachment`
        # accepte `company=` depuis SCA42 ; l'omettre retombe en
        # silence sur la cle PLATE `attachments/{uuid}.ext` au lieu du
        # prefixe `attachments/{company_id}/{uuid}.ext`. Defense en
        # profondeur : toute lecture applicative est deja scopee par
        # `Attachment.company` et aucun endpoint n'accepte un
        # `file_key` arbitraire.
        meta, err = store_attachment(file, company=interv.company)
        if err:
            # api-fuzz-full 27/10 (ENF11) : format lu dans les OCTETS / taille
            # = règles hors schéma (un ``binary`` publié) → 409, pas 400.
            return Response({'detail': err},
                            status=status.HTTP_409_CONFLICT)
        # Encode le créneau dans le filename pour réutiliser le modèle générique.
        meta = dict(meta)
        meta['filename'] = field_services.encode_slot_filename(
            slot_cle, meta['filename'])
        ct = ContentType.objects.get_for_model(Intervention)
        att = Attachment.objects.create(
            company=interv.company, content_type=ct, object_id=interv.id,
            uploaded_by=request.user, phase=phase, **meta)
        # Revue chantier 26/10/2026 — horodatage serveur + géoloc best-effort
        # (jamais bloquant : une photo sans position reste acceptée).
        geo = field_services.meta_photo_payload(
            field_services.enregistrer_meta_photo_intervention(
                interv, att, request.data))
        intervention_activity.log_note(
            interv, request.user,
            f"Photo ajoutée{(' — ' + slot_cle) if slot_cle else ''}.")
        return Response({
            'id': att.id,
            'filename': field_services.display_filename(att),
            'url': f'/api/django/records/attachments/{att.id}/download/',
            'slot': slot_cle, 'phase': phase,
            'lat': geo['lat'], 'lng': geo['lng'],
            'accuracy_m': geo['accuracy_m'],
            'horodatage_serveur': geo['horodatage_serveur'],
            'client_ts': geo['client_ts'],
        }, status=status.HTTP_201_CREATED)

    def _motif_suppression(self, interv):
        """ACHT41 — motif de suppression d'une pièce de preuve. Renvoie
        ``(motif, reponse_409)`` : sur une intervention terminée/validée le
        motif est OBLIGATOIRE (409 sinon) ; en cours il reste optionnel."""
        motif = (self.request.data.get('motif') or '').strip()
        if not motif and interv.statut in (
                Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE):
            return motif, Response(
                {'detail': 'Intervention terminée : indiquez le motif de '
                           'la suppression.'},
                status=status.HTTP_409_CONFLICT)
        return motif, None

    def _tracer_suppression(self, interv, libelle, motif):
        """ACHT41 — ligne d'historique « <libellé> — motif : … — par <nom> »
        (aucune suppression de preuve ne laisse l'historique muet)."""
        user = self.request.user
        nom = (getattr(user, 'get_full_name', lambda: '')()
               or getattr(user, 'username', '?'))
        corps = libelle
        if motif:
            corps += f" — motif : {motif}"
        intervention_activity.log_note(interv, user, f"{corps} — par {nom}")

    @oa.extend_schema(request=oa.body('SupprimerPhotoRequete', photo=oa.i(True)), responses={204: None})
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
            id=oa.id_ou_none(request.data.get('photo')), content_type=ct,
            object_id=interv.id, company=interv.company).first()
        if att is None:
            return Response({'detail': 'Photo inconnue.'},
                            status=oa.statut_inconnu(request.data.get('photo')))
        motif, refus = self._motif_suppression(interv)  # ACHT41
        if refus is not None:
            return refus
        slot = field_services._slot_of_attachment(att)
        delete_attachment(att.file_key)
        att.delete()
        self._tracer_suppression(
            interv, f"Photo supprimée{(' — ' + slot) if slot else ''}", motif)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── F9 — n° de série par composant (+ OCR swappable no-op) ───────────────
    def _serials_response(self, interv):
        return Response(ComponentSerialSerializer(
            interv.serials.all(), many=True,
            context={'request': self.request}).data)

    @oa.extend_schema(responses=ComponentSerialSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='serials',
            permission_classes=[IsAnyRole])
    def serials(self, request, pk=None):
        """F9 — liste des n° de série relevés sur l'intervention."""
        return self._serials_response(self.get_object())

    @oa.extend_schema(responses=oa.OBJ)
    @action(pagination_class=None, detail=True, methods=['get'],
            url_path='serials-attendus', permission_classes=[IsAnyRole])
    def serials_attendus(self, request, pk=None):
        """Revue chantier 26/10/2026 — séries ATTENDUES (produits porteurs de
        série de la nomenclature gelée du chantier) face aux séries relevées
        (toutes interventions du chantier + parc déjà sérié). Contrat :
        ``contract_samples/intervention_serials_attendus.json``. Aucun
        prix."""
        from ..selectors import serials_attendus_intervention
        return Response(serials_attendus_intervention(self.get_object()))

    @oa.extend_schema(
        request=oa.body(
            'AjouterSerialRequete',  # textes sans NUL : `texte_corps` les refuse (ENF11)
            client_op_id=oa.ChaineStricte(required=False, allow_blank=True),
            produit=oa.i(null=True),
            numero_serie=oa.ChaineStricte(required=False, allow_blank=True),
            designation=oa.ChaineStricte(required=False, allow_blank=True),
            slot=oa.ChaineStricte(required=False, allow_blank=True),
            caracteristiques=oa.Caracteristiques(required=False, allow_null=True),
            capture_source=oa.ChaineStricte(required=False, allow_blank=True),
            file=oa.serializers.FileField(required=False),
        ),
        responses={200: ComponentSerialSerializer, 201: ComponentSerialSerializer},
    )
    @action(parser_classes=oa.JSON_ET_MULTIPART_PARSERS, detail=True, methods=['post'], url_path='ajouter-serial',
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
        # ADEP44 — idempotence par `client_op_id` : le rejeu d'une op déjà
        # appliquée (en ligne OU par la synchro) renvoie l'objet existant,
        # AVANT toute autre garde (le doublon de série ne doit pas la bloquer).
        # api-fuzz-full 27/10 (ENF11) : champs texte TYPÉS (un fichier
        # multipart nommé `client_op_id` faisait lever `.strip()` → 500).
        op_id = oa.texte_corps(request, 'client_op_id', 'numero_serie',
                               'designation', 'slot', 'capture_source')
        try:
            memorise = field_sync.rejeu_op_en_ligne(
                company, op_id, 'intervention.serial')
        except field_sync.FieldOpError as exc:
            return Response({'client_op_id': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        if memorise is not None:
            existant = interv.serials.filter(
                pk=memorise.get('serial')).first()
            if existant is not None:
                data = ComponentSerialSerializer(
                    existant, context={'request': request}).data
                data['replayed'] = True
                return Response(data, status=status.HTTP_200_OK)
        produit = None
        produit_id = request.data.get('produit')
        if produit_id:
            produit = get_produit_scoped(company, produit_id)
            if produit is None:
                return Response({'produit': 'Produit inconnu.'},
                                status=status.HTTP_400_BAD_REQUEST)
        # Revue chantier 26/10/2026 — un relevé nomme son composant (produit
        # catalogue, ou à défaut une désignation) ; caractéristiques de
        # plaque validées ; source de capture (scan | saisie | photo).
        champs, refus = field_capture.champs_releve_serie(
            produit, request.data)
        if refus:  # api-fuzz-full 27/10 (ENF11) : ni produit ni désignation → 409
            return Response(refus, status=oa.statut_refus_releve(refus))
        numero = (request.data.get('numero_serie') or '').strip()
        # ACHT37 — doublon refusé dès la saisie (plus de 500 au push parc).
        raison = field_capture.raison_serie_en_double(company, numero)
        if raison:  # doublon (relevé ou parc SAV) : refus d'ÉTAT, 409 (ENF11)
            return Response({'numero_serie': raison},
                            status=status.HTTP_409_CONFLICT)
        serie_ocr = False
        plaque = None
        file = request.FILES.get('file')
        if file is not None:
            # AUD311 (SCA42) — cle scopee societe (voir ajouter_photo).
            meta, err = store_attachment(file, company=company)
            if err:  # api-fuzz-full 27/10 (ENF11) : format hors schéma → 409
                return Response({'detail': err},
                                status=status.HTTP_409_CONFLICT)
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
                    champs['capture_source'] = 'photo'
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                serial = ComponentSerial.objects.create(
                    company=company, intervention=interv, produit=produit,
                    designation=champs['designation'],
                    slot_cle=(request.data.get('slot') or '').strip(),
                    numero_serie=numero, plaque_attachment=plaque,
                    serie_ocr=serie_ocr,
                    caracteristiques=champs['caracteristiques'],
                    capture_source=champs['capture_source'],
                    created_by=request.user)
                field_sync.memoriser_op_en_ligne(
                    company, request.user, op_id, 'intervention.serial',
                    interv.id, {'serial': serial.id,
                                'numero_serie': serial.numero_serie})
        except IntegrityError:
            # Course sur la clé : le gagnant a déjà créé l'objet — on le rend.
            gagnant = field_sync.rejeu_op_en_ligne(
                company, op_id, 'intervention.serial')
            existant = interv.serials.filter(
                pk=(gagnant or {}).get('serial')).first()
            if existant is None:
                raise
            data = ComponentSerialSerializer(
                existant, context={'request': request}).data
            data['replayed'] = True
            return Response(data, status=status.HTTP_200_OK)
        field_capture.pousser_si_cloturee(interv, request.user)  # ACHT47
        data = ComponentSerialSerializer(
            serial, context={'request': request}).data
        if op_id:
            data['replayed'] = False
        return Response(data, status=status.HTTP_201_CREATED)

    @oa.extend_schema(
        request=oa.body('ModifierSerialRequete', serial=oa.i(True), numero_serie=oa.s(), designation=oa.s()),
        responses=ComponentSerialSerializer,
    )
    @action(detail=True, methods=['post'], url_path='modifier-serial',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_serial(self, request, pk=None):
        """F9 — édite un n° de série relevé. Corps : serial, numero_serie,
        [designation]."""
        interv = self.get_object()
        serial = interv.serials.filter(id=oa.id_ou_none(request.data.get('serial'))).first()
        if serial is None:  # api-fuzz-full 27/10 (ENF11) : id entier absent → 404
            return Response({'detail': 'Relevé inconnu.'},
                            status=oa.statut_inconnu(request.data.get('serial')))
        # ACHT37 — un relevé déjà poussé au parc ne se corrige plus ici.
        if serial.pousse_parc:
            return Response({'detail': field_capture.MESSAGE_SERIE_AU_PARC},
                            status=status.HTTP_409_CONFLICT)
        fields = []
        if 'numero_serie' in request.data:
            nouveau = (request.data.get('numero_serie') or '').strip()
            raison = field_capture.raison_serie_en_double(
                interv.company, nouveau, exclude_id=serial.pk)
            if raison:  # doublon : refus d'ÉTAT, 409 (ENF11)
                return Response({'numero_serie': raison},
                                status=status.HTTP_409_CONFLICT)
            serial.numero_serie = nouveau
            serial.serie_ocr = False
            fields += ['numero_serie', 'serie_ocr']
        if 'designation' in request.data:
            serial.designation = (request.data.get('designation') or '').strip()
            fields.append('designation')
        if 'caracteristiques' in request.data:
            propre, erreur = field_capture.valider_caracteristiques(
                request.data.get('caracteristiques'))
            if erreur:
                return Response({'caracteristiques': erreur},
                                status=status.HTTP_400_BAD_REQUEST)
            serial.caracteristiques = propre
            fields.append('caracteristiques')
        if fields:
            serial.save(update_fields=fields)
        return Response(ComponentSerialSerializer(
            serial, context={'request': request}).data)

    @oa.extend_schema(request=oa.body('SupprimerSerialRequete', serial=oa.i(True)), responses={204: None})
    @action(detail=True, methods=['post'], url_path='supprimer-serial',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_serial(self, request, pk=None):
        """F9 — supprime un relevé de n° de série. Corps : {"serial": <id>}."""
        interv = self.get_object()
        serial = interv.serials.filter(id=oa.id_ou_none(request.data.get('serial'))).first()
        if serial is None:  # api-fuzz-full 27/10 (ENF11) : id entier absent → 404
            return Response({'detail': 'Relevé inconnu.'},
                            status=oa.statut_inconnu(request.data.get('serial')))
        if serial.pousse_parc:  # ACHT37
            return Response({'detail': field_capture.MESSAGE_SERIE_AU_PARC},
                            status=status.HTTP_409_CONFLICT)
        motif, refus = self._motif_suppression(interv)  # ACHT41
        if refus is not None:
            return refus
        numero = serial.numero_serie or '—'
        serial.delete()
        self._tracer_suppression(interv, f"N° de série {numero} supprimé", motif)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── F10 — annotation d'une photo (dessin + légende) ─────────────────────
    @oa.extend_schema(
        request=oa.body(
            'AnnoterPhotoRequete',
            photo=oa.i(True),
            drawing=oa.obj(null=True),
            caption=oa.s(),
            probleme=oa.b(),
        ),
        responses=PhotoAnnotationSerializer,
    )
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
            id=oa.id_ou_none(request.data.get('photo')), content_type=ct,
            object_id=interv.id, company=interv.company).first()
        if att is None:
            return Response({'detail': 'Photo inconnue.'},
                            status=oa.statut_inconnu(request.data.get('photo')))
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

    @oa.extend_schema(responses=MaterielConsommationSerializer)
    @action(detail=True, methods=['get'], url_path='consommation',
            permission_classes=[IsAnyRole])
    def consommation(self, request, pk=None):
        """F11 — réconciliation matériel : prévu (nomenclature) vs réellement
        utilisé, lignes hors-nomenclature, variances + dépassements (F12)."""
        return self._consommation_response(self.get_object())

    @oa.extend_schema(
        request=oa.body(
            'AjouterLigneConsommationRequete',
            designation=oa.designation_ligne(),
            produit=oa.i(null=True),
            quantite_utilisee=oa.qte(),
            justification=oa.s(),
        ),
        responses={201: ConsommationLigneSerializer},
    )
    @action(detail=True, methods=['post'], url_path='ajouter-ligne-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_ligne_consommation(self, request, pk=None):
        """F11 — ajoute une ligne hors-nomenclature (câble, vis, MC4…). Corps :
        designation, quantite_utilisee, [produit], [justification]."""
        from apps.stock.selectors import get_produit_scoped
        interv = self.get_object()
        # ACHT30 — garde commune avec la synchro terrain.
        if not field_capture.consommation_modifiable(
                getattr(interv, 'consommation', None)):
            return Response(
                {'detail': field_capture.MESSAGE_CONSOMMATION_VALIDEE},
                status=status.HTTP_400_BAD_REQUEST)
        cons = field_capture.ensure_consommation(interv)
        # api-fuzz-full 27/10 (ENF11) : `designation` obligatoire PUBLIÉE et
        # validée par le même champ (non blanche, sans NUL, ≤ 255) — 400 dans
        # l'enveloppe commune ; un NUL ou une valeur non textuelle faisait 500.
        designation = oa.corps_valide(
            oa.DesignationLigneRequete, request)['designation']
        produit_id = oa.id_corps(request, 'produit')  # liste/objet → 400, plus 500
        produit = get_produit_scoped(interv.company, produit_id) if produit_id else None
        from decimal import Decimal
        qte = oa.quantite_bornee(request, 'quantite_utilisee')  # (12, 2) : 1e15 → 500
        ligne = ConsommationLigne.objects.create(
            company=interv.company, consommation=cons, produit=produit,
            designation=designation, quantite_prevue=Decimal('0'),
            quantite_utilisee=qte, hors_nomenclature=True,
            justification=oa.texte_corps(request, 'justification'),
            ordre=cons.lignes.count())
        return Response(ConsommationLigneSerializer(ligne).data,
                        status=status.HTTP_201_CREATED)

    @oa.extend_schema(
        request=oa.body(
            'ModifierLigneConsommationRequete',
            ligne=oa.i(True),
            quantite_utilisee=oa.qte(),
            justification=oa.s(),
            justification_memo=oa.i(null=True),
        ),
        responses=ConsommationLigneSerializer,
    )
    @action(detail=True, methods=['post'],
            url_path='modifier-ligne-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_ligne_consommation(self, request, pk=None):
        """F11 — édite une ligne : quantite_utilisee, justification,
        justification_memo. Corps : {"ligne": <id>, ...}."""
        interv = self.get_object()
        cons = field_capture.ensure_consommation(interv)
        if not field_capture.consommation_modifiable(cons):  # ACHT30
            return Response(
                {'detail': field_capture.MESSAGE_CONSOMMATION_VALIDEE},
                status=status.HTTP_400_BAD_REQUEST)
        ligne = cons.lignes.filter(id=oa.id_ou_none(request.data.get('ligne'))).first()
        if ligne is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=oa.statut_inconnu(request.data.get('ligne')))
        fields = []
        if 'quantite_utilisee' in request.data:
            ligne.quantite_utilisee = oa.quantite_bornee(request, 'quantite_utilisee')
            fields.append('quantite_utilisee')
        if 'justification' in request.data:
            ligne.justification = (request.data.get('justification') or '').strip()
            fields.append('justification')
        if 'justification_memo' in request.data:
            memo = interv.voice_memos.filter(
                id=oa.id_ou_none(request.data.get('justification_memo'))).first()
            ligne.justification_memo = memo
            fields.append('justification_memo')
        if fields:
            # ACHT32 — `auto_now` ne joue qu'avec le champ dans update_fields.
            ligne.save(update_fields=fields + ['date_modification'])
        return Response(ConsommationLigneSerializer(ligne).data)

    @oa.extend_schema(request=oa.body('SupprimerLigneConsommationRequete', ligne=oa.i(True)), responses={204: None})
    @action(detail=True, methods=['post'],
            url_path='supprimer-ligne-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_ligne_consommation(self, request, pk=None):
        """F11 — supprime une ligne HORS-nomenclature. Corps : {"ligne": <id>}."""
        interv = self.get_object()
        cons = field_capture.ensure_consommation(interv)
        if not field_capture.consommation_modifiable(cons):  # ACHT30
            return Response(
                {'detail': field_capture.MESSAGE_CONSOMMATION_VALIDEE},
                status=status.HTTP_400_BAD_REQUEST)
        # api-fuzz-full 27/10 (ENF11) : ligne inconnue → 404 (id entier) ;
        # ligne de la nomenclature = refus d'ÉTAT → 409 (les deux faisaient 400).
        ligne = cons.lignes.filter(id=oa.id_ou_none(request.data.get('ligne'))).first()
        if ligne is None or not ligne.hors_nomenclature:
            return Response(
                {'detail': 'Ligne inconnue.' if ligne is None else
                 'Seules les lignes hors-nomenclature sont supprimables.'},
                status=oa.statut_ligne_non_supprimable(
                    ligne, request.data.get('ligne')))
        motif, refus = self._motif_suppression(interv)  # ACHT41
        if refus is not None:
            return refus
        designation = ligne.designation
        ligne.delete()
        self._tracer_suppression(
            interv, f"Ligne de consommation {designation} supprimée", motif)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @oa.extend_schema(request=None, responses=MaterielConsommationSerializer)
    @action(detail=True, methods=['post'], url_path='valider-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def valider_consommation(self, request, pk=None):
        """F11 — valide la réconciliation : la consommation RÉELLE pilote les
        mouvements de stock (et la marge job-costing). Refuse si une variance
        n'est pas justifiée (texte ou mémo vocal)."""
        interv = self.get_object()
        cons = field_capture.ensure_consommation(interv)
        if not field_capture.consommation_modifiable(cons):  # ACHT30
            return Response(
                {'detail': field_capture.MESSAGE_CONSOMMATION_VALIDEE},
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
    @oa.extend_schema(
        parameters=[oa.qs('type_intervention', required=True,
                          pattern=MOTIF_NON_BLANC_SANS_NUL),
                    oa.qidv('technicien'),
                    oa.qs('type_installation', pattern=MOTIF_SANS_NUL)],
        responses=oa.OBJ,
    )
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
        # api-fuzz full : un caractère nul fait lever le pilote Postgres (500).
        type_intervention = oa.texte_requete(request, 'type_intervention')
        type_installation = oa.texte_requete(request, 'type_installation')
        if not non_blanc(type_intervention or ''):  # ERR-ENF11 : blanc = absent
            return Response(
                {'detail': 'type_intervention est requis.'}, status=400)
        technicien = None
        technicien_id = oa.id_requete(request, 'technicien')  # ERR-ENF11 : `abc` → 400
        if technicien_id:
            from authentication.models import CustomUser
            technicien = CustomUser.objects.filter(
                id=technicien_id, company=company).first()
        duree = suggestion_duree_intervention(
            company, type_intervention, technicien=technicien)
        pieces = suggestion_pieces_intervention(
            company, type_intervention,
            type_installation=type_installation)
        return Response({'duree': duree, 'pieces': pieces})

    @oa.extend_schema(responses=oa.OBJ)
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
    @oa.extend_schema(responses=VoiceMemoSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='memos',
            permission_classes=[IsAnyRole])
    def memos(self, request, pk=None):
        """F13 — mémos vocaux de l'intervention (audio + transcription F14)."""
        interv = self.get_object()
        return Response(VoiceMemoSerializer(
            interv.voice_memos.all(), many=True,
            context={'request': request}).data)

    @oa.extend_schema(
        request=oa.body('AjouterMemoRequete', file=oa.serializers.FileField(), cible=oa.s()),
        responses={201: VoiceMemoSerializer},
    )
    @action(parser_classes=oa.UPLOAD_PARSERS, detail=True, methods=['post'], url_path='ajouter-memo',
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
        # AUD311 (SCA42) — cle scopee societe (voir ajouter_photo).
        meta, err = store_attachment(file, audio=True,
                                     company=interv.company)
        if err:  # api-fuzz-full 27/10 (ENF11) : format audio hors schéma → 409
            return Response({'detail': err},
                            status=status.HTTP_409_CONFLICT)
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

    @oa.extend_schema(
        request=oa.body('ModifierMemoRequete', memo=oa.i(True), transcript=oa.s()),
        responses=VoiceMemoSerializer,
    )
    @action(detail=True, methods=['post'], url_path='modifier-memo',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_memo(self, request, pk=None):
        """F14 — édite la transcription d'un mémo (l'audio reste source de
        vérité). Corps : {"memo": <id>, "transcript": str}."""
        interv = self.get_object()
        memo = interv.voice_memos.filter(id=oa.id_ou_none(request.data.get('memo'))).first()
        if memo is None:
            return Response({'detail': 'Mémo inconnu.'},
                            status=oa.statut_inconnu(request.data.get('memo')))
        if 'transcript' in request.data:
            memo.transcript = request.data.get('transcript') or ''
            memo.transcrit = True
            memo.save(update_fields=['transcript', 'transcrit'])
        return Response(VoiceMemoSerializer(
            memo, context={'request': request}).data)

    @oa.extend_schema(request=oa.body('SupprimerMemoRequete', memo=oa.i(True)), responses={204: None})
    @action(detail=True, methods=['post'], url_path='supprimer-memo',
            permission_classes=[IsResponsableOrAdmin])
    def supprimer_memo(self, request, pk=None):
        """F13 — supprime un mémo vocal (objet audio + enregistrement). Corps :
        {"memo": <id>}."""
        from apps.records.storage import delete_attachment
        interv = self.get_object()
        memo = interv.voice_memos.filter(id=oa.id_ou_none(request.data.get('memo'))).first()
        if memo is None:
            return Response({'detail': 'Mémo inconnu.'},
                            status=oa.statut_inconnu(request.data.get('memo')))
        motif, refus = self._motif_suppression(interv)  # ACHT41
        if refus is not None:
            return refus
        if memo.audio_id:
            delete_attachment(memo.audio.file_key)
            memo.audio.delete()
        memo.delete()
        self._tracer_suppression(interv, 'Mémo vocal supprimé', motif)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── F15 — temps d'équipe ─────────────────────────────────────────────────
    @oa.extend_schema(responses=oa.OBJ)
    @action(detail=True, methods=['get'], url_path='crew-time',
            permission_classes=[IsAnyRole])
    def crew_time(self, request, pk=None):
        """F15 — durée sur site + temps de trajet, et jours-homme dérivés."""
        interv = self.get_object()
        data = field_capture.crew_time(interv)
        data['labour_jours'] = field_capture.labour_days_for_intervention(interv)
        return Response(data)

    # ── ZFSM1 — gabarit de fiche d'intervention (relevé matérialisé) ─────────
    @oa.extend_schema(responses=oa.OBJ)
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

    @oa.extend_schema(
        request=oa.body('RenseignerFicheRequete', valeur_id=oa.i(True), valeur=oa.s()),
        responses=FicheInterventionReleveSerializer,
    )
    @action(detail=True, methods=['post'], url_path='renseigner-fiche',
            permission_classes=[IsResponsableOrAdmin])
    def renseigner_fiche(self, request, pk=None):
        """ZFSM1 — renseigne la valeur d'UN champ du relevé. Corps :
        {"valeur_id": <id>, "valeur": <str>}."""
        interv = self.get_object()
        releve = field_services.ensure_fiche_releve(interv)
        if releve is None:
            return Response({'detail': "Aucun gabarit pour ce type d'intervention."},
                            status=status.HTTP_409_CONFLICT)
        valeur_obj = releve.valeurs.filter(
            id=oa.id_ou_none(request.data.get('valeur_id'))).first()
        if valeur_obj is None:
            return Response({'detail': 'Champ de fiche inconnu.'},
                            status=oa.statut_inconnu(request.data.get('valeur_id')))
        valeur_obj.valeur = str(request.data.get('valeur', '') or '').strip()
        valeur_obj.renseigne_le = timezone.now()
        valeur_obj.save(update_fields=['valeur', 'renseigne_le'])
        return Response(FicheInterventionReleveSerializer(
            releve, context={'request': request}).data)

    # ── F16 — réserves (punch-list) ──────────────────────────────────────────
    @oa.extend_schema(responses=ReserveSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='reserves',
            permission_classes=[IsAnyRole])
    def reserves(self, request, pk=None):
        """F16 — réserves (punch-list) de l'intervention."""
        interv = self.get_object()
        return Response(ReserveSerializer(
            interv.reserves.all(), many=True,
            context={'request': request}).data)

    @oa.extend_schema(
        request=oa.AjouterReserveRequete,  # ERR-ENF11 : déclaration = validation
        responses={200: ReserveSerializer, 201: ReserveSerializer},
    )
    @action(detail=True, methods=['post'], url_path='ajouter-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_reserve(self, request, pk=None):
        """F16 — crée une réserve (description, photo, mémo, assigné). Peut
        engendrer une intervention de suivi OU un ticket SAV. Corps :
        description, [assignee], [photo], [memo], [creer_suivi], [creer_ticket]."""
        interv = self.get_object()
        company = interv.company
        corps = oa.corps_valide(oa.AjouterReserveRequete, request)
        # ADEP44 — idempotence par `client_op_id` (voir `ajouter_serial`).
        op_id = corps.get('client_op_id', '').strip()
        try:
            memorise = field_sync.rejeu_op_en_ligne(
                company, op_id, 'intervention.reserve')
        except field_sync.FieldOpError as exc:
            return Response({'client_op_id': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        if memorise is not None:
            existante = interv.reserves.filter(
                pk=memorise.get('reserve')).first()
            if existante is not None:
                data = ReserveSerializer(
                    existante, context={'request': request}).data
                data['replayed'] = True
                return Response(data, status=status.HTTP_200_OK)
        from authentication.models import CustomUser
        from apps.records.models import Attachment
        assignee = CustomUser.objects.filter(
            id=corps.get('assignee'), company=company).first()
        photo = Attachment.objects.filter(
            id=corps.get('photo'), company=company).first()
        memo = interv.voice_memos.filter(id=corps.get('memo')).first()
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                reserve = Reserve.objects.create(
                    company=company, intervention=interv,
                    description=corps['description'].strip(),
                    assignee=assignee, photo=photo, memo=memo,
                    created_by=request.user)
                field_sync.memoriser_op_en_ligne(
                    company, request.user, op_id, 'intervention.reserve',
                    interv.id, {'reserve': reserve.id})
        except IntegrityError:
            gagnante = field_sync.rejeu_op_en_ligne(
                company, op_id, 'intervention.reserve')
            existante = interv.reserves.filter(
                pk=(gagnante or {}).get('reserve')).first()
            if existante is None:
                raise
            data = ReserveSerializer(
                existante, context={'request': request}).data
            data['replayed'] = True
            return Response(data, status=status.HTTP_200_OK)
        # Suivi optionnel : intervention de suivi (même chantier) et/ou ticket.
        if corps.get('creer_suivi'):
            suivi = Intervention.objects.create(
                company=company, installation=interv.installation,
                type_intervention=Intervention.Type.CONTROLE,
                created_by=request.user)
            intervention_activity.log_creation(suivi, request.user)
            reserve.suivi_intervention = suivi
            reserve.save(update_fields=['suivi_intervention'])
        if corps.get('creer_ticket'):
            ticket = self._spawn_ticket_for_reserve(reserve, request.user)
            if ticket is not None:
                reserve.ticket = ticket
                reserve.save(update_fields=['ticket'])
        data = ReserveSerializer(reserve, context={'request': request}).data
        if op_id:
            data['replayed'] = False
        return Response(data, status=status.HTTP_201_CREATED)

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
    @oa.extend_schema(
        request=oa.body('EnregistrerReverificationRequete', seuil_alerte_pct=oa.f(min_value=0, max_value=oa.PCT_MAX)),
        responses={201: ReverificationMesureSerializer},
    )
    @action(detail=True, methods=['post'], url_path='enregistrer-reverification',
            permission_classes=[IsResponsableOrAdmin])
    def enregistrer_reverification_view(self, request, pk=None):
        """XFSM13 — enregistre une re-vérification IEC 62446-2 (points
        électriques comparés à la baseline de recette du chantier). Corps :
        {"isolement_mohm": ..., "continuite_terre_ohm": ...,
        "voc_par_string": {"A": 620.5, ...}, "observations": ...,
        ["seuil_alerte_pct"]}. Un dépassement du seuil crée une Reserve."""
        interv = self.get_object()
        seuil = oa.seuil_pct(request.data.get('seuil_alerte_pct'), 'seuil_alerte_pct')
        reverif = enregistrer_reverification(
            interv, request.data, user=request.user, seuil_alerte_pct=seuil)
        return Response(
            ReverificationMesureSerializer(reverif).data,
            status=status.HTTP_201_CREATED)

    @oa.extend_schema(responses=ReverificationMesureSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='reverifications',
            permission_classes=[IsAnyRole])
    def reverifications(self, request, pk=None):
        """XFSM13 — historique des re-vérifications de l'intervention."""
        interv = self.get_object()
        from ..models import ReverificationMesure
        qs = ReverificationMesure.objects.filter(
            intervention_id=interv.id).order_by('-date_creation')
        return Response(ReverificationMesureSerializer(qs, many=True).data)

    @oa.extend_schema(
        request=oa.body('ModifierReserveRequete', reserve=oa.i(True), description=oa.s(), assignee=oa.i(null=True)),
        responses=ReserveSerializer,
    )
    @action(detail=True, methods=['post'], url_path='modifier-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def modifier_reserve(self, request, pk=None):
        """F16 — édite une réserve (description, assignee). Corps : reserve, ..."""
        interv = self.get_object()
        reserve = interv.reserves.filter(id=oa.id_ou_none(request.data.get('reserve'))).first()
        if reserve is None:
            return Response({'detail': 'Réserve inconnue.'},
                            status=oa.statut_inconnu(request.data.get('reserve')))
        fields = []
        if 'description' in request.data:
            reserve.description = (request.data.get('description') or '').strip()
            fields.append('description')
        if 'assignee' in request.data:
            from authentication.models import CustomUser
            reserve.assignee = CustomUser.objects.filter(
                id=oa.id_ou_none(request.data.get('assignee')), company=interv.company).first()
            fields.append('assignee')
        if fields:
            reserve.save(update_fields=fields)
        return Response(ReserveSerializer(
            reserve, context={'request': request}).data)

    @oa.extend_schema(
        request=oa.body('ResoudreReserveRequete', reserve=oa.i(True),
                        statut=oa.choice(Reserve.Statut.values), resolution=oa.s()),
        responses=ReserveSerializer,
    )
    @action(detail=True, methods=['post'], url_path='resoudre-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def resoudre_reserve(self, request, pk=None):
        """F16 — résout (ou ré-ouvre) une réserve. Corps : reserve, resolution,
        [statut]."""
        interv = self.get_object()
        reserve = interv.reserves.filter(id=oa.id_ou_none(request.data.get('reserve'))).first()
        if reserve is None:
            return Response({'detail': 'Réserve inconnue.'},
                            status=oa.statut_inconnu(request.data.get('reserve')))
        statut = oa.choix_corps(request, 'statut', Reserve.Statut.values, Reserve.Statut.RESOLUE)
        reserve.statut = statut
        reserve.resolution = (request.data.get('resolution') or '').strip()
        reserve.resolue_le = (timezone.now()
                              if statut == Reserve.Statut.RESOLUE else None)
        reserve.save(update_fields=['statut', 'resolution', 'resolue_le'])
        return Response(ReserveSerializer(
            reserve, context={'request': request}).data)

    # ── XFSM18 — réserve → devis de réparation ──────────────────────────────
    @oa.extend_schema(
        request=oa.body('GenererDevisReserveRequete', reserve=oa.i(True)),
        responses={200: oa.OBJ, 201: oa.OBJ},
    )
    @action(detail=True, methods=['post'], url_path='generer-devis-reserve',
            permission_classes=[IsResponsableOrAdmin])
    def generer_devis_reserve(self, request, pk=None):
        """XFSM18 — génère un devis brouillon de réparation à partir d'une
        réserve (client du chantier résolu côté serveur, description
        pré-remplie). Idempotent : si la réserve porte déjà un
        `devis_repare_id`, le renvoie sans en créer un second. Corps :
        {"reserve": <id>}."""
        interv = self.get_object()
        reserve = interv.reserves.filter(id=oa.id_ou_none(request.data.get('reserve'))).first()
        if reserve is None:
            return Response({'detail': 'Réserve inconnue.'},
                            status=oa.statut_inconnu(request.data.get('reserve')))
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
    @oa.extend_schema(request=None, responses=oa.RETOUR_OUTILLAGE)
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
        # ACHT72 — lit les outils réellement SORTIS (statut « En
        # intervention ») que CETTE intervention n'a pas elle-même chargés.
        from apps.outillage.models import Outillage
        from ..models import PreparationOutilLigne
        ids = list(outil_ids)
        sortis_ici = set(PreparationOutilLigne.objects.filter(
            preparation__intervention=interv, coche=True, outil_id__in=ids
        ).values_list('outil_id', flat=True))
        sortis = list(Outillage.objects.filter(
            company=interv.company, id__in=ids,
            statut=Outillage.Statut.EN_INTERVENTION,
        ).exclude(id__in=sortis_ici).values_list('id', flat=True))
        if not sortis:
            return {}
        par_qui = {}
        for oid, iid in (PreparationOutilLigne.objects
                         .filter(company=interv.company, outil_id__in=sortis,
                                 coche=True)
                         .exclude(preparation__intervention=interv)
                         .order_by('id')
                         .values_list('outil_id',
                                      'preparation__intervention_id')):
            par_qui[oid] = iid
        for oid, iid in (ToolReturn.objects
                         .filter(company=interv.company, outil_id__in=sortis)
                         .exclude(intervention=interv).order_by('id')
                         .values_list('outil_id', 'intervention_id')):
            par_qui.setdefault(oid, iid)
        return {oid: par_qui.get(oid) for oid in sortis}

    def _tool_return_response(self, interv):
        # Amorce les lignes de retour depuis les outils de la préparation, de
        # façon IDEMPOTENTE (get_or_create) — pas de doublon même en course
        # (ERR81). Un outil déjà réservé sur une autre intervention non
        # confirmée est ÉCARTÉ (anti double-réservation, ERR82).
        prep = getattr(interv, 'preparation', None)
        conflicts = {}
        if prep is not None:
            existing = {tr.outil_id for tr in interv.tool_returns.all()}
            lignes = [ol for ol in prep.outils.all()
                      if ol.outil_id and ol.outil_id not in existing]
            wanted = [ol.outil_id for ol in lignes]
            conflicts = self._checkout_conflicts(interv, wanted)
            # ACHT72 — seules les lignes CHARGÉES (cochées) ont un retour à
            # suivre : un outil non chargé n'est jamais matérialisé.
            for outil_id in [ol.outil_id for ol in lignes if ol.coche]:
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

    @oa.extend_schema(
        request=oa.CocherToolReturnRequete,  # ERR-ENF11 : déclaration = validation
        responses=ToolReturnSerializer,
    )
    @action(detail=True, methods=['post'], url_path='cocher-tool-return',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_tool_return(self, request, pk=None):
        """F17 — marque un outil rendu/non rendu + emplacement de retour. Corps :
        {"ligne": <id>, "rendu": bool, "emplacement": <id|null>}."""
        interv = self.get_object()
        corps = oa.corps_valide(oa.CocherToolReturnRequete, request)
        self._tool_return_response(interv)
        tr = interv.tool_returns.filter(id=corps['ligne']).first()
        if tr is None:
            return Response({'detail': 'Ligne inconnue.'},
                            status=status.HTTP_404_NOT_FOUND)
        tr.rendu = corps['rendu']
        fields = ['rendu']
        if 'emplacement' in corps:
            from apps.stock.selectors import get_emplacement_scoped
            emp_id = corps['emplacement']
            tr.emplacement_retour = (
                get_emplacement_scoped(interv.company, emp_id)
                if emp_id else None)
            fields.append('emplacement_retour')
        tr.save(update_fields=fields)
        return Response(ToolReturnSerializer(tr).data)

    @oa.extend_schema(request=None, responses=oa.OBJ)
    @action(detail=True, methods=['post'], url_path='confirmer-tool-return',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_tool_return(self, request, pk=None):
        """F17 — confirme le retour d'outillage à la clôture : met à jour le
        statut + l'emplacement de chaque outil rendu (Disponible) et signale les
        non rendus (statut maintenu « En intervention »)."""
        from apps.outillage.models import Outillage
        interv = self.get_object()
        self._tool_return_response(interv)
        retours = list(interv.tool_returns.select_related('outil').all())
        # ACHT72 — une 2e confirmation périmée n'écrase jamais un retour plus
        # récent (outil repris par une autre intervention depuis).
        if retours and all(tr.confirme_le for tr in retours):
            return Response({'detail': 'Retour déjà confirmé.'},
                            status=status.HTTP_409_CONFLICT)
        prep = getattr(interv, 'preparation', None)
        charges = set(prep.outils.filter(coche=True).values_list(
            'outil_id', flat=True)) if prep is not None else set()
        non_rendus = []
        for tr in retours:
            outil = tr.outil
            if outil is None or tr.confirme_le:
                continue
            # ACHT72 — ne traite QUE les outils sortis par CETTE intervention :
            # jamais un outil non chargé, Perdu, En réparation ou disponible.
            if (outil.id not in charges
                    or outil.statut != Outillage.Statut.EN_INTERVENTION):
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
    @oa.extend_schema(responses=SafetySignoffSerializer)
    @action(detail=True, methods=['get'], url_path='safety',
            permission_classes=[IsAnyRole])
    def safety(self, request, pk=None):
        """F18 — sign-off des consignes de sécurité (checklist configurable)."""
        interv = self.get_object()
        signoff = field_capture.ensure_safety_signoff(interv)
        return Response(SafetySignoffSerializer(signoff).data)

    @oa.extend_schema(
        request=oa.body('CocherSafetyRequete', cle=oa.ChaineStricte(), coche=oa.b()),  # sans NUL (ENF11)
        responses=SafetySignoffSerializer,
    )
    @action(detail=True, methods=['post'], url_path='cocher-safety',
            permission_classes=[IsResponsableOrAdmin])
    def cocher_safety(self, request, pk=None):
        """F18 — coche/décoche un point de consigne, avec qui + quand. Corps :
        {"cle": <str>, "coche": bool}."""
        interv = self.get_object()
        signoff = field_capture.ensure_safety_signoff(interv)
        item = signoff.items.filter(cle=oa.texte_corps(request, 'cle')).first()  # NUL → 400, plus 500
        if item is None:
            return Response({'detail': 'Consigne inconnue.'},
                            status=oa.statut_inconnu(request.data.get('cle'), str))
        coche = bool(request.data.get('coche', True))
        item.coche = coche
        item.coche_par = request.user if coche else None
        item.coche_le = timezone.now() if coche else None
        item.save(update_fields=['coche', 'coche_par', 'coche_le'])
        return Response(SafetySignoffSerializer(signoff).data)

    @oa.extend_schema(request=None, responses=SafetySignoffSerializer)
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
    @oa.extend_schema(responses=oa.PDF)
    @action(detail=True, methods=['get'], url_path='compte-rendu',
            permission_classes=[IsAnyRole])
    def compte_rendu(self, request, pk=None):
        """F19 — compte-rendu d'intervention en PDF. F9 serials, F11 consommation
        avec justifications, F16 réserves, photos avant/pendant/après, bloc
        signature « Bon pour accord ». Client-facing : aucun prix d'achat."""
        from django.http import HttpResponse
        from .. import intervention_pdf
        interv = self.get_object()
        # ACHT37 — un GET n'écrit RIEN : la poussée des n° de série vers le
        # parc installé (F9) se fait à la clôture de l'intervention.
        pdf_bytes = intervention_pdf.compte_rendu_pdf(interv)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="compte-rendu-intervention-{interv.id}.pdf"')
        return resp

    # ── ZFSM2 — lien public tokenisé du compte-rendu signé ──────────────────
    @oa.extend_schema(responses=oa.OBJ)
    @action(detail=True, methods=['get'], url_path='lien-rapport',
            permission_classes=[IsResponsableOrAdmin])
    def lien_rapport(self, request, pk=None):
        """ZFSM2 — génère (lazily) et renvoie l'URL publique du compte-rendu
        signé de cette intervention, à partager par WhatsApp/SMS (pattern
        FG86/liens WhatsApp/XFSM7). Jeton DISTINCT du lien « en route ».

        WIR264 — même correction que `lien_client` : le `path` renvoyé était
        amputé de son préfixe `/api/django` et ne menait à aucune page. Il
        pointe désormais vers la PAGE publique
        `/intervention-rapport/<token>`."""
        interv = self.get_object()
        token = interv.ensure_lien_rapport_token()
        path = f'/intervention-rapport/{token}'
        return Response({
            'token': token,
            'path': path,
            'url': request.build_absolute_uri(path),
        })

    # ── ZFSM4 — facturation directe d'une intervention hors contrat ─────────
    @oa.extend_schema(request=None, responses={200: oa.OBJ, 201: oa.OBJ})
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
    @oa.extend_schema(request=None, responses={200: oa.OBJ, 201: oa.OBJ})
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
    @oa.extend_schema(responses=oa.OBJ)
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
    @oa.extend_schema(responses=oa.OBJ)
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
    @oa.extend_schema(
        # api-fuzz-full 27/10 (ENF11) : `date_prevue` est publiée comme une
        # DATE (AAAA-MM-JJ) — ce que `parser_date_rdv` accepte ; une chaîne
        # libre était déclarée conforme puis refusée en 400.
        request=oa.body('ConfirmerRdvRequete', confirme=oa.b(), date_prevue=oa.d(null=True),
                        motif=oa.ChaineStricte(required=False, allow_null=True, allow_blank=True)),
        responses=InterventionSerializer,
    )
    @action(detail=True, methods=['post'], url_path='confirmer-rdv',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_rdv(self, request, pk=None):
        """FG78 — marque le RDV client comme confirmé (ou le déconfirme si
        `confirme=false`). Incrémente `rdv_reschedule_count` quand une nouvelle
        date est fournie avec `date_prevue` (reschedule). Métadonnées only —
        ne touche JAMAIS le statut de l'intervention."""
        from ..services import replanifier
        interv = self.get_object()
        confirme, new_date, motif = oa.confirmation_rdv(request)  # ENF11 : types du corps → 400
        # ACHT38 — report via le service unique (date parsée AVANT toute
        # écriture : date invalide → 400 sous le champ, jamais de 500).
        is_reschedule = False
        # Absente/null = simple (dé)confirmation ; toute autre valeur doit être
        # une date (une chaîne vide n'en est pas une : 400, comme le schéma).
        if new_date is not None:
            try:
                is_reschedule = replanifier(
                    interv, new_date, motif,
                    request.user, confirme=confirme, trace=False)
            except ValueError as exc:
                return Response({'date_prevue': str(exc)},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            interv.rdv_confirme = confirme
            interv.rdv_confirme_le = timezone.now() if confirme else None
            interv.save(update_fields=['rdv_confirme', 'rdv_confirme_le'])
        msg = ("RDV confirmé." if confirme
               else "Confirmation RDV annulée.")
        if is_reschedule:
            msg += (f" Reporté au {interv.date_prevue} "
                    f"(reschedule #{interv.rdv_reschedule_count}).")
        intervention_activity.log_note(interv, request.user, msg)
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    # ── FG68 — calendrier dispatch techniciens ───────────────────────────────
    @oa.extend_schema(parameters=[oa.qdv('date_from'), oa.qdv('date_to')], responses=oa.LIST)
    @action(pagination_class=None, detail=False, methods=['get'], url_path='calendrier',
            permission_classes=[IsAnyRole])
    def calendrier(self, request):
        """FG68 — vue calendrier des interventions groupées par technicien.
        Params : date_from, date_to (YYYY-MM-DD). Renvoie une liste de
        techniciens avec leurs interventions prévues sur la plage. Les
        interventions sans technicien sont groupées sous la clé `non_assigne`."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        params = request.query_params
        date_from = date_ou_400(params.get('date_from'), 'date_from')
        date_to = date_ou_400(params.get('date_to'), 'date_to')
        # ACHT50 — part du queryset du viewset (société + portée de
        # visibilité Feature F) : un Technicien de portée équipe ne voit ici
        # que ce que sa liste lui montre.
        qs = self.get_queryset().filter(annulee=False)
        if date_from:
            qs = qs.filter(date_prevue__gte=date_from)
        if date_to:
            qs = qs.filter(date_prevue__lte=date_to)
        # AUD324 — le calendrier construisait son propre queryset SANS le
        # moindre prefetch, alors qu'il sérialise l'InterventionSerializer
        # complet : `equipe` (M2M), `preparation` (OneToOne inverse) et le
        # compte des réserves ouvertes tiraient chacun une requête PAR
        # intervention sur l'écran de dispatch le plus consulté.
        qs = qs.select_related(
            'technicien', 'installation', 'installation__client',
            'camionnette',
        ).order_by('date_prevue', 'id')  # prefetch_related(dispatch) déjà posé par get_queryset
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
    @oa.extend_schema(
        request=oa.body(
            'SignerInterventionRequete',
            signature_client=oa.signature_publiee(),
            signataire_nom=oa.ChaineStricte(required=False, allow_blank=True),
            motif_override_signature=oa.ChaineStricte(required=False, allow_blank=True),
            motif_override=oa.ChaineStricte(required=False, allow_blank=True),
        ),
        responses=InterventionSerializer,
    )
    @action(detail=True, methods=['post'], url_path='signer-client',
            permission_classes=[IsAnyRole])
    def signer_client(self, request, pk=None):
        """FG69 — enregistre la signature client sur une intervention.
        Corps : {"signature_client": <data_url_ou_vecteur>, "signataire_nom": <str>}.
        Pose `signe_le` côté serveur.

        ACHT28 — délègue au service unique `enregistrer_signature_intervention`
        (validation ADOC78, re-signature refusée en 409 sans
        `motif_override_signature`, champs suivis au chatter)."""
        from ..signature_validation import (
            SignatureRefusee, enregistrer_signature_intervention,
        )
        interv = self.get_object()
        # api-fuzz-full 27/10 : un NUL dans le nom / le motif atteignait le
        # chatter (PostgreSQL) → 500 ; textes stricts publiés et validés.
        nom = oa.texte_corps(request, 'signataire_nom', 'motif_override_signature', 'motif_override')
        motif = (request.data.get('motif_override_signature')
                 or request.data.get('motif_override') or '')
        try:
            enregistrer_signature_intervention(
                interv, request.user, request.data.get('signature_client'),
                nom=nom, motif=motif)
        except SignatureRefusee as exc:
            if exc.code == 'deja_signee':
                return Response({'detail': exc.message},
                                status=status.HTTP_409_CONFLICT)
            return Response({'signature_client': exc.message},
                            status=status.HTTP_400_BAD_REQUEST)
        intervention_activity.log_note(
            interv, request.user,
            f"Signature client enregistrée ({nom or 'anonyme'}).")
        return Response(InterventionSerializer(
            interv, context={'request': request}).data)

    # ── FG73 — tournée journalière du technicien (ordre géographique) ─────────
    @oa.extend_schema(parameters=[oa.qdv('date')], responses=oa.OBJ)
    @action(detail=False, methods=['get'], url_path='ma-tournee',
            permission_classes=[IsAnyRole])
    def ma_tournee(self, request):
        """FG73 — interventions de la journée du technicien authentifié,
        ordonnées géographiquement (plus proche voisin depuis le dépôt /
        position actuelle). Chaque arrêt inclut un lien « Itinéraire » Google Maps.
        Param optionnel : date (YYYY-MM-DD, défaut=aujourd'hui)."""
        from django.utils.timezone import localdate
        company = request.user.company
        jour = str(date_ou_400(request.query_params.get('date'), 'date')
                   or localdate())
        qs = (Intervention.objects.actives()  # ACHT51 — hors annulées
              .filter(company=company, technicien=request.user, date_prevue=jour)
              .select_related('installation', 'installation__client',
                              'technicien', 'camionnette')
              # AUD324 — mêmes préchargements que le kanban/le calendrier.
              .prefetch_related(*dispatch_prefetches()))
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
        # AUD324 (suite) — UN SEUL contexte pour toute la passe de
        # sérialisation. Le cache de shot-list mémoïsé par
        # `InterventionSerializer._shotlist` vit dans le contexte : un
        # dictionnaire neuf par arrêt le repartait de zéro, et « Ma tournée »
        # retirait donc une requête `ShotListSlot` PAR intervention (le seul
        # des trois écrans de dispatch resté en N+1).
        contexte = {'request': request}
        for iv in ordered:
            lat = iv.installation.gps_lat
            lng = iv.installation.gps_lng
            maps_link = None
            if lat and lng:
                maps_link = (
                    f'https://www.google.com/maps/dir/?api=1&destination='
                    f'{lat},{lng}')
            stops.append({
                **InterventionSerializer(iv, context=contexte).data,
                'itineraire_url': maps_link,
                # NTMOB21 — coordonnées du site exposées telles quelles (elles
                # étaient déjà encodées dans `itineraire_url`) : l'écran
                # « Ma journée » y lit le point où demander la météo du jour
                # plutôt que de disséquer une URL Google Maps.
                'site_lat': float(lat) if lat else None,
                'site_lng': float(lng) if lng else None,
            })
        return Response({'date': jour, 'stops': stops})

    # ── FG299 — plan de charge des équipes (capacité vs affecté) ─────────────
    @oa.extend_schema(
        parameters=[oa.qdv('debut'), oa.qdv('fin'),
                    oa.qnombre('heures_par_jour', mini=0, maxi=24)],
        responses=oa.OBJ_FENETRE)
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
        from .. import selectors

        debut, fin = oa.fenetre_semaine(request)
        heures = oa.nombre_requete(
            request, 'heures_par_jour', defaut=8.0, mini=0, maxi=24)
        data = selectors.plan_de_charge_equipes(
            request.user.company, debut, fin, heures_par_jour=heures)
        return Response(data)

    # ── FG300 — détection de conflits d'affectation (double-booking) ─────────
    @oa.extend_schema(parameters=[oa.qdv('debut'), oa.qdv('fin')], responses=oa.OBJ_FENETRE)
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
        from .. import selectors

        debut, fin = oa.fenetre_semaine(request)
        data = selectors.conflits_affectation(
            request.user.company, debut, fin)
        return Response(data)

    # ── FG301 — nivellement de charge (resource levelling) ───────────────────
    @oa.extend_schema(
        parameters=[oa.qdv('debut'), oa.qdv('fin'),
                    oa.qnombre('heures_par_jour', mini=0, maxi=24)],
        responses=oa.OBJ_FENETRE)
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
        from .. import selectors

        debut, fin = oa.fenetre_semaine(request)
        heures = oa.nombre_requete(
            request, 'heures_par_jour', defaut=8.0, mini=0, maxi=24)
        data = selectors.nivellement_charge(
            request.user.company, debut, fin, heures_par_jour=heures)
        return Response(data)

    # ── XFSM5 — KPI taux d'arrivée à l'heure (fenêtres de RDV promises) ──────
    @oa.extend_schema(parameters=[oa.qdv('debut'), oa.qdv('fin'), oa.qidv('technicien')], responses=oa.OBJ)
    @action(detail=False, methods=['get'], url_path='taux-ponctualite',
            permission_classes=[IsAnyRole])
    def taux_ponctualite(self, request):
        """XFSM5 — proportion des arrivées dans la fenêtre promise
        (`fenetre_debut`/`fenetre_fin`), calculée au check-in GPS F6. Filtrable
        par `debut`/`fin` (bornes de `arrivee_site_le`) et `technicien`."""
        from .. import selectors

        def _parse(value, nom='date'):  # ERR-ENF11 : date illisible = 400
            return date_ou_400(value, nom)

        params = request.query_params
        data = selectors.taux_ponctualite(
            request.user.company,
            debut=_parse(params.get('debut'), 'debut'),
            fin=_parse(params.get('fin'), 'fin'),
            technicien_id=oa.id_requete(request, 'technicien'))
        return Response(data)

    # ── XFSM2 — Assistant de planification (meilleur créneau + technicien) ──
    @oa.extend_schema(
        request=oa.SuggererCreneauRequete,  # ERR-ENF11 : déclaration = validation
        responses=oa.OBJ,
    )
    @action(detail=False, methods=['post'], url_path='suggerer-creneau',
            permission_classes=[IsAnyRole])
    def suggerer_creneau(self, request):
        """XFSM2 — les 3 meilleures propositions (technicien, date) pour un
        chantier/type/durée cible. Lecture seule, NE MUTE RIEN. Corps :
        {chantier, type_intervention, [duree_jours], [date_cible]}."""
        from .. import selectors

        corps = oa.corps_valide(oa.SuggererCreneauRequete, request)
        data = selectors.suggerer_creneau(
            request.user.company, chantier_id=corps['chantier'],
            type_intervention=corps['type_intervention'],
            duree_jours=corps['duree_jours'], date_cible=corps.get('date_cible'))
        return Response(data)

    # ── XFSM3 — Replanification en masse d'une journée ──────────────────────
    @oa.extend_schema(
        parameters=[oa.qb('simuler')],
        request=oa.ReplanifierEnMasseRequete,  # ERR-ENF11 : déclaration = validation
        responses=oa.OBJ,
    )
    @action(detail=False, methods=['post'], url_path='replanifier-en-masse',
            permission_classes=[IsResponsableOrAdmin,
                                DroitDeLaGrille('technicien_assign')])
    def replanifier_en_masse(self, request):
        """XFSM3 — re-slotte en UN appel les interventions d'un jour (toutes
        celles d'un `technicien` absent, et/ou une liste `intervention_ids`).
        `?simuler=1` (ou body `simuler`) ne mute rien — dry-run des
        propositions XFSM2. Sans dry-run, applique + trace FG78 + notifie.
        Corps : {jour, [technicien], [intervention_ids], [motif]}."""
        from .. import services

        corps = oa.corps_valide(oa.ReplanifierEnMasseRequete, request)
        jour = corps['jour']
        technicien_id = corps.get('technicien')
        intervention_ids = corps.get('intervention_ids')
        drapeau = oa.drapeau_requete(request, 'simuler')  # toujours validé
        simuler = corps['simuler'] or drapeau

        if simuler:
            data = services.previsualiser_replanification_masse(
                request.user.company, jour=jour, technicien_id=technicien_id,
                intervention_ids=intervention_ids)
            return Response(data)

        motif = corps.get('motif')
        data = services.appliquer_replanification_masse(
            request.user.company, jour=jour, motif=motif, user=request.user,
            technicien_id=technicien_id, intervention_ids=intervention_ids)
        return Response(data)

    # ── FG303 — planning des camionnettes (capacité véhicule) ────────────────
    @oa.extend_schema(parameters=[oa.qdv('debut'), oa.qdv('fin'), oa.qidv('capacite_jour')], responses=oa.OBJ_FENETRE)
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
        from .. import selectors

        debut, fin = oa.fenetre_semaine(request)
        # ERR-ENF11 : entier >= 1 strict (illisible → 400, absent/vide → 1).
        cap = oa.id_requete(request, 'capacite_jour') or 1
        data = selectors.planning_camionnettes(
            request.user.company, debut, fin, capacite_jour=cap)
        return Response(data)
