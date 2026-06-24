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
            'generer_facture', 'reviser', 'accepter', 'refuser', 'noter',
            'layout', 'roof_image', 'from_layout', 'share_link',
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

        # FG52 — devise : si le corps n'en fournit pas, appliquer la devise par
        # défaut de la société (CompanyProfile.devise_defaut), repli MAD.
        save_kwargs = dict(
            client=client,
            created_by=self.request.user,
            company=company,
        )
        if 'devise' not in serializer.validated_data:
            from apps.parametres.models import CompanyProfile
            save_kwargs['devise'] = (
                getattr(CompanyProfile.get(company=company), 'devise_defaut', '')
                or 'MAD')

        create_numbered(
            Devis, company, 'devis',
            lambda ref: serializer.save(reference=ref, **save_kwargs),
        )

        # Mouvement automatique du funnel CRM : un devis créé directement en
        # « envoyé »/« accepté » avance le lead (ancien statut ≡ brouillon).
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, Devis.Statut.BROUILLON,
            serializer.instance.statut, self.request.user,
        )

    @action(detail=False, methods=['post'], url_path='from-layout',
            permission_classes=[IsResponsableOrAdmin])
    def from_layout(self, request):
        """Q3/B1 — transforme un layout toiture 3D FINALISÉ en Devis brouillon,
        puis frappe un lien public de proposition.

        Corps : ``{layout, lead, client, taux_tva?, remise_globale?}``. Le
        ``layout`` est le JSON sérialisé tel que stocké par l'action ``layout``
        (AreaRecord[] + result + renderPlan). La société est TOUJOURS celle du
        user (jamais lue du corps) ; lead et client sont résolus bornés à cette
        société (404/400 si une autre société). Au moins un lead OU un client est
        requis. Aucun statut n'est touché : le service renvoie un brouillon
        (préservation des statuts, règle #4) et la numérotation anti-collision
        est gérée par le service.

        QJ17 — idempotency: if a brouillon devis with the same lead + layout hash
        already exists for this company, it is returned (HTTP 200) instead of
        creating a duplicate.  A pre-flight composition check validates the
        catalogue before building and returns HTTP 422 with inline French guidance
        on failure (instead of a PDF error at render time).
        """
        from decimal import Decimal, InvalidOperation
        from ..services import build_devis_from_layout, layout_hash, validate_composition_for_layout
        from ..models import ShareLink

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        layout = request.data.get('layout')
        if not isinstance(layout, dict) or not layout:
            return Response(
                {'detail': 'Layout manquant ou invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        # Résolution bornée société du lead et du client. On passe par les
        # sélecteurs/services crm (jamais d'import direct des models crm depuis
        # ventes) ; un id d'une autre société → 404 (introuvable dans la portée).
        lead_obj = None
        client_obj = None
        lead_id = request.data.get('lead')
        client_id = request.data.get('client')
        if lead_id:
            from apps.crm.selectors import get_company_lead
            lead_obj = get_company_lead(company, lead_id)
            if lead_obj is None:
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        if client_id:
            from apps.crm.selectors import get_company_client
            client_obj = get_company_client(company, client_id)
            if client_obj is None:
                return Response({'detail': 'Client inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        if lead_obj is None and client_obj is None:
            return Response(
                {'detail': 'Un client ou un lead est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _dec(raw, default):
            if raw in (None, ''):
                return default
            try:
                return Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                return None

        taux_tva = _dec(request.data.get('taux_tva'), Decimal('20'))
        remise = _dec(request.data.get('remise_globale'), Decimal('0'))
        if taux_tva is None or remise is None:
            return Response(
                {'detail': 'taux_tva / remise_globale invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        # QJ17 — pre-flight composition check: validate catalogue before building.
        composition_errors = validate_composition_for_layout(layout, company)
        if composition_errors:
            return Response(
                {'detail': composition_errors[0], 'errors': composition_errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # QJ17 — idempotency: dedupe by lead + layout hash.
        # Re-clicking « Générer » returns the existing brouillon, not a duplicate.
        lhash = layout_hash(layout)
        existing = None
        if lead_obj is not None and lhash:
            existing = (
                Devis.objects.filter(
                    company=company,
                    lead=lead_obj,
                    statut=Devis.Statut.BROUILLON,
                    layout_hash=lhash,
                )
                .order_by('-date_creation')
                .first()
            )
        if existing is not None:
            link = ShareLink.for_devis(existing)
            import logging as _logging
            _logging.getLogger(__name__).info(
                'QJ17: dedup hit — returning existing brouillon %s (hash %s…)',
                existing.reference, lhash[:8])
            return Response(
                {
                    'id': existing.id,
                    'reference': existing.reference,
                    'statut': existing.statut,
                    'proposal_token': link.token,
                    'proposal_path': f'/proposition/{link.token}',
                    'deduplicated': True,
                },
                status=status.HTTP_200_OK)

        devis = build_devis_from_layout(
            layout=layout, user=request.user, company=company,
            lead=lead_obj, client=client_obj,
            taux_tva=taux_tva, remise_globale=remise)

        # QJ17 — persist the layout hash on the newly-created devis so future
        # duplicate requests are caught in O(1).
        if lhash:
            Devis.objects.filter(pk=devis.pk).update(layout_hash=lhash)
            devis.layout_hash = lhash

        link = ShareLink.for_devis(devis)
        return Response(
            {
                'id': devis.id,
                'reference': devis.reference,
                'statut': devis.statut,
                'proposal_token': link.token,
                'proposal_path': f'/proposition/{link.token}',
            },
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='share-link',
            permission_classes=[IsResponsableOrAdmin])
    def share_link(self, request, pk=None):
        """B2 — frappe (ou réutilise) un lien public de proposition pour ce
        devis. Permet au site de (re)générer le lien de proposition d'un devis
        existant lors de la livraison. Le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (autre société → 404)."""
        from ..models import ShareLink
        devis = self.get_object()
        link = ShareLink.for_devis(devis)
        return Response(
            {'token': link.token, 'path': f'/proposition/{link.token}'},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='envoyer-email',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_email(self, request, pk=None):
        """QJ14 — Envoie la proposition (PDF premium + lien tokenisé) au client
        par email, consigne l'envoi dans EmailLog et marque le devis « envoyé »
        via mark_devis_sent (règle #4 — seul chemin de transition brouillon→envoyé).

        Body (tous optionnels) :
          - ``to_email``  : adresse destinataire (défaut : client.email)
          - ``sujet``     : objet de l'email (défaut : modèle FR)
          - ``corps``     : corps de l'email (défaut : modèle FR)
          - ``pdf_mode``  : « full » | « onepage » (défaut : « full »)

        Idempotent : un devis déjà « envoyé » (ou plus avancé) ne régresse pas
        — l'email est tout de même envoyé mais mark_devis_sent ne re-stampe pas.

        Retourne l'EmailLog id + statut + le statut courant du devis.
        """
        from ..models import ShareLink
        from ..services import mark_devis_sent
        from ..quote_engine import clean_pdf_options, generate_premium_devis_pdf
        from ..utils.pdf import download_pdf

        devis = self.get_object()
        to_email = (request.data.get('to_email') or '').strip() or None
        sujet = (request.data.get('sujet') or '').strip() or None
        corps = (request.data.get('corps') or '').strip() or None
        pdf_mode = (request.data.get('pdf_mode') or 'full').strip()

        # Génère le PDF premium (persist=False — rendu à la volée, pas de
        # remplacement du fichier stocké : le moteur rend seulement).
        attachment = None
        attachment_name = None
        try:
            opts = clean_pdf_options({'pdf_mode': pdf_mode})
            key = generate_premium_devis_pdf(devis.id, opts, persist=False)
            attachment = download_pdf(key)
            attachment_name = f'Devis_{devis.reference}.pdf'
        except Exception:  # noqa: BLE001 — PDF indisponible n'empêche pas l'envoi
            pass

        # Ajoute le lien de proposition tokenisé dans le corps si fourni.
        link = ShareLink.for_devis(devis)
        proposal_url = f'/proposition/{link.token}'
        if not corps:
            client = devis.client
            nom_client = ''
            if client:
                nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
            salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
            corps = (
                f"{salut}\n\n"
                f"Veuillez trouver ci-joint votre devis {devis.reference}.\n\n"
                f"Vous pouvez également consulter et signer votre proposition en ligne :\n"
                f"{proposal_url}\n\n"
                f"Nous restons à votre disposition pour toute question.\n\n"
                f"Cordialement,\nL'équipe TAQINOR"
            )

        # Envoi + EmailLog via le service centralisé. attach_pdf=False car on
        # a déjà le contenu — on passe attachment/attachment_name directement.
        from ..email_service import _send, _from_email, _chatter_note
        from ..models import EmailLog  # noqa: F811 — local import shadows class-level

        client = devis.client
        dest = (to_email or (getattr(client, 'email', '') or '')).strip()
        reference = devis.reference or ''
        if not sujet:
            sujet = f'Votre devis {reference}'

        log = EmailLog(
            company=devis.company,
            direction=EmailLog.Direction.SORTANT,
            client=client,
            devis=devis,
            to_email=dest, from_email=_from_email(),
            sujet=(sujet or '')[:300], corps=corps,
            reference=reference[:80],
            piece_jointe=(attachment_name or '')[:255],
            created_by=request.user if getattr(request.user, 'is_authenticated', False) else None,
        )

        if not dest:
            log.statut = EmailLog.Statut.ECHEC
            log.erreur = 'Aucune adresse email destinataire.'
            log.save()
            return Response(
                {'detail': log.erreur, 'log_id': log.id, 'statut': 'echec'},
                status=status.HTTP_400_BAD_REQUEST)

        ok, err = _send(dest, sujet, corps, attachment, attachment_name)
        log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
        log.erreur = err
        log.save()

        etat = 'envoyé' if ok else "échec d'envoi"
        _chatter_note(devis, f"Email du devis {reference} — {etat} (à {dest}).", request.user)

        # Marque le devis « envoyé » via le seul chemin autorisé (règle #4).
        # Idempotent : un devis déjà envoyé/accepté/refusé n'est pas régressé.
        mark_devis_sent(devis=devis, user=request.user)

        return Response({
            'detail': f'Email envoyé à {dest}.' if ok else f'Échec envoi email : {err}',
            'log_id': log.id,
            'email_statut': log.statut,
            'devis_statut': devis.statut,
            'proposal_path': proposal_url,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='dupliquer-variante',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer_variante(self, request, pk=None):
        """QJ15 — Crée 2–3 variantes de taille du devis pour comparaison
        côte-à-côte.

        Chaque variante est un devis brouillon indépendant partageable :
          - même client / lead / mode / TVA / remise que l'original ;
          - lignes clonées avec quantités ajustées selon le facteur de
            dimensionnement (``scale``) passé dans le corps — ou déduit
            automatiquement : ×0.8 (−20 %) / ×1.0 (identique) / ×1.25 (+25 %) ;
          - ``version_parent`` positionné sur l'original (ou son propre parent)
            pour grouper les variantes sans créer une revision :
            ``is_active=True`` sur toutes → ce sont des alternatives, pas des
            remplacements ;
          - aucun changement de statut (règle #4) ;
          - numéros de référence séquentiels via ``create_numbered``.

        Corps optionnel :
          ``scales`` : liste de flottants, ex. [0.8, 1.0, 1.25]
                       (défaut : [0.8, 1.0, 1.25], max 3 éléments).

        Retourne la liste des devis créés.
        """
        source = self.get_object()
        company = source.company
        root = source.version_parent or source

        raw_scales = request.data.get('scales', [0.8, 1.0, 1.25])
        try:
            scales = [float(s) for s in raw_scales][:3]
        except (TypeError, ValueError):
            scales = [0.8, 1.0, 1.25]
        if not scales:
            scales = [0.8, 1.0, 1.25]

        # Labels FR pour les variantes (affichés dans la liste et la proposition)
        _labels = {0.8: '−20 %', 1.0: 'Standard', 1.25: '+25 %'}

        created = []
        from decimal import Decimal, ROUND_HALF_UP

        for scale in scales:
            variant_note = _labels.get(scale) or f'×{scale:.2f}'
            holder = {}

            def _save(ref, _scale=scale, _note=variant_note):
                obj = Devis.objects.create(
                    company=company, reference=ref,
                    client=source.client, lead=source.lead,
                    statut=Devis.Statut.BROUILLON,
                    taux_tva=source.taux_tva,
                    remise_globale=source.remise_globale,
                    note=(f'[Variante {_note}] ' + (source.note or '')).strip(),
                    mode_installation=source.mode_installation,
                    etude_params=source.etude_params,
                    prix_cible_kwc=source.prix_cible_kwc,
                    created_by=request.user,
                    # Groupe : version_parent = racine, version incrémentée,
                    # is_active=True (alternative, pas remplacement).
                    version=source.version + len(created) + 1,
                    version_parent=root,
                    is_active=True,
                )
                holder['obj'] = obj
                return obj

            create_numbered(Devis, company, 'devis', _save)
            nd = holder['obj']

            for ligne in source.lignes.all():
                raw_qty = ligne.quantite * Decimal(str(scale))
                qty = raw_qty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                qty = max(qty, Decimal('0.01'))
                LigneDevis.objects.create(
                    devis=nd,
                    produit=ligne.produit,
                    designation=ligne.designation,
                    quantite=qty,
                    prix_unitaire=ligne.prix_unitaire,
                    remise=ligne.remise,
                    taux_tva=ligne.taux_tva,
                )
            created.append(nd)

        return Response(
            [DevisSerializer(v, context={'request': request}).data
             for v in created],
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='variantes',
            permission_classes=[IsResponsableOrAdmin])
    def variantes(self, request, pk=None):
        """QJ15 — Liste les variantes liées à ce devis (même version_parent,
        toutes actives). Utilisé par la proposal côte-à-côte."""
        devis = self.get_object()
        root = devis.version_parent or devis
        siblings = (
            Devis.objects
            .filter(company=devis.company, version_parent=root, is_active=True)
            .select_related('client')
            .order_by('version', 'id')
        )
        # Include root itself in the comparison set.
        root_devis = Devis.objects.filter(
            pk=root.pk, company=devis.company, is_active=True).first()
        results = []
        if root_devis:
            results.append(root_devis)
        for s in siblings:
            if s.pk not in {r.pk for r in results}:
                results.append(s)
        return Response(
            [DevisSerializer(v, context={'request': request}).data
             for v in results],
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
        from ..services import accept_devis, AcceptError
        devis = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        date_str = (request.data.get('date') or '').strip()
        try:
            date_acc = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # A1 — option retenue (« Sans batterie » / « Avec batterie »). La
        # résolution (deux options → choix explicite obligatoire ; mono-option
        # → déduit du scénario) et le tampon d'acceptation passent désormais
        # par le service unique accept_devis (réutilisé par la proposition web
        # tokenisée Q7), préservant 1:1 la chaîne bon-commande/facture (règle #4).
        option = (request.data.get('option') or '').strip()
        try:
            accept_devis(
                devis=devis, user=request.user, nom=nom,
                date_acceptation=date_acc, option=option,
                idempotent_reaccept=False)
        except AcceptError as exc:
            return Response(
                {'detail': exc.message},
                status=(status.HTTP_409_CONFLICT if exc.conflict
                        else status.HTTP_400_BAD_REQUEST))
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

    @action(detail=True, methods=['post'], url_path='refuser',
            permission_classes=[IsResponsableOrAdmin])
    def refuser(self, request, pk=None):
        """FG44 — marque le devis « refusé » avec date + motif + chatter.

        Symétrique à « accepter » : consigne le refus dans l'historique du devis.
        Body optionnel :
          - ``motif``  : raison du refus (libre, max 255 caractères)
          - ``date``   : date ISO AAAA-MM-JJ (défaut = aujourd'hui)
          - ``marquer_lead_perdu`` : true → émet devis_refused → CRM marque
                                     le lead associé perdu (si lead_id présent)
        """
        from datetime import date as _date
        from .. import activity
        from core.events import devis_refused

        devis = self.get_object()
        if devis.statut not in (
            Devis.Statut.BROUILLON, Devis.Statut.ENVOYE,
        ):
            return Response(
                {'detail': (
                    'Seul un devis en cours (brouillon ou envoyé) peut être '
                    f'refusé ; statut actuel : '
                    f'« {devis.get_statut_display()} ».'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        motif = (request.data.get('motif') or '').strip()[:255]
        date_str = (request.data.get('date') or '').strip()
        try:
            date_ref = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        marquer_lead_perdu = bool(
            request.data.get('marquer_lead_perdu', False))

        devis.statut = Devis.Statut.REFUSE
        devis.date_refus = date_ref
        devis.motif_refus = motif
        devis.save(update_fields=['statut', 'date_refus', 'motif_refus'])
        activity.log_devis_refusal(devis, request.user, motif, date_ref)

        # M6 — événement découplé : ventes émet, crm réagit
        # (marque le lead perdu si demandé et lead_id présent).
        devis_refused.send(
            sender=Devis, devis=devis, user=request.user,
            motif_refus=motif,
            marquer_lead_perdu=marquer_lead_perdu,
        )
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

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
        # M4 — événement découplé : ventes émet, le satellite audit journalise
        # (AuditLog.Action.PDF). ventes n'importe plus apps.audit ; le signal
        # est synchrone (même requête), donc l'acteur/société restent identiques.
        from core.events import document_pdf_generated
        document_pdf_generated.send(
            sender=Devis, instance=devis, kind='devis')
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
        methods=['get', 'post'],
        url_path='layout',
        permission_classes=[IsResponsableOrAdmin],
    )
    def layout(self, request, pk=None):
        """Q1 — lit (GET) ou enregistre (POST) le layout 3D FINALISÉ du devis.

        Le corps POST EST le layout sérialisé (AreaRecord[] + result +
        renderPlan) tel que le produit l'outil roofPro11. La société n'est
        jamais lue du corps : le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (un devis d'une autre société →
        404). Seul ``roof_layout`` est touché ; aucun statut ne bouge
        (préservation des statuts, règle #4)."""
        devis = self.get_object()
        if request.method == 'GET':
            return Response({'roof_layout': devis.roof_layout})
        # POST — le corps entier est le layout (on accepte aussi un wrapper
        # {"roof_layout": …} pour rester souple côté front).
        payload = request.data
        if isinstance(payload, dict) and set(payload.keys()) == {'roof_layout'}:
            payload = payload['roof_layout']
        devis.roof_layout = payload
        devis.save(update_fields=['roof_layout'])
        return Response({'roof_layout': devis.roof_layout})

    @action(
        detail=True,
        methods=['post'],
        url_path='roof-image',
        permission_classes=[IsResponsableOrAdmin],
    )
    def roof_image(self, request, pk=None):
        """Q4 — réceptionne le snapshot PNG 3D et le stocke dans MinIO.

        L'image part dans le bucket PDF existant sous une clé scopée société
        (``roofs/<company>/<reference>.png``) et la clé est mémorisée sur
        ``devis.roof_image``. La société est forcée côté serveur (clé dérivée
        du devis, lui-même borné à la société par ``get_queryset``) ; rien
        n'est lu du corps hors le fichier. Aucun statut ne bouge (règle #4).
        Renvoie l'URL pré-signée de relecture (lecture seule, 1 h)."""
        from ..utils.pdf import upload_roof_image, roof_image_signed_url
        from ..quote_engine.builder import _ensure_pdf_bucket

        upload = request.FILES.get('image') or request.FILES.get('file')
        if upload is None:
            return Response(
                {'detail': "Fichier image manquant (champ « image »)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = upload.read()
        # Validation magic-bytes : PNG (\x89PNG) ou JPEG (\xff\xd8\xff).
        is_png = data[:8] == b'\x89PNG\r\n\x1a\n'
        is_jpeg = data[:3] == b'\xff\xd8\xff'
        if not (is_png or is_jpeg):
            return Response(
                {'detail': 'Image invalide (PNG ou JPEG attendu).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        devis = self.get_object()
        ext = 'png' if is_png else 'jpg'
        ctype = 'image/png' if is_png else 'image/jpeg'
        company_id = getattr(devis, 'company_id', None) or '0'
        key = f'roofs/{company_id}/{devis.reference}.{ext}'
        _ensure_pdf_bucket()
        upload_roof_image(data, key, content_type=ctype)
        devis.roof_image = key
        devis.save(update_fields=['roof_image'])
        return Response(
            {'roof_image': key, 'url': roof_image_signed_url(key)},
            status=status.HTTP_201_CREATED,
        )

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
        from ..services import (
            reserver_stock_devis_facture, StockInsuffisantError,
        )
        company = request.user.company
        try:
            # U9 — la facturation directe par échéancier court-circuite le bon
            # de commande : on réserve/consomme ici le stock matériel du devis,
            # comme le ferait la livraison d'un BC, dans la MÊME transaction que
            # la facture (rollback atomique si la réservation échoue). La garde
            # anti-double-comptage du service évite de re-décompter quand un BC
            # livré existe déjà ou qu'une tranche antérieure a déjà réservé.
            with transaction.atomic():
                reserver_stock_devis_facture(
                    devis=devis, user=request.user, company=company)
                facture = creer_facture_tranche(
                    devis, request.user, company,
                    create_with_reference,
                )
        except StockInsuffisantError as exc:
            return Response(
                {'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )
