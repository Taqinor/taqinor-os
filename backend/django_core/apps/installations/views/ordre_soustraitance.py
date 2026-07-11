"""Vue FG305 — ordres de travaux émis aux sous-traitants chantier.

``OrdreSousTraitanceViewSet`` : CRUD des ordres de prestation passés à un
sous-traitant de l'annuaire (FG304) — pour un chantier, une prestation, un
montant et une échéance — plus les actions de cycle de vie
(``emettre`` / ``receptionner`` / ``cloturer``). Lecture tout rôle, écriture
responsable/admin. Multi-tenant via ``TenantMixin`` : le queryset est filtré sur
la société de l'utilisateur ; la référence, la société et ``created_by`` sont
posés côté serveur (jamais lus du corps). Le ``sous_traitant`` et le
``chantier`` ciblés sont validés tenant (même société). La référence
``OST-YYYYMM-NNNN`` est anti-collision (jamais ``count()+1``).

SCA34 — pilote 1 du kit ``core.documents``. Le viewset gagne :
  * le chatter générique (``ChatterViewSetMixin``, ARC8) : ``chatter/historique``
    (GET) + ``chatter/noter`` (POST), adossé à ``records.Activity`` ;
  * une action ``pdf`` (GET) qui délègue à ``core.documents.render_document_pdf``
    (SCA33 → ``core.pdf.render_pdf``, ARC11) avec le gabarit minimal
    ``installations/ordre_soustraitance_pdf.html``.
Le reste (queryset/permissions/perform_create/actions de cycle de vie) est
INCHANGÉ — la numérotation continue de passer par le même shim
(``apps.ventes.utils.references`` = ré-export bit-identique de
``core.numbering``, cf. docstring du modèle)."""
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.documents import render_document_pdf
from core.viewsets import CompanyScopedModelViewSet

from apps.records.views import ChatterViewSetMixin
from apps.ventes.utils.references import create_with_reference

from ..models import OrdreSousTraitance
from ..serializers import OrdreSousTraitanceSerializer

# Toute action de LECTURE doit figurer ici (sinon écriture requise par défaut).
# SCA34 — 'pdf' est une lecture (même barrière que 'retrieve') ;
# 'chatter_historique' aussi (patron flotte : le get_permissions maison prime
# sur les permission_classes d'@action du mixin, donc la lecture du chatter se
# déclare ICI — 'chatter_noter' reste écriture responsable/admin par défaut).
READ_ACTIONS = ['list', 'retrieve', 'pdf', 'chatter_historique']


def _check_tenant(serializer, company, field):
    """Tenant safety : l'objet lié (sous_traitant/chantier) doit appartenir à la
    société du user. L'objet est déjà résolu par DRF (PrimaryKeyRelatedField),
    donc on lit `company_id` sans surprise cross-société.

    DC34 — pour ``sous_traitant`` (désormais un ``stock.Fournisseur``), on exige
    en plus le type « service » : un fournisseur matériel n'est pas un
    sous-traitant."""
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})
    if (field == 'sous_traitant' and obj is not None
            and getattr(obj, 'type', None) != 'service'):
        raise ValidationError(
            {field: 'Ce fournisseur n\'est pas un sous-traitant (type service).'})


class OrdreSousTraitanceViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """FG305 — ordres de travaux sous-traitant. Lecture tout rôle, écriture
    responsable/admin. Référence anti-collision + société + `created_by` posés
    côté serveur ; `sous_traitant`/`chantier` validés tenant. Filtrable par
    `sous_traitant`, `statut` et `chantier`. Cycle de vie via les actions
    `emettre`/`receptionner`/`cloturer`. SCA34 — chatter générique
    (`chatter/historique`, `chatter/noter`) + PDF (`pdf`) via le kit
    `core.documents`."""
    queryset = OrdreSousTraitance.objects.select_related(
        'sous_traitant', 'chantier', 'created_by').all()
    serializer_class = OrdreSousTraitanceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        sous_traitant = params.get('sous_traitant')
        if sous_traitant:
            qs = qs.filter(sous_traitant_id=sous_traitant)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        chantier = params.get('chantier')
        if chantier:
            qs = qs.filter(chantier_id=chantier)
        return qs

    def perform_create(self, serializer):
        """Référence anti-collision (jamais count()+1), société + créateur posés
        côté serveur. Le sous-traitant et le chantier doivent appartenir à la
        société."""
        company = self.request.user.company
        _check_tenant(serializer, company, 'sous_traitant')
        _check_tenant(serializer, company, 'chantier')

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(OrdreSousTraitance, 'OST', company, _save)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'sous_traitant')
        _check_tenant(serializer, company, 'chantier')
        serializer.save(company=company)

    # ── Actions de cycle de vie ──────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def emettre(self, request, pk=None):
        """FG305 — émet l'ordre (brouillon → émis) et pose la date d'émission si
        elle manque. Réservé responsable/admin (action d'écriture)."""
        ordre = self.get_object()
        if ordre.statut not in (
                OrdreSousTraitance.Statut.BROUILLON,
                OrdreSousTraitance.Statut.EMIS):
            return Response(
                {'detail': "Seul un ordre brouillon peut être émis."},
                status=status.HTTP_400_BAD_REQUEST)
        ordre.statut = OrdreSousTraitance.Statut.EMIS
        if ordre.date_emission is None:
            ordre.date_emission = timezone.now().date()
        ordre.save(update_fields=['statut', 'date_emission',
                                  'date_modification'])
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['post'])
    def receptionner(self, request, pk=None):
        """FG305 — réceptionne la prestation (émis/en cours → réceptionné).
        Accepte un `montant_realise` optionnel dans le corps. Réservé
        responsable/admin."""
        ordre = self.get_object()
        if ordre.statut not in (
                OrdreSousTraitance.Statut.EMIS,
                OrdreSousTraitance.Statut.EN_COURS,
                OrdreSousTraitance.Statut.RECEPTIONNE):
            return Response(
                {'detail': "L'ordre doit être émis ou en cours pour être "
                           "réceptionné."},
                status=status.HTTP_400_BAD_REQUEST)
        update_fields = ['statut', 'date_modification']
        montant_realise = request.data.get('montant_realise')
        if montant_realise is not None and montant_realise != '':
            try:
                valeur = float(montant_realise)
            except (TypeError, ValueError):
                return Response(
                    {'montant_realise': 'Montant réalisé invalide.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if valeur < 0:
                return Response(
                    {'montant_realise':
                        'Le montant réalisé ne peut pas être négatif.'},
                    status=status.HTTP_400_BAD_REQUEST)
            ordre.montant_realise = montant_realise
            update_fields.append('montant_realise')
        ordre.statut = OrdreSousTraitance.Statut.RECEPTIONNE
        ordre.save(update_fields=update_fields)
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """FG305 — clôt l'ordre (réceptionné → clos). Réservé responsable/admin."""
        ordre = self.get_object()
        if ordre.statut not in (
                OrdreSousTraitance.Statut.RECEPTIONNE,
                OrdreSousTraitance.Statut.CLOS):
            return Response(
                {'detail': "Seul un ordre réceptionné peut être clôturé."},
                status=status.HTTP_400_BAD_REQUEST)
        ordre.statut = OrdreSousTraitance.Statut.CLOS
        ordre.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """SCA34 — PDF de l'ordre via le hook du kit (``render_document_pdf``
        → ``core.pdf.render_pdf``, ARC11). Lecture : tout rôle (même barrière
        que ``retrieve``, cf. ``READ_ACTIONS``)."""
        ordre = self.get_object()
        pdf_bytes = render_document_pdf(
            ordre, 'installations/ordre_soustraitance_pdf.html')
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{ordre.reference}.pdf"')
        return response
