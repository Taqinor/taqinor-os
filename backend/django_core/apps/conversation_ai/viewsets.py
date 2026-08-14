"""ViewSets du module « conversation_ai » (Groupe NTAI).

``AppelCommercialViewSet`` hérite de ``core.viewsets.CompanyScopedModelViewSet``
(ARC2) : queryset filtré sur ``request.user.company`` et société FORCÉE côté
serveur — jamais lue du corps de la requête.

Le téléversement de l'enregistrement passe par le stockage objet partagé
(``records.storage``, clé préfixée société) ; la transcription est enfilée
APRÈS COMMIT, en best-effort — un broker injoignable n'empêche jamais
l'enregistrement de l'appel.
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.viewsets import CompanyScopedModelViewSet

from .models import AppelCommercial
from .serializers import AppelCommercialSerializer
from .services import AnalyseIndisponible, AppelUploadError

logger = logging.getLogger(__name__)


def _enfiler_transcription(appel_id):
    """Met la transcription en file, sans jamais lever (broker injoignable…)."""
    try:
        from .tasks import transcrire_appel_task

        transcrire_appel_task.delay(appel_id)
    except Exception:  # noqa: BLE001 - l'appel reste « non transcrit ».
        logger.warning(
            'conversation_ai: mise en file de la transcription impossible '
            '(appel %s)', appel_id, exc_info=True)


class AppelCommercialViewSet(CompanyScopedModelViewSet):
    """NTAI21 — CRUD scopé société sur les enregistrements d'appels.

    ``POST`` accepte un multipart ``fichier`` (l'enregistrement) + un
    rattachement facultatif ``lead``/``client`` de la MÊME société. La réponse
    porte l'appel créé au statut ``non_transcrit`` : la transcription arrive
    plus tard (et jamais du tout si aucun fournisseur STT n'est configuré).
    """

    queryset = AppelCommercial.objects.all()
    serializer_class = AppelCommercialSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    #: Le téléversement (et LUI SEUL) porte le throttle « transcription » : il
    #: borne le coût STT d'un dépôt répété. La simple consultation de la liste
    #: garde le throttle transverse par tenant.
    throttle_scope = 'ai_transcription'

    def get_throttles(self):
        if self.request.method == 'POST':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return super().get_queryset().order_by('-created_at', '-id')

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        from .services import stocker_audio

        company = self.request.user.company
        fichier = serializer.validated_data.pop('fichier', None)
        extra = {}
        if fichier is not None:
            try:
                infos = stocker_audio(fichier, company=company)
            except AppelUploadError as exc:
                raise ValidationError({'fichier': str(exc)})
            extra = {
                'fichier_key': infos['file_key'],
                'mime': infos.get('mime', '') or '',
            }
        appel = serializer.save(company=company, **extra)
        if appel.fichier_key:
            transaction.on_commit(lambda: _enfiler_transcription(appel.id))

    @action(detail=True, methods=['post'], url_path='analyser')
    def analyser(self, request, pk=None):
        """NTAI22 — ``POST appels/<id>/analyser/``.

        Extrait du transcript ``{objections, next_steps, produits, sentiment}``
        et PROPOSE des relances CRM. Rien n'est écrit dans le CRM ici
        (``confirme: false``) : la création passe par ``creer-relances/``.
        Sans clé LLM → 503 douce ; sans transcript → 400.
        """
        from .services import analyser_appel, proposer_relances

        appel = self.get_object()
        try:
            analyse = analyser_appel(appel)
        except AnalyseIndisponible as exc:
            code = (status.HTTP_400_BAD_REQUEST if exc.configured
                    else status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'detail': str(exc)}, status=code)
        return Response({
            'appel': appel.pk,
            'analyse': analyse,
            'relances_proposees': proposer_relances(appel, analyse),
            # Contrat explicite : proposer ≠ écrire.
            'confirme': False,
        })

    @action(detail=True, methods=['post'], url_path='creer-relances')
    def creer_relances(self, request, pk=None):
        """NTAI22 — ``POST appels/<id>/creer-relances/`` (CONFIRMATION).

        Body ``{"relances": [{"resume": "...", "delai_jours": 3}]}``. Crée les
        activités de relance sur le lead rattaché — SEULES les relances
        explicitement envoyées sont créées.
        """
        from .services import confirmer_relances

        appel = self.get_object()
        relances = request.data.get('relances')
        if not isinstance(relances, list) or not relances:
            return Response(
                {'detail': 'Fournissez au moins une relance à créer.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not appel.lead_id:
            return Response(
                {'detail': "Cet appel n'est rattaché à aucun lead."},
                status=status.HTTP_400_BAD_REQUEST)
        creees = confirmer_relances(appel, relances, user=request.user)
        return Response({
            'appel': appel.pk,
            'creees': [
                {'id': a.pk, 'resume': a.summary,
                 'due_date': a.due_date.isoformat() if a.due_date else None}
                for a in creees
            ],
            'confirme': True,
        }, status=status.HTTP_201_CREATED)
