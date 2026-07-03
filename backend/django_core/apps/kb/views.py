"""Vues de la Base de connaissances (scopées société, accès admin/responsable).

La base est INTERNE : les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société + l'auteur côté serveur (jamais du corps de
requête). Les versions d'article sont des instantanés numérotés côté serveur
(``services.snapshot_article`` — max(version)+1, JAMAIS count()+1).
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbArticleVersion,
    KbFavori,
    KbLectureObligatoire,
)
from .serializers import (
    KbArticleAclSerializer,
    KbArticleLienSerializer,
    KbArticleSerializer,
    KbArticleVersionSerializer,
    KbFavoriSerializer,
    KbLectureObligatoireSerializer,
)


class _KbBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class KbArticleViewSet(_KbBaseViewSet):
    """Articles de la base de connaissances. Recherche plein texte + filtres.

    Recherche plein-texte (``?search=``) sur titre/contenu/catégorie/tags via le
    ``SearchFilter`` de DRF (``icontains`` côté serveur). Filtres exacts/partiels
    additionnels appliqués dans ``get_queryset`` (KB3) :

    * ``?categorie=`` — catégorie exacte (insensible à la casse).
    * ``?tag=`` — présence du tag dans la liste ``tags`` (``icontains``).
    * ``?statut=`` — statut exact (``brouillon`` / ``publie`` / ``obsolete``).

    Tous les filtres s'appliquent APRÈS le scoping société du ``TenantMixin``
    (``super().get_queryset()``) : un résultat ne peut jamais fuir entre sociétés.
    """
    queryset = KbArticle.objects.select_related('auteur').all()
    serializer_class = KbArticleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'corps', 'categorie', 'tags']
    ordering_fields = ['id', 'titre', 'date_modification']

    def get_queryset(self):
        # Le scoping société est posé en premier par le TenantMixin ; les
        # filtres ci-dessous opèrent donc sur un queryset déjà borné à la
        # société de l'utilisateur (aucune fuite cross-tenant possible).
        qs = super().get_queryset()
        # KB7 — droits d'accès par rôle : restreint aux articles visibles pour
        # l'utilisateur. RÉTRO-COMPATIBLE : un article SANS ACL reste visible de
        # tous (KB2/KB3 inchangés) ; un admin voit tout.
        qs = selectors.visible_articles_qs(qs, self.request.user)
        params = self.request.query_params
        categorie = params.get('categorie')
        if categorie:
            qs = qs.filter(categorie__iexact=categorie)
        tag = params.get('tag')
        if tag:
            qs = qs.filter(tags__icontains=tag)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def list(self, request, *args, **kwargs):
        # XKB16 — journalise une recherche ?search= SANS RÉSULTAT (best-effort,
        # ne bloque jamais la réponse même en cas d'échec d'écriture).
        response = super().list(request, *args, **kwargs)
        terme = request.query_params.get('search')
        if terme:
            data = response.data
            results = data.get('results', data) if isinstance(
                data, dict) else data
            if not results:
                services.journaliser_recherche_vide(
                    request.user.company, terme, utilisateur=request.user)
        return response

    def retrieve(self, request, *args, **kwargs):
        # XKB16 — incrémente le compteur de vues à CHAQUE consultation
        # (distinct de KbLecture, qui est un lu/pas-lu idempotent).
        response = super().retrieve(request, *args, **kwargs)
        article = self.get_object()
        vues = services.incrementer_vues(article)
        if isinstance(response.data, dict):
            response.data['vues'] = vues
        return response

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    def perform_update(self, serializer):
        # XKB14 — un article VERROUILLÉ rejette tout PATCH/PUT venant de
        # quelqu'un sans ACL d'ÉDITION (ou admin) — 403, jamais silencieux.
        article = serializer.instance
        if article.est_verrouille and not selectors.peut_editer(
                article, self.request.user):
            raise PermissionDenied(
                "Cet article est verrouillé : seule une personne avec un "
                "droit d'édition peut le modifier.")
        # Sauvegarde l'article (société re-posée côté serveur) puis fige un
        # instantané versionné du nouvel état.
        article = serializer.save(company=self.request.user.company)
        services.snapshot_article(article, auteur=self.request.user)

    @action(detail=True, methods=['post'], url_path='publier')
    def publier(self, request, pk=None):
        """Passe le statut à ``publie`` et fige une version (instantané)."""
        article = self.get_object()
        article.statut = KbArticle.Statut.PUBLIE
        article.save(update_fields=['statut', 'date_modification'])
        services.snapshot_article(article, auteur=request.user)
        return Response(
            self.get_serializer(article).data)

    @action(detail=True, methods=['post'], url_path='nouvelle-version')
    def nouvelle_version(self, request, pk=None):
        """Fige explicitement une nouvelle version sans changer le statut."""
        article = self.get_object()
        version = services.snapshot_article(article, auteur=request.user)
        return Response(
            KbArticleVersionSerializer(
                version, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='marquer-lu')
    def marquer_lu(self, request, pk=None):
        """Enregistre que l'utilisateur courant a LU cet article (KB7).

        Idempotente : une seule ligne par (article, utilisateur) ; un second
        appel rafraîchit ``lu_le`` sans dupliquer. L'utilisateur agissant et la
        société sont posés côté serveur (jamais du corps de requête). Renvoie le
        résumé de lecture à jour de l'article.
        """
        article = self.get_object()
        services.marquer_lu(article, utilisateur=request.user)
        return Response(selectors.resume_lecture(article))

    @action(detail=True, methods=['get'], url_path='resume-lecture')
    def resume_lecture(self, request, pk=None):
        """Résumé de lecture d'un article : nombre de lecteurs + qui (KB7)."""
        article = self.get_object()
        return Response(selectors.resume_lecture(article))

    @action(detail=True, methods=['get'], url_path='rapport-conformite')
    def rapport_conformite(self, request, pk=None):
        """XKB7 — Rapport de conformité de lecture obligatoire (lus/non-lus)."""
        article = self.get_object()
        return Response(selectors.rapport_conformite_article(article))

    @action(detail=False, methods=['get'], url_path='arbre')
    def arbre(self, request):
        """XKB8 — Arbre des articles visibles (racines → enfants imbriqués)."""
        return Response(selectors.arbre_articles(self.get_queryset()))

    @action(detail=True, methods=['get'], url_path='sommaire')
    def sommaire(self, request, pk=None):
        """XKB10 — Sommaire auto (titres Markdown) d'un article."""
        article = self.get_object()
        return Response(selectors.sommaire_article(article))

    @action(detail=True, methods=['get'], url_path='retroliens')
    def retroliens(self, request, pk=None):
        """XKB11 — Articles qui pointent vers celui-ci (liens entrants)."""
        article = self.get_object()
        return Response(selectors.retroliens(article))

    @action(detail=True, methods=['post'], url_path='enregistrer-comme-gabarit')
    def enregistrer_comme_gabarit(self, request, pk=None):
        """XKB12 — Marque cet article comme gabarit réutilisable."""
        article = self.get_object()
        article.est_gabarit = True
        article.save(update_fields=['est_gabarit'])
        return Response(self.get_serializer(article).data)

    @action(detail=False, methods=['get'], url_path='gabarits')
    def gabarits(self, request):
        """XKB12 — Galerie des gabarits disponibles (société + seedés)."""
        qs = self.get_queryset().filter(est_gabarit=True)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='depuis-gabarit')
    def depuis_gabarit(self, request, pk=None):
        """XKB12 — Crée un nouvel article brouillon pré-rempli depuis ce gabarit."""
        gabarit = self.get_object()
        article = services.creer_depuis_gabarit(
            gabarit, auteur=request.user, company=request.user.company)
        return Response(
            self.get_serializer(article).data, status=201)

    @action(detail=True, methods=['post'], url_path='verifier')
    def verifier(self, request, pk=None):
        """XKB14 — Marque l'article vérifié (badge) jusqu'à ``horizon_jours``
        (défaut 90, accepte 7/30/90 ou tout entier via le corps)."""
        article = self.get_object()
        horizon = request.data.get('horizon_jours', 90)
        try:
            horizon = int(horizon)
        except (TypeError, ValueError):
            horizon = 90
        services.verifier_article(
            article, verificateur=request.user, horizon_jours=horizon)
        return Response(self.get_serializer(article).data)

    @action(detail=True, methods=['post'], url_path='verrouiller')
    def verrouiller(self, request, pk=None):
        """XKB14 — Verrouille l'article (lecture seule, SOP approuvées)."""
        article = self.get_object()
        article.est_verrouille = True
        article.save(update_fields=['est_verrouille'])
        return Response(self.get_serializer(article).data)

    @action(detail=True, methods=['post'], url_path='deverrouiller')
    def deverrouiller(self, request, pk=None):
        """XKB14 — Déverrouille l'article. Requiert un droit d'ÉDITION (ACL)
        ou le palier admin — sinon 403 (le verrou protège vraiment)."""
        article = self.get_object()
        if not selectors.peut_editer(article, request.user):
            raise PermissionDenied(
                "Seule une personne avec un droit d'édition peut "
                "déverrouiller cet article.")
        article.est_verrouille = False
        article.save(update_fields=['est_verrouille'])
        return Response(self.get_serializer(article).data)

    @action(detail=False, methods=['get'], url_path='rapport-peremption')
    def rapport_peremption(self, request):
        """XKB14 — Articles périmés (re-revue due) de la société."""
        return Response(
            selectors.rapport_peremption(request.user.company))

    @action(detail=True, methods=['post'], url_path='toggler-favori')
    def toggler_favori(self, request, pk=None):
        """XKB15 — Favorise/défavorise cet article pour l'utilisateur courant."""
        article = self.get_object()
        actif, _favori = services.toggler_favori(
            article, utilisateur=request.user)
        return Response({'favori': actif})

    @action(detail=False, methods=['get'], url_path='recents')
    def recents(self, request):
        """XKB15 — Articles récemment consultés par l'utilisateur courant."""
        return Response(selectors.recents_pour_utilisateur(request.user))

    @action(detail=False, methods=['get'], url_path='rapport-top-consultes')
    def rapport_top_consultes(self, request):
        """XKB16 — Articles les plus consultés de la société."""
        return Response(
            selectors.rapport_top_consultes(request.user.company))

    @action(detail=False, methods=['get'], url_path='rapport-moins-consultes')
    def rapport_moins_consultes(self, request):
        """XKB16 — Articles les moins consultés de la société."""
        return Response(
            selectors.rapport_moins_consultes(request.user.company))

    @action(detail=False, methods=['get'], url_path='rapport-lacunes-connaissance')
    def rapport_lacunes_connaissance(self, request):
        """XKB16 — Termes cherchés jamais servis (rapport de lacunes)."""
        return Response(
            selectors.rapport_lacunes_connaissance(request.user.company))

    @action(detail=True, methods=['post'], url_path='deplacer')
    def deplacer(self, request, pk=None):
        """XKB8 — Déplace (re-parente) tout un sous-arbre + réordonne.

        Attend ``{"parent": <id ou null>, "ordre": <entier, optionnel>}``.
        Réutilise ``KbArticleSerializer.validate_parent`` (même-société +
        anti-cycle) via une validation partielle.
        """
        article = self.get_object()
        ser = self.get_serializer(
            article, data=request.data, partial=True,
            context={'request': request})
        ser.is_valid(raise_exception=True)
        ser.save(company=self.request.user.company)
        return Response(ser.data)


class KbArticleVersionViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Historique des versions d'article (lecture seule). Filtrable par
    ``?article=<id>``. Société scopée côté serveur."""
    queryset = KbArticleVersion.objects.select_related(
        'article', 'auteur').all()
    serializer_class = KbArticleVersionSerializer
    permission_classes = [IsResponsableOrAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        article = self.request.query_params.get('article')
        if article:
            qs = qs.filter(article_id=article)
        return qs


class KbArticleLienViewSet(_KbBaseViewSet):
    """Liens article → produit / équipement / type d'intervention (refs lâches).

    ``company`` est posée côté serveur (TenantMixin) ; l'``article`` reçu est
    validé même-société par le sérialiseur. Filtres optionnels ``?article=<id>``
    et ``?type_cible=<type>``.

    Recherche INVERSE — un écran SAV / chantier demande « quels articles sont
    liés au produit X » via ``?type_cible=produit&cible_id=<id>`` : quand
    ``cible_id`` est fourni, la liste est restreinte à cette cible. L'action
    ``article-liens/articles/?type_cible=&cible_id=`` renvoie directement les
    articles liés (id/titre/statut), scopés société.
    """
    queryset = KbArticleLien.objects.select_related('article').all()
    serializer_class = KbArticleLienSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        article = params.get('article')
        if article:
            qs = qs.filter(article_id=article)
        type_cible = params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        cible_id = params.get('cible_id')
        if cible_id:
            qs = qs.filter(cible_id=cible_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def articles(self, request):
        """Recherche inverse : articles liés à une cible (id/titre/statut).

        Attend ``?type_cible=<type>&cible_id=<id>`` ; renvoie la liste des
        articles de la société rattachés à cette cible via le sélecteur
        ``articles_pour_cible`` (scopé ``request.user.company``).
        """
        type_cible = request.query_params.get('type_cible')
        cible_id = request.query_params.get('cible_id')
        if not type_cible or not cible_id:
            return Response(
                {'detail': 'type_cible et cible_id sont requis.'}, status=400)
        return Response(selectors.articles_pour_cible(
            request.user.company, type_cible, cible_id))


class KbArticleAclViewSet(_KbBaseViewSet):
    """Droits d'accès par rôle sur les articles (KB7) — gestion des ACL.

    ``company`` est posée côté serveur (TenantMixin) ; l'``article`` reçu est
    validé même-société par le sérialiseur. Filtres optionnels ``?article=<id>``
    et ``?niveau=<lecture|edition>``. Accès réservé au palier
    Administrateur/Responsable comme le reste de la base.
    """
    queryset = KbArticleAcl.objects.select_related('article').all()
    serializer_class = KbArticleAclSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        article = params.get('article')
        if article:
            qs = qs.filter(article_id=article)
        niveau = params.get('niveau')
        if niveau:
            qs = qs.filter(niveau=niveau)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class KbLectureObligatoireViewSet(_KbBaseViewSet):
    """XKB7 — Assignations de lecture obligatoire (article ↔ utilisateur/rôle).

    ``company`` est posée côté serveur (TenantMixin) ; l'``article`` reçu est
    validé même-société par le sérialiseur. Filtre optionnel ``?article=<id>``.
    """
    queryset = KbLectureObligatoire.objects.select_related(
        'article', 'utilisateur').all()
    serializer_class = KbLectureObligatoireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'echeance']

    def get_queryset(self):
        qs = super().get_queryset()
        article = self.request.query_params.get('article')
        if article:
            qs = qs.filter(article_id=article)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class KbFavoriViewSet(_KbBaseViewSet):
    """XKB15 — « Mes favoris » : STRICTEMENT personnel — un utilisateur ne
    voit jamais les favoris d'un autre, même dans la même société (le scoping
    société du TenantMixin est encore affiné par l'utilisateur courant)."""
    queryset = KbFavori.objects.select_related('article').all()
    serializer_class = KbFavoriSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, utilisateur=self.request.user)
