from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from authentication.mixins import TenantMixin  # noqa: F401
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


class BonCommandeFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
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
        if self.action in READ_ACTIONS + ['generer_pdf']:
            return [IsAnyRole()]
        elif self.action in ('whatsapp', 'envoyer_email'):
            # QS3 — envois fournisseur : permission fine stock_modifier (repli
            # légacy responsable/admin pour les comptes sans rôle fin).
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action in WRITE_ACTIONS + [
            'envoyer', 'recevoir', 'annuler',
        ]:
            return [IsResponsableOrAdmin()]
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
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(
            BonCommandeFournisseur, 'BCF', company, _save)

    def create(self, request, *args, **kwargs):
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
        return response

    @action(detail=True, methods=['post'], url_path='envoyer')
    def envoyer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommandeFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un BCF en brouillon peut être envoyé.'},
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
        bc.statut = BonCommandeFournisseur.Statut.ANNULE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

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
        from ..services import record_purchase_price
        today = timezone.now().date()
        with transaction.atomic():
            for ligne, qte in plan:
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
