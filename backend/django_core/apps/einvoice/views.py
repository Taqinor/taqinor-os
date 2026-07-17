"""Vues de facturation électronique DGI (Groupe NTMAR)."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import FactureElectronique, TransmissionDGI
from .serializers import (
    FactureElectroniqueSerializer, TransmissionDGISerializer,
)
from .services import (
    generer, is_einvoice_enabled, preparer_signature, regenerer,
    telecharger_xml, transmettre,
)
from .validators import controler_avant_transmission


def _detail_django_validation_error(exc):
    return ' '.join(exc.messages) if getattr(exc, 'messages', None) else str(exc)


class FactureElectroniqueViewSet(CompanyScopedModelViewSet):
    """CRUD lecture + actions de génération/signature/transmission (NTMAR5-9).

    Toute écriture passe par les services (jamais un ``create``/``update``
    direct côté client) — le XML est TOUJOURS calculé serveur, jamais reçu
    du corps de requête."""
    queryset = FactureElectronique.objects.all()
    serializer_class = FactureElectroniqueSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filterset_fields = ['facture_id', 'statut', 'mode']

    @action(detail=False, methods=['post'], url_path='generer')
    def generer_action(self, request):
        """NTMAR5 — génère (ou régénère en nouvelle version) l'e-facture d'une
        ``ventes.Facture``. Corps : ``{"facture_id": <int>, "mode": "dry_run"}``.
        Renvoie 204 (no-op) si ``EINVOICE_ENABLED`` est désactivé."""
        company = request.user.company
        if not is_einvoice_enabled(company):
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            facture_id = int(request.data.get('facture_id'))
        except (TypeError, ValueError):
            return Response(
                {'facture_id': 'facture_id est requis (entier).'},
                status=status.HTTP_400_BAD_REQUEST)
        mode = request.data.get('mode', FactureElectronique.Mode.DRY_RUN)
        try:
            fe = generer(facture_id, company, mode=mode, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': _detail_django_validation_error(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FactureElectroniqueSerializer(fe).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='regenerer')
    def regenerer_action(self, request, pk=None):
        """NTMAR9 — recalcule le XML et crée une NOUVELLE version (jamais
        d'écrasement) ; le contenu original reste téléchargeable."""
        fe = self.get_object()
        nouvelle = regenerer(fe, user=request.user)
        return Response(
            FactureElectroniqueSerializer(nouvelle).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='telecharger')
    def telecharger_action(self, request, pk=None):
        """NTMAR9 — streame le XML de CETTE version depuis MinIO (nosniff)."""
        fe = self.get_object()
        try:
            contenu = telecharger_xml(fe)
        except DjangoValidationError as exc:
            return Response(
                {'detail': _detail_django_validation_error(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(contenu, content_type='application/xml')
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Disposition'] = (
            f'attachment; filename="{fe.facture_ref or fe.facture_id}-v{fe.version}.xml"')
        return response

    @action(detail=True, methods=['post'], url_path='preparer-signature')
    def preparer_signature_action(self, request, pk=None):
        """NTMAR6 — calcule l'empreinte à signer, ne signe jamais."""
        fe = self.get_object()
        return Response(preparer_signature(fe))

    @action(detail=True, methods=['post'], url_path='transmettre')
    def transmettre_action(self, request, pk=None):
        """NTMAR7 — enregistre l'intention de transmission (no-op sans clé/URL
        DGI configurée)."""
        fe = self.get_object()
        transmission = transmettre(fe)
        return Response(
            TransmissionDGISerializer(transmission).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='controler')
    def controler_action(self, request, pk=None):
        """NTMAR8 — liste des anomalies bloquantes avant transmission
        (liste vide = conforme)."""
        fe = self.get_object()
        try:
            anomalies = controler_avant_transmission(fe)
        except Exception as exc:  # pragma: no cover - défense en profondeur
            raise ValidationError({'detail': str(exc)})
        return Response({'anomalies': anomalies, 'conforme': not anomalies})


class TransmissionDGIViewSet(CompanyScopedModelViewSet):
    """Lecture des transmissions DGI (NTMAR7) — écriture via ``transmettre``
    exclusivement (jamais de create/update direct côté client)."""
    queryset = TransmissionDGI.objects.select_related('einvoice')
    serializer_class = TransmissionDGISerializer
    http_method_names = ['get', 'head', 'options']
    filterset_fields = ['einvoice', 'statut']
