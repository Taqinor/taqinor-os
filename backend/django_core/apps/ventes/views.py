from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from apps.stock.models import MouvementStock
from .models import (
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
)
from .serializers import (
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
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from .utils.references import create_with_reference
from .utils.company_settings import create_numbered

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


class DevisViewSet(viewsets.ModelViewSet):
    queryset = Devis.objects.select_related(
        'client', 'created_by'
    ).prefetch_related('lignes').all()

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que les
        # devis qu'il a créés / son équipe. 'all' → inchangé.
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        # Filtre optionnel ?lead=<id> — utilisé par le dialogue « Signé » (A2)
        # pour lister les devis d'un lead. Borné à la société par _company_qs.
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DevisWriteSerializer
        return DevisSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'generer_pdf', 'telecharger_pdf', 'convertir_en_bc', 'proposal',
            'generer_facture', 'reviser', 'accepter', 'noter',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from apps.crm.services import resolve_client_for_lead

        company = self.request.user.company
        lead = serializer.validated_data.get('lead')
        client = serializer.validated_data.get('client')

        # Tenant safety: lead and client must belong to the user's company.
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})

        # Lead-primary: when no client is given, resolve it from the lead
        # (reuses the linked/matching client, else creates one — no duplicates).
        if client is None:
            if lead is None:
                raise ValidationError(
                    {'client': 'Un client ou un lead est requis.'})
            client = resolve_client_for_lead(lead)

        create_numbered(
            Devis, company, 'devis',
            lambda ref: serializer.save(
                reference=ref,
                client=client,
                created_by=self.request.user,
                company=company,
            ),
        )

        # Mouvement automatique du funnel CRM : un devis créé directement en
        # « envoyé »/« accepté » avance le lead (ancien statut ≡ brouillon).
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, Devis.Statut.BROUILLON,
            serializer.instance.statut, self.request.user,
        )

    @action(detail=True, methods=['post'], url_path='approuver-remise',
            permission_classes=[IsAdminRole])
    def approuver_remise(self, request, pk=None):
        """Approbation admin de la remise (T17) — débloque l'envoi du devis."""
        devis = self.get_object()
        devis.remise_approuvee = True
        devis.remise_approuvee_par = request.user
        devis.save(update_fields=['remise_approuvee', 'remise_approuvee_par'])
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reviser',
            permission_classes=[IsResponsableOrAdmin])
    def reviser(self, request, pk=None):
        """Révise un devis en une NOUVELLE version (v2, v3…). La nouvelle version
        clone les lignes et repart en brouillon ; l'ancienne devient inactive et
        pointe vers sa remplaçante (lecture seule côté UI). Les liens lead/client
        et le schéma de numérotation sont préservés. Additif, sans perte."""
        old = self.get_object()
        company = old.company
        root = old.version_parent or old
        new_devis = {}

        def _save(ref):
            new_devis['obj'] = Devis.objects.create(
                company=company, reference=ref, client=old.client, lead=old.lead,
                statut=Devis.Statut.BROUILLON, taux_tva=old.taux_tva,
                remise_globale=old.remise_globale, note=old.note,
                mode_installation=old.mode_installation,
                etude_params=old.etude_params, prix_cible_kwc=old.prix_cible_kwc,
                created_by=request.user, version=old.version + 1,
                version_parent=root, is_active=True)
            return new_devis['obj']

        create_numbered(Devis, company, 'devis', _save)
        nd = new_devis['obj']
        for ligne in old.lignes.all():
            LigneDevis.objects.create(
                devis=nd, produit=ligne.produit, designation=ligne.designation,
                quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
                remise=ligne.remise, taux_tva=ligne.taux_tva)
        old.is_active = False
        old.superseded_by = nd
        old.save(update_fields=['is_active', 'superseded_by'])
        return Response(
            DevisSerializer(nd, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='accepter',
            permission_classes=[IsResponsableOrAdmin])
    def accepter(self, request, pk=None):
        """N25 — marque le devis « accepté » à une date choisie, en capturant le
        nom de la personne qui accepte ; l'acceptation est consignée dans le
        chatter du devis et avance le funnel CRM (→ SIGNED). C'est le
        déclencheur explicite de la création d'un chantier."""
        from datetime import date as _date
        from . import activity
        from apps.crm.services import avancer_stage_pour_devis
        devis = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        date_str = (request.data.get('date') or '').strip()
        try:
            date_acc = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # A1 — option retenue (« Sans batterie » / « Avec batterie »). Pour un
        # devis à deux options, l'option est obligatoire ; pour un devis à
        # option unique, elle est déduite du scénario du document.
        option, err = self._resolve_accepted_option(devis, request.data)
        if err is not None:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)
        ancien = devis.statut
        devis.statut = Devis.Statut.ACCEPTE
        devis.date_acceptation = date_acc
        devis.accepte_par_nom = nom[:150]
        devis.option_acceptee = option
        devis.save(update_fields=[
            'statut', 'date_acceptation', 'accepte_par_nom', 'option_acceptee'])
        activity.log_devis_acceptance(
            devis, request.user, nom, date_acc, option)
        avancer_stage_pour_devis(devis, ancien, devis.statut, request.user)
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @staticmethod
    def _resolve_accepted_option(devis, data):
        """A1 — détermine l'option retenue à l'acceptation.

        Renvoie ``(option, None)`` en cas de succès ou ``('', message)`` en cas
        d'erreur. Un devis à deux options exige un choix explicite et valide ;
        un devis à option unique déduit l'option de son scénario (jamais
        d'échec : une liste libre / un pompage retombe sur « sans_batterie »).
        """
        valid = {c.value for c in Devis.OptionAcceptee}
        option = (data.get('option') or '').strip()
        if option and option not in valid:
            return '', ("Option invalide (attendu « sans_batterie » ou "
                        "« avec_batterie »).")
        try:
            from .quote_engine.builder import build_quote_data
            qd = build_quote_data(devis, {'pdf_mode': 'onepage'})
            nb_options = qd.get('nb_options', 1)
            scenario = qd.get('scenario', '')
        except Exception:  # noqa: BLE001 — l'acceptation ne doit jamais casser
            nb_options, scenario = 1, ''
        if nb_options == 2 and not option:
            return '', ("Ce devis comporte deux options — précisez celle "
                        "choisie par le client (« sans_batterie » ou "
                        "« avec_batterie »).")
        if not option:
            option = (Devis.OptionAcceptee.AVEC_BATTERIE
                      if scenario == 'Avec batterie'
                      else Devis.OptionAcceptee.SANS_BATTERIE)
        return option, None

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter du devis (notes + acceptation)."""
        devis = self.get_object()
        return Response(
            DevisActivitySerializer(devis.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        """Ajoute une note manuelle au chatter du devis."""
        from . import activity
        devis = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'detail': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_devis_note(devis, request.user, body)
        return Response(DevisActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    def _guard_discount_approval(self, devis, ancien, nouveau, remise):
        """T17 — bloque le passage en « envoyé » si la remise dépasse le seuil
        société sans approbation. Seuil non renseigné = désactivé (défaut).
        Un admin/propriétaire approuve implicitement en envoyant."""
        from rest_framework.exceptions import ValidationError
        if nouveau != 'envoye' or ancien == 'envoye':
            return
        from apps.parametres.models import CompanyProfile
        seuil = CompanyProfile.get(devis.company).discount_approval_threshold
        if seuil is None:
            return
        if (remise or 0) <= seuil or devis.remise_approuvee:
            return
        if getattr(self.request.user, 'is_admin_role', False):
            devis.remise_approuvee = True
            devis.remise_approuvee_par = self.request.user
            devis.save(update_fields=['remise_approuvee', 'remise_approuvee_par'])
            return
        raise ValidationError({'statut': (
            f'Remise de {remise} % supérieure au seuil de {seuil} % : '
            "l'approbation d'un administrateur est requise avant l'envoi.")})

    def perform_update(self, serializer):
        # Snapshot du statut AVANT écriture, puis mouvement automatique du
        # funnel CRM (envoye → QUOTE_SENT, accepte → SIGNED). Import local
        # pour éviter les cycles, comme dans perform_create.
        ancien_statut = serializer.instance.statut
        nouveau_statut = serializer.validated_data.get('statut', ancien_statut)
        remise = serializer.validated_data.get(
            'remise_globale', serializer.instance.remise_globale)
        self._guard_discount_approval(
            serializer.instance, ancien_statut, nouveau_statut, remise)
        super().perform_update(serializer)
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, ancien_statut,
            serializer.instance.statut, self.request.user,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_pdf(self, request, pk=None):
        devis = self.get_object()
        from .quote_engine import clean_pdf_options
        from .tasks import task_generate_devis_pdf
        # Format options (simulator parity) — whitelisted server-side.
        pdf_options = clean_pdf_options(request.data)
        task = task_generate_devis_pdf.delay(devis.id, pdf_options)
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.PDF, instance=devis, detail='PDF devis généré')
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='proposal',
        permission_classes=[IsResponsableOrAdmin],
    )
    def proposal(self, request, pk=None):
        """Canonical client-facing quote PDF path (CLAUDE.md rule #4).

        Renders the premium quote PDF for this devis (synchronously, via the
        vendored quote engine), stores it in MinIO and streams it inline.
        """
        devis = self.get_object()
        try:
            from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
            from .utils.pdf import download_pdf
            # Format via query params, e.g. ?pdf_mode=onepage&devis_final=1
            raw = {
                'pdf_mode': request.query_params.get('pdf_mode'),
                'payment_mode': request.query_params.get('payment_mode'),
                'custom_acompte': request.query_params.get('custom_acompte'),
            }
            if 'show_monthly' in request.query_params:
                raw['show_monthly'] = request.query_params['show_monthly'] not in ('0', 'false')
            if 'devis_final' in request.query_params:
                raw['devis_final'] = request.query_params['devis_final'] in ('1', 'true')
            # Page « Étude » (4e page premium) — dégrade proprement à 3 pages
            # si le devis n'a pas de données d'étude (géré par le moteur).
            if 'include_etude' in request.query_params:
                raw['include_etude'] = request.query_params['include_etude'] in ('1', 'true')
            key = generate_premium_devis_pdf(devis.id, clean_pdf_options(raw))
            pdf_bytes = download_pdf(key)
        except Exception as exc:
            return Response(
                {'detail': f'Génération de la proposition échouée : {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="Proposition_{devis.reference}.pdf"'
        )
        return response

    @action(
        detail=True,
        methods=['get'],
        url_path='telecharger-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def telecharger_pdf(self, request, pk=None):
        devis = self.get_object()
        if not devis.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from .utils.pdf import download_pdf
            pdf_bytes = download_pdf(devis.fichier_pdf)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f'{devis.reference}.pdf'
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @action(
        detail=True,
        methods=['post'],
        url_path='convertir-bc',
        permission_classes=[IsResponsableOrAdmin],
    )
    def convertir_en_bc(self, request, pk=None):
        devis = self.get_object()
        if devis.statut != Devis.Statut.ACCEPTE:
            return Response(
                {'detail': (
                    'Le devis doit être au statut '
                    '« Accepté » pour être converti.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if BonCommande.objects.filter(devis=devis).exists():
            return Response(
                {'detail': 'Un bon de commande existe déjà pour ce devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = request.user.company
        bc = create_numbered(
            BonCommande, company, 'bon_commande',
            lambda ref: BonCommande.objects.create(
                reference=ref,
                devis=devis,
                client=devis.client,
                statut=BonCommande.Statut.EN_ATTENTE,
                company=company,
            ),
        )
        serializer = BonCommandeSerializer(bc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-facture',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_facture(self, request, pk=None):
        """Génère la PROCHAINE facture de tranche de l'échéancier du devis.

        1er appel → facture d'acompte (30 % ou 50 % selon le mode) ; appels
        suivants → tranche matériel puis solde. Chaque facture est numérotée
        sans collision et créée « Émise » (postée). L'échéancier vient de
        l'unique mapping PAYMENT_TERMS_BY_MODE.
        """
        devis = self.get_object()
        from .utils.echeancier import creer_facture_tranche
        try:
            facture = creer_facture_tranche(
                devis, request.user, request.user.company,
                create_with_reference,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )


class LigneDevisViewSet(viewsets.ModelViewSet):
    queryset = LigneDevis.objects.select_related('devis', 'produit').all()
    serializer_class = LigneDevisSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(devis__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['destroy']:
            # Retirer une LIGNE fait partie de l'édition normale d'un
            # brouillon (le générateur remplace les lignes) — même niveau
            # que les autres écritures. Supprimer le DEVIS entier reste admin.
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]


class BonCommandeViewSet(viewsets.ModelViewSet):
    queryset = BonCommande.objects.select_related('client', 'devis').all()
    serializer_class = BonCommandeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'client__nom', 'client__email']
    ordering_fields = [
        'date_creation', 'date_livraison_prevue', 'statut'
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'confirmer', 'marquer_livre', 'annuler', 'creer_facture'
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company
        create_numbered(
            BonCommande, company, 'bon_commande',
            lambda ref: serializer.save(reference=ref, company=company),
        )

    @action(detail=True, methods=['post'], url_path='confirmer',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.EN_ATTENTE:
            return Response(
                {'detail': 'Seul un BC en attente peut être confirmé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommande.Statut.CONFIRME
        bc.save()
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='marquer-livre',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_livre(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.CONFIRME:
            return Response(
                {'detail': (
                    'Le BC doit être confirmé avant d\'être livré.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            if bc.devis:
                for ligne in bc.devis.lignes.select_related('produit'):
                    produit = ligne.produit
                    produit.refresh_from_db()
                    qte = int(ligne.quantite)
                    qte_avant = produit.quantite_stock
                    qte_apres = qte_avant - qte
                    if qte_apres < 0:
                        return Response(
                            {'detail': (
                                f'Stock insuffisant pour '
                                f'« {produit.nom} » '
                                f'(disponible : {qte_avant}, '
                                f'requis : {qte}).'
                            )},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    MouvementStock.objects.create(
                        company=bc.company,
                        produit=produit,
                        type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                        quantite=qte,
                        quantite_avant=qte_avant,
                        quantite_apres=qte_apres,
                        reference=bc.reference,
                        note=f'Livraison BC {bc.reference}',
                        created_by=request.user,
                    )
                    produit.quantite_stock = qte_apres
                    produit.save(update_fields=['quantite_stock'])
            bc.statut = BonCommande.Statut.LIVRE
            bc.save()
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommande.Statut.LIVRE:
            return Response(
                {'detail': 'Un BC livré ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommande.Statut.ANNULE
        bc.save()
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='creer-facture',
            permission_classes=[IsResponsableOrAdmin])
    def creer_facture(self, request, pk=None):
        bc = self.get_object()
        if bc.statut not in [
            BonCommande.Statut.CONFIRME, BonCommande.Statut.LIVRE
        ]:
            return Response(
                {'detail': 'Le BC doit être confirmé ou livré.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Facture.objects.filter(bon_commande=bc).exists():
            return Response(
                {'detail': 'Une facture existe déjà pour ce BC.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = request.user.company

        def _create_facture(ref):
            facture = Facture.objects.create(
                reference=ref,
                bon_commande=bc,
                client=bc.client,
                statut=Facture.Statut.BROUILLON,
                created_by=request.user,
                company=company,
            )
            if bc.devis:
                for ligne in bc.devis.lignes.all():
                    LigneFacture.objects.create(
                        facture=facture,
                        produit=ligne.produit,
                        designation=ligne.designation,
                        quantite=ligne.quantite,
                        prix_unitaire=ligne.prix_unitaire,
                        remise=ligne.remise,
                        # Reporte le taux TVA de la ligne de devis (10/20),
                        # pour que la facture reproduise fidèlement la TVA.
                        taux_tva=ligne.taux_tva,
                    )
            return facture

        # create_with_reference runs _create_facture inside a transaction, so
        # the facture and its copied lines stay atomic like before.
        facture = create_numbered(
            Facture, company, 'facture', _create_facture)
        return Response(
            FactureSerializer(facture).data,
            status=status.HTTP_201_CREATED,
        )


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
            'dgi_export', 'dgi_conformite',
        ]:
            return [IsResponsableOrAdmin()]
        # Annuler une facture = réservé à l'admin/propriétaire (geste comptable).
        elif self.action in ['destroy', 'annuler']:
            return [IsAdminRole()]
        # creer_avoir tombe ici → IsAdminRole (création d'avoir = admin).
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company
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
        # Garde sur-paiement : refuser un encaissement qui dépasse le reste à
        # payer (TTC − déjà payé − avoirs). Tolérance d'un centime pour les
        # arrondis ; un montant égal au reste passe (solde la facture).
        reste = facture.montant_du
        if montant - reste > Decimal('0.01'):
            return Response(
                {'detail': (
                    f'Le paiement dépasse le reste à payer '
                    f'({reste:.2f} MAD).'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            paiement = serializer.save(
                facture=facture,
                company=facture.company,
                created_by=request.user,
            )
            # Chatter facture : trace l'encaissement (acteur côté serveur,
            # jamais lu du corps de la requête).
            from . import activity
            activity.log_facture_paiement(facture, request.user, paiement)
            # Statut auto : intégralement réglée → « Payée ».
            facture.refresh_from_db()
            if facture.montant_du <= Decimal('0') and \
                    facture.statut != Facture.Statut.ANNULEE:
                facture.statut = Facture.Statut.PAYEE
                facture.save(update_fields=['statut'])
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='generer-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def generer_pdf(self, request, pk=None):
        facture = self.get_object()
        from .tasks import task_generate_facture_pdf
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
            from .utils.pdf import download_pdf
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
        from .utils.ubl import build_ubl_xml, store_ubl_xml
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
        from .utils.phone import normalize_ma_phone
        from .utils.whatsapp import build_facture_whatsapp, build_wa_url
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
        from .activity import log_facture_whatsapp
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
        from .email_service import send_document_email
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
        from decimal import Decimal
        reste_creditable = facture.total_ttc - facture.avoirs_total

        def _create(ref):
            avoir = Avoir.objects.create(
                company=company, reference=ref, facture=facture,
                client=facture.client, statut=Avoir.Statut.EMISE,
                motif=motif, taux_tva=facture.taux_tva,
                created_by=request.user)
            if isinstance(lignes, list) and lignes:
                for ligne in lignes:
                    try:
                        qte = ligne.get('quantite')
                        pu = ligne.get('prix_unitaire')
                        if qte in (None, '') or pu in (None, ''):
                            continue
                        LigneAvoir.objects.create(
                            avoir=avoir,
                            produit_id=ligne.get('produit') or None,
                            designation=ligne.get('designation', '')[:255],
                            quantite=qte, prix_unitaire=pu,
                            remise=ligne.get('remise') or 0,
                            taux_tva=ligne.get('taux_tva'))
                    except Exception:
                        continue
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
        from . import activity
        activity.log_facture_avoir(facture, request.user, avoir)
        try:
            from .utils.pdf import generate_avoir_pdf
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
            from .email_service import send_relance_email
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
        from .serializers import EmailLogSerializer
        facture = self.get_object()
        return Response(
            EmailLogSerializer(facture.email_logs.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter de la facture : avoirs créés + paiements encaissés (qui,
        quand, montant). Lecture seule ; acteur et société posés côté serveur."""
        from .serializers import FactureActivitySerializer
        facture = self.get_object()
        return Response(
            FactureActivitySerializer(
                facture.activites.all(), many=True).data)


class AvoirViewSet(viewsets.ReadOnlyModelViewSet):
    """Avoirs (notes de crédit) : lecture pour tout rôle ; PDF pour
    Responsable/Admin ; annulation Admin. Création via la facture
    (creer-avoir), jamais directement."""
    queryset = Avoir.objects.select_related(
        'client', 'facture', 'created_by').prefetch_related('lignes').all()
    serializer_class = AvoirSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'facture__reference', 'client__nom']
    ordering_fields = ['date_emission', 'reference']
    ordering = ['-date_emission']

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        # Portée de visibilité (Feature F) — avoirs créés par soi / l'équipe.
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        if self.action == 'annuler':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        avoir = self.get_object()
        avoir.statut = Avoir.Statut.ANNULEE
        avoir.save(update_fields=['statut'])
        return Response(AvoirSerializer(avoir).data)

    @action(detail=True, methods=['get'], url_path='telecharger-pdf')
    def telecharger_pdf(self, request, pk=None):
        avoir = self.get_object()
        from .utils.pdf import download_pdf, generate_avoir_pdf
        try:
            if not avoir.fichier_pdf:
                generate_avoir_pdf(avoir.id)
                avoir.refresh_from_db()
            pdf_bytes = download_pdf(avoir.fichier_pdf)
        except Exception:
            return Response({'detail': 'PDF indisponible.'},
                            status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{avoir.reference}.pdf"')
        return response


class PaiementViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule des paiements (l'enregistrement passe par la facture).

    Visible par tout rôle authentifié ; tenant-scopé par société.
    """
    queryset = Paiement.objects.select_related(
        'facture', 'facture__client', 'created_by'
    ).all()
    serializer_class = PaiementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'montant', 'date_creation']
    ordering = ['-date_paiement']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        return [IsAnyRole()]


class LigneFactureViewSet(viewsets.ModelViewSet):
    queryset = LigneFacture.objects.select_related(
        'facture', 'produit'
    ).all()
    serializer_class = LigneFactureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(facture__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


@api_view(['GET'])
@permission_classes([IsAnyRole])
def email_config(request):
    """N87 — État du compte d'envoi email (lecture seule, informatif).

    Renvoie si un compte d'envoi (Brevo/SMTP) est réellement configuré et
    l'adresse expéditrice. Quand `configured` est False, l'envoi reste un NO-OP
    (backend console) — le comportement actuel est préservé. La configuration
    réelle (clé Brevo, expéditeur) se fait par variables d'environnement, pas
    via cet endpoint."""
    from django.conf import settings as dj_settings
    from .email_service import is_email_configured
    return Response({
        'configured': is_email_configured(),
        'from_email': getattr(dj_settings, 'DEFAULT_FROM_EMAIL', ''),
        'inbound_configured': _inbound_configured(),
    })


def _inbound_configured():
    try:
        from .inbound_email import is_inbound_configured
        return is_inbound_configured()
    except Exception:
        return False
