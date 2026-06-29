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
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone
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

# GED19 — ACL par dossier/document (héritage + override).
#
# Niveaux d'accès (LOCAUX à la GED), ordonnés du plus faible au plus fort :
#   lecture  : voir / télécharger le document
#   ecriture : lecture + déposer une nouvelle version / éditer les métadonnées
#   gestion  : ecriture + gérer l'ACL elle-même (octroyer/retirer des droits)
#
# Une entrée ACL (`AclGed`) cible EXACTEMENT un dossier OU un document (jamais
# les deux, jamais aucun) et désigne un `principal` : un utilisateur ET/OU un
# rôle (au moins l'un des deux). Un document HÉRITE de l'ACL de son dossier (et
# des ancêtres) ; une entrée posée DIRECTEMENT sur le document (ou un dossier
# plus proche) constitue un OVERRIDE qui l'emporte sur l'ACL héritée. Le drapeau
# `herite` indique si cette entrée se propage aux sous-dossiers/documents
# (héritée vers le bas) ou reste locale à la cible (override pur).
#
# Ces niveaux sont LOCAUX à la GED et n'ont AUCUN rapport avec le funnel
# commercial `STAGES.py` (rule #2) — on n'importe surtout PAS `STAGES.py` ici.
ACL_LECTURE = 'lecture'
ACL_ECRITURE = 'ecriture'
ACL_GESTION = 'gestion'

ACL_CHOICES = [
    (ACL_LECTURE, 'Lecture'),
    (ACL_ECRITURE, 'Écriture'),
    (ACL_GESTION, 'Gestion'),
]

# Rang numérique des niveaux : un niveau supérieur INCLUT les inférieurs. Sert
# à comparer des droits (le plus permissif l'emporte au sein d'un même scope).
ACL_RANK = {
    ACL_LECTURE: 1,
    ACL_ECRITURE: 2,
    ACL_GESTION: 3,
}

# GED22 — Politiques de rétention documentaire (LOCALES à la GED).
#
# Une politique décrit COMBIEN DE TEMPS une classe de documents est conservée
# (`duree_conservation_jours`, à partir de la date de création du document) et
# CE QU'IL ADVIENT À L'ÉCHÉANCE (`action_echeance`). Par défaut l'échéance est
# purement CONSULTATIVE : `signaler` (flag) — le document reste intact, la
# politique se contente de le LISTER comme « échu » pour décision humaine.
# `archiver` suggère un classement (jamais un effacement). `supprimer` reste un
# choix EXPLICITE et n'est JAMAIS exécuté passivement : aucune politique ne
# supprime un document en cascade ; la suppression demeure une action séparée,
# délibérée et tracée (rule : jamais destructif par défaut).
#
# Ces actions sont LOCALES à la GED et n'ont AUCUN rapport avec le funnel
# commercial `STAGES.py` (rule #2) — on n'importe surtout PAS `STAGES.py` ici.
RETENTION_SIGNALER = 'signaler'   # flag : lister l'échu, ne rien faire d'autre
RETENTION_ARCHIVER = 'archiver'   # suggérer un archivage (jamais effacer)
RETENTION_SUPPRIMER = 'supprimer'  # purge EXPLICITE (action séparée, jamais auto)

RETENTION_ACTION_CHOICES = [
    (RETENTION_SIGNALER, 'Signaler'),
    (RETENTION_ARCHIVER, 'Archiver'),
    (RETENTION_SUPPRIMER, 'Supprimer'),
]

# Portée d'une politique : tout le module, un cabinet, un dossier (+sous-arbre),
# ou une catégorie libre (`type_document`). La résolution prend la politique la
# PLUS SPÉCIFIQUE qui couvre un document (document < dossier < cabinet < global ;
# une politique typée affine encore par catégorie).
RETENTION_SCOPE_GLOBAL = 'global'
RETENTION_SCOPE_CABINET = 'cabinet'
RETENTION_SCOPE_FOLDER = 'dossier'
RETENTION_SCOPE_TYPE = 'type'

# Spécificité numérique d'une portée — plus c'est grand, plus c'est spécifique.
# Sert à choisir la politique la plus proche d'un document (`documents_echus`).
RETENTION_SCOPE_RANK = {
    RETENTION_SCOPE_GLOBAL: 0,
    RETENTION_SCOPE_TYPE: 1,
    RETENTION_SCOPE_CABINET: 2,
    RETENTION_SCOPE_FOLDER: 3,
}

# GED23 — Archivage légal à valeur probante (write-once / object-lock).
#
# Une fois un document ARCHIVÉ LÉGALEMENT (`ArchivageLegal` posé), il devient
# IMMUABLE — WRITE-ONCE : ni le document ni ses versions ne peuvent plus être
# modifiés ou supprimés (au niveau APPLICATIF — la garantie est posée dans
# `save()`/`delete()` ici ET dans `services.py`). L'enregistrement
# `ArchivageLegal` lui-même est en CRÉATION SEULE (immuable : pas d'update, pas
# de delete via l'API). On enregistre un `hash_integrite` (SHA-256 du contenu de
# la version archivée) pour la valeur probante (preuve d'intégrité, anti-
# altération) et, en BONUS best-effort, on pose un verrou objet MinIO
# (object-lock retain-until) via la couche `records.storage` SI le backend le
# supporte — sinon on dégrade proprement (l'immuabilité applicative reste LA
# garantie ; l'object-lock n'est qu'un renfort). Couche LOCALE à la GED, séparée
# du funnel commercial `STAGES.py` (rule #2) — on n'importe surtout PAS STAGES.py.
#
# Le message d'erreur levé quand on tente d'écrire/supprimer un objet archivé.
ARCHIVE_LEGALE_MESSAGE = (
    "Document archivé à valeur probante (write-once) : il est immuable et ne "
    "peut plus être modifié ni supprimé."
)


class ArchivageLegalError(Exception):
    """GED23 — Levée à toute tentative d'écriture/suppression d'un objet archivé.

    Hérite d'``Exception`` (et non de ``PermissionError``/``ValidationError``)
    pour rester explicitement reconnaissable ; les vues la traduisent en 403.
    L'immuabilité write-once est posée au niveau modèle (`save()`/`delete()`)
    ET service, de sorte qu'aucun chemin d'écriture ne peut la contourner."""


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
    # GED21 — Contrôle de diffusion : quand vrai, le contenu de ce document est
    # FILIGRANÉ (watermark « CONFIDENTIEL ») à chaque diffusion (aperçu GED14 ET
    # téléchargement public GED20). Défaut faux → comportement 1:1 inchangé : le
    # flux reste byte-identique à l'original quand le filigrane est désactivé.
    # Le filigrane est purement de RENDU (services.apply_watermark) ; il ne
    # modifie jamais le binaire stocké en base/MinIO ni aucun statut.
    watermark_diffusion = models.BooleanField(
        default=False, verbose_name="filigraner à la diffusion")
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

    @property
    def est_archive_legalement(self):
        """GED23 — True si ce document est archivé à valeur probante (write-once).

        Lit en base l'existence d'un `ArchivageLegal` rattaché à ce document.
        Tant qu'un archivage existe, le document (et ses versions) est IMMUABLE."""
        if self.pk is None:
            return False
        return self.archivages_legaux.exists()

    def save(self, *args, **kwargs):
        """GED23 — Refuse toute MODIFICATION d'un document archivé (write-once).

        Une CRÉATION (pk encore absent) reste libre ; seules les écritures sur un
        document DÉJÀ archivé légalement sont bloquées. La garantie est posée au
        niveau modèle pour qu'aucun chemin d'écriture (`save`/`update_fields`) ne
        puisse la contourner. L'indexation plein-texte/embedding passe par des
        `QuerySet.update()` (qui n'appellent PAS `save()`) — elle n'est donc pas
        affectée par cette garde et reste opérante après archivage."""
        if self.pk is not None and self.est_archive_legalement:
            raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """GED23 — Refuse la SUPPRESSION d'un document archivé (write-once)."""
        if self.pk is not None and self.est_archive_legalement:
            raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
        return super().delete(*args, **kwargs)

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

    def _document_archive_legalement(self):
        """True si le document parent est archivé légalement (write-once GED23).

        Lecture en base (l'existence d'un `ArchivageLegal` sur le document) —
        bornée au document parent de cette version."""
        document_id = self.document_id
        if document_id is None:
            return False
        return ArchivageLegal.objects.filter(document_id=document_id).exists()

    def save(self, *args, **kwargs):
        """GED23 — Refuse l'ajout/modification d'une version sur un document
        archivé légalement (write-once).

        Couvre AUSSI la création d'une nouvelle version : un document archivé est
        figé — on ne lui ajoute plus de version. L'indexation passe par
        `QuerySet.update()` et n'est pas affectée."""
        if self._document_archive_legalement():
            raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """GED23 — Refuse la suppression d'une version d'un document archivé."""
        if self._document_archive_legalement():
            raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
        return super().delete(*args, **kwargs)

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


class AclGed(models.Model):
    """GED19 — Liste de contrôle d'accès par dossier/document (héritage + override).

    Une entrée ACL octroie à un `principal` (un utilisateur ET/OU un rôle, au
    moins l'un des deux) un `niveau` d'accès (lecture/ecriture/gestion) sur
    EXACTEMENT une cible : un `folder` OU un `document` (jamais les deux, jamais
    aucun — garde `clean()` + contrainte base).

    Modèle d'héritage : un document HÉRITE de l'ACL de son dossier et de tous les
    ancêtres (via le chemin matérialisé `Folder.path`). Une entrée posée
    directement sur la cible — ou sur un dossier PLUS PROCHE dans la chaîne —
    constitue un OVERRIDE qui l'emporte sur l'ACL héritée (le scope le plus
    proche gagne ; à scope égal, le niveau le plus permissif gagne). Le drapeau
    `herite` indique si l'entrée se propage vers le bas (sous-dossiers/documents)
    ou reste un override pur, local à sa cible.

    BACKWARD-COMPAT (DECISION) : sans aucune entrée ACL pour une cible, le
    comportement EXISTANT est strictement préservé (l'ACL coffre-fort GED8 +
    scoping société restent l'unique filtre). L'ACL GED19 ne fait que
    RESTREINDRE/AUTORISER en SUS, jamais élargir au-delà de la société. La
    résolution effective vit dans `selectors.acl_effective`.

    Company posée côté serveur (cohérente avec la cible) — jamais lue du corps
    de requête. Ces niveaux sont LOCAUX à la GED (séparés du funnel STAGES.py).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_acls')
    # Cible — EXACTEMENT l'une des deux est renseignée (garde clean()).
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_acls')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_acls')
    # Principal — utilisateur ET/OU rôle (au moins l'un des deux, garde clean()).
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_acls',
        verbose_name='utilisateur')
    role = models.ForeignKey(
        'roles.Role', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_acls',
        verbose_name='rôle')
    niveau = models.CharField(
        max_length=8, choices=ACL_CHOICES, default=ACL_LECTURE,
        verbose_name="niveau d'accès")
    # True : l'entrée se propage aux sous-dossiers/documents (héritage vers le
    # bas). False : override pur, local à la cible (ne descend pas).
    herite = models.BooleanField(default=True, verbose_name='héritée vers le bas')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_acls_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Droit d'accès GED"
        verbose_name_plural = "Droits d'accès GED"
        indexes = [
            models.Index(fields=['company', 'folder'],
                         name='ged_acl_co_folder_idx'),
            models.Index(fields=['company', 'document'],
                         name='ged_acl_co_doc_idx'),
            models.Index(fields=['utilisateur'], name='ged_acl_user_idx'),
            models.Index(fields=['role'], name='ged_acl_role_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(folder__isnull=False, document__isnull=True)
                    | models.Q(folder__isnull=True, document__isnull=False)
                ),
                name='ged_acl_exactly_one_target',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(utilisateur__isnull=False)
                    | models.Q(role__isnull=False)
                ),
                name='ged_acl_principal_required',
            ),
        ]

    def __str__(self):
        cible = self.document or self.folder
        principal = self.utilisateur or self.role
        return f'ACL {cible} → {principal} ({self.niveau})'

    @property
    def rank(self):
        """Rang numérique du niveau (1=lecture, 2=ecriture, 3=gestion)."""
        return ACL_RANK.get(self.niveau, 0)

    def clean(self):
        """Garantit cible exactement-une + principal au moins-un.

        - EXACTEMENT un de (`folder`, `document`) est renseigné.
        - AU MOINS un de (`utilisateur`, `role`) est renseigné.
        """
        from django.core.exceptions import ValidationError
        if bool(self.folder_id) == bool(self.document_id):
            raise ValidationError(
                "Une entrée ACL cible exactement un dossier OU un document.")
        if not self.utilisateur_id and not self.role_id:
            raise ValidationError(
                "Une entrée ACL désigne au moins un utilisateur ou un rôle.")


def _default_partage_token():
    """Jeton de partage long, imprévisible et URL-safe (GED20).

    Réutilise le même générateur que `ventes.ShareLink` (secrets.token_urlsafe,
    32 octets → ~43 caractères) : cryptographiquement fort, impossible à deviner
    ou à énumérer. C'est le SEUL secret qui authentifie l'accès public."""
    return secrets.token_urlsafe(32)


class PartageGed(models.Model):
    """GED20 — Partage public d'un document par lien tokenisé.

    Génère un lien PUBLIC (sans login) vers un document GED, authentifié par un
    seul secret : un `token` long et imprévisible (secrets.token_urlsafe). Le
    lien peut porter une expiration (`expires_at`), un mot de passe optionnel
    (`password_hash`, haché via make_password — jamais en clair), et un quota de
    téléchargements (`quota_max`). Chaque accès incrémente `telechargements` ;
    `actif` permet la révocation immédiate (kill-switch).

    SÉCURITÉ — modèle calqué sur `ventes.ShareLink` + le canal PDF public
    tokenisé : le jeton est l'UNIQUE clé d'accès. L'endpoint public NE FAIT
    JAMAIS confiance à une identité/société venue de la requête — il résout tout
    DEPUIS le jeton (donc la société du document est implicite, jamais lue du
    corps). Un lien révoqué/expiré/au quota épuisé renvoie 404/410 sans fuite.
    Le contenu binaire vit dans MinIO (via la version courante du document) et
    est relayé même-origine — jamais de prix d'achat ni de document d'un autre
    locataire (le jeton ne référence qu'un seul document d'une seule société).

    Company posée côté serveur (cohérente avec celle du document) — jamais lue du
    corps de requête. `created_by` posé côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_partages')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='partages')
    # Jeton long, imprévisible, URL-safe — l'UNIQUE secret d'accès public.
    # `unique=True` crée déjà l'index nécessaire au lookup `?token=`.
    token = models.CharField(
        max_length=64, unique=True, default=_default_partage_token,
        editable=False)
    # Expiration optionnelle (NULL = jamais expiré). Posée côté serveur.
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="expire le")
    # Hash du mot de passe optionnel (make_password). NULL/'' = pas de mot de
    # passe. JAMAIS stocké en clair ; vérifié via check_password. TextField pour
    # accueillir n'importe quel format de hash Django (qui peut être long).
    password_hash = models.TextField(
        blank=True, default='', verbose_name="hash du mot de passe")
    # Quota de téléchargements optionnel (NULL = illimité). Posé côté serveur.
    quota_max = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="quota de téléchargements")
    # Compteur de téléchargements (incrémenté à chaque accès public servi).
    telechargements = models.PositiveIntegerField(
        default=0, verbose_name="téléchargements")
    # Kill-switch : un partage révoqué (actif=False) est immédiatement mort.
    actif = models.BooleanField(default=True, verbose_name="actif")
    # GED21 — Contrôle de diffusion au niveau du PARTAGE : force le filigrane sur
    # CE lien public même si le document n'est pas globalement marqué. Le contenu
    # public est filigrané si `watermark` (ce partage) OU
    # `document.watermark_diffusion` est vrai. Défaut faux → flux byte-identique.
    watermark = models.BooleanField(
        default=False, verbose_name="filigraner le partage")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_partages_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Partage GED'
        verbose_name_plural = 'Partages GED'
        indexes = [
            models.Index(fields=['company', 'document'],
                         name='ged_partage_co_doc_idx'),
        ]

    def __str__(self):
        return f'Partage {self.token[:8]}… → {self.document_id}'

    @property
    def has_password(self):
        """True si un mot de passe protège ce partage."""
        return bool(self.password_hash)

    @property
    def is_expired(self):
        """True si le partage a une expiration dépassée."""
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def quota_exhausted(self):
        """True si le quota de téléchargements est atteint (NULL = illimité)."""
        return (self.quota_max is not None
                and self.telechargements >= self.quota_max)

    @property
    def is_accessible(self):
        """True si le partage est actuellement servable publiquement.

        Il faut : actif ET non expiré ET quota non épuisé. La validation du mot
        de passe (le cas échéant) est faite séparément côté endpoint — elle
        renvoie 403 (et non 404) pour distinguer « mauvais mot de passe » de
        « lien mort »."""
        return (self.actif and not self.is_expired
                and not self.quota_exhausted)

    def set_password(self, raw_password):
        """Pose (ou retire) le mot de passe — haché, jamais en clair.

        Une valeur vide/None retire la protection (`password_hash` = '')."""
        if raw_password:
            self.password_hash = make_password(raw_password)
        else:
            self.password_hash = ''

    def check_password(self, raw_password):
        """Vérifie un mot de passe candidat contre le hash stocké.

        Sans mot de passe configuré, renvoie True (rien à vérifier)."""
        if not self.password_hash:
            return True
        if not raw_password:
            return False
        return check_password(raw_password, self.password_hash)


class PolitiqueRetention(models.Model):
    """GED22 — Politique de rétention documentaire (durée + action à l'échéance).

    Décrit COMBIEN DE TEMPS une classe de documents est conservée et CE QU'IL
    ADVIENT à l'échéance. La durée (`duree_conservation_jours`) court à partir de
    la date de CRÉATION du document (`Document.created_at`). À l'échéance :

      * ``signaler`` (DÉFAUT) : purement consultatif — le document est juste
        LISTÉ comme « échu » (flag) pour décision humaine, rien n'est modifié ;
      * ``archiver`` : suggère un classement/archivage (jamais un effacement) ;
      * ``supprimer`` : marque une intention de purge — mais la rétention NE
        SUPPRIME JAMAIS rien passivement. La suppression reste une action séparée,
        explicite et tracée (jamais une cascade automatique).

    Portée (du plus large au plus spécifique) : ``global`` (tout le module),
    ``cabinet`` (un cabinet + ses dossiers), ``dossier`` (un dossier + son
    sous-arbre matérialisé) ou ``type`` (une catégorie libre `type_document`).
    La résolution effective (`selectors.documents_echus`) applique à chaque
    document la politique ACTIVE la PLUS SPÉCIFIQUE qui le couvre.

    Multi-tenant : `company` posée côté serveur (jamais lue du corps de requête),
    toutes les requêtes bornées à la société. Ces statuts/actions sont LOCAUX à
    la GED (séparés du funnel commercial STAGES.py, rule #2).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_politiques_retention')
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    # Portée optionnelle — facultative : aucune cible = politique GLOBALE (couvre
    # tous les documents de la société). `cabinet`/`folder` ciblent un sous-arbre ;
    # `type_document` affine par catégorie libre (ex. « contrat », « facture »).
    cabinet = models.ForeignKey(
        Cabinet, on_delete=models.CASCADE, null=True, blank=True,
        related_name='politiques_retention')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True,
        related_name='politiques_retention')
    type_document = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='catégorie de document')
    # Durée de conservation à partir de la création du document (en jours).
    duree_conservation_jours = models.PositiveIntegerField(
        verbose_name='durée de conservation (jours)')
    # Action à l'échéance — DÉFAUT « signaler » (consultatif, jamais destructif).
    action_echeance = models.CharField(
        max_length=10, choices=RETENTION_ACTION_CHOICES,
        default=RETENTION_SIGNALER, verbose_name="action à l'échéance")
    actif = models.BooleanField(default=True, verbose_name='active')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_politiques_retention_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Politique de rétention GED'
        verbose_name_plural = 'Politiques de rétention GED'
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='ged_retention_co_actif_idx'),
            models.Index(fields=['company', 'cabinet'],
                         name='ged_retention_co_cab_idx'),
            models.Index(fields=['company', 'folder'],
                         name='ged_retention_co_fol_idx'),
        ]
        constraints = [
            # Une politique ne cible jamais À LA FOIS un cabinet ET un dossier
            # (portées concurrentes) — au plus l'un des deux.
            models.CheckConstraint(
                condition=(
                    models.Q(cabinet__isnull=True)
                    | models.Q(folder__isnull=True)
                ),
                name='ged_retention_cab_xor_folder',
            ),
        ]

    @property
    def scope(self):
        """Type de portée le plus spécifique de cette politique (code).

        dossier > cabinet > type (catégorie) > global. Sert la résolution de la
        politique la plus proche d'un document."""
        if self.folder_id:
            return RETENTION_SCOPE_FOLDER
        if self.cabinet_id:
            return RETENTION_SCOPE_CABINET
        if self.type_document:
            return RETENTION_SCOPE_TYPE
        return RETENTION_SCOPE_GLOBAL

    @property
    def scope_rank(self):
        """Rang numérique de spécificité (plus grand = plus spécifique)."""
        return RETENTION_SCOPE_RANK.get(self.scope, 0)

    @property
    def is_destructive(self):
        """True seulement si l'action explicite est « supprimer ».

        La rétention reste consultative par défaut : ce drapeau ne déclenche
        JAMAIS d'effacement automatique — il signale une intention de purge à
        traiter par une action séparée et délibérée."""
        return self.action_echeance == RETENTION_SUPPRIMER

    def clean(self):
        """Garde : pas de cabinet ET dossier simultanés ; durée > 0."""
        from django.core.exceptions import ValidationError
        if self.cabinet_id and self.folder_id:
            raise ValidationError(
                'Une politique cible au plus un cabinet OU un dossier.')
        if self.duree_conservation_jours is not None \
                and self.duree_conservation_jours <= 0:
            raise ValidationError(
                'La durée de conservation doit être strictement positive.')

    def __str__(self):
        return f'{self.nom} ({self.duree_conservation_jours} j → ' \
               f'{self.action_echeance})'


class ArchivageLegal(models.Model):
    """GED23 — Archivage légal à valeur probante d'un document (write-once).

    Marque un document comme ARCHIVÉ LÉGALEMENT à une date donnée, par un
    utilisateur, avec un motif. Une fois posé, le document (et toutes ses
    versions) devient IMMUABLE — WRITE-ONCE : plus aucune modification ni
    suppression (garde au niveau modèle dans `Document.save/delete` &
    `DocumentVersion.save/delete`, ET dans `services`).

    Valeur PROBANTE : on fige le `hash_integrite` (SHA-256 hexadécimal, 64
    caractères) du CONTENU de la version archivée au moment de l'archivage. Ce
    condensat sert de preuve d'intégrité (anti-altération) : recalculer le hash
    du contenu plus tard et le comparer atteste qu'il n'a pas été modifié.

    Renfort BONUS (best-effort) : `object_lock_retain_until` enregistre la date
    jusqu'à laquelle un verrou objet (MinIO/S3 Object-Lock) devrait retenir le
    fichier. Le service tente de poser ce verrou côté stockage SI le backend le
    supporte (import paresseux, dégradation propre sinon) — mais l'immuabilité
    APPLICATIVE est LA garantie ; l'object-lock n'est qu'un renfort.

    L'enregistrement lui-même est en CRÉATION SEULE (immuable) : `save()` refuse
    toute mise à jour et `delete()` toute suppression — un archivage légal ne se
    « dé-archive » jamais. Multi-tenant : `company` & `archive_par` posés côté
    serveur (jamais lus du corps de requête), toutes les requêtes bornées à la
    société. Couche LOCALE à la GED, séparée du funnel `STAGES.py` (rule #2).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_archivages_legaux')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='archivages_legaux')
    # Version précise figée au moment de l'archivage (la version courante au
    # moment de l'appel). Optionnelle : un document peut être archivé sans
    # version (rare) — le hash reste alors vide.
    version = models.ForeignKey(
        DocumentVersion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='archivages_legaux',
        verbose_name='version archivée')
    archive_le = models.DateTimeField(
        auto_now_add=True, verbose_name='archivé le')
    archive_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_archivages_legaux',
        verbose_name='archivé par')
    motif = models.TextField(blank=True, default='', verbose_name='motif')
    # Condensat SHA-256 (hexadécimal = 64 caractères) du contenu de la version
    # archivée — preuve d'intégrité à valeur probante. Vide si aucune version.
    hash_integrite = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name="condensat d'intégrité (SHA-256)")
    # Renfort object-lock (best-effort) : date de rétention jusqu'à laquelle un
    # verrou objet devrait retenir le fichier côté stockage. NULL si non posé.
    object_lock_retain_until = models.DateField(
        null=True, blank=True, verbose_name='verrou objet jusqu\'au')
    # True si le verrou objet a effectivement été posé côté stockage (best-effort
    # — reste faux si le backend ne supporte pas l'object-lock : on dégrade).
    object_lock_applique = models.BooleanField(
        default=False, verbose_name='verrou objet appliqué')

    class Meta:
        ordering = ['-archive_le', '-id']
        verbose_name = 'Archivage légal'
        verbose_name_plural = 'Archivages légaux'
        constraints = [
            # Un document n'est archivé légalement qu'UNE seule fois (write-once).
            models.UniqueConstraint(
                fields=['document'], name='ged_arch_legal_doc_unique'),
        ]
        indexes = [
            models.Index(fields=['company', 'document'],
                         name='ged_arch_legal_co_doc_idx'),
        ]

    def save(self, *args, **kwargs):
        """GED23 — Création SEULE : refuse toute mise à jour (immuable).

        Un archivage légal ne se modifie jamais — il n'existe que pour figer un
        état. Toute tentative de ré-`save()` d'un enregistrement déjà persisté
        est rejetée (write-once de l'archivage lui-même)."""
        if self.pk is not None:
            raise ArchivageLegalError(
                "Un archivage légal est immuable (création seule) : il ne peut "
                "pas être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """GED23 — Refuse la suppression d'un archivage légal (immuable)."""
        raise ArchivageLegalError(
            "Un archivage légal est immuable : il ne peut pas être supprimé.")

    def __str__(self):
        return f'Archivage légal — {self.document} ({self.archive_le:%Y-%m-%d})'
