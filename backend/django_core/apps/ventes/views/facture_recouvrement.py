"""RECOUVREMENT d'une facture (VNT100, déplacé tel quel de
``views/facture.py``) : relances, aperçu, exclusion, journaux d'e-mails,
historique (``FactureRecouvrementActionsMixin``)."""

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from . import openapi_docs as D
from ..models import RelanceLog
from ..serializers import EmailLogSerializer
from ..serializers_facturation import (
    FactureActivitySerializer,
    FactureSerializer,
    RelanceLogSerializer,
    RelancerFactureSerializer,
)


class FactureRecouvrementActionsMixin:
    """Actions de ``FactureViewSet`` (mixin, aucune base)."""

    @extend_schema(request=RelancerFactureSerializer,
                   responses=D.FactureRelancee)
    @action(detail=True, methods=['post'], url_path='relancer',
            permission_classes=[IsResponsableOrAdmin])
    def relancer(self, request, pk=None):
        """Consigne une relance — l'envoi d'email est un OPT-IN explicite.

        AUD129 (PAY-4) : l'envoi était le DÉFAUT (``envoyer_email`` non fourni
        ⇒ email parti) alors que la modale annonce « Cette action journalise la
        relance (aucun envoi) » et que le lot poste ``{niveau}`` seul — une
        consignation en lot expédiait donc de vraies mises en demeure. Le
        défaut est désormais FALSE : il faut poster ``envoyer_email=true``
        (case « Envoyer l'email au client ») pour qu'un email parte.

        AUD129 (PAY-19) : le corps de l'email reprend la note saisie quand elle
        est renseignée (``note or lvl.message``) — elle n'était jusqu'ici
        écrite que dans le journal interne et perdue pour le destinataire.

        AUD131 (PAY-18) : l'action ne vérifiait NI ``statut`` NI ``montant_du``,
        alors que le cron exclut payee/annulee/brouillon — une facture déjà
        payée pouvait recevoir une mise en demeure. Elle partage désormais LE
        prédicat ``recouvrement.facture_relancable`` avec la liste des impayés
        et le beat, et son corps est validé par un serializer (un ``niveau``
        inexistant ou une ``prochaine_relance`` non-date ⇒ 400, plus jamais une
        relance consignée à vide ni une erreur base).

        Journalise une RelanceLog + fixe la prochaine date de relance. L'envoi
        passe par l'intégration configurable : NO-OP réseau sans clé (backend
        console), envoi réel via Brevo/SMTP quand configuré."""
        from ..recouvrement import (
            ensure_default_followup_levels, facture_relancable,
        )
        facture = self.get_object()
        # AUD131 — garde d'état AVANT toute écriture.
        ok, motif = facture_relancable(facture)
        if not ok:
            return Response({'detail': motif},
                            status=status.HTTP_400_BAD_REQUEST)
        # Fondateur 05/10/2026 — les 3 niveaux par défaut existent toujours
        # (créés seulement si la société n'en a aucun) : le `niveau` posté
        # (ORDRE, cf. RelancerFactureSerializer) se résout donc toujours.
        ensure_default_followup_levels(facture.company)

        payload = RelancerFactureSerializer(
            data=request.data, context={'company': facture.company})
        payload.is_valid(raise_exception=True)
        donnees = payload.validated_data

        niveau = donnees.get('niveau')
        note = (donnees.get('note') or '').strip()
        lvl = payload.context.get('followup_level')
        if niveau is None and lvl is None:
            # AFAC46 — sans niveau choisi, LE prochain niveau de la cadence
            # (le même que l'aperçu et le beat), jamais une relance hors
            # séquence.
            from ..domain.recouvrement import prochain_niveau
            lvl, _tous = prochain_niveau(facture)
            niveau = lvl.ordre if lvl is not None else None
        niveau_nom = lvl.nom if lvl is not None else ''
        RelanceLog.objects.create(
            company=facture.company, facture=facture,
            niveau=niveau or None, niveau_nom=niveau_nom, note=note,
            created_by=request.user)
        # AUD129 — envoi d'email en OPT-IN explicite (défaut : ne rien envoyer).
        # NO-OP réseau sans clé configurée.
        email_log_id = None
        if donnees.get('envoyer_email'):
            from ..email_service import send_relance_email
            # AUD129 (PAY-19) — la note saisie prime sur le message générique
            # du niveau : sinon la personnalisation n'atteint jamais le client.
            email_log = send_relance_email(
                facture, niveau_nom=niveau_nom,
                message=(note or (lvl.message if lvl is not None else '')),
                user=request.user)
            email_log_id = email_log.id
        # Prochaine relance proposée si fournie, sinon laissée telle quelle.
        prochaine = donnees.get('prochaine_relance')
        if prochaine:
            facture.prochaine_relance = prochaine
            facture.save(update_fields=['prochaine_relance'])
        data = FactureSerializer(facture).data
        data['email_log_id'] = email_log_id
        return Response(data)

    @extend_schema(responses=D.RelanceApercuResponse)
    @action(detail=True, methods=['get'], url_path='relance-apercu',
            permission_classes=[IsResponsableOrAdmin])
    def relance_apercu(self, request, pk=None):
        """Fenêtre « Relancer » (fondateur, 05/10/2026) : niveau qui part
        maintenant (1 → 2 → 3 d'après le journal des relances) + aperçu EXACT
        de l'email (même rendu que l'envoi). Lecture seule — hormis la
        création, si la société n'en a aucun, des 3 niveaux par défaut.
        Contrat : ``contract_samples/facture_relance_apercu.json``."""
        from ..recouvrement import apercu_relance
        facture = self.get_object()
        return Response(apercu_relance(facture))

    @extend_schema(request=D.ExclureRelanceRequest, responses=FactureSerializer)
    @action(detail=True, methods=['post'], url_path='exclure-relance',
            permission_classes=[IsResponsableOrAdmin])
    def exclure_relance(self, request, pk=None):
        """Bascule l'exclusion de la facture des listes d'impayés."""
        facture = self.get_object()
        corps = request.data if isinstance(request.data, dict) else {}
        exclu = corps.get('exclu', True)
        if not isinstance(exclu, bool):
            raise ValidationError({'exclu': ['Booléen attendu.']})
        facture.exclu_relances = exclu
        facture.save(update_fields=['exclu_relances'])
        return Response(FactureSerializer(facture).data)

    @extend_schema(responses=RelanceLogSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='relances',
            permission_classes=[IsAnyRole])
    def relances(self, request, pk=None):
        """Historique des relances consignées sur cette facture."""
        facture = self.get_object()
        return Response(
            RelanceLogSerializer(facture.relances.all(), many=True).data)

    @extend_schema(responses=EmailLogSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='emails',
            permission_classes=[IsAnyRole])
    def emails(self, request, pk=None):
        """Fil des emails (envoyés/reçus) consignés sur cette facture (N87/N88)."""
        from ..serializers import EmailLogSerializer
        facture = self.get_object()
        return Response(
            EmailLogSerializer(facture.email_logs.all(), many=True).data)

    @extend_schema(responses=FactureActivitySerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter de la facture : avoirs créés + paiements encaissés (qui,
        quand, montant). Lecture seule ; acteur et société posés côté serveur."""
        from ..serializers_facturation import FactureActivitySerializer
        facture = self.get_object()
        return Response(
            FactureActivitySerializer(
                facture.activites.all(), many=True).data)
