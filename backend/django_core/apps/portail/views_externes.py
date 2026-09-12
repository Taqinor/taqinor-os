"""NTPRT20/NTPRT27 — Tableaux de bord des portails FOURNISSEUR et PARTENAIRE.

Deux endpoints en LECTURE SEULE, symétriques du portail client :

* ``GET /api/django/portail/fournisseur/tableau-de-bord/``
* ``GET /api/django/portail/partenaire/tableau-de-bord/``

Chacun est gardé par la portée EXACTE correspondante
(``IsPortalFournisseurUser`` / ``IsPortalPartenaireUser``, NTPRT5+) : un compte
CLIENT — ou un compte portail d'une autre portée, ou un interne — est refusé.
La garde exige aussi un rattachement non nul, et les sélecteurs appelés exigent
le couple (société, entité) : un compte sans entité voit des compteurs à ZÉRO,
jamais les chiffres de la société entière.

Les lectures passent par ``stock.selectors`` / ``crm.selectors`` (jamais un
import de leurs ``models`` depuis portail — frontière cross-app CLAUDE.md).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.roles.permissions import (
    IsPortalFournisseurUser, IsPortalPartenaireUser, portal_scope_id,
)


@api_view(['GET'])
@permission_classes([IsPortalFournisseurUser])
def tableau_de_bord_fournisseur(request):
    """NTPRT20 — cartes résumé du fournisseur connecté."""
    from apps.stock.selectors import resume_portail_fournisseur
    return Response(resume_portail_fournisseur(
        request.user.company, portal_scope_id(request.user)))


@api_view(['GET'])
@permission_classes([IsPortalPartenaireUser])
def tableau_de_bord_partenaire(request):
    """NTPRT27 — cartes résumé du partenaire connecté."""
    from apps.crm.selectors import resume_portail_partenaire
    return Response(resume_portail_partenaire(
        request.user.company, portal_scope_id(request.user)))


#: ``MesBcfPortailFournisseurViewSet`` est un ``ViewSet`` nu (aucun queryset) :
#: sans type explicite, drf-spectacular dégrade le ``{id}`` de ses routes de
#: détail en "string" (garde YAPIC6). L'identifiant est la PK entière du BCF.
_ID_BCF = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description='Identifiant du bon de commande du fournisseur connecté.',
)


class MesBcfPortailLigneArticleSerializer(serializers.Serializer):
    """Un article commandé — vue FOURNISSEUR (jamais un prix, jamais une
    marge : à ce stade il n'a besoin que du QUOI et du QUAND)."""
    produit_nom = serializers.CharField()
    quantite = serializers.FloatField()
    quantite_recue = serializers.FloatField()


class MesBcfPortailLigneSerializer(serializers.Serializer):
    """Un bon de commande tel que le portail le montre au fournisseur.

    Reflet EXACT de ``apps.stock.selectors.bcf_portail_fournisseur``. Déclaré
    en classe (et non via ``inline_serializer``) pour que le composant OpenAPI
    porte un nom stable (``MesBcfPortailLigne``).
    """
    id = serializers.IntegerField()
    reference = serializers.CharField()
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    date_commande = serializers.DateField(allow_null=True)
    date_livraison_prevue = serializers.DateField(allow_null=True)
    date_confirmee_fournisseur = serializers.DateField(allow_null=True)
    numero_confirmation_fournisseur = serializers.CharField(allow_blank=True)
    a_confirmer = serializers.BooleanField()
    lignes = serializers.ListField(
        child=MesBcfPortailLigneArticleSerializer())


class MesBcfPortailFournisseurViewSet(viewsets.ViewSet):
    """NTPRT21 — « Mes BCF à confirmer » du portail fournisseur AUTHENTIFIÉ.

    Porte XPUR22 (portail public tokenisé) sur le COMPTE fournisseur réel : le
    fournisseur est résolu depuis le compte connecté (``portal_scope_id``),
    JAMAIS depuis un paramètre ni un corps de requête. Les deux opérations
    passent par ``apps.stock`` (selector pour la lecture, service pour
    l'écriture) — jamais un import de ses ``models``.

    La confirmation réutilise le CŒUR commun
    (``stock.services._appliquer_confirmation_bcf_fournisseur``) partagé avec
    le chemin tokenisé : le comportement est identique bit à bit, seule
    l'authentification change (critère d'acceptation NTPRT21). La date
    DEMANDÉE d'origine n'est donc jamais écrasée.
    """

    permission_classes = [IsPortalFournisseurUser]
    #: ``viewsets.ViewSet`` n'est pas une ``GenericAPIView`` : sans cet
    #: attribut drf-spectacular ne peut pas deviner le sérialiseur (YAPIC6).
    serializer_class = MesBcfPortailLigneSerializer

    @extend_schema(responses=inline_serializer(
        name='MesBcfPortail',
        fields={
            'results': serializers.ListField(
                child=MesBcfPortailLigneSerializer()),
        }))
    def list(self, request):
        from apps.stock.selectors import bcf_portail_fournisseur
        return Response({'results': bcf_portail_fournisseur(
            request.user.company, portal_scope_id(request.user))})

    @extend_schema(parameters=[_ID_BCF], responses=MesBcfPortailLigneSerializer)
    def retrieve(self, request, pk=None):
        from apps.stock.selectors import bcf_portail_fournisseur
        for ligne in bcf_portail_fournisseur(
                request.user.company, portal_scope_id(request.user)):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @extend_schema(parameters=[_ID_BCF], responses=inline_serializer(
        name='MesBcfPortailConfirmation',
        fields={
            'id': serializers.IntegerField(),
            'reference': serializers.CharField(),
            'date_confirmee_fournisseur': serializers.DateField(),
            'numero_confirmation_fournisseur': serializers.CharField(
                allow_blank=True),
            'detail': serializers.CharField(),
        }))
    @action(detail=True, methods=['post'], url_path='confirmer',
            permission_classes=[IsPortalFournisseurUser])
    def confirmer(self, request, pk=None):
        """Confirme le BCF et propose une date d'arrivée.

        Les erreurs NOMMENT le champ fautif (``date_confirmee``) : un
        « Non enregistré » générique laisserait le fournisseur deviner.
        """
        from django.utils.dateparse import parse_date

        from apps.stock.services import confirmer_bcf_compte_fournisseur

        brute = str(request.data.get('date_confirmee') or '').strip()
        if not brute:
            return Response(
                {'date_confirmee': "La date d'arrivée que vous confirmez est "
                                   'obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        date_confirmee = parse_date(brute)
        if date_confirmee is None:
            return Response(
                {'date_confirmee': "Date invalide : utilisez le format "
                                   'AAAA-MM-JJ.'},
                status=status.HTTP_400_BAD_REQUEST)

        numero = str(request.data.get('numero_confirmation') or '')[:100]
        try:
            bc = confirmer_bcf_compte_fournisseur(
                request.user.company, portal_scope_id(request.user), pk,
                date_confirmee=date_confirmee, numero_confirmation=numero)
        except ValueError:
            # Le BCF d'un autre fournisseur est INTROUVABLE, jamais « trouvé
            # puis refusé » : la réponse ne dit pas qu'il existe ailleurs.
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        return Response({
            'id': bc.id,
            'reference': bc.reference,
            'date_confirmee_fournisseur': bc.date_confirmee_fournisseur,
            'numero_confirmation_fournisseur': (
                bc.numero_confirmation_fournisseur or ''),
            'detail': 'Merci, votre date de livraison a bien été enregistrée.',
        })


#: Même remarque que ``_ID_BCF`` : ``ViewSet`` nu ⇒ type explicite (YAPIC6).
_ID_SOUMISSION = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description='Identifiant de la soumission du partenaire connecté.',
)


class MesSoumissionsPortailLigneSerializer(serializers.Serializer):
    """Une soumission de lead telle que le portail la montre au partenaire.

    Reflet EXACT de ``apps.crm.selectors.soumissions_partenaire_portail`` :
    ce que le partenaire a saisi + l'avancement. Aucune donnée interne (ni
    propriétaire du lead, ni notes commerciales, ni montant).
    """
    id = serializers.IntegerField()
    nom_prospect = serializers.CharField()
    telephone_prospect = serializers.CharField(allow_blank=True)
    email_prospect = serializers.CharField(allow_blank=True)
    ville = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    converti = serializers.BooleanField()
    date_soumission = serializers.DateTimeField(allow_null=True)


class MesSoumissionsPortailPartenaireViewSet(viewsets.ViewSet):
    """NTPRT28 — « Enregistrer une affaire » (deal registration) du portail
    PARTENAIRE authentifié.

    Branche le formulaire partenaire sur le modèle FG234
    (``crm.SoumissionLeadPartenaire``) déjà présent — aucune seconde
    modélisation des soumissions. Le ViewSet INTERNE
    (``SoumissionLeadPartenaireViewSet``, garde interne) reste inchangé : il
    porte la QUALIFICATION, qui demeure un acte interne ; la soumission ne
    crée jamais de lead toute seule.

    Le partenaire est résolu depuis le compte connecté (``portal_scope_id``),
    jamais du corps : ``company`` et ``partenaire`` sont posés côté serveur.
    Lecture et écriture passent par ``apps.crm`` (selector / service) — jamais
    un import de ses ``models``.

    ANTI-DOUBLON (critère d'acceptation) : une re-soumission du MÊME prospect
    (même email) par le MÊME partenaire à moins de 30 jours est REFUSÉE avec
    un message « déjà soumis » qui désigne la soumission existante — jamais
    une seconde ligne créée en silence.
    """

    permission_classes = [IsPortalPartenaireUser]
    serializer_class = MesSoumissionsPortailLigneSerializer

    def _scope(self, request):
        return request.user.company, portal_scope_id(request.user)

    @extend_schema(responses=inline_serializer(
        name='MesSoumissionsPortail',
        fields={
            'results': serializers.ListField(
                child=MesSoumissionsPortailLigneSerializer()),
        }))
    def list(self, request):
        from apps.crm.selectors import soumissions_partenaire_portail
        company, partenaire_id = self._scope(request)
        return Response({'results': soumissions_partenaire_portail(
            company, partenaire_id)})

    @extend_schema(parameters=[_ID_SOUMISSION],
                   responses=MesSoumissionsPortailLigneSerializer)
    def retrieve(self, request, pk=None):
        from apps.crm.selectors import soumissions_partenaire_portail
        company, partenaire_id = self._scope(request)
        for ligne in soumissions_partenaire_portail(company, partenaire_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @extend_schema(responses=MesSoumissionsPortailLigneSerializer)
    def create(self, request):
        """Enregistre une affaire. Les erreurs NOMMENT le champ fautif."""
        from apps.crm.selectors import soumissions_partenaire_portail
        from apps.crm.services import soumettre_lead_partenaire

        company, partenaire_id = self._scope(request)

        nom = str(request.data.get('nom_prospect') or '').strip()
        if not nom:
            return Response(
                {'nom_prospect': 'Le nom du prospect est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        email = str(request.data.get('email_prospect') or '').strip()
        telephone = str(request.data.get('telephone_prospect') or '').strip()
        if not email and not telephone:
            return Response(
                {'email_prospect': 'Indiquez au moins un email ou un '
                                   'téléphone pour que nous puissions '
                                   'joindre ce prospect.'},
                status=status.HTTP_400_BAD_REQUEST)

        soumission, doublon = soumettre_lead_partenaire(
            company, partenaire_id, {
                'nom_prospect': nom,
                'email_prospect': email,
                'telephone_prospect': telephone,
                'ville': request.data.get('ville'),
                'note': request.data.get('note'),
            })
        if doublon is not None:
            return Response(
                {'email_prospect': 'Déjà soumis : vous avez enregistré ce '
                                   'prospect le '
                                   f'{doublon.date_soumission:%d/%m/%Y}. '
                                   'Votre antériorité est conservée.',
                 'soumission_existante': doublon.id},
                status=status.HTTP_409_CONFLICT)
        if soumission is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        for ligne in soumissions_partenaire_portail(company, partenaire_id):
            if ligne['id'] == soumission.id:
                return Response(ligne, status=status.HTTP_201_CREATED)
        return Response({'id': soumission.id},
                        status=status.HTTP_201_CREATED)


class MesCommissionsPortailLigneSerializer(serializers.Serializer):
    """Une ligne de commission telle que le portail la montre au partenaire.

    Reflet EXACT de ``apps.crm.selectors.releve_commissions_partenaire``. Le
    devis et le lead ne sont que des RÉFÉRENCES opaques : le partenaire sait
    sur quoi porte sa commission, jamais ce que contient le dossier.
    """
    id = serializers.IntegerField()
    date_creation = serializers.DateTimeField(allow_null=True)
    devis_id = serializers.IntegerField(allow_null=True)
    lead_id = serializers.IntegerField(allow_null=True)
    base_ht = serializers.CharField()
    taux = serializers.CharField()
    montant = serializers.CharField()
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    paye_le = serializers.DateField(allow_null=True)


class MesCommissionsPortailTotauxSerializer(serializers.Serializer):
    """Sous-sommes du relevé. Elles s'additionnent au total, par
    construction : ce sont les mêmes lignes."""
    due = serializers.CharField()
    payee = serializers.CharField()
    annulee = serializers.CharField()
    total = serializers.CharField()


class MesCommissionsPortailReleveSerializer(serializers.Serializer):
    """Le relevé complet servi au partenaire."""
    partenaire_nom = serializers.CharField(allow_blank=True)
    debut = serializers.DateField(allow_null=True)
    fin = serializers.DateField(allow_null=True)
    lignes = serializers.ListField(child=MesCommissionsPortailLigneSerializer())
    totaux = MesCommissionsPortailTotauxSerializer()


#: NTPRT30 — bornes de période du relevé (facultatives, INCLUSIVES).
_PARAMS_PERIODE = [
    OpenApiParameter(
        name='debut', type=OpenApiTypes.DATE,
        location=OpenApiParameter.QUERY, required=False,
        description='Début de période (AAAA-MM-JJ, inclus).'),
    OpenApiParameter(
        name='fin', type=OpenApiTypes.DATE,
        location=OpenApiParameter.QUERY, required=False,
        description='Fin de période (AAAA-MM-JJ, incluse).'),
]


class MesCommissionsPortailPartenaireViewSet(viewsets.ViewSet):
    """NTPRT30 — « Mes commissions » : relevé + export PDF, portail PARTENAIRE.

    Lecture SEULE : le partenaire consulte, il ne solde jamais sa propre
    commission (``marquer_payee`` reste une action INTERNE). Le partenaire est
    résolu depuis le compte connecté ; la lecture passe par
    ``apps.crm.selectors`` — jamais un import de ses ``models``.

    L'écran et le PDF consomment le MÊME relevé : le total du PDF est, par
    construction, celui affiché, lui-même somme des lignes rendues (critère
    d'acceptation NTPRT30). Le PDF emprunte ``core.pdf.render_pdf`` (ARC11),
    jamais le moteur de devis premium (règle #4).
    """

    permission_classes = [IsPortalPartenaireUser]
    serializer_class = MesCommissionsPortailReleveSerializer

    @staticmethod
    def _bornes(request):
        """``(debut, fin, erreur)`` — une borne illisible NOMME son champ."""
        from django.utils.dateparse import parse_date

        bornes = {}
        for champ in ('debut', 'fin'):
            brute = (request.query_params.get(champ) or '').strip()
            if not brute:
                bornes[champ] = None
                continue
            valeur = parse_date(brute)
            if valeur is None:
                return None, None, {
                    champ: 'Date invalide : utilisez le format AAAA-MM-JJ.'}
            bornes[champ] = valeur
        return bornes['debut'], bornes['fin'], None

    def _releve(self, request):
        from apps.crm.selectors import releve_commissions_partenaire

        debut, fin, erreur = self._bornes(request)
        if erreur is not None:
            return None, erreur
        return releve_commissions_partenaire(
            request.user.company, portal_scope_id(request.user),
            debut=debut, fin=fin), None

    @extend_schema(parameters=_PARAMS_PERIODE,
                   responses=MesCommissionsPortailReleveSerializer)
    def list(self, request):
        releve, erreur = self._releve(request)
        if erreur is not None:
            return Response(erreur, status=status.HTTP_400_BAD_REQUEST)
        return Response(releve)

    @extend_schema(parameters=_PARAMS_PERIODE,
                   responses={(200, 'application/pdf'): OpenApiTypes.BINARY})
    @action(detail=False, methods=['get'], url_path='pdf',
            permission_classes=[IsPortalPartenaireUser])
    def pdf(self, request):
        """Relevé en PDF — même contenu et même total que l'écran."""
        from django.http import HttpResponse

        from .branding import marque_portail
        from .pdf_commissions import render_releve_commissions_pdf

        releve, erreur = self._releve(request)
        if erreur is not None:
            return Response(erreur, status=status.HTTP_400_BAD_REQUEST)

        societe = marque_portail(request.user.company).get('nom_affichage', '')
        pdf = render_releve_commissions_pdf(releve, societe=societe)
        reponse = HttpResponse(pdf, content_type='application/pdf')
        reponse['Content-Disposition'] = (
            'attachment; filename="releve-commissions.pdf"')
        reponse['X-Content-Type-Options'] = 'nosniff'
        return reponse


class CandidatureFournisseurThrottle(SimpleRateThrottle):
    """NTPRT25 — même patron de limitation que XPUR22 (par IP, cache-based,
    aucune dépendance nouvelle). Un formulaire d'auto-inscription PUBLIC est
    une surface d'écriture anonyme : sans plafond, c'est un injecteur de
    référentiel."""

    scope = 'portail_candidature_fournisseur'
    rate = '10/hour'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([CandidatureFournisseurThrottle])
def candidature_fournisseur(request):
    """NTPRT25 — auto-inscription d'un fournisseur (PUBLIC, rate-limité).

    La société est résolue par l'en-tête ``Host`` (domaine white-label du
    tenant, même mécanique que NTPRT19) — JAMAIS par un champ du corps : sinon
    n'importe qui poserait une candidature dans le référentiel du tenant de son
    choix. Hôte non reconnu ⇒ 404, jamais de fournisseur orphelin ni rattaché
    au mauvais tenant.

    Le fournisseur naît ``statut_validation='en_attente_validation'`` : il
    n'apparaît dans AUCUNE liste de sourcing automatique tant qu'un
    administrateur interne n'a pas tranché (``decider-candidature``). Seuls les
    champs de ``CHAMPS_CANDIDATURE_FOURNISSEUR`` sont lus du corps — ni
    ``statut``, ni ``statut_validation``, ni ``company``.

    La réponse ne renvoie AUCUNE donnée de la société ni l'id créé : un
    formulaire public n'a pas à savoir ce qui existe de l'autre côté.
    """
    from apps.stock.services import enregistrer_candidature_fournisseur

    from .branding import company_pour_hote

    company = company_pour_hote(request.get_host())
    if company is None:
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    fournisseur = enregistrer_candidature_fournisseur(company, request.data)
    if fournisseur is None:
        return Response(
            {'detail': 'Le nom de votre société est requis.'},
            status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {'detail': 'Votre candidature a bien été enregistrée. Elle sera '
                   'examinée par nos équipes.'},
        status=status.HTTP_201_CREATED)
