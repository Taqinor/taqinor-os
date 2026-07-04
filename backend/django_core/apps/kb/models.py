"""Modèles de la Base de connaissances interne (module `apps.kb`).

Référentiel d'articles internes (procédures, fiches techniques, FAQ) destinés
aux équipes. Multi-société : chaque modèle porte un FK ``company`` posé côté
serveur (jamais lu du corps de requête). Entièrement additif.
"""
from django.conf import settings
from django.db import models
from pgvector.django import VectorField

# KB6 — dimension du vecteur d'embedding RAG/DocQA. Alignée 1:1 sur
# ``apps.ged.models.EMBEDDING_DIM`` (1024) : les fragments d'articles partagent
# le MÊME magasin pgvector et le MÊME provider d'embedding que la GED (FG352) —
# pas un second magasin vectoriel. ``pgvector`` est déjà une dépendance dure du
# projet (utilisée par la GED) : ce modèle n'introduit AUCUNE nouvelle dépendance.
EMBEDDING_DIM = 1024


class KbArticle(models.Model):
    """Article de la base de connaissances interne d'une société."""
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PUBLIE = 'publie', 'Publié'
        OBSOLETE = 'obsolete', 'Obsolète'

    class Visibilite(models.TextChoices):
        """XKB9 — section de l'article. RÉTRO-COMPATIBLE : ``workspace`` est
        la valeur par défaut, comportement historique inchangé (visible de
        tous les paliers autorisés, sous réserve des ACL KB7)."""
        WORKSPACE = 'workspace', 'Espace de travail'
        PRIVE = 'prive', 'Privé'
        PARTAGE = 'partage', 'Partagé'

    class CorpsFormat(models.TextChoices):
        """XKB10 — format de rendu du champ ``corps``. RÉTRO-COMPATIBLE :
        ``texte`` (défaut) reproduit le rendu brut historique ; ``markdown``
        active le rendu Markdown sanitizé côté frontend (aucune conséquence
        backend au-delà du champ — le rendu/sanitizing vit côté client)."""
        TEXTE = 'texte', 'Texte brut'
        MARKDOWN = 'markdown', 'Markdown'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_articles',
        verbose_name='Société',
    )
    titre = models.CharField(max_length=255, verbose_name='Titre')
    corps = models.TextField(blank=True, default='', verbose_name='Contenu')
    categorie = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Catégorie')
    tags = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Tags')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # XKB9 — section. Défaut ``workspace`` = comportement historique inchangé.
    visibilite = models.CharField(
        max_length=10, choices=Visibilite.choices,
        default=Visibilite.WORKSPACE, verbose_name='Visibilité')
    # XKB10 — format du corps. Défaut ``texte`` = comportement historique
    # inchangé (aucun rendu Markdown des articles existants).
    corps_format = models.CharField(
        max_length=10, choices=CorpsFormat.choices,
        default=CorpsFormat.TEXTE, verbose_name='Format du contenu')
    # XKB12 — gabarit réutilisable (« enregistrer comme gabarit ») : apparaît
    # dans la galerie « nouveau depuis gabarit ». Couvre AUSSI les 5 gabarits
    # SOP/ONEE/82-21 seedés (KB5, ``seed_kb_templates`` — additif, aucune
    # migration de données requise : le flag est simplement False par défaut
    # sur les lignes existantes, qui restent des articles normaux tant qu'on
    # ne les marque pas gabarit explicitement).
    est_gabarit = models.BooleanField(
        default=False, verbose_name='Gabarit')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kb_app_articles',
        verbose_name='Auteur',
    )
    # XKB8 — arborescence de pages imbriquées : sous-article d'un article
    # parent (profondeur arbitraire). Validé même-société + anti-cycle côté
    # serializer/service (jamais en base). NULL = article racine.
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='enfants',
        verbose_name='Article parent',
    )
    # XKB8 — position parmi les frères (même parent) pour le réordonnancement
    # manuel dans l'arbre latéral. Posé côté serveur, jamais recalculé par
    # count() (juste un entier libre, pas une contrainte d'unicité).
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    # XKB14 — vérification & péremption. ``verifie_par`` + ``verifie_jusqua``
    # (posés par l'action ``verifier``) portent le badge « Vérifié » et
    # l'échéance de re-revue (7/30/90 j ou date libre — calculée côté client,
    # stockée en date absolue côté serveur pour un sweep simple).
    verifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kb_app_articles_verifies',
        verbose_name='Vérifié par',
    )
    verifie_jusqua = models.DateTimeField(
        null=True, blank=True, verbose_name="Vérifié jusqu'au")
    # XKB14 — verrou d'article (SOP approuvées, lecture seule). Seule une
    # personne avec ACL ÉDITION (ou admin) peut déverrouiller ; l'API rejette
    # tout PATCH sur un article verrouillé pour les autres.
    est_verrouille = models.BooleanField(
        default=False, verbose_name='Verrouillé')
    # XKB16 — compteur de VUES par article, DISTINCT de KbLecture (KB7) :
    # incrémenté à CHAQUE consultation (même relecture par la même personne),
    # alors que KbLecture est un « lu/pas lu » idempotent par utilisateur.
    # Posé côté serveur (jamais du corps de requête) via l'action de détail.
    vues = models.PositiveIntegerField(default=0, verbose_name='Vues')
    # XKB18 — langue de CET article. Défaut ``fr`` = comportement historique
    # inchangé (tout article existant reste un article français ordinaire).
    LANGUE_CHOICES = [('fr', 'Français'), ('ar', 'العربية'), ('en', 'English')]
    langue = models.CharField(
        max_length=5, choices=LANGUE_CHOICES,
        default='fr', verbose_name='Langue')
    # XKB18 — groupe de traduction : pointe vers l'article SOURCE dont celui-ci
    # est la traduction (self-FK, NULL = article racine/source, pas encore
    # traduit). Toutes les traductions d'un même contenu partagent la MÊME
    # source (jamais une chaîne de traductions de traductions) — validé côté
    # serializer. RÉTRO-COMPATIBLE : NULL par défaut, aucun article existant
    # n'est affecté.
    traduction_de = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='traductions',
        verbose_name='Traduction de',
    )
    # XKB18 — la traduction est-elle PÉRIMÉE (la source a été modifiée depuis)?
    # Posé côté serveur : à chaque modification de l'article SOURCE, toutes ses
    # traductions sont marquées périmées (services.marquer_traductions_perimees).
    # Une traduction elle-même modifiée redevient à jour (remis à False).
    traduction_perimee = models.BooleanField(
        default=False, verbose_name='Traduction à mettre à jour')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'parent', 'ordre'],
                name='kb_article_parent_ordre_idx'),
            # XKB18 — nom EXPLICITE (≤30 car.) pour éviter toute divergence
            # avec le nom haché déterministe de Django.
            models.Index(
                fields=['company', 'traduction_de'],
                name='kb_article_traduction_idx'),
        ]

    def __str__(self):
        return self.titre


class KbArticleVersion(models.Model):
    """Instantané versionné du contenu d'un :class:`KbArticle`.

    À chaque mise à jour de l'article (ou via l'action explicite ``publier`` /
    ``nouvelle-version``) on fige titre + contenu dans une nouvelle ligne. Le
    numéro (``version``) est incrémental PAR article, calculé côté serveur
    (max(version)+1 — JAMAIS count()+1, sujet aux collisions). La société est
    posée côté serveur et toujours cohérente avec celle de l'article.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_article_versions',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Article',
    )
    version = models.PositiveIntegerField(
        default=1, verbose_name='Numéro de version')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    contenu = models.TextField(blank=True, default='', verbose_name='Contenu')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kb_app_article_versions',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Version d’article'
        verbose_name_plural = 'Versions d’article'
        ordering = ['-version', '-id']
        unique_together = [('article', 'version')]
        indexes = [
            models.Index(fields=['company', 'article']),
            models.Index(fields=['article', 'version']),
        ]

    def __str__(self):
        return f'{self.titre} v{self.version}'


class KbArticleLien(models.Model):
    """Lien LÂCHE d'un article vers un objet métier d'une AUTRE app.

    Permet de rattacher un article de la base de connaissances à un produit
    (``stock``), un équipement (``sav``) ou un type d'intervention SANS aucun
    FK dur : la cible est désignée par un couple typé ``(type_cible, cible_id)``
    — jamais un import du modèle d'une autre app. Les écrans SAV / chantier
    peuvent ainsi remonter les articles contextuels (« quels articles sont liés
    au produit X »). Le ``libelle`` met en cache un libellé d'affichage ; les
    sélecteurs (``selectors.py``) l'enrichissent au vol quand l'app cible expose
    un sélecteur de lecture, et dégradent proprement (libellé stocké seul) sinon.
    """
    class TypeCible(models.TextChoices):
        PRODUIT = 'produit', 'Produit'
        EQUIPEMENT = 'equipement', 'Équipement'
        TYPE_INTERVENTION = 'type_intervention', "Type d'intervention"
        # XKB11 — lien interne ARTICLE → ARTICLE (cible = autre KbArticle,
        # même société, validée côté serializer). ``cible_id`` porte alors le
        # PK d'un autre KbArticle plutôt qu'un objet d'une autre app.
        ARTICLE = 'article', 'Article'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_article_liens',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='liens',
        verbose_name='Article',
    )
    type_cible = models.CharField(
        max_length=20, choices=TypeCible.choices, verbose_name='Type de cible')
    # PK de l'objet cible dans son app (référence lâche, aucun FK dur).
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    # Libellé d'affichage mis en cache (fallback quand l'app cible n'a pas de
    # sélecteur d'enrichissement).
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Lien de l'article"
        verbose_name_plural = "Liens de l'article"
        ordering = ['id']
        unique_together = [('article', 'type_cible', 'cible_id')]
        indexes = [
            models.Index(fields=['company', 'type_cible', 'cible_id']),
        ]

    def __str__(self):
        return f'{self.article_id} → {self.type_cible} #{self.cible_id}'


class KbArticleAcl(models.Model):
    """Droit d'accès d'un RÔLE sur un :class:`KbArticle` (KB7).

    Restreint la visibilité d'un article par palier de rôle. Le ``role`` stocké
    est le palier de menu CANONIQUE faisant autorité du projet
    (``CustomUser.menu_tier`` : ``admin`` / ``responsable`` / ``normal``) — la
    seule source de vérité de rôle, jamais une chaîne en dur ailleurs. Le
    ``niveau`` distingue un droit de LECTURE d'un droit d'ÉDITION.

    RÉTRO-COMPATIBLE — clé de la feature : un article SANS aucune ligne ACL
    reste visible de TOUS (comportement historique inchangé). Dès qu'au moins
    une ligne ACL existe pour un article, seuls les paliers listés (plus le
    palier ``admin``, toujours autorisé) peuvent le lire. La société est posée
    côté serveur (jamais du corps de requête) et reste cohérente avec celle de
    l'article.
    """
    class Niveau(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        EDITION = 'edition', 'Édition'

    # Paliers canoniques : repris 1:1 de ``CustomUser.ROLE_CHOICES`` (accesseur
    # de rôle faisant autorité ``menu_tier``). Définis localement comme simples
    # constantes de chaîne pour ne pas créer de dépendance dure au moment de
    # l'import du modèle ; les valeurs sont validées par ``ROLE_CHOICES``.
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('responsable', 'Responsable'),
        ('normal', 'Utilisateur'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_acls',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='acls',
        verbose_name='Article',
    )
    # ``role`` XOR ``utilisateur`` (validé côté serializer) : une ligne ACL
    # par-RÔLE (comportement historique KB7, ``role`` seul) OU par-UTILISATEUR
    # (XKB9 — partage nominatif d'un article ``partage``, ``utilisateur``
    # seul). ``role`` reste blank pour les lignes par-utilisateur.
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, blank=True, default='',
        verbose_name='Palier de rôle autorisé')
    # XKB9 — ACL nominative : membre explicite d'un article ``partage``.
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='kb_app_acls',
        verbose_name='Utilisateur autorisé',
    )
    niveau = models.CharField(
        max_length=10, choices=Niveau.choices,
        default=Niveau.LECTURE, verbose_name='Niveau')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Droit d'accès de l'article"
        verbose_name_plural = "Droits d'accès de l'article"
        ordering = ['id']
        constraints = [
            # Unicité CONDITIONNELLE : une ligne par-RÔLE est unique sur
            # (article, role, niveau) UNIQUEMENT quand ``role`` est renseigné —
            # sinon deux ACL par-utilisateur (role='') sur le même article/niveau
            # entreraient en collision sur (article, '', niveau). Idem pour les
            # lignes par-UTILISATEUR (unicité seulement quand ``utilisateur`` est
            # posé), pour ne pas contraindre les lignes par-rôle (utilisateur NULL).
            models.UniqueConstraint(
                fields=['article', 'role', 'niveau'],
                condition=~models.Q(role=''),
                name='kb_acl_role_niveau_uniq'),
            models.UniqueConstraint(
                fields=['article', 'utilisateur', 'niveau'],
                condition=models.Q(utilisateur__isnull=False),
                name='kb_acl_user_niveau_uniq'),
        ]
        indexes = [
            # Nom EXPLICITE (≤30 car.) pour éviter toute divergence entre le
            # nom haché déterministe de Django et celui de la migration.
            models.Index(
                fields=['company', 'article'], name='kb_acl_company_article_idx'),
        ]

    def __str__(self):
        cible = self.role or f'user:{self.utilisateur_id}'
        return f'{self.article_id} · {cible} ({self.niveau})'


class KbLecture(models.Model):
    """Suivi de LECTURE d'un :class:`KbArticle` par un utilisateur (KB7).

    Une ligne par (article, utilisateur) : enregistre QUI a lu QUOI et QUAND
    (``lu_le``). Écrite par l'action ``marquer-lu`` du viewset des articles —
    l'utilisateur agissant et la société sont posés côté serveur (jamais du
    corps de requête). Idempotente : remarquer-lu un article déjà lu rafraîchit
    ``lu_le`` au lieu de créer une seconde ligne (``get_or_create`` côté
    service). Alimente le résumé de lecture par article
    (nombre de lecteurs + qui).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_lectures',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='lectures',
        verbose_name='Article',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='kb_app_lectures',
        verbose_name='Lecteur',
    )
    lu_le = models.DateTimeField(
        auto_now=True, verbose_name='Lu le')

    class Meta:
        verbose_name = "Lecture d'article"
        verbose_name_plural = "Lectures d'article"
        ordering = ['-lu_le', '-id']
        unique_together = [('article', 'utilisateur')]
        indexes = [
            # Nom EXPLICITE (≤30 car.) — voir KbArticleAcl.Meta.
            models.Index(
                fields=['company', 'article'], name='kb_lecture_company_art_idx'),
        ]

    def __str__(self):
        return f'{self.utilisateur_id} a lu {self.article_id}'


class KbArticleChunk(models.Model):
    """KB6 — Fragment indexé d'un :class:`KbArticle` pour le RAG / DocQA (FG352).

    Rend les articles de la base de connaissances exploitables par le pipeline
    RAG/DocQA déjà construit dans ``apps.ged`` (FG352) : le texte de l'article
    (titre + corps) est découpé en fragments (« chunks ») chevauchants et un
    embedding par fragment est stocké ici, dans le MÊME type pgvector et avec le
    MÊME provider d'embedding que ``ged.DocumentChunk`` — on ne dresse PAS un
    second magasin vectoriel et on réutilise ``ged.services`` (chunk_text /
    compute_embedding / embedding_enabled) plutôt que de réimplémenter.

    KEY-GATED no-op (comme la GED) : sans clé d'embedding
    (``ged.services.embedding_enabled()``), AUCUN fragment n'est embeddé ni
    écrit (l'indexation est un no-op qui renvoie 0) — aucun appel réseau, aucun
    coût, aucune nouvelle dépendance dure.

    Multi-société : la company est posée côté serveur (celle de l'article),
    jamais lue d'un corps de requête. ``chunk_index`` ordonne les fragments d'un
    même article.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='kb_app_article_chunks',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='Article',
    )
    # Position du fragment dans l'article (0, 1, 2…) — posée côté serveur.
    chunk_index = models.PositiveIntegerField(
        default=0, verbose_name='Position du fragment')
    # Texte brut du fragment (sert à renvoyer le passage récupéré à l'agent).
    texte = models.TextField(blank=True, default='', verbose_name='Texte')
    # Embedding du fragment (dimension EMBEDDING_DIM, alignée sur la GED). NULL
    # tant que la clé d'embedding est absente (no-op). Même type pgvector que
    # ``ged.DocumentChunk`` — pas un second magasin vectoriel.
    embedding = VectorField(
        dimensions=EMBEDDING_DIM, null=True, blank=True,
        verbose_name='Embedding')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Fragment d'article"
        verbose_name_plural = "Fragments d'article"
        ordering = ['article', 'chunk_index', 'id']
        unique_together = [('article', 'chunk_index')]
        indexes = [
            # Nom EXPLICITE (≤30 car.) pour éviter toute divergence entre le
            # nom haché déterministe de Django et celui de la migration.
            models.Index(
                fields=['company', 'article'], name='kb_chunk_co_article_idx'),
        ]

    def __str__(self):
        return f'{self.article_id} #{self.chunk_index}'


class KbLectureObligatoire(models.Model):
    """XKB7 — Assignation de lecture OBLIGATOIRE d'un article publié.

    Assigne un article à un utilisateur donné OU à un palier de rôle entier
    (``menu_tier`` : admin/responsable/normal — exactement les mêmes paliers
    canoniques que :class:`KbArticleAcl`). La complétion s'appuie sur le
    ``KbLecture``/``marquer-lu`` DÉJÀ existant (KB7) — on ne réimplémente pas
    le suivi de lecture, on l'annote d'une échéance + d'un statut
    obligatoire/volontaire. La société est posée côté serveur (jamais du corps
    de requête) et reste cohérente avec celle de l'article.

    Exactement un de ``utilisateur``/``role_cible`` est renseigné (validé côté
    serializer) : une ligne par utilisateur explicite, ou une ligne par palier
    de rôle couvrant tous les utilisateurs de ce palier.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_lectures_obligatoires',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='lectures_obligatoires',
        verbose_name='Article',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='kb_app_lectures_obligatoires',
        verbose_name='Utilisateur assigné',
    )
    # Palier de rôle canonique (mêmes choix que KbArticleAcl.ROLE_CHOICES) :
    # assigne TOUS les utilisateurs de ce palier, sans énumérer chaque ligne.
    role_cible = models.CharField(
        max_length=20, choices=KbArticleAcl.ROLE_CHOICES,
        blank=True, default='', verbose_name='Palier de rôle ciblé')
    echeance = models.DateTimeField(
        null=True, blank=True, verbose_name='Échéance')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Assigné le')

    class Meta:
        verbose_name = 'Lecture obligatoire'
        verbose_name_plural = 'Lectures obligatoires'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'article'], name='kb_lecobl_co_article_idx'),
        ]

    def __str__(self):
        cible = self.utilisateur_id or f'rôle:{self.role_cible}'
        return f'{self.article_id} → {cible}'


class KbFavori(models.Model):
    """XKB15 — Article ÉTOILÉ par un utilisateur (favori personnel).

    Une ligne par (article, utilisateur) — togglable (créer/supprimer). La
    société et l'utilisateur agissant sont posés côté serveur (jamais du
    corps de requête). Les favoris d'un utilisateur ne sont jamais visibles
    d'un autre (strictement personnel, contrairement au reste de la base qui
    est partagée à l'échelle de la société).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_favoris',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='favoris',
        verbose_name='Article',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='kb_app_favoris',
        verbose_name='Utilisateur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Ajouté le')

    class Meta:
        verbose_name = 'Favori'
        verbose_name_plural = 'Favoris'
        ordering = ['-date_creation', '-id']
        unique_together = [('article', 'utilisateur')]
        indexes = [
            models.Index(
                fields=['company', 'utilisateur'], name='kb_favori_co_user_idx'),
        ]

    def __str__(self):
        return f'{self.utilisateur_id} ★ {self.article_id}'


class KbRechercheVide(models.Model):
    """XKB16 — Journal des recherches KB SANS RÉSULTAT (terme, qui, quand).

    Alimente le rapport « lacunes de connaissance » : les termes cherchés
    jamais servis, pour prioriser la rédaction. Écrit par l'action de liste
    des articles quand une recherche ``?search=`` ne renvoie aucun résultat.
    Société et utilisateur posés côté serveur (jamais du corps de requête).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_recherches_vides',
        verbose_name='Société',
    )
    terme = models.CharField(max_length=255, verbose_name='Terme recherché')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kb_app_recherches_vides',
        verbose_name='Utilisateur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Recherché le')

    class Meta:
        verbose_name = 'Recherche sans résultat'
        verbose_name_plural = 'Recherches sans résultat'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'terme'], name='kb_rech_vide_co_terme_idx'),
        ]

    def __str__(self):
        return f'« {self.terme} » (0 résultat)'
