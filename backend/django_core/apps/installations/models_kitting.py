"""
FG328 — Pré-assemblage / kitting magasin.

Le magasin assemble parfois un ARTICLE COMPOSITE léger (un coffret AC/DC
pré-câblé) à partir de composants du catalogue. FG328 modélise :
  * `Kit` — la DÉFINITION du composite (article produit, string-FK
    `stock.Produit`) et sa nomenclature (`KitComposant`, SKU + quantité) ;
  * `OrdreAssemblage` — l'EXÉCUTION : assembler N kits, qui CONSOMME les
    composants et produit le composite. L'ordre suit un cycle planifié → en
    cours → terminé.

Cross-app : `stock.Produit` en STRING-FK uniquement. La consommation/production
réelle de stock reste pilotée par le module stock ; FG328 trace l'ordre. Additif
& multi-tenant : FK `company` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class Kit(models.Model):
    """FG328 — définition d'un composite assemblé en magasin (article + BOM).

    Multi-tenant : société posée côté serveur. ``produit_compose`` est l'article
    catalogue produit par l'assemblage (string-FK `stock.Produit`, optionnel si
    le composite n'est pas encore référencé au catalogue)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_kits')
    nom = models.CharField(max_length=255)
    reference_interne = models.CharField(max_length=80, blank=True, null=True)
    produit_compose = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_kits_composes')
    active = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_kits_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kit de pré-assemblage'
        verbose_name_plural = 'Kits de pré-assemblage'
        ordering = ['nom']
        indexes = [
            models.Index(fields=['company', 'active'],
                         name='idx_kit_co_active'),
        ]

    def __str__(self):
        return self.nom


class KitComposant(models.Model):
    """FG328 — composant de la nomenclature d'un kit (SKU + quantité unitaire)."""

    kit = models.ForeignKey(
        Kit, on_delete=models.CASCADE, related_name='composants')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_kit_composants')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.PositiveIntegerField(default=1)
    # XMFG11 — taux de perte attendu (%) pour ce composant (casse/chutes au
    # montage). Défaut 0 = comportement historique inchangé. Gonfle le besoin
    # planifié (XMFG2 réservation) : besoin_effectif = quantite × (1 + taux/100).
    taux_perte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Taux de perte attendu (%) — gonfle le besoin planifié.")

    class Meta:
        verbose_name = 'Composant de kit'
        verbose_name_plural = 'Composants de kit'
        ordering = ['kit_id', 'id']
        indexes = [
            models.Index(fields=['kit'], name='idx_kitc_kit'),
            models.Index(fields=['produit'], name='idx_kitc_produit'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite}'


class RevisionKit(models.Model):
    """XMFG18 — révision de nomenclature d'un kit de pré-assemblage (pattern
    RevisionDocument FG297) : snapshot JSON AUTO de la composition à chaque
    modification des composants, numéroté par kit. L'ordre d'assemblage FIGE
    le numéro de révision en vigueur à sa création
    (``OrdreAssemblage.revision_kit_numero``)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_revisions_kit')
    kit = models.ForeignKey(
        Kit, on_delete=models.CASCADE, related_name='revisions')
    numero = models.PositiveIntegerField(default=1)
    composition = models.JSONField(
        default=list,
        help_text='Snapshot des composants : produit_id, désignation, '
                  'quantité, taux de perte.')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_revisions_kit_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Révision de kit de pré-assemblage'
        verbose_name_plural = 'Révisions de kit de pré-assemblage'
        ordering = ['kit_id', '-numero']
        constraints = [
            models.UniqueConstraint(
                fields=['kit', 'numero'],
                name='inst_revkit_kit_numero_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'kit'],
                         name='inst_revkit_co_kit_idx'),
        ]

    def __str__(self):
        return f'Rev.{self.numero} — kit {self.kit_id}'


class OrdreAssemblage(models.Model):
    """FG328 — ordre d'assemblage de N kits. Référence ``ASM-YYYYMM-NNNN``
    anti-collision. Cycle : planifié → en cours → terminé. La consommation des
    composants / production du composite reste pilotée par le module stock."""

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_ordres_assemblage')
    reference = models.CharField(max_length=50)
    kit = models.ForeignKey(
        Kit, on_delete=models.PROTECT, related_name='ordres')
    quantite = models.PositiveIntegerField(default=1)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIE)
    note = models.TextField(blank=True, null=True)
    date_terminaison = models.DateTimeField(null=True, blank=True)

    # XMFG1 — backflush : emplacements optionnels (string-FK stock, N15) +
    # quantité RÉELLEMENT produite (défaut = quantite, éditable à la clôture —
    # tolérance sur/sous-production). `stock_mouvemente` verrouille
    # l'idempotence : une re-clôture n'émet jamais de second mouvement.
    emplacement_source = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_assemblage_source')
    emplacement_destination = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_assemblage_destination')
    quantite_produite = models.PositiveIntegerField(null=True, blank=True)
    stock_mouvemente = models.BooleanField(default=False)

    # XMFG3 — assembler-à-la-commande : liens optionnels vers le devis source
    # (string-FK `ventes.Devis`) et le chantier (same-app `Installation`).
    # `devis` sert à l'idempotence de la création (get_or_create par
    # devis+kit) ; `chantier` permet au coût du chantier lié de VOIR l'ordre
    # (lecture seule).
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_assemblage')
    chantier = models.ForeignKey(
        'Installation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ordres_assemblage')

    # XMFG4 — cycle de vie : planification/pilotage + annulation motivée
    # (interdite si le stock a déjà été mouvementé — XMFG1).
    date_prevue = models.DateField(null=True, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_assemblage_responsable')
    motif_annulation = models.TextField(blank=True, null=True)

    # XMFG16 — assemblage sous-traité (façon) : composants confiés à un
    # atelier externe puis composite reçu. `sous_traitant` (FK CHAÎNE
    # `stock.Fournisseur` de type « service », même référentiel unifié que
    # FG305/DC34 — jamais d'import de `stock.models`) + `ordre_sous_traitance`
    # (same-app, optionnel) lie l'ordre d'assemblage à sa prestation façon
    # (montant/montant_realise = coût façon, INTERNE, jamais client-facing).
    # Les deux champs sont NULLABLES : un ordre d'assemblage interne (aucune
    # sous-traitance) garde le comportement actuel inchangé.
    sous_traitant = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_assemblage_soustraites')
    ordre_sous_traitance = models.ForeignKey(
        'OrdreSousTraitance', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ordres_assemblage')

    # XMFG18 — numéro de la révision de nomenclature (RevisionKit) en vigueur
    # à la création de l'ordre : l'ordre FIGE sa révision (traçabilité de la
    # composition réellement utilisée, même si la BOM évolue ensuite).
    revision_kit_numero = models.PositiveIntegerField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_assemblage_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ordre d\'assemblage'
        verbose_name_plural = 'Ordres d\'assemblage'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_asm_co_statut'),
            models.Index(fields=['company', 'kit'],
                         name='idx_asm_co_kit'),
            models.Index(fields=['devis', 'kit'], name='idx_asm_devis_kit'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class ReservationAssemblage(models.Model):
    """XMFG2 — réservation de composant engagée par un ordre d'assemblage,
    même patron que ``StockReservation`` (N14, chantiers) : ENGAGE le stock
    sans le décrémenter. Semée à la création/confirmation de l'ordre depuis la
    BOM du kit (ou les lignes d'ordre — XMFG6, avec repli BOM). Libérée
    (``active=False``) à l'annulation ; marquée ``consomme`` par XMFG1 au
    backflush (verrou d'idempotence, jamais deux fois décomptée)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_reservations_assemblage')
    ordre = models.ForeignKey(
        OrdreAssemblage, on_delete=models.CASCADE, related_name='reservations')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='installations_reservations_assemblage')
    quantite = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    consomme = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réservation d\'assemblage'
        verbose_name_plural = 'Réservations d\'assemblage'
        ordering = ['ordre_id', 'id']
        unique_together = [('ordre', 'produit')]
        indexes = [
            models.Index(fields=['produit', 'active', 'consomme'],
                         name='idx_resa_asm_prod_act_cons'),
        ]

    def __str__(self):
        return f'{self.ordre_id} · {self.produit_id} × {self.quantite}'


class OrdreAssemblageActivity(models.Model):
    """XMFG4 — chatter de l'ordre d'assemblage, même patron que
    ``InstallationActivity`` : log auto ancien→nouveau des champs suivis +
    notes manuelles via `historique`/`noter`. Utilisateur et société toujours
    posés côté serveur."""

    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_ordre_assemblage_activities')
    ordre = models.ForeignKey(
        OrdreAssemblage, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordre_assemblage_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Activité d'ordre d'assemblage"
        verbose_name_plural = "Activités d'ordre d'assemblage"
        ordering = ['-created_at']
        indexes = [models.Index(fields=['ordre', '-created_at'],
                                name='idx_asmact_ordre_created')]

    def __str__(self):
        return f"{self.ordre_id} {self.kind} {self.field or ''}".strip()


class OrdreAssemblageLigne(models.Model):
    """XMFG6 — composants PERSONNALISABLES d'un ordre (kit sur-mesure à la
    commande). Copiées depuis la BOM du kit à la création de l'ordre, puis
    éditables tant que l'ordre est PLANIFIÉ (verrouillé dès `en_cours`).
    XMFG1 (backflush) et XMFG2 (réservation) consomment/réservent depuis CES
    lignes en priorité — repli sur la BOM du kit si aucune ligne n'existe
    (rétro-compatible avec les ordres créés avant XMFG6)."""

    class Origine(models.TextChoices):
        KIT = 'kit', 'Copié du kit'
        AJOUT = 'ajout', 'Ajouté sur cet ordre'

    ordre = models.ForeignKey(
        OrdreAssemblage, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordre_assemblage_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.PositiveIntegerField(default=1)
    origine = models.CharField(
        max_length=10, choices=Origine.choices, default=Origine.KIT)

    class Meta:
        verbose_name = "Ligne d'ordre d'assemblage"
        verbose_name_plural = "Lignes d'ordre d'assemblage"
        ordering = ['ordre_id', 'id']
        indexes = [
            models.Index(fields=['ordre'], name='idx_asmligne_ordre'),
            models.Index(fields=['produit'], name='idx_asmligne_produit'),
        ]

    def __str__(self):
        return f'{self.ordre_id} · {self.designation or self.produit_id} × {self.quantite}'


class SerieAssemblage(models.Model):
    """XMFG7 — n° de série relevé À LA CLÔTURE d'un ordre d'assemblage : une
    ligne par unité de composite produite (`role=composite`) et, en option,
    une ligne par composant sérialisé consommé (`role=composant`), reliée à
    son composite via `composite_ref`. Comble le trou noir entre la réception
    (FG61) et la pose (`ComponentSerial`) : après l'assemblage, on sait quel
    onduleur est parti dans quel coffret. Company posée côté serveur."""

    class Role(models.TextChoices):
        COMPOSITE = 'composite', 'Composite produit'
        COMPOSANT = 'composant', 'Composant consommé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_series_assemblage')
    ordre = models.ForeignKey(
        OrdreAssemblage, on_delete=models.CASCADE, related_name='series')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_series_assemblage')
    numero_serie = models.CharField(max_length=120)
    role = models.CharField(max_length=12, choices=Role.choices)
    # Lien composite↔composants : pour une ligne `composant`, référence la
    # ligne `composite` de la même unité produite (NULL pour une ligne
    # `composite` elle-même, ou si le lien composite n'est pas précisé).
    composite_ref = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='composants_lies')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_series_assemblage_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Série d'assemblage"
        verbose_name_plural = "Séries d'assemblage"
        ordering = ['ordre_id', 'id']
        indexes = [
            models.Index(fields=['ordre', 'role'], name='idx_serieasm_ordre_role'),
            models.Index(fields=['numero_serie'], name='idx_serieasm_numero'),
        ]

    def __str__(self):
        return f'{self.ordre_id} · {self.role} · {self.numero_serie}'


class OrdreDemontage(models.Model):
    """XMFG12 — ordre de DÉMONTAGE (unbuild) : chemin inverse de
    l'assemblage, composite → composants. Référence ``DSM-YYYYMM-NNNN``
    anti-collision (même pattern que ``OrdreAssemblage``). À la clôture :
    SORTIE du composite + ENTREE de chaque composant selon la BOM, avec
    quantités RÉCUPÉRÉES éditables ligne à ligne (les composants cassés non
    restockés sont déclarés en rebut — XMFG11). Idempotent via
    `stock_mouvemente`."""

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_ordres_demontage')
    reference = models.CharField(max_length=50)
    kit = models.ForeignKey(
        Kit, on_delete=models.PROTECT, related_name='ordres_demontage')
    quantite = models.PositiveIntegerField(default=1)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIE)
    note = models.TextField(blank=True, null=True)
    emplacement_source = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_demontage_source')
    emplacement_destination = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_demontage_destination')
    stock_mouvemente = models.BooleanField(default=False)
    date_terminaison = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_demontage_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ordre de démontage'
        verbose_name_plural = 'Ordres de démontage'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_dsm_co_statut'),
            models.Index(fields=['company', 'kit'], name='idx_dsm_co_kit'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class OrdreDemontageLigne(models.Model):
    """XMFG12 — quantité RÉCUPÉRÉE éditable par composant, copiée depuis la
    BOM du kit à la création de l'ordre. La différence entre la quantité BOM
    attendue et la quantité récupérée (`quantite_recuperee < quantite_attendue`)
    représente la perte — déclarable en rebut (XMFG11) par l'appelant."""

    ordre = models.ForeignKey(
        OrdreDemontage, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordre_demontage_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite_attendue = models.PositiveIntegerField(default=0)
    quantite_recuperee = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de démontage'
        verbose_name_plural = 'Lignes de démontage'
        ordering = ['ordre_id', 'id']
        indexes = [
            models.Index(fields=['ordre'], name='idx_dsmligne_ordre'),
        ]

    def __str__(self):
        return (f'{self.ordre_id} · {self.designation or self.produit_id} '
                f'récup {self.quantite_recuperee}/{self.quantite_attendue}')


class ControleQualiteModele(models.Model):
    """XMFG13 — modèle de checklist qualité PAR KIT (gate avant clôture).
    Un kit SANS modèle défini garde le comportement actuel inchangé (aucune
    checklist n'est exigée). Un kit AVEC un modèle actif voit `terminer`
    bloqué tant que sa checklist n'est pas passée."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_controle_qualite_modeles')
    kit = models.OneToOneField(
        Kit, on_delete=models.CASCADE, related_name='controle_qualite_modele')
    active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Modèle de contrôle qualité'
        verbose_name_plural = 'Modèles de contrôle qualité'
        ordering = ['kit_id']

    def __str__(self):
        return f'QC · {self.kit_id}'


class ControleQualiteItemModele(models.Model):
    """XMFG13 — item de checklist QC du modèle (pass/fail, valeur mesurée
    optionnelle avec tolérance min/max, photo optionnelle exigée)."""

    modele = models.ForeignKey(
        ControleQualiteModele, on_delete=models.CASCADE, related_name='items')
    libelle = models.CharField(max_length=255)
    ordre = models.PositiveIntegerField(default=0)
    # Tolérance optionnelle : si définie, la valeur mesurée doit être dans
    # [valeur_min, valeur_max] pour que l'item passe automatiquement (pass/fail
    # manuel reste toujours possible même sans tolérance définie).
    valeur_min = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True)
    valeur_max = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True)
    unite = models.CharField(max_length=20, blank=True, default='')
    photo_requise = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Item de contrôle qualité'
        verbose_name_plural = 'Items de contrôle qualité'
        ordering = ['modele_id', 'ordre', 'id']

    def __str__(self):
        return self.libelle


class ControleQualiteOrdre(models.Model):
    """XMFG13 — état d'exécution d'un item QC POUR un ordre d'assemblage
    donné (résultat, valeur mesurée, photo). Instancié depuis
    `ControleQualiteItemModele` à la première consultation de l'ordre."""

    class Resultat(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        PASS_ = 'pass', 'Passé'
        FAIL = 'fail', 'Échec'

    ordre = models.ForeignKey(
        OrdreAssemblage, on_delete=models.CASCADE,
        related_name='controles_qualite')
    item_modele = models.ForeignKey(
        ControleQualiteItemModele, on_delete=models.CASCADE,
        related_name='executions')
    resultat = models.CharField(
        max_length=12, choices=Resultat.choices, default=Resultat.EN_ATTENTE)
    valeur_mesuree = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True)
    photo = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    controle_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_controle = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Exécution de contrôle qualité"
        verbose_name_plural = "Exécutions de contrôle qualité"
        ordering = ['ordre_id', 'item_modele__ordre', 'id']
        unique_together = [('ordre', 'item_modele')]
        indexes = [
            models.Index(fields=['ordre', 'resultat'],
                         name='idx_cqordre_ordre_resultat'),
        ]

    def __str__(self):
        return f'{self.ordre_id} · {self.item_modele_id} · {self.resultat}'


class EtapeAssemblage(models.Model):
    """XMFG14 — étape de la gamme (mode opératoire) d'un ``Kit`` : instructions
    texte, durée attendue, pièce jointe optionnelle (schéma câblage, photo).
    Un kit SANS étape garde le comportement actuel inchangé (pas de mode
    opératoire affiché). Instanciée en checklist d'exécution (`EtapeOrdre`)
    sur chaque ordre."""

    kit = models.ForeignKey(
        Kit, on_delete=models.CASCADE, related_name='etapes_assemblage')
    ordre = models.PositiveIntegerField(default=0)
    libelle = models.CharField(max_length=255)
    instructions = models.TextField(blank=True, default='')
    duree_attendue_min = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Durée attendue de cette étape, en minutes.')
    piece_jointe = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text='Schéma de câblage, photo de référence…')

    class Meta:
        verbose_name = "Étape d'assemblage"
        verbose_name_plural = "Étapes d'assemblage"
        ordering = ['kit_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['kit'], name='idx_etapeasm_kit'),
        ]

    def __str__(self):
        return f'{self.kit_id} · {self.libelle}'


class EtapeOrdre(models.Model):
    """XMFG14 — état d'exécution d'une étape POUR un ordre d'assemblage
    donné : fait/par qui/quand + durée réelle saisie. Instanciée depuis
    `EtapeAssemblage` à la première consultation de l'ordre. La somme des
    durées réelles vs attendues alimente XMFG15 (tableau de bord atelier)."""

    ordre = models.ForeignKey(
        OrdreAssemblage, on_delete=models.CASCADE, related_name='etapes')
    etape_modele = models.ForeignKey(
        EtapeAssemblage, on_delete=models.CASCADE, related_name='executions')
    fait = models.BooleanField(default=False)
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    fait_le = models.DateTimeField(null=True, blank=True)
    duree_reelle_min = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Étape d'ordre"
        verbose_name_plural = "Étapes d'ordre"
        ordering = ['ordre_id', 'etape_modele__ordre', 'id']
        unique_together = [('ordre', 'etape_modele')]
        indexes = [
            models.Index(fields=['ordre', 'fait'], name='idx_etapeord_ordre_fait'),
        ]

    def __str__(self):
        return f'{self.ordre_id} · {self.etape_modele_id} · {"fait" if self.fait else "à faire"}'
