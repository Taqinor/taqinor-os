"""Vues FG329 — planification des livraisons (dépôt → site).

``LivraisonViewSet`` : CRUD des livraisons ; référence anti-collision posée
serveur ; cycle ``expedier`` (→ en transit) / ``livrer`` (→ livrée) / ``annuler``
(→ annulée). ``LivraisonLigneViewSet`` : articles d'une livraison. Lecture tout
rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
chantier/dépôt validés tenant. Cross-app : ``stock`` en string-FK.
"""
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import Livraison, LivraisonLigne
from ..serializers import (
    LivraisonSerializer, LivraisonLigneSerializer, RetourLivraisonSerializer,
)
from ..services import (
    ExpeditionImpossible, ventiler_stock_livraison,
    contre_transferer_stock_livraison, generer_retour_livraison,
)
from . import _openapi as oa

#: ACHT20 — message unique d'une livraison expédiée (lignes et en-tête figés).
MESSAGE_LIVRAISON_FIGEE = (
    "Livraison expédiée : annulez-la puis recréez-la.")
#: ACHT20 — champs d'en-tête figés dès `stock_mouvemente=True`.
CHAMPS_FIGES_LIVRAISON = ('depot', 'mode_acheminement', 'installation')


def _exiger_lignes_modifiables(livraison):
    """ACHT20 — les lignes d'une livraison ventilée sont figées."""
    if livraison is not None and livraison.stock_mouvemente:
        raise ValidationError({'livraison': MESSAGE_LIVRAISON_FIGEE})


def _valeur(obj):
    return getattr(obj, 'pk', obj)


READ_ACTIONS = ['list', 'retrieve']

#: ACHT19 (C-ACHT-017) — table de transitions des livraisons, lue par
#: `expedier`, `livrer` et `annuler` : planifiée → en transit → livrée ;
#: annulation seulement avant livraison.
_LS = Livraison.Statut
TRANSITIONS_LIVRAISON = {
    _LS.PLANIFIEE: {_LS.EN_TRANSIT, _LS.ANNULEE},
    _LS.EN_TRANSIT: {_LS.LIVREE, _LS.ANNULEE},
}
_VERBES_LIVRAISON = {
    _LS.EN_TRANSIT: "l'expédier", _LS.LIVREE: 'la livrer',
    _LS.ANNULEE: "l'annuler",
}


def _exiger_transition_livraison(liv, cible):
    """ACHT19 — 400 en français nommant la transition refusée, AVANT tout
    effet (stock, notification, webhook)."""
    if cible in TRANSITIONS_LIVRAISON.get(liv.statut, set()):
        return
    if liv.statut == _LS.PLANIFIEE and cible == _LS.LIVREE:
        raise ValidationError({'statut': "Expédiez d'abord la livraison."})
    raise ValidationError({'statut': (
        f"Livraison {liv.get_statut_display().lower()} : impossible de "
        f"{_VERBES_LIVRAISON.get(cible, 'changer son statut')}.")})


@oa.listing(p0=oa.qs('mode_acheminement'), p1=oa.qs('statut'), p2=oa.qd('date_prevue'), p3=oa.qi('depot'), p4=oa.qi('installation'))
class LivraisonViewSet(oa.JsonOnlyMixin, CompanyScopedModelViewSet):
    """FG329 — livraisons planifiées. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `installation`, `statut`, `depot`,
    `date_prevue`."""
    queryset = Livraison.objects.select_related(
        'installation', 'depot', 'created_by').prefetch_related(
        'lignes__produit').all()
    serializer_class = LivraisonSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        installation = params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        depot = params.get('depot')
        if depot:
            qs = qs.filter(depot_id=depot)
        date_prevue = params.get('date_prevue')
        if date_prevue:
            qs = qs.filter(date_prevue=date_prevue)
        # FG333 — filtre par mode d'acheminement (dépôt vs direct site).
        mode = params.get('mode_acheminement')
        if mode:
            qs = qs.filter(mode_acheminement=mode)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field, label in (
                ('installation', 'Chantier'), ('depot', 'Dépôt'),
                ('transporteur', 'Transporteur')):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: f'{label} inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(Livraison, 'LIV', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        liv = serializer.instance
        if liv.stock_mouvemente:
            actuels = {'depot': liv.depot_id,
                       'mode_acheminement': liv.mode_acheminement,
                       'installation': liv.installation_id}
            modifies = [
                nom for nom in CHAMPS_FIGES_LIVRAISON
                if nom in serializer.validated_data
                and _valeur(serializer.validated_data[nom]) != actuels[nom]]
            if modifies:  # ACHT20
                raise ValidationError(
                    {nom: MESSAGE_LIVRAISON_FIGEE for nom in modifies})
        serializer.save(company=self.request.user.company)

    def _set_statut(self, request, statut):
        liv = self.get_object()
        liv.statut = statut
        liv.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(liv).data)

    def _notify_client(self, liv, statut, request):
        """XSTK22 — notification client best-effort au passage en transit/
        livrée, UNE SEULE FOIS (garde ``notifie_transit_le`` pour le
        transit ; la notification livrée n'a pas besoin de garde dédiée
        car ``livrer`` n'est jamais appelé deux fois par le même flux
        d'action, mais on reste idempotent en ne renvoyant rien si déjà
        notifié pour ce statut)."""
        from .. import livraison_client_notify
        if statut == Livraison.Statut.EN_TRANSIT:
            if liv.notifie_transit_le is not None:
                return
            livraison_client_notify.notify_livraison_transition(
                liv, 'en_transit', request=request)
            liv.notifie_transit_le = timezone.now()
            liv.save(update_fields=['notifie_transit_le'])
        elif statut == Livraison.Statut.LIVREE:
            # ACHT19 — une seule fois (horodatage persisté).
            if liv.notifie_livree_le is not None:
                return
            livraison_client_notify.notify_livraison_transition(
                liv, 'livree', request=request)

    @oa.extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def expedier(self, request, pk=None):
        """FG329 — passe la livraison en transit. YSTCK5 : ventile le stock
        dépôt → van (idempotent, best-effort). XSTK22 : notifie le client
        (best-effort, une seule fois)."""
        from django.db import transaction

        liv = self.get_object()
        _exiger_transition_livraison(liv, Livraison.Statut.EN_TRANSIT)
        # ACHT20 — ventilation exacte PUIS statut, dans la même transaction :
        # une ligne en stock insuffisant refuse l'expédition (400 nommant la
        # ligne), rien n'est transféré ni notifié.
        try:
            with transaction.atomic():
                ventiler_stock_livraison(liv, request.user)
                liv.statut = Livraison.Statut.EN_TRANSIT
                liv.save(update_fields=['statut', 'date_modification'])
        except ExpeditionImpossible as exc:
            raise ValidationError({'lignes': str(exc)})
        self._notify_client(liv, Livraison.Statut.EN_TRANSIT, request)
        return Response(self.get_serializer(liv).data)

    @oa.extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def livrer(self, request, pk=None):
        """FG329 — marque la livraison livrée. XSTK22 : notifie le client
        (best-effort). XSTK23 : émet le webhook public `livraison.livree`
        (best-effort, jamais bloquant, via le SERVICE publicapi — jamais son
        modèle)."""
        liv = self.get_object()
        _exiger_transition_livraison(liv, Livraison.Statut.LIVREE)
        liv.statut = Livraison.Statut.LIVREE
        liv.save(update_fields=['statut', 'date_modification'])
        if liv.notifie_livree_le is None:
            self._notify_client(liv, Livraison.Statut.LIVREE, request)
            try:
                from apps.publicapi.services import notify_livraison_livree
                notify_livraison_livree(
                    company_id=liv.company_id,
                    livraison_id=liv.id,
                    reference=liv.reference,
                    installation_id=liv.installation_id,
                    numero_suivi=liv.numero_suivi,
                )
            except Exception:  # pragma: no cover - défensif, best-effort
                pass
            # ACHT19 — notification + webhook « livrée » : une seule fois.
            liv.notifie_livree_le = timezone.now()
            liv.save(update_fields=['notifie_livree_le'])
        return Response(self.get_serializer(liv).data)

    @oa.extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """FG329 — annule la livraison. YSTCK5 : contre-transfert van → dépôt
        si le stock avait été ventilé (idempotent, best-effort)."""
        liv = self.get_object()
        _exiger_transition_livraison(liv, Livraison.Statut.ANNULEE)
        try:
            contre_transferer_stock_livraison(liv, request.user)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        return self._set_statut(request, Livraison.Statut.ANNULEE)

    @oa.extend_schema(request=oa.body('GenererRetourLivraisonRequete', motif=oa.s()), responses={201: RetourLivraisonSerializer})
    @action(detail=True, methods=['post'], url_path='generer-retour',
            permission_classes=[IsResponsableOrAdmin])
    def generer_retour(self, request, pk=None):
        """ZSTK8 — génère un `RetourLivraison` brouillon pré-rempli depuis
        les lignes livrées. Refuse si la livraison n'est pas LIVREE (rien à
        retourner tant qu'elle n'est pas arrivée)."""
        liv = self.get_object()
        if liv.statut != Livraison.Statut.LIVREE:
            return Response(
                {'detail': 'Seule une livraison livrée peut générer un '
                 'retour.'},
                status=status.HTTP_400_BAD_REQUEST)
        motif = (request.data.get('motif') or '').strip()
        try:
            retour = generer_retour_livraison(liv, request.user, motif=motif)
        except ValueError as exc:  # ACHT21 — « Rien à retourner »
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            RetourLivraisonSerializer(retour).data,
            status=status.HTTP_201_CREATED)

    @oa.extend_schema(responses=oa.PDF)
    @action(detail=True, methods=['get'], url_path='bon-livraison',
            permission_classes=[IsAnyRole])
    def bon_livraison(self, request, pk=None):
        """ZSTK4 — bon de livraison PDF (packing/delivery slip). Client-facing :
        aucun `cout_transport` ni prix d'achat (test dédié)."""
        from django.http import HttpResponse
        from .. import livraison_pdf
        liv = self.get_object()
        pdf_bytes = livraison_pdf.bon_livraison_pdf(liv)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="bon-livraison-{liv.id}.pdf"')
        return resp

    @oa.extend_schema(parameters=[oa.qi('client', required=True)], responses=oa.LIST)
    @action(detail=False, methods=['get'], url_path='portail',
            permission_classes=[IsAnyRole])
    def portail(self, request):
        """XSTK22 — section « Livraisons » du portail client (FG228) : les
        livraisons des chantiers de ``?client=ID``, format plat SANS
        ``cout_transport`` ni prix d'achat (même patron que
        ``monitoring.client_portal``)."""
        from .. import selectors
        company = request.user.company
        client_id = request.query_params.get('client')
        if company is None or not client_id:
            return Response(
                {'detail': 'client requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            selectors.livraisons_client_portail(company, client_id))


@oa.listing(p0=oa.qi('livraison'))
class LivraisonLigneViewSet(oa.JsonOnlyMixin, viewsets.ModelViewSet):
    """FG329 — lignes de livraison. Pas de `company` propre : scope via la
    livraison parente. Filtrable par `livraison`. Lecture tout rôle, écriture
    responsable/admin."""
    queryset = LivraisonLigne.objects.select_related(
        'livraison', 'produit').all()
    serializer_class = LivraisonLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(livraison__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        livraison = self.request.query_params.get('livraison')
        if livraison:
            qs = qs.filter(livraison_id=livraison)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        livraison = serializer.validated_data.get('livraison')
        if livraison is not None and getattr(
                livraison, 'company_id', None) != cid:
            raise ValidationError(
                {'livraison': 'Livraison inconnue pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        _exiger_lignes_modifiables(
            serializer.validated_data.get('livraison'))  # ACHT20
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        _exiger_lignes_modifiables(serializer.instance.livraison)  # ACHT20
        _exiger_lignes_modifiables(serializer.validated_data.get('livraison'))
        serializer.save()

    def perform_destroy(self, instance):
        _exiger_lignes_modifiables(instance.livraison)  # ACHT20
        instance.delete()
