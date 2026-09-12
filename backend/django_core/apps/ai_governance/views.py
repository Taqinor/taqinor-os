"""Vues du module « ai_governance » — copilotes IA (Groupe NTAI).

Toutes les vues sont des ``APIView`` de GÉNÉRATION : elles lisent, proposent un
brouillon, et n'écrivent JAMAIS dans un modèle métier. Sans clé LLM/STT
configurée, elles répondent 503 avec un message FR explicite et ne font aucun
appel réseau.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .serializers import (CapacitesRequeteSerializer, FicheCibleSerializer,
                          RechercheGlobaleRequeteSerializer,
                          UsageRequeteSerializer)
from .services import AiCopiloteUnavailable


def _unavailable_response(exc: AiCopiloteUnavailable) -> Response:
    """Traduit une :class:`AiCopiloteUnavailable` en 503 (pas de clé) ou 400."""
    code = (status.HTTP_400_BAD_REQUEST if exc.configured
            else status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'detail': str(exc)}, status=code)


class UsageContexteMixin:
    """NTAI1 — pose « quelle société, quelle feature » autour du traitement.

    Un fournisseur IA ne reçoit qu'un prompt : il ne peut pas savoir pour quelle
    société il travaille. Ce contexte, posé ICI (côté serveur, à partir de
    l'utilisateur authentifié — jamais d'un corps de requête), est ce qui permet
    au journal d'usage d'attribuer l'appel à la bonne société. Sans lui, aucune
    ligne n'est écrite (on ne devine jamais une société).

    Le contexte est posé APRÈS ``initial()`` (donc après authentification, quand
    ``request.user`` est réellement résolu) et rendu dans
    ``finalize_response()``, qui est appelé même quand la vue lève.
    """

    #: Identifie la feature appelante dans le journal (texte stable).
    feature_key = ''

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        from core.ai.usage import set_context

        self._usage_token = set_context(
            company_id=getattr(request.user, 'company_id', None),
            feature_key=self.feature_key)

    def finalize_response(self, request, response, *args, **kwargs):
        from core.ai.usage import reset_context

        reset_context(getattr(self, '_usage_token', None))
        self._usage_token = None
        return super().finalize_response(request, response, *args, **kwargs)


class UsageView(GenericAPIView):
    """NTAI1 — ``GET /api/django/ai-governance/usage/?since=&feature=``.

    Agrégats d'usage IA de la société de l'appelant : par jour, par feature et
    par fournisseur. Réservé au palier Administrateur/Directeur.

    Ne renvoie QUE des métriques (aucun prompt, aucune donnée métier) et
    signale explicitement les appels dont le coût est INCONNU (fournisseur sans
    tarif configuré) plutôt que de les compter comme gratuits.
    """

    permission_classes = [IsAuthenticated, IsAdminOrResponsableTier]
    # R2 (check_openapi_shapes) : base GenericAPIView + serializer de requête +
    # `responses=` déclaré — la forme n'est jamais devinée, donc cette vue
    # n'ajoute rien au cliquet, qui ne peut que décroître.
    serializer_class = UsageRequeteSerializer

    def get_queryset(self):
        """Journal d'usage de la SOCIÉTÉ de l'appelant, jamais au-delà."""
        from .models import LlmUsageRecord

        return LlmUsageRecord.objects.filter(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('AiUsageAgregats', {
        'depuis': drf_serializers.CharField(allow_null=True),
        'feature': drf_serializers.CharField(),
        'totaux': drf_serializers.JSONField(),
        'cout_complet': drf_serializers.BooleanField(),
        'par_jour': drf_serializers.JSONField(),
        'par_feature': drf_serializers.JSONField(),
        'par_fournisseur': drf_serializers.JSONField(),
    }))
    def get(self, request):
        from datetime import date

        from .usage import agreger_usage, fenetre_par_defaut

        since = request.query_params.get('since') or ''
        if since:
            try:
                depuis = date.fromisoformat(since)
            except ValueError:
                return Response(
                    {'detail': 'Paramètre « since » invalide — format attendu '
                               'AAAA-MM-JJ.'},
                    status=status.HTTP_400_BAD_REQUEST)
        else:
            depuis = fenetre_par_defaut()

        return Response(agreger_usage(
            request.user.company, since=depuis,
            feature=request.query_params.get('feature') or ''))


class CapabilitiesView(GenericAPIView):
    """NTAI6 — ``GET /api/django/ai-governance/capabilities/``.

    Pour chaque capacité IA (ocr/stt/vision_qa/llm) : le fournisseur
    sélectionné, s'il est ACTIF, pourquoi il ne l'est pas, et ses mesures
    (appels, latence médiane, dernière erreur) issues du journal NTAI1.

    AUCUNE CLÉ N'EST EXPOSÉE : on renvoie le NOM du fournisseur, jamais son
    secret. La lecture se fait dans le contexte de la société de l'appelant,
    pour que l'état affiché soit celui qu'il obtiendrait réellement (budget
    épuisé compris).
    """

    permission_classes = [IsAuthenticated, IsAdminOrResponsableTier]
    serializer_class = CapacitesRequeteSerializer

    def get_queryset(self):
        """Journal d'usage de la SOCIÉTÉ de l'appelant — seule source des
        mesures de cet écran. Le rendre explicite rend le périmètre
        vérifiable par la garde d'isolation multi-société, au lieu de le
        laisser enfoui dans le calculateur de métriques."""
        from .models import LlmUsageRecord

        return LlmUsageRecord.objects.filter(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('AiCapacitesEtat', {
        'capacite': drf_serializers.CharField(),
        'fournisseur_choisi': drf_serializers.CharField(),
        'fournisseur_actif': drf_serializers.CharField(),
        'label': drf_serializers.CharField(),
        'configure': drf_serializers.BooleanField(),
        'motif': drf_serializers.CharField(),
        'appels': drf_serializers.IntegerField(allow_null=True),
        'latence_p50_ms': drf_serializers.IntegerField(allow_null=True),
        'derniere_erreur': drf_serializers.CharField(allow_blank=True),
        'derniere_erreur_le': drf_serializers.CharField(allow_null=True),
    }, many=True))
    def get(self, request):
        from core.ai.registry import capabilities_status
        from core.ai.usage import usage_context

        company = request.user.company
        with usage_context(company_id=getattr(company, 'id', None),
                           feature_key='ai.capabilities'):
            return Response(capabilities_status(company))


class ResumeFicheView(UsageContexteMixin, GenericAPIView):
    """NTAI8 — ``POST /api/django/ai/resume-fiche/``.

    Body ``{"content_type": "crm.lead", "object_id": 12}``. Renvoie un résumé
    FR de la SITUATION de la fiche, construit à partir d'une allowlist de
    champs + du fil d'activité (tout deux scopés société).

    LECTURE SEULE. Type hors whitelist → 400 ; sans clé LLM → 503 douce
    (« lecture manuelle »), aucun appel réseau.
    """

    feature_key = 'ai.resume_fiche'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'
    serializer_class = FicheCibleSerializer

    def get_queryset(self):
        """Fil d'activité de la SOCIÉTÉ de l'appelant — la seule source lue.

        La fiche elle-même est résolue par ``resolve_target`` (qui refuse une
        cible d'une autre société) ; ce ``get_queryset`` rend ce périmètre
        EXPLICITE et vérifiable par la garde d'isolation multi-société.
        """
        from apps.records.models import Activity

        return Activity.objects.filter(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('AiResumeFiche', {
        'content_type': drf_serializers.CharField(),
        'object_id': drf_serializers.IntegerField(),
        'libelle': drf_serializers.CharField(),
        'resume': drf_serializers.CharField(),
        'faits': drf_serializers.JSONField(),
        'entrees_fil': drf_serializers.IntegerField(),
        'source': drf_serializers.CharField(),
    }))
    def post(self, request):
        from .copilote import resumer_fiche

        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        if not content_type or object_id in (None, ''):
            return Response(
                {'detail': 'content_type et object_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = resumer_fiche(
                company=request.user.company, content_type=content_type,
                object_id=object_id)
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class ProchainesActionsView(UsageContexteMixin, GenericAPIView):
    """NTAI9 — ``POST /api/django/ai/prochaines-actions/``.

    Body ``{"content_type": "crm.lead", "object_id": 12}``. Renvoie 1 à 3
    actions priorisées avec leur raison, et — quand elle existe — la clé
    d'action du catalogue agent qui permet de l'exécuter EN UN CLIC, via le
    chemin propose → confirme existant.

    Disponible même SANS clé LLM (l'heuristique est déterministe et gratuite).
    N'EXÉCUTE RIEN : la réponse porte ``execute: false``.
    """

    feature_key = 'ai.prochaines_actions'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'
    serializer_class = FicheCibleSerializer

    def get_queryset(self):
        """Fil d'activité de la SOCIÉTÉ de l'appelant — la seule source lue.

        La fiche elle-même est résolue par ``resolve_target`` (qui refuse une
        cible d'une autre société) ; ce ``get_queryset`` rend ce périmètre
        EXPLICITE et vérifiable par la garde d'isolation multi-société.
        """
        from apps.records.models import Activity

        return Activity.objects.filter(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('AiProchainesActions', {
        'content_type': drf_serializers.CharField(),
        'object_id': drf_serializers.IntegerField(),
        'libelle': drf_serializers.CharField(),
        'actions': drf_serializers.JSONField(),
        'faits': drf_serializers.JSONField(),
        'execute': drf_serializers.BooleanField(),
    }))
    def post(self, request):
        from .copilote import prochaines_actions

        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        if not content_type or object_id in (None, ''):
            return Response(
                {'detail': 'content_type et object_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = prochaines_actions(
                company=request.user.company, content_type=content_type,
                object_id=object_id, user=request.user)
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class DescriptionProduitView(UsageContexteMixin, APIView):
    """NTAI13 — ``POST /api/django/ai/description-produit/``.

    Body ``{"produit_id": <int>}``. Renvoie une description commerciale FR + une
    variante courte, à VALIDER par l'utilisateur : rien n'est enregistré ici.
    ``Produit.prix_achat`` n'est jamais transmis au fournisseur (allowlist de
    champs côté service, testée).
    """

    feature_key = 'ai.description_produit'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import generer_description_produit

        produit_id = request.data.get('produit_id')
        if produit_id in (None, ''):
            return Response({'detail': 'produit_id est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = generer_description_produit(
                company=request.user.company, produit_id=produit_id)
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class RedigerView(UsageContexteMixin, APIView):
    """NTAI11 — ``POST /api/django/ai/rediger/``.

    Body ``{"content_type": "crm.lead", "object_id": 12, "canal":
    "email|whatsapp|sms", "intention": "..."}``. Aplatit le fil (chatter +
    activités) de la fiche et renvoie un brouillon FR ÉDITABLE.

    N'ENVOIE JAMAIS : la réponse porte ``envoye: false`` ; l'envoi reste une
    action utilisateur explicite via les endpoints d'envoi existants. La
    relance CRM et la réponse SAV réutilisent CET endpoint.
    """

    feature_key = 'ai.rediger'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import rediger_brouillon

        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        if not content_type or object_id in (None, ''):
            return Response(
                {'detail': 'content_type et object_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = rediger_brouillon(
                company=request.user.company,
                content_type=content_type,
                object_id=object_id,
                canal=request.data.get('canal') or 'email',
                intention=request.data.get('intention') or '')
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class CrInterventionView(UsageContexteMixin, APIView):
    """NTAI12 — ``POST /api/django/ai/cr-intervention/`` (multipart).

    Champs : ``file`` (mémo vocal) et ``ticket_id`` optionnel. Transcrit puis
    structure le mémo en ``{diagnostic, travaux, pieces, recommandations}``
    pour PRÉ-REMPLIR le rapport du ticket SAV.

    Ne change JAMAIS le statut du ticket (le moteur SAV existant reste seul
    maître des transitions) et ne persiste JAMAIS l'audio reçu.
    """

    feature_key = 'ai.cr_intervention'
    permission_classes = [IsAuthenticated, IsAnyRole]
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_transcription'

    def post(self, request):
        from .services import cr_intervention_depuis_audio

        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'Aucun fichier audio fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            content = upload.read()
        finally:
            upload.close()

        try:
            resultat = cr_intervention_depuis_audio(
                company=request.user.company, file_bytes=content,
                ticket_id=request.data.get('ticket_id'))
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class RapportPeriodeView(UsageContexteMixin, APIView):
    """NTAI36 — ``POST /api/django/ai/rapport-periode/``.

    Body ``{"module": "commercial|facturation", "periode": "AAAA-MM"}``.

    Les CHIFFRES sont calculés par le serveur via les sélecteurs de lecture
    existants ; le LLM ne fait que les mettre en phrases. Un narratif
    contenant un nombre absent des métriques est REFUSÉ (400), jamais rendu.
    Brouillon éditable — ``envoye: false``, aucune diffusion automatique.
    """

    feature_key = 'ai.rapport_periode'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import rapport_periode

        try:
            resultat = rapport_periode(
                company=request.user.company,
                module=request.data.get('module') or '',
                periode=request.data.get('periode') or '')
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class RechercheGlobaleView(UsageContexteMixin, GenericAPIView):
    """NTAI25 — ``POST /api/django/ai/recherche-globale/``.

    Body ``{"question": "quels clients ont un litige ouvert ?"}``. Cherche dans
    l'index sémantique cross-module (NTAI24, TOUJOURS scopé société), assemble
    un contexte et fait rédiger une réponse FR qui CITE chaque fiche source
    sous la forme ``[app.model#id]``.

    Distinct de l'agent NL→SQL (qui interroge des agrégats) : ici on répond sur
    des FICHES. Garde NTAI4 : toute citation absente des résultats est retirée
    de la réponse (jamais de lien mort). Sans clé LLM, l'endpoint dégrade sur
    la recherche par mots-clés — l'utilisateur obtient toujours ses fiches.
    LECTURE SEULE : rien n'est jamais écrit.
    """

    feature_key = 'ai.recherche_globale'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    # R2 (check_openapi_shapes) : base GenericAPIView + serializer_class de
    # requête + `responses=` déclaré — la forme n'est JAMAIS devinée, donc
    # cette vue n'ajoute rien au cliquet, qui ne peut que décroître.
    serializer_class = RechercheGlobaleRequeteSerializer

    def get_queryset(self):
        """Index sémantique de la SOCIÉTÉ de l'appelant, jamais au-delà.

        La recherche elle-même passe par ``recherche_globale(company=...)``
        ; ce ``get_queryset`` rend ce périmètre EXPLICITE et vérifiable par
        la garde d'isolation multi-société (YDATA21), au lieu de le laisser
        enfoui dans le service.
        """
        from core.models import SearchChunk

        return SearchChunk.objects.filter(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('RechercheGlobaleReponse', {
        'question': drf_serializers.CharField(),
        'reponse': drf_serializers.CharField(),
        'citations': drf_serializers.JSONField(),
        'citations_ecartees': drf_serializers.JSONField(),
        'resultats': drf_serializers.JSONField(),
        'source': drf_serializers.CharField(),
    }))
    def post(self, request):
        from .services import recherche_globale

        try:
            resultat = recherche_globale(
                company=request.user.company,
                question=request.data.get('question') or '')
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class AssistantConfigView(UsageContexteMixin, APIView):
    """NTAI35 — ``POST /api/django/ai/assistant-config/``.

    Body ``{"question": "où régler la TVA ?"}``. Renvoie une réponse FR et des
    LIENS PROFONDS vers les écrans Paramètres concernés.

    GUIDAGE SEUL : aucune modification de paramètre (``modifie: false``, aucun
    verbe d'écriture exposé). Les écrans que le rôle de l'appelant ne peut pas
    atteindre ne lui sont jamais proposés. Sans clé LLM, la réponse dégrade
    sur la FAQ statique de l'index — l'utilisateur obtient toujours son lien.
    """

    feature_key = 'ai.assistant_config'
    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import assistant_config

        try:
            resultat = assistant_config(
                question=request.data.get('question') or '',
                role=getattr(request.user, 'role_legacy', None))
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)
