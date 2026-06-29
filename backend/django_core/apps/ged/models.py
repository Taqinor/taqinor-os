"""Module GED — gestion documentaire (DMS) multi-tenant.

Transforme les fichiers épars de `records.Attachment` en un référentiel gouverné :
une arborescence (Cabinet → Folder), des documents versionnés et stockés dans
MinIO via les conventions de `records.storage` (clé `file_key`), avec un
checksum pour la déduplication.

Tout est company-stampé côté serveur et filtré par société, comme le reste de
l'ERP. Le fichier binaire lui-même ne quitte jamais le stockage objet — seul le
`file_key` (et ses métadonnées) vit en base.

GED2 — Cabinet + Folder arborescent avec un CHEMIN MATÉRIALISÉ (`path`, ex.
"/1/4/9/") : chaque dossier porte le chemin de ses ancêtres, ce qui rend les
requêtes de sous-arbre (descendants) triviales sans récursion SQL.

GED3 — Document + DocumentVersion : un document vit dans un dossier et porte N
versions ordonnées (numéro, file_key MinIO, checksum, uploadé par, date).

GED6 — DocumentLien : liaison polymorphe entre un Document et N'IMPORTE quel
objet métier autorisé (lead, client, devis, bon de commande, facture, chantier,
ticket SAV, outillage). On RÉUTILISE le registre `records.ALLOWED_TARGETS` et le
mécanisme ContentType déjà en place pour Activity/Attachment/Comment/TaggedItem
— on n'invente pas un nouveau schéma de FK générique. Company posée côté serveur.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import VectorField

# GED12 — dimension du vecteur d'embedding documentaire (clé-gated). Aligné sur
# les embeddings Zhipu/OpenAI-compatibles (1024). Fixe : changer la dimension
# exigerait une migration destructive (jamais fait à la volée).
EMBEDDING_DIM = 1024

# GED17 — Cycle de vie documentaire (statuts LOCAUX à la GED).
#
# Ce cycle de vie est un attribut PROPRE au document (« où en est ce document
# dans son processus de validation interne »). Il est DISTINCT et SÉPARÉ du
# funnel de pipeline commercial de `STAGES.py` (rule #2) : les deux couches ne
# se croisent jamais et on n'importe surtout PAS `STAGES.py` ici.
#
# Machine à états (transitions autorisées seulement) :
#
#   brouillon ─▶ revue
#   revue     ─▶ approuve | brouillon (renvoyé pour correction)
#   approuve  ─▶ archive  | obsolete
#   archive   ─▶ obsolete | approuve (réactivation)
#   obsolete  ─▶ brouillon (remise en chantier d'une nouvelle itération)
#
# Toute autre transition est refusée par `services.change_lifecycle_status`.
LIFECYCLE_BROUILLON = 'brouillon'
LIFECYCLE_REVUE = 'revue'
LIFECYCLE_APPROUVE = 'approuve'
LIFECYCLE_ARCHIVE = 'archive'
LIFECYCLE_OBSOLETE = 'obsolete'

LIFECYCLE_CHOICES = [
    (LIFECYCLE_BROUILLON, 'Brouillon'),
    (LIFECYCLE_REVUE, 'En revue'),
    (LIFECYCLE_APPROUVE, 'Approuvé'),
    (LIFECYCLE_ARCHIVE, 'Archivé'),
    (LIFECYCLE_OBSOLETE, 'Obsolète'),
]

# Transitions autorisées : statut courant -> ensemble des statuts atteignables.
LIFECYCLE_TRANSITIONS = {
    LIFECYCLE_BROUILLON: {LIFECYCLE_REVUE},
    LIFECYCLE_REVUE: {LIFECYCLE_APPROUVE, LIFECYCLE_BROUILLON},
    LIFECYCLE_APPROUVE: {LIFECYCLE_ARCHIVE, LIFECYCLE_OBSOLETE},
    LIFECYCLE_ARCHIVE: {LIFECYCLE_OBSOLETE, LIFECYCLE_APPROUVE},
    LIFECYCLE_OBSOLETE: {LIFECYCLE_BROUILLON},
}

# GED18 — Workflow d'approbation / revue documentaire (statuts LOCAUX à la GED).
#
# Couche EXPLICITE de validation par-dessus le cycle de vie GED17 : une demande
# d'approbation enregistre QUI doit relire/valider un document et SA décision.
# Elle PILOTE (sans dupliquer) la machine à états du cycle de vie — à
# l'approbation, le service réutilise `change_lifecycle_status` pour faire
# avancer le document « revue → approuvé ». Ces statuts de demande sont LOCAUX
# à la GED et n'ont aucun rapport avec le funnel commercial `STAGES.py`
# (rule #2) — on n'importe surtout PAS `STAGES.py` ici.
APPROBATION_EN_ATTENTE = 'en_attente'
APPROBATION_APPROUVE = 'approuve'
APPROBATION_REJETE = 'rejete'

APPROBATION_CHOICES = [
    (APPROBATION_EN_ATTENTE, 'En attente'),
    (APPROBATION_APPROUVE, 'Approuvée'),
    (APPROBATION_REJETE, 'Rejetée'),
]


class Cabinet(models.Model):
    """Espace documentaire racine (« armoire ») d'une société.

    Une société peut avoir plusieurs cabinets (ex. « Administratif »,
    « Technique », « RH ») ; chacun est la racine d'une arborescence de
    dossiers. Company posée côté serveur — jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_cabinets')
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        unique_together = [('company', 'nom')]
        verbose_name = 'Cabinet'
        verbose_name_plural = 'Cabinets'
        indexes = [
            models.Index(fields=['company', 'nom']),
        ]

    def __str__(self):
        return self.nom


class Folder(models.Model):
    """Dossier arborescent (GED2) — CHEMIN MATÉRIALISÉ.

    Un dossier appartient à un cabinet et peut avoir un dossier parent
    (self-FK). Le champ `path` est un chemin matérialisé de la forme
    "/<id_ancetre1>/<id_ancetre2>/…/<id_self>/" (les pk des ancêtres + soi),
    recalculé à chaque save : il rend une requête de sous-arbre triviale
    (`Folder.objects.filter(path__startswith=parent.path)`), sans récursion.

    Company posée côté serveur ; toujours cohérente avec celle du cabinet.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_folders')
    cabinet = models.ForeignKey(
        Cabinet, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='children')
    nom = models.CharField(max_length=200)
    # Chemin matérialisé : "/1/4/9/" — les pk des ancêtres puis soi, encadrés
    # de '/'. Renseigné/recalculé dans save() ; jamais lu du corps de requête.
    path = models.CharField(max_length=1000, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Dossier'
        verbose_name_plural = 'Dossiers'
        indexes = [
            models.Index(fields=['company', 'cabinet']),
            models.Index(fields=['parent']),
            models.Index(fields=['path']),
        ]

    def __str__(self):
        return self.nom

    def compute_path(self):
        """Construit le chemin matérialisé "/…/<self.pk>/" à partir du parent.

        Le parent porte déjà son propre chemin (matérialisé), donc on se
        contente d'y ajouter notre pk — pas de remontée récursive en base.
        Suppose un `self.pk` déjà attribué (on save APRÈS le premier insert)."""
        base = self.parent.path if (self.parent and self.parent.path) else '/'
        if not base.endswith('/'):
            base += '/'
        return f'{base}{self.pk}/'

    def save(self, *args, **kwargs):
        """Persiste, puis garantit un `path` matérialisé cohérent.

        Au premier insert le pk n'existe pas encore : on enregistre d'abord,
        puis on calcule le chemin et on met à jour le seul champ `path` si
        nécessaire (idempotent — pas de boucle de save)."""
        super().save(*args, **kwargs)
        expected = self.compute_path()
        if self.path != expected:
            self.path = expected
            super().save(update_fields=['path'])

    def descendants(self):
        """QuerySet des dossiers strictement sous celui-ci (sous-arbre).

        Trivial grâce au chemin matérialisé : tout descendant a un `path` qui
        COMMENCE par le nôtre (et n'est pas nous-même)."""
        return Folder.objects.filter(
            company=self.company, path__startswith=self.path
        ).exclude(pk=self.pk)


class Coffre(models.Model):
    """GED8 — Coffre-fort par employé/client (ACL propriétaire + admin).

    Un coffre-fort est un espace documentaire confidentiel rattaché à UN
    propriétaire : soit un employé (`proprietaire`, un User de la société), soit
    un client (`client_id`, référence string-FK vers `crm.Client` — jamais un
    import direct du modèle). Les documents placés dans un coffre (via
    `Document.coffre`) ne sont visibles QUE de leur propriétaire et des
    administrateurs de la société : le filtrage ACL est appliqué côté serveur
    dans les `selectors`/viewsets (jamais lu du corps de requête).

    Company posée côté serveur. Le coffre porte exactement un type de
    propriétaire : un employé OU un client (jamais les deux, jamais aucun).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_coffres')
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    # Propriétaire employé (User de la société) — exclusif avec `client_id`.
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_coffres')
    # Propriétaire client — référence string-FK vers crm.Client (cross-app via
    # selectors, jamais un import du modèle). Exclusif avec `proprietaire`.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_coffres')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_coffres_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Coffre-fort'
        verbose_name_plural = 'Coffres-forts'
        indexes = [
            models.Index(fields=['company', 'proprietaire']),
            models.Index(fields=['company', 'client']),
        ]

    def __str__(self):
        return self.nom

    def is_accessible_by(self, user):
        """ACL — True si `user` peut accéder à ce coffre (propriétaire OU admin).

        Un employé voit son propre coffre (`proprietaire`). Un coffre client
        n'a pas d'utilisateur propriétaire : seuls les admins de la société y
        accèdent. Les administrateurs voient tous les coffres de leur société.
        """
        if user is None or not user.is_authenticated:
            return False
        if user.company_id != self.company_id:
            return False
        if getattr(user, 'is_admin_role', False) or user.is_superuser:
            return True
        return self.proprietaire_id == user.id


class Document(models.Model):
    """Document logique vivant dans un dossier (GED3).

    Le document est le conteneur stable (nom, dossier, société) ; son contenu
    binaire vit dans une ou plusieurs `DocumentVersion`. La version courante
    est simplement la plus récente (numéro le plus élevé). Company posée côté
    serveur — toujours cohérente avec celle du dossier.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_documents')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, related_name='documents')
    # GED8 — un document peut vivre dans un coffre-fort (ACL propriétaire+admin).
    # Quand `coffre` est non nul, seuls le propriétaire du coffre et les admins
    # voient/manipulent ce document (filtrage en `selectors`/viewset).
    coffre = models.ForeignKey(
        'Coffre', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documents')
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    # GED10 — métadonnées typées configurables (réutilise `customfields`).
    # Un admin définit des `CustomFieldDef` sur le module « document » ; les
    # valeurs vivent ici, indexées par `code` (approche additive JSONField —
    # ajouter/retirer une définition ne touche jamais le schéma). Validé contre
    # les définitions actives via `customfields.serializers.validate_custom_data`.
    custom_data = models.JSONField(null=True, blank=True, default=dict)
    # GED11 — recherche plein-texte Postgres. `search_vector` est un tsvector
    # maintenu côté serveur (via `services.update_search_vector`) à partir du
    # nom, de la description, des tags et — quand GED12 l'alimente — du texte
    # OCR. Un index GIN dessus rend la recherche `@@` rapide. Le `texte_ocr`
    # est le texte extrait (vide par défaut ; rempli par l'indexation GED12).
    texte_ocr = models.TextField(blank=True, default='')
    search_vector = SearchVectorField(null=True, blank=True)
    # GED12 — index OCR + recherche sémantique (pgvector, KEY-GATED no-op).
    # `embedding` est le vecteur d'embedding du texte OCR/nom du document
    # (dimension EMBEDDING_DIM). Il n'est calculé QUE si une clé d'embedding est
    # configurée (`settings.GED_EMBEDDING_ENABLED` + provider) — sinon il reste
    # NULL et la recherche sémantique est un no-op qui retombe sur la recherche
    # plein-texte (GED11). Aucun appel réseau ni coût tant que la clé est absente.
    embedding = VectorField(dimensions=EMBEDDING_DIM, null=True, blank=True)
    # GED16 — verrouillage optimiste (check-out / check-in).
    # `locked_by` : utilisateur qui a extrait le document ; NULL = libre.
    # `locked_at` : horodatage du verrouillage (posé côté serveur).
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_documents_verrou',
        verbose_name="verrouille par")
    locked_at = models.DateTimeField(null=True, blank=True,
                                     verbose_name="verrouille le")
    # GED17 — cycle de vie documentaire (statut LOCAL à la GED, séparé du
    # funnel STAGES.py). Tout document naît « brouillon » ; les transitions
    # sont gardées côté serveur par `services.change_lifecycle_status` selon la
    # machine à états `LIFECYCLE_TRANSITIONS`. Jamais muté directement par
    # l'API (lecture seule au serializer) — uniquement via l'action dédiée.
    statut = models.CharField(
        max_length=12, choices=LIFECYCLE_CHOICES, default=LIFECYCLE_BROUILLON,
        verbose_name="statut du cycle de vie")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_documents_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        indexes = [
            models.Index(fields=['company', 'folder']),
            # GED11 — index GIN sur le tsvector pour la recherche plein-texte.
            GinIndex(fields=['search_vector'], name='ged_doc_search_gin'),
            # GED16 — index rapide sur les documents verrouillés par un utilisateur.
            models.Index(fields=['locked_by'], name='ged_doc_locked_by_idx'),
            # GED17 — filtre rapide par statut du cycle de vie (par société).
            models.Index(fields=['company', 'statut'],
                         name='ged_doc_co_statut_idx'),
        ]

    @property
    def is_locked(self):
        """True si le document est actuellement verrouillé (check-out actif)."""
        return self.locked_by_id is not None

    @property
    def transitions_autorisees(self):
        """GED17 — statuts atteignables depuis le statut courant (liste triée).

        Sert l'UI (boutons d'avancement disponibles) et reste l'unique source
        de vérité de la machine à états, partagée avec
        `services.change_lifecycle_status`."""
        return sorted(LIFECYCLE_TRANSITIONS.get(self.statut, set()))

    def __str__(self):
        return self.nom


class DocumentChunk(models.Model):
    """FG352 — Fragment indexé d'un document pour le RAG / DocQA.

    Le RAG (récupération augmentée) découpe le texte d'un document (OCR/nom) en
    fragments (« chunks ») chevauchants et stocke un embedding par fragment dans
    le MÊME magasin pgvector que `Document.embedding` (GED12) — on ne dresse PAS
    un second magasin vectoriel. Un outil de récupération renvoie les top-k
    fragments les plus proches d'une question, scopés société + ACL coffre-fort.

    KEY-GATED no-op : sans clé d'embedding (`services.embedding_enabled()`),
    aucun fragment n'est embeddé (l'indexation est un no-op) et la récupération
    renvoie un résultat vide — aucun appel réseau, aucun coût.

    Company posée côté serveur (cohérente avec celle du document) — jamais lue du
    corps de requête. `chunk_index` ordonne les fragments d'un même document.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_document_chunks')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='chunks')
    # Position du fragment dans le document (0, 1, 2…) — posée côté serveur.
    chunk_index = models.PositiveIntegerField(default=0)
    # Texte brut du fragment (sert à renvoyer le passage récupéré à l'agent).
    texte = models.TextField(blank=True, default='')
    # Embedding du fragment (dimension EMBEDDING_DIM, alignée sur GED12). NULL
    # tant que la clé d'embedding est absente (no-op). Réutilise le même type
    # pgvector — pas un second magasin vectoriel.
    embedding = VectorField(dimensions=EMBEDDING_DIM, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index', 'id']
        unique_together = [('document', 'chunk_index')]
        verbose_name = 'Fragment de document'
        verbose_name_plural = 'Fragments de document'
        indexes = [
            models.Index(fields=['company', 'document'],
                         name='ged_chunk_co_doc_idx'),
        ]

    def __str__(self):
        return f'{self.document} #{self.chunk_index}'


class DocumentVersion(models.Model):
    """Version d'un document (GED3) — pointeur vers un objet MinIO.

    Chaque version porte une clé objet MinIO (`file_key`, conventions de
    `records.storage` — bucket erp-uploads, le fichier ne quitte jamais le
    stockage objet), un `checksum` (SHA-256) pour la déduplication, un numéro
    de version incrémental (1, 2, 3…), l'auteur et la date. Company posée côté
    serveur — toujours cohérente avec celle du document.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_document_versions')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='versions')
    # Numéro de version incrémental par document (1, 2, 3…) — posé côté serveur.
    version = models.PositiveIntegerField(default=1)
    # Clé objet MinIO (bucket erp-uploads) — conventions records.storage.
    file_key = models.CharField(max_length=500)
    filename = models.CharField(max_length=255, blank=True, default='')
    size = models.PositiveIntegerField(default=0)
    mime = models.CharField(max_length=120, blank=True, default='')
    # SHA-256 (hex) du contenu pour la déduplication : deux versions de même
    # checksum dans une société pointent vers un contenu identique.
    checksum = models.CharField(max_length=64, blank=True, default='', db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_versions_uploadees')
    # GED15 — traçabilité de la restauration : si cette version est le résultat
    # d'une restauration d'une version antérieure, `restored_from` pointe vers
    # cette version d'origine. NULL pour toutes les autres versions. Jamais lu
    # du corps de requête — posé côté serveur dans `services.restore_version`.
    restored_from = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_restorations',
        verbose_name='restaurée depuis')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version', '-id']
        unique_together = [('document', 'version')]
        verbose_name = 'Version de document'
        verbose_name_plural = 'Versions de document'
        indexes = [
            models.Index(fields=['company', 'checksum']),
            models.Index(fields=['document', 'version']),
        ]

    def __str__(self):
        return f'{self.document} v{self.version}'


class DocumentLien(models.Model):
    """GED6 — Liaison polymorphe entre un Document et un objet métier.

    Rattache un document GED à N'IMPORTE quel enregistrement métier autorisé
    (lead, client, devis, bon de commande, facture, chantier/installation,
    ticket SAV, outillage) via le MÊME mécanisme ContentType que
    `records.Activity`/`Attachment`/`Comment`/`TaggedItem` — on ne réinvente pas
    de schéma de FK générique. La cible est bornée par `records.ALLOWED_TARGETS`
    (validation côté serveur : on ne lie jamais un type arbitraire).

    Company posée côté serveur (cohérente avec celle du document) — jamais lue du
    corps de requête. Un même document ne se lie qu'UNE fois à un objet donné.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_document_liens')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='liens')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_liens_crees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        unique_together = [('document', 'content_type', 'object_id')]
        verbose_name = 'Lien de document'
        verbose_name_plural = 'Liens de document'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['company', 'document']),
        ]

    def __str__(self):
        return f'{self.document} ↔ {self.content_type.model}:{self.object_id}'


class DocumentTag(models.Model):
    """GED9 — Taxonomie de tags documentaires (vocabulaire HIÉRARCHIQUE).

    Contrairement au tag plat partagé de `records.Tag`, la GED gère une
    TAXONOMIE : des tags peuvent porter un parent (`parent`, self-FK) pour
    former une arborescence de catégories (ex. « Juridique » → « Contrats » →
    « NDA »). Le `slug` est l'identifiant stable par société ; `couleur` un chip
    UI optionnel. Company posée côté serveur. Un tag est unique par (société,
    slug). On applique un tag à un document via `DocumentTagAssignment`.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_tags')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='enfants')
    nom = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110)
    couleur = models.CharField(max_length=7, blank=True, default='')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        unique_together = [('company', 'slug')]
        verbose_name = 'Tag documentaire'
        verbose_name_plural = 'Tags documentaires'
        indexes = [
            models.Index(fields=['company', 'slug']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return self.nom

    def ancetres(self):
        """Liste des tags ancêtres (du plus proche à la racine).

        Remonte la self-FK `parent` en restant borné à la société. Sert au
        chemin lisible « Juridique / Contrats / NDA » et à la garde anti-cycle.
        """
        chaine = []
        courant = self.parent
        seen = set()
        while courant is not None and courant.pk not in seen:
            seen.add(courant.pk)
            chaine.append(courant)
            courant = courant.parent
        return chaine


class DocumentTagAssignment(models.Model):
    """GED9 — Application d'un tag de la taxonomie à un document.

    Lien M2M explicite (through) entre `Document` et `DocumentTag` : un document
    porte N tags, un tag étiquette N documents. Unique par (document, tag).
    Company posée côté serveur (cohérente avec le document et le tag).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_tag_assignments')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='tag_assignments')
    tag = models.ForeignKey(
        DocumentTag, on_delete=models.CASCADE, related_name='assignments')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_tag_assignments_crees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        unique_together = [('document', 'tag')]
        verbose_name = 'Affectation de tag'
        verbose_name_plural = 'Affectations de tag'
        indexes = [
            models.Index(fields=['company', 'document']),
            models.Index(fields=['tag']),
        ]

    def __str__(self):
        return f'{self.document} #{self.tag}'


class DemandeApprobation(models.Model):
    """GED18 — Demande d'approbation / revue d'un document.

    Couche EXPLICITE de validation par-dessus le cycle de vie GED17 : un
    `demandeur` lance une revue d'un document et désigne (optionnellement) un
    `approbateur` ; ce dernier APPROUVE ou REJETTE, ce qui horodate la décision
    (`decision_le`) et la trace (`commentaire`). À l'approbation, le service
    réutilise `change_lifecycle_status` pour faire avancer le document
    « revue → approuvé » — il NE duplique PAS la machine à états du cycle de vie.

    Les statuts (`en_attente` / `approuve` / `rejete`) sont LOCAUX à la GED et
    distincts du funnel commercial `STAGES.py` (rule #2). `company`,
    `demandeur` et `approbateur` (au moment de la décision) sont posés côté
    serveur — jamais lus du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_demandes_approbation')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='demandes_approbation')
    # Utilisateur qui a lancé la demande de revue (posé côté serveur).
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_demandes_approbation_emises',
        verbose_name='demandeur')
    # Approbateur (relecteur). Renseigné à l'assignation OU au moment de la
    # décision (celui qui tranche) — posé côté serveur, jamais du corps.
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_demandes_approbation_recues',
        verbose_name='approbateur')
    statut = models.CharField(
        max_length=10, choices=APPROBATION_CHOICES,
        default=APPROBATION_EN_ATTENTE,
        verbose_name="statut de la demande")
    commentaire = models.TextField(blank=True, default='')
    # Horodatage de la décision (approbation/rejet) — NULL tant qu'en attente.
    decision_le = models.DateTimeField(
        null=True, blank=True, verbose_name='décidée le')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Demande d'approbation"
        verbose_name_plural = "Demandes d'approbation"
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ged_demande_co_statut_idx'),
            models.Index(fields=['company', 'document'],
                         name='ged_demande_co_doc_idx'),
            models.Index(fields=['approbateur'],
                         name='ged_demande_approb_idx'),
        ]

    @property
    def is_pending(self):
        """True si la demande est encore en attente d'une décision."""
        return self.statut == APPROBATION_EN_ATTENTE

    def __str__(self):
        return f'Approbation {self.document} ({self.statut})'
