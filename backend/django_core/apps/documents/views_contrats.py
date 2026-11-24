"""API du dossier contractuel d'un chantier (contract_samples/*.json).

Portée : société de l'utilisateur ET portée de rôle de la fiche chantier
(``views._get_chantier_or_404``) — un acte d'une autre société, ou d'un
chantier hors portée, répond 404. Lecture : ``LectureChantiersOuVentes`` ;
écriture : + ``IsResponsableOrAdmin`` + le code de grille ``installation_gerer`` ;
modèle de la société : Directeur.
Refus servis ``{detail, code}`` (409 refus d'état, 400 corps invalide).
"""
from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.roles.permissions import DroitDeLaGrille
from authentication.permissions import IsResponsableOrAdmin

from .contrats import selectors, services
from .contrats import types as T
from .serializers_contrats import (
    CorpsMarquerSigneSerializer, CorpsPatchSerializer, CorpsSignerSerializer,
    DetailActeSerializer, DossierContractuelSerializer, ErreurActeSerializer,
    ModeleActeReponseSerializer,
)
from .views import LectureChantiersOuVentes, _get_chantier_or_404

PARAM_LANGUE = OpenApiParameter(
    'langue', OpenApiTypes.STR, required=False, enum=list(T.LANGUES),
    description="Langue du contenu servi : fr (défaut) ou ar (traduction "
                "arabe).")
_ERREURS = {400: ErreurActeSerializer, 404: ErreurActeSerializer,
            409: ErreurActeSerializer}
#: Code de la grille des écritures d'un acte : celui des chantiers (un acte
#: est un document du chantier) — décocher « Modifier » dans l'éditeur de
#: rôles retire le geste.
CODE_ECRITURE = 'installation_gerer'


class EstDirecteur(BasePermission):
    """Réservé au Directeur (même règle que la configuration des étapes de
    chantier) : superuser ; rôle fin portant ``journal_activite_voir`` ;
    compte hérité sans rôle fin au palier administrateur."""
    message = 'Réservé au Directeur.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        if getattr(user, 'role_id', None):
            return 'journal_activite_voir' in (user.role.permissions or [])
        return bool(getattr(user, 'is_admin_role', False))


def _refus(code, detail, statut_http=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': detail, 'code': code}, status=statut_http)


def _langue(request):
    """``?langue=`` (défaut fr) ; toute autre valeur → None (400)."""
    langue = request.query_params.get('langue', T.LANGUE_DEFAUT)
    return langue if langue in T.LANGUES else None


def _acte_ou_404(request, pk):
    acte = selectors.acte_de_la_societe(
        getattr(request.user, 'company', None), pk)
    if acte is None:
        raise Http404
    acte.chantier = _get_chantier_or_404(request, acte.chantier_id)
    return acte


def _erreur(exc):
    return _refus(exc.code, exc.detail, exc.statut_http)


class _RequeteEcriture:
    """La requête vue comme un geste d'écriture (POST) : sert à évaluer les
    permissions des routes d'écriture pendant une lecture."""
    method = 'POST'

    def __init__(self, request):
        self._requete = request

    def __getattr__(self, nom):
        return getattr(self._requete, nom)


def _droits(request):
    """Les droits d'écriture de l'utilisateur, évalués avec les MÊMES
    permissions que les routes d'écriture (rôle + droit de la grille) et que
    l'enregistrement du modèle (Directeur) : les ``peut_*`` servis disent la
    vérité."""
    ecriture = _RequeteEcriture(request)
    vue = ActeEmettreView()
    ecrire = all(p.has_permission(ecriture, vue) for p in (
        IsResponsableOrAdmin(), DroitDeLaGrille(CODE_ECRITURE)()))
    return {'ecrire': ecrire,
            'enregistrer_modele': EstDirecteur().has_permission(
                request, ActeModeleView())}


def _detail(acte, langue='fr', avertissements=None, request=None):
    donnees = selectors.detail_acte(
        acte, langue, droits=_droits(request) if request is not None else None)
    if avertissements:
        donnees['avertissements'] = list(donnees['avertissements']) + list(
            avertissements)
    return Response(donnees)


def _corps_invalide(serializer):
    premier = next(iter(serializer.errors.items()), ('corps', ['invalide']))
    champ, messages = premier
    message = messages[0] if isinstance(messages, list) and messages else messages
    return _refus(T.CODE_CONTENU_INVALIDE, f'{champ} : {message}')


class DossierContractuelView(APIView):
    """Le dossier contractuel d'un chantier (cinq actes, prochaine action).
    Prépare le dossier s'il manque (idempotent)."""
    permission_classes = [LectureChantiersOuVentes]

    @extend_schema(responses={200: DossierContractuelSerializer,
                              404: ErreurActeSerializer})
    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        return Response(selectors.dossier_du_chantier(
            chantier, request.user, droits=_droits(request)))


class _ActeVue(APIView):
    permission_classes = [LectureChantiersOuVentes, IsResponsableOrAdmin,
                          DroitDeLaGrille(CODE_ECRITURE)]


class ActeDetailView(APIView):
    """Détail d'un acte (résumé + contenu) ; PATCH = personnaliser un
    brouillon."""

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [LectureChantiersOuVentes()]
        return [LectureChantiersOuVentes(), IsResponsableOrAdmin(),
                DroitDeLaGrille(CODE_ECRITURE)()]

    @extend_schema(parameters=[PARAM_LANGUE],
                   responses={200: DetailActeSerializer, **_ERREURS})
    def get(self, request, pk):
        langue = _langue(request)
        if langue is None:
            return _refus(T.CODE_CONTENU_INVALIDE,
                          'Langue inconnue : fr ou ar attendu.')
        acte = _acte_ou_404(request, pk)
        return Response(selectors.detail_acte(acte, langue,
                                              droits=_droits(request)))

    @extend_schema(request=CorpsPatchSerializer,
                   responses={200: DetailActeSerializer, **_ERREURS})
    def patch(self, request, pk):
        corps = CorpsPatchSerializer(data=request.data)
        if not corps.is_valid():
            return _corps_invalide(corps)
        acte = _acte_ou_404(request, pk)
        langue = corps.validated_data['langue']
        try:
            acte = services.modifier(acte, corps.validated_data['surcharges'],
                                     request.user, langue)
        except services.ErreurActe as exc:
            return _erreur(exc)
        return _detail(acte, langue, request=request)


class ActePdfView(APIView):
    """Le PDF d'un acte : vivant pour un brouillon, figé ensuite."""
    permission_classes = [LectureChantiersOuVentes]

    @extend_schema(parameters=[PARAM_LANGUE],
                   responses={(200, 'application/pdf'): OpenApiTypes.BINARY,
                              **_ERREURS})
    def get(self, request, pk):
        langue = _langue(request)
        if langue is None:
            return _refus(T.CODE_CONTENU_INVALIDE,
                          'Langue inconnue : fr ou ar attendu.')
        acte = _acte_ou_404(request, pk)
        pdf = services.pdf_de_l_acte(acte, langue)
        nom = (acte.reference or f'acte-{acte.pk}') + (
            '-ar' if langue == 'ar' else '')
        reponse = HttpResponse(pdf, content_type='application/pdf')
        reponse['Content-Disposition'] = f'inline; filename="{nom}.pdf"'
        return reponse


class ActeEmettreView(_ActeVue):
    """Fige le contenu (français et arabe) et les PDF ; statut « émis »."""

    @extend_schema(request=None,
                   responses={200: DetailActeSerializer, **_ERREURS})
    def post(self, request, pk):
        acte = _acte_ou_404(request, pk)
        try:
            acte, avertissements = services.emettre(acte, request.user)
        except services.ErreurActe as exc:
            return _erreur(exc)
        return _detail(acte, avertissements=avertissements,
                       request=request)


class ActeRouvrirView(_ActeVue):
    """Retour au brouillon d'un acte émis non signé."""

    @extend_schema(request=None,
                   responses={200: DetailActeSerializer, **_ERREURS})
    def post(self, request, pk):
        acte = _acte_ou_404(request, pk)
        try:
            acte = services.rouvrir(acte, request.user)
        except services.ErreurActe as exc:
            return _erreur(exc)
        return _detail(acte, request=request)


def _agent(request):
    return str(request.META.get('HTTP_USER_AGENT', ''))[:300]


def _ip(request):
    from core.throttling import ip_de_requete
    return ip_de_requete(request) or ''


class ActeSignerView(_ActeVue):
    """Signature tracée sur place (composant SignaturePad)."""

    @extend_schema(request=CorpsSignerSerializer,
                   responses={200: DetailActeSerializer, **_ERREURS})
    def post(self, request, pk):
        corps = CorpsSignerSerializer(data=request.data)
        if not corps.is_valid():
            return _corps_invalide(corps)
        acte = _acte_ou_404(request, pk)
        try:
            acte, avertissements = services.signer_sur_place(
                acte, user=request.user, ip=_ip(request), agent=_agent(request),
                **corps.validated_data)
        except services.ErreurActe as exc:
            return _erreur(exc)
        return _detail(acte, avertissements=avertissements,
                       request=request)


class ActeMarquerSigneView(_ActeVue):
    """Signature sur papier : l'exemplaire signé à la main est noté."""

    @extend_schema(request=CorpsMarquerSigneSerializer,
                   responses={200: DetailActeSerializer, **_ERREURS})
    def post(self, request, pk):
        corps = CorpsMarquerSigneSerializer(data=request.data)
        if not corps.is_valid():
            return _corps_invalide(corps)
        acte = _acte_ou_404(request, pk)
        signe_le = corps.validated_data.get('signe_le')
        try:
            acte, avertissements = services.marquer_signe_papier(
                acte, signataire_nom=corps.validated_data['signataire_nom'],
                signe_le=signe_le.isoformat() if signe_le else None,
                user=request.user, ip=_ip(request), agent=_agent(request))
        except services.ErreurActe as exc:
            return _erreur(exc)
        return _detail(acte, avertissements=avertissements,
                       request=request)


class ActeModeleView(APIView):
    """Enregistre les sections de texte de l'acte comme modèle de la société
    (Directeur)."""
    permission_classes = [LectureChantiersOuVentes, EstDirecteur]

    @extend_schema(request=None,
                   responses={200: ModeleActeReponseSerializer, **_ERREURS})
    def post(self, request, pk):
        acte = _acte_ou_404(request, pk)
        return Response({'detail': services.enregistrer_modele(
            acte, request.user)})
