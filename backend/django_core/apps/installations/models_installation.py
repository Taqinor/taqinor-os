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

# NOTE: découpage de l'ancien models.py monolithe (un fichier par
# domaine). app_label, noms de table et Meta inchangés : models.py
# ré-exporte toutes les classes pour la découverte Django + migrations.


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

    # ── CH1 — étape CONFIGURABLE du cycle de vie (gates). Pointeur vers la
    #    définition d'étape de la société (StageModele) ; nullable : un chantier
    #    sans pointeur dérive son étape du statut hérité via le mapping des
    #    services (aucune perte de donnée, l'enum `statut` reste la source des
    #    effets de bord existants). SET_NULL : supprimer une étape de la config
    #    ne casse jamais un chantier. Additif. ──
    etape = models.ForeignKey(
        'installations.StageModele', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chantiers')

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
    # ── FG72 — pose multi-jours. ──
    # `date_pose_fin_prevue` est la date de FIN prévue de la pose (> date_pose_prevue
    # pour un chantier multi-jours). `duree_pose_jours` est calculée/éditée à la
    # main ; rendue comme « durée » sur le calendrier chantier. Additif, nullable.
    date_pose_fin_prevue = models.DateField(null=True, blank=True)
    duree_pose_jours = models.PositiveSmallIntegerField(null=True, blank=True)
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
    # FG100 — champs personnalisés (additif, jamais destructif).
    # Les définitions viennent de apps.customfields (module='installation').
    custom_data = models.JSONField(null=True, blank=True)

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
