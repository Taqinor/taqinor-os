"""SPL79 — visites : actions visite de LeadViewSet
(``LeadVisitesActionsMixin``) et AppointmentViewSet (+ ses aides de rendez-vous),
déplacés de ``views.py`` à l'identique (move only).

Nom ``visites_views.py`` (jamais views_visites.py : core/action_permission_scan
ne lit que ``*_views.py``) — à ne pas confondre avec ``apps/crm/visites.py``
(T-TRACE). Règle d'import : ce module n'importe JAMAIS ``views.py``.
"""
import logging

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from core.viewsets import CompanyScopedModelViewSet
from authentication.scoping import scope_queryset
from .models import Appointment, Lead, RelanceEtape
from .serializers import AppointmentSerializer
from .actions_crud import READ_ACTIONS
from .cadence_views import _prochaine_touche_publique
from . import activity
from . import schema_docs as sd
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin, HasPermissionOrLegacy

logger = logging.getLogger(__name__)


def _libelle_statut_rdv(statut):
    """ACRM23 — le libellé FR d'un statut de rendez-vous."""
    return dict(Appointment.Statut.choices).get(statut, statut or '—')


def _quand_rdv(quand):
    """ACRM23 — « JJ/MM/AAAA à HH:MM » (heure de Casablanca)."""
    if quand is None:
        return '—'
    from . import horaires
    return quand.astimezone(horaires.CASABLANCA).strftime('%d/%m/%Y à %H:%M')


def _noter_rdv(lead, user, corps):
    """ACRM23 — une ligne de chatter du lead pour un geste sur un RDV,
    l'acteur nommé (jamais un prénom en dur)."""
    if lead is None:
        return
    qui = getattr(user, 'username', '') or 'système'
    activity.log_note(lead, user, f'{corps} (par {qui}).')


@extend_schema_view(list=extend_schema(parameters=[sd.P_LEAD]))
class AppointmentViewSet(CompanyScopedModelViewSet):
    """QJ20 — Rendez-vous planifiés sur les leads (visites commerciales/techniques).

    Lecture tout rôle, écriture responsable/admin.
    Toujours scopé par société (TenantMixin). La société est posée côté serveur
    depuis l'utilisateur actif (jamais lue du corps de requête — multi-tenant).
    Filtre ?lead=<id> pour n'avoir que les RDV d'un lead donné.
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.select_related('lead', 'company').all()
    filterset_fields = ['lead', 'statut']
    ordering_fields = ['scheduled_at', 'date_creation']
    ordering = ['scheduled_at']

    def get_permissions(self):
        # VX245(a) — `ics` (téléchargement, lecture seule) rejoint les
        # READ_ACTIONS : tout rôle peut télécharger le `.ics` d'un RDV qu'il
        # peut déjà VOIR (queryset scopé société, jamais un nouveau droit).
        if self.action in READ_ACTIONS or self.action == 'ics':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        # ALEA27 — portée équipe/sous-arbre : seuls les RDV d'un lead dans la
        # portée (responsable visible) ou créés par un utilisateur visible.
        # Portée 'all' (admin) → inchangé.
        qs = scope_queryset(qs, self.request.user, ['lead__owner', 'created_by'])
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Company et created_by toujours posés côté serveur."""
        from .visites_rdv import book_appointment
        lead = serializer.validated_data['lead']
        scheduled_at = serializer.validated_data['scheduled_at']
        notes = serializer.validated_data.get('notes') or ''
        appt = book_appointment(
            lead=lead,
            scheduled_at=scheduled_at,
            notes=notes,
            user=self.request.user,
        )
        # The serializer's save() would create a duplicate — we bypass it here
        # and return the already-created appointment via the serializer for the
        # response. Patch self so the serializer picks up the instance.
        serializer.instance = appt

    def perform_update(self, serializer):
        """ACRM23 (C-ACRM-016) — l'annulation, le changement de statut et le
        DÉPLACEMENT d'un rendez-vous sont journalisés au chatter du lead
        (acteur + ancien → nouveau) ; un déplacement RÉARME le rappel
        (``reminder_sent=False``). Un PATCH qui ne change rien reste muet."""
        avant = serializer.instance
        ancien_statut = avant.statut
        ancien_quand = avant.scheduled_at
        ancien_lead_id = avant.lead_id
        rdv = serializer.save()
        changements = []
        if rdv.statut != ancien_statut:
            changements.append(
                f'{_libelle_statut_rdv(ancien_statut)} → '
                f'{_libelle_statut_rdv(rdv.statut)}')
        if rdv.scheduled_at != ancien_quand:
            changements.append(
                f'déplacé du {_quand_rdv(ancien_quand)} au '
                f'{_quand_rdv(rdv.scheduled_at)}')
            if rdv.reminder_sent:
                rdv.reminder_sent = False
                rdv.save(update_fields=['reminder_sent'])
        if changements and rdv.lead_id:
            _noter_rdv(rdv.lead, self.request.user,
                       f'RDV #{rdv.pk} : ' + ' ; '.join(changements))
        if rdv.lead_id and rdv.lead_id != ancien_lead_id and ancien_lead_id:
            _noter_rdv(Lead.objects.filter(pk=ancien_lead_id).first(),
                       self.request.user,
                       f'RDV #{rdv.pk} : rattaché à un autre lead')

    def perform_destroy(self, instance):
        """ACRM23 — la SUPPRESSION d'un rendez-vous est journalisée au
        chatter du lead (acteur, date du rendez-vous)."""
        lead = instance.lead
        pk, quand = instance.pk, instance.scheduled_at
        super().perform_destroy(instance)
        if lead is not None:
            _noter_rdv(lead, self.request.user,
                       f'RDV #{pk} du {_quand_rdv(quand)} : supprimé')

    @extend_schema(responses=sd.EXPORT_ICS)
    @action(detail=True, methods=['get'], url_path='ics')
    def ics(self, request, pk=None):
        """VX245(a) — `.ics` d'ÉVÉNEMENT UNIQUE pour CE rendez-vous (RFC 5545,
        1 VEVENT horodaté) — distinct du flux d'ABONNEMENT complet de
        `reporting.calendar.calendar_ics`. Réutilise la MÊME fonction pure
        `build_ics` (extraite pour être réutilisable, jamais une 2ᵉ
        implémentation ICS).

        Scopé société via `get_object()` (`CompanyScopedModelViewSet` — le
        RDV d'une autre société renvoie 404, jamais fabriqué)."""
        appt = self.get_object()
        from datetime import timedelta

        from django.http import HttpResponse

        from apps.reporting.calendar import build_ics

        lead_nom = f'{appt.lead.nom} {appt.lead.prenom or ""}'.strip()
        titre = f'RDV — {lead_nom}' if lead_nom else f'RDV #{appt.pk}'
        events = [{
            'uid': f'appointment-{appt.pk}',
            'start_dt': appt.scheduled_at,
            'end_dt': appt.scheduled_at + timedelta(hours=1),
            'summary': titre,
            'description': appt.notes or '',
        }]
        body = build_ics(request.user, events, calname=titre)
        resp = HttpResponse(body, content_type='text/calendar; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="rdv-{appt.pk}.ics"'
        return resp

    @extend_schema(request=None, responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='confirmer-whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_whatsapp(self, request, pk=None):
        """VX245(b) — aperçu du message de CONFIRMATION WhatsApp post-RDV
        (date/heure + lien `.ics`). N'ENVOIE RIEN : le commercial ouvre
        WhatsApp lui-même après avoir vérifié l'aperçu (même convention que
        `LeadViewSet.whatsapp_devis`)."""
        appt = self.get_object()
        from .visites_rdv import build_appointment_confirmation_whatsapp

        message, wa_url, ics_url = build_appointment_confirmation_whatsapp(
            request, appt)
        if wa_url is None:
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'message': message, 'wa_url': wa_url, 'ics_url': ics_url,
        })


class LeadVisitesActionsMixin:
    """SPL79 — actions visite de LeadViewSet (lecture des visites,
    planification, message de visite et son ouverture), déplacées de
    ``views.py`` à corps inchangés. ``locataire`` RESTE dans LeadViewSet.

    ``get_permissions`` coopératif (patron SPL75) : il ne garde QUE ses
    actions, sinon ``super()`` (la chaîne finit sur ``_RepliIsAdminMixin``).
    """

    def get_permissions(self):
        if self.action in ('visites', 'message_visite'):
            # VISITE-CADENCE — les deux LECTURES de la visite depuis la fiche
            # lead : sans cette garde elles retomberaient sur le
            # `[IsAdminRole()]` final — 403 pour la Commerciale, qui lit.
            return [HasPermissionOrLegacy('crm_voir')()]
        if self.action == 'planifier_visite':
            # VISITE-CADENCE — POSER un rendez-vous de visite est une
            # ÉCRITURE commerciale ordinaire (`crm_modifier`).
            return [HasPermissionOrLegacy('crm_modifier')()]
        if self.action == 'message_visite_ouvert':
            # CAD111 — journaliser l'ouverture du message de visite : une
            # ÉCRITURE commerciale (chatter), même garde que `whatsapp_devis`.
            return [IsResponsableOrAdmin()]
        return super().get_permissions()

    @extend_schema(responses=inline_serializer('CrmLeadVisites', {
        'visites': serializers.ListField(child=serializers.DictField()),
        'avertissement_sans_devis': serializers.CharField(),
        'rappel_juridique': serializers.CharField(),
    }))
    @action(detail=True, methods=['get'], url_path='visites',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def visites(self, request, pk=None):
        """Les visites techniques du lead, de la plus récente à la plus ancienne.

        CAD123 — plus l'AVERTISSEMENT (jamais un blocage) quand aucun devis
        n'est encore parti : la règle « la visite se propose après le devis »
        et son effet de bord juridique (CAD122), textes du serveur — deux
        chaînes vides sinon."""
        from apps.visites.selectors import visites_pour_lead

        from .cadence_visite import avertissement_visite

        lead = self.get_object()
        avertissement = avertissement_visite(lead)
        return Response({
            'visites': visites_pour_lead(lead),
            'avertissement_sans_devis': avertissement[
                'avertissement_sans_devis'],
            'rappel_juridique': avertissement['rappel_juridique'],
        })

    @extend_schema(request=sd.corps('CrmPlanifierVisiteRequest', commercial=serializers.IntegerField(required=False), date_prevue=serializers.CharField(), etape=serializers.CharField(required=False), note_etape=serializers.CharField(required=False), notes=serializers.CharField(required=False), replanifier=serializers.BooleanField(required=False)), responses=inline_serializer('CrmLeadVisitePlanifiee', {
        'visite': serializers.DictField(),
        'prochaine_touche': serializers.DictField(allow_null=True),
    }))
    @action(detail=True, methods=['post'], url_path='visites/planifier',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def planifier_visite(self, request, pk=None):
        """POSE un rendez-vous de visite technique sur ce lead.

        Corps : ``{date_prevue: 'AAAA-MM-JJ', commercial?: <id>, notes?,
        replanifier?, etape?, note_etape?}``. Chaque refus NOMME son champ
        (règle fondateur 08/09/2026) : jamais un « non enregistré » générique.

        L'écriture elle-même vit dans ``apps.visites.services.planifier_visite``
        — la visite appartient à cette app, le CRM ne fait que la lui demander.
        Les effets de bord (cadence recalée, chatter, notification à l'assigné)
        naissent de l'événement ``visite_planifiee``, pas d'ici.

        SUIVI E18 (30/09/2026) — la planification CLÔT la touche qui l'a
        demandée : ``etape`` (une touche de CE lead) et ``note_etape`` ; après
        la planification réussie, la touche encore à faire est close
        « visite acceptée » (``services.clore_etape_apres_planification``).
        ``replanifier`` DÉPLACE le rendez-vous en attente (SUIVI E5). La
        réponse porte aussi ``prochaine_touche`` (forme E9, ou ``null``).
        """
        from django.utils.dateparse import parse_date

        from apps.visites.selectors import ligne_visite_pour_lead
        from apps.visites.services import planifier_visite

        from .cadence_visite import clore_etape_apres_planification
        from .cadence_plan import _prochaine_touche_a_faire

        lead = self.get_object()
        brut = (request.data.get('date_prevue') or '').strip()
        date_prevue = parse_date(brut) if brut else None
        if brut and date_prevue is None:
            return Response(
                {'date_prevue': ['Date illisible (format AAAA-MM-JJ '
                                 'attendu).']},
                status=status.HTTP_400_BAD_REQUEST)

        commercial = None
        brut_commercial = request.data.get('commercial')
        if brut_commercial not in (None, '', 0):
            from django.contrib.auth import get_user_model
            # Borné à la SOCIÉTÉ de l'appelant : un id d'un autre locataire est
            # indiscernable d'un id inconnu (on ne confirme pas son existence).
            commercial = (get_user_model().objects
                          .filter(pk=brut_commercial,
                                  company=request.user.company)
                          .first())
            if commercial is None:
                return Response(
                    {'commercial': ['Utilisateur inconnu dans votre '
                                    'société.']},
                    status=status.HTTP_400_BAD_REQUEST)

        # SUIVI E18 — la touche qui a demandé la planification : une touche
        # de CE lead (donc de la société de l'appelant, ``get_object`` étant
        # borné), vérifiée AVANT toute écriture.
        etape = None
        brut_etape = request.data.get('etape')
        if brut_etape not in (None, '', 0):
            if str(brut_etape).isdigit():
                etape = lead.relance_etapes.filter(pk=int(brut_etape)).first()
            if etape is None:
                return Response(
                    {'etape': ['Étape de relance inconnue sur ce lead.']},
                    status=status.HTTP_400_BAD_REQUEST)
        replanifier = request.data.get('replanifier') in (
            True, 'true', 'True', '1', 1)
        # COCKPIT-CONTRÔLE B8 — l'échéance que la touche avait au moment où on
        # la TRAITE, lue AVANT la planification : celle-ci décale le suivi
        # pendant (donc cette touche) jusqu'après la visite.
        echeance_avant = (None if etape is None else
                          (etape.due_at, etape.due_date, etape.due_initial_at))

        visite, erreurs = planifier_visite(
            lead, request.user, date_prevue, commercial=commercial,
            notes=(request.data.get('notes') or ''), replanifier=replanifier)
        if erreurs:
            return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)
        if etape is not None:
            clore_etape_apres_planification(
                etape, request.user,
                note=(request.data.get('note_etape') or ''),
                echeance_avant=echeance_avant)
        return Response({'visite': ligne_visite_pour_lead(visite),
                         'prochaine_touche': _prochaine_touche_publique(
                             _prochaine_touche_a_faire(lead))},
                        status=status.HTTP_201_CREATED)

    @extend_schema(parameters=[sd.P_CLE], responses=inline_serializer('CrmLeadMessageVisite', {
        'corps_fr': serializers.CharField(),
        'corps_darija': serializers.CharField(),
    }))
    @action(detail=True, methods=['get'], url_path='message-visite',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def message_visite(self, request, pk=None):
        """Le message de visite à copier-coller, rendu côté serveur.

        ``?cle=visite_proposition|visite_confirmation``. MÊME machinerie que
        les messages de cadence : ``{conseiller}`` est le RESPONSABLE du lead
        (jamais un prénom codé en dur), et une phrase dont le placeholder n'a
        pas de valeur réelle est OMISE — un lead sans date de visite ne reçoit
        donc pas « la visite prévue  chez vous ».

        LECTURE PURE : le serveur REND, il n'ENVOIE pas (décision D5).
        """
        from .serializers import pii_masquee_pour
        from .cadence_messages import cles_message_visite_du_lead, message_visite_pour_lead

        cle = (request.query_params.get('cle') or '').strip()
        lead = self.get_object()
        # CAD111 — les liens wa.me sont construits ICI (E.164) ; un rôle sans
        # `client_pii_voir` ne reçoit aucun numéro (liens nuls, `phone` vide).
        # AGR526 — `dossier_fda` / `dossier_8221` seulement pour le lead dont
        # le playbook de segment les confirme.
        rendu = message_visite_pour_lead(
            lead, cle, user=request.user,
            masquer_numero=pii_masquee_pour(request.user))
        if rendu is None:
            return Response(
                {'cle': ['Message de visite inconnu « ' + cle + ' ». Clés '
                         'connues : '
                         + ', '.join(cles_message_visite_du_lead(lead)) + '.']},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(rendu)

    @extend_schema(request=sd.corps('CrmMessageVisiteOuvertRequest', cle=serializers.CharField(), etape=serializers.CharField(required=False), langue=serializers.CharField(required=False)), responses=inline_serializer('CrmMessageVisiteOuvert', {
        'journalise': serializers.BooleanField(),
        'cle': serializers.CharField(),
        'langue': serializers.CharField(),
        'etape': serializers.IntegerField(allow_null=True),
    }))
    @action(detail=True, methods=['post'], url_path='message-visite/ouvert',
            permission_classes=[IsResponsableOrAdmin])
    def message_visite_ouvert(self, request, pk=None):
        """CAD111 — le message de VISITE vient d'être OUVERT dans WhatsApp.

        Jumeau POST de la lecture ``message-visite`` (même patron que la
        touche : ``window.open`` d'abord, puis cet appel best-effort). Corps :
        ``{cle, langue, etape?}``. Journalise « WhatsApp ouvert » au chatter
        (tentative + premier contact + AuditLog) — JAMAIS « fait » : aucune
        issue, aucune touche avancée. ``etape`` (une touche à faire de CE lead)
        rattache l'ouverture à la touche, que son panneau « Fait » reconnaît.
        Refus 400 nommant le champ (``cle``, ``langue``, ``etape``)."""
        from .cadence_messages import (
            LANGUES_MESSAGE_VISITE,
            cle_message_visite_autorisee,
            cles_message_visite_du_lead,
            journaliser_message_visite_ouvert,
        )
        lead = self.get_object()
        cle = (request.data.get('cle') or '').strip()
        # AGR526 — mêmes clés que la lecture `message-visite` pour CE lead.
        if not cle_message_visite_autorisee(lead, cle):
            raise DRFValidationError({'erreurs': {'cle': (
                f'« Message de visite » inconnu : « {cle} ». Clés connues : '
                + ', '.join(cles_message_visite_du_lead(lead)) + '.')}})
        langue = (request.data.get('langue') or 'fr').strip()
        if langue not in LANGUES_MESSAGE_VISITE:
            raise DRFValidationError({'erreurs': {'langue': (
                f'« Langue du message » inconnue : « {langue} ». Langues : '
                + ', '.join(LANGUES_MESSAGE_VISITE) + '.')}})
        etape = None
        brut = str(request.data.get('etape') or '').strip()
        if brut:
            if brut.isdigit():
                etape = (RelanceEtape.objects
                         .filter(pk=int(brut), lead=lead, company=lead.company,
                                 statut=RelanceEtape.Statut.A_FAIRE)
                         .first())
            if etape is None:
                raise DRFValidationError({'erreurs': {'etape': (
                    '« Touche » : aucune touche à faire de ce lead ne porte '
                    f'l’identifiant « {brut} ».')}})
        journaliser_message_visite_ouvert(
            lead, request.user, cle=cle, langue=langue, etape=etape)
        try:
            from apps.audit.models import AuditLog
            from apps.audit.recorder import record
            record(AuditLog.Action.WHATSAPP, instance=lead,
                   detail=f'Message de visite ouvert ({cle})')
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('CAD111: AuditLog non écrit (lead #%s)', lead.pk,
                           exc_info=True)
        return Response({'journalise': True, 'cle': cle, 'langue': langue,
                         'etape': etape.pk if etape is not None else None})
