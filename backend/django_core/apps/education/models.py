"""Modèles de l'app éducation (``apps.education``) — établissements scolaires.

Vertical NTEDU : structure année/niveau/classe, dossier famille/élève,
inscriptions (avec liste d'attente), scolarité (grille tarifaire, remises
fratrie/bourse, échéancier), présences par séance, matières et coefficients.
Multi-société : chaque modèle hérite de ``core.models.TenantModel`` (FK
``company`` posée côté serveur, jamais lue du corps de requête).

FONDATIONS (NTEDU1-3 — ``AnneeScolaire``/``Niveau``/``Classe``/``Famille``/
``Eleve``/``Inscription``) sont posées ICI, prérequis direct des tâches
NTEDU4-8/12-14 de ce lot (aucune ne peut exister sans le socle structurel de
l'app) ; elles restent volontairement MINIMALES — pièces jointes GED
(``ged.Document`` via ``ged/services.py``), workflow d'inscription complet
(actions ``valider``/``refuser``/``affecter_classe``) et écrans dédiés sont
le périmètre exact du reste du groupe NTEDU, hors de ce lot.

Cross-app : ``enseignant``/``enseignant_principal`` référencent
``rh.DossierEmploye`` et ``photo`` référence ``records.Attachment`` PAR FK À
CHAÎNE (jamais d'import direct des modèles `rh`/`records`), conformément à la
règle de frontière cross-app.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TenantModel


# =============================================================================
# NTEDU1 — Structure année scolaire / niveau / classe.
# =============================================================================

class AnneeScolaire(TenantModel):
    """NTEDU1 — année scolaire (ex. « 2026-2027 »). Une seule active par
    société (contrainte partielle sur ``statut='active'``)."""

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ARCHIVEE = 'archivee', 'Archivée'

    libelle = models.CharField(max_length=30, verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin = models.DateField(verbose_name='Date de fin')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIVE,
        verbose_name='Statut')

    class Meta:
        verbose_name = 'Année scolaire'
        verbose_name_plural = 'Années scolaires'
        ordering = ['-date_debut']
        constraints = [
            models.UniqueConstraint(
                fields=['company'], condition=Q(statut='active'),
                name='education_une_annee_active_par_societe'),
        ]

    def __str__(self):
        return self.libelle


class Niveau(TenantModel):
    """NTEDU1 — niveau scolaire (ex. « CP », « 6ème »), avec un ordre de
    progression utilisé par la réinscription en masse (NTEDU4) pour proposer
    le niveau supérieur."""

    class Cycle(models.TextChoices):
        PRESCOLAIRE = 'prescolaire', 'Préscolaire'
        PRIMAIRE = 'primaire', 'Primaire'
        COLLEGE = 'college', 'Collège'
        LYCEE = 'lycee', 'Lycée'
        FORMATION = 'formation', 'Formation'

    nom = models.CharField(max_length=50, verbose_name='Nom')
    cycle = models.CharField(
        max_length=15, choices=Cycle.choices, verbose_name='Cycle')
    ordre = models.PositiveIntegerField(
        default=0, verbose_name='Ordre de progression')

    class Meta:
        verbose_name = 'Niveau'
        verbose_name_plural = 'Niveaux'
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Classe(TenantModel):
    """NTEDU1 — classe (ex. « 6ème A ») d'une année scolaire donnée.
    ``enseignant_principal`` référence ``rh.DossierEmploye`` par FK à chaîne
    (jamais d'import direct de ``apps.rh.models``)."""

    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='classes',
        verbose_name='Année scolaire')
    niveau = models.ForeignKey(
        Niveau, on_delete=models.PROTECT, related_name='classes',
        verbose_name='Niveau')
    nom = models.CharField(max_length=50, verbose_name='Nom')
    capacite_max = models.PositiveIntegerField(
        default=30, verbose_name='Capacité maximale')
    enseignant_principal = models.ForeignKey(
        'rh.DossierEmploye', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='classes_principales', verbose_name='Enseignant principal')
    salle = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Salle')

    class Meta:
        verbose_name = 'Classe'
        verbose_name_plural = 'Classes'
        ordering = ['annee_scolaire', 'niveau__ordre', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.annee_scolaire.libelle})"

    @property
    def effectif(self):
        """Effectif courant (élèves affectés à cette classe)."""
        return self.eleves.count()


# =============================================================================
# NTEDU2 — Famille + Élève.
# =============================================================================

class Famille(TenantModel):
    """NTEDU2 — dossier famille (contacts des parents)."""

    nom = models.CharField(max_length=150, verbose_name='Nom de famille')
    parent1_nom = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Parent 1 — nom')
    parent1_telephone = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Parent 1 — téléphone')
    parent1_whatsapp = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Parent 1 — WhatsApp')
    parent1_email = models.EmailField(
        blank=True, default='', verbose_name='Parent 1 — email')
    parent2_nom = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Parent 2 — nom')
    parent2_telephone = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Parent 2 — téléphone')
    parent2_whatsapp = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Parent 2 — WhatsApp')
    parent2_email = models.EmailField(
        blank=True, default='', verbose_name='Parent 2 — email')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')

    class Meta:
        verbose_name = 'Famille'
        verbose_name_plural = 'Familles'
        ordering = ['nom']

    def __str__(self):
        return self.nom

    @property
    def enfants_actifs(self):
        """Enfants inscrits activement (statut inscrit/réinscrit) — utilisé par
        la détection automatique de remise fratrie (NTEDU7)."""
        return self.eleves.filter(
            statut__in=[Eleve.Statut.INSCRIT, Eleve.Statut.REINSCRIT])


class Eleve(TenantModel):
    """NTEDU2 — élève. ``numero_dossier`` est attribué côté serveur à la
    création via ``core.numbering`` (plus-haut-utilisé+1 par société, jamais
    ``count()+1``). ``photo`` référence ``records.Attachment`` par FK à
    chaîne (magasin de fichiers déjà existant, jamais un second)."""

    class Sexe(models.TextChoices):
        M = 'M', 'Masculin'
        F = 'F', 'Féminin'

    class Statut(models.TextChoices):
        PROSPECT = 'prospect', 'Prospect'
        INSCRIT = 'inscrit', 'Inscrit'
        REINSCRIT = 'reinscrit', 'Réinscrit'
        RADIE = 'radie', 'Radié'
        DIPLOME = 'diplome', 'Diplômé'

    famille = models.ForeignKey(
        Famille, on_delete=models.CASCADE, related_name='eleves',
        verbose_name='Famille')
    nom = models.CharField(max_length=150, verbose_name='Nom')
    prenom = models.CharField(max_length=150, verbose_name='Prénom')
    date_naissance = models.DateField(
        null=True, blank=True, verbose_name='Date de naissance')
    sexe = models.CharField(
        max_length=1, choices=Sexe.choices, blank=True, default='',
        verbose_name='Sexe')
    cin = models.CharField(
        max_length=30, blank=True, default='', verbose_name="CIN / numéro d'identité")
    photo = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eleves_photo', verbose_name='Photo')
    classe = models.ForeignKey(
        Classe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eleves', verbose_name='Classe')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.PROSPECT,
        verbose_name='Statut')
    numero_dossier = models.CharField(
        max_length=30, blank=True, default='', db_index=True,
        verbose_name='Numéro de dossier')

    class Meta:
        verbose_name = 'Élève'
        verbose_name_plural = 'Élèves'
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    @property
    def actif(self):
        return self.statut in (self.Statut.INSCRIT, self.Statut.REINSCRIT)


# =============================================================================
# NTEDU3 — Inscription.
# =============================================================================

class Inscription(TenantModel):
    """NTEDU3 — inscription d'un élève sur une année scolaire. Une inscription
    validée sur une classe pleine (``effectif >= capacite_max``) bascule
    automatiquement en ``liste_attente`` avec une position calculée FIFO
    (NTEDU5). ``position_liste_attente`` est recalculé par
    ``services.recalculer_liste_attente`` — jamais lu tel quel côté client
    sans recalcul serveur."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        VALIDEE = 'validee', 'Validée'
        REFUSEE = 'refusee', 'Refusée'
        LISTE_ATTENTE = "liste_attente", "Liste d'attente"

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='inscriptions',
        verbose_name='Élève')
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='inscriptions',
        verbose_name='Année scolaire')
    classe_demandee = models.ForeignKey(
        Classe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inscriptions_demandees', verbose_name='Classe demandée')
    classe_affectee = models.ForeignKey(
        Classe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inscriptions_affectees', verbose_name='Classe affectée')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut')
    date_demande = models.DateField(
        auto_now_add=True, verbose_name='Date de demande')
    date_decision = models.DateField(
        null=True, blank=True, verbose_name='Date de décision')
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='education_inscriptions_decidees', verbose_name='Décidé par')
    position_liste_attente = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Position en liste d'attente")

    class Meta:
        verbose_name = 'Inscription'
        verbose_name_plural = 'Inscriptions'
        ordering = ['-date_demande']

    def __str__(self):
        return f"{self.eleve} — {self.annee_scolaire}"


# =============================================================================
# NTEDU6 — Grille tarifaire par niveau.
# =============================================================================

class GrilleTarifaire(TenantModel):
    """NTEDU6 — grille tarifaire d'un niveau pour une année scolaire. Une
    seule ligne ACTIVE par (annee_scolaire, niveau) — contrainte unique
    partielle sur ``active=True`` (une grille désactivée peut être conservée
    en historique sans violer la contrainte)."""

    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='grilles_tarifaires',
        verbose_name='Année scolaire')
    niveau = models.ForeignKey(
        Niveau, on_delete=models.CASCADE, related_name='grilles_tarifaires',
        verbose_name='Niveau')
    frais_inscription = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name="Frais d'inscription")
    scolarite_annuelle = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Scolarité annuelle')
    transport_mensuel = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Transport mensuel')
    cantine_mensuelle = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Cantine mensuelle')
    activites_annuelles = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Activités annuelles')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Grille tarifaire'
        verbose_name_plural = 'Grilles tarifaires'
        ordering = ['annee_scolaire', 'niveau__ordre']
        constraints = [
            models.UniqueConstraint(
                fields=['annee_scolaire', 'niveau'], condition=Q(active=True),
                name='education_une_grille_active_par_annee_niveau'),
        ]

    def __str__(self):
        return f"{self.niveau} — {self.annee_scolaire}"
