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
        AnneeScolaire, on_delete=models.CASCADE, related_name='classes',  # on_delete: composition (parent-enfant)
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
        Famille, on_delete=models.CASCADE, related_name='eleves',  # on_delete: composition (parent-enfant)
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
        Eleve, on_delete=models.CASCADE, related_name='inscriptions',  # on_delete: composition (parent-enfant)
        verbose_name='Élève')
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='inscriptions',  # on_delete: composition (parent-enfant)
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
        AnneeScolaire, on_delete=models.CASCADE, related_name='grilles_tarifaires',  # on_delete: composition (parent-enfant)
        verbose_name='Année scolaire')
    niveau = models.ForeignKey(
        Niveau, on_delete=models.CASCADE, related_name='grilles_tarifaires',  # on_delete: composition (parent-enfant)
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


# =============================================================================
# NTEDU7 — Remises fratrie et bourses.
# =============================================================================

class Remise(TenantModel):
    """NTEDU7 — remise (fratrie/bourse/autre) appliquée à l'échéancier
    (NTEDU8). Reste ``brouillon`` tant qu'elle n'est pas explicitement
    ``approuvee`` — la remise fratrie détectée automatiquement (``services_
    remises.detecter_remise_fratrie``) n'est JAMAIS auto-appliquée sans
    validation."""

    class Type(models.TextChoices):
        FRATRIE = 'fratrie', 'Fratrie'
        BOURSE = 'bourse', 'Bourse'
        AUTRE = 'autre', 'Autre'

    class Mode(models.TextChoices):
        POURCENTAGE = 'pourcentage', 'Pourcentage'
        MONTANT_FIXE = 'montant_fixe', 'Montant fixe'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        APPROUVEE = 'approuvee', 'Approuvée'
        REJETEE = 'rejetee', 'Rejetée'

    famille = models.ForeignKey(
        Famille, on_delete=models.CASCADE, null=True, blank=True,  # on_delete: composition (parent-enfant)
        related_name='remises', verbose_name='Famille')
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, null=True, blank=True,  # on_delete: composition (parent-enfant)
        related_name='remises', verbose_name='Élève')
    type = models.CharField(
        max_length=10, choices=Type.choices, verbose_name='Type')
    mode = models.CharField(
        max_length=15, choices=Mode.choices, default=Mode.POURCENTAGE,
        verbose_name='Mode')
    valeur = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Valeur')
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    valable_annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='remises',  # on_delete: composition (parent-enfant)
        verbose_name='Année scolaire')
    justificatif = models.ForeignKey(
        'ged.Document', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='remises_education', verbose_name='Justificatif (GED)')
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='education_remises_approuvees', verbose_name='Approuvé par')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')

    class Meta:
        verbose_name = 'Remise'
        verbose_name_plural = 'Remises'
        ordering = ['-id']

    def __str__(self):
        cible = self.eleve or self.famille
        return f"{self.get_type_display()} — {cible}"


# =============================================================================
# NTEDU8 — Échéancier de scolarité.
# =============================================================================

class EcheancierScolarite(TenantModel):
    """NTEDU8 — échéancier de scolarité d'un élève pour une année scolaire,
    généré automatiquement à la validation de l'inscription (``services_
    echeancier.generer_echeancier``)."""

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='echeanciers',  # on_delete: composition (parent-enfant)
        verbose_name='Élève')
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='echeanciers',  # on_delete: composition (parent-enfant)
        verbose_name='Année scolaire')
    grille_tarifaire = models.ForeignKey(
        GrilleTarifaire, on_delete=models.PROTECT, related_name='echeanciers',
        verbose_name='Grille tarifaire')
    remises = models.ManyToManyField(
        Remise, blank=True, related_name='echeanciers',
        verbose_name='Remises appliquées')
    montant_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant total')
    nombre_echeances = models.PositiveIntegerField(
        default=10, verbose_name="Nombre d'échéances")

    class Meta:
        verbose_name = 'Échéancier de scolarité'
        verbose_name_plural = 'Échéanciers de scolarité'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['eleve', 'annee_scolaire'],
                name='education_un_echeancier_par_eleve_annee'),
        ]

    def __str__(self):
        return f"Échéancier {self.eleve} — {self.annee_scolaire}"


class LigneEcheance(TenantModel):
    """NTEDU8 — ligne d'échéance mensuelle d'un échéancier."""

    class Statut(models.TextChoices):
        A_VENIR = 'a_venir', 'À venir'
        FACTUREE = 'facturee', 'Facturée'
        PAYEE = 'payee', 'Payée'
        EN_RETARD = 'en_retard', 'En retard'

    echeancier = models.ForeignKey(
        EcheancierScolarite, on_delete=models.CASCADE, related_name='lignes',  # on_delete: composition (parent-enfant)
        verbose_name='Échéancier')
    libelle = models.CharField(max_length=150, verbose_name='Libellé')
    montant = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_VENIR,
        verbose_name='Statut')

    class Meta:
        verbose_name = "Ligne d'échéance"
        verbose_name_plural = "Lignes d'échéance"
        ordering = ['date_echeance']

    def __str__(self):
        return f"{self.libelle} ({self.date_echeance})"


# =============================================================================
# NTEDU12 — Présences/absences par séance.
# =============================================================================

class Seance(TenantModel):
    """NTEDU12 — séance de cours d'une classe. ``matiere`` reste un libellé
    libre à ce stade (l'app expose par ailleurs le référentiel structuré
    ``Matiere``/``MatiereClasse`` — NTEDU14 — pour les coefficients ; les
    séances n'ont pas besoin d'y être liées pour la saisie de présence)."""

    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE, related_name='seances',  # on_delete: composition (parent-enfant)
        verbose_name='Classe')
    matiere = models.CharField(max_length=100, verbose_name='Matière')
    enseignant = models.ForeignKey(
        'rh.DossierEmploye', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='seances', verbose_name='Enseignant')
    date = models.DateField(verbose_name='Date')
    heure_debut = models.TimeField(verbose_name='Heure de début')
    heure_fin = models.TimeField(verbose_name='Heure de fin')
    salle = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Salle')

    class Meta:
        verbose_name = 'Séance'
        verbose_name_plural = 'Séances'
        ordering = ['-date', '-heure_debut']

    def __str__(self):
        return f"{self.classe} — {self.matiere} ({self.date})"


class Presence(TenantModel):
    """NTEDU12 — présence d'un élève à une séance. ``justificatif`` référence
    ``ged.Document`` par FK à chaîne (pièce jointe justifiant une absence)."""

    class Statut(models.TextChoices):
        PRESENT = 'present', 'Présent'
        ABSENT = 'absent', 'Absent'
        RETARD = 'retard', 'Retard'
        EXCUSE = 'excuse', 'Excusé'

    seance = models.ForeignKey(
        Seance, on_delete=models.CASCADE, related_name='presences',  # on_delete: composition (parent-enfant)
        verbose_name='Séance')
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='presences',  # on_delete: composition (parent-enfant)
        verbose_name='Élève')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.PRESENT,
        verbose_name='Statut')
    justificatif = models.ForeignKey(
        'ged.Document', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='presences_education', verbose_name='Justificatif (GED)')
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='education_presences_saisies', verbose_name='Saisi par')

    class Meta:
        verbose_name = 'Présence'
        verbose_name_plural = 'Présences'
        ordering = ['-seance__date']
        constraints = [
            models.UniqueConstraint(
                fields=['seance', 'eleve'],
                name='education_presence_unique_par_seance_eleve'),
        ]

    def __str__(self):
        return f"{self.eleve} — {self.seance} — {self.get_statut_display()}"


# =============================================================================
# NTEDU14 — Matières et coefficients.
# =============================================================================

class Matiere(TenantModel):
    """NTEDU14 — matière enseignable (nationale/transverse si ``niveau`` est
    vide, ou spécifique à un niveau)."""

    nom = models.CharField(max_length=100, verbose_name='Nom')
    code = models.CharField(max_length=20, blank=True, default='', verbose_name='Code')
    niveau = models.ForeignKey(
        Niveau, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='matieres', verbose_name='Niveau')

    class Meta:
        verbose_name = 'Matière'
        verbose_name_plural = 'Matières'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class MatiereClasse(TenantModel):
    """NTEDU14 — coefficient d'une matière POUR une classe donnée (jamais
    global) : deux classes du même niveau peuvent porter des coefficients
    différents pour la même matière. ``enseignant`` référence
    ``rh.DossierEmploye`` par FK à chaîne."""

    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE, related_name='matieres_classe',  # on_delete: composition (parent-enfant)
        verbose_name='Classe')
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name='classes_matiere',  # on_delete: composition (parent-enfant)
        verbose_name='Matière')
    enseignant = models.ForeignKey(
        'rh.DossierEmploye', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='matieres_enseignees', verbose_name='Enseignant')
    coefficient = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('1'),
        verbose_name='Coefficient')

    class Meta:
        verbose_name = 'Matière de classe'
        verbose_name_plural = 'Matières de classe'
        ordering = ['classe', 'matiere']
        constraints = [
            models.UniqueConstraint(
                fields=['classe', 'matiere'],
                name='education_coefficient_unique_par_classe_matiere'),
        ]

    def __str__(self):
        return f"{self.matiere} — {self.classe} (coef. {self.coefficient})"


# =============================================================================
# NTEDU15 — Évaluations et notes.
# =============================================================================

class Evaluation(TenantModel):
    """NTEDU15 — évaluation (contrôle/examen/devoir) rattachée à une
    ``MatiereClasse`` (jamais globale : coefficient/barème sont propres à la
    matière ENSEIGNÉE DANS CETTE CLASSE). La saisie en masse des notes
    (``NoteViewSet.bulk_saisie``) est restreinte à l'enseignant de cette
    ``matiere_classe`` (AUTH — ``services.peut_saisir_notes``)."""

    class Type(models.TextChoices):
        CONTROLE = 'controle', 'Contrôle'
        EXAMEN = 'examen', 'Examen'
        DEVOIR = 'devoir', 'Devoir'

    matiere_classe = models.ForeignKey(
        MatiereClasse, on_delete=models.CASCADE, related_name='evaluations',  # on_delete: composition (parent-enfant)
        verbose_name='Matière de classe')
    type = models.CharField(
        max_length=10, choices=Type.choices, default=Type.CONTROLE,
        verbose_name="Type d'évaluation")
    date = models.DateField(verbose_name='Date')
    coefficient_evaluation = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('1'),
        verbose_name="Coefficient de l'évaluation")
    bareme = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20'),
        verbose_name='Barème')

    class Meta:
        verbose_name = 'Évaluation'
        verbose_name_plural = 'Évaluations'
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_type_display()} — {self.matiere_classe} ({self.date})"


class Note(TenantModel):
    """NTEDU15 — note d'un élève à une évaluation. ``valeur`` NULLABLE = élève
    absent à l'évaluation (jamais un 0 fictif qui fausserait une moyenne)."""

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name='notes',  # on_delete: composition (parent-enfant)
        verbose_name='Évaluation')
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='notes',  # on_delete: composition (parent-enfant)
        verbose_name='Élève')
    valeur = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Valeur')
    appreciation = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Appréciation')

    class Meta:
        verbose_name = 'Note'
        verbose_name_plural = 'Notes'
        ordering = ['-evaluation__date']
        constraints = [
            models.UniqueConstraint(
                fields=['evaluation', 'eleve'],
                name='education_note_unique_par_evaluation_eleve'),
        ]

    def __str__(self):
        valeur = self.valeur if self.valeur is not None else 'absent'
        return f"{self.eleve} — {self.evaluation} : {valeur}"


# =============================================================================
# NTEDU18 — Certificat de scolarité.
# =============================================================================

class CertificatScolarite(TenantModel):
    """NTEDU18 — certificat de scolarité généré à la demande. ``numero``
    attribué côté serveur via ``core.numbering`` (plus-haut-utilisé+1 par
    société, JAMAIS ``count()+1`` — même util que ``Eleve.numero_dossier``).
    Contrairement à ``numero_dossier`` (idempotent par élève), CHAQUE appel de
    ``services.generer_certificat_scolarite`` pose une NOUVELLE ligne : deux
    certificats générés le même jour pour deux élèves différents obtiennent
    des numéros distincts et séquentiels."""

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='certificats_scolarite',  # on_delete: composition (parent-enfant)
        verbose_name='Élève')
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='certificats_scolarite',  # on_delete: composition (parent-enfant)
        verbose_name='Année scolaire')
    numero = models.CharField(
        max_length=30, db_index=True, verbose_name='Numéro')
    date_generation = models.DateField(verbose_name='Date de génération')
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='education_certificats_generes', verbose_name='Généré par')

    class Meta:
        verbose_name = 'Certificat de scolarité'
        verbose_name_plural = 'Certificats de scolarité'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'numero'],
                name='education_certificat_numero_unique_par_societe'),
        ]

    def __str__(self):
        return f"{self.numero} — {self.eleve}"
