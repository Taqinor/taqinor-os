"""Modèles des notes de frais & indemnités (``apps.frais``) — ODX15.

Ces modèles vivaient dans ``apps.compta`` (FG135/FG136/ZACC6/XACC27/XACC28).
ODX15 les en sort en **STATE-ONLY** : les migrations sont des
``SeparateDatabaseAndState`` avec ``database_operations=[]`` et chaque modèle
GÈLE son ``db_table`` sur le nom historique ``compta_*`` — aucune table n'est
créée, renommée ou déplacée, aucune donnée ne bouge, et le retour arrière est
un simple ``git revert`` (les migrations inverses sont, elles aussi,
state-only).

FRONTIÈRE (CLAUDE.md) : le POSTING COMPTABLE reste dans ``apps.compta``.
``apps.frais`` ne connaît les comptes/écritures/trésorerie que par des
FK-STRING (``'compta.CompteComptable'``…) et appelle ``apps.compta.services``
pour toute écriture (6143/4432/trésorerie) et pour le verrou de période FG115 ;
il n'importe JAMAIS ``apps.compta.models``.

DOUBLON TRANCHÉ (ODX15, cf. ``docs/module-map.md``) : ``rh.NoteDeFrais``
(déclaration self-service d'un employé du portail RH, aucune écriture) et
``frais.NoteFrais`` (validation + posting GL) sont DEUX surfaces distinctes et
le restent — aucune fusion, aucune 3ᵉ surface.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# ── FG135 — Notes de frais & remboursements employés ───────────────────────

class NoteFrais(models.Model):
    """Note de frais d'un employé : dépense engagée à rembourser (FG135).

    Un employé qui avance du cash sur le terrain (déplacement, repas, carburant,
    petites fournitures…) saisit une note de frais avec un ``justificatif`` photo
    (scan du ticket/reçu) et un ``montant`` TTC. La note suit un cycle de vie :

    * ``brouillon`` — saisie en cours par l'employé ;
    * ``soumise`` — envoyée pour validation ;
    * ``validee`` — approuvée par un responsable (qui POSTE l'écriture de
      constatation de la charge : débit compte de charge classe 6 / crédit du
      compte personnel-créditeur 4432) ; le montant devient une dette envers
      l'employé ;
    * ``rejetee`` — refusée (motif figé) ;
    * ``remboursee`` — l'avance est rendue à l'employé (écriture de paiement :
      débit 4432 / crédit du compte de trésorerie payeur) ; état terminal.

    Strictement additif. ``company`` posée côté serveur, jamais lue du corps de
    requête. L'employé est un ``settings.AUTH_USER_MODEL`` (app fondation
    authentication — import autorisé). Aucun montant d'achat interne (prix
    d'achat/marge) n'apparaît ici.
    """
    class Categorie(models.TextChoices):
        DEPLACEMENT = 'deplacement', 'Déplacement / transport'
        CARBURANT = 'carburant', 'Carburant'
        REPAS = 'repas', 'Repas / restauration'
        HEBERGEMENT = 'hebergement', 'Hébergement'
        FOURNITURES = 'fournitures', 'Petites fournitures'
        PEAGE = 'peage', 'Péage / stationnement'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMISE = 'soumise', 'Soumise'
        VALIDEE = 'validee', 'Validée'
        REJETEE = 'rejetee', 'Rejetée'
        REMBOURSEE = 'remboursee', 'Remboursée'

    class ModeRemboursement(models.TextChoices):
        VIREMENT = 'virement', 'Virement bancaire'
        ESPECES = 'especes', 'Espèces'
        CHEQUE = 'cheque', 'Chèque'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='notes_frais',
        verbose_name='Société',
    )
    # Référence interne par société (NDF-YYYYMM-NNNN), posée côté serveur via
    # apps.ventes.utils.references (highest-used+1, jamais count()+1).
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    # Employé qui a engagé la dépense (créancier une fois la note validée).
    employe = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='notes_frais',
        verbose_name='Employé',
    )
    date_frais = models.DateField(verbose_name='Date de la dépense')
    categorie = models.CharField(
        max_length=15, choices=Categorie.choices,
        default=Categorie.AUTRE, verbose_name='Catégorie')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant (TTC)')
    motif = models.CharField(max_length=255, verbose_name='Motif')
    # Justificatif PHOTO (scan du ticket/reçu) stocké via le storage projet.
    justificatif = models.FileField(
        upload_to='notes_frais/justificatifs/%Y/%m/',
        blank=True, null=True, verbose_name='Justificatif (photo)')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Compte de charge (classe 6) imputé à la validation (défaut 6143).
    compte_charge = models.ForeignKey(
        'compta.CompteComptable',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='notes_frais_charge',
        verbose_name='Compte de charge',
    )
    # ── Validation (constatation de la charge / dette envers l'employé) ──
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes_frais_validees',
        verbose_name='Validée par',
    )
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Validée le')
    ecriture_charge = models.ForeignKey(
        'compta.EcritureComptable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes_frais_charge',
        verbose_name='Écriture de charge',
    )
    motif_rejet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de rejet')
    # ── Remboursement (paiement de l'avance à l'employé) ──
    mode_remboursement = models.CharField(
        max_length=10, choices=ModeRemboursement.choices,
        default=ModeRemboursement.VIREMENT, verbose_name='Mode de remboursement')
    compte_tresorerie = models.ForeignKey(
        'compta.CompteTresorerie',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='notes_frais',
        verbose_name='Compte de trésorerie (payeur)',
    )
    date_remboursement = models.DateField(
        null=True, blank=True, verbose_name='Date de remboursement')
    rembourse_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes_frais_remboursees',
        verbose_name='Remboursée par',
    )
    ecriture_remboursement = models.ForeignKey(
        'compta.EcritureComptable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes_frais_remboursement',
        verbose_name='Écriture de remboursement',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes_frais_creees',
        verbose_name='Saisie par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # ── XACC27 — Politique de plafonds par catégorie ──
    hors_politique = models.BooleanField(
        default=False,
        verbose_name='Hors politique (dépasse le plafond)')
    # ── NTP2P11 — escalade direction + warning de délai ──
    # Posés CÔTÉ SERVEUR à la soumission depuis ``PlafondNoteFrais`` ; jamais
    # lus du corps de la requête. Défauts = comportement historique inchangé.
    escalade_direction = models.BooleanField(
        default=False,
        verbose_name='Validation DIRECTION requise (escalade de montant)')
    warning_delai = models.TextField(
        blank=True, default='',
        verbose_name='Warning de délai (non bloquant, affiché au valideur)')
    # ── XACC28 — Refacturation au client (billable expense) ──
    refacturable = models.BooleanField(
        default=False, verbose_name='Refacturable au client')
    taux_marge = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name='Taux de marge à la refacturation (%)')
    client_refacturation_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Client à refacturer (id crm, string-ref)')
    chantier_refacturation = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Chantier (référence libre)')
    facture_refacturation_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Facture de refacturation (id ventes, string-ref)')
    # ── ZACC6 — Regroupement en UN rapport de frais (Odoo « Expense Report ») ──
    # Nullable : une note SANS rapport garde son cycle actuel intact
    # (soumettre/valider/rembourser individuellement). Une note RATTACHÉE à un
    # rapport est postée/remboursée EN BLOC par le rapport (services du
    # rapport), jamais individuellement une fois rattachée.
    rapport = models.ForeignKey(
        'RapportNoteFrais',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes',
        verbose_name='Rapport de frais',
    )

    class Meta:
        # ODX15 — table PHYSIQUE inchangée (move state-only).
        db_table = 'compta_notefrais'
        verbose_name = 'Note de frais'
        verbose_name_plural = 'Notes de frais'
        ordering = ['-date_frais', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_note_frais_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "NDF"} — {self.motif} '
                f'({self.montant})')

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant <= 0:
            raise ValidationError(
                "Le montant d'une note de frais doit être strictement positif.")

    @property
    def est_remboursable(self):
        """Vrai si la note est validée et pas encore remboursée."""
        return self.statut == self.Statut.VALIDEE

    @property
    def est_terminee(self):
        """Vrai si la note est dans un état terminal (remboursée ou rejetée)."""
        return self.statut in (self.Statut.REMBOURSEE, self.Statut.REJETEE)


# ── ZACC6 — Rapport de notes de frais (regroupement multi-lignes) ─────────

class RapportNoteFrais(models.Model):
    """Regroupe N ``NoteFrais`` d'un même employé en UN rapport soumis en
    bloc (ZACC6 — Odoo « Expense Report »).

    L'employé coche plusieurs notes en brouillon/rejetées et les regroupe en
    UN rapport ; la validation du RAPPORT poste UNE écriture agrégée (Σ des
    charges par compte / crédit 4432) et le remboursement solde en UN
    paiement — jamais deux fois. Les ``NoteFrais`` isolées (``rapport=None``)
    gardent leur cycle individuel actuel, intact. ``company`` posée côté
    serveur, jamais lue du corps de requête. Strictement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMIS = 'soumis', 'Soumis'
        VALIDE = 'valide', 'Validé'
        REMBOURSE = 'rembourse', 'Remboursé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rapports_notes_frais',
        verbose_name='Société',
    )
    # Référence interne par société (RNF-YYYYMM-NNNN), posée côté serveur via
    # apps.ventes.utils.references (highest-used+1, jamais count()+1).
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    employe = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='rapports_notes_frais',
        verbose_name='Employé',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rapports_notes_frais_valides',
        verbose_name='Validé par',
    )
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Validé le')
    ecriture_charge = models.ForeignKey(
        'compta.EcritureComptable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rapports_notes_frais_charge',
        verbose_name='Écriture de charge agrégée',
    )
    mode_remboursement = models.CharField(
        max_length=10, choices=NoteFrais.ModeRemboursement.choices,
        default=NoteFrais.ModeRemboursement.VIREMENT,
        verbose_name='Mode de remboursement')
    compte_tresorerie = models.ForeignKey(
        'compta.CompteTresorerie',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='rapports_notes_frais',
        verbose_name='Compte de trésorerie (payeur)',
    )
    date_remboursement = models.DateField(
        null=True, blank=True, verbose_name='Date de remboursement')
    rembourse_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rapports_notes_frais_rembourses',
        verbose_name='Remboursé par',
    )
    ecriture_remboursement = models.ForeignKey(
        'compta.EcritureComptable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rapports_notes_frais_remboursement',
        verbose_name='Écriture de remboursement',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rapports_notes_frais_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        # ODX15 — table PHYSIQUE inchangée (move state-only).
        db_table = 'compta_rapportnotefrais'
        verbose_name = 'Rapport de notes de frais'
        verbose_name_plural = 'Rapports de notes de frais'
        ordering = ['-date_creation', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_rapport_note_frais_reference',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "RNF"} — {self.employe_id}'

    @property
    def montant_total(self):
        """Σ des montants des notes rattachées (toutes, quel que soit leur
        statut individuel — un affichage informatif, jamais utilisé pour le
        posting qui relit toujours les notes SOUMISES au moment de valider)."""
        return self.notes.aggregate(
            total=models.Sum('montant'))['total'] or Decimal('0')

    @property
    def est_remboursable(self):
        return self.statut == self.Statut.VALIDE

    @property
    def est_terminal(self):
        return self.statut == self.Statut.REMBOURSE


# ── XACC27 — Plafonds de notes de frais par catégorie ──────────────────────

class PlafondNoteFrais(models.Model):
    """Plafond de dépense par catégorie de note de frais (XACC27).

    Référentiel company-scopé adossé au champ ``NoteFrais.categorie``
    EXISTANT : au-delà de ``montant_max``, la note est flaggée
    ``hors_politique`` (warning visible au valideur, jamais de blocage). Au-delà
    de ``seuil_justificatif_obligatoire`` (optionnel), un justificatif devient
    obligatoire pour valider. Une catégorie sans plafond configuré n'est jamais
    flaggée. ``company`` posée côté serveur ; purement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='plafonds_notes_frais',
        verbose_name='Société',
    )
    categorie = models.CharField(
        max_length=15, choices=NoteFrais.Categorie.choices,
        verbose_name='Catégorie')
    montant_max = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Plafond (montant max)')
    seuil_justificatif_obligatoire = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Seuil au-delà duquel le justificatif est obligatoire')
    # ── NTP2P11 — délai de soumission + escalade direction ─────────────────
    # Deux réglages ADDITIFS et OPTIONNELS (``None`` = comportement historique
    # inchangé : aucun contrôle de délai, aucune escalade).
    jours_max_apres_depense = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Délai max entre la dépense et sa soumission (jours)',
        help_text='Au-delà, un WARNING non bloquant est journalisé pour le '
                  'valideur. Vide = aucun contrôle de délai.')
    escalade_direction_au_dela_de = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant au-delà duquel la direction doit valider',
        help_text="Au-delà, la note exige une validation DIRECTION (jamais un "
                  'blocage silencieux). Vide = aucune escalade.')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        # ODX15 — table PHYSIQUE inchangée (move state-only).
        db_table = 'compta_plafondnotefrais'
        verbose_name = 'Plafond de note de frais'
        verbose_name_plural = 'Plafonds de notes de frais'
        ordering = ['categorie']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'categorie'],
                name='uniq_plafond_notefrais_categorie',
            ),
        ]

    def __str__(self):
        return f'{self.get_categorie_display()} ≤ {self.montant_max}'

    def clean(self):
        super().clean()
        if self.montant_max is not None and self.montant_max < 0:
            raise ValidationError("Le plafond ne peut pas être négatif.")
        if (self.seuil_justificatif_obligatoire is not None
                and self.seuil_justificatif_obligatoire < 0):
            raise ValidationError("Le seuil ne peut pas être négatif.")


# ── FG136 — Indemnités kilométriques & per-diem chantier ───────────────────


class BaremeIndemnite(models.Model):
    """Barème d'indemnités de déplacement chantier d'une société (FG136).

    Porte les deux tarifs qui transforment un déplacement terrain en montant
    remboursable :

    * ``taux_km`` — indemnité kilométrique par km parcouru (MAD/km) ; le
      kilométrage est calculé AUTOMATIQUEMENT par la formule de haversine à
      partir des coordonnées GPS du point de départ et du chantier (les GPS et
      le calcul de distance existent déjà dans le code — réutilisés ici) ;
    * ``per_diem`` — indemnité journalière forfaitaire (MAD/jour) couvrant
      repas/hébergement sur place.

    Plusieurs barèmes peuvent coexister par société (révisions successives) ;
    celui marqué ``defaut`` est appliqué quand aucun barème n'est précisé.
    Strictement additif, ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='baremes_indemnite',
        verbose_name='Société',
    )
    libelle = models.CharField(
        max_length=120, verbose_name='Libellé du barème')
    # Indemnité kilométrique (MAD par km parcouru).
    taux_km = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0'),
        verbose_name='Indemnité kilométrique (MAD/km)')
    # Per-diem forfaitaire (MAD par jour de chantier).
    per_diem = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Per-diem chantier (MAD/jour)')
    # Barème appliqué par défaut quand une indemnité n'en précise aucun.
    defaut = models.BooleanField(
        default=False, verbose_name='Barème par défaut')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        # ODX15 — table PHYSIQUE inchangée (move state-only).
        db_table = 'compta_baremeindemnite'
        verbose_name = "Barème d'indemnité"
        verbose_name_plural = "Barèmes d'indemnité"
        ordering = ['-defaut', 'libelle', '-id']
        constraints = [
            # Un seul barème "par défaut" actif par société.
            models.UniqueConstraint(
                fields=['company'],
                condition=models.Q(defaut=True, actif=True),
                name='uniq_bareme_indem_defaut',
            ),
        ]

    def __str__(self):
        return (f'{self.libelle} ({self.taux_km} MAD/km, '
                f'{self.per_diem} MAD/jour)')

    def clean(self):
        super().clean()
        if self.taux_km is not None and self.taux_km < 0:
            raise ValidationError(
                "L'indemnité kilométrique ne peut pas être négative.")
        if self.per_diem is not None and self.per_diem < 0:
            raise ValidationError(
                "Le per-diem ne peut pas être négatif.")


class IndemniteChantier(models.Model):
    """Indemnité de déplacement d'un employé vers un chantier (FG136).

    Calcule AUTOMATIQUEMENT le montant dû à un employé pour un déplacement
    chantier, à partir :

    * de la distance GPS (haversine) entre le point de départ
      (``depart_lat``/``depart_lng``) et le chantier
      (``site_lat``/``site_lng``) — multipliée par 2 si ``aller_retour`` ;
    * du barème (``taux_km`` × km) ;
    * du per-diem (``per_diem`` × ``nombre_jours``).

    Les coordonnées GPS du chantier sont copiées côté appelant (le module reste
    autonome). ``distance_km``, ``montant_km``, ``montant_per_diem`` et
    ``montant_total`` sont FIGÉS au calcul (jamais lus du corps), pour rester
    auditables même si le barème change ensuite.

    Cycle de vie identique à la note de frais (FG135) :
    ``brouillon`` → ``soumise`` → ``validee`` (POSTE la charge : débit compte de
    charge classe 6 / crédit 4432 personnel-créditeur) → ``remboursee`` /
    ``rejetee``. ``company`` posée côté serveur.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMISE = 'soumise', 'Soumise'
        VALIDEE = 'validee', 'Validée'
        REJETEE = 'rejetee', 'Rejetée'
        REMBOURSEE = 'remboursee', 'Remboursée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='indemnites_chantier',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    employe = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='indemnites_chantier',
        verbose_name='Employé',
    )
    bareme = models.ForeignKey(
        BaremeIndemnite,
        on_delete=models.PROTECT,
        related_name='indemnites',
        verbose_name='Barème appliqué',
    )
    date_deplacement = models.DateField(verbose_name='Date du déplacement')
    libelle_chantier = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Chantier')
    # ── Coordonnées GPS (départ + chantier) — distance auto par haversine ──
    depart_lat = models.FloatField(
        null=True, blank=True, verbose_name='Latitude départ')
    depart_lng = models.FloatField(
        null=True, blank=True, verbose_name='Longitude départ')
    site_lat = models.FloatField(
        null=True, blank=True, verbose_name='Latitude chantier')
    site_lng = models.FloatField(
        null=True, blank=True, verbose_name='Longitude chantier')
    aller_retour = models.BooleanField(
        default=True, verbose_name='Aller-retour')
    nombre_jours = models.PositiveIntegerField(
        default=1, verbose_name='Nombre de jours de chantier')
    # ── Montants FIGÉS au calcul (auditables) ──
    distance_km = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0'),
        verbose_name='Distance (km)')
    montant_km = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Indemnité kilométrique')
    montant_per_diem = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Per-diem')
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant total')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    compte_charge = models.ForeignKey(
        'compta.CompteComptable',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='indemnites_chantier_charge',
        verbose_name='Compte de charge',
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indemnites_chantier_validees',
        verbose_name='Validée par',
    )
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Validée le')
    ecriture_charge = models.ForeignKey(
        'compta.EcritureComptable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indemnites_chantier_charge',
        verbose_name='Écriture de charge',
    )
    motif_rejet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de rejet')
    # ── Remboursement ──
    compte_tresorerie = models.ForeignKey(
        'compta.CompteTresorerie',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='indemnites_chantier',
        verbose_name='Compte de trésorerie (payeur)',
    )
    date_remboursement = models.DateField(
        null=True, blank=True, verbose_name='Date de remboursement')
    rembourse_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indemnites_chantier_remboursees',
        verbose_name='Remboursée par',
    )
    ecriture_remboursement = models.ForeignKey(
        'compta.EcritureComptable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indemnites_chantier_remboursement',
        verbose_name='Écriture de remboursement',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indemnites_chantier_creees',
        verbose_name='Saisie par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        # ODX15 — table PHYSIQUE inchangée (move state-only).
        db_table = 'compta_indemnitechantier'
        verbose_name = 'Indemnité chantier'
        verbose_name_plural = 'Indemnités chantier'
        ordering = ['-date_deplacement', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_indem_chantier_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "IND"} — {self.libelle_chantier} '
                f'({self.montant_total})')

    def clean(self):
        super().clean()
        if self.nombre_jours is not None and self.nombre_jours < 0:
            raise ValidationError(
                "Le nombre de jours ne peut pas être négatif.")

    @property
    def est_remboursable(self):
        """Vrai si l'indemnité est validée et pas encore remboursée."""
        return self.statut == self.Statut.VALIDEE

    @property
    def est_terminee(self):
        """Vrai si l'indemnité est dans un état terminal."""
        return self.statut in (self.Statut.REMBOURSEE, self.Statut.REJETEE)
