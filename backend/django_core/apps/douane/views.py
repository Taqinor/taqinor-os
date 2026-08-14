from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from .models import DossierExport, ParametresDouane, PieceDossierExport
from .permissions import DOUANE_RESPONSABLE
from .serializers import (
    DossierExportSerializer, ParametresDouaneSerializer, PieceDossierExportSerializer,
)
from .services import attribuer_numero_dossier_export

# NTLOG47 — export CSV/xlsx dossiers-export pour l'expert-comptable. La
# colonne « estimation non contractuelle » est le contrat que NTLOG13/21
# (valeur en douane calculée, droits/taxes estimés) devront remplir une fois
# débloqués (dépendent de NTLOG10, BLOCKED) — présente dès aujourd'hui,
# vide tant qu'aucun calcul réel n'existe, JAMAIS présentée comme la
# déclaration douanière officielle.
_EXPORT_HEADERS = [
    'Numéro', 'Statut', 'Incoterm', 'Devise', 'Valeur marchandise (devise)',
    'Pays destinataire',
    'Droits/taxes estimés — estimation non contractuelle',
]


def _export_row(dossier):
    return [
        dossier.numero,
        dossier.get_statut_display(),
        dossier.get_incoterm_display(),
        dossier.devise,
        dossier.valeur_marchandise_devise,
        dossier.pays_destinataire,
        '',
    ]


class DossierExportViewSet(CompanyScopedModelViewSet):
    """NTLOG14 — CRUD ``dossiers-export/`` + filtre ``?statut=``. ``numero``
    posé côté serveur (jamais lu du corps de la requête) via
    ``core.numbering``, JAMAIS ``count()+1`` (ARC6). Filtre manuel (pas de
    ``DjangoFilterBackend`` dans ce projet — défaut global :
    ``OrderingFilter``/``SearchFilter`` seulement, motif ``ao.
    PieceConsultationViewSet._filtres_exacts``).

    NTLOG43 — écriture réservée à ``douane_responsable`` (repli superuser/
    palier historique via ``ScopedPermission``, déjà le défaut de
    ``CompanyScopedModelViewSet`` — voir ``apps/douane/permissions.py``).
    Lecture ouverte à tout utilisateur authentifié de la société (couvre le
    rôle lecture-seule ``comptabilite``)."""
    queryset = DossierExport.objects.all()
    serializer_class = DossierExportSerializer
    write_permission = DOUANE_RESPONSABLE

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        # ``devis``/``facture`` sont des string-FK cross-app en LECTURE
        # (jamais un import de leurs modèles) mais restent écrivables via
        # l'API : sans ce garde un id d'une AUTRE société lierait le dossier
        # à un devis/une facture étrangère (motif
        # ``installations.DossierImportViewSet._check_tenant``, FG315).
        company_id = self.request.user.company_id
        for field in ('devis', 'facture'):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != company_id:
                raise ValidationError({field: 'Objet inconnu pour cette société.'})

    def perform_create(self, serializer):
        # Création + numérotation dans UNE transaction (revue coordinateur
        # NTLOG14) : sinon un échec de numérotation laisse une ligne
        # `numero=''` committée, et `unique_together (company, numero)`
        # bloque alors toute création suivante pour cette société.
        self._check_tenant(serializer)
        with transaction.atomic():
            instance = serializer.save(
                company=self.request.user.company, created_by=self.request.user)
            attribuer_numero_dossier_export(instance)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """NTLOG47 — export ``dossiers-export/export/?periode=YYYY-MM&format=
        csv|xlsx`` pour transmission périodique à l'expert-comptable. Volet
        ``dossiers-import/`` NON couvert (n'existe pas dans cette app —
        NTLOG10 BLOCKED). GET = méthode sûre, déjà ouverte à tout utilisateur
        authentifié de la société (couvre le rôle lecture-seule
        ``comptabilite``, cohérent avec l'usage rapprochement comptable)."""
        fmt = request.query_params.get('format', 'csv')
        if fmt not in ('csv', 'xlsx'):
            return Response(
                {'detail': "Le paramètre 'format' doit être 'csv' ou 'xlsx'."},
                status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset()
        periode = request.query_params.get('periode')
        if periode:
            try:
                annee, mois = periode.split('-')
                qs = qs.filter(created_at__year=int(annee), created_at__month=int(mois))
            except (ValueError, TypeError):
                return Response(
                    {'detail': "Le paramètre 'periode' doit être au format YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST)
        rows = [_export_row(d) for d in qs.order_by('numero')]

        if fmt == 'xlsx':
            from apps.records.xlsx import build_xlsx_response
            return build_xlsx_response(
                'dossiers-export-douane.xlsx', _EXPORT_HEADERS, rows,
                sheet_title='Dossiers export')

        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
        writer.writerow(_EXPORT_HEADERS)
        for row in rows:
            writer.writerow(row)
        resp = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            'attachment; filename="dossiers-export-douane.csv"')
        return resp


class PieceDossierExportViewSet(CompanyScopedModelViewSet):
    """NTLOG14 — pièces d'un dossier d'export, filtrables par
    ``?dossier=<id>`` (motif ``pieces-consultation`` de ``apps.ao``). Scopage
    société standard (``CompanyScopedModelViewSet``) via la FK ``company``
    propre du modèle — voir la docstring de ``PieceDossierExport``.

    NTLOG43 — même garde d'écriture que ``DossierExportViewSet``
    (``douane_responsable``)."""
    queryset = PieceDossierExport.objects.all()
    serializer_class = PieceDossierExportSerializer
    write_permission = DOUANE_RESPONSABLE

    def get_queryset(self):
        qs = super().get_queryset()
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            qs = qs.filter(dossier_id=dossier_id)
        return qs

    def perform_create(self, serializer):
        # Le `dossier` fourni par le client doit appartenir à la MÊME société
        # que l'utilisateur — sans ce garde, un id d'une AUTRE société créerait
        # une pièce reliée à un dossier étranger (isolation cassée), même si
        # la ligne PieceDossierExport elle-même reste correctement scopée.
        dossier = serializer.validated_data.get('dossier')
        user_company_id = self.request.user.company_id
        if dossier is not None and user_company_id and dossier.company_id != user_company_id:
            raise PermissionDenied("Dossier hors de votre société.")
        serializer.save(company=self.request.user.company)


class ParametresDouaneViewSet(viewsets.ViewSet):
    """NTLOG36 — réglages douane, singleton par société (motif
    ``stock.AchatsParametresViewSet``, XPUR1). GET (``list``, sur
    ``parametres-douane/``) renvoie le réglage courant, le créant si besoin ;
    PATCH (``partial_update``) le met à jour. ``company`` toujours dérivée de
    l'utilisateur, jamais du corps de requête. Écriture réservée à
    ``douane_responsable`` (même garde que les autres viewsets — NTLOG43)."""
    permission_classes = [ScopedPermission]
    write_permission = DOUANE_RESPONSABLE

    def list(self, request):
        obj = ParametresDouane.for_company(request.user.company)
        return Response(ParametresDouaneSerializer(obj).data)

    def partial_update(self, request, pk=None):
        obj = ParametresDouane.for_company(request.user.company)
        serializer = ParametresDouaneSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
