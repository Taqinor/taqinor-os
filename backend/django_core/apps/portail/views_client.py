"""NTPRT10/NTPRT11 — Surface self-service AUTHENTIFIÉE du portail CLIENT.

Ces deux ViewSets sont la version « compte réel » (NTPRT1/2/5) de ce que le
client obtenait jusqu'ici par lien tokenisé. Ils n'ajoutent AUCUNE logique
métier :

* la LECTURE passe par ``apps.ventes.selectors`` (jamais un import de
  ``apps.ventes.models`` — frontière cross-app CLAUDE.md), avec des payloads
  volontairement pauvres : aucun champ de coût/marge, aucune donnée interne ;
* l'ACCEPTATION d'un devis appelle ``apps.ventes.services.accept_devis``, le
  chemin d'acceptation UNIQUE déjà utilisé par la proposition publique
  tokenisée — la chaîne aval (statut accepté → BonCommande/Facture → chantier)
  est donc préservée 1:1 (règle #4), et la trace portail ``AcceptationDevisPortail``
  (FG229) est posée en plus via ``services.signer_acceptation_devis`` ;
* le PAIEMENT réutilise ``services.initier_paiement_facture`` : NO-OP tant que
  ``CMI_ENABLED`` est OFF (aucun appel réseau payant sans clé), avec repli
  virement (RIB de ``CompanyProfile``, lu via ``parametres.selectors``).

Le PDF du devis n'est PAS rendu ici : il reste servi par l'UNIQUE chemin
canonique ``GET /api/django/ventes/devis/<id>/proposal/`` (règle #4), dont la
garde a été ouverte au client PROPRIÉTAIRE (NTPRT10, cf.
``roles.permissions.IsInternalWriterOrPortalClientOwner``).

SÉCURITÉ — chaque endpoint exige ``IsPortalClientUser`` : portée EXACTEMENT
``portail_client`` (un compte fournisseur/partenaire est refusé même s'il est
« portail ») ET un ``portail_client_id`` non nul. Tout accès à un document
passe ensuite par un sélecteur qui exige le triplet (société, client, id) : un
document d'autrui est INTROUVABLE (404), jamais « trouvé puis refusé ».
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.roles.permissions import IsPortalClientUser, portal_scope_id

from . import services

#: Valeurs acceptées comme « oui » pour le consentement e-signature (QX9).
_VRAI = (True, 'true', 'True', '1', 1, 'on')


def _scope(request):
    """(société, client_id) du compte portail appelant.

    AUD148 (a) — POINT UNIQUE du chemin JWT client : c'est la porte que
    traversent TOUTES les méthodes des trois ViewSets self-service ci-dessous.
    On y horodate ``ComptePortailClient.derniere_connexion`` (au plus une fois
    par heure, cf. ``services.enregistrer_connexion_portail``) — la colonne
    était affichée par l'écran ERP et n'était écrite par aucun code, donc vide
    le jour où l'on cherche qui a consulté quoi.
    """
    company = request.user.company
    client_id = portal_scope_id(request.user)
    _noter_connexion(company, client_id)
    return company, client_id


def _noter_connexion(company, client_id):
    """Horodatage best-effort : une panne de trace n'a jamais fermé un
    portail."""
    try:
        from .selectors import etat_compte_portail_client
        etat = etat_compte_portail_client(
            getattr(company, 'id', None), client_id)
        if etat is not None:
            services.enregistrer_connexion_portail(etat[0], etat[2])
    except Exception:  # noqa: BLE001 - la trace ne casse jamais l'accès
        pass


def _ip(request):
    return request.META.get('REMOTE_ADDR')


class MesDevisPortailViewSet(viewsets.ViewSet):
    """NTPRT10 — « Mes devis » : liste, détail, acceptation."""

    permission_classes = [IsPortalClientUser]

    def list(self, request):
        from apps.ventes.selectors import devis_du_client_portail
        company, client_id = _scope(request)
        return Response(
            {'results': devis_du_client_portail(company, client_id)})

    def retrieve(self, request, pk=None):
        from apps.ventes.selectors import devis_du_client_portail
        company, client_id = _scope(request)
        for ligne in devis_du_client_portail(company, client_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='accepter',
            permission_classes=[IsPortalClientUser])
    def accepter(self, request, pk=None):
        """Accepte le devis via le chemin d'acceptation UNIQUE de ``ventes``.

        Exige un nom signataire ET un consentement EXPLICITE à la signature
        électronique (QX9, loi 43-20) : le consentement ne défaute jamais à
        vrai. Idempotent — un second envoi ne re-signe pas.
        """
        from apps.ventes.selectors import devis_du_client_portail_obj
        from apps.ventes.services import AcceptError, accept_devis

        company, client_id = _scope(request)
        devis = devis_du_client_portail_obj(company, client_id, pk)
        if devis is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'detail': 'Votre nom est requis pour signer le devis.'},
                status=status.HTTP_400_BAD_REQUEST)
        if request.data.get('consent_esign') not in _VRAI:
            return Response(
                {'detail': 'Votre consentement explicite à la signature '
                           'électronique est requis pour accepter le devis.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            accept_devis(
                devis=devis,
                user=request.user,
                nom=nom,
                option=(request.data.get('option') or '').strip(),
                ip=_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
                consentement=True,
            )
        except AcceptError as exc:
            return Response(
                {'detail': exc.message},
                status=(status.HTTP_409_CONFLICT if exc.conflict
                        else status.HTTP_400_BAD_REQUEST))

        # Trace portail (FG229) — posée APRÈS la bascule, jamais à sa place.
        #
        # AUD145 — le ``get_or_create`` tournait HORS transaction et sans
        # contrainte d'unicité : deux POST concurrents (le double-clic du
        # client sur « J'accepte ») créaient DEUX preuves du même devis, avec
        # deux horodatages. Le verrou d'``accept_devis`` ne couvre que le
        # DEVIS. On englobe donc création + signature dans UNE transaction, et
        # on rattrape l'``IntegrityError`` que la nouvelle contrainte
        # ``uniq_acceptation_portail_devis`` lève sur le perdant de la course :
        # il RELIT la preuve du gagnant au lieu d'en fabriquer une seconde.
        from django.db import IntegrityError, transaction

        from .models import AcceptationDevisPortail
        try:
            with transaction.atomic():
                acceptation, _ = AcceptationDevisPortail.objects.get_or_create(
                    company=company, devis=devis)
                services.signer_acceptation_devis(
                    acceptation, nom=nom, ip=_ip(request))
        except IntegrityError:
            acceptation = AcceptationDevisPortail.objects.filter(
                company=company, devis=devis).first()
            if acceptation is not None:
                services.signer_acceptation_devis(
                    acceptation, nom=nom, ip=_ip(request))

        devis.refresh_from_db(fields=['statut'])
        return Response({
            'detail': 'Devis accepté. Merci !',
            'reference': devis.reference,
            'statut': devis.statut,
        })


class MesFacturesPortailViewSet(viewsets.ViewSet):
    """NTPRT11 — « Mes commandes & factures » : liste, détail, intention de
    paiement (GATED CMI)."""

    permission_classes = [IsPortalClientUser]

    def list(self, request):
        from apps.ventes.selectors import factures_du_client_portail
        company, client_id = _scope(request)
        return Response({
            'results': factures_du_client_portail(company, client_id),
            'paiement_en_ligne_actif': services.cmi_actif(),
        })

    def retrieve(self, request, pk=None):
        from apps.ventes.selectors import factures_du_client_portail
        company, client_id = _scope(request)
        for ligne in factures_du_client_portail(company, client_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='payer',
            permission_classes=[IsPortalClientUser])
    def payer(self, request, pk=None):
        """Crée une intention de paiement locale — JAMAIS d'appel payant.

        Critère NTPRT11 : sans clé CMI, le bouton « Payer » crée une intention
        ``initie`` ET renvoie les coordonnées bancaires (RIB de
        ``CompanyProfile``) comme repli — jamais une erreur. Avec CMI actif, la
        même intention est créée et l'intégration (future) prend le relais dans
        ``services.initier_paiement_facture`` : rien n'est décidé ici.
        """
        from apps.parametres.selectors import company_identity
        from apps.ventes.selectors import facture_du_client_portail

        company, client_id = _scope(request)
        facture = facture_du_client_portail(company, client_id, pk)
        if facture is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        from .models import PaiementFacturePortail
        actif = services.cmi_actif()
        paiement = PaiementFacturePortail.objects.create(
            company=company,
            facture=facture,
            montant=facture.montant_du,
            methode=(PaiementFacturePortail.Methode.CARTE if actif
                     else PaiementFacturePortail.Methode.VIREMENT),
        )
        services.initier_paiement_facture(paiement)
        paiement.refresh_from_db(fields=['reference', 'statut'])

        # Repli virement : UNIQUEMENT le nom, la banque et le RIB de la société
        # émettrice — jamais le reste de son identité légale (on ne déverse pas
        # ``company_identity`` entier vers un écran externe).
        identite = company_identity(company)
        return Response({
            'paiement_id': paiement.id,
            'reference': paiement.reference,
            'statut': paiement.statut,
            'montant': str(paiement.montant),
            'paiement_en_ligne_actif': actif,
            'virement': {
                'beneficiaire': identite.get('nom', ''),
                'banque': identite.get('banque', ''),
                'rib': identite.get('rib', ''),
            },
        })


#: ``MesLivraisonsPortailViewSet`` est un ``ViewSet`` nu (aucun queryset) :
#: drf-spectacular ne peut pas déduire le type de ``{id}`` sur ses routes de
#: détail et le dégradait en "string" avec un avertissement. L'identifiant est
#: la PK entière de la livraison. Déclaré UNE fois et partagé par TOUTES les
#: actions `detail=True` — en oublier une laisse l'avertissement revenir (c'est
#: exactement ce qui est arrivé à ``preuve-photo``).
_ID_LIVRAISON = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description="Identifiant de la livraison du client connecté.",
)


class MesLivraisonsPortailArticleSerializer(serializers.Serializer):
    """Un article d'une livraison — vue CLIENT (jamais un prix ni un coût).

    Déclaré en classe (et non plus par ``inline_serializer``) pour que le
    schéma OpenAPI soit dérivable : drf-spectacular nomme le composant d'après
    la classe en retirant le suffixe ``Serializer``, donc le composant reste
    EXACTEMENT ``MesLivraisonsPortailArticle`` — le contrat publié ne bouge pas.
    """
    designation = serializers.CharField()
    quantite = serializers.FloatField()


class MesLivraisonsPortailLigneSerializer(serializers.Serializer):
    """Une livraison telle que le portail la montre au client.

    Reflet EXACT de ``apps.installations.selectors.livraisons_client_portail``
    (le contrat client-safe testé par XSTK22 : jamais ``cout_transport``,
    jamais un prix d'achat). Même remarque que ci-dessus sur le nom du
    composant : il reste ``MesLivraisonsPortailLigne``.
    """
    id = serializers.IntegerField()
    reference = serializers.CharField()
    chantier_id = serializers.IntegerField(allow_null=True)
    date_prevue = serializers.DateField(allow_null=True)
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    numero_suivi = serializers.CharField(allow_null=True)
    articles = serializers.ListField(
        child=MesLivraisonsPortailArticleSerializer())
    pod_disponible = serializers.BooleanField()
    pod_url = serializers.CharField(allow_null=True)


class MesLivraisonsPortailViewSet(viewsets.ViewSet):
    """WIR216 — « Mes livraisons » : la section portail que le lien de l'email
    ``livraison_en_transit``/``livraison_livree`` (FG228,
    ``apps.installations.livraison_client_notify``) prétendait déjà ouvrir —
    elle n'existait pas (404 systématique).

    Lecture SEULE via ``apps.installations.selectors.livraisons_client_portail``
    (jamais un import de ``apps.installations.models`` — frontière cross-app) :
    ce sélecteur est DÉJÀ le contrat client-safe testé par XSTK22 (jamais
    ``cout_transport`` ni un prix d'achat). Distinct de l'action
    ``LivraisonViewSet.portail`` (INTERNE, ``IsAnyRole`` + ``?client=`` du
    corps de requête — jamais atteignable par un compte portail, cf.
    ``IsAnyRole`` qui exclut explicitement ``portee != interne``) : ICI, le
    client est dérivé du compte portail CONNECTÉ, jamais d'un paramètre."""

    permission_classes = [IsPortalClientUser]
    #: ``viewsets.ViewSet`` n'est pas une ``GenericAPIView`` : sans cet
    #: attribut, drf-spectacular ne peut PAS deviner le sérialiseur de la vue
    #: et journalise « unable to guess serializer » (garde YAPIC6). Ce n'est
    #: pas une déclaration décorative : c'est la ressource principale de ce
    #: ViewSet (une livraison), réutilisée telle quelle dans la réponse de
    #: ``list``. ``preuve`` déclare sa propre forme dans son ``@extend_schema``.
    serializer_class = MesLivraisonsPortailLigneSerializer

    @extend_schema(responses=inline_serializer(
        name='MesLivraisonsPortail',
        fields={
            'results': serializers.ListField(
                child=MesLivraisonsPortailLigneSerializer()),
        }))
    def list(self, request):
        from apps.installations.selectors import livraisons_client_portail
        company, client_id = _scope(request)
        return Response(
            {'results': livraisons_client_portail(company, client_id)})

    @extend_schema(parameters=[_ID_LIVRAISON], responses=inline_serializer(
        name='MesLivraisonsPortailPreuve',
        fields={
            'livraison_id': serializers.IntegerField(),
            'livraison_reference': serializers.CharField(),
            'signataire_nom': serializers.CharField(allow_null=True),
            'signature_image': serializers.CharField(allow_null=True),
            'horodatage': serializers.DateTimeField(allow_null=True),
            'note': serializers.CharField(allow_null=True),
            'gps_lat': serializers.CharField(allow_null=True),
            'gps_lng': serializers.CharField(allow_null=True),
            'photo_url': serializers.CharField(allow_null=True),
        }))
    @action(detail=True, methods=['get'], url_path='preuve')
    def preuve(self, request, pk=None):
        """AUD301 — preuve de livraison (FG330) CONSULTABLE par le client.

        Le lien « Voir la preuve de livraison » du portail pointait vers
        l'endpoint INTERNE ``/installations/preuves-livraison/<id>/``
        (``IsAnyRole``, qui exclut explicitement ``portee != 'interne'``) : un
        compte ``portail_client`` obtenait 403 à CHAQUE clic. Ici, le client
        est dérivé du compte CONNECTÉ (jamais d'un paramètre) et la lecture
        passe par ``apps.installations.selectors`` — jamais un import de ses
        modèles. Une livraison d'un autre client (ou d'une autre société) est
        INTROUVABLE : 404, jamais « trouvée puis refusée »."""
        from apps.installations.selectors import (
            preuve_livraison_client_portail,
        )
        company, client_id = _scope(request)
        preuve = preuve_livraison_client_portail(company, client_id, pk)
        if preuve is None:
            return Response({'detail': 'Preuve de livraison introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        preuve.pop('photo_attachment_id', None)
        return Response(preuve)

    @extend_schema(parameters=[_ID_LIVRAISON])
    @action(detail=True, methods=['get'], url_path='preuve-photo')
    def preuve_photo(self, request, pk=None):
        """AUD301 — sert la PHOTO de la preuve de livraison, en ligne.

        L'endpoint générique ``records/attachments/<id>/download/`` est
        ``IsAnyRole`` : il rejouerait exactement le 403 que cette tâche
        corrige. On relaie donc le fichier ici, sous la MÊME garde de portée et
        le MÊME scope client que ``preuve``. ``apps.records`` est une app de
        FONDATION (import direct autorisé) ; le scope, lui, vient du sélecteur
        installations."""
        from django.http import HttpResponse
        from apps.installations.selectors import (
            preuve_livraison_client_portail,
        )
        from apps.records.models import Attachment
        from apps.records.storage import fetch_attachment

        company, client_id = _scope(request)
        preuve = preuve_livraison_client_portail(company, client_id, pk)
        attachment_id = (preuve or {}).get('photo_attachment_id')
        if not attachment_id:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        att = Attachment.objects.filter(
            id=attachment_id, company=company).first()
        if att is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        data, err = fetch_attachment(att.file_key)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(
            data, content_type=att.mime or 'application/octet-stream')
        nom = (att.filename or 'preuve-livraison').replace('"', '')
        resp['Content-Disposition'] = f'inline; filename="{nom}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

class MesDemandesSavPortailViewSet(viewsets.ViewSet):
    """AUD525 — « Mes demandes SAV » : la surface CLIENT de FG233.

    FG233 (ouverture d'un ticket SAV depuis le portail) était du code MORT :
    son seul ViewSet (``DemandeTicketPortailViewSet``) est gardé par
    ``IsResponsableOrAdmin`` — une garde INTERNE, refusée à tout rôle
    ``portail_*``. Aucun compte portail réel ne pouvait donc l'atteindre, et
    la déflection KB (suggestions/consultation) héritait de la même garde :
    jamais exercée par un vrai client.

    Ce ViewSet est la surface authentifiée manquante, sur le même patron que
    ``MesDevisPortailViewSet``/``MesFacturesPortailViewSet`` : garde
    ``IsPortalClientUser``, société ET client résolus du COMPTE connecté
    (jamais du corps de requête). Les écrans internes d'administration des
    demandes (liste, ``prendre_en_charge``) restent inchangés."""

    permission_classes = [IsPortalClientUser]

    @staticmethod
    def _ligne(demande):
        """Payload CLIENT — volontairement pauvre : aucune donnée interne."""
        return {
            'id': demande.id,
            'sujet': demande.sujet,
            'description': demande.description,
            'statut': demande.statut,
            'statut_display': demande.get_statut_display(),
            'chantier_id': demande.chantier_id,
            'ticket_id': demande.ticket_id,
            'date_creation': (demande.date_creation.isoformat()
                              if demande.date_creation else None),
        }

    def _mes_demandes(self, request):
        from .models import DemandeTicketPortail
        company, client_id = _scope(request)
        return DemandeTicketPortail.objects.filter(
            company=company, client_id=client_id)

    def list(self, request):
        return Response({
            'results': [self._ligne(d) for d in self._mes_demandes(request)]})

    def retrieve(self, request, pk=None):
        demande = self._mes_demandes(request).filter(pk=pk).first()
        if demande is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(self._ligne(demande))

    def create(self, request):
        """Ouvre une demande SAV (statut SOUMISE) pour le client connecté.

        ``company`` et ``client`` viennent du compte portail, JAMAIS du
        corps. Le chantier éventuel est vérifié comme appartenant au client
        (un id étranger est ignoré, jamais lié)."""
        from .models import DemandeTicketPortail

        company, client_id = _scope(request)
        sujet = (request.data.get('sujet') or '').strip()[:200]
        if not sujet:
            return Response({'sujet': 'Ce champ est obligatoire.'},
                            status=status.HTTP_400_BAD_REQUEST)
        description = (request.data.get('description') or '').strip()[:4000]

        chantier_id = request.data.get('chantier') or request.data.get(
            'chantier_id')
        if chantier_id:
            from apps.installations.selectors import installation_scoped
            chantier = installation_scoped(company, chantier_id)
            if chantier is None or chantier.client_id != client_id:
                chantier_id = None

        demande = DemandeTicketPortail.objects.create(
            company=company, client_id=client_id, chantier_id=chantier_id,
            sujet=sujet, description=description,
            statut=DemandeTicketPortail.Statut.SOUMISE)
        return Response(self._ligne(demande),
                        status=status.HTTP_201_CREATED)

    # ── XSAV22 — Déflection KB, désormais servie au VRAI client ────────────
    # Lit/écrit UNIQUEMENT via ``apps.kb.selectors``/``apps.kb.services``
    # (jamais ``apps.kb.models``). ``detail=False`` : appelables PENDANT la
    # saisie, avant toute création de demande.

    @action(detail=False, methods=['get'], url_path='suggestions-kb',
            permission_classes=[IsPortalClientUser])
    def suggestions_kb(self, request):
        """Articles KB (publiés + ``visible_portail``) suggérés pendant la
        saisie du sujet — la déflection avant soumission."""
        from apps.kb.selectors import suggestions_portail
        company, _ = _scope(request)
        return Response({'suggestions': suggestions_portail(
            company, request.query_params.get('q', ''))})

    @action(detail=False, methods=['post'], url_path='consulter-article-kb',
            permission_classes=[IsPortalClientUser])
    def consulter_article_kb(self, request):
        """Journalise la consultation d'un article suggéré (déflection)."""
        from apps.kb.services import enregistrer_consultation_portail
        company, _ = _scope(request)
        article_id = request.data.get('article_id')
        if not article_id:
            return Response({'detail': 'article_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'enregistre': enregistrer_consultation_portail(
            company, article_id)})
