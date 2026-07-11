"""Vues FG310 — demande d'achat (réquisition) → approbation.

``DemandeAchatViewSet`` : CRUD des réquisitions d'achat chantier + cycle de vie
(``soumettre`` / ``approuver`` / ``refuser`` / ``marquer_commandee``).
``DemandeAchatLigneViewSet`` : CRUD des lignes (produit catalogue OU désignation
libre). Lecture tout rôle, écriture responsable/admin ; APPROBATION réservée
responsable/admin (FG310 : la réquisition doit être approuvée avant de devenir un
BCF). Multi-tenant via ``TenantMixin`` : référence/société/created_by posés côté
serveur ; les FK liées (chantier/programme/fournisseur_suggere) sont validées
tenant. Cross-app : ``stock.Fournisseur`` / ``stock.Produit`` en string-FK.

SCA36 — pilote 3 du kit ``core.documents`` (dégradation gracieuse sans totaux).
Le viewset gagne le chatter générique ARC8 (``ChatterViewSetMixin`` :
``chatter/historique`` GET tout rôle + ``chatter/noter`` POST
responsable/admin) ; la numérotation passe EXPLICITEMENT par la primitive du
kit ``core.numbering`` (le shim ``apps.ventes.utils.references`` en était déjà
le ré-export bit-identique — format ``DA-YYYYMM-NNNN`` inchangé). Les actions
d'approbation et leurs gardes restent STRICTEMENT inchangées (moteur propre,
chemin ARC10 nommé) ; aucun PDF (document d'approbation interne).
"""
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.numbering import create_with_reference
from core.viewsets import CompanyScopedModelViewSet

from apps.records.views import ChatterViewSetMixin

from ..models import DemandeAchat, DemandeAchatLigne
from ..serializers import DemandeAchatSerializer, DemandeAchatLigneSerializer

# SCA36 — 'chatter_historique' est une lecture (patron flotte : le
# get_permissions maison prime sur les permission_classes d'@action du mixin).
READ_ACTIONS = ['list', 'retrieve', 'chatter_historique']


def _check_tenant(serializer, company, field):
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})


def _notifier_demandeur_decision(da, approuvee):
    """VX213 (c) — bord RETOUR : notifie le DEMANDEUR (``created_by``) de la
    décision d'approbation de sa réquisition (motif inclus si refus).

    Best-effort (ne lève jamais) : émettre la notification ne doit jamais
    casser la transition d'approbation. No-op si aucun demandeur. Le corps
    reste CLIENT-SAFE — aucun montant (jamais dérivé de ``prix_achat``) : la
    décision porte sur la référence + l'objet, pas sur un prix d'achat interne.
    La société est celle de la DA (jamais issue d'une requête)."""
    demandeur = getattr(da, 'created_by', None)
    if demandeur is None or not getattr(demandeur, 'pk', None):
        return
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        if approuvee:
            titre = f"Demande d'achat approuvée — {da.reference}"
            corps = f"Votre demande « {da.objet} » ({da.reference}) a été approuvée."
        else:
            titre = f"Demande d'achat refusée — {da.reference}"
            corps = f"Votre demande « {da.objet} » ({da.reference}) a été refusée."
            if da.motif_refus:
                corps += f" Motif : {da.motif_refus}"
        notify(
            demandeur, EventType.DA_DECIDEE, titre, body=corps,
            link=f'/installations/demandes-achat?demande={da.pk}',
            company=da.company)
    except Exception:  # pragma: no cover - défensif
        pass


class DemandeAchatViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """FG310 — réquisitions d'achat. Lecture tout rôle, écriture
    responsable/admin. Référence anti-collision + société + `created_by` posés
    serveur ; chantier/programme/fournisseur_suggere validés tenant. Filtrable
    par `statut`, `chantier`, `programme`. Cycle de vie via les actions.
    SCA36 — chatter générique (`chatter/historique`, `chatter/noter`) via le
    kit ; approbations inchangées."""
    queryset = DemandeAchat.objects.select_related(
        'chantier', 'programme', 'fournisseur_suggere',
        'approuvee_par', 'created_by').prefetch_related('lignes').all()
    serializer_class = DemandeAchatSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('statut', 'statut'),
                         ('chantier', 'chantier_id'),
                         ('programme', 'programme_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs

    def _check_all_tenant(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'chantier')
        _check_tenant(serializer, company, 'programme')
        _check_tenant(serializer, company, 'fournisseur_suggere')

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_all_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(DemandeAchat, 'DA', company, _save)

    def perform_update(self, serializer):
        self._check_all_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        """FG310 — soumet la demande pour approbation (brouillon → soumise)."""
        da = self.get_object()
        if da.statut not in (DemandeAchat.Statut.BROUILLON,
                             DemandeAchat.Statut.SOUMISE):
            return Response(
                {'detail': "Seule une demande brouillon peut être soumise."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """FG310 — approuve la demande (soumise → approuvée), prérequis avant
        transformation en BCF. Trace l'approbateur + la date."""
        da = self.get_object()
        if da.statut != DemandeAchat.Statut.SOUMISE:
            return Response(
                {'detail': "Seule une demande soumise peut être approuvée."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.APPROUVEE
        da.approuvee_par = request.user
        da.date_decision = timezone.now()
        da.motif_refus = None
        da.save(update_fields=['statut', 'approuvee_par', 'date_decision',
                               'motif_refus', 'date_modification'])
        _notifier_demandeur_decision(da, approuvee=True)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """FG310 — refuse la demande (soumise → refusée) avec un motif."""
        da = self.get_object()
        if da.statut != DemandeAchat.Statut.SOUMISE:
            return Response(
                {'detail': "Seule une demande soumise peut être refusée."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.REFUSEE
        da.approuvee_par = request.user
        da.date_decision = timezone.now()
        da.motif_refus = (request.data.get('motif_refus') or '').strip() or None
        da.save(update_fields=['statut', 'approuvee_par', 'date_decision',
                               'motif_refus', 'date_modification'])
        _notifier_demandeur_decision(da, approuvee=False)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'])
    def marquer_commandee(self, request, pk=None):
        """FG310 — marque la demande comme commandée (approuvée → commandée),
        une fois le BCF émis. Garde : seule une demande APPROUVÉE peut l'être."""
        da = self.get_object()
        if da.statut != DemandeAchat.Statut.APPROUVEE:
            return Response(
                {'detail': "Seule une demande approuvée peut être marquée "
                           "commandée."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.COMMANDEE
        da.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'], url_path='generer-bcf')
    def generer_bcf(self, request, pk=None):
        """YPROC5 — convertit les lignes de la DA APPROUVÉE en BCF brouillon
        chez le fournisseur choisi (corps, défaut `fournisseur_suggere`).
        Idempotent : une DA déjà commandée avec un BCF lié est refusée."""
        from django.apps import apps as django_apps
        from apps.stock.services import creer_bcf_depuis_lignes

        da = self.get_object()
        if da.statut != DemandeAchat.Statut.APPROUVEE:
            return Response(
                {'detail': "Seule une demande approuvée peut générer un BCF."},
                status=status.HTTP_400_BAD_REQUEST)
        if da.bon_commande_id:
            return Response(
                {'detail': 'Cette demande a déjà un BCF lié.'},
                status=status.HTTP_400_BAD_REQUEST)

        fournisseur_id = request.data.get('fournisseur') or (
            da.fournisseur_suggere_id)
        if not fournisseur_id:
            return Response(
                {'detail': 'Aucun fournisseur (ni suggéré, ni fourni).'},
                status=status.HTTP_400_BAD_REQUEST)
        fournisseur_model = django_apps.get_model('stock', 'Fournisseur')
        fournisseur = fournisseur_model.objects.filter(
            id=fournisseur_id, company=request.user.company).first()
        if fournisseur is None:
            return Response(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)

        lignes_source = list(da.lignes.select_related('produit').all())
        # XPUR16 — les lignes sans produit catalogue sont reportées en
        # désignation libre (jamais ignorées : couverture complète de la DA).
        lignes = [
            (ligne.produit_id, ligne.designation or
             (ligne.produit.nom if ligne.produit_id else ''),
             ligne.quantite, ligne.prix_estime)
            for ligne in lignes_source
        ]
        if not lignes:
            return Response(
                {'detail': 'Cette demande ne contient aucune ligne.'},
                status=status.HTTP_400_BAD_REQUEST)

        bon = creer_bcf_depuis_lignes(
            company=request.user.company, user=request.user,
            fournisseur=fournisseur, lignes=lignes,
            note=f'Généré depuis {da.reference}')
        da.bon_commande = bon
        da.statut = DemandeAchat.Statut.COMMANDEE
        da.save(update_fields=['bon_commande', 'statut', 'date_modification'])
        return Response(self.get_serializer(da).data)


class DemandeAchatLigneViewSet(viewsets.ModelViewSet):
    """FG310 — lignes de demande d'achat. La ligne n'a pas de `company` propre :
    le scope société passe par la demande parente (`demande__company`).
    Filtrable par `demande`. Lecture tout rôle, écriture responsable/admin."""
    queryset = DemandeAchatLigne.objects.select_related(
        'demande', 'produit').all()
    serializer_class = DemandeAchatLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(demande__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        demande = self.request.query_params.get('demande')
        if demande:
            qs = qs.filter(demande_id=demande)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        demande = serializer.validated_data.get('demande')
        if demande is not None and getattr(
                demande, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'demande': 'Demande inconnue pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
