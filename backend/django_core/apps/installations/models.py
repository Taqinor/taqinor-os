"""
Module Chantiers / Installations — l'objet pivot de l'après-vente.

Le chantier (Installation) est créé une fois le devis signé/accepté. C'est le
dossier de réalisation auquel tout l'après-vente (interventions, mise en
service, et plus tard parc équipements / garanties / SAV) viendra s'attacher.

Trois couches de statuts INDÉPENDANTES coexistent dans l'OS, à ne jamais
mélanger :
  1. l'étape du lead (STAGES.py — l'entonnoir commercial) ;
  2. le statut du document devis/facture (ventes) ;
  3. le statut du CHANTIER ci-dessous (réalisation physique).

Cet enum est une liste FERMÉE, en ordre d'entonnoir. « annulé » n'est PAS une
étape : c'est un drapeau (avec motif), comme « Perdu » sur un lead.
"""
from django.conf import settings
from django.db import models


class Installation(models.Model):
    class Statut(models.TextChoices):
        # ── Entonnoir CANONIQUE du chantier (N1) — ordre d'exécution ──
        SIGNE = 'signe', 'Signé'
        MATERIEL_COMMANDE = 'materiel_commande', 'Matériel commandé'
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        INSTALLE = 'installe', 'Installé'
        RECEPTIONNE = 'receptionne', 'Réceptionné'
        CLOTURE = 'cloture', 'Clôturé'
        # ── Statuts HÉRITÉS (chantiers d'avant le funnel N1) — conservés
        #    valides pour ne jamais invalider une donnée existante. Hors de
        #    l'entonnoir principal ; rabattus pour l'affichage via
        #    LEGACY_STATUT_MAP. Additif : aucune migration destructive. ──
        A_PLANIFIER = 'a_planifier', 'À planifier'
        POSE_EN_COURS = 'pose_en_cours', 'Pose en cours'
        POSE = 'pose', 'Posé'
        RACCORDEMENT_ONEE = 'raccordement_onee', 'Raccordement ONEE'
        MISE_EN_SERVICE = 'mise_en_service', 'Mise en service'

    # Ordre d'entonnoir CANONIQUE (pour le tri des vues — JAMAIS alphabétique).
    STATUT_ORDER = [
        Statut.SIGNE,
        Statut.MATERIEL_COMMANDE,
        Statut.PLANIFIE,
        Statut.EN_COURS,
        Statut.INSTALLE,
        Statut.RECEPTIONNE,
        Statut.CLOTURE,
    ]

    # Rabat un statut hérité sur sa colonne canonique (affichage/kanban only ;
    # la valeur stockée reste intacte jusqu'à ce que l'utilisateur la change).
    LEGACY_STATUT_MAP = {
        'a_planifier': Statut.SIGNE,
        'pose_en_cours': Statut.EN_COURS,
        'pose': Statut.INSTALLE,
        'raccordement_onee': Statut.EN_COURS,
        'mise_en_service': Statut.RECEPTIONNE,
    }

    @classmethod
    def canonical_statut(cls, value):
        return cls.LEGACY_STATUT_MAP.get(value, value)

    class Raccordement(models.TextChoices):
        MONOPHASE = 'monophase', 'Monophasé'
        TRIPHASE = 'triphase', 'Triphasé'

    class TypeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel / Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations',
    )
    reference = models.CharField(max_length=50)

    # ── Liens (pivot) ──
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='installations',
    )
    # Devis d'origine. SET_NULL pour ne jamais perdre un chantier réalisé si le
    # devis est supprimé. Un seul chantier par devis (garde dans le service).
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations',
    )
    bon_commande = models.ForeignKey(
        'ventes.BonCommande', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations',
    )
    # Lead d'origine — pour le lien retour vers la fiche prospect.
    lead = models.ForeignKey(
        'crm.Lead', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations',
    )

    # ── Adresse du SITE (lieu physique des panneaux) — distincte de l'adresse
    #    de facturation du client. Pré-remplie depuis le lead, éditable. ──
    site_adresse = models.TextField(blank=True, null=True)
    site_ville = models.CharField(max_length=120, blank=True, null=True)
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    # ── Caractéristiques techniques (gelées à la création) ──
    puissance_installee_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Raccordement GELÉ ici : la valeur engagée du chantier (copiée du lead),
    # indépendante d'une modification ultérieure du lead.
    raccordement = models.CharField(
        max_length=12, choices=Raccordement.choices, blank=True, null=True)
    type_installation = models.CharField(
        max_length=20, choices=TypeInstallation.choices, blank=True, null=True)

    technicien_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_techniques',
    )

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.SIGNE)

    # ── Charge de main-d'œuvre (N1) — jours-homme estimés vs réels. ──
    labour_jours_estimes = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True)
    labour_jours_reels = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True)

    # ── Parc installé (N7) — un chantier réceptionné devient un « système
    #    installé » actif. Le drapeau permet de retirer un système du parc
    #    sans le supprimer. La date de réception est posée au passage à
    #    « Réceptionné ». ──
    parc_actif = models.BooleanField(default=True)

    # Nomenclature (BOM) GELÉE à la création depuis le devis : liste de
    # {produit_id, designation, quantite, marque}. Sert de résumé système et
    # de base composants pour le parc, indépendant d'une édition ultérieure
    # du devis. Additif (JSON, défaut liste vide).
    bom = models.JSONField(default=list, blank=True)

    # ── Dossier réglementaire loi 82-21 / Article 33 (N40/N42) — additif,
    #    tout optionnel. Le régime et le statut pilotent les filtres (N41). ──
    class Regime8221(models.TextChoices):
        NON_CONCERNE = 'non_concerne', 'Non concerné'
        DECLARATION_BT = 'declaration_bt', 'Déclaration (< 11 kW, BT)'
        ACCORD_RACCORDEMENT = 'accord_raccordement', 'Accord de raccordement'
        AUTORISATION_ANRE = 'autorisation_anre', 'Autorisation ANRE (> 1 MW)'

    class DossierStatut(models.TextChoices):
        NON_CONCERNE = 'non_concerne', 'Non concerné'
        A_DEPOSER = 'a_deposer', 'À déposer'
        DEPOSE = 'depose', 'Déposé'
        APPROUVE = 'approuve', 'Approuvé'
        COMPTEUR_POSE = 'compteur_pose', 'Compteur posé'

    regime_8221 = models.CharField(
        max_length=24, choices=Regime8221.choices,
        default=Regime8221.NON_CONCERNE)
    dossier_statut = models.CharField(
        max_length=16, choices=DossierStatut.choices,
        default=DossierStatut.NON_CONCERNE)
    dossier_reference = models.CharField(max_length=120, blank=True, null=True)
    dossier_operateur = models.CharField(max_length=120, blank=True, null=True)
    dossier_date_depot = models.DateField(null=True, blank=True)
    dossier_date_approbation = models.DateField(null=True, blank=True)
    # N42 — régularisation Article 33 (installation existante à régulariser).
    art33_regularisation = models.BooleanField(default=False)

    # ── Annulation : un DRAPEAU avec motif, pas une étape (comme « Perdu »). ──
    annule = models.BooleanField(default=False)
    motif_annulation = models.CharField(max_length=255, blank=True, null=True)

    # ── Dates clés (jalons — alimentent la timeline N6). ──
    date_signature = models.DateField(null=True, blank=True)
    date_materiel_commande = models.DateField(null=True, blank=True)
    date_pose_prevue = models.DateField(null=True, blank=True)
    date_pose_reelle = models.DateField(null=True, blank=True)
    date_mise_en_service = models.DateField(null=True, blank=True)
    date_reception = models.DateField(null=True, blank=True)
    date_cloture = models.DateField(null=True, blank=True)

    # ── Mise en service (commissioning) ──
    mes_pv_notes = models.TextField(blank=True, null=True)
    mes_production_test = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    mes_tension = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)

    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='installations_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Chantier'
        verbose_name_plural = 'Chantiers'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return self.reference


class TypeIntervention(models.Model):
    """Type d'intervention géré (Paramètres → Chantiers). `Intervention.type`
    reste une clé texte ; cette liste pilote le sélecteur et les libellés.
    `protege` verrouille un type système contre le renommage/la suppression.
    Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='types_intervention')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=80)
    ordre = models.PositiveIntegerField(default=0)
    protege = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = "Type d'intervention"
        verbose_name_plural = "Types d'intervention"

    def __str__(self):
        return self.libelle


class Intervention(models.Model):
    class Type(models.TextChoices):
        POSE = 'pose', 'Pose'
        RACCORDEMENT = 'raccordement', 'Raccordement'
        MISE_EN_SERVICE = 'mise_en_service', 'Mise en service'
        CONTROLE = 'controle', 'Contrôle'
        DEPANNAGE = 'depannage', 'Dépannage'

    class Statut(models.TextChoices):
        # F3 — machine à états PROPRE à l'intervention (sortie chantier).
        # TOTALEMENT séparée du statut chantier (Installation.Statut) et du
        # contrat STAGES.py : changer ce statut ne touche JAMAIS le chantier.
        A_PREPARER = 'a_preparer', 'À préparer'
        PRETE = 'prete', 'Prête'
        EN_ROUTE = 'en_route', 'En route'
        SUR_SITE = 'sur_site', 'Sur site'
        TERMINEE = 'terminee', 'Terminée'
        VALIDEE = 'validee', 'Validée'

    # Ordre de progression du statut intervention (pour un tri non-alphabétique
    # et le kanban). Ne pilote AUCUNE logique chantier.
    STATUT_ORDER = [
        Statut.A_PREPARER, Statut.PRETE, Statut.EN_ROUTE,
        Statut.SUR_SITE, Statut.TERMINEE, Statut.VALIDEE,
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='interventions',
    )
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='interventions',
    )
    # Lien OPTIONNEL vers un ticket SAV : résoudre un ticket peut enregistrer
    # une ou plusieurs interventions (visites terrain) contre lui, sans créer
    # de concept « visite » parallèle. Additif, nullable — le comportement
    # chantier→intervention existant reste intact.
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    type_intervention = models.CharField(max_length=20, choices=Type.choices)
    # F3 — statut PROPRE de l'intervention. Défaut « À préparer » ⇒ toute
    # intervention existante migrée prend ce statut (additif, non destructif).
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_PREPARER)
    date_prevue = models.DateField(null=True, blank=True)
    date_realisee = models.DateField(null=True, blank=True)
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    # F3 — équipe assignée (un+ employés). Défaut = l'installateur du chantier,
    # posé côté serveur à la création quand l'équipe est laissée vide.
    equipe = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='interventions_equipe',
    )
    # F3 — camionnette assignée : un emplacement de stock (dépôt/camionnette).
    camionnette = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    compte_rendu = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='interventions_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Intervention"
        verbose_name_plural = "Interventions"
        ordering = ['-date_prevue', '-date_creation']

    def __str__(self):
        return f"{self.get_type_intervention_display()} — {self.installation_id}"


class InterventionActivity(models.Model):
    """Historique « chatter » d'une intervention — même patron que
    InstallationActivity / LeadActivity. Entrées automatiques (création +
    changements de champs suivis, dont le statut) et notes manuelles.
    L'utilisateur et la société sont toujours posés côté serveur."""
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='intervention_activities',
    )
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='intervention_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité intervention'
        verbose_name_plural = 'Activités intervention'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['intervention', '-created_at'])]

    def __str__(self):
        return f"{self.intervention_id} {self.kind} {self.field or ''}".strip()


class InstallationActivity(models.Model):
    """Historique « chatter » d'un chantier — même modèle que LeadActivity.

    Entrées automatiques (création + changements de champs suivis, dont le
    statut) et notes manuelles. L'utilisateur et la société sont toujours
    posés côté serveur, jamais lus du corps de la requête.
    """
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installation_activities',
    )
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installation_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité chantier'
        verbose_name_plural = 'Activités chantier'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['installation', '-created_at'])]

    def __str__(self):
        return f"{self.installation_id} {self.kind} {self.field or ''}".strip()


class ChecklistTemplate(models.Model):
    """N74 — modèle NOMMÉ de checklist d'onboarding/chantier, configurable dans
    Paramètres. Un template regroupe des étapes ordonnées (ChecklistEtapeModele)
    et peut être rattaché à un `type_installation` : à la création d'un chantier,
    le template dont le type correspond est sélectionné automatiquement ; sinon
    on retombe sur le template « Défaut » (type_installation vide).

    Le template « Défaut » est protégé et porte EXACTEMENT les étapes appliquées
    aujourd'hui — un chantier sans type spécifique reçoit donc la même checklist
    qu'avant (comportement préservé). Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_templates')
    nom = models.CharField(max_length=120)
    # Type d'installation qui auto-sélectionne ce template (résidentiel /
    # industriel / agricole). Vide = template « Défaut » (repli générique).
    type_installation = models.CharField(
        max_length=20, choices=Installation.TypeInstallation.choices,
        blank=True, null=True)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    # `protege` verrouille le template « Défaut » système contre la suppression.
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Modèle de checklist chantier"
        verbose_name_plural = "Modèles de checklist chantier"

    def __str__(self):
        return self.nom


class ChecklistEtapeModele(models.Model):
    """N4 — étape MODÈLE de la checklist d'exécution chantier, éditable dans
    Paramètres (libellé + ordre + activation). `capture_serie` marque les
    étapes où l'on saisit des numéros de série (N9 : panneaux/onduleur).
    `protege` verrouille une étape système contre la suppression. Additif.

    N74 — chaque étape appartient à un `template` (nullable : les étapes
    historiques sans template sont rattachées au template « Défaut » par la
    migration de données / l'amorçage paresseux)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_etapes')
    # N74 — template propriétaire (nullable pour la compat ; les étapes
    # orphelines sont migrées vers le template « Défaut »).
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.CASCADE,
        null=True, blank=True, related_name='etapes')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    capture_serie = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        # N74 — la clé est unique PAR template (même cle réutilisable d'un
        # template à l'autre). Les étapes historiques (template=NULL) gardent
        # l'unicité par société jusqu'à leur rattachement au template « Défaut ».
        unique_together = [('company', 'template', 'cle')]
        verbose_name = "Étape de checklist chantier"
        verbose_name_plural = "Étapes de checklist chantier"

    def __str__(self):
        return self.libelle


class StockReservation(models.Model):
    """N14 — réservation de stock d'un chantier sur un SKU (produit catalogue).

    À la création d'un chantier, on RÉSERVE auprès du stock les quantités
    requises issues de la nomenclature GELÉE du devis lié (`Installation.bom`),
    une ligne par produit. La réservation ENGAGE le stock sans le décrémenter :
    le « disponible » d'un produit = `quantite_stock` − somme des réservations
    actives non encore consommées (les vues stock + alertes de stock bas en
    tiennent compte). Au passage du chantier à « Installé », la réservation est
    CONSOMMÉE : un seul MouvementStock SORTIE par SKU, idempotent (le drapeau
    `consomme` garantit qu'un re-passage par « Installé » ne re-décrémente
    jamais). À l'annulation/clôture du chantier, la réservation NON consommée
    est LIBÉRÉE (`active=False`) — le disponible revient.

    Entièrement additif ; multi-tenant (société posée côté serveur).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='stock_reservations')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='reservations')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='reservations')
    quantite = models.PositiveIntegerField(default=0)
    # Réservation engagée tant que `active` ET non `consomme` : elle pèse alors
    # sur le « disponible ». Libérée (annulation/clôture) ⇒ active=False.
    active = models.BooleanField(default=True)
    # Consommée au passage « Installé » : le stock A été décrémenté. Le drapeau
    # est le verrou d'idempotence (jamais deux SORTIE pour la même réservation).
    consomme = models.BooleanField(default=False)
    date_consommation = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réservation de stock'
        verbose_name_plural = 'Réservations de stock'
        ordering = ['installation_id', 'id']
        # Une seule réservation par (chantier, produit) — le réamorçage est
        # idempotent (on met à jour la quantité plutôt que d'empiler).
        unique_together = [('installation', 'produit')]
        indexes = [
            models.Index(fields=['produit', 'active', 'consomme']),
        ]

    def __str__(self):
        return f'{self.installation_id} · {self.produit_id} × {self.quantite}'


class ChantierChecklistItem(models.Model):
    """N4 — état d'une étape de checklist POUR un chantier donné : fait / par
    qui / quand. Le pourcentage d'avancement du chantier en dérive. Créés
    paresseusement depuis les étapes modèle à la première consultation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_items')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='checklist')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    capture_serie = models.BooleanField(default=False)
    fait = models.BooleanField(default=False)
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_items_faits')
    fait_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('installation', 'cle')]
        verbose_name = "Étape de checklist (chantier)"
        verbose_name_plural = "Étapes de checklist (chantier)"

    def __str__(self):
        return f"{self.installation_id} · {self.libelle} · {'✓' if self.fait else '—'}"
