from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class BonCommandeFournisseurViewSet(CompanyScopedModelViewSet):
    """Bons de commande fournisseur (achats). Distinct du BC CLIENT de ventes.

    - référence numérotée sans trou (préfixe BCF) via references.py ;
    - réceptions partielles : l'action `recevoir` incrémente le stock via
      MouvementStock (ENTREE) pour les quantités reçues uniquement ;
    - les prix d'ACHAT restent internes (jamais sur un document client).
    """
    queryset = BonCommandeFournisseur.objects.select_related(
        'fournisseur', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = BonCommandeFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'note']
    ordering_fields = ['date_creation', 'date_commande', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        # QS1 — le PDF (interne) est une LECTURE : il rend exactement les
        # données que `retrieve` expose déjà à tout rôle authentifié. Le
        # laisser en IsResponsableOrAdmin faisait échouer (403) le bouton
        # « PDF (interne) » pour les rôles normaux qui voient pourtant le BCF.
        if self.action in READ_ACTIONS + ['generer_pdf', 'lignes_import']:
            return [IsAnyRole()]
        elif self.action in ('whatsapp', 'envoyer_email'):
            # QS3 — envois fournisseur : permission fine stock_modifier (repli
            # légacy responsable/admin pour les comptes sans rôle fin).
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action in WRITE_ACTIONS + [
            'envoyer', 'recevoir', 'annuler', 'rouvrir', 'confirmer',
            'reviser', 'facturer', 'dupliquer', 'fusionner',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'en_retard':
            return [IsAnyRole()]
        elif self.action in (
                'bcf_similaires', 'historique_prix', 'achats_hors_contrat'):
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _mark_bcf_envoye(self, bc):
        """QS3 — Marque un BCF « envoyé » de façon idempotente et SANS régression.

        Seul un BROUILLON avance vers ENVOYE ; un BCF déjà ENVOYE reste tel quel
        (idempotent) ; RECU et ANNULE ne sont JAMAIS régressés. Renvoie True si
        une transition a eu lieu."""
        if bc.statut == BonCommandeFournisseur.Statut.BROUILLON:
            bc.statut = BonCommandeFournisseur.Statut.ENVOYE
            bc.save(update_fields=['statut'])
            return True
        return False

    @action(detail=True, methods=['post'], url_path='whatsapp')
    def whatsapp(self, request, pk=None):
        """QS3 — Lien wa.me PRÊT à envoyer vers le FOURNISSEUR + lien tokenisé
        vers le PDF du BCF.

        N'envoie RIEN : ouvre WhatsApp avec le message pré-rempli (l'acheteur
        appuie lui-même sur Envoyer). Le {lien} est un lien public tokenisé
        (30 j) vers le PDF du BCF — destiné au FOURNISSEUR (il voit légitimement
        les prix d'achat), imprévisible + expirant, jamais surfacé côté client.

        Marque le BCF « envoyé » (idempotent, ne régresse jamais RECU/ANNULE).
        Le numéro vient de ``fournisseur.telephone``. 400 si aucun numéro."""
        from apps.ventes.utils.phone import normalize_ma_phone
        from apps.ventes.utils.whatsapp import build_wa_url
        from apps.ventes.services import bcf_share_url

        bc = self.get_object()
        phone = bc.fournisseur.telephone if bc.fournisseur_id else ''
        if not normalize_ma_phone(phone):
            return Response(
                {'detail': 'Aucun numéro de téléphone fournisseur.'},
                status=status.HTTP_400_BAD_REQUEST)
        url, _token = bcf_share_url(bc, request)
        fournisseur_nom = bc.fournisseur.nom if bc.fournisseur_id else ''
        message = (
            f'Bonjour {fournisseur_nom},\n\n'
            f'Voici notre bon de commande {bc.reference}. '
            f'Vous pouvez le consulter ici : {url}\n\n'
            f'Merci de nous confirmer la disponibilité.')
        self._mark_bcf_envoye(bc)
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.WHATSAPP, instance=bc,
                   detail=f'Lien WhatsApp BCF {bc.reference} préparé')
        except Exception:  # noqa: BLE001 — l'audit ne casse jamais l'action
            pass
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': url,
            'statut': bc.statut,
        })

    @action(detail=True, methods=['post'], url_path='envoyer-email')
    def envoyer_email(self, request, pk=None):
        """QS3 — Envoie le BCF (PDF joint) au FOURNISSEUR par email + EmailLog.

        Le PDF est rendu à la volée (montre les prix d'achat — légitime pour le
        fournisseur). L'envoi + la trace EmailLog passent par le service ventes
        ``log_supplier_email`` (stock n'importe pas ventes.models). NO-OP réseau
        sans clé (backend console), l'entrée EmailLog est tout de même écrite.
        Marque le BCF « envoyé » (idempotent, ne régresse jamais RECU/ANNULE).

        Body optionnel : ``to_email`` (défaut : email du fournisseur),
        ``sujet``, ``corps``."""
        from apps.ventes.services import log_supplier_email
        from ..utils.pdf_fournisseur import generate_bcf_pdf

        bc = self.get_object()
        to_email = ((request.data.get('to_email') or '').strip()
                    or (bc.fournisseur.email if bc.fournisseur_id else '')
                    or '')
        if not to_email:
            return Response(
                {'detail': 'Aucune adresse email fournisseur.'},
                status=status.HTTP_400_BAD_REQUEST)

        # PDF du BCF (rendu à la volée) — indisponible n'empêche pas l'email.
        attachment = attachment_name = None
        try:
            attachment = generate_bcf_pdf(bc)
            attachment_name = f'{bc.reference}.pdf'
        except Exception:  # noqa: BLE001
            pass

        fournisseur_nom = bc.fournisseur.nom if bc.fournisseur_id else ''
        sujet = ((request.data.get('sujet') or '').strip()
                 or f'Bon de commande {bc.reference}')
        corps = ((request.data.get('corps') or '').strip() or (
            f'Bonjour {fournisseur_nom},\n\n'
            f'Veuillez trouver ci-joint notre bon de commande '
            f'{bc.reference}.\n\n'
            f'Merci de nous confirmer la disponibilité.\n\n'
            f'Cordialement,'))

        ok, log = log_supplier_email(
            company=bc.company, to_email=to_email, sujet=sujet, corps=corps,
            attachment=attachment, attachment_name=attachment_name,
            reference=bc.reference, user=request.user)
        self._mark_bcf_envoye(bc)
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.EMAIL, instance=bc,
                   detail=f'Email BCF {bc.reference} envoyé à {to_email}')
        except Exception:  # noqa: BLE001
            pass
        return Response({
            'detail': (f'Email envoyé à {to_email}.' if ok
                       else "Échec de l'envoi de l'email."),
            'log_id': log.id, 'email_statut': log.statut,
            'statut': bc.statut,
        })

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            # ZPUR8 — l'acheteur par défaut est le créateur (éditable
            # ensuite), sauf si explicitement fourni dans le corps.
            extra = {}
            if not serializer.validated_data.get('acheteur'):
                extra['acheteur'] = self.request.user
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
                **extra,
            )
        bc = create_with_reference(
            BonCommandeFournisseur, 'BCF', company, _save)
        # ZPUR8 — reporte les défauts fournisseur (incoterm/conditions de
        # paiement) au document, une fois, sans écraser une valeur déjà
        # fournie. Best-effort : ne bloque jamais la création.
        try:
            from ..services import default_other_information_bcf
            default_other_information_bcf(bc)
        except Exception:  # noqa: BLE001
            pass

    def create(self, request, *args, **kwargs):
        # XPUR4 — refuse la création si le fournisseur est bloqué commandes
        # (ou total). No-op pour un fournisseur actif (comportement
        # historique).
        fournisseur_id = request.data.get('fournisseur')
        if fournisseur_id:
            try:
                from ..services import check_fournisseur_statut_commande
                fournisseur = Fournisseur.objects.get(
                    pk=fournisseur_id, company=request.user.company)
                check_fournisseur_statut_commande(fournisseur)
            except Fournisseur.DoesNotExist:
                pass
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # XPUR1 — WARNING (non bloquant) si le fournisseur a un document de
        # conformité manquant/expiré ; ajouté à la réponse sans jamais
        # empêcher la création du BCF.
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            try:
                from ..services import bcf_warning_conformite
                bc = BonCommandeFournisseur.objects.select_related(
                    'fournisseur').get(pk=response.data['id'])
                warning = bcf_warning_conformite(bc.fournisseur)
                if warning:
                    response.data['conformite_warning'] = warning
            except Exception:  # noqa: BLE001 — le warning ne casse jamais
                pass
            self._attach_prix_warnings(response, request)
        return response

    def update(self, request, *args, **kwargs):
        # XPUR18 — un BCF ENVOYE/RECU se modifie UNIQUEMENT via l'action
        # `reviser` (tracée + ré-approbation) : l'édition directe (PUT/PATCH)
        # est refusée après l'envoi. Un BROUILLON garde l'édition normale
        # (comportement historique inchangé).
        bc = self.get_object()
        if bc.statut in (
            BonCommandeFournisseur.Statut.ENVOYE,
            BonCommandeFournisseur.Statut.RECU,
        ):
            return Response(
                {'detail': (
                    "Ce BCF a été envoyé : utilisez l'action « réviser » "
                    'pour le modifier (traçabilité + ré-approbation).')},
                status=status.HTTP_400_BAD_REQUEST)
        response = super().update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            self._attach_prix_warnings(response, request)
        return response

    @action(detail=True, methods=['post'], url_path='reviser')
    def reviser(self, request, pk=None):
        """XPUR18 — SEUL chemin de modification d'un BCF déjà ENVOYE/RECU :
        journalise chaque changement (ancien→nouveau, records.Comment),
        incrémente `revision`, ré-exige une approbation FG312 si le montant
        augmente au-delà du seuil en vigueur. Corps optionnel :
        ``{"date_commande": "...", "date_livraison_prevue": "...",
        "note": "...", "lignes": [{"id": <id>, "quantite": ..., "prix_achat_unitaire": ..., "designation": "..."}]}``."""
        from ..services import reviser_bcf
        bc = self.get_object()
        try:
            bc, reapprobation_requise = reviser_bcf(
                request.user.company, request.user, bc,
                lignes=request.data.get('lignes'),
                date_commande=request.data.get('date_commande'),
                date_livraison_prevue=request.data.get(
                    'date_livraison_prevue'),
                note=request.data.get('note'),
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = self.get_serializer(bc).data
        data['reapprobation_requise'] = reapprobation_requise
        return Response(data)

    def _attach_prix_warnings(self, response, request):
        """XPUR13 — WARNING (non bloquant) : ajoute `prix_warnings` à la
        réponse pour chaque ligne dont le prix saisi dépasse le contrat en
        vigueur ou dévie au-delà du seuil société. Ne bloque jamais la
        création/mise à jour."""
        try:
            from ..services import check_prix_ligne_bcf
            fournisseur_id = response.data.get('fournisseur')
            lignes = response.data.get('lignes') or []
            prix_warnings = []
            for ligne in lignes:
                produit_id = ligne.get('produit')
                prix_saisi = ligne.get('prix_achat_unitaire')
                if not produit_id or prix_saisi is None:
                    continue
                result = check_prix_ligne_bcf(
                    request.user.company, produit_id=produit_id,
                    fournisseur_id=fournisseur_id, prix_saisi=prix_saisi)
                if result['warnings']:
                    prix_warnings.append({
                        'ligne_id': ligne.get('id'),
                        'produit': produit_id,
                        'warnings': result['warnings'],
                    })
            if prix_warnings:
                response.data['prix_warnings'] = prix_warnings
        except Exception:  # noqa: BLE001 — le warning ne casse jamais
            pass

    @action(detail=True, methods=['post'], url_path='envoyer')
    def envoyer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommandeFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un BCF en brouillon peut être envoyé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # YPROC4 — l'approbation par palier (FG312) doit BLOQUER l'envoi :
        # sans seuil configuré pour la société, comportement strictement
        # inchangé (le sélecteur renvoie True). Import paresseux (précédent
        # existant : stock.services.reserved_quantity importe déjà
        # apps.installations.selectors en lazy).
        from apps.installations.selectors import (
            bcf_approbation_valide, palier_manquant_bcf_detail,
        )
        if not bcf_approbation_valide(bc.company, bc.id, bc.total_achat):
            palier = palier_manquant_bcf_detail(bc.company, bc.total_achat)
            return Response(
                {'detail': (
                    "Ce BCF dépasse le seuil d'approbation : une "
                    f"approbation au palier « {palier} » est requise avant "
                    'envoi (le montant a peut-être augmenté depuis une '
                    'approbation existante).')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ENVOYE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommandeFournisseur.Statut.RECU:
            return Response(
                {'detail': 'Un BCF entièrement reçu ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # ZPUR11 — motif OBLIGATOIRE (400 si vide), tracé horodaté + acteur.
        motif = (request.data.get('motif_annulation') or '').strip()
        if not motif:
            return Response(
                {'detail': "Un motif d'annulation est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ANNULE
        bc.motif_annulation = motif
        bc.save(update_fields=['statut', 'motif_annulation'])
        from ..services import log_bcf_chatter
        log_bcf_chatter(
            bc, user=request.user,
            body=f'BCF annulé — motif : {motif}')
        # YPROC7 — cascade : les réceptions brouillon de ce BCF ne doivent
        # plus jamais être confirmables, et le créateur est notifié
        # (best-effort). Un BCF partiellement reçu reste annulable
        # (comportement inchangé) ; le détail des quantités déjà entrées en
        # stock est renvoyé pour décision (retour fournisseur éventuel).
        from ..services import annuler_bcf_cascade
        detail_cascade = annuler_bcf_cascade(bc, user=request.user)
        data = self.get_serializer(bc).data
        data['cascade'] = detail_cascade
        return Response(data)

    @action(detail=True, methods=['post'], url_path='rouvrir')
    def rouvrir(self, request, pk=None):
        """ZPUR11 — réouvre un BCF ANNULE en BROUILLON (jamais si des
        réceptions CONFIRME existent — refus explicite 400). Journalise la
        réouverture (chatter, acteur + horodatage)."""
        bc = self.get_object()
        if bc.statut != BonCommandeFournisseur.Statut.ANNULE:
            return Response(
                {'detail': 'Seul un BCF annulé peut être réouvert.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if bc.receptions.filter(
                statut=ReceptionFournisseur.Statut.CONFIRME).exists():
            return Response(
                {'detail': (
                    'Ce BCF a des réceptions confirmées : impossible de le '
                    'réouvrir.')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.BROUILLON
        bc.save(update_fields=['statut'])
        from ..services import log_bcf_chatter
        log_bcf_chatter(
            bc, user=request.user,
            body='BCF réouvert (repassé en brouillon).')
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='confirmer')
    def confirmer(self, request, pk=None):
        """XPUR7 — accusé de commande fournisseur : date confirmée + numéro
        de confirmation. La date DEMANDÉE d'origine (`date_livraison_prevue`)
        n'est jamais écrasée (préserve l'OTD promis-vs-reçu). Corps :
        ``{"date_confirmee_fournisseur": "YYYY-MM-DD",
        "numero_confirmation_fournisseur": "..."}``."""
        bc = self.get_object()
        date_confirmee = request.data.get('date_confirmee_fournisseur')
        if not date_confirmee:
            return Response(
                {'detail': 'date_confirmee_fournisseur est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        bc.date_confirmee_fournisseur = date_confirmee
        bc.numero_confirmation_fournisseur = (
            request.data.get('numero_confirmation_fournisseur') or '')
        bc.save(update_fields=[
            'date_confirmee_fournisseur', 'numero_confirmation_fournisseur'])
        return Response(self.get_serializer(bc).data)

    @action(detail=False, methods=['get'], url_path='bcf-similaires')
    def bcf_similaires(self, request):
        """XPUR11 — panneau « BCF ouverts similaires » : BCF brouillon/envoyé
        du même fournisseur (optionnellement filtrés aux produits communs).
        Query params : ``fournisseur`` (requis), ``produits`` (ids séparés
        par virgule, optionnel). LECTURE SEULE, jamais bloquant."""
        from ..services import bcf_similaires_ouverts
        fournisseur_id = request.query_params.get('fournisseur')
        if not fournisseur_id:
            return Response(
                {'detail': 'Le paramètre fournisseur est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        produits_param = request.query_params.get('produits') or ''
        produit_ids = [
            int(p) for p in produits_param.split(',') if p.strip().isdigit()
        ]
        similaires = bcf_similaires_ouverts(
            request.user.company, fournisseur_id=fournisseur_id,
            produit_ids=produit_ids)
        return Response(similaires)

    @action(detail=False, methods=['get'], url_path='historique-prix')
    def historique_prix(self, request):
        """XPUR13 — popover « historique des prix » : derniers achats (toutes
        sources) d'un produit, optionnellement filtrés à un fournisseur.
        Query params : ``produit`` (requis), ``fournisseur`` (optionnel).
        LECTURE SEULE."""
        from ..services import historique_prix_produit
        produit_id = request.query_params.get('produit')
        if not produit_id:
            return Response(
                {'detail': 'Le paramètre produit est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        fournisseur_id = request.query_params.get('fournisseur')
        historique = historique_prix_produit(
            request.user.company, produit_id, fournisseur_id=fournisseur_id)
        return Response(historique)

    @action(detail=False, methods=['get'], url_path='achats-hors-contrat')
    def achats_hors_contrat(self, request):
        """XPUR13 — rapport « achats hors contrat » : lignes de BCF dont le
        prix dépasse le prix convenu du contrat en vigueur, filtrable par
        fournisseur/période. LECTURE SEULE."""
        from ..services import rapport_achats_hors_contrat
        fournisseur_id = request.query_params.get('fournisseur')
        date_debut = request.query_params.get('date_debut')
        date_fin = request.query_params.get('date_fin')
        rapport = rapport_achats_hors_contrat(
            request.user.company, fournisseur_id=fournisseur_id,
            date_debut=date_debut, date_fin=date_fin)
        return Response(rapport)

    @action(detail=False, methods=['get'], url_path='en-retard')
    def en_retard(self, request):
        """XPUR7 — liste des BCF ENVOYE en retard (prévue/confirmée dépassée
        sans réception complète). LECTURE SEULE."""
        from ..services import bcf_en_retard_list
        en_retard = bcf_en_retard_list(request.user.company)
        return Response(self.get_serializer(en_retard, many=True).data)

    @action(detail=True, methods=['post'], url_path='recevoir')
    def recevoir(self, request, pk=None):
        """Réception (totale ou partielle) — incrémente le stock par ENTREE.

        Corps : {"receptions": [{"ligne": <id>, "quantite": <int>}, ...]}.
        Idempotent/sûr : on ne reçoit jamais plus que le reste dû ; le stock
        n'augmente que des quantités effectivement reçues.
        """
        bc = self.get_object()
        if bc.statut in (
            BonCommandeFournisseur.Statut.BROUILLON,
            BonCommandeFournisseur.Statut.ANNULE,
            BonCommandeFournisseur.Statut.RECU,
        ):
            return Response(
                {'detail': (
                    'Seul un BCF envoyé (non encore entièrement reçu) '
                    'peut recevoir des quantités.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receptions = request.data.get('receptions') or []
        if not isinstance(receptions, list) or not receptions:
            return Response(
                {'detail': 'Aucune réception fournie.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Index par id de ligne (scopé à ce BC uniquement).
        lignes = {ligne.id: ligne for ligne in bc.lignes.select_related(
            'produit')}
        from ..services import (
            convertir_en_unites_stock, resoudre_conditionnement,
        )
        plan = []
        for rec in receptions:
            try:
                ligne_id = int(rec.get('ligne'))
                qte = int(rec.get('quantite'))
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Réception invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ligne = lignes.get(ligne_id)
            if ligne is None:
                return Response(
                    {'detail': f'Ligne {ligne_id} introuvable sur ce BCF.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if qte <= 0:
                continue
            # XSTK15 — conditionnement optionnel (touret/carton…) : la
            # quantité saisie compte des CONDITIONNEMENTS, convertie en
            # unités de stock avant tout plafonnement (comportement
            # historique inchangé quand aucun conditionnement n'est fourni).
            conditionnement = resoudre_conditionnement(
                bc.company,
                conditionnement_id=rec.get('conditionnement'),
                code_barres=rec.get('conditionnement_code_barres'))
            if conditionnement is not None:
                qte = convertir_en_unites_stock(qte, conditionnement)
            # Plafonnement au reste dû — jamais plus que commandé (idempotence).
            qte = min(qte, ligne.quantite_restante)
            if qte > 0:
                plan.append((ligne, qte))

        if not plan:
            return Response(
                {'detail': 'Rien à recevoir (quantités déjà reçues).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        from ..services import (
            record_purchase_price, credit_emplacement_destination,
            affecter_livraison_directe_chantier,
        )
        today = timezone.now().date()
        with transaction.atomic():
            for ligne, qte in plan:
                # XPUR16 — ligne libre/service (sans_stock ou produit=null) :
                # aucun MouvementStock, la quantité reçue est simplement
                # actée (compte pour le total/l'approbation/la facturation).
                if ligne.sans_stock or ligne.produit_id is None:
                    ligne.quantite_recue += qte
                    ligne.save(update_fields=['quantite_recue'])
                    continue
                # ERR24 — verrou de ligne produit dans la transaction pour que
                # des réceptions concurrentes du même produit ne perdent pas
                # d'incrément (au lieu d'un simple refresh_from_db sans verrou).
                produit = (Produit.objects.select_for_update()
                           .get(pk=ligne.produit_id))
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + qte
                MouvementStock.objects.create(
                    company=bc.company,
                    produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                    quantite=qte,
                    quantite_avant=qte_avant,
                    quantite_apres=qte_apres,
                    reference=bc.reference,
                    note=f'Réception BCF {bc.reference}',
                    created_by=request.user,
                )
                produit.quantite_stock = qte_apres
                produit.save(update_fields=['quantite_stock'])
                ligne.quantite_recue += qte
                ligne.save(update_fields=['quantite_recue'])
                # N17 — mémorise le prix d'achat (interne) chez ce fournisseur.
                record_purchase_price(
                    company=bc.company, produit=produit,
                    fournisseur=bc.fournisseur,
                    prix_achat=ligne.prix_achat_unitaire, date=today)
                # XPUR23 — destination de réception : dépôt cible OU
                # chantier de livraison directe (l'un ou l'autre, jamais les
                # deux en usage normal ; défaut = dépôt principal inchangé).
                if bc.chantier_livraison_id:
                    affecter_livraison_directe_chantier(
                        bc.company, request.user, bc, produit, qte,
                        bc.reference)
                elif bc.emplacement_destination_id:
                    credit_emplacement_destination(
                        bc.company, produit, bc.emplacement_destination, qte)
            bc.refresh_from_db()
            if bc.est_entierement_recu:
                bc.statut = BonCommandeFournisseur.Statut.RECU
                bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def generer_pdf(self, request, pk=None):
        """PDF fournisseur (INTERNE — montre les prix d'achat). Jamais un
        document client."""
        from ..utils.pdf_fournisseur import generate_bcf_pdf
        bc = self.get_object()
        pdf_bytes = generate_bcf_pdf(bc)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ fournisseur _ référence). Le
        # segment « fournisseur » réutilise le paramètre client du helper
        # (Fournisseur porte .nom) — jamais de prix d'achat dans le nom.
        from apps.ventes.utils.filenames import document_filename
        filename = document_filename(
            'Bon-de-commande', bc.reference,
            client=bc.fournisseur if bc.fournisseur_id else None,
            company=bc.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"')
        return response

    @action(detail=True, methods=['get'], url_path='lignes-import')
    def lignes_import(self, request, pk=None):
        """XSTK19 — lignes candidates pour un dossier d'import ADII,
        pré-remplies (code SH + pays d'origine) depuis les SKUs de ce BCF."""
        from ..selectors import lignes_import_depuis_bcf
        bc = self.get_object()
        return Response(lignes_import_depuis_bcf(request.user.company, bc.pk))

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, pk=None):
        """ZPUR4 — clone ce BCF en un nouveau BROUILLON (nouvelle référence,
        quantités reçues à zéro, statut réinitialisé), copiant fournisseur +
        lignes. La source n'est jamais modifiée."""
        from ..services import dupliquer_bcf
        bc = self.get_object()
        clone = dupliquer_bcf(request.user.company, request.user, bc)
        return Response(
            self.get_serializer(clone).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='fusionner')
    def fusionner(self, request):
        """ZPUR6 — fusionne plusieurs BCF BROUILLON du MÊME fournisseur (et
        de cette société) en un BCF cible unique aux quantités cumulées par
        produit ; les BCF sources passent en `annule` avec une note de
        fusion. Corps : ``{"bons_commande": [id, id, ...]}`` (≥ 2 requis)."""
        from ..services import fusionner_bcf
        ids = request.data.get('bons_commande') or []
        if not isinstance(ids, list):
            return Response(
                {'detail': 'bons_commande doit être une liste d\'ids.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            cible = fusionner_bcf(request.user.company, request.user, ids)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(cible).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='facturer')
    def facturer(self, request, pk=None):
        """ZPUR1 — facture DIRECTEMENT ce BCF depuis ses lignes « sur
        commande » (`Produit.politique_facturation_achat`), SANS exiger de
        réception préalable. Les lignes « sur réception » (défaut) restent
        hors de ce chemin — elles ne se facturent que via FG56
        (`receptions-fournisseur/{id}/facturer/`)."""
        from ..services import facturer_bcf_sur_commande
        bc = self.get_object()
        try:
            facture = facturer_bcf_sur_commande(
                company=request.user.company, user=request.user,
                bon_commande=bc)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FactureFournisseurSerializer(
                facture, context={'request': request}).data,
            status=status.HTTP_201_CREATED)
