"""
Couche GESTION DE PROJET du chantier (Installation).

Trois briques additives, toutes rattachées au chantier pivot
(``Installation``), toutes multi-tenant (FK ``company`` posée côté serveur) :

  * FG293 — ``JalonProjet`` : les jalons/phases de projet
    (étude → appro → pose → MES → réception) avec dates CIBLES et RÉELLES,
    pour suivre l'avancement macro d'un chantier au-delà de la checklist
    d'exécution fine (``ChantierChecklistItem``).
  * FG296 — ``ModeleProjet`` (+ ``ModeleProjetJalon`` / ``ModeleProjetBomLigne``)
    : un patron de « chantier-type » qui pré-crée à la signature les jalons
    standard et une nomenclature (BoM) type. Instancié sur un chantier par
    ``services.instantiate_modele_projet``.
  * FG298 — ``ReunionChantier`` : un compte-rendu de réunion de chantier
    horodaté (ordre du jour / présents / décisions / actions).

Aucune migration destructive : on AJOUTE des tables, on ne touche jamais aux
colonnes existantes. Les statuts du chantier (``Installation.Statut``) restent
la couche d'entonnoir de réalisation ; cette couche projet est INDÉPENDANTE.
"""
from django.conf import settings
from django.db import models

from .models_installation import Installation


# ── FG293 — Jalons & phases de projet ────────────────────────────────────────
class JalonProjet(models.Model):
    """FG293 — jalon (phase) de projet d'un chantier, avec date CIBLE et date
    RÉELLE. Les phases canoniques d'un projet solaire : étude, approvisionnement,
    pose, mise en service, réception. La liste de `Phase` reste OUVERTE (un
    libellé libre est autorisé pour un jalon ad hoc), mais les cinq phases types
    sont pré-câblées et pré-créées par les modèles de projet (FG296).

    Indépendant de la checklist d'exécution fine : un jalon suit l'avancement
    MACRO du projet (« la phase appro est-elle finie ? »), pas chaque geste de
    terrain. Additif, multi-tenant (société posée côté serveur)."""

    class Phase(models.TextChoices):
        ETUDE = 'etude', 'Étude'
        APPRO = 'appro', 'Approvisionnement'
        POSE = 'pose', 'Pose'
        MES = 'mes', 'Mise en service'
        RECEPTION = 'reception', 'Réception'

    # Ordre canonique des phases (pour le tri — jamais alphabétique).
    PHASE_ORDER = [
        Phase.ETUDE, Phase.APPRO, Phase.POSE, Phase.MES, Phase.RECEPTION,
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='jalons_projet')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='jalons')
    # Phase type quand le jalon en est une ; vide pour un jalon ad hoc nommé
    # uniquement par `libelle`.
    phase = models.CharField(
        max_length=12, choices=Phase.choices, blank=True, null=True)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    # Dates CIBLES (planifiées) vs RÉELLES (constatées). Le jalon est « atteint »
    # quand `date_reelle` est posée — le drapeau `atteint` est dérivé/explicite.
    date_cible = models.DateField(null=True, blank=True)
    date_reelle = models.DateField(null=True, blank=True)
    atteint = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    # YSERV7 — tranche de l'échéancier devis (ventes.Facture.TypeFacture) que
    # l'atteinte de CE jalon doit rappeler de facturer. Vide = jalon non lié à
    # une tranche (comportement historique inchangé, aucun rappel émis).
    # Choix en dur volontairement limités à acompte/intermediaire/solde (jamais
    # `complete`, réservé aux factures classiques hors échéancier) — string
    # libre pour éviter un import du modèle ventes depuis installations.
    TRANCHE_ACOMPTE = 'acompte'
    TRANCHE_INTERMEDIAIRE = 'intermediaire'
    TRANCHE_SOLDE = 'solde'
    TRANCHE_CHOICES = [
        (TRANCHE_ACOMPTE, 'Acompte'),
        (TRANCHE_INTERMEDIAIRE, 'Intermédiaire'),
        (TRANCHE_SOLDE, 'Solde'),
    ]
    tranche_echeancier = models.CharField(
        max_length=20, choices=TRANCHE_CHOICES, blank=True, null=True)
    # YSERV7 — garde d'idempotence : une seule notification de rappel par
    # jalon (jamais deux nudges pour la même atteinte).
    rappel_facturation_envoye = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jalon de projet'
        verbose_name_plural = 'Jalons de projet'
        ordering = ['installation_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'installation']),
        ]

    def __str__(self):
        return f'{self.installation_id} · {self.libelle}'


# ── FG296 — Modèles de projet (templates de chantier-type) ───────────────────
class ModeleProjet(models.Model):
    """FG296 — patron de « chantier-type » : un modèle de projet qui, instancié
    sur un chantier (à la signature ou à la demande), pré-crée les jalons
    standard (`ModeleProjetJalon`) et une nomenclature type (`ModeleProjetBomLigne`).

    Peut viser un `type_installation` (résidentiel / industriel / agricole) pour
    être proposé par défaut au bon type de chantier. Additif, multi-tenant
    (société posée côté serveur). L'instanciation vit dans
    `services.instantiate_modele_projet` (idempotente, additive)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='modeles_projet')
    nom = models.CharField(max_length=120)
    type_installation = models.CharField(
        max_length=20, choices=Installation.TypeInstallation.choices,
        blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Modèle de projet'
        verbose_name_plural = 'Modèles de projet'
        ordering = ['nom']
        unique_together = [('company', 'nom')]

    def __str__(self):
        return self.nom


class ModeleProjetJalon(models.Model):
    """FG296 — jalon TYPE d'un modèle de projet. Pré-crée un `JalonProjet` sur
    le chantier à l'instanciation, avec un décalage en jours (`offset_jours`)
    appliqué à une date de base (la date de signature, à défaut aujourd'hui)
    pour pré-remplir `date_cible`."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='modele_projet_jalons')
    modele = models.ForeignKey(
        ModeleProjet, on_delete=models.CASCADE, related_name='jalons')
    phase = models.CharField(
        max_length=12, choices=JalonProjet.Phase.choices, blank=True, null=True)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    # Décalage (jours) à partir de la date de base pour pré-remplir la date cible
    # du jalon créé (ex. appro = +7 j, pose = +21 j…).
    offset_jours = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Jalon type de modèle de projet'
        verbose_name_plural = 'Jalons type de modèle de projet'
        ordering = ['modele_id', 'ordre', 'id']

    def __str__(self):
        return f'{self.modele_id} · {self.libelle}'


class ModeleProjetBomLigne(models.Model):
    """FG296 — ligne de nomenclature (BoM) TYPE d'un modèle de projet. À
    l'instanciation, elle est ajoutée à la nomenclature gelée du chantier
    (`Installation.bom`, un JSON) sans jamais écraser une ligne déjà présente
    pour le même produit. `produit` est une string-FK (catalogue stock) : le
    couplage cross-app reste lâche."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='modele_projet_bom_lignes')
    modele = models.ForeignKey(
        ModeleProjet, on_delete=models.CASCADE, related_name='bom_lignes')
    # Référence catalogue par string-FK (jamais d'import des modèles stock).
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modele_projet_bom_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de BoM type de modèle de projet'
        verbose_name_plural = 'Lignes de BoM type de modèle de projet'
        ordering = ['modele_id', 'ordre', 'id']

    def __str__(self):
        return f'{self.modele_id} · {self.designation or self.produit_id}'


# ── FG298 — Comptes-rendus de réunion de chantier ────────────────────────────
class ReunionChantier(models.Model):
    """FG298 — compte-rendu de réunion de chantier, horodaté et rattaché au
    chantier. Porte l'ordre du jour, les présents (texte libre), les décisions
    et les actions décidées. Additif, multi-tenant (société + auteur posés côté
    serveur)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reunions_chantier')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='reunions')
    titre = models.CharField(max_length=200, blank=True, null=True)
    # Date/heure de la réunion (saisie) ; distincte de l'horodatage de création.
    date_reunion = models.DateTimeField(null=True, blank=True)
    ordre_du_jour = models.TextField(blank=True, null=True)
    presents = models.TextField(blank=True, null=True)
    decisions = models.TextField(blank=True, null=True)
    actions = models.TextField(blank=True, null=True)
    redige_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reunions_chantier_redigees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compte-rendu de réunion de chantier'
        verbose_name_plural = 'Comptes-rendus de réunion de chantier'
        ordering = ['-date_reunion', '-date_creation']
        indexes = [
            models.Index(fields=['company', 'installation']),
        ]

    def __str__(self):
        return f'{self.installation_id} · {self.titre or "Réunion"}'
