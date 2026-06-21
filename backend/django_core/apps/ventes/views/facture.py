from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AvoirSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class FactureViewSet(viewsets.ModelViewSet):
    queryset = Facture.objects.select_related(
        'client', 'created_by', 'bon_commande'
    ).prefetch_related('lignes').all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'client__email'
    ]
    ordering_fields = [
        'date_emission', 'date_echeance', 'statut', 'reference'
    ]
    ordering = ['-date_emission']

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        # Portée de visibilité (Feature F) — factures créées par soi / l'équipe.
        return scope_queryset(qs, self.request.user, ['created_by'])

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FactureWriteSerializer
        return FactureSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['paiements', 'relances', 'emails']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'emettre', 'marquer_payee', 'enregistrer_paiement',
            'generer_pdf', 'telecharger_pdf', 'envoyer_email',
            'relancer', 'exclure_relance', 'whatsapp', 'ubl',
            'dgi_export', 'dgi_conformite', 'bulk',
        ]:
            return [IsResponsableOrAdmin()]
        # Annuler une facture = réservé à l'admin/propriétaire (geste comptable).
        elif self.action in ['destroy', 'annuler']:
            return [IsAdminRole()]
        # creer_avoir tombe ici → IsAdminRole (création d'avoir = admin).
        return [IsAdminRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        # ERR14 — client/bon_commande/devis du corps doivent appartenir à la
        # société (refuse de lier une facture aux enregistrements d'un autre
        # tenant).
        if company is not None:
            client = serializer.validated_data.get('client')
            bon_commande = serializer.validated_data.get('bon_commande')
            devis = serializer.validated_data.get('devis')
            if client is not None and client.company_id != company.id:
                raise ValidationError({'client': 'Client inconnu.'})
            if bon_commande is not None and \
                    bon_commande.company_id != company.id:
                raise ValidationError(
                    {'bon_commande': 'Bon de commande inconnu.'})
            if devis is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
        create_numbered(
            Facture, company, 'facture',
            lambda ref: serializer.save(
                created_by=self.request.user,
                reference=ref,
                company=company,
            ),
        )

    @action(detail=True, methods=['post'], url_path='emettre',
            permission_classes=[IsResponsableOrAdmin])
    def emettre(self, request, pk=None):
        facture = self.get_object()
        if facture.statut != Facture.Statut.BROUILLON:
            return Response(
                {'detail': 'Seule une facture brouillon peut être émise.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not facture.lignes.exists():
            return Response(
                {'detail': (
                    'La facture doit contenir au moins une ligne.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.EMISE
        facture.save()
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='marquer-payee',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_payee(self, request, pk=None):
        facture = self.get_object()
        if facture.statut not in [
            Facture.Statut.EMISE, Facture.Statut.EN_RETARD
        ]:
            return Response(
                {'detail': (
                    'Seule une facture émise ou en retard '
                    'peut être marquée payée.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.PAYEE
        facture.save()
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsAdminRole])
    def annuler(self, request, pk=None):
        facture = self.get_object()
        if facture.statut == Facture.Statut.PAYEE:
            return Response(
                {'detail': 'Une facture payée ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.ANNULEE
        facture.save()
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['get'], url_path='paiements',
            permission_classes=[IsAnyRole])
    def paiements(self, request, pk=None):
        """Liste les paiements enregistrés sur cette facture."""
        facture = self.get_object()
        return Response(
            PaiementSerializer(
                facture.paiements.all(), many=True
            ).data
        )

    @action(detail=True, methods=['post'], url_path='enregistrer-paiement',
            permission_classes=[IsResponsableOrAdmin])
    def enregistrer_paiement(self, request, pk=None):
        """Enregistre MANUELLEMENT un paiement (montant + date + mode).

        Réduit le reste à payer de la facture et le solde du devis. Quand la
        facture est intégralement réglée, elle passe automatiquement « Payée ».
        Disponible à la Commerciale (création) ; l'annulation reste admin.
        """
        from decimal import Decimal
        facture = self.get_object()
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail': 'Impossible d\'encaisser sur une facture annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PaiementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        montant = serializer.validated_data.get('montant')
        if montant is None or montant <= 0:
            return Response(
                {'detail': 'Le montant du paiement doit être positif.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # ERR72 — la garde sur-paiement et l'écriture du paiement doivent être
        # sérialisées : on verrouille la ligne facture (select_for_update) puis
        # on lit le reste à payer, on contrôle, et on enregistre — le tout dans
        # une seule transaction. Sans le verrou, deux paiements concurrents
        # lisaient chacun l'ancien reste et passaient tous deux la garde.
        with transaction.atomic():
            locked = Facture.objects.select_for_update().get(pk=facture.pk)
            if locked.statut == Facture.Statut.ANNULEE:
                return Response(
                    {'detail':
                     'Impossible d\'encaisser sur une facture annulée.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Garde sur-paiement : refuser un encaissement qui dépasse le reste
            # à payer (TTC − déjà payé − avoirs). Tolérance d'un centime pour
            # les arrondis ; un montant égal au reste passe (solde la facture).
            reste = locked.montant_du
            if montant - reste > Decimal('0.01'):
                return Response(
                    {'detail': (
                        f'Le paiement dépasse le reste à payer '
                        f'({reste:.2f} MAD).'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            paiement = serializer.save(
                facture=locked,
                company=locked.company,
                created_by=request.user,
            )
            # Chatter facture : trace l'encaissement (acteur côté serveur,
            # jamais lu du corps de la requête).
            from .. import activity
            activity.log_facture_paiement(locked, request.user, paiement)
            # Statut auto : intégralement réglée → « Payée ».
            locked.refresh_from_db()
            if locked.montant_du <= Decimal('0') and \
                    locked.statut != Facture.Statut.ANNULEE:
                locked.statut = Facture.Statut.PAYEE
                locked.save(update_fields=['statut'])
            facture = locked
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='generer-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def generer_pdf(self, request, pk=None):
        facture = self.get_object()
        from ..tasks import task_generate_facture_pdf
        task = task_generate_facture_pdf.delay(facture.id)
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.PDF, instance=facture,
               detail='PDF facture généré')
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='telecharger-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def telecharger_pdf(self, request, pk=None):
        facture = self.get_object()
        if not facture.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from ..utils.pdf import download_pdf
            pdf_bytes = download_pdf(facture.fichier_pdf)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f'{facture.reference}.pdf'
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

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

    @action(detail=True, methods=['get'], url_path='dgi-export',
            permission_classes=[IsResponsableOrAdmin])
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

    @action(detail=True, methods=['post'], url_path='whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp(self, request, pk=None):
        """Lien wa.me prêt à envoyer pour une facture (ou un rappel).

        N'envoie RIEN : ouvre WhatsApp avec le message pré-rempli. Le {lien} est
        un lien public tokenisé (30 j) vers le PDF CLIENT de la facture.
        Body : `modele` ∈ {'facture','relance'}, `langue` ∈ {'fr','darija'}.
        """
        from ..utils.phone import normalize_ma_phone
        from ..utils.whatsapp import build_facture_whatsapp, build_wa_url
        facture = self.get_object()
        phone = facture.client.telephone if facture.client_id else ''
        if not normalize_ma_phone(phone):
            return Response(
                {'detail': 'Aucun numéro de téléphone.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        modele = request.data.get('modele', 'facture')
        langue = request.data.get('langue', 'fr')
        message, link = build_facture_whatsapp(request, facture, modele, langue)
        # L856 — trace l'action dans le chatter de la facture (Historique).
        # Acteur et société posés côté serveur, jamais lus du corps de requête.
        from ..activity import log_facture_whatsapp
        log_facture_whatsapp(facture, request.user, modele)
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
        })

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
        log = send_document_email(
            facture,
            to_email=(request.data.get('to_email') or '').strip() or None,
            sujet=(request.data.get('sujet') or '').strip() or None,
            corps=(request.data.get('corps') or '').strip() or None,
            user=request.user,
            attach_pdf=request.data.get('attach_pdf', True),
        )
        if log.statut == EmailLog.Statut.ECHEC:
            return Response(
                {'detail': log.erreur or 'Envoi impossible.',
                 'email_log_id': log.id},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'detail': 'Email envoyé.', 'email_log_id': log.id,
             'to_email': log.to_email},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['post'], url_path='creer-avoir')
    def creer_avoir(self, request, pk=None):
        """Crée un Avoir (note de crédit) depuis une facture ÉMISE — admin only
        (get_permissions par défaut). Total ou partiel : si `lignes` est fourni
        on crédite ces lignes ; sinon on crédite toute la facture. Lié à la
        facture d'origine ; le PDF reprend le style facture."""
        facture = self.get_object()
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            return Response(
                {'detail': 'Un avoir ne peut être créé que depuis une '
                           'facture émise (ou payée/en retard).'},
                status=status.HTTP_400_BAD_REQUEST)
        company = facture.company
        motif = (request.data.get('motif') or '').strip()
        lignes = request.data.get('lignes')
        # Plafond : un avoir ne peut pas dépasser le reste créditable de la
        # facture (TTC − avoirs actifs déjà émis). Mesuré AVANT création.
        from decimal import Decimal, InvalidOperation
        reste_creditable = facture.total_ttc - facture.avoirs_total

        # ERR34 — valider les lignes fournies AVANT toute création, et échouer
        # bruyamment (400) au lieu de les avaler en silence (l'ancien
        # `except Exception: continue` créait un avoir amputé de son montant,
        # sans erreur). On vérifie désignation / quantité / prix_unitaire de
        # chaque ligne et on renvoie une erreur 400 claire si l'une est
        # invalide.
        clean_lignes = None
        if isinstance(lignes, list) and lignes:
            clean_lignes = []
            for i, ligne in enumerate(lignes, start=1):
                if not isinstance(ligne, dict):
                    return Response(
                        {'detail': f'Ligne {i} invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                designation = (ligne.get('designation') or '').strip()
                if not designation:
                    return Response(
                        {'detail': f'Ligne {i} : désignation requise.'},
                        status=status.HTTP_400_BAD_REQUEST)
                try:
                    qte = Decimal(str(ligne.get('quantite')))
                    pu = Decimal(str(ligne.get('prix_unitaire')))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': (f'Ligne {i} : quantité et prix unitaire '
                                    'numériques requis.')},
                        status=status.HTTP_400_BAD_REQUEST)
                if qte <= 0 or pu < 0:
                    return Response(
                        {'detail': (f'Ligne {i} : quantité > 0 et prix '
                                    'unitaire ≥ 0 requis.')},
                        status=status.HTTP_400_BAD_REQUEST)
                try:
                    remise = Decimal(str(ligne.get('remise') or 0))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': f'Ligne {i} : remise invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                taux_tva = ligne.get('taux_tva')
                if taux_tva not in (None, ''):
                    try:
                        taux_tva = Decimal(str(taux_tva))
                    except (InvalidOperation, TypeError, ValueError):
                        return Response(
                            {'detail': f'Ligne {i} : taux TVA invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
                else:
                    taux_tva = None
                clean_lignes.append({
                    'produit_id': ligne.get('produit') or None,
                    'designation': designation[:255],
                    'quantite': qte, 'prix_unitaire': pu,
                    'remise': remise, 'taux_tva': taux_tva,
                })

        def _create(ref):
            avoir = Avoir.objects.create(
                company=company, reference=ref, facture=facture,
                client=facture.client, statut=Avoir.Statut.EMISE,
                motif=motif, taux_tva=facture.taux_tva,
                created_by=request.user)
            if clean_lignes:
                for ligne in clean_lignes:
                    LigneAvoir.objects.create(avoir=avoir, **ligne)
            else:
                f_lignes = list(facture.lignes.all())
                if f_lignes:
                    for ligne in f_lignes:
                        LigneAvoir.objects.create(
                            avoir=avoir, produit=ligne.produit,
                            designation=ligne.designation,
                            quantite=ligne.quantite,
                            prix_unitaire=ligne.prix_unitaire,
                            remise=ligne.remise, taux_tva=ligne.taux_tva)
                else:
                    # Facture de tranche sans lignes : montants figés.
                    avoir.montant_ht = facture.total_ht
                    avoir.montant_tva = facture.total_tva
                    avoir.montant_ttc = facture.total_ttc
                    avoir.save(update_fields=[
                        'montant_ht', 'montant_tva', 'montant_ttc'])
            return avoir

        avoir = create_numbered(
            Avoir, company, 'avoir', _create)
        # Garde plafond : si l'avoir créé dépasse le reste créditable, on le
        # supprime (avec ses lignes) et on refuse — un avoir partiel correct
        # passe inchangé. Tolérance d'un centime pour les arrondis.
        if avoir.total_ttc - reste_creditable > Decimal('0.01'):
            avoir.lignes.all().delete()
            avoir.delete()
            return Response(
                {'detail': "L'avoir dépasse le montant restant de la facture "
                           f"({reste_creditable:.2f} MAD)."},
                status=status.HTTP_400_BAD_REQUEST)
        # Chatter facture : trace la création de l'avoir (acteur côté serveur,
        # jamais lu du corps de la requête).
        from .. import activity
        activity.log_facture_avoir(facture, request.user, avoir)
        try:
            from ..utils.pdf import generate_avoir_pdf
            generate_avoir_pdf(avoir.id)
            avoir.refresh_from_db()
        except Exception:
            pass
        return Response(AvoirSerializer(avoir).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='relancer',
            permission_classes=[IsResponsableOrAdmin])
    def relancer(self, request, pk=None):
        """Consigne une relance et, par défaut, l'envoie par email (N87).

        Journalise une RelanceLog + fixe la prochaine date de relance. L'email
        de relance part via l'intégration configurable : NO-OP réseau sans clé
        (backend console), envoi réel via Brevo/SMTP quand configuré. Passer
        ``envoyer_email=false`` pour seulement consigner sans envoyer (ancien
        comportement). Ouvert à la Commerciale."""
        facture = self.get_object()
        niveau = request.data.get('niveau')
        note = (request.data.get('note') or '').strip()
        niveau_nom = ''
        lvl = None
        if niveau:
            lvl = FollowupLevel.objects.filter(
                company=facture.company, ordre=niveau).first()
            niveau_nom = lvl.nom if lvl else ''
        RelanceLog.objects.create(
            company=facture.company, facture=facture,
            niveau=niveau or None, niveau_nom=niveau_nom, note=note,
            created_by=request.user)
        # Envoi email de relance (par défaut) — NO-OP sans clé configurée.
        email_log_id = None
        if request.data.get('envoyer_email', True):
            from ..email_service import send_relance_email
            email_log = send_relance_email(
                facture, niveau_nom=niveau_nom,
                message=(lvl.message if lvl else ''), user=request.user)
            email_log_id = email_log.id
        # Prochaine relance proposée si fournie, sinon laissée telle quelle.
        prochaine = request.data.get('prochaine_relance')
        if prochaine:
            facture.prochaine_relance = prochaine
            facture.save(update_fields=['prochaine_relance'])
        data = FactureSerializer(facture).data
        data['email_log_id'] = email_log_id
        return Response(data)

    @action(detail=True, methods=['post'], url_path='exclure-relance',
            permission_classes=[IsResponsableOrAdmin])
    def exclure_relance(self, request, pk=None):
        """Bascule l'exclusion de la facture des listes d'impayés."""
        facture = self.get_object()
        facture.exclu_relances = bool(request.data.get('exclu', True))
        facture.save(update_fields=['exclu_relances'])
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['get'], url_path='relances',
            permission_classes=[IsAnyRole])
    def relances(self, request, pk=None):
        """Historique des relances consignées sur cette facture."""
        facture = self.get_object()
        return Response(
            RelanceLogSerializer(facture.relances.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='emails',
            permission_classes=[IsAnyRole])
    def emails(self, request, pk=None):
        """Fil des emails (envoyés/reçus) consignés sur cette facture (N87/N88)."""
        from ..serializers import EmailLogSerializer
        facture = self.get_object()
        return Response(
            EmailLogSerializer(facture.email_logs.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter de la facture : avoirs créés + paiements encaissés (qui,
        quand, montant). Lecture seule ; acteur et société posés côté serveur."""
        from ..serializers import FactureActivitySerializer
        facture = self.get_object()
        return Response(
            FactureActivitySerializer(
                facture.activites.all(), many=True).data)

    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[IsResponsableOrAdmin])
    def bulk(self, request):
        """FG43 — opérations en masse sur les factures.

        Body :
          - ``action`` ∈ {emettre, relancer, envoyer-email, generer-pdf}
          - ``ids``    : liste d'ids de factures (toutes scopées à la société)

        Renvoie un dict par id : ``{id: {ok: bool, detail: str}}``.
        Les erreurs par facture n'interrompent pas le batch.
        """
        company = request.user.company
        action_name = (request.data.get('action') or '').strip()
        ids = request.data.get('ids') or []

        VALID_ACTIONS = {'emettre', 'relancer', 'envoyer-email', 'generer-pdf'}
        if action_name not in VALID_ACTIONS:
            return Response(
                {'detail': (
                    f'Action invalide. Valeurs acceptées : '
                    f'{", ".join(sorted(VALID_ACTIONS))}.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not ids or not isinstance(ids, list):
            return Response(
                {'detail': 'La liste `ids` est requise et doit être non vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Borner aux factures de la société (scoping multi-tenant).
        factures_qs = _company_qs(
            Facture.objects.select_related('client').all(), request.user
        ).filter(id__in=ids)
        factures_by_id = {f.id: f for f in factures_qs}

        results = {}
        for fid in ids:
            try:
                fid_int = int(fid)
            except (ValueError, TypeError):
                results[fid] = {'ok': False, 'detail': 'ID invalide.'}
                continue
            facture = factures_by_id.get(fid_int)
            if facture is None:
                results[fid_int] = {'ok': False, 'detail': 'Introuvable.'}
                continue
            try:
                if action_name == 'emettre':
                    if facture.statut != Facture.Statut.BROUILLON:
                        results[fid_int] = {
                            'ok': False,
                            'detail': (
                                f'Statut {facture.get_statut_display()} : '
                                'seule une facture brouillon peut être émise.'
                            )}
                    elif not facture.lignes.exists() and not facture.libelle:
                        results[fid_int] = {
                            'ok': False,
                            'detail': 'La facture doit avoir au moins une ligne.'}
                    else:
                        facture.statut = Facture.Statut.EMISE
                        facture.save(update_fields=['statut'])
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Émise.',
                            'reference': facture.reference}

                elif action_name == 'relancer':
                    if facture.statut not in (
                        Facture.Statut.EMISE, Facture.Statut.EN_RETARD,
                    ):
                        results[fid_int] = {
                            'ok': False,
                            'detail': (
                                f'Statut {facture.get_statut_display()} : '
                                'relance uniquement sur facture émise ou en retard.'
                            )}
                    else:
                        from ..models import RelanceLog
                        RelanceLog.objects.create(
                            company=facture.company, facture=facture,
                            note='Relance en masse', created_by=request.user)
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Relance consignée.',
                            'reference': facture.reference}

                elif action_name == 'envoyer-email':
                    from ..email_service import send_document_email
                    from ..models import EmailLog
                    log = send_document_email(
                        facture, user=request.user, attach_pdf=True)
                    if log.statut == EmailLog.Statut.ECHEC:
                        results[fid_int] = {
                            'ok': False,
                            'detail': log.erreur or 'Envoi impossible.'}
                    else:
                        results[fid_int] = {
                            'ok': True,
                            'detail': f'Email envoyé à {log.to_email}.',
                            'reference': facture.reference}

                elif action_name == 'generer-pdf':
                    from ..tasks import task_generate_facture_pdf
                    task = task_generate_facture_pdf.delay(facture.id)
                    results[fid_int] = {
                        'ok': True,
                        'detail': 'Génération PDF lancée.',
                        'task_id': task.id,
                        'reference': facture.reference}

            except Exception as exc:  # noqa: BLE001 — batch: no single failure kills all
                results[fid_int] = {'ok': False, 'detail': str(exc)}

        return Response(results)
