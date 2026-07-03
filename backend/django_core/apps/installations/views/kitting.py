"""Vues FG328 — pré-assemblage / kitting magasin.

``KitViewSet`` : définition des composites + nomenclature. ``KitComposantViewSet``
: composants (BOM). ``OrdreAssemblageViewSet`` : ordres d'assemblage ; référence
anti-collision posée serveur ; cycle ``demarrer`` / ``terminer`` (la
consommation/production de stock reste pilotée par le module stock). Lecture
tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
produit/kit validés tenant. Cross-app : ``stock`` en string-FK.
"""
import copy
from collections import namedtuple

from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference
from apps.ventes.selectors import get_devis_by_pk

from .. import activity_kitting as activity
from ..models import Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne
from ..serializers import (
    KitSerializer, KitComposantSerializer, OrdreAssemblageSerializer,
    OrdreAssemblageActivitySerializer, OrdreAssemblageLigneSerializer,
)
from ..services import (
    seed_reservations_assemblage, release_reservations_assemblage,
    disponibilite_par_ligne, alerter_penurie_assemblage,
    seed_lignes_assemblage,
)

READ_ACTIONS = ['list', 'retrieve']

_ScaledLigne = namedtuple('_ScaledLigne', ['produit', 'quantite'])


class KitViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG328 — kits de pré-assemblage. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `active`."""
    queryset = Kit.objects.select_related(
        'produit_compose', 'created_by').prefetch_related('composants').all()
    serializer_class = KitSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get('active')
        if active in ('0', 'false', 'False'):
            qs = qs.filter(active=False)
        elif active in ('1', 'true', 'True'):
            qs = qs.filter(active=True)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        produit = serializer.validated_data.get('produit_compose')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit_compose': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)


class KitComposantViewSet(viewsets.ModelViewSet):
    """FG328 — composants de kit. Pas de `company` propre : scope via le kit
    parent. Filtrable par `kit`. Lecture tout rôle, écriture
    responsable/admin."""
    queryset = KitComposant.objects.select_related('kit', 'produit').all()
    serializer_class = KitComposantSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(kit__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        kit = self.request.query_params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        kit = serializer.validated_data.get('kit')
        if kit is not None and getattr(kit, 'company_id', None) != cid:
            raise ValidationError(
                {'kit': 'Kit inconnu pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()


class OrdreAssemblageLigneViewSet(viewsets.ModelViewSet):
    """XMFG6 — lignes de composant PERSONNALISABLES d'un ordre. Pas de
    `company` propre : scope via l'ordre parent. Filtrable par `ordre`.
    Éditable UNIQUEMENT tant que l'ordre est planifié (verrouillé dès
    `en_cours`/`termine`/`annule`) — recalcule le coût prévu de l'ordre
    (`OrdreAssemblageSerializer.cout_prevu`, lecture live sur les lignes)."""
    queryset = OrdreAssemblageLigne.objects.select_related('ordre', 'produit').all()
    serializer_class = OrdreAssemblageLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(ordre__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        ordre = self.request.query_params.get('ordre')
        if ordre:
            qs = qs.filter(ordre_id=ordre)
        return qs

    def _check_editable(self, ordre):
        if ordre.statut != OrdreAssemblage.Statut.PLANIFIE:
            raise ValidationError({
                'ordre': "Lignes verrouillées : l'ordre n'est plus planifié."})

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        ordre = serializer.validated_data.get('ordre') or getattr(
            serializer.instance, 'ordre', None)
        if ordre is not None and getattr(ordre, 'company_id', None) != cid:
            raise ValidationError(
                {'ordre': 'Ordre inconnu pour cette société.'})
        if ordre is not None:
            self._check_editable(ordre)
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save(origine=OrdreAssemblageLigne.Origine.AJOUT)

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_editable(instance.ordre)
        instance.delete()


class OrdreAssemblageViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG328 — ordres d'assemblage. Lecture tout rôle, écriture
    responsable/admin. Référence/société/`created_by` posés serveur. Filtrable
    par `statut`, `kit`."""
    queryset = OrdreAssemblage.objects.select_related(
        'kit', 'created_by').all()
    serializer_class = OrdreAssemblageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        kit = params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        responsable = params.get('responsable')
        if responsable:
            qs = qs.filter(responsable_id=responsable)
        date_prevue = params.get('date_prevue')
        if date_prevue:
            qs = qs.filter(date_prevue=date_prevue)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        kit = serializer.validated_data.get('kit')
        if kit is not None and getattr(kit, 'company_id', None) != cid:
            raise ValidationError(
                {'kit': 'Kit inconnu pour cette société.'})
        responsable = serializer.validated_data.get('responsable')
        if responsable is not None and getattr(
                responsable, 'company_id', None) != cid:
            raise ValidationError(
                {'responsable': 'Utilisateur inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(OrdreAssemblage, 'ASM', company, _save)
        # XMFG6 — copie la BOM du kit en lignes éditables AVANT de semer les
        # réservations (XMFG2 lit ces lignes en priorité).
        seed_lignes_assemblage(serializer.instance)
        # XMFG2 — sème les réservations composant depuis la BOM du kit dès la
        # création de l'ordre.
        seed_reservations_assemblage(serializer.instance)
        # XMFG4 — chatter : entrée de création.
        activity.log_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        old = copy.copy(serializer.instance)
        serializer.save(company=self.request.user.company)
        activity.log_changes(old, serializer.instance, self.request.user)

    @action(detail=False, methods=['post'], url_path='depuis-devis')
    def depuis_devis(self, request):
        """XMFG3 — assembler-à-la-commande : pour un devis donné, détecte les
        lignes dont le produit est le `produit_compose` d'un kit actif et crée
        (idempotent, get_or_create par devis+kit) les ordres dimensionnés aux
        quantités des lignes. Renvoie la liste des ordres (créés ou déjà
        existants)."""
        company = self.request.user.company
        devis_id = request.data.get('devis')
        if not devis_id:
            raise ValidationError({'devis': 'Devis requis.'})
        devis = get_devis_by_pk(devis_id)
        if devis is None or devis.company_id != getattr(company, 'id', None):
            raise ValidationError({'devis': 'Devis inconnu pour cette société.'})

        produit_ids = [
            ligne.produit_id for ligne in devis.lignes.all()
            if ligne.produit_id is not None]
        from ..selectors import kit_map_for_produits_composes
        kit_map = kit_map_for_produits_composes(company, produit_ids)
        if not kit_map:
            return Response([])

        kits_by_id = {k.id: k for k in Kit.objects.filter(
            id__in=set(kit_map.values()), company=company)}

        ordres = []
        for ligne in devis.lignes.all():
            kit_id = kit_map.get(ligne.produit_id)
            if kit_id is None:
                continue
            kit = kits_by_id.get(kit_id)
            if kit is None:
                continue
            quantite = int(ligne.quantite) if ligne.quantite else 1
            ordre = OrdreAssemblage.objects.filter(
                company=company, devis=devis, kit=kit).first()
            if ordre is None:
                def _save(reference, kit=kit, quantite=quantite):
                    return OrdreAssemblage.objects.create(
                        company=company, kit=kit, quantite=quantite,
                        devis=devis, created_by=request.user,
                        reference=reference)
                ordre = create_with_reference(
                    OrdreAssemblage, 'ASM', company, _save)
                seed_lignes_assemblage(ordre)
                seed_reservations_assemblage(ordre)
            ordres.append(ordre)
        return Response(
            OrdreAssemblageSerializer(ordres, many=True).data,
            status=201 if ordres else 200)

    @action(detail=True, methods=['get'])
    def disponibilite(self, request, pk=None):
        """XMFG2 — disponibilité par ligne de composant (disponible / partiel
        / manquant, réservation-aware)."""
        ordre = self.get_object()
        return Response(disponibilite_par_ligne(ordre))

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """FG328/XMFG2 — passe l'ordre en cours. Avertit (non bloquant) si des
        composants manquent."""
        ordre = self.get_object()
        old = copy.copy(ordre)
        ordre.statut = OrdreAssemblage.Statut.EN_COURS
        ordre.save(update_fields=['statut', 'date_modification'])
        activity.log_changes(old, ordre, request.user)
        alerter_penurie_assemblage(ordre)
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """XMFG4 — annule l'ordre (motivé). Interdite si le stock a déjà été
        mouvementé (XMFG1) — la traçabilité stock ne peut pas être défaite par
        une simple annulation. Libère les réservations non consommées."""
        ordre = self.get_object()
        if ordre.stock_mouvemente:
            raise ValidationError({
                'statut': "Ordre déjà mouvementé en stock : annulation "
                          "impossible."})
        motif = (request.data.get('motif_annulation') or '').strip()
        if not motif:
            raise ValidationError({
                'motif_annulation': "Le motif d'annulation est requis."})
        old = copy.copy(ordre)
        ordre.statut = OrdreAssemblage.Statut.ANNULE
        ordre.motif_annulation = motif
        ordre.save(update_fields=[
            'statut', 'motif_annulation', 'date_modification'])
        activity.log_changes(old, ordre, request.user)
        release_reservations_assemblage(ordre)
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """XMFG4 — chatter complet de l'ordre."""
        ordre = self.get_object()
        return Response(
            OrdreAssemblageActivitySerializer(
                ordre.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        """XMFG4 — note manuelle sur le chatter de l'ordre."""
        ordre = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(ordre, request.user, body)
        return Response(OrdreAssemblageActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """FG328/XMFG1 — clôture l'ordre (→ terminé, horodate) et backflush le
        stock : consomme les composants du kit, produit le composite. Refuse si
        le kit n'a pas de `produit_compose`. `quantite_produite` (défaut =
        `quantite`) et les emplacements sont éditables au moment de la clôture.
        Idempotent : `stock_mouvemente` empêche une re-clôture de re-mouvementer."""
        from django.db import transaction

        from apps.stock.services import consommer_et_produire_assemblage

        ordre = self.get_object()
        if ordre.kit.produit_compose_id is None:
            raise ValidationError({
                'kit': "Ce kit n'a pas d'article composite "
                       "(produit_compose) : clôture impossible."})

        quantite_produite = request.data.get('quantite_produite')
        try:
            quantite_produite = (
                int(quantite_produite) if quantite_produite not in (None, '')
                else ordre.quantite_produite or ordre.quantite)
        except (TypeError, ValueError):
            raise ValidationError({
                'quantite_produite': 'Quantité produite invalide.'})
        if quantite_produite <= 0:
            raise ValidationError({
                'quantite_produite': 'La quantité produite doit être positive.'})

        emplacement_source_id = request.data.get('emplacement_source')
        emplacement_destination_id = request.data.get('emplacement_destination')

        with transaction.atomic():
            ordre = OrdreAssemblage.objects.select_for_update().get(pk=ordre.pk)
            old = copy.copy(ordre)
            ordre.quantite_produite = quantite_produite
            if emplacement_source_id:
                ordre.emplacement_source_id = emplacement_source_id
            if emplacement_destination_id:
                ordre.emplacement_destination_id = emplacement_destination_id
            already_moved = ordre.stock_mouvemente
            ordre.statut = OrdreAssemblage.Statut.TERMINE
            ordre.date_terminaison = timezone.now()
            update_fields = [
                'statut', 'date_terminaison', 'date_modification',
                'quantite_produite', 'emplacement_source',
                'emplacement_destination']
            if not already_moved:
                lignes = list(ordre.lignes.select_related('produit').all())
                if lignes:
                    # XMFG6 — lignes personnalisées : quantité déjà TOTALE pour
                    # `ordre.quantite`, remise à l'échelle si `quantite_produite`
                    # en diffère (même tolérance sur/sous-production que XMFG1).
                    ratio = (quantite_produite / ordre.quantite
                             if ordre.quantite else 1)
                    composants = [
                        _ScaledLigne(ligne.produit, round(
                            (ligne.quantite or 0) * ratio))
                        for ligne in lignes]
                    consommer_et_produire_assemblage(
                        company=ordre.company, kit=ordre.kit,
                        composants=composants,
                        produit_compose=ordre.kit.produit_compose,
                        quantite_produite=quantite_produite,
                        reference=ordre.reference, user=request.user,
                        emplacement_source=ordre.emplacement_source,
                        emplacement_destination=ordre.emplacement_destination,
                        per_unit=False)
                else:
                    consommer_et_produire_assemblage(
                        company=ordre.company, kit=ordre.kit,
                        composants=ordre.kit.composants.select_related(
                            'produit').all(),
                        produit_compose=ordre.kit.produit_compose,
                        quantite_produite=quantite_produite,
                        reference=ordre.reference, user=request.user,
                        emplacement_source=ordre.emplacement_source,
                        emplacement_destination=ordre.emplacement_destination)
                ordre.stock_mouvemente = True
                update_fields.append('stock_mouvemente')
                # XMFG2 — les réservations composant sont désormais consommées
                # (le stock a été décrémenté par le backflush ci-dessus).
                ordre.reservations.filter(
                    active=True, consomme=False).update(consomme=True)
            ordre.save(update_fields=update_fields)
            activity.log_changes(old, ordre, request.user)
        return Response(self.get_serializer(ordre).data)
