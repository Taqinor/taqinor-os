"""Modèles de la Comptabilité générale (module `apps.compta`).

Socle d'une comptabilité en partie double conforme au CGNC marocain
(Code Général de la Normalisation Comptable) :

* ``PlanComptable`` / ``CompteComptable`` (FG107) — plan de comptes par société,
  classes 1 à 7, avec un jeu de comptes usuels semés à la demande.
* ``Journal`` (FG108) — journaux paramétrables (VTE/ACH/BNK/CSH/OD…).
* ``EcritureComptable`` / ``LigneEcriture`` (FG108) — écritures en partie double
  GARANTIES équilibrées (Σ débit = Σ crédit) au niveau ``clean()``.
* ``CompteTresorerie`` (FG121) — référentiel des comptes bancaires & caisses,
  rattaché à un compte comptable de classe 5.
* ``ExerciceComptable`` / ``PeriodeComptable`` (FG115) — exercice fiscal et
  période (mois ou exercice) VERROUILLABLE : une fois clôturée, les écritures et
  les factures dont la date tombe dedans deviennent IMMUABLES (audit). Les
  écritures (et leurs lignes) sont protégées au niveau ``save()``/``delete()``.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Aucun comportement existant n'est modifié — ce
module est entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# ── FG107 / COMPTA1 — Plan comptable CGNC ──────────────────────────────────

class PlanComptable(models.Model):
    """Plan de comptes d'une société (un par société en pratique).

    Conteneur paramétrable : il regroupe les ``CompteComptable``. Le code par
    défaut « CGNC » correspond au plan normalisé marocain.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='plans_comptables',
        verbose_name='Société',
    )
    code = models.CharField(
        max_length=20, default='CGNC', verbose_name='Code du plan')
    libelle = models.CharField(
        max_length=120, default='Plan comptable CGNC',
        verbose_name='Libellé')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Plan comptable'
        verbose_name_plural = 'Plans comptables'
        unique_together = [('company', 'code')]
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class CompteComptable(models.Model):
    """Un compte du plan comptable (ex. 3421 « Clients »).

    Le ``numero`` (chaîne) porte la classe CGNC dans son premier chiffre
    (1 financement, 2 actif immobilisé, 3 actif circulant, 4 passif circulant,
    5 trésorerie, 6 charges, 7 produits, 8 résultats analytiques).
    """
    class Classe(models.IntegerChoices):
        FINANCEMENT = 1, '1 — Financement permanent'
        ACTIF_IMMOBILISE = 2, '2 — Actif immobilisé'
        ACTIF_CIRCULANT = 3, '3 — Actif circulant (hors trésorerie)'
        PASSIF_CIRCULANT = 4, '4 — Passif circulant (hors trésorerie)'
        TRESORERIE = 5, '5 — Trésorerie'
        CHARGES = 6, '6 — Charges'
        PRODUITS = 7, '7 — Produits'
        RESULTATS = 8, '8 — Résultats'

    class Sens(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        PASSIF = 'passif', 'Passif'
        CHARGE = 'charge', 'Charge'
        PRODUIT = 'produit', 'Produit'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='comptes_comptables',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanComptable,
        on_delete=models.CASCADE,
        related_name='comptes',
        verbose_name='Plan comptable',
    )
    numero = models.CharField(max_length=20, verbose_name='Numéro de compte')
    intitule = models.CharField(max_length=200, verbose_name='Intitulé')
    classe = models.IntegerField(
        choices=Classe.choices, verbose_name='Classe')
    # Sens « naturel » du compte (informatif, pour les états de synthèse).
    sens = models.CharField(
        max_length=10, choices=Sens.choices, blank=True, default='',
        verbose_name='Sens')
    # Compte de tiers (clients/fournisseurs) : peut porter un auxiliaire.
    est_tiers = models.BooleanField(
        default=False, verbose_name='Compte de tiers')
    # Compte lettrable (clients/fournisseurs) : on peut apparier ses lignes.
    lettrable = models.BooleanField(
        default=False, verbose_name='Lettrable')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Compte comptable'
        verbose_name_plural = 'Comptes comptables'
        unique_together = [('company', 'numero')]
        ordering = ['numero']

    def __str__(self):
        return f'{self.numero} — {self.intitule}'

    def save(self, *args, **kwargs):
        # Déduit la classe du premier chiffre du numéro si non fournie.
        if not self.classe and self.numero[:1].isdigit():
            self.classe = int(self.numero[0])
        super().save(*args, **kwargs)


# ── FG108 / COMPTA4 — Journaux ─────────────────────────────────────────────

class Journal(models.Model):
    """Journal comptable d'une société (VTE/ACH/BNK/CSH/OD…).

    Les écritures sont toujours rattachées à un journal. Le ``type_journal``
    pilote le filtrage et l'auto-génération (les ventes vont au journal VTE…).
    """
    class Type(models.TextChoices):
        VENTE = 'VTE', 'Ventes'
        ACHAT = 'ACH', 'Achats'
        BANQUE = 'BNK', 'Banque'
        CAISSE = 'CSH', 'Caisse'
        OPERATIONS_DIVERSES = 'OD', 'Opérations diverses'
        A_NOUVEAUX = 'AN', 'À-nouveaux'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='journaux',
        verbose_name='Société',
    )
    code = models.CharField(max_length=10, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    type_journal = models.CharField(
        max_length=5, choices=Type.choices, verbose_name='Type de journal')
    # Compte de contrepartie par défaut (trésorerie d'un journal BNK/CSH).
    compte_contrepartie = models.ForeignKey(
        CompteComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='journaux_contrepartie',
        verbose_name='Compte de contrepartie',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Journal'
        verbose_name_plural = 'Journaux'
        unique_together = [('company', 'code')]
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.libelle}'


# ── FG108 / COMPTA7 — Écritures en partie double ───────────────────────────

class EcritureComptable(models.Model):
    """Écriture comptable (pièce) en partie double.

    Une écriture porte plusieurs ``LigneEcriture`` (au moins deux) dont la somme
    des débits égale la somme des crédits. L'équilibre est VÉRIFIÉ dans
    ``clean()`` ; la validation refuse une écriture déséquilibrée.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDEE = 'validee', 'Validée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ecritures',
        verbose_name='Société',
    )
    journal = models.ForeignKey(
        Journal,
        on_delete=models.PROTECT,
        related_name='ecritures',
        verbose_name='Journal',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence de pièce')
    date_ecriture = models.DateField(verbose_name="Date d'écriture")
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Origine documentaire (facture/paiement/avoir) — purement informatif, pour
    # l'idempotence de l'auto-génération. Jamais un import cross-app de modèle.
    source_type = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Type de document source')
    source_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du document source')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ecritures_creees',
        verbose_name='Créée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Écriture comptable'
        verbose_name_plural = 'Écritures comptables'
        ordering = ['-date_ecriture', '-id']
        constraints = [
            # Idempotence : un même document ne produit qu'une écriture par
            # société (NULL source_id non contraint → écritures manuelles OK).
            models.UniqueConstraint(
                fields=['company', 'source_type', 'source_id'],
                condition=models.Q(source_id__isnull=False),
                name='uniq_ecriture_par_source',
            ),
        ]

    def __str__(self):
        return f'{self.journal.code} {self.date_ecriture} — {self.libelle}'

    @property
    def total_debit(self):
        return sum((lig.debit for lig in self.lignes.all()), Decimal('0'))

    @property
    def total_credit(self):
        return sum((lig.credit for lig in self.lignes.all()), Decimal('0'))

    @property
    def est_equilibree(self):
        return self.total_debit == self.total_credit

    def clean(self):
        """Garantit l'équilibre (Σ débit = Σ crédit) au niveau validation.

        N'est exécutable que sur une écriture déjà persistée (les lignes ont
        besoin d'un FK). On tolère 0 ligne (écriture en cours de saisie) ; dès
        qu'il y a au moins une ligne, l'écriture doit être équilibrée.
        """
        super().clean()
        if not self.pk:
            return
        lignes = list(self.lignes.all())
        if not lignes:
            return
        debit = sum((lig.debit for lig in lignes), Decimal('0'))
        credit = sum((lig.credit for lig in lignes), Decimal('0'))
        if debit != credit:
            raise ValidationError(
                "L'écriture comptable doit être équilibrée : "
                f"Σ débit ({debit}) ≠ Σ crédit ({credit})."
            )

    # ── FG115 — Immutabilité d'une écriture en période verrouillée ─────────
    def _verifier_periode_ouverte(self):
        """Refuse toute écriture dont la date tombe dans une période clôturée.

        Garde-fou d'audit : tant qu'une ``PeriodeComptable`` couvre
        ``date_ecriture`` et est ``verrouillee``, on ne peut ni créer, ni
        modifier, ni supprimer cette écriture. Lève ``ValidationError``.
        """
        if self.company_id is None or self.date_ecriture is None:
            return
        if PeriodeComptable.date_verrouillee(self.company_id, self.date_ecriture):
            raise ValidationError(
                "Période comptable clôturée : l'écriture du "
                f"{self.date_ecriture} est verrouillée et ne peut plus être "
                "modifiée."
            )

    def save(self, *args, **kwargs):
        self._verifier_periode_ouverte()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._verifier_periode_ouverte()
        return super().delete(*args, **kwargs)


class LigneEcriture(models.Model):
    """Ligne d'une écriture : un compte mouvementé au débit OU au crédit.

    Une ligne ne peut pas être à la fois débitée et créditée d'un montant
    positif ; au moins l'un des deux est non nul.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_ecriture',
        verbose_name='Société',
    )
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Écriture',
    )
    compte = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        related_name='lignes_ecriture',
        verbose_name='Compte',
    )
    libelle = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Libellé')
    debit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Débit')
    credit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Crédit')
    # FG112 — lettrage : code d'appariement (ex. « A », « B »…). Vide = non
    # lettré. Toutes les lignes d'un même lettrage soldent un tiers.
    lettrage = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Lettrage')
    # Référence aux tiers (auxiliaire) — string FK pour ne jamais importer les
    # modèles d'une autre app. NULL = pas de tiers (compte général).
    tiers_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')

    class Meta:
        verbose_name = "Ligne d'écriture"
        verbose_name_plural = "Lignes d'écriture"
        ordering = ['id']

    def __str__(self):
        return f'{self.compte.numero} D:{self.debit} C:{self.credit}'

    def clean(self):
        super().clean()
        if self.debit and self.credit:
            raise ValidationError(
                "Une ligne ne peut être débitée ET créditée simultanément."
            )
        if not self.debit and not self.credit:
            raise ValidationError(
                "Une ligne doit porter un débit ou un crédit non nul."
            )
        if self.debit < 0 or self.credit < 0:
            raise ValidationError(
                "Les montants débit/crédit doivent être positifs."
            )

    # ── FG115 — Immutabilité d'une ligne en période verrouillée ────────────
    def _verifier_periode_ouverte(self):
        """Refuse de toucher une ligne dont l'écriture est en période close."""
        if self.company_id is None:
            return
        d = getattr(self.ecriture, 'date_ecriture', None)
        if d is not None and PeriodeComptable.date_verrouillee(
                self.company_id, d):
            raise ValidationError(
                "Période comptable clôturée : cette ligne d'écriture est "
                "verrouillée et ne peut plus être modifiée."
            )

    def save(self, *args, **kwargs):
        self._verifier_periode_ouverte()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._verifier_periode_ouverte()
        return super().delete(*args, **kwargs)


# ── FG121 / COMPTA23 — Référentiel comptes bancaires & caisses ─────────────

class CompteTresorerie(models.Model):
    """Compte de trésorerie : banque ou caisse, rattaché à un compte de classe 5.

    Remplace le « RIB texte » unique par un référentiel structuré. Le solde
    courant se déduit du grand livre (lignes d'écriture sur ``compte_comptable``)
    ; ``solde_initial`` permet d'amorcer un solde de départ.
    """
    class Type(models.TextChoices):
        BANQUE = 'banque', 'Banque'
        CAISSE = 'caisse', 'Caisse'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='comptes_tresorerie',
        verbose_name='Société',
    )
    type_compte = models.CharField(
        max_length=10, choices=Type.choices,
        default=Type.BANQUE, verbose_name='Type')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    banque = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Banque')
    rib = models.CharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    iban = models.CharField(
        max_length=40, blank=True, default='', verbose_name='IBAN')
    swift = models.CharField(
        max_length=20, blank=True, default='', verbose_name='SWIFT/BIC')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    solde_initial = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Solde initial')
    # Compte comptable de classe 5 lié (5141 banque, 5161 caisse…).
    compte_comptable = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        related_name='comptes_tresorerie',
        verbose_name='Compte comptable',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Compte de trésorerie'
        verbose_name_plural = 'Comptes de trésorerie'
        ordering = ['type_compte', 'libelle']

    def __str__(self):
        return f'{self.get_type_compte_display()} — {self.libelle}'


# ── FG115 / FG117 — Exercice comptable (année fiscale) ─────────────────────

class ExerciceComptable(models.Model):
    """Exercice fiscal d'une société (généralement l'année civile).

    Sert de cadre à la clôture (FG115) et à la réouverture / report des
    à-nouveaux (FG117). Un exercice ``cloture`` est définitivement figé ; on
    ouvre l'exercice suivant et on y reporte les soldes de bilan.
    """
    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        CLOTURE = 'cloture', 'Clôturé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='exercices_comptables',
        verbose_name='Société',
    )
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.OUVERT, verbose_name='Statut')
    # Trace de la réouverture / report (FG117) : l'écriture d'à-nouveaux créée.
    an_reporte = models.BooleanField(
        default=False, verbose_name='À-nouveaux reportés')
    date_cloture = models.DateTimeField(
        null=True, blank=True, verbose_name='Clôturé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Exercice comptable'
        verbose_name_plural = 'Exercices comptables'
        ordering = ['-date_debut']
        unique_together = [('company', 'date_debut', 'date_fin')]

    def __str__(self):
        return self.libelle or f'Exercice {self.date_debut}–{self.date_fin}'

    def clean(self):
        super().clean()
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début.")

    @property
    def est_cloture(self):
        return self.statut == self.Statut.CLOTURE


# ── FG115 — Période comptable verrouillable (clôture & immutabilité) ────────

class PeriodeComptable(models.Model):
    """Période comptable (mois ou exercice) que l'on peut figer pour l'audit.

    Tant qu'elle est ``verrouillee``, toute écriture (et facture) dont la date
    tombe dans l'intervalle ``[date_debut ; date_fin]`` devient IMMUABLE : la
    création/modification/suppression est refusée au niveau ``save()`` du
    modèle ``EcritureComptable``/``LigneEcriture`` et par la couche service
    pour les factures (FG115).
    """
    class Type(models.TextChoices):
        MOIS = 'mois', 'Mois'
        EXERCICE = 'exercice', 'Exercice'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='periodes_comptables',
        verbose_name='Société',
    )
    exercice = models.ForeignKey(
        ExerciceComptable,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='periodes',
        verbose_name='Exercice',
    )
    type_periode = models.CharField(
        max_length=10, choices=Type.choices,
        default=Type.MOIS, verbose_name='Type de période')
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    verrouillee = models.BooleanField(
        default=False, verbose_name='Verrouillée')
    date_verrouillage = models.DateTimeField(
        null=True, blank=True, verbose_name='Verrouillée le')
    verrouillee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='periodes_verrouillees',
        verbose_name='Verrouillée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Période comptable'
        verbose_name_plural = 'Périodes comptables'
        ordering = ['-date_debut']
        unique_together = [('company', 'date_debut', 'date_fin')]

    def __str__(self):
        etat = 'verrouillée' if self.verrouillee else 'ouverte'
        return f'{self.libelle or self.date_debut} ({etat})'

    def clean(self):
        super().clean()
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début.")

    def contient(self, une_date):
        """Vrai si ``une_date`` (date) tombe dans l'intervalle de la période."""
        return self.date_debut <= une_date <= self.date_fin

    @classmethod
    def date_verrouillee(cls, company_id, une_date):
        """Vrai si une période VERROUILLÉE de la société couvre ``une_date``.

        Point d'appui de l'immutabilité (FG115) : une seule requête, scopée
        société, qui répond « cette date est-elle figée ? ». ``une_date`` peut
        être une ``date`` ou un ``datetime`` (on prend sa partie date).
        """
        if une_date is None or company_id is None:
            return False
        if isinstance(une_date, str):
            return False
        # ``datetime`` est une sous-classe de ``date`` : on prend sa partie date.
        d = une_date.date() if hasattr(une_date, 'hour') else une_date
        return cls.objects.filter(
            company_id=company_id, verrouillee=True,
            date_debut__lte=d, date_fin__gte=d,
        ).exists()


# ── FG118 — Registre des immobilisations ───────────────────────────────────

class Immobilisation(models.Model):
    """Une immobilisation (actif immobilisé) au registre des immobilisations.

    Simple REGISTRE par société : chaque bif (camionnette, outillage, matériel…)
    est inventorié avec son coût d'acquisition, sa date d'acquisition, sa
    catégorie et le taux de TVA appliqué. Ce module est strictement additif et
    NE calcule PAS de plan d'amortissement (hors périmètre) — il tient le
    registre. La TVA récupérable est dérivée du ``cout`` HT et du ``taux_tva``.
    """
    class Categorie(models.TextChoices):
        VEHICULE = 'vehicule', 'Véhicule'
        OUTILLAGE = 'outillage', 'Outillage'
        MATERIEL = 'materiel', 'Matériel'
        MOBILIER = 'mobilier', 'Mobilier'
        INFORMATIQUE = 'informatique', 'Matériel informatique'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='immobilisations',
        verbose_name='Société',
    )
    # Référence interne optionnelle (par société). Libre, jamais auto-numérotée :
    # le registre n'impose pas de codification. Unicité non contrainte en base
    # pour rester purement additif sur une table éventuellement déjà peuplée.
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence interne')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    categorie = models.CharField(
        max_length=15, choices=Categorie.choices,
        default=Categorie.MATERIEL, verbose_name='Catégorie')
    cout = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name="Coût d'acquisition (HT)")
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        verbose_name='Taux de TVA (%)')
    date_acquisition = models.DateField(verbose_name="Date d'acquisition")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Immobilisation'
        verbose_name_plural = 'Immobilisations'
        ordering = ['-date_acquisition', '-id']

    def __str__(self):
        return f'{self.libelle} ({self.get_categorie_display()})'

    def clean(self):
        super().clean()
        if self.cout is not None and self.cout < 0:
            raise ValidationError(
                "Le coût d'acquisition doit être positif.")
        if self.taux_tva is not None and self.taux_tva < 0:
            raise ValidationError(
                "Le taux de TVA doit être positif.")

    @property
    def montant_tva(self):
        """Montant de TVA dérivé du coût HT et du taux (informatif)."""
        cout = self.cout or Decimal('0')
        taux = self.taux_tva or Decimal('0')
        return (cout * taux / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def cout_ttc(self):
        """Coût TTC = coût HT + TVA dérivée."""
        return (self.cout or Decimal('0')) + self.montant_tva


# ── FG119 — Plan d'amortissement & dotations ───────────────────────────────

class PlanAmortissement(models.Model):
    """Plan d'amortissement d'une ``Immobilisation`` (FG119).

    Capture les paramètres de calcul : mode (linéaire/dégressif), durée en
    années (→ taux linéaire = 100 / durée), base amortissable (en pratique le
    coût HT de l'immobilisation) et date de début (généralement la date
    d'acquisition). Le plan engendre une ``DotationAmortissement`` par exercice
    via ``services.generer_plan_amortissement`` (idempotent).

    Mode DÉGRESSIF (cadre marocain) : le taux dégressif = taux linéaire ×
    coefficient fiscal. Les coefficients usuels au Maroc (CGI) sont 1,5 pour une
    durée de 3-4 ans, 2 pour 5-6 ans et 3 au-delà de 6 ans. La dotation de
    chaque exercice s'applique à la VALEUR NETTE résiduelle ; lorsque l'annuité
    dégressive devient inférieure à l'amortissement linéaire du résiduel sur la
    durée restante, on bascule sur le linéaire (règle classique). Le coefficient
    retenu est figé sur le plan (``coefficient_degressif``) pour rester
    reproductible même si le barème évolue.
    """
    class Mode(models.TextChoices):
        LINEAIRE = 'lineaire', 'Linéaire'
        DEGRESSIF = 'degressif', 'Dégressif'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='plans_amortissement',
        verbose_name='Société',
    )
    immobilisation = models.OneToOneField(
        Immobilisation,
        on_delete=models.CASCADE,
        related_name='plan_amortissement',
        verbose_name='Immobilisation',
    )
    mode = models.CharField(
        max_length=10, choices=Mode.choices, default=Mode.LINEAIRE,
        verbose_name="Mode d'amortissement")
    duree_annees = models.PositiveIntegerField(
        verbose_name="Durée (années)")
    base_amortissable = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Base amortissable (HT)')
    date_debut = models.DateField(verbose_name="Date de début")
    # Coefficient dégressif fiscal figé (None pour un plan linéaire). Stocké pour
    # la reproductibilité : un même plan recalculé donne toujours le même barème.
    coefficient_degressif = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        verbose_name='Coefficient dégressif')
    # Comptes mouvementés par les dotations (classe 6 / classe 28). Optionnels :
    # par défaut le service utilise 6193 (DEA) et un compte 28xx assorti.
    compte_dotation = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='plans_amortissement_dotation',
        verbose_name='Compte de dotation (classe 6)',
    )
    compte_amortissement = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='plans_amortissement_cumul',
        verbose_name="Compte d'amortissement (classe 28)",
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Plan d'amortissement"
        verbose_name_plural = "Plans d'amortissement"
        ordering = ['-date_creation', '-id']

    def __str__(self):
        return f"Plan {self.get_mode_display()} — {self.immobilisation}"

    def clean(self):
        super().clean()
        if self.duree_annees is not None and self.duree_annees < 1:
            raise ValidationError(
                "La durée d'amortissement doit être d'au moins 1 an.")
        if self.base_amortissable is not None and self.base_amortissable < 0:
            raise ValidationError(
                "La base amortissable doit être positive.")

    @property
    def taux_lineaire(self):
        """Taux linéaire annuel (%) = 100 / durée."""
        if not self.duree_annees:
            return Decimal('0')
        return (Decimal('100') / Decimal(self.duree_annees)).quantize(
            Decimal('0.0001'))


class DotationAmortissement(models.Model):
    """Dotation d'amortissement d'un exercice pour un plan (FG119).

    Une ligne par exercice/année : montant de la dotation, cumul des dotations
    jusqu'à cet exercice inclus, valeur nette comptable résiduelle, et — une fois
    postée au grand livre — un lien vers l'``EcritureComptable`` créée
    (``posted`` + ``ecriture``). Unicité ``(plan, annee)`` : un exercice ne porte
    qu'une dotation.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='dotations_amortissement',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanAmortissement,
        on_delete=models.CASCADE,
        related_name='dotations',
        verbose_name="Plan d'amortissement",
    )
    annee = models.PositiveIntegerField(verbose_name='Exercice (année)')
    # Date imputée à l'écriture postée (31/12 de l'exercice par défaut).
    date_dotation = models.DateField(verbose_name='Date de dotation')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Dotation')
    cumul = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul des amortissements')
    valeur_nette = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Valeur nette comptable')
    posted = models.BooleanField(
        default=False, verbose_name='Postée au grand livre')
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dotations_amortissement',
        verbose_name='Écriture comptable',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Dotation d'amortissement"
        verbose_name_plural = "Dotations d'amortissement"
        ordering = ['plan_id', 'annee']
        constraints = [
            # Un exercice = une seule dotation par plan.
            models.UniqueConstraint(
                fields=['plan', 'annee'],
                name='uniq_dotation_par_plan_annee',
            ),
        ]

    def __str__(self):
        return f"Dotation {self.annee} — {self.montant}"


# ── FG120 — Cession / mise au rebut d'immobilisation ───────────────────────

class CessionImmobilisation(models.Model):
    """Cession (vente) ou mise au rebut d'une ``Immobilisation`` (FG120).

    Constate la SORTIE d'un actif immobilisé du patrimoine : soit une vente (un
    ``prix_cession`` est encaissé), soit une mise au rebut (``prix_cession`` =
    0). La valeur nette comptable (VNC = coût − amortissements cumulés à la date
    de cession) est figée sur la cession, ainsi que le résultat de cession
    (``resultat_cession`` = prix de cession − VNC) : positif → plus-value,
    négatif → moins-value.

    Le posting (``services.poster_cession``) passe l'écriture standard de sortie
    (reprise des amortissements + sortie de l'immobilisation + constatation du
    résultat) au grand livre, RESPECTE le verrou de période et marque
    l'immobilisation inactive. Strictement additif ; ``company`` posée côté
    serveur, jamais lue du corps de requête.
    """
    class Type(models.TextChoices):
        VENTE = 'vente', 'Vente'
        REBUT = 'rebut', 'Mise au rebut'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='cessions_immobilisation',
        verbose_name='Société',
    )
    immobilisation = models.ForeignKey(
        Immobilisation,
        on_delete=models.PROTECT,
        related_name='cessions',
        verbose_name='Immobilisation',
    )
    type_cession = models.CharField(
        max_length=10, choices=Type.choices, default=Type.VENTE,
        verbose_name='Type de cession')
    date_cession = models.DateField(verbose_name='Date de cession')
    prix_cession = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Prix de cession (HT)')
    # Valeur nette comptable figée à la date de cession (coût − cumul amort.).
    valeur_nette_comptable = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Valeur nette comptable')
    # Cumul des amortissements à la date de cession (figé).
    amortissements_cumules = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Amortissements cumulés')
    # Résultat de cession SIGNÉ = prix de cession − VNC. > 0 plus-value,
    # < 0 moins-value (mise au rebut → toujours une moins-value = −VNC).
    resultat_cession = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Résultat de cession')
    posted = models.BooleanField(
        default=False, verbose_name='Postée au grand livre')
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cessions_immobilisation',
        verbose_name='Écriture comptable',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Cession d'immobilisation"
        verbose_name_plural = "Cessions d'immobilisation"
        ordering = ['-date_cession', '-id']

    def __str__(self):
        return (f'{self.get_type_cession_display()} — '
                f'{self.immobilisation.libelle} ({self.date_cession})')

    def clean(self):
        super().clean()
        if self.prix_cession is not None and self.prix_cession < 0:
            raise ValidationError(
                "Le prix de cession doit être positif.")

    @property
    def plus_value(self):
        """Plus-value de cession (résultat positif, sinon 0)."""
        resultat = self.resultat_cession or Decimal('0')
        return resultat if resultat > 0 else Decimal('0')

    @property
    def moins_value(self):
        """Moins-value de cession (valeur absolue du résultat négatif, sinon 0)."""
        resultat = self.resultat_cession or Decimal('0')
        return -resultat if resultat < 0 else Decimal('0')


# ── FG123 — Rapprochement bancaire (relevé ↔ écritures) ────────────────────

class RapprochementBancaire(models.Model):
    """Rapprochement bancaire d'un ``CompteTresorerie`` sur une période (FG123).

    Pointe les lignes du RELEVÉ de banque contre les lignes du GRAND LIVRE
    (``LigneEcriture`` du compte comptable de classe 5 rattaché) jusqu'à
    concordance. C'est une opération STRICTEMENT DISTINCTE de l'import de
    paiements clients (FG42) : ici on ne crée aucun encaissement ; on apparie
    relevé ↔ écritures déjà comptabilisées et on mesure l'écart.

    Le rapprochement porte un ``solde_releve`` (solde de clôture lu sur le
    relevé) et une période ``[date_debut ; date_fin]``. Le solde GL se déduit du
    grand livre (``solde_initial`` du compte de trésorerie + mouvements jusqu'à
    ``date_fin``). L'écart = solde relevé − solde GL ; il tend vers 0 à mesure
    que l'on pointe. Le statut passe ``rapproche`` lorsque toutes les lignes de
    relevé sont pointées et que l'écart est nul.
    """
    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        RAPPROCHE = 'rapproche', 'Rapproché'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rapprochements_bancaires',
        verbose_name='Société',
    )
    compte_tresorerie = models.ForeignKey(
        CompteTresorerie,
        on_delete=models.PROTECT,
        related_name='rapprochements',
        verbose_name='Compte de trésorerie',
    )
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Début de période')
    date_fin = models.DateField(verbose_name='Fin de période')
    # Date d'arrêté du relevé bancaire (généralement = date_fin).
    date_releve = models.DateField(
        null=True, blank=True, verbose_name='Date du relevé')
    # Solde de clôture lu sur le relevé de banque. Le solde GL est comparé tel
    # quel et l'écart (solde relevé − solde GL) en découle.
    solde_releve = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Solde du relevé')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.EN_COURS, verbose_name='Statut')
    date_rapprochement = models.DateTimeField(
        null=True, blank=True, verbose_name='Rapproché le')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rapprochements_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Rapprochement bancaire'
        verbose_name_plural = 'Rapprochements bancaires'
        ordering = ['-date_fin', '-id']

    def __str__(self):
        return (f'Rapprochement {self.compte_tresorerie_id} '
                f'{self.date_debut}–{self.date_fin}')

    def clean(self):
        super().clean()
        if (self.date_debut and self.date_fin
                and self.date_fin < self.date_debut):
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début.")

    @property
    def est_rapproche(self):
        return self.statut == self.Statut.RAPPROCHE


class LigneReleve(models.Model):
    """Ligne d'un relevé bancaire à pointer contre le grand livre (FG123).

    Une ligne de relevé porte un montant SIGNÉ (``montant`` ; positif =
    encaissement/crédit côté entreprise, négatif = décaissement) et un libellé.
    On la POINTE en l'appariant à une ou plusieurs ``LigneEcriture`` du grand
    livre (``lignes_gl``). Quand le montant pointé GL concorde avec le montant
    de la ligne de relevé, elle est ``rapprochee`` (``ecart`` = 0). Tant qu'elle
    n'est pas appariée, elle est ``non_pointee``.

    L'appariement passe par une table de liaison ``PointageReleve`` (jamais un
    import cross-app : ``LigneEcriture`` est dans la même app).
    """
    class Statut(models.TextChoices):
        NON_POINTEE = 'non_pointee', 'Non pointée'
        RAPPROCHEE = 'rapprochee', 'Rapprochée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_releve',
        verbose_name='Société',
    )
    rapprochement = models.ForeignKey(
        RapprochementBancaire,
        on_delete=models.CASCADE,
        related_name='lignes_releve',
        verbose_name='Rapprochement',
    )
    date_operation = models.DateField(verbose_name="Date d'opération")
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    reference = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Référence')
    # Montant SIGNÉ tel que lu sur le relevé : + = crédit (entrée), − = débit.
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.NON_POINTEE, verbose_name='Statut')
    # Lignes du grand livre appariées à cette ligne de relevé.
    lignes_gl = models.ManyToManyField(
        LigneEcriture,
        through='PointageReleve',
        related_name='lignes_releve',
        verbose_name='Lignes du grand livre',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de relevé'
        verbose_name_plural = 'Lignes de relevé'
        ordering = ['date_operation', 'id']

    def __str__(self):
        return f'{self.date_operation} — {self.libelle} ({self.montant})'

    @property
    def montant_pointe(self):
        """Montant GL apparié, SIGNÉ comme le relevé (débit GL = entrée banque).

        Côté grand livre, un encaissement bancaire DÉBITE le compte de
        trésorerie (classe 5) ; on aligne donc le signe sur le relevé en prenant
        ``débit − crédit`` des lignes GL pointées.
        """
        total = Decimal('0')
        for ligne in self.lignes_gl.all():
            total += (ligne.debit or Decimal('0')) - (ligne.credit or Decimal('0'))
        return total

    @property
    def ecart(self):
        """Écart entre le montant du relevé et le montant GL pointé (0 = concord)."""
        return (self.montant or Decimal('0')) - self.montant_pointe

    @property
    def est_concordante(self):
        """Vrai si au moins une ligne GL est pointée et l'écart est nul."""
        return self.lignes_gl.exists() and self.ecart == Decimal('0')


class PointageReleve(models.Model):
    """Table de liaison ligne de relevé ↔ ligne du grand livre (FG123).

    Matérialise un POINTAGE : on coche qu'une ligne de relevé correspond à une
    ligne d'écriture du grand livre. Unicité ``(ligne_releve, ligne_gl)`` : on
    ne pointe pas deux fois le même couple.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='pointages_releve',
        verbose_name='Société',
    )
    ligne_releve = models.ForeignKey(
        LigneReleve,
        on_delete=models.CASCADE,
        related_name='pointages',
        verbose_name='Ligne de relevé',
    )
    ligne_gl = models.ForeignKey(
        LigneEcriture,
        on_delete=models.CASCADE,
        related_name='pointages_releve',
        verbose_name='Ligne du grand livre',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Pointage de relevé'
        verbose_name_plural = 'Pointages de relevé'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['ligne_releve', 'ligne_gl'],
                name='uniq_pointage_releve_gl',
            ),
        ]

    def __str__(self):
        return f'Pointage relevé {self.ligne_releve_id} ↔ GL {self.ligne_gl_id}'


# ── FG124 — Caisse / petty cash (journal d'espèces) ────────────────────────

class Caisse(models.Model):
    """Caisse d'espèces (petty cash) rattachée à un ``CompteTresorerie`` caisse.

    Tient un JOURNAL D'ESPÈCES pour les achats terrain : chaque entrée/sortie de
    liquide est un ``MouvementCaisse``, et le SOLDE COURANT théorique se déduit du
    ``solde_initial`` + Σ(entrées) − Σ(sorties). Périodiquement, une
    ``ClotureCaisse`` constate le comptage physique (cash count) et fige les
    mouvements antérieurs : ils deviennent immuables (audit terrain).

    Le ``compte_tresorerie`` lié DOIT être de type ``caisse`` (classe 5). Une
    caisse par compte de trésorerie en pratique (unicité non contrainte pour
    rester purement additif). Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='caisses',
        verbose_name='Société',
    )
    compte_tresorerie = models.ForeignKey(
        CompteTresorerie,
        on_delete=models.PROTECT,
        related_name='caisses',
        verbose_name='Compte de trésorerie (caisse)',
    )
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    # Responsable de la caisse terrain (caissier). Optionnel.
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='caisses_responsable',
        verbose_name='Responsable',
    )
    # Fonds de caisse de départ (encaisse initiale).
    solde_initial = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Solde initial')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Caisse'
        verbose_name_plural = 'Caisses'
        ordering = ['libelle']

    def __str__(self):
        return f'Caisse {self.libelle}'

    def clean(self):
        super().clean()
        treso = self.compte_tresorerie
        if treso is not None and treso.type_compte != CompteTresorerie.Type.CAISSE:
            raise ValidationError(
                "Une caisse doit être rattachée à un compte de trésorerie de "
                "type « caisse ».")


class MouvementCaisse(models.Model):
    """Mouvement d'une caisse : entrée OU sortie d'espèces (FG124).

    Un mouvement porte un ``sens`` (entrée/sortie), un ``montant`` POSITIF, une
    ``date_mouvement``, un ``motif`` (achat terrain, appoint, dépense…) et la
    référence du justificatif (ticket/reçu). Une ``piece`` optionnelle pointe un
    document (URL/chemin du scan du reçu). Une fois la caisse clôturée à une date
    couvrant le mouvement, celui-ci devient IMMUABLE (audit). Si l'auto-posting
    est demandé, le mouvement porte un lien vers l'``EcritureComptable`` passée.
    """
    class Sens(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='mouvements_caisse',
        verbose_name='Société',
    )
    caisse = models.ForeignKey(
        Caisse,
        on_delete=models.CASCADE,
        related_name='mouvements',
        verbose_name='Caisse',
    )
    sens = models.CharField(
        max_length=10, choices=Sens.choices, verbose_name='Sens')
    date_mouvement = models.DateField(verbose_name='Date du mouvement')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    motif = models.CharField(max_length=255, verbose_name='Motif')
    # Référence du justificatif (ticket de caisse, reçu, n° de pièce).
    justificatif = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Référence du justificatif')
    # Lien vers le document scanné (URL/chemin) — optionnel.
    piece = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Pièce (document)')
    # Compte de contrepartie (classe 6 charge, ou autre) si le mouvement est posté.
    compte_contrepartie = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='mouvements_caisse',
        verbose_name='Compte de contrepartie',
    )
    posted = models.BooleanField(
        default=False, verbose_name='Postée au grand livre')
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mouvements_caisse',
        verbose_name='Écriture comptable',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mouvements_caisse_crees',
        verbose_name='Saisi par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Mouvement de caisse'
        verbose_name_plural = 'Mouvements de caisse'
        ordering = ['date_mouvement', 'id']

    def __str__(self):
        return f'{self.get_sens_display()} {self.montant} — {self.motif}'

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant <= 0:
            raise ValidationError(
                "Le montant d'un mouvement de caisse doit être strictement "
                "positif.")

    @property
    def montant_signe(self):
        """Montant signé : + pour une entrée, − pour une sortie."""
        montant = self.montant or Decimal('0')
        if self.sens == self.Sens.SORTIE:
            return -montant
        return montant

    # ── FG124 — Immutabilité d'un mouvement clôturé ────────────────────────
    def _verifier_caisse_ouverte(self):
        """Refuse de toucher un mouvement couvert par une clôture de caisse.

        Garde-fou d'audit : dès qu'une ``ClotureCaisse`` de la même caisse a une
        ``date_cloture`` ≥ ``date_mouvement``, le mouvement est figé (création,
        modification, suppression refusées). Lève ``ValidationError``.
        """
        if self.caisse_id is None or self.date_mouvement is None:
            return
        if ClotureCaisse.objects.filter(
                caisse_id=self.caisse_id,
                date_cloture__gte=self.date_mouvement).exists():
            raise ValidationError(
                "Caisse clôturée : le mouvement du "
                f"{self.date_mouvement} est verrouillé et ne peut plus être "
                "modifié.")

    def save(self, *args, **kwargs):
        self._verifier_caisse_ouverte()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._verifier_caisse_ouverte()
        return super().delete(*args, **kwargs)


class ClotureCaisse(models.Model):
    """Clôture de caisse : comptage physique (cash count) à une date (FG124).

    Constate l'ARRÊTÉ d'une caisse : le ``solde_theorique`` (figé = solde initial
    + Σ mouvements jusqu'à ``date_cloture``) est comparé au ``solde_compte``
    (espèces réellement comptées). L'``ecart`` = solde compté − solde théorique
    (> 0 excédent, < 0 manquant). Une fois posée, elle VERROUILLE tous les
    mouvements de la caisse antérieurs ou égaux à sa date (immutabilité d'audit).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='clotures_caisse',
        verbose_name='Société',
    )
    caisse = models.ForeignKey(
        Caisse,
        on_delete=models.CASCADE,
        related_name='clotures',
        verbose_name='Caisse',
    )
    date_cloture = models.DateField(verbose_name='Date de clôture')
    # Solde théorique figé à la clôture (solde initial + Σ mouvements ≤ date).
    solde_theorique = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Solde théorique')
    # Espèces réellement comptées en caisse (cash count).
    solde_compte = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Solde compté')
    # Écart = solde compté − solde théorique (figé).
    ecart = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Écart')
    commentaire = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Commentaire')
    cloturee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clotures_caisse',
        verbose_name='Clôturée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Clôture de caisse'
        verbose_name_plural = 'Clôtures de caisse'
        ordering = ['-date_cloture', '-id']
        constraints = [
            # Une seule clôture par caisse et par date.
            models.UniqueConstraint(
                fields=['caisse', 'date_cloture'],
                name='uniq_cloture_caisse_date',
            ),
        ]

    def __str__(self):
        return f'Clôture caisse {self.caisse_id} au {self.date_cloture}'
