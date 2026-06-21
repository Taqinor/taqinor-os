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
        from .. import activity
        from core.events import devis_accepted
        devis = self.get_object()
        # ERR33 — garde de statut : seul un devis « en cours » (brouillon /
        # envoyé) peut être accepté. Un devis refusé, expiré ou déjà accepté
        # ne se ré-accepte pas (sinon on ressusciterait un devis mort et on
        # ferait avancer le funnel / déclencherait l'échéancier à tort).
        if devis.statut not in (
            Devis.Statut.BROUILLON, Devis.Statut.ENVOYE,
        ):
            return Response(
                {'detail': (
                    'Seul un devis en cours (brouillon ou envoyé) peut être '
                    f'accepté ; statut actuel : '
                    f'« {devis.get_statut_display()} ».'
                )},
                status=status.HTTP_409_CONFLICT,
            )
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
        # M6 — découplage par événement : au lieu d'appeler directement
        # crm.services, on émet l'événement métier « devis accepté ». Le CRM y
        # est abonné (apps/crm/receivers.py) et avance l'étape du lead (→ SIGNED)
        # — comportement identique, mais ventes n'appelle plus crm au site
        # d'acceptation.
        devis_accepted.send(
            sender=Devis, devis=devis, user=request.user, ancien_statut=ancien)
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
            from ..quote_engine.builder import build_quote_data
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
        from .. import activity
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
        from rest_framework.exceptions import ValidationError
        # ERR8 — un PATCH/PUT ne doit pas re-pointer le devis vers le client/lead
        # d'une autre société (mass-assignment). perform_create valide déjà ces
        # FK ; on applique la même garde à la mise à jour.
        company = self.request.user.company
        if company is not None:
            lead = serializer.validated_data.get('lead')
            client = serializer.validated_data.get('client')
            if lead is not None and lead.company_id != company.id:
                raise ValidationError({'lead': 'Lead inconnu.'})
            if client is not None and client.company_id != company.id:
                raise ValidationError({'client': 'Client inconnu.'})
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
        from ..quote_engine import clean_pdf_options
        from ..tasks import task_generate_devis_pdf
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
            from ..quote_engine import clean_pdf_options, generate_premium_devis_pdf
            from ..utils.pdf import download_pdf
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
            # ERR74 — /proposal is a safe GET: render + stream, but do NOT
            # persist fichier_pdf on every call (persist=False). The single
            # engine picks the residential (redesigned) or legacy renderer.
            key = generate_premium_devis_pdf(
                devis.id, clean_pdf_options(raw), persist=False)
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
            from ..utils.pdf import download_pdf
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
        from ..utils.echeancier import creer_facture_tranche
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
