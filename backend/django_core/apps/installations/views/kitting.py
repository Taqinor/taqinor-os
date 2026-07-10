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

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference
from apps.ventes.selectors import get_devis_by_pk

from .. import activity_kitting as activity
from ..models import (
    Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne,
    OrdreDemontage, OrdreDemontageLigne, ControleQualiteModele,
    EtapeAssemblage,
)
from ..serializers import (
    KitSerializer, KitComposantSerializer, OrdreAssemblageSerializer,
    OrdreAssemblageActivitySerializer, OrdreAssemblageLigneSerializer,
    SerieAssemblageSerializer, OrdreDemontageSerializer,
    OrdreDemontageLigneSerializer, ControleQualiteModeleSerializer,
    ControleQualiteOrdreSerializer, EtapeAssemblageSerializer,
    EtapeOrdreSerializer,
)
from ..services import (
    seed_reservations_assemblage, release_reservations_assemblage,
    disponibilite_par_ligne, alerter_penurie_assemblage,
    seed_lignes_assemblage, enregistrer_series_assemblage,
    etiquette_items_assemblage, seed_lignes_demontage,
    instancier_controle_qualite, controle_qualite_bloque_cloture,
    enregistrer_controle_qualite, instancier_etapes_ordre,
    cocher_etape_ordre,
)

READ_ACTIONS = ['list', 'retrieve']

_ScaledLigne = namedtuple('_ScaledLigne', ['produit', 'quantite'])


class KitViewSet(CompanyScopedModelViewSet):
    """FG328 — kits de pré-assemblage. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `active`. XMFG18 : révisions de
    nomenclature (`revisions/`, `composition-au/`) + `dupliquer/`."""
    queryset = Kit.objects.select_related(
        'produit_compose', 'created_by').prefetch_related('composants').all()
    serializer_class = KitSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['revisions', 'composition_au']:
            # XMFG18 — lecture seule (aucun prix dans les snapshots).
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

    @action(detail=True, methods=['get'], url_path='revisions')
    def revisions(self, request, pk=None):
        """XMFG18 — historique des révisions de nomenclature de ce kit
        (numéro, date, utilisateur, snapshot JSON). Lecture seule."""
        from ..serializers import RevisionKitSerializer
        kit = self.get_object()
        qs = kit.revisions.select_related('user').order_by('-numero')
        return Response(RevisionKitSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='composition-au')
    def composition_au(self, request, pk=None):
        """XMFG18 — « composition au JJ/MM/AAAA » : la révision en vigueur
        à la date donnée (`?date=JJ/MM/AAAA` ou `AAAA-MM-JJ`). 404 si aucune
        révision n'existait encore à cette date."""
        from datetime import datetime
        from ..serializers import RevisionKitSerializer
        kit = self.get_object()
        brut = (request.query_params.get('date') or '').strip()
        date_limite = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                date_limite = datetime.strptime(brut, fmt).date()
                break
            except ValueError:
                continue
        if date_limite is None:
            return Response(
                {'detail': 'Paramètre date requis (JJ/MM/AAAA ou '
                           'AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        from ..services import composition_kit_au
        revision = composition_kit_au(kit, date_limite)
        if revision is None:
            return Response(
                {'detail': 'Aucune révision à cette date.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(RevisionKitSerializer(revision).data)

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, pk=None):
        """XMFG18 — duplique ce kit (en-tête + composants), avec facteur
        d'échelle optionnel sur les quantités (`facteur_echelle`). La copie
        reçoit sa révision n°1."""
        from ..services import dupliquer_kit
        kit = self.get_object()
        facteur = request.data.get('facteur_echelle')
        try:
            copie = dupliquer_kit(
                kit, user=request.user, facteur_echelle=facteur)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(copie).data, status=status.HTTP_201_CREATED)


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

    def _snapshot(self, kit):
        # XMFG18 — snapshot auto de la composition à chaque modification des
        # composants (idempotent : composition identique → pas de doublon).
        from ..services import snapshot_revision_kit
        snapshot_revision_kit(kit, user=self.request.user)

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()
        self._snapshot(serializer.instance.kit)

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
        self._snapshot(serializer.instance.kit)

    def perform_destroy(self, instance):
        kit = instance.kit
        instance.delete()
        self._snapshot(kit)


class ControleQualiteModeleViewSet(CompanyScopedModelViewSet):
    """XMFG13 — modèle de checklist QC par kit. Société posée COTE SERVEUR.
    Un kit sans modèle (ou avec un modèle inactif) garde le comportement
    `terminer` actuel inchangé (aucune checklist exigée).

    ARC3 — converti au socle transverse (contrairement aux autres viewsets de
    ce fichier qui scopent via leur kit parent) : ce modèle porte une FK
    `company` propre. get_queryset (filtre `kit`) et perform_create/
    perform_update (company forcée serveur) SURCHARGENT la base : réponses
    inchangées."""
    queryset = ControleQualiteModele.objects.select_related(
        'kit').prefetch_related('items').all()
    serializer_class = ControleQualiteModeleSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        kit = self.request.query_params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        kit = serializer.validated_data.get('kit')
        if kit is not None and getattr(kit, 'company_id', None) != cid:
            raise ValidationError(
                {'kit': 'Kit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)


class EtapeAssemblageViewSet(viewsets.ModelViewSet):
    """XMFG14 — gamme légère : étapes d'assemblage d'un kit (mode opératoire).
    Pas de `company` propre : scope via le kit parent. Filtrable par `kit`."""
    queryset = EtapeAssemblage.objects.select_related('kit', 'piece_jointe').all()
    serializer_class = EtapeAssemblageSerializer

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


class OrdreAssemblageViewSet(CompanyScopedModelViewSet):
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
        # XMFG16 — sous-traitant validé tenant (référentiel unifié DC34 :
        # stock.Fournisseur de type « service »).
        sous_traitant = serializer.validated_data.get('sous_traitant')
        if sous_traitant is not None and getattr(
                sous_traitant, 'company_id', None) != cid:
            raise ValidationError(
                {'sous_traitant': 'Sous-traitant inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(OrdreAssemblage, 'ASM', company, _save)
        # XMFG18 — l'ordre FIGE le numéro de révision de nomenclature en
        # vigueur (crée la révision n°1 si le kit n'en a pas encore).
        from ..services import snapshot_revision_kit
        ordre = serializer.instance
        revision, _created = snapshot_revision_kit(
            ordre.kit, user=self.request.user)
        ordre.revision_kit_numero = revision.numero
        ordre.save(update_fields=['revision_kit_numero'])
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
        any_created = False
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
                any_created = True
            ordres.append(ordre)
        return Response(
            OrdreAssemblageSerializer(ordres, many=True).data,
            status=201 if any_created else 200)

    @action(detail=True, methods=['get'])
    def disponibilite(self, request, pk=None):
        """XMFG2 — disponibilité par ligne de composant (disponible / partiel
        / manquant, réservation-aware)."""
        ordre = self.get_object()
        return Response(disponibilite_par_ligne(ordre))

    @action(detail=True, methods=['get'], url_path='bon-pdf',
            permission_classes=[IsAnyRole])
    def bon_pdf(self, request, pk=None):
        """ZMFG10 — bon d'assemblage PDF (worksheet atelier). STRICTEMENT
        INTERNE : aucun prix (test dédié « aucun prix dans le PDF »)."""
        from django.http import HttpResponse
        from .. import assembly_pdf
        ordre = self.get_object()
        pdf_bytes = assembly_pdf.bon_assemblage_pdf(ordre)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="bon-assemblage-{ordre.id}.pdf"')
        return resp

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """FG328/XMFG2 — passe l'ordre en cours. Avertit (non bloquant) si des
        composants manquent. XMFG16 — si l'ordre est lié à un sous-traitant,
        confie les composants (transfert vers l'emplacement dédié « chez
        {sous-traitant} », idempotent) : le backflush à la clôture consommera
        depuis cet emplacement."""
        from ..services import confier_composants_soustraitance

        ordre = self.get_object()
        old = copy.copy(ordre)
        ordre.statut = OrdreAssemblage.Statut.EN_COURS
        ordre.save(update_fields=['statut', 'date_modification'])
        activity.log_changes(old, ordre, request.user)
        alerter_penurie_assemblage(ordre)
        if ordre.sous_traitant_id is not None:
            confier_composants_soustraitance(ordre)
            ordre.refresh_from_db()
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

    @action(detail=True, methods=['post'], url_path='declarer-rebut')
    def declarer_rebut(self, request, pk=None):
        """XMFG11 — déclare un rebut de production (casse/défaut/erreur/autre)
        rattaché à cet ordre : une SORTIE typée REBUT, motivée."""
        from apps.stock.services import declarer_rebut as _declarer_rebut
        from apps.stock.selectors import get_produit_scoped

        ordre = self.get_object()
        company = self.request.user.company
        produit_id = request.data.get('produit')
        quantite = request.data.get('quantite')
        motif = request.data.get('motif')
        note = (request.data.get('note') or '').strip()
        if not produit_id:
            raise ValidationError({'produit': 'Produit requis.'})
        produit = get_produit_scoped(company, produit_id)
        if produit is None:
            raise ValidationError({'produit': 'Produit inconnu pour cette société.'})
        try:
            quantite = int(quantite)
        except (TypeError, ValueError):
            raise ValidationError({'quantite': 'Quantité invalide.'})
        try:
            mouvement = _declarer_rebut(
                company=company, produit=produit, quantite=quantite,
                motif=motif, reference=ordre.reference,
                note=note or f'Rebut ordre {ordre.reference}',
                user=request.user)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response({
            'id': mouvement.id, 'produit': produit.id, 'quantite': mouvement.quantite,
            'motif_rebut': mouvement.motif_rebut, 'reference': mouvement.reference,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='cout-soustraitance',
            permission_classes=[IsResponsableOrAdmin])
    def cout_soustraitance(self, request, pk=None):
        """XMFG16 — coût du composite sous-traité (composants + façon OST) :
        responsable/admin uniquement (coûts d'achat), JAMAIS client-facing."""
        from ..services import cout_composite_soustraite
        ordre = self.get_object()
        cout = cout_composite_soustraite(ordre)
        if cout is None:
            return Response(
                {'detail': "Cet ordre n'est pas lié à une sous-traitance."},
                status=status.HTTP_404_NOT_FOUND)
        return Response({'ordre_id': ordre.id, 'cout_composite': float(cout)})

    @action(detail=False, methods=['get'], url_path='rapport-soustraitants',
            permission_classes=[IsResponsableOrAdmin])
    def rapport_soustraitants(self, request):
        """XMFG16 — reliquat des composants restant chez chaque sous-traitant
        (responsable/admin uniquement)."""
        from ..services import rapport_composants_chez_soustraitants
        company = self.request.user.company
        return Response(rapport_composants_chez_soustraitants(company))

    @action(detail=False, methods=['get'], url_path='rapport-rebuts')
    def rapport_rebuts(self, request):
        """XMFG11 — mini-rapport rebuts agrégé par produit/période."""
        from apps.stock.services import rapport_rebuts as _rapport_rebuts
        company = self.request.user.company
        params = request.query_params
        return Response(_rapport_rebuts(
            company, date_debut=params.get('date_debut'),
            date_fin=params.get('date_fin')))

    @action(detail=True, methods=['get'], url_path='controle-qualite')
    def controle_qualite(self, request, pk=None):
        """XMFG13 — checklist QC de l'ordre (instanciée à la volée depuis le
        modèle du kit ; liste vide si le kit n'a pas de modèle)."""
        ordre = self.get_object()
        controles = instancier_controle_qualite(ordre)
        return Response(ControleQualiteOrdreSerializer(controles, many=True).data)

    @action(detail=True, methods=['post'],
            url_path='controle-qualite/(?P<item_modele_id>[^/.]+)')
    def enregistrer_controle_qualite_item(self, request, pk=None,
                                          item_modele_id=None):
        """XMFG13 — enregistre le résultat d'un item de checklist QC."""
        ordre = self.get_object()
        instancier_controle_qualite(ordre)
        resultat = request.data.get('resultat')
        valeur_mesuree = request.data.get('valeur_mesuree')
        try:
            controle = enregistrer_controle_qualite(
                ordre, item_modele_id, resultat=resultat,
                valeur_mesuree=valeur_mesuree, user=request.user)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(ControleQualiteOrdreSerializer(controle).data)

    @action(detail=True, methods=['get'])
    def etapes(self, request, pk=None):
        """XMFG14 — gamme d'exécution de l'ordre (instanciée à la volée
        depuis les étapes du kit ; liste vide si le kit n'a pas d'étape)."""
        ordre = self.get_object()
        etapes = instancier_etapes_ordre(ordre)
        return Response(EtapeOrdreSerializer(etapes, many=True).data)

    @action(detail=True, methods=['post'],
            url_path='etapes/(?P<etape_modele_id>[^/.]+)/cocher')
    def cocher_etape(self, request, pk=None, etape_modele_id=None):
        """XMFG14 — coche/décoche une étape d'exécution avec sa durée réelle."""
        ordre = self.get_object()
        instancier_etapes_ordre(ordre)
        fait = str(request.data.get('fait', 'true')).lower() in (
            '1', 'true', 'yes')
        duree_reelle_min = request.data.get('duree_reelle_min')
        try:
            duree_reelle_min = (
                int(duree_reelle_min) if duree_reelle_min not in (None, '')
                else None)
        except (TypeError, ValueError):
            raise ValidationError({
                'duree_reelle_min': 'Durée réelle invalide.'})
        try:
            etape_ordre = cocher_etape_ordre(
                ordre, etape_modele_id, fait=fait,
                duree_reelle_min=duree_reelle_min, user=request.user)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(EtapeOrdreSerializer(etape_ordre).data)

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

        # XMFG13 — gate qualité : un kit avec modèle QC actif bloque la
        # clôture tant que la checklist n'est pas entièrement passée, sauf
        # `forcer=true` + motif (responsable/admin — déjà exigé par les
        # permissions du viewset).
        instancier_controle_qualite(ordre)
        forcer = str(request.data.get('forcer') or '').lower() in (
            '1', 'true', 'yes')
        motif_forcage = (request.data.get('motif_forcage') or '').strip()
        if controle_qualite_bloque_cloture(ordre) and not forcer:
            raise ValidationError({
                'controle_qualite':
                    "Checklist qualité incomplète ou en échec : clôture "
                    "bloquée. Forcer avec `forcer=true` + `motif_forcage`."})
        if forcer and not motif_forcage:
            raise ValidationError({
                'motif_forcage': 'Motif de forçage requis.'})

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
            # XMFG7 — capture optionnelle des séries à la clôture (composite
            # produit + composants sérialisés consommés, si transmis).
            series_composite = request.data.get('series_composite')
            series_composants = request.data.get('series_composants')
            if series_composite or series_composants:
                enregistrer_series_assemblage(
                    ordre, series_composite=series_composite or [],
                    series_composants=series_composants or [],
                    user=request.user)
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['get'])
    def series(self, request, pk=None):
        """XMFG7 — séries enregistrées sur cet ordre (composite + composants)."""
        ordre = self.get_object()
        return Response(
            SerieAssemblageSerializer(ordre.series.all(), many=True).data)

    @action(detail=True, methods=['get'])
    def etiquette(self, request, pk=None):
        """XMFG7 — étiquette QR/PDF du composite (référence, kit, série,
        contenu — SANS AUCUN PRIX), une carte par unité avec série enregistrée.
        Renvoie du HTML prêt WeasyPrint, sur le patron des étiquettes FG85."""
        from apps.stock.labels import render_labels_html
        from django.http import HttpResponse as HR

        ordre = self.get_object()
        items = etiquette_items_assemblage(ordre)
        if not items:
            return Response(
                {'detail': 'Aucune série de composite enregistrée.'},
                status=status.HTTP_404_NOT_FOUND)
        symbology = request.query_params.get('symbology', 'qr')
        html = render_labels_html(items, symbology=symbology)
        return HR(html, content_type='text/html; charset=utf-8')

    @action(detail=True, methods=['get'], url_path='analyse',
            permission_classes=[IsResponsableOrAdmin])
    def analyse(self, request, pk=None):
        """XMFG15 — analyse prévu-vs-réel (coût composants + temps) de cet
        ordre. Responsable/admin uniquement (coûts d'achat)."""
        from ..selectors import analyse_ecarts_ordre
        ordre = self.get_object()
        return Response(analyse_ecarts_ordre(ordre))

    @action(detail=False, methods=['get'], url_path='atelier',
            permission_classes=[IsResponsableOrAdmin])
    def atelier(self, request):
        """XMFG15 — panneau « Atelier » : ordres en retard/en cours/terminés
        sur la période, taux de rebut, écart moyen. Filtrable par
        `date_debut`/`date_fin` (bornes de `date_terminaison`)."""
        from ..selectors import panneau_atelier
        company = self.request.user.company
        params = request.query_params
        return Response(panneau_atelier(
            company, date_debut=params.get('date_debut'),
            date_fin=params.get('date_fin')))


class OrdreDemontageLigneViewSet(viewsets.ModelViewSet):
    """XMFG12 — lignes de démontage (quantité récupérée éditable). Pas de
    `company` propre : scope via l'ordre parent. Filtrable par `ordre`.
    Éditable UNIQUEMENT tant que l'ordre est planifié."""
    queryset = OrdreDemontageLigne.objects.select_related('ordre', 'produit').all()
    serializer_class = OrdreDemontageLigneSerializer

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

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        ordre = serializer.validated_data.get('ordre') or getattr(
            serializer.instance, 'ordre', None)
        if ordre is not None and getattr(ordre, 'company_id', None) != cid:
            raise ValidationError(
                {'ordre': 'Ordre inconnu pour cette société.'})
        if ordre is not None and ordre.statut != OrdreDemontage.Statut.PLANIFIE:
            raise ValidationError({
                'ordre': "Lignes verrouillées : l'ordre n'est plus planifié."})

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()


class OrdreDemontageViewSet(CompanyScopedModelViewSet):
    """XMFG12 — ordres de démontage (unbuild) : composite → composants.
    Lecture tout rôle, écriture responsable/admin. Référence/société/
    `created_by` posés serveur. Filtrable par `statut`, `kit`."""
    queryset = OrdreDemontage.objects.select_related('kit', 'created_by').all()
    serializer_class = OrdreDemontageSerializer

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
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        kit = serializer.validated_data.get('kit')
        if kit is not None and getattr(kit, 'company_id', None) != cid:
            raise ValidationError(
                {'kit': 'Kit inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(OrdreDemontage, 'DSM', company, _save)
        seed_lignes_demontage(serializer.instance)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """XMFG12 — clôture l'ordre de démontage : sort le composite, restocke
        les composants selon les quantités RÉCUPÉRÉES (éditées ligne à ligne).
        Idempotent via `stock_mouvemente`."""
        from django.db import transaction
        from apps.stock.services import demonter_composite

        ordre = self.get_object()
        if ordre.kit.produit_compose_id is None:
            raise ValidationError({
                'kit': "Ce kit n'a pas d'article composite "
                       "(produit_compose) : démontage impossible."})

        with transaction.atomic():
            ordre = OrdreDemontage.objects.select_for_update().get(pk=ordre.pk)
            already_moved = ordre.stock_mouvemente
            ordre.statut = OrdreDemontage.Statut.TERMINE
            ordre.date_terminaison = timezone.now()
            update_fields = [
                'statut', 'date_terminaison', 'date_modification']
            if not already_moved:
                lignes = list(ordre.lignes.select_related('produit').all())
                demonter_composite(
                    company=ordre.company, kit=ordre.kit,
                    quantite_demontee=ordre.quantite,
                    lignes_recuperation=lignes,
                    produit_compose=ordre.kit.produit_compose,
                    reference=ordre.reference, user=request.user,
                    emplacement_source=ordre.emplacement_source,
                    emplacement_destination=ordre.emplacement_destination)
                ordre.stock_mouvemente = True
                update_fields.append('stock_mouvemente')
            ordre.save(update_fields=update_fields)
        return Response(self.get_serializer(ordre).data)
