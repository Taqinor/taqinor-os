"""SPL81 — actions WhatsApp-devis et devis-auto de LeadViewSet
(``LeadDevisActionsMixin``), déplacées de ``views.py`` à corps inchangés
(move only). Module de ``apps/crm`` possédé par « devis »
(docs/ownership.yml). Règle n°4 : aucun code du moteur de devis touché ;
aucun statut de Devis lu ou écrit ici autrement qu'avant. Règle d'import :
ce module n'importe JAMAIS ``views.py``.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from . import activity
from . import schema_docs as sd
from .devis_auto import champs_manquants, message_manquants
from authentication.permissions import IsResponsableOrAdmin


def _refus_pii_whatsapp(request):
    """ACRM4 — le partage WhatsApp d'un devis rend le NUMÉRO du client
    (``phone``, ``wa_url``) : refusé 403 ``droit_manquant`` sans
    ``client_pii_voir``, exactement comme ``resume_associe``. ``None`` si
    l'appelant a le droit."""
    from .serializers import pii_masquee_pour
    if not pii_masquee_pour(request.user):
        return None
    return Response(
        {'detail': "Vous n'avez pas la permission de voir les coordonnées "
                   'du client.',
         'code': 'droit_manquant'},
        status=status.HTTP_403_FORBIDDEN)


class LeadDevisActionsMixin:
    """SPL81 — partage WhatsApp du devis (aperçu + envoi) et devis
    automatique depuis la fiche lead.

    ``get_permissions`` coopératif (patron SPL75) : il ne garde QUE ses
    actions, sinon ``super()`` (la chaîne finit sur ``_RepliIsAdminMixin``).
    """

    def get_permissions(self):
        if self.action in ('devis_auto', 'whatsapp_devis',
                           'whatsapp_devis_apercu'):
            return [IsResponsableOrAdmin()]
        return super().get_permissions()

    def _whatsapp_devis_message(self, request, lead, *, enregistrer):
        """Valide la sélection et construit le message multi-devis du lead.

        QJR538 — partagé par l'APERÇU (`whatsapp-devis-apercu`, sans aucun
        effet) et le COMMIT (`whatsapp-devis`). ``ShareLink.for_devis``
        réutilise le jeton : aperçu et commit portent le MÊME lien. Renvoie
        ``(Response d'erreur, None)`` ou ``(None, (devis_list, phone, message,
        links))``.
        """
        from apps.ventes.selectors import devis_for_lead
        from apps.ventes.utils.phone import normalize_phone_e164
        from apps.ventes.utils.whatsapp import build_devis_whatsapp

        from .fiche_bulk import coerce_id_list

        raw_ids = request.data.get('devis_ids') or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {'detail': 'Sélectionnez au moins un devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        try:
            ids = coerce_id_list(raw_ids)
        except ValueError:
            return Response(
                {'detail': 'Identifiant de devis invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        # Devis du lead, dans la société courante uniquement.
        devis_list = devis_for_lead(lead, ids)
        if len(devis_list) != len(set(ids)):
            return Response(
                {'detail': 'Un devis sélectionné est introuvable pour ce lead.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        phone = lead.whatsapp or lead.telephone
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        # QJR539 — garde de remise T17 (ventes.services) AVANT tout effet,
        # lien compris : un seul devis refusé refuse toute la sélection. Un
        # aperçu (``enregistrer=False``) n'écrit pas l'approbation implicite.
        from apps.ventes.services import (
            RemiseNonApprouvee, exiger_approbation_remise)
        for d in devis_list:
            if d.statut not in ('brouillon', 'envoye'):
                continue
            try:
                exiger_approbation_remise(
                    d, request.user, enregistrer=enregistrer)
            except RemiseNonApprouvee as erreur:
                return Response({'detail': erreur.message},
                                status=status.HTTP_400_BAD_REQUEST), None
        # Langue du message : la valeur explicite de la requête l'emporte ;
        # sinon on retombe sur la langue préférée du lead, puis sur le FR.
        langue = request.data.get('langue')
        if langue is None:
            langue = lead.langue_preferee or 'fr'
        message, links = build_devis_whatsapp(request, lead, devis_list, langue)
        return None, (devis_list, phone, message, links)

    @extend_schema(request=sd.corps('CrmWhatsappDevisApercuRequest', devis_ids=sd.ids_requis(), langue=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='whatsapp-devis-apercu',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_devis_apercu(self, request, pk=None):
        """QJR538 (contrat ``whatsapp_devis_apercu.json``) — APERÇU du message
        WhatsApp multi-devis, SANS AUCUN EFFET : ni ``mark_devis_sent``, ni
        AuditLog, ni note. Remplir le dialogue d'aperçu puis « Annuler » ne
        change donc ni le statut, ni la date d'envoi, ni le funnel."""
        from apps.ventes.utils.whatsapp import build_wa_url

        refus = _refus_pii_whatsapp(request)
        if refus is not None:
            return refus
        lead = self.get_object()
        erreur, built = self._whatsapp_devis_message(
            request, lead, enregistrer=False)
        if erreur is not None:
            return erreur
        _devis_list, phone, message, links = built
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'links': links,
        })

    @extend_schema(request=sd.corps('CrmWhatsappDevisRequest', devis_ids=sd.ids_requis(), langue=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='whatsapp-devis',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_devis(self, request, pk=None):
        """COMMIT du partage WhatsApp d'un/plusieurs devis du lead.

        Appelé par « Ouvrir WhatsApp » (QJR538) — jamais pour remplir
        l'aperçu (voir `whatsapp_devis_apercu`). N'envoie RIEN lui-même : le
        commercial appuie sur Envoyer dans WhatsApp. Chaque {lien} est un lien
        public tokenisé (30 j) vers le PDF CLIENT — jamais de prix d'achat ni
        de marge.
        """
        from apps.ventes.utils.whatsapp import build_wa_url

        refus = _refus_pii_whatsapp(request)
        if refus is not None:
            return refus
        lead = self.get_object()
        erreur, built = self._whatsapp_devis_message(
            request, lead, enregistrer=True)
        if erreur is not None:
            return erreur
        devis_list, phone, message, links = built
        # U4 — partager un devis au client le marque « envoyé » et fait avancer
        # le funnel (→ QUOTE_SENT). On passe par le service ventes (jamais une
        # écriture brute de statut) pour préserver la sémantique (règle #4) + le
        # chatter du devis ; l'avance du lead se fait via l'événement domaine
        # ``devis_sent``, comme ``devis_accepted``. Idempotent et ne dégrade
        # jamais un devis déjà accepté/refusé/envoyé.
        from apps.ventes.services import mark_devis_sent
        for d in devis_list:
            mark_devis_sent(devis=d, user=request.user)
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.WHATSAPP, instance=lead,
               detail=f'Lien WhatsApp devis préparé ({len(devis_list)})')
        # L856 — trace l'action dans le chatter du lead (Historique). Acteur et
        # société posés côté serveur, jamais lus du corps de la requête.
        refs = ', '.join(d.reference for d in devis_list)
        activity.log_note(
            lead, request.user,
            f'Lien WhatsApp généré pour {refs} '
            f'par {getattr(request.user, "username", "?")}.')
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'links': links,
        })

    @extend_schema(request=None, responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='devis-auto',
            permission_classes=[IsResponsableOrAdmin])
    def devis_auto(self, request, pk=None):
        """Garde serveur du devis automatique : le lead a-t-il les champs
        requis pour son mode ? Aucun effet de bord — la création du devis
        reste le flux générateur existant. Toute entrée UI appelle cette
        règle AVANT de lancer le générateur."""
        lead = self.get_object()
        manquants = champs_manquants(lead)
        if manquants:
            return Response({'detail': message_manquants(manquants)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'ok': True, 'detail': 'Lead prêt pour le devis automatique.'})
