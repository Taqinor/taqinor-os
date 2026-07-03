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
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES,
        verbose_name='Palier de rôle autorisé')
    niveau = models.CharField(
        max_length=10, choices=Niveau.choices,
        default=Niveau.LECTURE, verbose_name='Niveau')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Droit d'accès de l'article"
        verbose_name_plural = "Droits d'accès de l'article"
        ordering = ['id']
        unique_together = [('article', 'role', 'niveau')]
        indexes = [
            # Nom EXPLICITE (≤30 car.) pour éviter toute divergence entre le
            # nom haché déterministe de Django et celui de la migration.
            models.Index(
                fields=['company', 'article'], name='kb_acl_company_article_idx'),
        ]

    def __str__(self):
        return f'{self.article_id} · {self.role} ({self.niveau})'


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
