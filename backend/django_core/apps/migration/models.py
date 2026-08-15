"""Modèles du groupe NTMIG — projets de migration ERP sortants.

Trois modèles :

* :class:`ProjetMigration` — le conteneur d'une migration (une source, N lots
  d'entités).
* :class:`LotMigration` — un lot par entité (clients, produits, devis…) ; le
  chargement effectif est DÉLÉGUÉ à ``apps.dataimport`` (traçabilité par FK
  CHAÎNE ``import_job`` vers ``dataimport.ImportJob``, jamais un import
  parallèle ni un second journal).
* :class:`RapportReconciliation` — LE différenciateur : comptages et totaux
  financiers source vs cible ; un lot ne passe jamais « réconcilié » sans un
  rapport ``conforme=True`` ou une dérogation motivée (NTMIG5).
* :class:`PlaybookInstance` (NTMIG22) — l'instanciation d'un playbook kb
  (NTMIG21) pour UN déploiement client : l'intégrateur coche les étapes,
  la progression persiste.
* :class:`DeploiementPartenaire` (NTMIG28) — qui a déployé quoi, chez quel
  client final ; source du scoring de certification (NTMIG27).

Multi-société : tout hérite de ``core.models.TenantModel`` (FK ``company`` +
horodatage). Les FK vers d'autres apps sont des références par CHAÎNE
(``'dataimport.ImportJob'``), jamais un import direct de leurs modèles.
Aucune écriture SQL vers Odoo (règle #1).
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TenantModel


class ProjetMigration(TenantModel):
    """Conteneur d'une migration : une source, N lots d'entités."""

    class Source(models.TextChoices):
        ODOO = 'odoo', 'Odoo'
        SAGE = 'sage', 'Sage'
        EXCEL = 'excel', 'Excel'
        CSV_GENERIQUE = 'csv_generique', 'CSV générique'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ANALYSE = 'analyse', 'Analyse'
        CHARGEMENT = 'chargement', 'Chargement'
        RECONCILIATION = 'reconciliation', 'Réconciliation'
        TERMINE = 'termine', 'Terminé'
        ECHOUE = 'echoue', 'Échoué'

    nom = models.CharField(max_length=200)
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.EXCEL)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    cree_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='projets_migration_crees')
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    # NTMIG35 — trace de la purge des fichiers source (PII) du projet. Les
    # rapports de réconciliation, eux, sont des AGRÉGATS non-PII : ils sont
    # conservés (ce sont les pièces justificatives remises au client migré).
    fichiers_purges = models.BooleanField(
        default=False, verbose_name='Fichiers source purgés')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]
        verbose_name = 'Projet de migration'
        verbose_name_plural = 'Projets de migration'

    def __str__(self):
        return f'{self.nom} ({self.get_source_display()})'


class LotMigration(TenantModel):
    """Un lot par entité dans un projet.

    Le chargement effectif est délégué au moteur ``dataimport`` ;
    ``import_job`` trace le commit réel (journal unique). Les compteurs miroir
    (source/créés/màj/erreurs) alimentent le rapport de réconciliation.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ANALYSE = 'analyse', 'Analysé'
        CHARGE = 'charge', 'Chargé'
        RECONCILIE = 'reconcilie', 'Réconcilié'
        ECHOUE = 'echoue', 'Échoué'

    projet = models.ForeignKey(
        ProjetMigration,
        # on_delete: composition — un lot n'existe que rattaché à son projet.
        on_delete=models.CASCADE,
        related_name='lots')
    entite = models.CharField(
        max_length=50,
        help_text="Clé de cible d'import ``dataimport.TARGETS`` (clients, "
                  "products, fournisseurs…).")
    ordre = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    # FK-CHAÎNE vers dataimport (jamais un import direct de son modèle).
    import_job = models.ForeignKey(
        'dataimport.ImportJob', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_migration')

    # Compteurs miroir du dernier chargement (base du reconcile).
    source_lignes = models.PositiveIntegerField(default=0)
    crees = models.PositiveIntegerField(default=0)
    maj = models.PositiveIntegerField(default=0)
    erreurs = models.PositiveIntegerField(default=0)
    # Somme des colonnes montant déclarées par le kit (reconcile financier).
    source_montant = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)

    # NTMIG35 — fichier source TEMPORAIRE. On stocke sa CLÉ D'OBJET MinIO
    # (bucket `erp-uploads`), jamais un `FileField` : ARC26 interdit toute
    # nouvelle pièce jointe hors stockage objet, et le fichier ne doit vivre ni
    # dans le dépôt ni sur le disque d'un conteneur. Il contient des données
    # personnelles (clients, leads) : gardé le temps de rejouer/reprendre un
    # chargement (NTMIG38) ou de tester à blanc (NTMIG33), puis purgé
    # automatiquement `RETENTION_FICHIERS_JOURS` jours après la clôture.
    fichier_source_cle = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name="Clé de stockage du fichier source")
    #: Nom d'origine du fichier — le nom stocké est suffixé par le stockage,
    #: et l'EXTENSION d'origine décide du parseur (CSV vs XLSX) à la reprise.
    fichier_source_nom = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name="Nom du fichier source d'origine")
    #: NTMIG38 — nombre de lignes du fichier D'ORIGINE déjà commitées lors des
    #: passes précédentes. Le dernier ``import_job`` numérote ses lignes à
    #: partir du fichier qu'on lui a donné (le RESTE du fichier lors d'une
    #: reprise) : sans cet décalage, « ligne 12 » du journal serait prise pour
    #: la ligne 12 de la source alors qu'elle en est la 612ᵉ, et la reprise
    #: suivante rechargerait 600 lignes déjà passées.
    fichier_offset_lignes = models.PositiveIntegerField(
        default=0, verbose_name="Lignes source déjà chargées (reprise)")

    # NTMIG5 — dérogation explicite « pas de succès sans reconcile ».
    derogation_reconcile = models.BooleanField(default=False)
    derogation_motif = models.TextField(blank=True, default='')
    derogation_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_migration_deroges')
    derogation_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['projet', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'projet']),
        ]
        verbose_name = 'Lot de migration'
        verbose_name_plural = 'Lots de migration'

    def __str__(self):
        return f'{self.projet_id}:{self.entite} ({self.statut})'


class RapportReconciliation(TenantModel):
    """Rapport de réconciliation d'un lot.

    Compare les comptages/totaux SOURCE (posés à l'analyse) aux comptages
    CIBLE réels après chargement. ``conforme`` n'est vrai que si les comptages
    ET les totaux financiers matchent à la tolérance près.

    Un rapport est un CONSTAT HORODATÉ : on en crée un nouveau à chaque
    réconciliation, on n'écrase jamais le précédent (l'historique des écarts
    est la pièce justificative remise au client migré).
    """

    lot = models.ForeignKey(
        LotMigration,
        # on_delete: composition — un rapport n'existe que pour son lot.
        on_delete=models.CASCADE,
        related_name='rapports')

    nb_source = models.PositiveIntegerField(default=0)
    nb_cible_crees = models.PositiveIntegerField(default=0)
    nb_cible_existants = models.PositiveIntegerField(default=0)
    nb_erreurs = models.PositiveIntegerField(default=0)

    total_financier_source = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)
    total_financier_cible = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)
    ecart_financier = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)

    ecarts = models.JSONField(default=list, blank=True)
    conforme = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'lot']),
        ]
        verbose_name = 'Rapport de réconciliation'
        verbose_name_plural = 'Rapports de réconciliation'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        src = self.total_financier_source
        cib = self.total_financier_cible
        if src is not None and cib is not None:
            self.ecart_financier = Decimal(cib) - Decimal(src)
            # Un ``update_fields`` restreint ne doit pas faire disparaître
            # silencieusement l'écart qu'on vient de recalculer. La signature
            # est explicite (et non ``*args``) pour que le cas positionnel
            # ``save(False, False, None, ['conforme'])`` soit couvert lui aussi.
            if (update_fields is not None
                    and 'ecart_financier' not in update_fields):
                update_fields = list(update_fields) + ['ecart_financier']
        super().save(force_insert=force_insert, force_update=force_update,
                     using=using, update_fields=update_fields)

    def __str__(self):
        etat = 'conforme' if self.conforme else 'écarts'
        return f'Reconcile lot {self.lot_id} ({etat})'


class PlaybookInstance(TenantModel):
    """NTMIG22 — un playbook kb (NTMIG21) instancié pour UN déploiement.

    Le playbook (``kb.KbArticle`` de type ``playbook``) est le MODÈLE, versionné
    par kb ; cette instance en est l'exécution chez un client donné : elle porte
    l'état COCHÉ de chaque étape et sa progression.

    ``etapes`` est un INSTANTANÉ des étapes prises au moment de l'instanciation
    (via ``kb.selectors.phases_playbook`` — jamais un import de ``kb.models``).
    C'est délibéré : une checklist de déploiement en cours ne doit pas se
    réécrire sous les pieds de l'intégrateur parce que quelqu'un a édité le
    playbook modèle — sans instantané, ajouter une 9ᵉ étape au modèle ferait
    silencieusement CHUTER la progression d'un chantier déjà à 100 %. C'est
    aussi ce qui rend l'instance lisible si l'article modèle disparaît.
    """

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    # FK-CHAÎNE vers kb (jamais un import de ``apps.kb.models``). SET_NULL :
    # l'instance et sa progression SURVIVENT à la suppression du playbook
    # modèle — les étapes cochées sont la trace du déploiement, pas une copie
    # jetable de l'article.
    playbook_article = models.ForeignKey(
        'kb.KbArticle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='instances_playbook',
        verbose_name='Playbook (article kb)')
    playbook_titre = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Titre du playbook',
        help_text="Titre figé à l'instanciation (reste lisible si l'article "
                  "modèle est supprimé ou renommé).")
    projet_migration = models.ForeignKey(
        ProjetMigration, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='playbooks',
        verbose_name='Projet de migration')
    client_final = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Client final',
        help_text='Nom libre du client déployé (jamais un FK cross-app dur).')
    # Instantané des étapes : [{'cle', 'libelle', 'phase', 'phase_titre'}, …]
    etapes = models.JSONField(default=list, blank=True,
                              verbose_name='Étapes (instantané)')
    # État coché par étape : {'<cle étape>': True/False}. Les clés inconnues
    # sont IGNORÉES au calcul (une étape retirée du modèle ne peut pas faire
    # dépasser la progression au-dessus de 100 %).
    avancement = models.JSONField(default=dict, blank=True,
                                  verbose_name='Avancement')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS,
        verbose_name='Statut')
    # PROTECT (jamais SET_NULL) : ``responsable`` est un champ d'identité —
    # le vider en silence à la suppression d'un compte ferait perdre QUI
    # pilotait le déploiement (garde YDATA3).
    responsable = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.PROTECT,
        null=True, blank=True, related_name='playbooks_migration',
        verbose_name='Responsable')

    class Meta:
        ordering = ['-created_at']
        # Noms EXPLICITES (≤30 car.) : un nom haché écrit à la main dans la
        # migration diverge du nom recalculé par Django et fait échouer le
        # contrôle de dérive modèle↔migration.
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='mig_playbook_soc_statut_idx'),
            models.Index(fields=['company', 'projet_migration'],
                         name='mig_playbook_soc_projet_idx'),
        ]
        verbose_name = 'Instance de playbook'
        verbose_name_plural = 'Instances de playbook'

    # ── Progression ────────────────────────────────────────────────────────

    @property
    def cles_etapes(self):
        """Clés des étapes de l'instantané, dans l'ordre, DÉDOUBLONNÉES."""
        vues, cles = set(), []
        for etape in self.etapes or []:
            if not isinstance(etape, dict):
                continue
            cle = str(etape.get('cle') or '')
            if not cle or cle in vues:
                continue
            vues.add(cle)
            cles.append(cle)
        return cles

    @property
    def nb_etapes(self):
        return len(self.cles_etapes)

    @property
    def nb_faites(self):
        """Étapes cochées — comptées SUR L'INSTANTANÉ uniquement.

        Une clé d'``avancement`` qui ne correspond à aucune étape connue est
        ignorée : sans ce filtrage, une clé résiduelle ferait afficher une
        progression supérieure à 100 %.
        """
        avancement = self.avancement if isinstance(self.avancement, dict) else {}
        return sum(1 for cle in self.cles_etapes if bool(avancement.get(cle)))

    @property
    def progression(self):
        """Pourcentage entier d'avancement (0 si le playbook n'a aucune étape).

        Tronqué, jamais arrondi au supérieur : 5 étapes sur 8 = 62 %, et une
        checklist incomplète ne peut jamais afficher 100 %.
        """
        total = self.nb_etapes
        if not total:
            return 0
        return int(self.nb_faites * 100 // total)

    def __str__(self):
        titre = self.playbook_titre or f'playbook {self.playbook_article_id}'
        return f'{titre} — {self.progression} %'


class DeploiementPartenaire(TenantModel):
    """NTMIG28 — traçabilité « qui a déployé quoi » chez quel client.

    Alimente le scoring de certification (NTMIG27) : c'est la SOURCE des
    déploiements réussis d'un partenaire, le compteur
    ``crm.Partenaire.nb_deploiements_reussis`` n'en étant qu'un miroir
    dénormalisé, posé par ``crm.services`` (jamais écrit depuis ici en direct).

    ``client_final`` est du TEXTE LIBRE, jamais un FK cross-app dur : le client
    déployé peut être une entreprise qui n'existe dans AUCUNE table de ce
    tenant (c'est le client de l'intégrateur, pas le nôtre).
    """

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        REUSSI = 'reussi', 'Réussi'
        ABANDONNE = 'abandonne', 'Abandonné'

    # FK-CHAÎNE vers crm (jamais un import de ``apps.crm.models``). Un
    # déploiement ne désigne plus personne sans son partenaire et ne peut
    # alors plus alimenter aucun score.
    partenaire = models.ForeignKey(
        'crm.Partenaire',
        # on_delete: composition — un déploiement n'existe que rattaché à
        # son partenaire.
        on_delete=models.CASCADE,
        related_name='deploiements', verbose_name='Partenaire')
    projet_migration = models.ForeignKey(
        ProjetMigration, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='deploiements_partenaire',
        verbose_name='Projet de migration')
    client_final = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Client final',
        help_text='Nom libre du client déployé (jamais un FK cross-app dur).')
    modules = models.JSONField(
        default=list, blank=True, verbose_name='Modules déployés')
    date_go_live = models.DateField(
        null=True, blank=True, verbose_name='Date de mise en service')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS,
        verbose_name='Statut')
    note_satisfaction = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Note de satisfaction (0-10)',
        validators=[MinValueValidator(0), MaxValueValidator(10)])

    class Meta:
        ordering = ['-date_go_live', '-created_at']
        # Noms EXPLICITES (≤30 car.) — même raison que ci-dessus.
        indexes = [
            models.Index(fields=['company', 'partenaire'],
                         name='mig_deploi_soc_part_idx'),
            models.Index(fields=['company', 'statut'],
                         name='mig_deploi_soc_statut_idx'),
        ]
        verbose_name = 'Déploiement partenaire'
        verbose_name_plural = 'Déploiements partenaire'

    def __str__(self):
        client = self.client_final or 'client non nommé'
        return f'{client} — {self.get_statut_display()}'
