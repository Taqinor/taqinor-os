"""Vues de la Base de connaissances (scopées société, accès admin/responsable).

La base est INTERNE : les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société + l'auteur côté serveur (jamais du corps de
requête). Les versions d'article sont des instantanés numérotés côté serveur
(``services.snapshot_article`` — max(version)+1, JAMAIS count()+1).
"""
from django.http import HttpResponse
from rest_framework import filters, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes, throttle_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from authentication.mixins import TenantMixin
from authentication.permissions import HasPermissionOrLegacy
from core.permissions import WriteScopedPermissionMixin

from . import selectors, services
from .models import (
    BlocReutilisable,
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbArticleVersion,
    KbFavori,
    KbLectureObligatoire,
    KbParcours,
    KbParcoursArticle,
    KbParcoursAssignation,
    PartageArticleKb,
)
from .serializers import (
    BlocReutilisableSerializer,
    KbArticleAclSerializer,
    KbArticleLienSerializer,
    KbArticleSerializer,
    KbArticleVersionSerializer,
    KbFavoriSerializer,
    KbLectureObligatoireSerializer,
    KbParcoursArticleSerializer,
    KbParcoursAssignationSerializer,
    KbParcoursSerializer,
    PartageArticleKbSerializer,
)


class _KbBaseViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + lecture/écriture fine-grainées (YRBAC3).

    ``kb_voir`` gate les méthodes sûres (GET/HEAD/OPTIONS), ``kb_gerer`` gate
    l'écriture (POST/PUT/PATCH/DELETE + actions custom). Comptes légacy sans
    rôle fin : repli historique Administrateur/Responsable préservé.
    """
    read_permission = 'kb_voir'
    write_permission = 'kb_gerer'


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
        etait_traduction = article.traduction_de_id is not None
        article = serializer.save(company=self.request.user.company)
        services.snapshot_article(article, auteur=self.request.user)
        # XKB18 — la source qui avance périme ses traductions ; une
        # traduction elle-même mise à jour redevient à jour.
        if etait_traduction and article.traduction_perimee:
            article.traduction_perimee = False
            article.save(update_fields=['traduction_perimee'])
        else:
            services.marquer_traductions_perimees(article)

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

    @action(detail=True, methods=['get'], url_path='descendants-count',
            permission_classes=[HasPermissionOrLegacy('kb_voir')])
    def descendants_count(self, request, pk=None):
        """VX241(a) — compte RÉEL du sous-arbre qu'un DELETE cascaderait
        (``parent`` est ``on_delete=CASCADE``, ``apps/kb/models.py``) : le
        frontend affiche ce nombre AVANT confirmation (``KbPage.jsx``,
        ``handleRemove``) plutôt qu'un message générique qui mentait par
        omission sur ce qui allait réellement disparaître.

        Parcours PYTHON scopé à la société ENTIÈRE (pas le queryset filtré
        par visibilité ACL du viewset — une cascade DB ne consulte aucune
        ACL) : une seule requête ``(id, parent_id)`` puis BFS en mémoire,
        robuste à un cycle éventuel déjà en base (chaque id compté une fois).
        """
        article = self.get_object()
        paires = KbArticle.objects.filter(
            company=article.company_id).values_list('id', 'parent_id')
        enfants = {}
        for id_, parent_id in paires:
            if parent_id is not None:
                enfants.setdefault(parent_id, []).append(id_)
        vus = set()
        pile = [article.id]
        while pile:
            courant = pile.pop()
            for enfant_id in enfants.get(courant, []):
                if enfant_id not in vus:
                    vus.add(enfant_id)
                    pile.append(enfant_id)
        return Response({'nb_descendants': len(vus)})

    @action(detail=True, methods=['get'], url_path='items')
    def items(self, request, pk=None):
        """ZGED11 — Sous-articles de cet article rendus comme une COLLECTION
        structurée. ``?vue=kanban|cartes|liste|calendrier`` (défaut
        ``liste``) ; ``?propriete=<code>`` sélectionne la propriété de
        regroupement (kanban) ou de datation (calendrier)."""
        article = self.get_object()
        vue = request.query_params.get('vue', 'liste')
        propriete = request.query_params.get('propriete')
        enfants = self.get_queryset().filter(parent=article)
        return Response(
            selectors.items_parcours_vue(
                enfants, vue=vue, propriete=propriete))

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

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, pk=None):
        """XKB21 — Duplique cet article en une copie BROUILLON indépendante.

        Attend ``{"avec_sous_articles": true|false}`` (défaut false). Avec
        ``avec_sous_articles=true``, clone récursivement tout le sous-arbre
        sous la nouvelle copie (jamais sous l'original)."""
        article = self.get_object()
        avec_sous_articles = bool(request.data.get('avec_sous_articles', False))
        copie = services.dupliquer_article(
            article, auteur=request.user, company=request.user.company,
            avec_sous_articles=avec_sous_articles)
        return Response(self.get_serializer(copie).data, status=201)

    @action(detail=True, methods=['post'], url_path='traduire')
    def traduire(self, request, pk=None):
        """XKB18 — Crée la traduction ``langue`` de cet article (brouillon,
        rattachée à la source via ``traduction_de``). Attend
        ``{"langue": "ar"|"en"|"fr"}``."""
        article = self.get_object()
        langue = request.data.get('langue')
        if langue not in dict(KbArticle.LANGUE_CHOICES):
            return Response(
                {'detail': 'Langue invalide (fr, ar ou en attendu).'},
                status=400)
        traduction = services.creer_traduction(
            article, langue=langue, auteur=request.user,
            company=request.user.company)
        return Response(
            self.get_serializer(traduction).data, status=201)

    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None):
        """XKB17 — Export PDF fidèle d'un article (WeasyPrint, jamais le
        moteur devis premium — rule #4). Aucun statut n'est modifié."""
        article = self.get_object()
        pdf_bytes = services.article_to_pdf(article)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="article-{article.id}.pdf"')
        return response

    @action(detail=True, methods=['get'], url_path='export-markdown')
    def export_markdown(self, request, pk=None):
        """XKB17 — Export Markdown fidèle d'un article."""
        article = self.get_object()
        contenu = services.article_to_markdown(article)
        response = HttpResponse(contenu, content_type='text/markdown')
        response['Content-Disposition'] = (
            f'attachment; filename="article-{article.id}.md"')
        return response

    @action(detail=False, methods=['post'], url_path='importer-markdown')
    def importer_markdown(self, request):
        """XKB17 — Importe un fichier/texte Markdown comme nouvel article
        BROUILLON. Attend soit un fichier ``fichier`` (multipart), soit un
        champ texte ``contenu``."""
        upload = request.FILES.get('fichier')
        if upload is not None:
            contenu = upload.read().decode('utf-8', errors='replace')
        else:
            contenu = request.data.get('contenu', '')
        if not contenu:
            return Response(
                {'detail': 'Fournissez un fichier ou un contenu Markdown.'},
                status=400)
        article = services.importer_markdown(
            contenu, company=request.user.company, auteur=request.user)
        return Response(self.get_serializer(article).data, status=201)

    @action(detail=False, methods=['get'], url_path='export-zip')
    def export_zip(self, request):
        """XKB17 — Export ZIP de TOUTE la base de la société (sauvegarde /
        migration, contrôle des données loi 09-08) : articles + pièces
        jointes, scopé STRICTEMENT à la société de l'utilisateur — jamais un
        article d'une autre société."""
        zip_bytes = services.exporter_zip_company(request.user.company)
        response = HttpResponse(zip_bytes, content_type='application/zip')
        response['Content-Disposition'] = (
            'attachment; filename="kb-export.zip"')
        return response

    @action(detail=True, methods=['post', 'delete'], url_path='couverture')
    def couverture(self, request, pk=None):
        """ZGED10 — Téléverse (POST, multipart ``fichier``) ou retire
        (DELETE) l'image de couverture de cet article. Validation
        type/taille via ``records.storage.store_attachment`` — même
        pipeline que les pièces jointes existantes ; le fichier vit
        UNIQUEMENT dans MinIO, jamais en base (seule la clé l'est)."""
        article = self.get_object()
        if request.method == 'DELETE':
            article.couverture_file_key = ''
            article.save(update_fields=['couverture_file_key'])
            return Response(self.get_serializer(article).data)

        from apps.records.storage import store_attachment
        upload = request.FILES.get('fichier')
        if upload is None:
            return Response({'detail': 'Fichier requis.'}, status=400)
        meta, err = store_attachment(upload)
        if err:
            return Response({'detail': err}, status=400)
        article.couverture_file_key = meta['file_key']
        article.save(update_fields=['couverture_file_key'])
        return Response(self.get_serializer(article).data)

    @action(detail=True, methods=['get'], url_path='couverture-image')
    def couverture_image(self, request, pk=None):
        """ZGED10 — Relaie même-origine l'image de couverture (proxy, comme
        les avatars) : le navigateur ne peut pas joindre l'hôte interne
        MinIO."""
        article = self.get_object()
        if not article.couverture_file_key:
            return Response({'detail': 'Aucune couverture.'}, status=404)
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(article.couverture_file_key)
        if err or data is None:
            return Response({'detail': 'Couverture indisponible.'}, status=404)
        return HttpResponse(data, content_type='image/*')


class KbArticleVersionViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Historique des versions d'article (lecture seule). Filtrable par
    ``?article=<id>``. Société scopée côté serveur."""
    queryset = KbArticleVersion.objects.select_related(
        'article', 'auteur').all()
    serializer_class = KbArticleVersionSerializer
    permission_classes = [HasPermissionOrLegacy('kb_voir')]
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


class PartageArticleKbViewSet(_KbBaseViewSet):
    """XKB19 — Gestion des partages publics d'article (lien tokenisé, opt-in).

    ``company``/``created_by`` posés côté serveur ; l'``article`` reçu est
    validé même-société par le sérialiseur. Filtre optionnel ``?article=<id>``.
    """
    queryset = PartageArticleKb.objects.select_related('article').all()
    serializer_class = PartageArticleKbSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        article = self.request.query_params.get('article')
        if article:
            qs = qs.filter(article_id=article)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='depublier')
    def depublier(self, request, pk=None):
        """XKB19 — Dépublication IMMÉDIATE (kill-switch) : le lien répond
        404 dès cet appel (indistinct d'un jeton inconnu)."""
        partage = self.get_object()
        partage.actif = False
        partage.save(update_fields=['actif'])
        return Response(self.get_serializer(partage).data)


class KbParcoursViewSet(_KbBaseViewSet):
    """XKB22 — Parcours de lecture d'intégration (séquences ordonnées
    d'articles). ``company``/``created_by`` posés côté serveur."""
    queryset = KbParcours.objects.all()
    serializer_class = KbParcoursSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'nom', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='articles')
    def articles(self, request, pk=None):
        """XKB22 — Articles ordonnés de ce parcours."""
        parcours = self.get_object()
        membres = selectors.articles_ordonnes_parcours(parcours)
        return Response(KbParcoursArticleSerializer(membres, many=True).data)


class KbParcoursArticleViewSet(_KbBaseViewSet):
    """XKB22 — Articles ordonnés d'un parcours (CRUD). ``company`` posée côté
    serveur ; ``parcours``/``article`` validés même-société par le
    sérialiseur. Filtre optionnel ``?parcours=<id>``."""
    queryset = KbParcoursArticle.objects.select_related(
        'parcours', 'article').all()
    serializer_class = KbParcoursArticleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        parcours = self.request.query_params.get('parcours')
        if parcours:
            qs = qs.filter(parcours_id=parcours)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class KbParcoursAssignationViewSet(_KbBaseViewSet):
    """XKB22 — Assignations de parcours (article par article, par personne).

    ``company`` posée côté serveur ; ``parcours``/``utilisateur`` validés
    même-société par le sérialiseur. Filtres optionnels ``?parcours=<id>``
    et ``?utilisateur=<id>``."""
    queryset = KbParcoursAssignation.objects.select_related(
        'parcours', 'utilisateur').all()
    serializer_class = KbParcoursAssignationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        parcours = params.get('parcours')
        if parcours:
            qs = qs.filter(parcours_id=parcours)
        utilisateur = params.get('utilisateur')
        if utilisateur:
            qs = qs.filter(utilisateur_id=utilisateur)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'], url_path='progression')
    def progression(self, request, pk=None):
        """XKB22 — Progression article par article + complétion de cette
        assignation (déduite des ``KbLecture`` déjà existantes)."""
        assignation = self.get_object()
        return Response(selectors.progression_parcours(assignation))


# ── XKB19 — Endpoint PUBLIC (sans login) servant un article par jeton ───────
# AUTHENTIFIÉ UNIQUEMENT PAR LE JETON : aucune identité/société n'est lue de la
# requête (même motif que ``ged.views.public_partage`` — GED20). Révoqué/
# inconnu → 404 ; expiré → 410. Aucune autre donnée n'est atteignable.

class PublicPartageArticleRateThrottle(SimpleRateThrottle):
    """Limite le débit de l'accès public par IP + jeton (même motif que
    ``ged.views.PublicPartageRateThrottle``)."""
    scope = 'public_kb_partage'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (getattr(view, 'kwargs', None) or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _kb_noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicPartageArticleRateThrottle])
def public_article(request, token):
    """XKB19 — Sert un article partagé par jeton (PUBLIC, sans login).

    `GET /api/django/kb/public/<token>/`. Le jeton est l'UNIQUE secret
    d'accès ; aucune identité/société n'est lue de la requête — tout est
    résolu DEPUIS le jeton (``services.resolve_partage_public``).

    Codes :
      - 404 : jeton inconnu OU partage dépublié (indistinct, pas de fuite).
      - 410 : partage expiré.
      - 200 : titre + corps de l'article (lecture seule), et le compteur
        ``consultations`` est incrémenté atomiquement.
    """
    statut, partage = services.resolve_partage_public(token)
    if statut == services.PARTAGE_INTROUVABLE:
        return _kb_noindex(Response(
            {'detail': "Ce lien est introuvable ou n'est plus disponible."},
            status=404))
    if statut == services.PARTAGE_EXPIRE:
        return _kb_noindex(Response(
            {'detail': "Ce lien a expiré."}, status=410))

    services.consume_partage_consultation(partage)
    article = partage.article
    return _kb_noindex(Response({
        'titre': article.titre,
        'corps': article.corps,
        'corps_format': article.corps_format,
        'categorie': article.categorie,
    }))


class BlocReutilisableViewSet(_KbBaseViewSet):
    """ZGED12 — Blocs de texte réutilisables (« presse-papiers Knowledge »).

    Chaque utilisateur voit ses blocs PERSONNELS + tous les blocs SOCIÉTÉ
    (``selectors.blocs_visibles``) ; ``company``/``created_by`` posés côté
    serveur. Suppression réservée au CRÉATEUR ou à un admin — un autre
    utilisateur responsable ne peut pas supprimer le bloc personnel d'un
    tiers."""
    queryset = BlocReutilisable.objects.all()
    serializer_class = BlocReutilisableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'nom', 'date_creation']

    def get_queryset(self):
        super().get_queryset()
        return selectors.blocs_visibles(
            self.request.user.company, self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_destroy(self, instance):
        tier = getattr(self.request.user, 'menu_tier', None)
        if tier != 'admin' and instance.created_by_id != self.request.user.id:
            raise PermissionDenied(
                "Seul le créateur ou un administrateur peut supprimer ce bloc.")
        instance.delete()
