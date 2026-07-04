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


# GED24 — Rétention légale / legal hold.
#
# Message d'erreur levé quand on tente de supprimer/purger un document couvert
# par une rétention légale active (gel anti-suppression pour contentieux).
LEGAL_HOLD_MESSAGE = (
    "Document sous rétention légale (legal hold) : sa suppression est gelée "
    "tant qu'une mise sous séquestre active le couvre."
)


# GED36 — Quota de stockage par société.
#
# Message levé quand un dépôt ferait dépasser le quota de stockage de la société.
QUOTA_DEPASSE_MESSAGE = (
    "Quota de stockage atteint pour cette société : impossible de déposer un "
    "nouveau fichier tant que de l'espace n'est pas libéré ou le quota relevé."
)


class QuotaDepasseError(Exception):
    """GED36 — Levée quand un dépôt dépasserait le quota de stockage de la société.

    Hérite d'``Exception`` (reconnaissable comme les erreurs GED23/GED24) ; la
    vue la traduit en 403 (jamais 500). Garde purement APPLICATIVE posée avant
    un dépôt — elle ne supprime jamais rien."""


class LegalHoldError(Exception):
    """GED24 — Levée à toute tentative de suppression d'un document sous hold.

    Hérite d'``Exception`` (et non de ``PermissionError``/``ValidationError``)
    pour rester explicitement reconnaissable ; les vues la traduisent en 403
    (jamais 500), exactement comme `ArchivageLegalError` (GED23). Le gel est
    posé au niveau modèle (`Document.delete()`) ET service, de sorte qu'aucun
    chemin de suppression ne peut le contourner. À la DIFFÉRENCE de l'archivage
    légal (write-once, permanent), une rétention légale est TEMPORAIRE et
    LIABLE : on la lève (`actif=False`) et le document redevient supprimable."""


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
    # XGED9 — alias d'ingestion email (ex. "compta", matché sur une adresse
    # plus-adressée `ged+compta@…` ou un objet `[compta]`). Vide = pas de
    # routage email vers ce dossier. Unique par société (jamais deux dossiers
    # sur le même alias — routage sans ambiguïté).
    alias_email = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="alias d'ingestion email")
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
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'alias_email'],
                condition=models.Q(~models.Q(alias_email='')),
                name='ged_folder_unique_alias_email'),
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
    # GED26 — Corbeille (soft-delete réversible). Un document « dans la
    # corbeille » a `supprime_le` renseigné : il disparaît des listes par défaut
    # mais N'EST PAS effacé (réversible via `restaurer_de_corbeille`). C'est une
    # couche SÉPARÉE de l'archivage légal write-once (GED23) et du legal hold
    # (GED24) — un document archivé/sous-hold n'est PAS mettable en corbeille
    # (mêmes gardes 403). Posé/effacé côté serveur uniquement.
    supprime_le = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name="mis en corbeille le")
    supprime_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_documents_corbeille',
        verbose_name="mis en corbeille par")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_documents_crees')
    # XGED18 — Document-LIEN : quand renseigné, ce document référence une URL
    # externe (Google Doc, fichier cloud…) au lieu de porter un fichier stocké.
    # Une entrée GED de première classe (tags/ACL/liaison métier/cycle de vie/
    # chatter) SANS stockage. Exclusif d'une version fichier en pratique — les
    # actions fichier (version/OCR/signature) le refusent explicitement (400).
    url_externe = models.URLField(
        max_length=2000, blank=True, default='',
        verbose_name="URL externe (document-lien)")
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

    @property
    def est_sous_legal_hold(self):
        """GED24 — True si une rétention légale ACTIVE couvre ce document.

        Lit en base l'existence d'un `LegalHold` `actif=True` rattaché à ce
        document. Tant qu'un hold actif existe, le document NE PEUT PAS être
        supprimé/purgé (gel anti-suppression pour contentieux), même si une
        politique de rétention (GED22) suggérait une purge. À la différence de
        l'archivage légal (GED23), le document reste ÉDITABLE — seul l'effacement
        est gelé — et le gel est TEMPORAIRE (levable)."""
        if self.pk is None:
            return False
        return self.legal_holds.filter(actif=True).exists()

    @property
    def est_document_lien(self):
        """XGED18 — True si ce document est un DOCUMENT-LIEN (URL externe, pas
        de fichier stocké). Les actions fichier (version/OCR/signature) doivent
        se refuser explicitement (400) sur un document-lien."""
        return bool(self.url_externe)

    @property
    def est_dans_corbeille(self):
        """GED26 — True si ce document est actuellement dans la corbeille.

        Un document est « en corbeille » dès que `supprime_le` est renseigné :
        il est masqué des listes par défaut mais reste intégralement récupérable
        (soft-delete réversible). Couche séparée des protections légales
        (GED23/GED24)."""
        return self.supprime_le is not None

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
        """GED23/GED24 — Refuse la SUPPRESSION d'un document protégé.

        Deux gels indépendants bloquent l'effacement, posés au niveau modèle
        comme filet de sécurité ultime (aucun chemin de suppression ne les
        contourne) :
          * GED23 — archivage légal write-once (permanent) ;
          * GED24 — rétention légale / legal hold (temporaire, levable).
        Les deux sont des couches SÉPARÉES : un document peut être sous l'une,
        l'autre, ou les deux."""
        if self.pk is not None and self.est_archive_legalement:
            raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
        if self.pk is not None and self.est_sous_legal_hold:
            raise LegalHoldError(LEGAL_HOLD_MESSAGE)
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


class LegalHold(models.Model):
    """GED24 — Rétention légale / legal hold sur un document (gel anti-suppression).

    Pose un GEL TEMPORAIRE de la suppression sur un document — typiquement pour
    un contentieux/litige — qui SURCLASSE toute purge de politique de rétention
    (GED22) : tant qu'un hold ACTIF couvre le document, sa suppression/purge/
    destruction de cycle de vie est BLOQUÉE (garde au niveau modèle
    `Document.delete()` ET service, traduite en 403 côté vue — jamais 500).

    Couche DISTINCTE et complémentaire des deux autres :
      * GED22 `PolitiqueRetention` — durée + action à l'échéance (consultatif) ;
        un legal hold prime sur toute intention de purge ;
      * GED23 `ArchivageLegal` — write-once probant, PERMANENT, qui fige AUSSI
        l'édition. Un legal hold, lui, est TEMPORAIRE et LEVABLE et ne gèle QUE
        la suppression (le document reste éditable).

    Un hold porte un motif, qui l'a posé (`place_par`) et quand (`date_pose`),
    et un drapeau `actif`. La levée (`lever_legal_hold`) bascule `actif=False`
    et trace `date_levee`/`leve_par` — on ne supprime jamais la trace d'un hold,
    on la lève (historique conservé). Un même document peut accumuler plusieurs
    holds (plusieurs litiges) : il reste gelé tant qu'AU MOINS un est actif.

    Multi-tenant : `company`, `place_par` et `leve_par` sont posés CÔTÉ SERVEUR
    (jamais lus du corps de requête) ; toutes les requêtes bornées à la société.
    Couche LOCALE à la GED, séparée du funnel commercial `STAGES.py` (rule #2).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_legal_holds')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='legal_holds')
    motif = models.TextField(blank=True, default='', verbose_name='motif')
    place_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_legal_holds_poses',
        verbose_name='placé par')
    date_pose = models.DateTimeField(
        auto_now_add=True, verbose_name='placé le')
    # True tant que la rétention légale est en vigueur (gel actif). Levée → faux.
    actif = models.BooleanField(default=True, verbose_name='actif')
    date_levee = models.DateTimeField(
        null=True, blank=True, verbose_name='levé le')
    leve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_legal_holds_leves',
        verbose_name='levé par')

    class Meta:
        ordering = ['-date_pose', '-id']
        verbose_name = 'Rétention légale (legal hold)'
        verbose_name_plural = 'Rétentions légales (legal holds)'
        indexes = [
            # Filtre rapide « ce document est-il gelé ? » (par société + actif).
            models.Index(fields=['company', 'document', 'actif'],
                         name='ged_hold_co_doc_actif_idx'),
        ]

    def __str__(self):
        etat = 'actif' if self.actif else 'levé'
        return f'Legal hold — {self.document} ({etat})'


# XGED6 — Vérification périodique d'intégrité des archives légales (loi 43-20).
CONTROLE_RESULTAT_OK = 'ok'
CONTROLE_RESULTAT_ALTERE = 'altere'
CONTROLE_RESULTAT_INDISPONIBLE = 'indisponible'  # contenu introuvable/erreur

CONTROLE_RESULTAT_CHOICES = [
    (CONTROLE_RESULTAT_OK, 'Intègre'),
    (CONTROLE_RESULTAT_ALTERE, 'Altéré'),
    (CONTROLE_RESULTAT_INDISPONIBLE, 'Indisponible'),
]


class ControleIntegrite(models.Model):
    """XGED6 — Journal d'un contrôle d'intégrité périodique d'un archivage
    légal (GED23, loi 43-20).

    `ArchivageLegal` fige un `hash_integrite` (SHA-256) AU DÉPÔT mais rien ne
    le RE-VÉRIFIE dans le temps. Ce modèle journalise CHAQUE contrôle
    (`verifier_integrite_archives`) : le hash CONSTATÉ au moment du contrôle,
    le résultat (intègre / altéré / indisponible) et l'horodatage — append-only
    par convention (aucun update/delete via l'API, comme `JournalAcces` GED35).

    « Altéré » signale un écart entre `hash_integrite` (figé au dépôt) et le
    hash recalculé maintenant — preuve d'une altération. « Indisponible »
    signale un contenu non re-téléchargeable (stockage KO) — DISTINCT d'une
    altération confirmée (pas d'accusation sans preuve positive).

    Multi-tenant : `company` posée CÔTÉ SERVEUR (cohérente avec l'archivage) —
    jamais lue du corps de requête."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_controles_integrite')
    archivage = models.ForeignKey(
        ArchivageLegal, on_delete=models.CASCADE, related_name='controles')
    resultat = models.CharField(
        max_length=14, choices=CONTROLE_RESULTAT_CHOICES,
        default=CONTROLE_RESULTAT_OK, verbose_name='résultat')
    hash_constate = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='hash constaté (SHA-256)')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Contrôle d'intégrité"
        verbose_name_plural = "Contrôles d'intégrité"
        indexes = [
            models.Index(fields=['company', 'archivage'],
                         name='ged_ctrl_co_arch_idx'),
            models.Index(fields=['company', 'resultat'],
                         name='ged_ctrl_co_resultat_idx'),
        ]

    def __str__(self):
        return f'Contrôle {self.archivage_id} — {self.resultat} @ {self.created_at}'


# GED30 — Signature électronique (point d'intégration + stub no-op).
#
# Statuts LOCAUX à la GED d'une demande de signature électronique sur un
# document. Couche GÉNÉRIQUE de signature de N'IMPORTE quel document GED —
# SÉPARÉE et DISTINCTE de la signature des CONTRATS (`contrats.SignatureContrat`,
# CONTRAT16) : on ne touche jamais l'app contrats. Ces statuts sont aussi sans
# rapport avec le funnel commercial `STAGES.py` (rule #2) — on n'importe surtout
# PAS `STAGES.py` ici.
#
#   en_attente ─▶ signe | refuse | annule
#
# KEY-GATED no-op (mirroir de l'embedding GED12) : tant qu'aucun provider e-sign
# externe n'est configuré (`settings.ESIGN_ENABLED` faux), la demande est un STUB
# purement LOCAL — aucun appel réseau, aucun coût, aucune dépendance nouvelle.
SIGNATURE_EN_ATTENTE = 'en_attente'
SIGNATURE_SIGNE = 'signe'
SIGNATURE_REFUSE = 'refuse'
SIGNATURE_ANNULE = 'annule'

SIGNATURE_CHOICES = [
    (SIGNATURE_EN_ATTENTE, 'En attente'),
    (SIGNATURE_SIGNE, 'Signée'),
    (SIGNATURE_REFUSE, 'Refusée'),
    (SIGNATURE_ANNULE, 'Annulée'),
]

# Provider e-sign par défaut quand aucun n'est configuré : « aucun » (stub).
SIGNATURE_PROVIDER_AUCUN = 'aucun'

# XGED2 — Mode de routage d'une demande multi-signataires (déclaré ici, avant
# `DemandeSignatureDocument`, qui porte le champ `routage`).
ROUTAGE_SEQUENTIEL = 'sequentiel'
ROUTAGE_PARALLELE = 'parallele'

ROUTAGE_CHOICES = [
    (ROUTAGE_SEQUENTIEL, 'Séquentiel (par ordre)'),
    (ROUTAGE_PARALLELE, 'Parallèle (tous en même temps)'),
]


class DemandeSignatureDocument(models.Model):
    """GED30 — Demande de signature électronique sur un document (point
    d'intégration + STUB no-op).

    Enregistre une demande de signature électronique d'UN document GED par UN
    signataire (nom + email), et SUIT son statut (`en_attente` → `signe` /
    `refuse` / `annule`). C'est un POINT D'INTÉGRATION générique vers un futur
    fournisseur e-sign (DocuSign/Yousign/…), volontairement câblé comme un STUB :

    KEY-GATED NO-OP (mirroir de l'embedding GED12) : tant que
    `services.esign_active()` est faux (aucun `settings.ESIGN_ENABLED` +
    provider configuré), `demander_signature` se contente de CRÉER la demande
    `en_attente` côté serveur — AUCUN appel réseau, AUCUN coût, AUCUNE dépendance
    nouvelle. Le `provider` reste « aucun » et `provider_ref` vide. Quand un
    provider sera câblé (clé posée par le founder), le service appellera le
    fournisseur et renseignera `provider`/`provider_ref` ; la complétion sera
    enregistrée via `marquer_signe` (webhook/manuel).

    Couche GÉNÉRIQUE de signature documentaire — SÉPARÉE et DISTINCTE de la
    signature des CONTRATS (`contrats.SignatureContrat`, CONTRAT16, jamais
    touchée ici) et du funnel commercial `STAGES.py` (rule #2 — jamais importé).

    Multi-tenant : `company` & `created_by` posés CÔTÉ SERVEUR (jamais lus du
    corps de requête) ; toutes les requêtes bornées à la société.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_demandes_signature')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='demandes_signature')
    signataire_nom = models.CharField(
        max_length=255, verbose_name='nom du signataire')
    signataire_email = models.EmailField(
        verbose_name='email du signataire')
    statut = models.CharField(
        max_length=10, choices=SIGNATURE_CHOICES,
        default=SIGNATURE_EN_ATTENTE,
        verbose_name='statut de la signature')
    # Fournisseur e-sign utilisé. « aucun » = STUB no-op (aucun provider câblé).
    provider = models.CharField(
        max_length=40, default=SIGNATURE_PROVIDER_AUCUN,
        verbose_name='fournisseur e-sign')
    # Référence opaque de la demande côté provider (vide en mode stub).
    provider_ref = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='référence fournisseur')
    date_demande = models.DateTimeField(
        auto_now_add=True, verbose_name='demandée le')
    # Horodatage de la signature effective — NULL tant que non signée.
    date_signature = models.DateTimeField(
        null=True, blank=True, verbose_name='signée le')
    # XGED1 — Cérémonie de signature in-app (lien public tokenisé, loi 53-05).
    #
    # `token` est le SEUL secret d'accès public — même motif que
    # `PartageGed.token` (secrets.token_urlsafe, cryptographiquement fort,
    # impossible à deviner/énumérer). `expires_at` optionnelle (NULL = jamais
    # expiré) borne la validité du lien (token inconnu/expiré → 404/410 côté
    # endpoint public, jamais de fuite distinguant les deux cas pour un jeton
    # inconnu). Rétro-compatible : une demande GED30 pré-XGED1 reçoit un token
    # au premier `save()` via le défaut — aucune migration de données requise.
    token = models.CharField(
        max_length=64, unique=True, default=_default_partage_token,
        editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name='expire le')
    # Preuves IMMUABLES de la cérémonie (posées CÔTÉ SERVEUR uniquement, jamais
    # lues du corps de requête) — pattern QJ10 (`ventes.DevisSignature`) :
    # consentement explicite, IP, user-agent, hash SHA-256 du contenu signé
    # (la version courante du document au moment de la signature), horodatage.
    # En LECTURE SEULE via l'API (aucun endpoint ne les modifie après coup).
    consentement_explicite = models.BooleanField(
        default=False, verbose_name="consentement explicite à signer")
    adresse_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='adresse IP du signataire')
    user_agent = models.CharField(
        max_length=512, blank=True, default='', verbose_name='user-agent')
    hash_contenu = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='hash du contenu signé (SHA-256)')
    # Signature tapée (nom) ET/OU tracée (pattern FG69 `signature_client` —
    # data-URL/vecteur base64 d'un tracé). Au moins l'un des deux est requis
    # pour signer (garde côté service). Jamais lues du corps après signature.
    signature_texte = models.CharField(
        max_length=255, blank=True, default='', verbose_name='signature tapée')
    signature_tracee = models.TextField(
        blank=True, default='', verbose_name='signature tracée (vecteur/data-URL)')
    # Refus explicite avec motif obligatoire — alternative terminale à la
    # signature. `refuse_le` horodate le refus (NULL tant que non refusée).
    motif_refus = models.TextField(blank=True, default='', verbose_name='motif de refus')
    refuse_le = models.DateTimeField(
        null=True, blank=True, verbose_name='refusée le')
    # XGED2 — Circuit multi-signataires : mode de routage des `SignataireDemande`
    # rattachés (séquentiel par défaut = rétrocompatible avec le mono-signataire
    # GED30/XGED1, qui n'a qu'un seul rang de toute façon). Cadence des relances
    # automatiques en jours (0/NULL = pas de relance auto). `annule_le`/
    # `annule_par` tracent une annulation ÉMETTEUR (action dédiée, jamais
    # silencieuse) — distincte du refus SIGNATAIRE.
    routage = models.CharField(
        max_length=10, choices=ROUTAGE_CHOICES, default=ROUTAGE_SEQUENTIEL,
        verbose_name='mode de routage')
    relance_cadence_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='cadence de relance (jours)')
    annule_le = models.DateTimeField(
        null=True, blank=True, verbose_name='annulée le')
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_demandes_signature_annulees',
        verbose_name='annulée par')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_demandes_signature_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_demande', '-id']
        verbose_name = 'Demande de signature'
        verbose_name_plural = 'Demandes de signature'
        indexes = [
            models.Index(fields=['company', 'document'],
                         name='ged_sign_co_doc_idx'),
            models.Index(fields=['company', 'statut'],
                         name='ged_sign_co_statut_idx'),
        ]

    @property
    def is_pending(self):
        """True si la demande est encore en attente de signature."""
        return self.statut == SIGNATURE_EN_ATTENTE

    @property
    def is_expired(self):
        """XGED1 — True si le lien public de signature a une expiration dépassée."""
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def __str__(self):
        return f'Signature {self.document} → {self.signataire_nom} ' \
               f'({self.statut})'


# XGED2 — Circuit multi-signataires (séquentiel/parallèle).
#
# Statuts LOCAUX au signataire — indépendants du statut GLOBAL de la demande
# (`DemandeSignatureDocument.statut`). Un signataire au rang N+1 n'est notifié
# (et donc « actionnable ») qu'une fois le rang N traité, en mode séquentiel ;
# tous les rangs sont notifiés immédiatement en mode parallèle.
SIGNATAIRE_EN_ATTENTE = 'en_attente'   # pas encore son tour (séquentiel) / notifié
SIGNATAIRE_NOTIFIE = 'notifie'         # notifié, en attente de son action
SIGNATAIRE_SIGNE = 'signe'
SIGNATAIRE_REFUSE = 'refuse'

SIGNATAIRE_STATUT_CHOICES = [
    (SIGNATAIRE_EN_ATTENTE, 'En attente de son tour'),
    (SIGNATAIRE_NOTIFIE, 'Notifié'),
    (SIGNATAIRE_SIGNE, 'Signé'),
    (SIGNATAIRE_REFUSE, 'Refusé'),
]

# Rôle du destinataire dans le circuit — un « copie » consulte sans signer,
# un « approbateur » valide sans être juridiquement signataire du document,
# un « signataire » signe effectivement.
ROLE_SIGNATAIRE = 'signataire'
ROLE_COPIE = 'copie'
ROLE_APPROBATEUR = 'approbateur'

ROLE_DESTINATAIRE_CHOICES = [
    (ROLE_SIGNATAIRE, 'Signataire'),
    (ROLE_COPIE, 'Copie'),
    (ROLE_APPROBATEUR, 'Approbateur'),
]


# ZGED1 — Authentification extra optionnelle d'un rôle signataire réutilisable.
ROLE_AUTH_EXTRA_AUCUNE = 'aucune'
ROLE_AUTH_EXTRA_SMS = 'sms'
ROLE_AUTH_EXTRA_EMAIL_OTP = 'email_otp'

ROLE_AUTH_EXTRA_CHOICES = [
    (ROLE_AUTH_EXTRA_AUCUNE, 'Aucune'),
    (ROLE_AUTH_EXTRA_SMS, 'Code SMS'),
    (ROLE_AUTH_EXTRA_EMAIL_OTP, 'Code par email (OTP)'),
]


class RoleSignataire(models.Model):
    """ZGED1 — Catalogue de rôles signataires RÉUTILISABLES (pattern Odoo Sign
    « Rôle »).

    Une entité PARTAGÉE (« Client », « Employé »…) portant une `couleur`
    (#hex, cohérence visuelle du champ de signature dans l'éditeur XGED3), une
    étape d'authentification supplémentaire optionnelle (`auth_extra` —
    aucune/sms/email_otp, exploitée par ZGED2) et un drapeau
    `peut_changer_signataire` (le destinataire peut réassigner sa propre
    signature à un tiers). Réutilisable à travers les `ModeleDocument` (GED27)
    et les demandes (XGED1/XGED2) — un même rôle est référencé par N
    `SignataireDemande` sans duplication.

    RÉTROCOMPATIBLE : `SignataireDemande.role` (texte libre
    signataire/copie/approbateur) reste la valeur DE FAIT quand aucun
    `role_signataire` n'est référencé — ce catalogue est un ENRICHISSEMENT
    optionnel, jamais un remplacement du champ existant. Company posée côté
    serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_roles_signataire')
    nom = models.CharField(max_length=100)
    couleur = models.CharField(
        max_length=7, default='#2b5cab', verbose_name='couleur (#hex)')
    auth_extra = models.CharField(
        max_length=10, choices=ROLE_AUTH_EXTRA_CHOICES,
        default=ROLE_AUTH_EXTRA_AUCUNE,
        verbose_name='authentification supplémentaire')
    peut_changer_signataire = models.BooleanField(
        default=False, verbose_name='peut changer de signataire')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_roles_signataire_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Rôle signataire'
        verbose_name_plural = 'Rôles signataires'
        indexes = [
            models.Index(fields=['company'], name='ged_rolesign_co_idx'),
        ]

    def __str__(self):
        return self.nom


class SignataireDemande(models.Model):
    """XGED2 — Un destinataire (signataire/copie/approbateur) d'une demande de
    signature multi-parties.

    Une `DemandeSignatureDocument` (GED30/XGED1) porte désormais N destinataires
    ordonnés via cette table — RÉTROCOMPATIBLE : le signataire historique mono-
    partie de GED30 (`signataire_nom`/`signataire_email` sur la demande) reste
    la valeur affichée quand AUCUN `SignataireDemande` n'existe pour la demande
    (comportement 1:1 inchangé pour les demandes XGED1 pré-existantes) ;
    `services.signataires_effectifs` résout cette rétrocompatibilité.

    Chaque destinataire porte son PROPRE `token` public (même motif que
    `PartageGed`/`DemandeSignatureDocument.token`) : le lien envoyé à un
    signataire ne dévoile jamais les autres, et signer/refuser à SON rang
    n'affecte que SON statut individuel (`statut`) — le service agrège vers le
    statut GLOBAL de la demande.

    Routage (`demande.routage`) : en séquentiel, un signataire au rang `ordre`
    N+1 n'est notifié (`statut → notifie`) qu'après que le rang N a signé ; en
    parallèle, tous les signataires sont notifiés dès l'envoi. Les `copie` et
    `approbateur` ne bloquent jamais la progression séquentielle des
    `signataire` (ils sont notifiés en parallèle du flux, informatif).

    Multi-tenant : `company` posée CÔTÉ SERVEUR (cohérente avec la demande) —
    jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_signataires_demande')
    demande = models.ForeignKey(
        DemandeSignatureDocument, on_delete=models.CASCADE,
        related_name='signataires')
    nom = models.CharField(max_length=255, verbose_name='nom')
    email = models.EmailField(blank=True, default='', verbose_name='email')
    telephone = models.CharField(
        max_length=32, blank=True, default='', verbose_name='téléphone')
    # Rang dans le circuit — détermine l'ordre de notification en séquentiel ;
    # purement informatif (tri d'affichage) en parallèle.
    ordre = models.PositiveIntegerField(default=1, verbose_name='ordre')
    role = models.CharField(
        max_length=12, choices=ROLE_DESTINATAIRE_CHOICES,
        default=ROLE_SIGNATAIRE, verbose_name='rôle')
    # ZGED1 — référence OPTIONNELLE au catalogue de rôles réutilisables : quand
    # renseigné, préremplit couleur/auth_extra depuis `RoleSignataire`.
    # RÉTROCOMPATIBLE : sans référence, le `role` texte ci-dessus reste la
    # seule valeur (comportement XGED2 strictement inchangé).
    role_signataire = models.ForeignKey(
        RoleSignataire, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='signataires_demande', verbose_name='rôle réutilisable')
    statut = models.CharField(
        max_length=10, choices=SIGNATAIRE_STATUT_CHOICES,
        default=SIGNATAIRE_EN_ATTENTE, verbose_name='statut')
    # Jeton public PROPRE à ce destinataire — un lien par personne.
    token = models.CharField(
        max_length=64, unique=True, default=_default_partage_token,
        editable=False)
    # Horodatage de la dernière notification/relance envoyée (sert la cadence
    # des relances automatiques — `services.relancer_signataires_dus`).
    notifie_le = models.DateTimeField(
        null=True, blank=True, verbose_name='notifié le')
    derniere_relance_le = models.DateTimeField(
        null=True, blank=True, verbose_name='dernière relance le')
    nb_relances = models.PositiveIntegerField(
        default=0, verbose_name='nombre de relances envoyées')
    date_action = models.DateTimeField(
        null=True, blank=True, verbose_name='signé/refusé le')
    motif_refus = models.TextField(blank=True, default='', verbose_name='motif de refus')
    # ZGED2 — Authentification extra AVANT signature (SMS/OTP email, key-gated).
    #
    # `auth_extra` : mode effectif pour CE destinataire. Vide (défaut) = hérite
    # du `role_signataire.auth_extra` (ZGED1) s'il y en a un, sinon « aucune ».
    # Le code/hash/expiration/essais sont posés CÔTÉ SERVEUR uniquement — jamais
    # lus d'un corps de requête. `otp_code_hash` : SHA-256 du code à 6 chiffres
    # (jamais le code en clair en base). `otp_valide` : True une fois le bon
    # code saisi (débloque la signature). Tout est journalisé dans les preuves
    # (pattern QJ10) via `DocumentActivity`/preuves existantes.
    auth_extra = models.CharField(
        max_length=10, choices=ROLE_AUTH_EXTRA_CHOICES,
        blank=True, default='', verbose_name='authentification extra (effective)')
    otp_code_hash = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='hash du code OTP (SHA-256)')
    otp_expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name='code OTP expire le')
    otp_essais = models.PositiveIntegerField(
        default=0, verbose_name="essais de code OTP")
    otp_valide = models.BooleanField(
        default=False, verbose_name='authentification extra validée')
    otp_valide_le = models.DateTimeField(
        null=True, blank=True, verbose_name='authentification extra validée le')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['demande', 'ordre', 'id']
        verbose_name = 'Signataire de demande'
        verbose_name_plural = 'Signataires de demande'
        indexes = [
            models.Index(fields=['company', 'demande'],
                         name='ged_signataire_co_dem_idx'),
            models.Index(fields=['demande', 'ordre'],
                         name='ged_signataire_dem_ordre_idx'),
            models.Index(fields=['company', 'statut'],
                         name='ged_signataire_co_statut_idx'),
        ]

    @property
    def is_actionnable(self):
        """True si CE destinataire peut actuellement signer/refuser (a été
        notifié et n'a pas encore agi)."""
        return self.statut in (SIGNATAIRE_EN_ATTENTE, SIGNATAIRE_NOTIFIE) \
            and self.role == ROLE_SIGNATAIRE

    @property
    def auth_extra_effective(self):
        """ZGED2 — Mode d'authentification extra EFFECTIF de ce destinataire.

        `self.auth_extra` (posé explicitement sur ce destinataire) prime ;
        sinon hérite du `role_signataire.auth_extra` (ZGED1) s'il y en a un ;
        sinon « aucune » (comportement XGED1 inchangé — simple consentement +
        signature)."""
        if self.auth_extra:
            return self.auth_extra
        if self.role_signataire_id:
            return self.role_signataire.auth_extra
        return ROLE_AUTH_EXTRA_AUCUNE

    @property
    def otp_requis_et_non_valide(self):
        """ZGED2 — True si une authentification extra est requise pour CE
        destinataire et n'a pas encore été validée (bloque la signature)."""
        return self.auth_extra_effective != ROLE_AUTH_EXTRA_AUCUNE \
            and not self.otp_valide

    def __str__(self):
        return f'{self.nom} (#{self.ordre}) → {self.demande_id} ({self.statut})'


# XGED3 — Zones de champs positionnées sur le PDF à signer.
CHAMP_TYPE_SIGNATURE = 'signature'
CHAMP_TYPE_INITIALES = 'initiales'
CHAMP_TYPE_DATE = 'date'
CHAMP_TYPE_TEXTE = 'texte'
CHAMP_TYPE_CASE = 'case'

CHAMP_TYPE_CHOICES = [
    (CHAMP_TYPE_SIGNATURE, 'Signature'),
    (CHAMP_TYPE_INITIALES, 'Initiales'),
    (CHAMP_TYPE_DATE, 'Date'),
    (CHAMP_TYPE_TEXTE, 'Texte'),
    (CHAMP_TYPE_CASE, 'Case à cocher'),
]


class ChampSignature(models.Model):
    """XGED3 — Zone de champ positionnée sur le PDF à signer.

    Rattaché À EXACTEMENT UNE des deux cibles (jamais les deux, jamais aucune
    — garde `clean()` + contrainte base) : une `demande` de signature EN COURS
    (positionnement ad-hoc pour cette cérémonie) OU un `ModeleDocument`
    (GED27, positionnement RÉUTILISABLE — le champ se recopie à chaque demande
    générée depuis ce modèle).

    Position en POURCENTAGE de la page (`x`/`y`/`largeur`/`hauteur`, 0-100) —
    indépendant de la résolution/taille du PDF rendu, ce qui permet un rendu
    identique sur l'aperçu web (mobile-first) et le PDF final aplati. `page`
    est l'index 0-based de la page portant le champ. `role` cible le
    destinataire concerné (nom libre — aligné sur `SignataireDemande.nom` ou
    `SignataireDemande.role` selon l'usage ; laissé libre pour rester
    utilisable sur un `ModeleDocument` qui n'a pas encore de destinataires
    concrets). `requis` bloque la complétion tant que non rempli ; un champ
    optionnel peut être laissé vide.

    Multi-tenant : `company` posée CÔTÉ SERVEUR (cohérente avec la cible) —
    jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_champs_signature')
    demande = models.ForeignKey(
        DemandeSignatureDocument, on_delete=models.CASCADE,
        null=True, blank=True, related_name='champs')
    modele = models.ForeignKey(
        'ModeleDocument', on_delete=models.CASCADE,
        null=True, blank=True, related_name='champs_signature')
    type_champ = models.CharField(
        max_length=12, choices=CHAMP_TYPE_CHOICES,
        default=CHAMP_TYPE_SIGNATURE, verbose_name='type de champ')
    page = models.PositiveIntegerField(default=0, verbose_name='page (0-based)')
    # Position/taille en POURCENTAGE de la page (0-100) — résolution-indépendant.
    x = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    y = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    largeur = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    hauteur = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    # Destinataire concerné — nom/role libre (aligné XGED2 `SignataireDemande`
    # sans FK dure : un champ sur un `ModeleDocument` n'a pas encore de
    # destinataire concret tant qu'aucune demande n'en est générée).
    role = models.CharField(max_length=100, blank=True, default='')
    requis = models.BooleanField(default=True, verbose_name='requis')
    # Valeur remplie par le signataire (texte/case/date) — vide pour les
    # champs `signature`/`initiales` (qui utilisent la signature de la
    # cérémonie elle-même, tapée/tracée, jamais stockée deux fois ici).
    valeur = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['page', 'y', 'x', 'id']
        verbose_name = 'Champ de signature'
        verbose_name_plural = 'Champs de signature'
        indexes = [
            models.Index(fields=['company', 'demande'],
                         name='ged_champ_co_demande_idx'),
            models.Index(fields=['company', 'modele'],
                         name='ged_champ_co_modele_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(demande__isnull=False, modele__isnull=True)
                    | models.Q(demande__isnull=True, modele__isnull=False)
                ),
                name='ged_champ_exactly_one_target',
            ),
        ]

    def clean(self):
        """Garantit cible exactement-une (demande XOR modèle)."""
        from django.core.exceptions import ValidationError
        if bool(self.demande_id) == bool(self.modele_id):
            raise ValidationError(
                "Un champ de signature cible exactement une demande OU un "
                "modèle de document.")

    def __str__(self):
        cible = self.demande_id or self.modele_id
        return f'Champ {self.type_champ} p{self.page} → {cible}'


class ModeleDocument(models.Model):
    """GED27 — Modèle de document avec fusion/mailing (corps → PDF WeasyPrint).

    Un modèle stocke un CORPS HTML (`corps_html`) contenant des champs de fusion
    de la forme ``{{ placeholder }}`` (ex. « Cher {{ nom }}, … »). Fusionné avec
    un dictionnaire de données fourni, il rend un document final puis un PDF via
    WeasyPrint (rendu direct dans `services.rendre_modele`). C'est une couche
    GÉNÉRIQUE pour les documents INTERNES/administratifs (attestations, courriers,
    mailing) — elle est SÉPARÉE et DISTINCTE du chemin `/proposal` (rule #4), qui
    reste l'UNIQUE chemin des PDF de DEVIS client : un modèle GED27 ne produit
    JAMAIS un PDF de devis et ne route jamais par le moteur premium.

    SÉCURITÉ DE FUSION : la substitution des jetons utilise le moteur de gabarit
    Django dans un CONTEXTE EXPLICITE et borné (`services.rendre_modele`) — jamais
    d'``eval``/exécution de code arbitraire. Les jetons inconnus sont rendus vides
    (comportement standard du moteur), jamais une fuite d'objet Python.

    Multi-tenant : `company` posée CÔTÉ SERVEUR (jamais lue du corps de requête) ;
    toutes les requêtes bornées à la société. `categorie` est une étiquette libre
    de classement (ex. « attestation », « courrier ») — purement informative,
    sans rapport avec le funnel commercial `STAGES.py` (rule #2). `actif` permet
    de désactiver un modèle sans le supprimer.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_modeles_document')
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    # Étiquette libre de classement (ex. « attestation », « courrier »,
    # « mailing »). Purement informative — jamais un statut de pipeline.
    categorie = models.CharField(
        max_length=80, blank=True, default='', verbose_name='catégorie')
    # Corps HTML du modèle avec des champs de fusion ``{{ placeholder }}``.
    # Fusionné côté serveur via le moteur de gabarit Django (contexte borné).
    corps_html = models.TextField(
        blank=True, default='', verbose_name='corps HTML (avec {{ champs }})')
    # GED28 — Classement automatique : où DÉPOSER le document généré.
    # `cabinet_cible` = nom du cabinet de destination (auto-créé si absent) ;
    # `dossier_cible` = nom du dossier racine de destination, qui peut porter des
    # jetons ``{{ champ }}`` résolus depuis le CONTEXTE de fusion (ex.
    # « Attestations {{ annee }} ») — permettant de router par année/client. Vide
    # = comportement rétro-compatible (le dossier par défaut de l'appelant).
    # Purement un classement documentaire interne — sans rapport avec le funnel
    # commercial `STAGES.py` (rule #2).
    cabinet_cible = models.CharField(
        max_length=120, blank=True, default='Documents',
        verbose_name='cabinet de classement')
    dossier_cible = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='dossier de classement (avec {{ champs }})')
    actif = models.BooleanField(default=True, verbose_name='actif')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_modeles_document_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Modèle de document'
        verbose_name_plural = 'Modèles de document'
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='ged_modele_co_actif_idx'),
        ]

    def __str__(self):
        return self.nom


# GED35 — Journal d'audit d'accès aux documents (lectures).
#
# Trace chaque ACCÈS EN LECTURE à un document (aperçu inline GED14, téléchargement
# public tokenisé GED20, consultation). Append-only par convention : on n'expose
# ni update ni delete via l'API (lecture seule côté viewset). Multi-tenant :
# `company` posée CÔTÉ SERVEUR (jamais lue du corps), bornée à la société du
# document. Couche LOCALE à la GED — sans rapport avec le funnel `STAGES.py`.
ACCES_APERCU = 'apercu'          # aperçu inline authentifié (GED14)
ACCES_TELECHARGEMENT = 'telechargement'  # téléchargement (proxy)
ACCES_PUBLIC = 'public'          # accès via lien public tokenisé (GED20)
ACCES_CONSULTATION = 'consultation'      # ouverture de la fiche document

ACCES_TYPE_CHOICES = [
    (ACCES_APERCU, 'Aperçu'),
    (ACCES_TELECHARGEMENT, 'Téléchargement'),
    (ACCES_PUBLIC, 'Accès public (lien)'),
    (ACCES_CONSULTATION, 'Consultation'),
]


class JournalAcces(models.Model):
    """GED35 — Entrée d'audit d'un accès EN LECTURE à un document.

    Enregistre QUI (utilisateur, NULL pour un accès public anonyme), QUAND, QUEL
    document, et SOUS QUELLE forme (aperçu / téléchargement / public /
    consultation). Append-only : aucune mise à jour ni suppression via l'API.
    Multi-tenant : `company` posée côté serveur (cohérente avec celle du
    document) — jamais lue du corps de requête."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_journaux_acces')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='acces')
    # NULL = accès PUBLIC anonyme (lien tokenisé GED20) — pas d'utilisateur connu.
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_acces_documents',
        verbose_name='utilisateur')
    type_acces = models.CharField(
        max_length=14, choices=ACCES_TYPE_CHOICES, default=ACCES_CONSULTATION,
        verbose_name="type d'accès")
    # Métadonnées best-effort (jamais sensibles) : IP tronquée / user-agent court.
    adresse_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='adresse IP')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Accès au document (audit)"
        verbose_name_plural = "Journal d'accès aux documents"
        indexes = [
            models.Index(fields=['company', 'document'],
                         name='ged_acces_co_doc_idx'),
            models.Index(fields=['company', 'created_at'],
                         name='ged_acces_co_date_idx'),
        ]

    def __str__(self):
        return f'{self.type_acces} #{self.document_id} @ {self.created_at}'


class QuotaStockage(models.Model):
    """GED36 — Quota de stockage documentaire d'une société (octets).

    UNE entrée par société (OneToOne) fixe la capacité de stockage allouée
    (`quota_octets` ; 0 = illimité). L'usage courant n'est PAS stocké ici (il est
    calculé à la volée par `services.usage_stockage_octets` en sommant la taille
    des versions de la société) — on évite un compteur dénormalisé qui dériverait.
    Multi-tenant : `company` posée CÔTÉ SERVEUR (jamais lue du corps). Le quota
    est CONSULTATIF par défaut (l'application le LIT pour bloquer un dépôt qui
    dépasserait) — jamais une suppression automatique. Sans entrée explicite, le
    défaut `settings.GED_QUOTA_DEFAUT_OCTETS` s'applique (0 = illimité)."""
    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_quota_stockage')
    # Capacité allouée en octets. 0 = illimité (aucun plafond appliqué).
    quota_octets = models.BigIntegerField(
        default=0, verbose_name='quota (octets, 0 = illimité)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Quota de stockage GED'
        verbose_name_plural = 'Quotas de stockage GED'

    def __str__(self):
        return f'Quota {self.company_id}: {self.quota_octets} o'


class DepotPublic(models.Model):
    """XGED7 — Lien public de DÉPÔT (upload-request) tokenisé.

    Symétrique de `PartageGed` (GED20, téléchargement) mais dans l'autre sens :
    un tiers SANS LOGIN peut UNIQUEMENT téléverser des fichiers dans un dossier
    cible, sans jamais voir le contenu déjà présent. `token` est l'UNIQUE secret
    d'accès (même générateur que GED20/XGED1). Chaque dépôt crée un `Document`
    (traçant l'uploader anonyme par nom/email saisis dans `custom_data`), incrémente
    `depots_effectues`, et respecte la validation type/taille existante
    (`records.storage.store_attachment`).

    Company posée côté serveur (cohérente avec `folder`) — jamais lue du corps
    de requête. `created_by` posé côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_depots_publics')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, related_name='depots_publics')
    token = models.CharField(
        max_length=64, unique=True, default=_default_partage_token,
        editable=False)
    message = models.TextField(
        blank=True, default='', verbose_name="message d'instruction")
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="expire le")
    # Quotas optionnels (NULL = illimité). Posés côté serveur.
    quota_fichiers = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="quota de fichiers")
    quota_octets = models.BigIntegerField(
        null=True, blank=True, verbose_name="quota d'octets cumulés")
    depots_effectues = models.PositiveIntegerField(
        default=0, verbose_name="fichiers déposés")
    octets_deposes = models.BigIntegerField(
        default=0, verbose_name="octets déposés")
    actif = models.BooleanField(default=True, verbose_name="actif")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_depots_publics_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Lien de dépôt public'
        verbose_name_plural = 'Liens de dépôt public'
        indexes = [
            models.Index(fields=['company', 'folder'],
                         name='ged_depot_co_folder_idx'),
        ]

    def __str__(self):
        return f'Dépôt {self.token[:8]}… → {self.folder_id}'

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def quota_fichiers_exhausted(self):
        return (self.quota_fichiers is not None
                and self.depots_effectues >= self.quota_fichiers)

    @property
    def quota_octets_exhausted(self):
        return (self.quota_octets is not None
                and self.octets_deposes >= self.quota_octets)

    @property
    def is_accessible(self):
        """True si le lien accepte encore des dépôts (actif, non expiré, quotas
        non épuisés). Un lien plein/expiré/révoqué renvoie 410 côté vue."""
        return (self.actif and not self.is_expired
                and not self.quota_fichiers_exhausted
                and not self.quota_octets_exhausted)


class ExigenceDossier(models.Model):
    """XGED8 — Modèle de checklist de pièces requises (par société).

    Décrit un type de pièce attendue dans un dossier (libellé libre, ex.
    « CIN », « Attestation CNSS », « Visite médicale ») — soit rattaché à un
    dossier précis (`folder`), soit générique (applicable à un cabinet entier
    via `cabinet`, `folder` NULL). Company posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_exigences')
    cabinet = models.ForeignKey(
        Cabinet, on_delete=models.CASCADE, null=True, blank=True,
        related_name='exigences')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True,
        related_name='exigences')
    libelle = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    obligatoire = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_exigences_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['libelle', 'id']
        verbose_name = 'Exigence de dossier'
        verbose_name_plural = 'Exigences de dossier'
        indexes = [
            models.Index(fields=['company', 'folder'],
                         name='ged_exig_co_folder_idx'),
            models.Index(fields=['company', 'cabinet'],
                         name='ged_exig_co_cabinet_idx'),
        ]

    def __str__(self):
        return self.libelle


DEMANDE_DOC_EN_ATTENTE = 'en_attente'
DEMANDE_DOC_SOLDEE = 'soldee'
DEMANDE_DOC_ANNULEE = 'annulee'
DEMANDE_DOC_CHOICES = [
    (DEMANDE_DOC_EN_ATTENTE, 'En attente'),
    (DEMANDE_DOC_SOLDEE, 'Soldée'),
    (DEMANDE_DOC_ANNULEE, 'Annulée'),
]


class DemandeDocument(models.Model):
    """XGED8 — Demande d'une pièce nommée (interne OU contact externe).

    Le destinataire est soit un `utilisateur` interne (ex. un employé pour son
    dossier RH), soit un contact externe désigné par `destinataire_email`/
    `destinataire_nom` (le dépôt externe passe par un `DepotPublic`, XGED7). Un
    placeholder est visible dans le dossier tant que `statut` reste
    `en_attente` ; il se solde AUTOMATIQUEMENT (`statut = soldee`,
    `document` renseigné) quand un dépôt correspondant arrive — matching par
    `folder` + `exigence` (voir `services.matcher_depot_demandes`).

    Company posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_demandes_document')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, related_name='demandes_document')
    exigence = models.ForeignKey(
        ExigenceDossier, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='demandes')
    libelle = models.CharField(max_length=200)
    # Destinataire interne (optionnel) — exclusif en pratique avec l'externe,
    # mais non forcé au niveau modèle (un rappel peut viser les deux canaux).
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_demandes_document_recues')
    destinataire_nom = models.CharField(max_length=200, blank=True, default='')
    destinataire_email = models.EmailField(blank=True, default='')
    echeance = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=10, choices=DEMANDE_DOC_CHOICES,
        default=DEMANDE_DOC_EN_ATTENTE)
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='demandes_soldees')
    derniere_relance_le = models.DateTimeField(null=True, blank=True)
    nombre_relances = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_demandes_document_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Demande de document'
        verbose_name_plural = 'Demandes de document'
        indexes = [
            models.Index(fields=['company', 'folder'],
                         name='ged_ddoc_co_folder_idx'),
            models.Index(fields=['company', 'statut'],
                         name='ged_ddoc_co_statut_idx'),
        ]

    @property
    def is_pending(self):
        return self.statut == DEMANDE_DOC_EN_ATTENTE

    def __str__(self):
        return f'{self.libelle} ({self.statut})'


class ValidationOcrDocument(models.Model):
    """XGED13 — File de validation d'extraction OCR (score de confiance).

    Quand l'extraction OCR/IA d'un document produit un score de confiance sous
    le seuil configuré, le document entre dans cette file (`statut =
    a_valider`) : un écran dédié permet de corriger les champs avant de les
    appliquer définitivement. `champs_extraits` porte les valeurs brutes
    proposées (JSON, jamais appliquées telles quelles à `Document.custom_data`
    avant validation). Company posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_validations_ocr')
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name='validation_ocr')
    score_confiance = models.FloatField(default=0.0)
    champs_extraits = models.JSONField(null=True, blank=True, default=dict)
    valide = models.BooleanField(default=False)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_validations_ocr_faites')
    valide_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Validation OCR'
        verbose_name_plural = 'Validations OCR'
        indexes = [
            models.Index(fields=['company', 'valide'],
                         name='ged_valocr_co_valide_idx'),
        ]

    def __str__(self):
        return f'Validation OCR #{self.document_id} ({self.score_confiance:.2f})'


ANNOTATION_TYPE_NOTE = 'note'
ANNOTATION_TYPE_SURLIGNAGE = 'surlignage'
ANNOTATION_TYPE_TAMPON = 'tampon'
ANNOTATION_TYPE_CHOICES = [
    (ANNOTATION_TYPE_NOTE, 'Note'),
    (ANNOTATION_TYPE_SURLIGNAGE, 'Surlignage'),
    (ANNOTATION_TYPE_TAMPON, 'Tampon'),
]


class AnnotationDocument(models.Model):
    """XGED16 — Annotation/tampon sur l'image d'une version (couche séparée).

    Vit en base, superposée dans l'aperçu côté frontend — le fichier original
    (`DocumentVersion`) n'est JAMAIS modifié. `page` (0-based) + coordonnées en
    POURCENTAGE (`x`, `y` : 0-100, indépendantes de la résolution de rendu).
    `contenu` porte le texte de la note ou le libellé du tampon (ex. « Payé »).
    Company + auteur posés côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_annotations')
    version = models.ForeignKey(
        DocumentVersion, on_delete=models.CASCADE, related_name='annotations')
    type_annotation = models.CharField(
        max_length=12, choices=ANNOTATION_TYPE_CHOICES,
        default=ANNOTATION_TYPE_NOTE)
    page = models.PositiveIntegerField(default=0)
    x = models.FloatField(default=0.0)
    y = models.FloatField(default=0.0)
    contenu = models.CharField(max_length=500, blank=True, default='')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_annotations_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['page', 'created_at', 'id']
        verbose_name = 'Annotation de document'
        verbose_name_plural = 'Annotations de document'
        indexes = [
            models.Index(fields=['company', 'version'],
                         name='ged_annot_co_version_idx'),
        ]

    def __str__(self):
        return f'{self.type_annotation} p{self.page} @ {self.version_id}'


class TamponSociete(models.Model):
    """XGED16 — Tampon prédéfini par société (en plus des 3 tampons système).

    Les tampons système (« Payé », « Validé », « Confidentiel ») sont une
    constante applicative (`TAMPONS_SYSTEME`, ci-dessous) ; ce modèle permet à
    une société d'ajouter SES propres libellés. Company posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_tampons')
    libelle = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['libelle', 'id']
        unique_together = [('company', 'libelle')]
        verbose_name = 'Tampon (société)'
        verbose_name_plural = 'Tampons (société)'

    def __str__(self):
        return self.libelle


# XGED16 — tampons système offerts à toutes les sociétés (constante, pas de table).
TAMPONS_SYSTEME = ['Payé', 'Validé', 'Confidentiel']


class RegleDossier(models.Model):
    """XGED19 — Règle d'action automatique à l'upload dans un dossier.

    Déclenchée à la création d'un `Document` dans `folder` : si
    `condition_group` (format `core.rules`, JSON groupe ET/OU/NON validé côté
    serveur — JAMAIS d'exécution de code) s'évalue vrai contre les métadonnées
    du document nouvellement créé, les `actions` (liste ordonnée de
    `{type, params}`) s'exécutent EN SÉQUENCE, best-effort (une action en échec
    est journalisée sans jamais faire échouer l'upload lui-même). Company posée
    côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_regles_dossier')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, related_name='regles')
    nom = models.CharField(max_length=200)
    condition_group = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    actif = models.BooleanField(default=True)
    ordre = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_regles_dossier_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Règle de dossier'
        verbose_name_plural = 'Règles de dossier'
        indexes = [
            models.Index(fields=['company', 'folder', 'actif'],
                         name='ged_regle_co_folder_idx'),
        ]

    def __str__(self):
        return self.nom


class ExecutionRegleDossier(models.Model):
    """XGED19 — Journal d'exécution d'une `RegleDossier` sur un document.

    Une ligne par exécution (déclenchée à l'upload) ; `resultats` porte le
    détail par action (`ok`/erreur) — jamais tout-ou-rien silencieux."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_executions_regle')
    regle = models.ForeignKey(
        RegleDossier, on_delete=models.CASCADE, related_name='executions')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='executions_regle')
    declenchee = models.BooleanField(default=False)
    resultats = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Exécution de règle de dossier"
        verbose_name_plural = "Exécutions de règle de dossier"
        indexes = [
            models.Index(fields=['company', 'regle'],
                         name='ged_execregle_co_regle_idx'),
        ]

    def __str__(self):
        return f'Exécution règle #{self.regle_id} @ doc #{self.document_id}'


class RegleApprobationGed(models.Model):
    """XGED20 — Routage conditionnel des approbations par métadonnées.

    Étend GED18 (`DemandeApprobation`) : au lieu d'un approbateur unique fixe,
    `request_review` consulte la règle la plus SPÉCIFIQUE (plus haute
    `priorite`, puis id le plus récent) dont `condition_group` (format
    `core.rules`) s'évalue vrai contre les métadonnées du document, et
    instancie une chaîne SÉQUENTIELLE d'approbateurs (`approbateurs`, liste
    ordonnée d'ids utilisateur — résolue/validée côté serveur, bornée à la
    société). RÉTROCOMPATIBLE : aucune règle applicable ⇒ comportement GED18
    inchangé (approbateur unique fixe, ou aucun). Company posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_regles_approbation')
    libelle = models.CharField(max_length=200)
    condition_group = models.JSONField(default=dict, blank=True)
    # Chaîne séquentielle d'ids utilisateur (ordre = ordre d'approbation).
    approbateurs = models.JSONField(default=list, blank=True)
    priorite = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_regles_approbation_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priorite', '-id']
        verbose_name = "Règle d'approbation GED"
        verbose_name_plural = "Règles d'approbation GED"
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='ged_regleapp_co_actif_idx'),
        ]

    def __str__(self):
        return self.libelle


class ChaineApprobationGed(models.Model):
    """XGED20 — Instance de chaîne séquentielle résolue pour une demande.

    Rattachée 1:1 à une `DemandeApprobation` (GED18) quand une `RegleApprobationGed`
    s'est appliquée. `etapes` porte la liste ordonnée `[{approbateur_id, statut,
    decision_le}]` — la demande GED18 elle-même reste la source de vérité du
    statut global (`en_attente`/`approuve`/`rejete`) ; cette table détaille les
    étapes intermédiaires du parcours séquentiel."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_chaines_approbation')
    demande = models.OneToOneField(
        DemandeApprobation, on_delete=models.CASCADE,
        related_name='chaine_approbation')
    regle = models.ForeignKey(
        RegleApprobationGed, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chaines')
    etapes = models.JSONField(default=list, blank=True)
    etape_courante = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chaîne d'approbation GED"
        verbose_name_plural = "Chaînes d'approbation GED"

    def __str__(self):
        return f'Chaîne #{self.demande_id}'


class DocumentActivity(models.Model):
    """XGED15 — Journal automatique des événements majeurs GED (pattern
    `crm.LeadActivity`). Complète `JournalAcces` (GED35, lectures) SANS le
    remplacer : ceci trace les événements de CYCLE DE VIE (nouvelle version,
    changement de statut, partage créé, signature) — jamais de lecture simple.
    Auteur et société toujours posés côté serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_document_activities')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='activities')
    type_evenement = models.CharField(max_length=40)
    message = models.CharField(max_length=500, blank=True, default='')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_document_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Activité de document (journal)'
        verbose_name_plural = 'Activités de document (journal)'
        indexes = [
            models.Index(fields=['company', 'document'],
                         name='ged_docact_co_doc_idx'),
        ]

    def __str__(self):
        return f'{self.type_evenement} @ {self.document_id}'


class PlanificationDocument(models.Model):
    """XGED15 — Activité planifiée sur un document (« relancer le J+7 »).

    Volontairement LOCALE à la GED (plutôt que de forcer `records.Activity`
    générique dont le registre de cibles/serializer est pensé pour les objets
    métier CRM/ventes) : porte une échéance + un assigné, notifié à échéance
    via `notifications.notify` (best-effort). Company + créateur posés côté
    serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_planifications')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='planifications')
    libelle = models.CharField(max_length=200)
    echeance = models.DateField()
    assigne_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_planifications_assignees')
    faite = models.BooleanField(default=False)
    notifiee = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_planifications_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['echeance', 'id']
        verbose_name = 'Planification de document'
        verbose_name_plural = 'Planifications de document'
        indexes = [
            models.Index(fields=['company', 'echeance', 'faite'],
                         name='ged_plandoc_co_echeance_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.echeance})'


class RegleAclMetadonnee(models.Model):
    """XGED21 — ACL automatique pilotée par métadonnées (couche dynamique).

    Étend GED19 (`AclGed`) sans matérialiser de lignes : une règle décrit une
    CONDITION (`condition_group`, format `core.rules` — groupe ET/OU/NON validé
    côté serveur, jamais d'exécution de code) évaluée contre les métadonnées
    d'un document (tags/type/custom_data — même contexte que `RegleDossier`
    XGED19 via `_document_contexte_regle`) et un `niveau` d'accès octroyé à un
    `role` UNIQUEMENT (jamais un utilisateur nommé — la règle cible une
    population, pas un individu) SI la condition matche.

    `selectors.acl_effective` (GED19) consulte ces règles APRÈS les entrées
    `AclGed` matérialisées : si une règle matche pour le rôle de l'utilisateur,
    son niveau participe à la résolution du meilleur rang au même titre qu'une
    entrée directe sur le document (recalcul IMMÉDIAT à chaque lecture — poser
    ou retirer un tag change l'accès sans aucune ligne à mettre à jour).
    L'admin/superuser reste TOUJOURS non affecté (contournement GED19 déjà
    inconditionnel). RÉTROCOMPATIBLE : aucune règle active ⇒ comportement
    GED19 strictement inchangé.

    Company posée côté serveur. Couche LOCALE à la GED (séparée du funnel
    commercial STAGES.py, rule #2).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_regles_acl_metadonnee')
    nom = models.CharField(max_length=200)
    condition_group = models.JSONField(default=dict, blank=True)
    role = models.ForeignKey(
        'roles.Role', on_delete=models.CASCADE,
        related_name='ged_regles_acl_metadonnee',
        verbose_name='rôle')
    niveau = models.CharField(
        max_length=8, choices=ACL_CHOICES, default=ACL_LECTURE,
        verbose_name="niveau d'accès")
    priorite = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ged_regles_acl_metadonnee_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priorite', '-id']
        verbose_name = 'Règle ACL par métadonnée'
        verbose_name_plural = 'Règles ACL par métadonnée'
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='ged_reglecl_co_actif_idx'),
            models.Index(fields=['role'], name='ged_reglecl_role_idx'),
        ]

    def __str__(self):
        return self.nom


# ── XGED23 — Disposition fin de rétention (revue humaine + certificat) ──────

DISPOSITION_EN_ATTENTE = 'en_attente'
DISPOSITION_APPROUVEE = 'approuvee'
DISPOSITION_REJETEE = 'rejetee'
DISPOSITION_EXECUTEE = 'executee'

DISPOSITION_STATUT_CHOICES = [
    (DISPOSITION_EN_ATTENTE, 'En attente'),
    (DISPOSITION_APPROUVEE, 'Approuvée'),
    (DISPOSITION_REJETEE, 'Rejetée'),
    (DISPOSITION_EXECUTEE, 'Exécutée'),
]

DISPOSITION_ACTION_DETRUIRE = 'detruire'
DISPOSITION_ACTION_ARCHIVER = 'archiver'

DISPOSITION_ACTION_CHOICES = [
    (DISPOSITION_ACTION_DETRUIRE, 'Détruire'),
    (DISPOSITION_ACTION_ARCHIVER, 'Archiver'),
]


class DemandeDispositionError(Exception):
    """XGED23 — Levée quand une opération de disposition est invalide (déjà
    décidée, document sous legal hold…). Traduite en 400/403 côté vue."""


class DemandeDisposition(models.Model):
    """XGED23 — Revue humaine entre l'échéance de rétention (GED22) et la
    purge (GED25).

    Regroupe un LOT de documents ÉCHUS (`selectors.documents_echus`)
    proposés à disposition (destruction ou archivage) et les fait passer par
    un circuit approuver/rejeter — RÉUTILISE le pattern `DemandeApprobation`
    (GED18) : un `demandeur` propose, un `approbateur` décide. L'EXÉCUTION
    (après approbation) produit un `CertificatDestruction` immuable par
    document réellement détruit ; le rejet CONSERVE tous les documents du
    lot (aucun effacement). Les documents sous `LegalHold` (GED24) ACTIF sont
    exclus D'OFFICE du lot à la création (jamais proposés à destruction).

    `documents` porte la liste des ids de documents proposés (résolue et
    bornée à la société à la création — jamais lue telle quelle du corps de
    requête sans validation). Company/demandeur posés côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_demandes_disposition')
    libelle = models.CharField(max_length=200)
    action = models.CharField(
        max_length=10, choices=DISPOSITION_ACTION_CHOICES,
        default=DISPOSITION_ACTION_DETRUIRE)
    documents = models.JSONField(
        default=list, blank=True,
        verbose_name='ids des documents proposés')
    statut = models.CharField(
        max_length=10, choices=DISPOSITION_STATUT_CHOICES,
        default=DISPOSITION_EN_ATTENTE)
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ged_demandes_disposition_emises')
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ged_demandes_disposition_recues')
    commentaire = models.TextField(blank=True, default='')
    decision_le = models.DateTimeField(
        null=True, blank=True, verbose_name='décidée le')
    executee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='exécutée le')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Demande de disposition'
        verbose_name_plural = 'Demandes de disposition'
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ged_dispo_co_statut_idx'),
        ]

    @property
    def is_pending(self):
        return self.statut == DISPOSITION_EN_ATTENTE

    def __str__(self):
        return f'Disposition {self.libelle} ({self.statut})'


class CertificatDestruction(models.Model):
    """XGED23 — Certificat IMMUABLE de destruction d'un document (write-once,
    pattern `ArchivageLegal` GED23).

    Émis à L'EXÉCUTION d'une `DemandeDisposition` approuvée, un par document
    réellement détruit : trace QUOI (référence document — le document lui-même
    est déjà supprimé à ce stade, on n'en garde que le libellé/l'id d'origine),
    QUAND, PAR QUI (l'exécutant, posé côté serveur), la POLITIQUE appliquée
    (libellé de la `PolitiqueRetention` GED22 résolue) et le HASH des
    métadonnées détruites (SHA-256 hexadécimal — preuve que CES métadonnées
    précises ont bien été celles détruites, sans conserver le contenu). Classé
    en GED via un `Document` de type texte généré à la volée par l'appelant
    (hors modèle — cette table ne fait que porter la preuve structurée).

    Write-once : `save()` refuse toute mise à jour, `delete()` toute
    suppression (même motif qu'`ArchivageLegal`). Company posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_certificats_destruction')
    demande = models.ForeignKey(
        DemandeDisposition, on_delete=models.CASCADE,
        related_name='certificats')
    document_id_origine = models.PositiveBigIntegerField(
        verbose_name="id d'origine du document détruit")
    document_nom = models.CharField(max_length=255)
    politique_appliquee = models.CharField(max_length=255, blank=True, default='')
    hash_metadonnees = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='hash des métadonnées détruites (SHA-256)')
    detruit_le = models.DateTimeField(auto_now_add=True)
    detruit_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ged_certificats_destruction_emis')

    class Meta:
        ordering = ['-detruit_le', '-id']
        verbose_name = 'Certificat de destruction'
        verbose_name_plural = 'Certificats de destruction'
        indexes = [
            models.Index(fields=['company', 'demande'],
                         name='ged_certif_co_demande_idx'),
        ]

    def save(self, *args, **kwargs):
        """XGED23 — Création SEULE : refuse toute mise à jour (immuable),
        même motif qu'`ArchivageLegal.save`."""
        if self.pk is not None:
            raise DemandeDispositionError(
                "Un certificat de destruction est immuable (création seule) : "
                "il ne peut pas être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """XGED23 — Refuse la suppression d'un certificat (immuable)."""
        raise DemandeDispositionError(
            "Un certificat de destruction est immuable : il ne peut pas être "
            "supprimé.")

    def __str__(self):
        return f'Certificat destruction — {self.document_nom} ({self.detruit_le:%Y-%m-%d})'


# ── XGED27 — Envoi en masse de demandes de signature ────────────────────────

class LotEnvoi(models.Model):
    """XGED27 — Suivi GROUPÉ d'un envoi en masse de demandes de signature.

    Un `ModeleDocument` (GED27) fusionné avec N destinataires (CSV nom/email/
    champs de fusion, ou une sélection de clients CRM via `crm.selectors` —
    cross-app en LECTURE SEULE, jamais d'import de `crm.models`) produit UN
    document personnalisé PAR destinataire + SA demande de signature
    individuelle (XGED1/2) ; ce lot les regroupe pour un suivi consolidé
    (compteurs envoyé/vu/signé/refusé). Cas d'usage : renouvellements annuels
    de contrats de maintenance.

    `resultats` porte le détail par ligne (succès avec l'id de la
    `DemandeSignatureDocument` créée, ou erreur — jamais tout-ou-rien : une
    ligne en échec ne bloque jamais les autres). Company/créateur posés côté
    serveur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ged_lots_envoi')
    modele = models.ForeignKey(
        ModeleDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lots_envoi')
    libelle = models.CharField(max_length=200)
    resultats = models.JSONField(default=list, blank=True)
    total = models.PositiveIntegerField(default=0)
    nb_envoyes = models.PositiveIntegerField(default=0)
    nb_vus = models.PositiveIntegerField(default=0)
    nb_signes = models.PositiveIntegerField(default=0)
    nb_refuses = models.PositiveIntegerField(default=0)
    nb_erreurs = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_lots_envoi_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Lot d'envoi de signature"
        verbose_name_plural = "Lots d'envoi de signature"
        indexes = [
            models.Index(fields=['company', 'created_at'],
                         name='ged_lotenvoi_co_created_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.nb_envoyes}/{self.total})'
