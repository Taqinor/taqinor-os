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

    # ── F6 — horodatage du trajet & arrivée sur site (géolocalisation
    #    navigateur, AUCUN service externe). Tout est ADDITIF et nullable :
    #    une intervention existante n'est pas affectée. Le check-in pose une
    #    position GPS d'arrivée (≠ GPS du chantier, qui reste la cible) ; on en
    #    dérive une distance-au-site indicative côté API. Le départ-dépôt et le
    #    retour bornent le temps de trajet. ──
    depart_depot_le = models.DateTimeField(null=True, blank=True)
    arrivee_site_le = models.DateTimeField(null=True, blank=True)
    arrivee_gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    arrivee_gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    retour_depot_le = models.DateTimeField(null=True, blank=True)

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


# ── F7/F8 — Shot list (modèle de prises de vue guidées) ──────────────────────
class ShotListSlot(models.Model):
    """F7/F8 — emplacement (créneau) d'une SHOT LIST de documentation terrain,
    configurable dans Paramètres. Chaque créneau définit une vue attendue lors
    d'une intervention, groupée par PHASE (avant/pendant/après). `obligatoire`
    pilote l'application F8 : une intervention ne peut passer à « Terminée » tant
    qu'un créneau obligatoire n'a pas au moins une photo.

    Les défauts sont semés au standard de documentation d'un chantier solaire.
    `protege` verrouille un créneau système contre la suppression. Additif —
    company-scopé, aucune migration destructive."""

    class Phase(models.TextChoices):
        AVANT = 'avant', 'Avant'
        PENDANT = 'pendant', 'Pendant'
        APRES = 'apres', 'Après'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shotlist_slots')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    phase = models.CharField(
        max_length=8, choices=Phase.choices, default=Phase.AVANT)
    # F8 — une photo de ce créneau est requise pour terminer l'intervention.
    obligatoire = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Créneau de shot list'
        verbose_name_plural = 'Créneaux de shot list'

    def __str__(self):
        return f'{self.get_phase_display()} · {self.libelle}'


# ── F5 — Liste de préparation d'une intervention ─────────────────────────────
class InterventionPreparation(models.Model):
    """F5 — liste de préparation PROPRE à une intervention (une seule par
    intervention). Le matériel provient de la nomenclature gelée du chantier
    (`Installation.bom`, copiée du devis) ; les outils proviennent du kit
    d'outillage sélectionné. La confirmation « Tout est chargé » (`tout_charge`)
    est requise AVANT que l'intervention puisse quitter « À préparer ». Additif —
    company-scopé, posé côté serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='intervention_preparations')
    intervention = models.OneToOneField(
        Intervention, on_delete=models.CASCADE, related_name='preparation')
    # Kit d'outillage sélectionné (apps.outillage.KitOutillage). SET_NULL : si le
    # kit est supprimé, la préparation et ses lignes outils restent.
    kit = models.ForeignKey(
        'outillage.KitOutillage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparations')
    # F5 — confirmation « Tout est chargé ». Garde la transition de statut.
    tout_charge = models.BooleanField(default=False)
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparations_confirmees')
    confirme_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Préparation d'intervention"
        verbose_name_plural = "Préparations d'intervention"
        ordering = ['intervention_id']

    def __str__(self):
        return f'Préparation · intervention {self.intervention_id}'


class PreparationMaterielLigne(models.Model):
    """F5 — une ligne MATÉRIEL de la préparation : quantité requise (issue de la
    nomenclature gelée du chantier) + une case « chargé ». `manquant` lie le
    flux Besoin matériel / brouillon de bon de commande existant (un manque =
    une rupture sur le disponible du SKU). Le produit catalogue est optionnel
    (les lignes libres restent traçables par désignation)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='preparation_materiel_lignes')
    preparation = models.ForeignKey(
        InterventionPreparation, on_delete=models.CASCADE,
        related_name='materiel')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparation_lignes')
    designation = models.CharField(max_length=255)
    quantite_requise = models.PositiveIntegerField(default=0)
    charge = models.BooleanField(default=False)
    # F5 — drapeau de pénurie au moment de la préparation (disponible < requis).
    manquant = models.BooleanField(default=False)
    quantite_manquante = models.PositiveIntegerField(default=0)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Ligne matériel de préparation'
        verbose_name_plural = 'Lignes matériel de préparation'

    def __str__(self):
        return f'{self.designation} × {self.quantite_requise}'


class PreparationOutilLigne(models.Model):
    """F5 — une ligne OUTIL de la préparation : un outil du kit sélectionné, avec
    une case « coché » (chargé dans la camionnette). Référence un outil du
    catalogue Outillage (SET_NULL si l'outil est retiré du parc)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='preparation_outil_lignes')
    preparation = models.ForeignKey(
        InterventionPreparation, on_delete=models.CASCADE,
        related_name='outils')
    outil = models.ForeignKey(
        'outillage.Outillage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparation_lignes')
    libelle = models.CharField(max_length=255)
    coche = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Ligne outil de préparation'
        verbose_name_plural = 'Lignes outil de préparation'

    def __str__(self):
        return f'{self.libelle} · {"✓" if self.coche else "—"}'


# ── F9 — Saisie de n° de série par composant (étapes Pendant/Après) ──────────
class ComponentSerial(models.Model):
    """F9 — n° de série d'un composant relevé pendant une intervention, avec une
    photo OPTIONNELLE de la plaque signalétique (via la pièce jointe générique)
    et une éventuelle extraction OCR (interface SWAPPABLE, no-op par défaut).

    Le n° de série PEUT être vide : la saisie ne bloque JAMAIS la complétion
    d'une étape ni de l'intervention. À la validation, ces relevés alimentent le
    parc installé (sav.Equipement), exactement comme la checklist chantier (N9).
    Additif — company-scopé, posé côté serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='component_serials')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='serials')
    # Produit catalogue concerné (onduleur, panneau…). Optionnel : un composant
    # hors catalogue reste traçable par sa désignation libre.
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='component_serials')
    designation = models.CharField(max_length=255, blank=True, default='')
    # Le créneau de shot list / l'étape où la plaque est photographiée (clé).
    slot_cle = models.CharField(max_length=40, blank=True, default='')
    numero_serie = models.CharField(max_length=120, blank=True, default='')
    # Photo de la plaque (records.Attachment) — clé MinIO, jamais commitée.
    plaque_attachment = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    # True si le n° de série a été proposé par l'OCR (sinon saisie manuelle).
    serie_ocr = models.BooleanField(default=False)
    # True une fois ce relevé poussé vers le parc installé (sav.Equipement),
    # pour ne jamais créer deux fois le même équipement.
    pousse_parc = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'N° de série de composant'
        verbose_name_plural = 'N° de série de composants'
        ordering = ['intervention_id', 'id']

    def __str__(self):
        return f'{self.designation or self.produit_id} · {self.numero_serie or "—"}'


# ── F10 — Annotation d'une photo (dessin + légende pour signaler un défaut) ───
class PhotoAnnotation(models.Model):
    """F10 — annotation d'une photo d'intervention : un calque de dessin simple
    (tracés vectoriels JSON) + une légende texte, pour signaler un problème. Fait
    partie de l'enregistrement de la photo (lié à records.Attachment). Le calque
    est stocké en JSON (lignes/flèches/rectangles relatifs) — aucune nouvelle
    dépendance d'image. Additif — company-scopé."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='photo_annotations')
    attachment = models.OneToOneField(
        'records.Attachment', on_delete=models.CASCADE,
        related_name='annotation')
    # Calque de dessin : liste d'objets {type, points/coords, couleur}. Vide =
    # pas de dessin (seule la légende compte).
    drawing = models.JSONField(default=list, blank=True)
    caption = models.TextField(blank=True, default='')
    # F10 — drapeau « problème signalé » (une annotation peut juste légender).
    probleme = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Annotation de photo'
        verbose_name_plural = 'Annotations de photo'
        ordering = ['-date_modification']

    def __str__(self):
        return f'Annotation · pièce {self.attachment_id}'


# ── F11/F12 — Réconciliation du matériel consommé ────────────────────────────
class MaterielConsommation(models.Model):
    """F11 — réconciliation du matériel consommé d'une intervention (une par
    intervention). Liste chaque ligne de la nomenclature (prévu) face au
    réellement utilisé, autorise des lignes hors-nomenclature, et exige une
    justification dès qu'utilisé ≠ prévu. À la validation, la consommation
    RÉELLE (et non l'estimation du devis) pilote les mouvements de stock du
    chantier et la marge job-costing. Les prix d'achat restent internes."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='materiel_consommations')
    intervention = models.OneToOneField(
        Intervention, on_delete=models.CASCADE, related_name='consommation')
    valide = models.BooleanField(default=False)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    valide_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réconciliation matériel consommé'
        verbose_name_plural = 'Réconciliations matériel consommé'
        ordering = ['intervention_id']

    def __str__(self):
        return f'Consommation · intervention {self.intervention_id}'


class ConsommationLigne(models.Model):
    """F11 — une ligne de la réconciliation : prévu (nomenclature) vs utilisé.
    `hors_nomenclature` marque une ligne ajoutée sur le terrain (câble, vis,
    MC4…). La justification (texte OU mémo vocal) est requise quand utilisé ≠
    prévu — vérifié au service, pas au modèle. La consommation réelle de cette
    ligne (sur SKU catalogue) pilote le mouvement de stock à la validation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='consommation_lignes')
    consommation = models.ForeignKey(
        MaterielConsommation, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consommation_lignes')
    designation = models.CharField(max_length=255)
    quantite_prevue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    quantite_utilisee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    hors_nomenclature = models.BooleanField(default=False)
    justification = models.TextField(blank=True, default='')
    # Mémo vocal de justification (F13) — lien optionnel vers un VoiceMemo.
    justification_memo = models.ForeignKey(
        'installations.VoiceMemo', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    # True une fois la consommation réelle de cette ligne portée au stock, pour
    # garantir l'idempotence (jamais deux mouvements pour la même ligne).
    stock_applique = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de consommation'
        verbose_name_plural = 'Lignes de consommation'
        ordering = ['ordre', 'id']

    def __str__(self):
        return f'{self.designation} · {self.quantite_utilisee}/{self.quantite_prevue}'

    @property
    def variance(self):
        """Écart utilisé − prévu (Decimal)."""
        return (self.quantite_utilisee or 0) - (self.quantite_prevue or 0)


# ── F13/F14 — Mémo vocal + transcription (interface swappable, no-op) ─────────
class VoiceMemo(models.Model):
    """F13 — mémo vocal enregistré sur le terrain, stocké via la pièce jointe
    générique (records.Attachment → MinIO, jamais commité). Rattachable n'importe
    où sur une intervention : note générale, note sur une photo, justification de
    variance, ou note sur une réserve (via `cible`). F14 — la transcription est
    posée par l'interface SWAPPABLE : tant qu'aucun fournisseur n'est configuré,
    `transcript` = « Non transcrit — service non configuré » et `transcrit`=False.
    L'audio reste la source de vérité ; le transcript est éditable."""
    class Cible(models.TextChoices):
        GENERAL = 'general', 'Note générale'
        PHOTO = 'photo', 'Note sur photo'
        VARIANCE = 'variance', 'Justification de variance'
        RESERVE = 'reserve', 'Note sur réserve'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='voice_memos')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='voice_memos')
    cible = models.CharField(
        max_length=12, choices=Cible.choices, default=Cible.GENERAL)
    # Audio stocké (records.Attachment) — clé MinIO. SET_NULL : la suppression
    # de la pièce jointe ne perd pas l'historique de transcription.
    audio = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    transcript = models.TextField(blank=True, default='')
    # F14 — True seulement si un fournisseur a réellement transcrit. Le no-op
    # laisse False et le libellé « Non transcrit — service non configuré ».
    transcrit = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mémo vocal'
        verbose_name_plural = 'Mémos vocaux'
        ordering = ['-date_creation', 'id']

    def __str__(self):
        return f'Mémo · intervention {self.intervention_id} ({self.cible})'


# ── F16 — Réserves (punch-list) d'une intervention ───────────────────────────
class Reserve(models.Model):
    """F16 — réserve (point de finition à reprendre) d'une intervention :
    description, photo optionnelle, mémo vocal optionnel, assigné, résolution.
    Peut faire naître une intervention de suivi OU un ticket SAV (liens
    optionnels). Additif — company-scopé."""
    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        RESOLUE = 'resolue', 'Résolue'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reserves')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='reserves')
    description = models.TextField(blank=True, default='')
    photo = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    memo = models.ForeignKey(
        'installations.VoiceMemo', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reserves_assignees')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERTE)
    resolution = models.TextField(blank=True, default='')
    resolue_le = models.DateTimeField(null=True, blank=True)
    # F16 — suivi engendré (optionnel) : intervention de suivi et/ou ticket SAV.
    suivi_intervention = models.ForeignKey(
        Intervention, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reserves_origine')
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reserves')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réserve'
        verbose_name_plural = 'Réserves'
        ordering = ['statut', '-date_creation']

    def __str__(self):
        return f'Réserve · intervention {self.intervention_id} ({self.statut})'


# ── F17 — Réconciliation du retour d'outillage ───────────────────────────────
class ToolReturn(models.Model):
    """F17 — état du retour d'un outil du kit à la clôture d'une intervention :
    rendu (oui/non) + emplacement de retour. À la confirmation, met à jour le
    statut + l'emplacement de l'outil dans le catalogue Outillage. Un outil non
    rendu est signalé (statut maintenu « En intervention »)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tool_returns')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='tool_returns')
    outil = models.ForeignKey(
        'outillage.Outillage', on_delete=models.CASCADE,
        related_name='tool_returns')
    rendu = models.BooleanField(default=False)
    emplacement_retour = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    note = models.CharField(max_length=255, blank=True, default='')
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    confirme_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Retour d\'outil'
        verbose_name_plural = 'Retours d\'outils'
        ordering = ['intervention_id', 'id']
        unique_together = [('intervention', 'outil')]

    def __str__(self):
        return f'{self.outil_id} · {"rendu" if self.rendu else "non rendu"}'


# ── F18 — Consignes de sécurité (checklist configurable + sign-off) ──────────
class SafetyChecklistSlot(models.Model):
    """F18 — point d'une checklist de consignes de sécurité, éditable dans
    Paramètres. Défauts semés (EPI portés, consignation électrique).
    `protege` verrouille un point système. Additif — company-scopé."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='safety_slots')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Consigne de sécurité'
        verbose_name_plural = 'Consignes de sécurité'

    def __str__(self):
        return self.libelle


class SafetySignoff(models.Model):
    """F18 — sign-off des consignes de sécurité pour une intervention (un par
    intervention). Coche chaque point de la checklist, avec qui + quand (patron
    d'audit existant)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='safety_signoffs')
    intervention = models.OneToOneField(
        Intervention, on_delete=models.CASCADE, related_name='safety_signoff')
    signe = models.BooleanField(default=False)
    signe_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    signe_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sign-off sécurité'
        verbose_name_plural = 'Sign-offs sécurité'
        ordering = ['intervention_id']

    def __str__(self):
        return f'Sécurité · intervention {self.intervention_id}'


class SafetyCheckItem(models.Model):
    """F18 — état d'un point de consigne de sécurité pour une intervention :
    coché / par qui / quand. Matérialisé depuis les points actifs à la première
    consultation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='safety_check_items')
    signoff = models.ForeignKey(
        SafetySignoff, on_delete=models.CASCADE, related_name='items')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(default=0)
    coche = models.BooleanField(default=False)
    coche_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    coche_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('signoff', 'cle')]
        verbose_name = 'Point de consigne (intervention)'
        verbose_name_plural = 'Points de consigne (intervention)'

    def __str__(self):
        return f'{self.libelle} · {"✓" if self.coche else "—"}'
