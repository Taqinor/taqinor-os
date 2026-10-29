"""VNT100 — documents de la facture (PDF, UBL, export et transmission DGI,
WhatsApp, e-mail) : actions de ``FactureViewSet`` portées par
``FactureDocumentsActionsMixin``, déplacées telles quelles depuis
``views/facture.py``. Le logger garde le nom ``apps.ventes.views.facture``.
Aucune route dans ``urls.py`` : le routeur les découvre sur le viewset.
"""
import logging

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.roles.permissions import DroitDeLaGrille  # ASEC50
from . import openapi_docs as D
from ..models import EmailLog, Facture
from ..utils.corps import valider_corps

logger = logging.getLogger('apps.ventes.views.facture')


class FactureDocumentsActionsMixin:
    """Les documents émis depuis une facture : PDF, UBL, DGI, envoi par
    WhatsApp ou e-mail."""

    @extend_schema(request=None, responses={202: D.PdfTaskResponse})
    @action(detail=True, methods=['post'], url_path='generer-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def generer_pdf(self, request, pk=None):
        facture = self.get_object()
        from ..tasks import task_generate_facture_pdf
        task = task_generate_facture_pdf.delay(facture.id)
        # M4 — événement découplé : ventes émet, le satellite audit journalise
        # (AuditLog.Action.PDF). ventes n'importe plus apps.audit ; le signal
        # est synchrone (même requête), donc l'acteur/société restent identiques.
        from core.events import document_pdf_generated
        document_pdf_generated.send(
            sender=Facture, instance=facture, kind='facture')
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(responses=D.PdfBinaire)
    @action(detail=True, methods=['get'], url_path='telecharger-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def telecharger_pdf(self, request, pk=None):
        facture = self.get_object()
        # AFAC41 (C-AFAC-042) — le téléchargement interne (et l'aperçu inline
        # de la liste) sert le PDF GARANTI à jour par `cle_facture_pdf_a_jour`,
        # exactement comme le lien public : après un paiement, le « Reste à
        # payer » imprimé est le courant ; une facture jamais rendue se rend à
        # la volée. Si le rafraîchissement échoue, le fichier stocké est servi
        # tel quel (même repli que le lien public).
        from ..utils.pdf import cle_facture_pdf_a_jour, download_pdf
        try:
            cle = cle_facture_pdf_a_jour(facture)
        except Exception:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
            logger.warning("facture.FactureViewSet.telecharger_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            cle = facture.fichier_pdf
        if not cle:
            return Response(
                {'detail': 'PDF indisponible pour le moment. Réessayez.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            pdf_bytes = download_pdf(cle)
        except Exception:
            logger.warning("facture.FactureViewSet.telecharger_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Facture', facture.reference,
            client=facture.client if facture.client_id else None,
            company=facture.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @extend_schema(responses=D.UblXml)
    @action(detail=True, methods=['get'], url_path='ubl',
            permission_classes=[IsResponsableOrAdmin])
    def ubl(self, request, pk=None):
        """N38 — aperçu BROUILLON UBL 2.1 de la facture (XML téléchargeable).

        Génère le XML à la volée, le dépose en local (MinIO, best-effort) et le
        renvoie. Aucun appel externe, aucune transmission DGI."""
        facture = self.get_object()
        from apps.parametres.models import CompanyProfile
        from ..utils.ubl import build_ubl_xml, store_ubl_xml
        profile = CompanyProfile.get(company=facture.company)
        xml_str = build_ubl_xml(facture, profile)
        key = store_ubl_xml(facture, xml_str)
        if key and facture.fichier_ubl != key:
            facture.fichier_ubl = key
            facture.save(update_fields=['fichier_ubl'])
        response = HttpResponse(xml_str, content_type='application/xml')
        response['Content-Disposition'] = (
            f'attachment; filename="{facture.reference}-ubl.xml"'
        )
        return response

    @extend_schema(responses=D.UblXml)
    @action(detail=True, methods=['get'], url_path='dgi-export',
            # ASEC50 / D-ASEC-4 — l'export DGI exige ``ventes_export``.
            permission_classes=[IsResponsableOrAdmin,
                                DroitDeLaGrille('ventes_export')])
    def dgi_export(self, request, pk=None):
        """N105 — Export DGI local (UBL 2.1) de la facture, à la demande.

        GARDÉ par l'interrupteur maître ``dgi_export_actif`` (défaut OFF) : tant
        qu'il est OFF pour la société, cet endpoint se comporte comme
        introuvable (404) → la capacité reste invisible. Aucun statut n'est
        modifié, rien n'est transmis."""
        facture = self.get_object()
        from apps.ventes.dgi import build_ubl_xml, is_dgi_enabled
        if not is_dgi_enabled(facture.company):
            return Response(
                {'detail': 'Introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        xml_str = build_ubl_xml(facture)
        response = HttpResponse(xml_str, content_type='application/xml')
        response['Content-Disposition'] = (
            f'attachment; filename="{facture.reference}-dgi.xml"'
        )
        return response

    @extend_schema(responses=D.DgiConformiteResponse)
    @action(detail=True, methods=['get'], url_path='dgi-conformite',
            permission_classes=[IsResponsableOrAdmin])
    def dgi_conformite(self, request, pk=None):
        """N105 — Contrôle de conformité DGI de la facture, à la demande.

        Même garde que ``dgi_export`` : 404 tant que l'interrupteur maître est
        OFF. Renvoie la liste des problèmes (vide = conforme) ; ne modifie
        aucun statut."""
        facture = self.get_object()
        from apps.ventes.dgi import validate_dgi_conformity, is_dgi_enabled
        if not is_dgi_enabled(facture.company):
            return Response(
                {'detail': 'Introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        problemes = validate_dgi_conformity(facture)
        return Response(
            {'conforme': not problemes, 'problemes': problemes})

    @extend_schema(request=None, responses=D.DgiTransmissionResponse)
    @action(detail=True, methods=['post'], url_path='dgi-transmettre',
            permission_classes=[IsResponsableOrAdmin])
    def dgi_transmettre(self, request, pk=None):
        """XFAC29 — Transmet (ou retransmet) la facture à la plateforme DGI
        agréée configurée. GARDÉ par l'interrupteur maître
        ``dgi_transmission_actif`` (défaut OFF) : tant qu'il est OFF pour la
        société, cet endpoint se comporte comme introuvable (404) — la
        capacité reste invisible, symétrique de `dgi_export`/`dgi_conformite`.
        Un rejet peut être rejoué (nouvelle tentative) ; une facture déjà
        ACCEPTÉE n'est jamais retransmise (idempotence)."""
        facture = self.get_object()
        from apps.ventes.dgi.transmission import (
            is_dgi_transmission_enabled, transmettre_facture,
        )
        if not is_dgi_transmission_enabled(facture.company):
            return Response(
                {'detail': 'Introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        facture = transmettre_facture(facture)
        return Response({
            'dgi_statut': facture.dgi_statut,
            'dgi_reference': facture.dgi_reference,
            'dgi_motif_rejet': facture.dgi_motif_rejet,
        })

    @extend_schema(request=D.FactureWhatsappRequest, responses=D.FactureWhatsappResponse)
    @action(detail=True, methods=['post'], url_path='whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp(self, request, pk=None):
        """Lien wa.me prêt à envoyer pour une facture (ou un rappel).

        N'envoie RIEN : ouvre WhatsApp avec le message pré-rempli. Le {lien} est
        un lien public tokenisé (30 j) vers le PDF CLIENT de la facture.
        Body : `modele` ∈ {'facture','relance'}, `langue` ∈ {'fr','darija'}.
        """
        from ..utils.phone import normalize_phone_e164
        from ..utils.whatsapp import build_facture_whatsapp, build_wa_url
        facture = self.get_object()
        phone = facture.client.telephone if facture.client_id else ''
        saisie = valider_corps(request, D.FactureWhatsappRequest)
        if not normalize_phone_e164(phone):
            return Response(
                # ENF11 (api-fuzz 29/10) — le numéro vient de la FICHE client,
                # pas du corps : refus d'état (409), la requête est valide.
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_409_CONFLICT,
            )
        modele, langue = saisie.get('modele', 'facture'), saisie.get('langue', 'fr')
        message, link = build_facture_whatsapp(request, facture, modele, langue)
        # L856 — trace l'action dans le chatter de la facture (Historique).
        # Acteur et société posés côté serveur, jamais lus du corps de requête.
        from ..activity import log_facture_whatsapp
        log_facture_whatsapp(facture, request.user, modele)
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
        })

    @extend_schema(request=D.EnvoyerEmailFactureRequest,
                   responses={202: D.EnvoyerEmailFactureResponse,
                              400: D.ErreurEnvoiEmail, 409: D.ErreurEnvoiEmail})
    @action(detail=True, methods=['post'], url_path='envoyer-email',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_email(self, request, pk=None):
        """N87 — Envoie la facture au client par email (PDF en pièce jointe).

        Route par l'intégration email configurable : NO-OP réseau sans clé
        (backend console), envoi réel via Brevo/SMTP quand configuré. L'envoi
        est consigné sur le fil (EmailLog). Le corps/sujet/destinataire peuvent
        être surchargés dans le body de la requête."""
        from ..email_service import send_document_email
        facture = self.get_object()
        saisie = valider_corps(request, D.EnvoyerEmailFactureRequest)
        log = send_document_email(
            facture, user=request.user,
            to_email=saisie.get('to_email', '').strip() or None,
            sujet=saisie.get('sujet', '').strip() or None,
            corps=saisie.get('corps', '').strip() or None,
            attach_pdf=saisie.get('attach_pdf', True))
        if log.statut == EmailLog.Statut.ECHEC:
            # ENF11 (nocturne 15/10) — corps conforme mais client SANS adresse
            # (aucune n'est saisie) : c'est la fiche qui s'oppose, 409 ; un
            # autre échec d'envoi garde son 400 (même corps).
            sans_adresse = not log.to_email
            return Response(
                {'detail': log.erreur or 'Envoi impossible.',
                 'email_log_id': log.id},
                status=status.HTTP_409_CONFLICT if sans_adresse else status.HTTP_400_BAD_REQUEST)
        return Response(
            {'detail': 'Email envoyé.', 'email_log_id': log.id,
             'to_email': log.to_email},
            status=status.HTTP_202_ACCEPTED,
        )
