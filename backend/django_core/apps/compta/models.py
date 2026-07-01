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
    # FG150 — axe analytique optionnel : ventile la ligne sur un centre de coût
    # (chantier/agence/marché/commercial). NULL = pas d'imputation analytique.
    # Rétro-compatible : champ ajouté en option, ne change aucune écriture
    # existante. ``CentreCout`` est défini plus bas (référence par chaîne).
    centre_cout = models.ForeignKey(
        'compta.CentreCout',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_ecriture',
        verbose_name='Centre de coût')

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


# ── FG125 — Virements internes entre comptes de trésorerie ─────────────────

class VirementInterne(models.Model):
    """Virement interne entre deux comptes de trésorerie (FG125).

    Transfère un montant d'un ``CompteTresorerie`` SOURCE vers un
    ``CompteTresorerie`` DESTINATION de la MÊME société (banque↔banque,
    banque↔caisse, caisse↔caisse). Le posting (``services.poster_virement``)
    passe une écriture ÉQUILIBRÉE à deux jambes dans le journal OD : débit du
    compte comptable de la destination (entrée), crédit du compte comptable de
    la source (sortie). Strictement additif ; ``company`` posée côté serveur,
    jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='virements_internes',
        verbose_name='Société',
    )
    compte_source = models.ForeignKey(
        CompteTresorerie,
        on_delete=models.PROTECT,
        related_name='virements_emis',
        verbose_name='Compte source',
    )
    compte_destination = models.ForeignKey(
        CompteTresorerie,
        on_delete=models.PROTECT,
        related_name='virements_recus',
        verbose_name='Compte destination',
    )
    date_virement = models.DateField(verbose_name='Date du virement')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    libelle = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Libellé')
    reference = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Référence')
    posted = models.BooleanField(
        default=False, verbose_name='Postée au grand livre')
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='virements_internes',
        verbose_name='Écriture comptable',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='virements_internes_crees',
        verbose_name='Saisi par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Virement interne'
        verbose_name_plural = 'Virements internes'
        ordering = ['-date_virement', '-id']

    def __str__(self):
        return (f'Virement {self.montant} {self.compte_source_id}'
                f'→{self.compte_destination_id} ({self.date_virement})')

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant <= 0:
            raise ValidationError(
                "Le montant d'un virement interne doit être strictement "
                "positif.")
        if (self.compte_source_id is not None
                and self.compte_source_id == self.compte_destination_id):
            raise ValidationError(
                "Les comptes source et destination doivent être différents.")


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

class LignePrevisionnelTresorerie(models.Model):
    """Ligne prévue d'un prévisionnel de trésorerie roulant (FG126).

    Saisie MANUELLE d'un flux attendu (crédit bancaire, leasing, salaires,
    acompte d'IS, loyer…) au-dessus de la projection AR/AP automatique. Chaque
    ligne porte une ``date_prevue`` (qui la range dans l'une des 13 semaines du
    prévisionnel roulant) et un ``montant`` SIGNÉ : positif = encaissement
    prévu, négatif = décaissement prévu. ``recurrence`` permet de la dupliquer
    chaque semaine/mois pour étaler une charge récurrente (informatif côté
    selector). ``company`` posée côté serveur. Strictement additif.
    """
    class Categorie(models.TextChoices):
        CREDIT = 'credit', 'Crédit / financement'
        LEASING = 'leasing', 'Leasing'
        SALAIRE = 'salaire', 'Salaires'
        IMPOT = 'impot', 'Impôts / acomptes IS'
        LOYER = 'loyer', 'Loyer'
        ENCAISSEMENT = 'encaissement', 'Encaissement prévu'
        DECAISSEMENT = 'decaissement', 'Décaissement prévu'
        AUTRE = 'autre', 'Autre'

    class Recurrence(models.TextChoices):
        AUCUNE = 'aucune', 'Ponctuelle'
        HEBDOMADAIRE = 'hebdomadaire', 'Hebdomadaire'
        MENSUELLE = 'mensuelle', 'Mensuelle'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_previsionnel_tresorerie',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    categorie = models.CharField(
        max_length=15, choices=Categorie.choices,
        default=Categorie.AUTRE, verbose_name='Catégorie')
    date_prevue = models.DateField(verbose_name='Date prévue')
    # Montant SIGNÉ : + encaissement prévu, − décaissement prévu.
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    recurrence = models.CharField(
        max_length=15, choices=Recurrence.choices,
        default=Recurrence.AUCUNE, verbose_name='Récurrence')
    commentaire = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Commentaire')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de prévisionnel de trésorerie'
        verbose_name_plural = 'Lignes de prévisionnel de trésorerie'
        ordering = ['date_prevue', 'id']

    def __str__(self):
        return f'{self.date_prevue} — {self.libelle} ({self.montant})'

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant == 0:
            raise ValidationError(
                "Le montant d'une ligne prévue ne peut être nul.")


# ── FG127 / FG128 — Effets (chèques / traites) à recevoir & à payer ────────

class Effet(models.Model):
    """Effet de commerce : chèque ou traite (LCN) à recevoir OU à payer.

    Modèle marocain OMNIPRÉSENT en B2B : un effet (chèque, traite/LCN, billet à
    ordre) porte un ``sens`` — ``recevoir`` (client, FG127) ou ``payer``
    (fournisseur, FG128) — un ``montant``, une ``date_echeance`` (calendrier qui
    alimente la trésorerie), une ``banque``, et un ``statut`` qui suit son
    cycle de vie :

    * À recevoir : ``portefeuille`` → ``remis`` (déposé en banque via un
      ``BordereauRemise``, FG129) → ``encaisse`` → ``impaye`` (rejet, FG130).
    * À payer : ``portefeuille`` (émis) → ``paye`` → ``impaye`` (rejeté).

    Le tiers (client/fournisseur) est référencé en string-FK (``tiers_type`` /
    ``tiers_id``) — jamais d'import cross-app de modèle. ``company`` posée côté
    serveur. Strictement additif.
    """
    class Sens(models.TextChoices):
        RECEVOIR = 'recevoir', 'À recevoir (client)'
        PAYER = 'payer', 'À payer (fournisseur)'

    class TypeEffet(models.TextChoices):
        CHEQUE = 'cheque', 'Chèque'
        TRAITE = 'traite', 'Traite / LCN'
        BILLET = 'billet', 'Billet à ordre'

    class Statut(models.TextChoices):
        PORTEFEUILLE = 'portefeuille', 'En portefeuille'
        REMIS = 'remis', "Remis à l'encaissement"
        ENCAISSE = 'encaisse', 'Encaissé'
        PAYE = 'paye', 'Payé'
        IMPAYE = 'impaye', 'Impayé / rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='effets',
        verbose_name='Société',
    )
    sens = models.CharField(
        max_length=10, choices=Sens.choices, verbose_name='Sens')
    type_effet = models.CharField(
        max_length=10, choices=TypeEffet.choices,
        default=TypeEffet.CHEQUE, verbose_name="Type d'effet")
    numero = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Numéro (chèque/traite)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    date_emission = models.DateField(verbose_name="Date d'émission")
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    banque = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Banque (tirée/domiciliation)')
    tireur = models.CharField(
        max_length=160, blank=True, default='',
        verbose_name='Tireur / bénéficiaire')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.PORTEFEUILLE, verbose_name='Statut')
    # Tiers (client/fournisseur) en string-FK — jamais d'import cross-app.
    tiers_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')
    # Bordereau de remise (FG129) qui a déposé cet effet, le cas échéant.
    bordereau = models.ForeignKey(
        'BordereauRemise',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='effets',
        verbose_name='Bordereau de remise',
    )
    # Frais de rejet figés en cas d'impayé (FG130).
    frais_rejet = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Frais de rejet')
    commentaire = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Commentaire')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='effets_crees',
        verbose_name='Saisi par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Effet (chèque / traite)'
        verbose_name_plural = 'Effets (chèques / traites)'
        ordering = ['date_echeance', 'id']

    def __str__(self):
        return (f'{self.get_type_effet_display()} {self.montant} '
                f'{self.get_sens_display()} — éch. {self.date_echeance}')

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant <= 0:
            raise ValidationError(
                "Le montant d'un effet doit être strictement positif.")
        if (self.date_emission and self.date_echeance
                and self.date_echeance < self.date_emission):
            raise ValidationError(
                "L'échéance doit être postérieure ou égale à l'émission.")

    @property
    def est_solde(self):
        """Vrai si l'effet est dans un état terminal (encaissé/payé)."""
        return self.statut in (self.Statut.ENCAISSE, self.Statut.PAYE)


# ── FG129 — Bordereau de remise en banque (chèques / effets) ───────────────

class BordereauRemise(models.Model):
    """Bordereau de remise en banque d'effets à recevoir (FG129).

    Regroupe plusieurs ``Effet`` (à recevoir) pour un DÉPÔT groupé sur un
    ``CompteTresorerie`` bancaire. Le posting (``services.poster_bordereau``)
    passe l'écriture de remise (débit « effets à l'encaissement » / crédit
    « effets à recevoir » par défaut), passe les effets liés en ``remis`` et fige
    le total. ``company`` posée côté serveur. Strictement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        REMIS = 'remis', 'Remis en banque'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='bordereaux_remise',
        verbose_name='Société',
    )
    compte_tresorerie = models.ForeignKey(
        CompteTresorerie,
        on_delete=models.PROTECT,
        related_name='bordereaux_remise',
        verbose_name='Compte de trésorerie (banque)',
    )
    reference = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Référence')
    date_remise = models.DateField(verbose_name='Date de remise')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Total remis')
    posted = models.BooleanField(
        default=False, verbose_name='Postée au grand livre')
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bordereaux_remise',
        verbose_name='Écriture comptable',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bordereaux_remise_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bordereau de remise'
        verbose_name_plural = 'Bordereaux de remise'
        ordering = ['-date_remise', '-id']

    def __str__(self):
        return f'Bordereau {self.reference or self.id} ({self.date_remise})'

    @property
    def est_remis(self):
        return self.statut == self.Statut.REMIS


# ── FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) ────

class Rapprochement(models.Model):
    """Rapprochement 3 voies d'un achat avant paiement (FG131).

    Contrôle de pré-paiement qui confronte les TROIS montants HT d'un même achat
    fournisseur : ce qui a été COMMANDÉ (bon de commande fournisseur), ce qui a
    été REÇU (réceptions confirmées) et ce qui a été FACTURÉ (factures
    fournisseur). Les trois documents vivent dans ``apps.stock`` ; ce modèle ne
    fait que les RÉFÉRENCER (FK chaîne ``stock.BonCommandeFournisseur``) et lit
    leurs montants UNIQUEMENT à travers ``apps.stock.selectors`` — il ne
    duplique aucun document d'achat.

    À chaque évaluation (``services.evaluer_rapprochement``) les trois montants
    sont rafraîchis (snapshot) et l'``ecart`` reçu↔facturé est recalculé. Tant
    que l'écart dépasse la tolérance, le rapprochement reste ``ecart`` (bloquant
    pour le paiement) ; concordant sinon. Un responsable peut le ``valider``
    explicitement (bon à payer). ``company`` posée côté serveur, jamais lue du
    corps de requête. Strictement additif ; montants d'achat INTERNES.
    """
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ECART = 'ecart', 'Écart détecté'
        CONCORDANT = 'concordant', 'Concordant'
        VALIDE = 'valide', 'Validé (bon à payer)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='compta_rapprochements',
        verbose_name='Société',
    )
    # Référence au bon de commande fournisseur (apps.stock) par FK chaîne —
    # jamais d'import du modèle stock. related_name préfixé par le label d'app.
    bon_commande = models.ForeignKey(
        'stock.BonCommandeFournisseur',
        on_delete=models.CASCADE,
        related_name='compta_rapprochements',
        verbose_name='Bon de commande fournisseur',
    )
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.EN_ATTENTE, verbose_name='Statut')
    # Tolérance d'écart absolue (arrondis, frais de port…) en deçà de laquelle
    # reçu et facturé sont jugés concordants.
    tolerance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Tolérance')
    # Snapshot des trois montants HT à la dernière évaluation (lus via les
    # sélecteurs de stock). Permet d'auditer ce qui a été comparé.
    montant_commande = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant commandé (HT)')
    montant_recu = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant reçu (HT)')
    montant_facture = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant facturé (HT)')
    # Écart reçu↔facturé (facturé − reçu) figé à la dernière évaluation : le
    # contrôle bloquant avant paiement (on ne paie pas plus que reçu).
    ecart = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Écart (facturé − reçu)')
    note = models.TextField(blank=True, null=True, verbose_name='Note')
    date_evaluation = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière évaluation')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='compta_rapprochements_valides',
        verbose_name='Validé par',
    )
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Validé le')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='compta_rapprochements_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Rapprochement 3 voies'
        verbose_name_plural = 'Rapprochements 3 voies'
        ordering = ['-date_creation', '-id']
        # Un seul rapprochement par BCF et par société.
        unique_together = [('company', 'bon_commande')]

    def __str__(self):
        return f'Rapprochement BCF {self.bon_commande_id} ({self.statut})'

    @property
    def ecart_commande_recu(self):
        """Écart commandé↔reçu (reçu − commandé) — informatif (livraison
        partielle si négatif)."""
        return (self.montant_recu or Decimal('0')) - (
            self.montant_commande or Decimal('0'))

    @property
    def est_concordant(self):
        """True si l'écart reçu↔facturé tient dans la tolérance."""
        return abs(self.ecart or Decimal('0')) <= (
            self.tolerance or Decimal('0'))

    @property
    def bon_a_payer(self):
        """True si le rapprochement autorise le paiement (concordant ou
        explicitement validé)."""
        return self.statut in (self.Statut.CONCORDANT, self.Statut.VALIDE)


# ── FG133 — Campagnes de règlement fournisseurs (payment run) ──────────────

class PaymentRun(models.Model):
    """Campagne de règlement fournisseurs (payment run, FG133).

    Regroupe une sélection de dettes fournisseur DUES à régler en un lot : on
    choisit les échéances à payer (lignes ``PaymentRunLine``), on retient un
    ``mode_paiement`` (chèque/virement) et un compte de trésorerie payeur, puis
    on POSTE le lot au grand livre en une seule écriture (débit 4411
    Fournisseurs par ligne / crédit 5141 Banque pour le total) via
    ``services.poster_payment_run``. Pour un run en virement, un fichier bancaire
    peut ensuite être exporté (FG134).

    Cycle de vie : ``brouillon`` (sélection en cours) → ``proposee`` (proposition
    figée) → ``postee`` (écriture passée, irréversible). Les fournisseurs sont
    référencés en string-FK (``tiers_type``/``tiers_id``) sur les lignes — jamais
    d'import cross-app de modèle. ``company`` posée côté serveur. Strictement
    additif ; ``related_name`` préfixés par le label d'app.
    """
    class ModePaiement(models.TextChoices):
        VIREMENT = 'virement', 'Virement bancaire'
        CHEQUE = 'cheque', 'Chèque'
        ESPECES = 'especes', 'Espèces'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PROPOSEE = 'proposee', 'Proposition figée'
        POSTEE = 'postee', 'Postée au grand livre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='compta_payment_runs',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Référence')
    mode_paiement = models.CharField(
        max_length=10, choices=ModePaiement.choices,
        default=ModePaiement.VIREMENT, verbose_name='Mode de paiement')
    # Compte de trésorerie payeur (banque). Requis pour poster un virement/chèque.
    compte_tresorerie = models.ForeignKey(
        CompteTresorerie,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='compta_payment_runs',
        verbose_name='Compte de trésorerie (payeur)',
    )
    date_paiement = models.DateField(verbose_name='Date de paiement')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Total proposé')
    posted = models.BooleanField(
        default=False, verbose_name='Postée au grand livre')
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='compta_payment_runs',
        verbose_name='Écriture comptable',
    )
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='compta_payment_runs_crees',
        verbose_name='Créée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Campagne de règlement fournisseurs'
        verbose_name_plural = 'Campagnes de règlement fournisseurs'
        ordering = ['-date_creation', '-id']

    def __str__(self):
        return (f'Règlement {self.reference or self.id} '
                f'({self.get_mode_paiement_display()}, {self.statut})')

    @property
    def est_postee(self):
        return self.statut == self.Statut.POSTEE


class PaymentRunLine(models.Model):
    """Ligne d'une campagne de règlement : une échéance fournisseur à payer.

    Porte le fournisseur (string-FK ``tiers_type``/``tiers_id``), le ``montant``
    à régler, une ``reference`` de pièce (facture/échéance) et les coordonnées
    bancaires (``rib``/``iban``) figées pour l'export du fichier de virement
    (FG134). ``beneficiaire`` est le nom figé du fournisseur au moment de la
    sélection. Strictement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='compta_payment_run_lines',
        verbose_name='Société',
    )
    payment_run = models.ForeignKey(
        PaymentRun,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Campagne de règlement',
    )
    # Fournisseur en string-FK — jamais d'import cross-app de modèle.
    tiers_type = models.CharField(
        max_length=20, blank=True, default='fournisseur',
        verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')
    beneficiaire = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Bénéficiaire')
    reference = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Référence (facture / échéance)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant à régler')
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name="Date d'échéance")
    rib = models.CharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    iban = models.CharField(
        max_length=40, blank=True, default='', verbose_name='IBAN')

    class Meta:
        verbose_name = 'Ligne de règlement fournisseur'
        verbose_name_plural = 'Lignes de règlement fournisseur'
        ordering = ['date_echeance', 'id']

    def __str__(self):
        return f'{self.beneficiaire or self.tiers_id} — {self.montant}'

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant <= 0:
            raise ValidationError(
                "Le montant d'une ligne de règlement doit être strictement "
                "positif.")


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
        CompteComptable,
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
        EcritureComptable,
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
        CompteTresorerie,
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
        EcritureComptable,
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

    class Meta:
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
        CompteComptable,
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
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indemnites_chantier_charge',
        verbose_name='Écriture de charge',
    )
    motif_rejet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de rejet')
    # ── Remboursement ──
    compte_tresorerie = models.ForeignKey(
        CompteTresorerie,
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
        EcritureComptable,
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


# ── FG137 — Préparation de la déclaration de TVA ────────────────────────────

class DeclarationTVA(models.Model):
    """Préparation d'une déclaration de TVA sur une période (FG137).

    Constate, pour une période ``[date_debut ; date_fin]``, le résultat de TVA à
    déclarer : ``tva_collectee`` (TVA facturée, comptes de classe 4455…) moins
    ``tva_deductible`` (TVA récupérable, comptes de classe 3455…), tous deux
    DÉRIVÉS du grand livre de la compta (mouvements de la période sur ces
    comptes — AUCUN import cross-app). La déclaration porte un ``regime``
    (mensuel/trimestriel) et une ``methode`` (débit/encaissement) qui qualifient
    le dépôt déclaratif ; les montants sont FIGÉS au moment de la préparation
    (snapshot auditable) et restitués à l'identique à l'écran et à l'export CSV.

    ``tva_a_declarer`` = max(0, collectée − déductible). Lorsque la TVA
    déductible dépasse la collectée, l'excédent devient un ``credit_reportable``
    sur la période suivante (le montant à déclarer est alors nul). Un
    ``credit_anterieur`` (crédit reporté d'une déclaration précédente) peut être
    saisi et vient en déduction du montant net dû. Multi-société : ``company``
    posée côté serveur, jamais lue du corps de requête.
    """
    class Regime(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'

    class Methode(models.TextChoices):
        DEBIT = 'debit', 'Débit'
        ENCAISSEMENT = 'encaissement', 'Encaissement'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PREPAREE = 'preparee', 'Préparée'
        DEPOSEE = 'deposee', 'Déposée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='declarations_tva',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence')
    regime = models.CharField(
        max_length=12, choices=Regime.choices,
        default=Regime.MENSUEL, verbose_name='Régime')
    methode = models.CharField(
        max_length=12, choices=Methode.choices,
        default=Methode.DEBIT, verbose_name='Méthode')
    date_debut = models.DateField(verbose_name='Début de période')
    date_fin = models.DateField(verbose_name='Fin de période')
    # ── Montants FIGÉS au calcul (snapshot auditable) ──
    tva_collectee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='TVA collectée')
    tva_deductible = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='TVA déductible')
    # Crédit de TVA reporté d'une période antérieure (saisi), déduit du net dû.
    credit_anterieur = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Crédit de TVA antérieur')
    # TVA nette à déclarer = max(0, collectée − déductible − crédit antérieur).
    tva_a_declarer = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='TVA à déclarer')
    # Excédent reportable sur la période suivante (crédit de TVA).
    credit_reportable = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Crédit de TVA reportable')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='declarations_tva_creees',
        verbose_name='Préparée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Déclaration de TVA'
        verbose_name_plural = 'Déclarations de TVA'
        ordering = ['-date_fin', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_decl_tva_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "TVA"} — '
                f'{self.date_debut}–{self.date_fin} ({self.tva_a_declarer})')

    def clean(self):
        super().clean()
        if (self.date_debut and self.date_fin
                and self.date_fin < self.date_debut):
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début.")
        if self.credit_anterieur is not None and self.credit_anterieur < 0:
            raise ValidationError(
                "Le crédit de TVA antérieur ne peut pas être négatif.")

    def recalculer(self):
        """(Re)calcule la TVA à déclarer et le crédit reportable depuis le snapshot.

        ``net`` = collectée − déductible − crédit antérieur. S'il est positif,
        c'est le montant à déclarer (et payer) ; s'il est négatif, sa valeur
        absolue devient un crédit reportable sur la période suivante.
        """
        collectee = self.tva_collectee or Decimal('0')
        deductible = self.tva_deductible or Decimal('0')
        anterieur = self.credit_anterieur or Decimal('0')
        net = collectee - deductible - anterieur
        if net >= 0:
            self.tva_a_declarer = net
            self.credit_reportable = Decimal('0')
        else:
            self.tva_a_declarer = Decimal('0')
            self.credit_reportable = -net
        return self


# ── FG139 — Retenue à la source (RAS) sur honoraires/prestations ────────────

class RetenueSource(models.Model):
    """Retenue à la source (RAS) sur une pièce d'honoraires/prestation (FG139).

    Obligation marocaine : sur certaines prestations (honoraires, redevances,
    rémunérations de prestataires), le débiteur (la société) doit RETENIR un
    pourcentage du montant payé au prestataire/fournisseur et le REVERSER à la
    DGT (déclaration sur bordereau de versement). On constate ici, par pièce et
    par tiers, la ``base`` (assiette HT/TTC de la prestation), le ``taux`` de RAS
    applicable et le ``montant`` retenu = base × taux (arrondi 2 décimales). Le
    montant net réellement versé au prestataire = base − montant retenu.

    Le tiers est référencé par un auxiliaire string-FK (``tiers_type`` /
    ``tiers_id``) — JAMAIS un import cross-app de modèle — exactement comme une
    ``LigneEcriture``. ``identifiant_fiscal`` porte l'IF/ICE du prestataire,
    exigé sur le bordereau. Multi-société : ``company`` posée côté serveur,
    jamais lue du corps de requête. Le snapshot (base/taux/montant) est FIGÉ au
    moment de l'enregistrement et restitué à l'identique à l'écran et au CSV.
    """
    class TypePrestation(models.TextChoices):
        HONORAIRES = 'honoraires', 'Honoraires'
        REDEVANCES = 'redevances', 'Redevances'
        LOYERS = 'loyers', 'Loyers'
        PRESTATIONS = 'prestations', 'Prestations de services'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        A_VERSER = 'a_verser', 'À verser'
        VERSEE = 'versee', 'Versée'

    # Taux légal usuel pour une RAS sur honoraires/prestations versés à un
    # prestataire non patenté (informatif : le taux réel est saisi par pièce).
    TAUX_DEFAUT = Decimal('10.00')

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='retenues_source',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence')
    # Pièce / facture fournisseur d'origine (texte libre, informatif).
    piece = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Pièce / facture')
    date_piece = models.DateField(verbose_name='Date de la pièce')
    type_prestation = models.CharField(
        max_length=12, choices=TypePrestation.choices,
        default=TypePrestation.HONORAIRES, verbose_name='Type de prestation')
    # ── Tiers prestataire (auxiliaire string-FK, jamais d'import modèle) ──
    tiers_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')
    tiers_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Nom du prestataire')
    identifiant_fiscal = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Identifiant fiscal (IF/ICE)')
    # ── Montants FIGÉS au calcul (snapshot auditable) ──
    base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Base imposable')
    taux = models.DecimalField(
        max_digits=5, decimal_places=2, default=TAUX_DEFAUT,
        verbose_name='Taux de RAS (%)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant retenu')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_VERSER, verbose_name='Statut')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='retenues_source_creees',
        verbose_name='Enregistrée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Retenue à la source'
        verbose_name_plural = 'Retenues à la source'
        ordering = ['-date_piece', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_ras_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "RAS"} — '
                f'{self.tiers_nom or self.piece} ({self.montant})')

    @property
    def net_a_payer(self):
        """Montant net réellement versé au prestataire (base − retenue)."""
        return (self.base or Decimal('0')) - (self.montant or Decimal('0'))

    def clean(self):
        super().clean()
        if self.base is not None and self.base < 0:
            raise ValidationError(
                "La base imposable ne peut pas être négative.")
        if self.taux is not None and (self.taux < 0 or self.taux > 100):
            raise ValidationError(
                "Le taux de RAS doit être compris entre 0 et 100 %.")

    def recalculer(self):
        """(Re)calcule le montant retenu = base × taux %, arrondi 2 décimales."""
        base = self.base or Decimal('0')
        taux = self.taux or Decimal('0')
        self.montant = (base * taux / Decimal('100')).quantize(
            Decimal('0.01'))
        return self


# ── FG144 — Droit de timbre sur encaissements en espèces ───────────────────
class TimbreFiscal(models.Model):
    """Droit de timbre (stamp duty) sur un encaissement réglé en ESPÈCES (FG144).

    Obligation marocaine (Code Général des Impôts, droit de timbre de quittance) :
    tout paiement encaissé EN ESPÈCES est soumis à un droit de timbre proportionnel
    — taux légal 0,25 % de la somme reçue, avec un MINIMUM forfaitaire par quittance.
    Les règlements NON espèces (virement, chèque, carte, prélèvement…) en sont
    EXONÉRÉS : ce snapshot n'existe donc que pour les encaissements cash. On fige
    par encaissement la ``base`` (montant encaissé en espèces), le ``taux`` appliqué,
    le ``minimum`` forfaitaire et le ``montant`` du timbre = max(base × taux %,
    minimum), arrondi à 2 décimales.

    Le paiement d'origine (``apps.ventes.Paiement``) est référencé UNIQUEMENT par
    string-id (``paiement_id`` / ``facture_ref``) — JAMAIS un import cross-app de
    modèle, exactement comme une ``LigneEcriture`` ou une ``RetenueSource``. Tout
    est multi-société : ``company`` posée côté serveur, jamais lue du corps de
    requête. Le snapshot (base/taux/minimum/montant) est FIGÉ au moment de
    l'enregistrement et restitué à l'identique à l'écran et au CSV.
    """
    class Statut(models.TextChoices):
        A_VERSER = 'a_verser', 'À verser'
        VERSEE = 'versee', 'Versée'

    # Taux légal du droit de timbre de quittance (espèces) : 0,25 %.
    TAUX_DEFAUT = Decimal('0.25')
    # Minimum forfaitaire de perception par quittance (statutaire).
    MINIMUM_DEFAUT = Decimal('0.25')

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='timbres_fiscaux',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence')
    date_encaissement = models.DateField(verbose_name="Date d'encaissement")
    # ── Paiement d'origine (string-ref, jamais d'import modèle ventes) ──
    paiement_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID du paiement d'origine")
    facture_ref = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Facture / pièce')
    mode_reglement = models.CharField(
        max_length=20, blank=True, default='especes',
        verbose_name='Mode de règlement')
    # ── Tiers payeur (auxiliaire string-FK, jamais d'import modèle) ──
    tiers_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')
    tiers_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Nom du payeur')
    # ── Montants FIGÉS au calcul (snapshot auditable) ──
    base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant encaissé (base)')
    taux = models.DecimalField(
        max_digits=5, decimal_places=2, default=TAUX_DEFAUT,
        verbose_name='Taux du droit de timbre (%)')
    minimum = models.DecimalField(
        max_digits=8, decimal_places=2, default=MINIMUM_DEFAUT,
        verbose_name='Minimum de perception')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Droit de timbre')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_VERSER, verbose_name='Statut')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='timbres_fiscaux_crees',
        verbose_name='Enregistré par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Droit de timbre'
        verbose_name_plural = 'Droits de timbre'
        ordering = ['-date_encaissement', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_timbre_reference',
            ),
            # Idempotence : un même paiement espèces ne produit qu'un timbre par
            # société (NULL paiement_id non contraint → saisies libres OK).
            models.UniqueConstraint(
                fields=['company', 'paiement_id'],
                condition=models.Q(paiement_id__isnull=False),
                name='uniq_timbre_paiement',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "TIMBRE"} — '
                f'{self.tiers_nom or self.facture_ref} ({self.montant})')

    def clean(self):
        super().clean()
        if self.base is not None and self.base < 0:
            raise ValidationError(
                "Le montant encaissé ne peut pas être négatif.")
        if self.taux is not None and (self.taux < 0 or self.taux > 100):
            raise ValidationError(
                "Le taux du droit de timbre doit être compris entre 0 et 100 %.")
        if self.minimum is not None and self.minimum < 0:
            raise ValidationError(
                "Le minimum de perception ne peut pas être négatif.")

    def recalculer(self):
        """(Re)calcule le droit de timbre = max(base × taux %, minimum).

        Le droit de timbre proportionnel s'applique avec un plancher forfaitaire :
        on retient le plus grand des deux, arrondi à 2 décimales. Une base nulle ne
        génère aucun timbre (pas d'encaissement = pas de quittance)."""
        base = self.base or Decimal('0')
        taux = self.taux or Decimal('0')
        minimum = self.minimum or Decimal('0')
        if base <= 0:
            self.montant = Decimal('0.00')
            return self
        proportionnel = (base * taux / Decimal('100')).quantize(
            Decimal('0.01'))
        self.montant = max(proportionnel, minimum.quantize(Decimal('0.01')))
        return self


# ── FG145 — Retenue de garantie & cautions bancaires sur marchés ───────────
class RetenueGarantie(models.Model):
    """Retenue de garantie (RG / bonne fin) prélevée sur un marché (FG145).

    Sur les marchés de travaux/fournitures, le maître d'ouvrage (ou le client)
    RETIENT un pourcentage (usuellement 5 ou 10 %) de chaque décompte/facture en
    garantie de la bonne exécution ; cette somme est LIBÉRÉE (restituée) à une
    date d'échéance (réception définitive / fin de la période de garantie). On
    fige par marché/facture la ``base`` (montant du décompte sur lequel porte la
    retenue), le ``taux`` de RG et le ``montant`` retenu = base × taux %
    (arrondi 2 décimales), avec la date de constitution et la date de levée
    prévue ; ``date_liberation`` est posée quand la RG est effectivement libérée.

    Le marché / la facture d'origine est référencé UNIQUEMENT par string-ref
    (``marche_ref`` / ``facture_id`` / ``facture_ref``) — JAMAIS un import
    cross-app de modèle, exactement comme une ``LigneEcriture`` ou une
    ``RetenueSource``. Tout est multi-société : ``company`` posée côté serveur,
    jamais lue du corps de requête. Le snapshot (base/taux/montant) est FIGÉ au
    moment de l'enregistrement et restitué à l'identique à l'écran et au CSV.
    """
    class Statut(models.TextChoices):
        RETENUE = 'retenue', 'Retenue'
        LIBEREE = 'liberee', 'Libérée'

    # Taux usuel d'une retenue de garantie sur marché (informatif : le taux réel
    # est saisi par marché ; 10 % est le plafond courant côté CCAG-Travaux).
    TAUX_DEFAUT = Decimal('10.00')

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='retenues_garantie',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence')
    # Marché / facture d'origine (string-ref, jamais d'import modèle ventes).
    marche_ref = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Marché / contrat')
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la facture')
    facture_ref = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Facture / décompte')
    # ── Tiers (maître d'ouvrage / client) — auxiliaire string-FK ──
    tiers_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')
    tiers_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Maître d\'ouvrage / client')
    # ── Montants FIGÉS au calcul (snapshot auditable) ──
    base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Base du décompte')
    taux = models.DecimalField(
        max_digits=5, decimal_places=2, default=TAUX_DEFAUT,
        verbose_name='Taux de RG (%)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant retenu')
    date_constitution = models.DateField(
        verbose_name='Date de constitution')
    date_levee_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de levée prévue')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.RETENUE, verbose_name='Statut')
    date_liberation = models.DateField(
        null=True, blank=True, verbose_name='Date de libération')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='retenues_garantie_creees',
        verbose_name='Enregistrée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Retenue de garantie'
        verbose_name_plural = 'Retenues de garantie'
        ordering = ['-date_constitution', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_rg_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "RG"} — '
                f'{self.tiers_nom or self.marche_ref} ({self.montant})')

    def clean(self):
        super().clean()
        if self.base is not None and self.base < 0:
            raise ValidationError(
                "La base du décompte ne peut pas être négative.")
        if self.taux is not None and (self.taux < 0 or self.taux > 100):
            raise ValidationError(
                "Le taux de RG doit être compris entre 0 et 100 %.")

    def recalculer(self):
        """(Re)calcule le montant retenu = base × taux %, arrondi 2 décimales."""
        base = self.base or Decimal('0')
        taux = self.taux or Decimal('0')
        self.montant = (base * taux / Decimal('100')).quantize(
            Decimal('0.01'))
        return self


class CautionBancaire(models.Model):
    """Caution / garantie bancaire émise sur un marché (FG145).

    Sur un marché, la banque émet pour le compte de l'entreprise des cautions au
    profit du maître d'ouvrage : caution PROVISOIRE (à la soumission), caution
    DÉFINITIVE (à l'attribution), retenue de garantie (en remplacement de la RG
    prélevée), ou caution de RESTITUTION d'acompte. Chacune porte un ``montant``,
    une ``date_emission`` et une ``date_echeance``, et reste ACTIVE jusqu'à sa
    MAINLEVÉE (la banque est déliée) puis sa RESTITUTION. On suit ici l'engagement
    hors-bilan : la banque, le marché concerné et les dates de levée.

    Le marché est référencé UNIQUEMENT par string-ref (``marche_ref``) — JAMAIS
    un import cross-app de modèle. Tout est multi-société : ``company`` posée côté
    serveur, jamais lue du corps de requête.
    """
    class TypeCaution(models.TextChoices):
        PROVISOIRE = 'provisoire', 'Caution provisoire'
        DEFINITIVE = 'definitive', 'Caution définitive'
        RETENUE_GARANTIE = 'retenue_garantie', 'Caution de retenue de garantie'
        RESTITUTION = 'restitution', "Caution de restitution d'acompte"

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        LEVEE = 'levee', 'Mainlevée'
        RESTITUEE = 'restituee', 'Restituée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='cautions_bancaires',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence')
    type_caution = models.CharField(
        max_length=20, choices=TypeCaution.choices,
        default=TypeCaution.DEFINITIVE, verbose_name='Type de caution')
    # Marché / contrat (string-ref, jamais d'import modèle ventes).
    marche_ref = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Marché / contrat')
    tiers_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Bénéficiaire (maître d\'ouvrage)')
    banque = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Banque émettrice')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant de la caution')
    date_emission = models.DateField(verbose_name='Date d\'émission')
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name='Date d\'échéance')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.ACTIVE, verbose_name='Statut')
    date_mainlevee = models.DateField(
        null=True, blank=True, verbose_name='Date de mainlevée')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cautions_bancaires_creees',
        verbose_name='Enregistrée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Caution bancaire'
        verbose_name_plural = 'Cautions bancaires'
        ordering = ['-date_emission', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_caution_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "CAUTION"} — '
                f'{self.get_type_caution_display()} ({self.montant})')

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant < 0:
            raise ValidationError(
                "Le montant de la caution ne peut pas être négatif.")


# ── FG146 — Reconnaissance du revenu par avancement (% completion) ──────────

class ContratAvancement(models.Model):
    """Contrat / chantier pluri-tranches reconnu au pourcentage d'avancement.

    Sur un chantier long (plusieurs tranches/décomptes), le CA n'est PAS
    reconnu à la facturation mais au PRORATA de l'avancement réel (méthode du
    pourcentage d'avancement, « percentage-of-completion »). On fige ici le
    revenu total contractuel (``revenu_total``, HT) et le coût total estimé
    (``cout_total_estime``) ; chaque ``AvancementRevenu`` ajoute un constat
    périodique d'avancement et reconnaît le CA cumulé correspondant.

    Le chantier/marché d'origine est référencé UNIQUEMENT par string-ref
    (``chantier_ref`` / ``marche_ref`` / ``client_id`` / ``client_nom``) —
    JAMAIS un import cross-app de modèle. Tout est multi-société : ``company``
    posée côté serveur, jamais lue du corps de requête. Purement additif : ne
    touche ni devis, ni facture, ni leur statut (rule #4).
    """
    class Methode(models.TextChoices):
        COUTS = 'couts', 'Cost-to-cost (coûts engagés / coûts estimés)'
        SAISIE = 'saisie', "Avancement physique saisi (%)"

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_avancement',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    # Chantier / marché / client d'origine (string-ref, jamais d'import modèle).
    chantier_ref = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Chantier')
    marche_ref = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Marché')
    client_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du client')
    client_nom = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Client')
    methode = models.CharField(
        max_length=10, choices=Methode.choices, default=Methode.COUTS,
        verbose_name="Méthode d'avancement")
    revenu_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Revenu total contractuel (HT)')
    cout_total_estime = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Coût total estimé')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de fin prévue')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS,
        verbose_name='Statut')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrats_avancement_crees',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Contrat à l'avancement"
        verbose_name_plural = "Contrats à l'avancement"
        ordering = ['-date_creation', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_contrat_av_ref',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "CONTRAT"} — '
                f'{self.libelle or self.chantier_ref}')

    def clean(self):
        super().clean()
        if self.revenu_total is not None and self.revenu_total < 0:
            raise ValidationError(
                "Le revenu total ne peut pas être négatif.")
        if (self.cout_total_estime is not None
                and self.cout_total_estime < 0):
            raise ValidationError(
                "Le coût total estimé ne peut pas être négatif.")

    @property
    def revenu_reconnu(self):
        """CA cumulé déjà reconnu = somme des constats d'avancement."""
        total = self.avancements.aggregate(s=models.Sum('revenu_periode'))
        return total['s'] or Decimal('0')


class AvancementRevenu(models.Model):
    """Constat périodique d'avancement et de revenu reconnu (FG146).

    À chaque arrêté (mensuel ou par décompte), on fige le ``pourcentage``
    d'avancement cumulé (0–100) ; le revenu cumulé à reconnaître =
    ``revenu_total`` × pourcentage %, et le ``revenu_periode`` est le DELTA par
    rapport au cumul déjà reconnu (snapshot figé, auditable). Quand l'écriture
    OD est passée (3427 « clients - factures à établir » / 71xx « ventes »),
    ``ecriture_id`` est renseignée et le constat devient immuable.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='avancements_revenu',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        ContratAvancement,
        on_delete=models.CASCADE,
        related_name='avancements',
        verbose_name='Contrat',
    )
    date_arrete = models.DateField(verbose_name="Date d'arrêté")
    pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name="Avancement cumulé (%)")
    cout_engage_cumule = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Coût engagé cumulé')
    # Snapshots FIGÉS au constat (auditable).
    revenu_cumule = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Revenu cumulé reconnu')
    revenu_periode = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Revenu reconnu sur la période')
    # Écriture OD de reconnaissance (string-ref interne à compta).
    ecriture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'écriture OD")
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='avancements_revenu_crees',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Constat d'avancement"
        verbose_name_plural = "Constats d'avancement"
        ordering = ['contrat', 'date_arrete', 'id']

    def __str__(self):
        return f'{self.contrat_id} @ {self.pourcentage}% ({self.date_arrete})'

    def clean(self):
        super().clean()
        if self.pourcentage is not None and (
                self.pourcentage < 0 or self.pourcentage > 100):
            raise ValidationError(
                "L'avancement doit être compris entre 0 et 100 %.")


# ── FG147 — Produits constatés d'avance & travaux en cours (WIP) ────────────

class TravauxEnCours(models.Model):
    """Régularisation de cut-off : PCA (produits différés) ou WIP (en-cours).

    Deux natures de régularisation de fin de période (rattachement des
    produits/charges au bon exercice) :

    * ``pca`` — PRODUITS CONSTATÉS D'AVANCE : un acompte encaissé/facturé mais
      NON encore ACQUIS en produit ; on neutralise le produit prématuré
      (débit 71xx « ventes » / crédit 4491 « produits constatés d'avance »).
    * ``wip`` — TRAVAUX EN COURS : des coûts engagés mais NON encore facturés ;
      on porte la production stockée à l'actif (débit 3134 « travaux en cours »
      / crédit 7132 « variation des stocks de travaux en cours »).

    Chaque ligne fige le ``montant`` régularisé, la ``date_arrete`` et est
    REPRISE (extournée) à l'ouverture suivante via ``reprendre``. Le
    chantier/contrat d'origine est référencé par string-ref. Tout est
    multi-société (``company`` posée côté serveur) ; purement additif.
    """
    class Nature(models.TextChoices):
        PCA = 'pca', "Produits constatés d'avance"
        WIP = 'wip', 'Travaux en cours (production stockée)'

    class Statut(models.TextChoices):
        CONSTATE = 'constate', 'Constaté'
        REPRIS = 'repris', 'Repris (extourné)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='travaux_en_cours',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    nature = models.CharField(
        max_length=4, choices=Nature.choices, default=Nature.WIP,
        verbose_name='Nature')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    chantier_ref = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Chantier')
    contrat_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du contrat')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant régularisé')
    date_arrete = models.DateField(verbose_name="Date d'arrêté")
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.CONSTATE,
        verbose_name='Statut')
    ecriture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'écriture de constat")
    ecriture_reprise_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'écriture de reprise")
    date_reprise = models.DateField(
        null=True, blank=True, verbose_name='Date de reprise')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='travaux_en_cours_crees',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Régularisation (PCA / WIP)'
        verbose_name_plural = 'Régularisations (PCA / WIP)'
        ordering = ['-date_arrete', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_tec_reference',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "REG"} — {self.get_nature_display()} '
                f'({self.montant})')

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant < 0:
            raise ValidationError(
                "Le montant régularisé ne peut pas être négatif.")


# ── FG148 — Campagnes de versement des commissions (payout run) ─────────────

class CommissionPayoutRun(models.Model):
    """Campagne de versement des commissions commerciales (FG148).

    Transforme le calcul de commission (lecture seule) en PAYABLE : on regroupe
    par campagne (un mois) les commissions dues par commercial dans des
    ``CommissionPayoutLine``. Le run passe par ``brouillon`` -> ``valide`` (gel
    des montants) -> ``poste`` (écriture OD au grand livre : débit 6171
    « rémunérations » / crédit 4432 « rémunérations dues au personnel »). Le
    commercial est référencé par string-ref (``commercial_id``, un user) — jamais
    d'import cross-app de modèle. ``company`` posée côté serveur.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        POSTE = 'poste', 'Posté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='commission_payout_runs',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    periode = models.CharField(
        max_length=7, blank=True, default='',
        verbose_name='Période (YYYY-MM)')
    date_run = models.DateField(verbose_name='Date du run')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Total des commissions')
    ecriture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'écriture OD")
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Validé le')
    date_poste = models.DateTimeField(
        null=True, blank=True, verbose_name='Posté le')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='commission_payout_runs_crees',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Campagne de commissions'
        verbose_name_plural = 'Campagnes de commissions'
        ordering = ['-date_run', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_commrun_reference',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "COMM"} — {self.periode} ({self.total})'

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    def recalculer_total(self):
        agg = self.lignes.aggregate(s=models.Sum('montant'))
        self.total = agg['s'] or Decimal('0')
        return self.total


class CommissionPayoutLine(models.Model):
    """Ligne de commission due à un commercial dans une campagne (FG148).

    Snapshot figé : commercial (string-ref ``commercial_id`` + nom), base de
    calcul, taux, montant dû. Le commercial est référencé par string-ref (un
    user) — jamais d'import cross-app.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='commission_payout_lines',
        verbose_name='Société',
    )
    run = models.ForeignKey(
        CommissionPayoutRun,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Campagne',
    )
    commercial_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du commercial')
    commercial_nom = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Commercial')
    base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Base de calcul')
    taux = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Taux de commission (%)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant dû')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Détail')

    class Meta:
        verbose_name = 'Ligne de commission'
        verbose_name_plural = 'Lignes de commission'
        ordering = ['run', 'commercial_nom', 'id']

    def __str__(self):
        return f'{self.commercial_nom} — {self.montant}'

    def clean(self):
        super().clean()
        if self.montant is not None and self.montant < 0:
            raise ValidationError(
                "Le montant de la commission ne peut pas être négatif.")


# ── FG149 — Budgets annuels & suivi budget-vs-réalisé ──────────────────────

class Budget(models.Model):
    """Budget annuel d'une société (FG149).

    Conteneur d'un exercice budgétaire : un ``BudgetLigne`` par compte (et/ou
    centre de coût) porte les douze montants mensuels prévus. Le réalisé se lit
    du grand livre (``LigneEcriture``) ; la variance = réalisé − budget. Tout
    est multi-société (``company`` posée côté serveur), purement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        APPROUVE = 'approuve', 'Approuvé'
        CLOTURE = 'cloture', 'Clôturé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='budgets',
        verbose_name='Société',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='budgets_crees',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'
        ordering = ['-annee', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'annee', 'libelle'],
                name='uniq_budget_an_lib',
            ),
        ]

    def __str__(self):
        return f'Budget {self.annee} — {self.libelle}'


class BudgetLigne(models.Model):
    """Ligne de budget : montant prévu par compte/centre de coût (FG149).

    Les douze montants mensuels (``m01``…``m12``) somment le budget annuel de la
    ligne. Le compte est un FK même-app (``CompteComptable``) ; le centre de
    coût est un FK optionnel (``CentreCout``, FG150). ``montant_annuel`` est
    DÉRIVÉ (somme des mois).
    """
    MOIS = ['m01', 'm02', 'm03', 'm04', 'm05', 'm06',
            'm07', 'm08', 'm09', 'm10', 'm11', 'm12']

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='budget_lignes',
        verbose_name='Société',
    )
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Budget',
    )
    compte = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        related_name='budget_lignes',
        verbose_name='Compte',
    )
    centre_cout = models.ForeignKey(
        'compta.CentreCout',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='budget_lignes',
        verbose_name='Centre de coût',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    m01 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m02 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m03 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m04 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m05 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m06 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m07 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m08 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m09 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m10 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m11 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    m12 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        verbose_name = 'Ligne de budget'
        verbose_name_plural = 'Lignes de budget'
        ordering = ['budget', 'compte__numero', 'id']

    def __str__(self):
        return f'{self.budget_id} — {self.compte_id} ({self.montant_annuel})'

    @property
    def montant_annuel(self):
        return sum(
            (getattr(self, m) or Decimal('0') for m in self.MOIS),
            Decimal('0'))


# ── FG150 — Comptabilité analytique / centres de coût ──────────────────────

class CentreCout(models.Model):
    """Axe analytique (chantier / agence / marché / commercial) — FG150.

    Référentiel des centres de coût/profit d'une société. Une ``LigneEcriture``
    peut porter un ``centre_cout`` (ajouté en option, rétro-compatible) pour
    ventiler la charge/le produit par axe analytique. ``company`` posée côté
    serveur ; purement additif.
    """
    class Axe(models.TextChoices):
        CHANTIER = 'chantier', 'Chantier'
        AGENCE = 'agence', 'Agence'
        MARCHE = 'marche', 'Marché'
        COMMERCIAL = 'commercial', 'Commercial'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='centres_cout',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    axe = models.CharField(
        max_length=12, choices=Axe.choices, default=Axe.CHANTIER,
        verbose_name='Axe analytique')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Centre de coût'
        verbose_name_plural = 'Centres de coût'
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='uniq_centrecout_code',
            ),
        ]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


# ── FG152 — Provisions pour créances douteuses ─────────────────────────────

class ProvisionCreance(models.Model):
    """Provision pour dépréciation d'une créance client douteuse (FG152).

    Calculée depuis la balance âgée : pour un tiers client, on fige la ``base``
    (créance échue restant due), un ``taux`` de provision (selon l'antériorité)
    et la ``dotation`` = base × taux %. Le poste de la dotation au grand livre
    (débit 6196 « dotations aux provisions » / crédit 3942 « provisions pour
    dépréciation des clients ») se fait à la validation ; une ``reprise`` solde
    la provision (créance recouvrée ou passée en perte). Le client est référencé
    par string-ref. ``company`` posée côté serveur ; purement additif.
    """
    class Statut(models.TextChoices):
        DOTATION = 'dotation', 'Dotation'
        REPRISE = 'reprise', 'Reprise'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='provisions_creances',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    tiers_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Type de tiers')
    tiers_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du tiers')
    tiers_nom = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Client')
    base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Créance échue (base)')
    taux = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name='Taux de provision (%)')
    dotation = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Dotation provisionnée')
    anciennete_jours = models.PositiveIntegerField(
        default=0, verbose_name='Antériorité (jours)')
    date_dotation = models.DateField(verbose_name='Date de dotation')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.DOTATION,
        verbose_name='Statut')
    ecriture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'écriture de dotation")
    ecriture_reprise_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'écriture de reprise")
    date_reprise = models.DateField(
        null=True, blank=True, verbose_name='Date de reprise')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='provisions_creances_creees',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Provision pour créance douteuse'
        verbose_name_plural = 'Provisions pour créances douteuses'
        ordering = ['-date_dotation', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__gt=''),
                name='uniq_provcreance_ref',
            ),
        ]

    def __str__(self):
        return (f'{self.reference or "PROV"} — {self.tiers_nom} '
                f'({self.dotation})')

    def clean(self):
        super().clean()
        if self.base is not None and self.base < 0:
            raise ValidationError(
                "La base de la provision ne peut pas être négative.")
        if self.taux is not None and (self.taux < 0 or self.taux > 100):
            raise ValidationError(
                "Le taux de provision doit être compris entre 0 et 100 %.")

    def recalculer(self):
        base = self.base or Decimal('0')
        taux = self.taux or Decimal('0')
        self.dotation = (base * taux / Decimal('100')).quantize(
            Decimal('0.01'))
        return self


# ── FG153 — Inter-sociétés / consolidation multi-entités ───────────────────

class EntiteConsolidation(models.Model):
    """Entité d'un périmètre de consolidation multi-entités (FG153).

    Une société du groupe (EI + SARL…) rattachée à une société « tête de
    groupe » (``company``) avec son pourcentage d'intérêt et sa méthode de
    consolidation. La consolidation agrège les CPC/bilans de chaque entité du
    périmètre (lus via le grand livre de CHAQUE société membre) après
    élimination des opérations inter-co. L'entité membre est référencée par FK
    ``authentication.Company`` (référentiel partagé, foundation app — exempt de
    la règle cross-app). ``company`` (tête de groupe) posée côté serveur.
    """
    class Methode(models.TextChoices):
        INTEGRATION_GLOBALE = 'globale', 'Intégration globale'
        MISE_EN_EQUIVALENCE = 'equivalence', 'Mise en équivalence'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='consolidation_perimetre',
        verbose_name='Société tête de groupe',
    )
    entite = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='consolidation_membre_de',
        verbose_name='Entité consolidée',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    pourcentage_interet = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.00'),
        verbose_name="Pourcentage d'intérêt (%)")
    methode = models.CharField(
        max_length=12, choices=Methode.choices,
        default=Methode.INTEGRATION_GLOBALE,
        verbose_name='Méthode de consolidation')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Entité de consolidation'
        verbose_name_plural = 'Entités de consolidation'
        ordering = ['company', 'entite']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'entite'],
                name='uniq_consol_entite',
            ),
        ]

    def __str__(self):
        return f'{self.company_id} ⊃ {self.entite_id} ({self.methode})'

    def clean(self):
        super().clean()
        if (self.pourcentage_interet is not None
                and (self.pourcentage_interet < 0
                     or self.pourcentage_interet > 100)):
            raise ValidationError(
                "Le pourcentage d'intérêt doit être entre 0 et 100 %.")


# ── FG201 — Campagnes email & SMS (envoi groupé, Brevo, GATED) ──────────────

class Campagne(models.Model):
    """Campagne d'envoi groupé email / SMS vers un segment ciblé (FG201).

    Sert à « réveiller » une base froide : on définit un segment (critères de
    ciblage libres, stockés en JSON), un canal et un message, puis on déclenche
    l'envoi groupé. L'envoi RÉEL passe par Brevo et n'a lieu que si l'intégration
    est explicitement activée (réglage ``BREVO_ENABLED`` + clé) — sinon l'envoi
    est un NO-OP (aucun appel payant, aucune dépendance dure). Les compteurs
    d'ouvertures/clics sont stockés ici pour mesurer le réveil.
    """
    class Canal(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ENVOYEE = 'envoyee', 'Envoyée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='campagnes_marketing',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom de la campagne')
    canal = models.CharField(
        max_length=8, choices=Canal.choices, default=Canal.EMAIL,
        verbose_name='Canal')
    objet = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Objet (email)')
    corps = models.TextField(blank=True, default='', verbose_name='Message')
    segment = models.JSONField(
        default=dict, blank=True,
        verbose_name='Critères de segment (JSON)')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # Compteurs de réveil — alimentés par les webhooks Brevo (gated).
    nb_destinataires = models.PositiveIntegerField(
        default=0, verbose_name='Destinataires')
    nb_envois = models.PositiveIntegerField(default=0, verbose_name='Envoyés')
    nb_ouvertures = models.PositiveIntegerField(
        default=0, verbose_name='Ouvertures')
    nb_clics = models.PositiveIntegerField(default=0, verbose_name='Clics')
    envoyee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Envoyée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Campagne email/SMS'
        verbose_name_plural = 'Campagnes email/SMS'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.nom} ({self.canal})'


# ── FG202 — Séquences de relance automatisées (drip / nurture) ─────────────

class SequenceRelance(models.Model):
    """Séquence multi-étapes déclenchée par l'entrée d'un lead en étape (FG202).

    Exemple : J0 WhatsApp → J3 email → J7 appel. La séquence est attachée à un
    déclencheur (l'entrée dans une étape du pipeline, désignée par sa CLÉ
    canonique ``STAGES.py`` stockée en texte — jamais codée en dur ici). Les
    étapes réelles (envoi WhatsApp/email) sont gated comme FG201 : tant que les
    intégrations sont OFF, le moteur ne fait qu'enregistrer/planifier, sans
    appel payant.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='sequences_relance',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom de la séquence')
    # Clé de l'étape déclencheuse (vient de STAGES.py — stockée en texte, jamais
    # hardcodée dans le code). Vide = manuelle.
    stage_declencheur = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name="Clé d'étape déclencheuse")
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Séquence de relance'
        verbose_name_plural = 'Séquences de relance'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class EtapeSequence(models.Model):
    """Une étape d'une séquence de relance (FG202).

    ``delai_jours`` = décalage depuis le déclenchement (J0, J3, J7…). ``canal``
    = WhatsApp/email/appel. L'ordre détermine l'enchaînement.
    """
    class Canal(models.TextChoices):
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Email'
        APPEL = 'appel', 'Appel'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='etapes_sequence',
        verbose_name='Société',
    )
    sequence = models.ForeignKey(
        SequenceRelance,
        on_delete=models.CASCADE,
        related_name='etapes',
        verbose_name='Séquence',
    )
    ordre = models.PositiveIntegerField(default=1, verbose_name='Ordre')
    delai_jours = models.PositiveIntegerField(
        default=0, verbose_name='Délai (jours depuis le déclenchement)')
    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.EMAIL,
        verbose_name='Canal')
    modele_message = models.TextField(
        blank=True, default='', verbose_name='Modèle de message')

    class Meta:
        verbose_name = 'Étape de séquence'
        verbose_name_plural = 'Étapes de séquence'
        ordering = ['sequence', 'ordre']
        constraints = [
            models.UniqueConstraint(
                fields=['sequence', 'ordre'],
                name='uniq_etape_sequence_ordre',
            ),
        ]

    def __str__(self):
        return f'{self.sequence_id} #{self.ordre} ({self.canal}, J+{self.delai_jours})'


# ── FG203 — Récupération des devis abandonnés ──────────────────────────────

class RelanceDevisAbandonne(models.Model):
    """Trace d'une relance sur un devis envoyé non répondu après N jours (FG203).

    On ne touche JAMAIS le modèle Devis (ventes) : on le référence par sa
    ``devis_reference`` (texte) et son ``devis_id`` (entier opaque), lus via les
    selectors de ventes. Ce log consigne la relance émise (jamais l'envoi
    lui-même), comme ``RelanceLog`` côté factures.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='relances_devis_abandonnes',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(verbose_name='Devis (id ventes)')
    devis_reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence devis')
    jours_sans_reponse = models.PositiveIntegerField(
        default=0, verbose_name='Jours sans réponse à la relance')
    canal = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Canal de relance')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_relance = models.DateTimeField(
        auto_now_add=True, verbose_name='Relancé le')

    class Meta:
        verbose_name = 'Relance devis abandonné'
        verbose_name_plural = 'Relances devis abandonnés'
        ordering = ['-date_relance']

    def __str__(self):
        return f'Relance devis {self.devis_reference or self.devis_id}'


# ── FG205 — Tracking d'ouverture des ShareLink devis/facture ───────────────

class OuverturePartage(models.Model):
    """Horodatage des ouvertures d'un lien de partage devis/facture (FG205).

    Le ShareLink lui-même vit dans ventes ; on ne l'importe pas. On indexe ici
    les ÉVÉNEMENTS d'ouverture par ``token`` (texte opaque) pour prioriser les
    relances : premier vu, dernier vu, nombre de vues. Aucune donnée client
    n'est dupliquée.
    """
    class Cible(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        FACTURE = 'facture', 'Facture'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ouvertures_partage',
        verbose_name='Société',
    )
    token = models.CharField(max_length=64, db_index=True,
                             verbose_name='Token du lien de partage')
    cible = models.CharField(
        max_length=8, choices=Cible.choices, default=Cible.DEVIS,
        verbose_name='Cible')
    cible_reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence document')
    nb_ouvertures = models.PositiveIntegerField(
        default=0, verbose_name="Nombre d'ouvertures")
    premier_vu_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Premier vu le')
    dernier_vu_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernier vu le')

    class Meta:
        verbose_name = "Ouverture de lien de partage"
        verbose_name_plural = "Ouvertures de liens de partage"
        ordering = ['-dernier_vu_le']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'token'],
                name='uniq_ouverture_partage_token',
            ),
        ]

    def __str__(self):
        return f'{self.cible} {self.token[:8]}… ({self.nb_ouvertures} vues)'


# ── FG206 — Constructeur de formulaires / landing pages multiples ──────────

class FormulaireIntake(models.Model):
    """Définition d'un formulaire d'intake / landing page (FG206).

    Plusieurs formulaires d'entrée (pompage agricole, régularisation 82-21…),
    chacun pré-taguant le lead créé avec un ``tag_prefill`` et un
    ``type_installation`` par défaut. Les champs sont décrits en JSON (libre).
    Le slug tokenisé rend la page adressable publiquement (création de lead via
    crm.services, jamais d'import de modèles crm).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='formulaires_intake',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du formulaire')
    slug = models.SlugField(max_length=80, verbose_name='Slug public')
    tag_prefill = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Tag pré-rempli sur le lead')
    type_installation = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name="Type d'installation par défaut")
    champs = models.JSONField(
        default=list, blank=True, verbose_name='Définition des champs (JSON)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Formulaire d'intake"
        verbose_name_plural = "Formulaires d'intake"
        ordering = ['nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='uniq_formulaire_intake_slug',
            ),
        ]

    def __str__(self):
        return self.nom


# ── FG207 — Capture de leads via WhatsApp (inbound, GATED) ─────────────────

class MessageWhatsAppEntrant(models.Model):
    """Message WhatsApp entrant capturé pour créer un lead pré-qualifié (FG207).

    L'intégration WhatsApp Business Cloud (Meta) est GATED : sans le jeton
    fourni par le founder, le webhook entrant est inactif (NO-OP) et aucun
    message n'est traité. Quand activé, chaque message crée/rattache un lead
    DRAFT via ``crm.services`` (jamais d'import de modèles crm), en laissant le
    funnel à NEW. Ce modèle journalise l'entrée pour audit/idempotence.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='messages_whatsapp_entrants',
        verbose_name='Société',
    )
    wa_message_id = models.CharField(
        max_length=128, verbose_name='ID message WhatsApp')
    expediteur = models.CharField(
        max_length=32, verbose_name='Numéro expéditeur')
    nom_profil = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Nom du profil')
    texte = models.TextField(blank=True, default='', verbose_name='Texte')
    # Id opaque du lead créé/rattaché côté crm (jamais un FK direct cross-app).
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Lead créé (id crm)')
    traite = models.BooleanField(default=False, verbose_name='Traité')
    date_reception = models.DateTimeField(
        auto_now_add=True, verbose_name='Reçu le')

    class Meta:
        verbose_name = 'Message WhatsApp entrant'
        verbose_name_plural = 'Messages WhatsApp entrants'
        ordering = ['-date_reception']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'wa_message_id'],
                name='uniq_wa_message_entrant',
            ),
        ]

    def __str__(self):
        return f'WA {self.expediteur} ({self.wa_message_id[:10]}…)'


# ── FG208 — Journal d'appels & click-to-call ───────────────────────────────

class AppelTelephonique(models.Model):
    """Consigne d'un appel téléphonique et de son issue (FG208).

    Mesure l'effort téléphonique. Le bouton ``tel:`` (click-to-call) est un
    rendu front pur ; côté backend on enregistre l'appel, sa direction, sa durée
    et son issue. Le lead/contact est référencé par id opaque (jamais un FK
    cross-app vers crm).
    """
    class Direction(models.TextChoices):
        SORTANT = 'sortant', 'Sortant'
        ENTRANT = 'entrant', 'Entrant'

    class Issue(models.TextChoices):
        REPONDU = 'repondu', 'Répondu'
        SANS_REPONSE = 'sans_reponse', 'Sans réponse'
        RAPPEL = 'rappel', 'À rappeler'
        FAUX_NUMERO = 'faux_numero', 'Faux numéro'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='appels_telephoniques',
        verbose_name='Société',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appels_passes',
        verbose_name='Auteur',
    )
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Lead (id crm)')
    numero = models.CharField(max_length=32, verbose_name='Numéro')
    direction = models.CharField(
        max_length=8, choices=Direction.choices, default=Direction.SORTANT,
        verbose_name='Direction')
    issue = models.CharField(
        max_length=14, choices=Issue.choices, default=Issue.REPONDU,
        verbose_name='Issue')
    duree_secondes = models.PositiveIntegerField(
        default=0, verbose_name='Durée (s)')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    a_rappeler_le = models.DateField(
        null=True, blank=True, verbose_name='À rappeler le')
    date_appel = models.DateTimeField(
        auto_now_add=True, verbose_name='Appelé le')

    class Meta:
        verbose_name = "Journal d'appel"
        verbose_name_plural = "Journal d'appels"
        ordering = ['-date_appel']

    def __str__(self):
        return f'{self.direction} {self.numero} ({self.issue})'


# ── FG209 — Promotions & campagnes de remise (codes datés) ─────────────────

class CodePromotion(models.Model):
    """Code de remise daté applicable à un devis (FG209), traçable au ROI.

    Exemple « -5 % Aïd » valable du… au… Le taux est plafonné 0–100 %. Le
    compteur ``nb_utilisations`` et ``ca_genere`` permettent de mesurer le ROI.
    L'application au devis est faite côté ventes ; ici on définit/valide le code.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='codes_promotion',
        verbose_name='Société',
    )
    code = models.CharField(max_length=40, verbose_name='Code')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    taux_remise = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Taux de remise (%)')
    date_debut = models.DateField(verbose_name='Valable du')
    date_fin = models.DateField(verbose_name='Valable au')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    nb_utilisations = models.PositiveIntegerField(
        default=0, verbose_name="Nombre d'utilisations")
    ca_genere = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='CA généré (TTC)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Code de promotion'
        verbose_name_plural = 'Codes de promotion'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='uniq_code_promotion',
            ),
        ]

    def __str__(self):
        return f'{self.code} (-{self.taux_remise} %)'

    def clean(self):
        super().clean()
        if self.taux_remise is not None and (
                self.taux_remise < 0 or self.taux_remise > 100):
            raise ValidationError(
                'Le taux de remise doit être entre 0 et 100 %.')
        if (self.date_debut and self.date_fin
                and self.date_fin < self.date_debut):
            raise ValidationError(
                'La date de fin doit être postérieure à la date de début.')


# ── FG210 — Bibliothèque de modèles de devis ───────────────────────────────

class ModeleDevis(models.Model):
    """Modèle de devis réutilisable par marché (FG210).

    Exemples : « Résidentiel 5 kWc », « Pompage 3 CV ». Les lignes-types sont
    décrites en JSON (désignation/quantité/prix indicatif) : une amorce que le
    commercial charge dans le générateur de devis. Ne crée aucun document ; ne
    touche pas le modèle Devis.
    """
    class Marche(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel/Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='modeles_devis',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du modèle')
    marche = models.CharField(
        max_length=12, choices=Marche.choices, default=Marche.RESIDENTIEL,
        verbose_name='Marché')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    lignes_type = models.JSONField(
        default=list, blank=True, verbose_name='Lignes-types (JSON)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Modèle de devis'
        verbose_name_plural = 'Modèles de devis'
        ordering = ['marche', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.marche})'


# ── FG211 — Configurateur d'options guidé (guided selling) ─────────────────

class SessionGuidedSelling(models.Model):
    """Session d'un assistant pas-à-pas de configuration de devis (FG211).

    Persiste les réponses d'un commercial junior au fil des étapes ; un service
    valide la cohérence (ex. kWc vs onduleur) et propose une composition. Ne
    crée pas le devis lui-même.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='sessions_guided_selling',
        verbose_name='Société',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions_guided_selling',
        verbose_name='Auteur',
    )
    marche = models.CharField(
        max_length=12, default='residentiel', verbose_name='Marché')
    reponses = models.JSONField(
        default=dict, blank=True, verbose_name='Réponses (JSON)')
    composition = models.JSONField(
        default=dict, blank=True,
        verbose_name='Composition proposée (JSON)')
    complet = models.BooleanField(default=False, verbose_name='Complète')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Session de configuration guidée'
        verbose_name_plural = 'Sessions de configuration guidée'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Guided selling {self.id} ({self.marche})'


# ── FG213 — Routage d'approbation des configurations non-standard ──────────

class DemandeApprobationConfig(models.Model):
    """Demande d'approbation d'une composition de devis non-standard (FG213).

    Quand la composition sort des règles (ex. kWc/onduleur incohérents), elle
    part en validation. Le devis est référencé par id opaque (ventes). Workflow :
    en_attente → approuvée/refusée, traçable (qui, quand, motif).
    """
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVEE = 'approuvee', 'Approuvée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='approbations_config',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Devis (id ventes)')
    devis_reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence devis')
    motif = models.TextField(
        verbose_name='Motif de la non-conformité')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut')
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approbations_demandees',
        verbose_name='Demandeur',
    )
    decideur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approbations_decidees',
        verbose_name='Décideur',
    )
    commentaire_decision = models.TextField(
        blank=True, default='', verbose_name='Commentaire de décision')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidée le')

    class Meta:
        verbose_name = "Demande d'approbation de configuration"
        verbose_name_plural = "Demandes d'approbation de configuration"
        ordering = ['-date_creation']

    def __str__(self):
        return f'Approbation {self.devis_reference or self.devis_id} ({self.statut})'


# ── FG214 — E-catalogue à prix publics (tokenisé) ──────────────────────────

class ECatalogue(models.Model):
    """Page catalogue publique tokenisée, prix public TTC SEULEMENT (FG214).

    Jeton long/imprévisible/expirant. Le rendu n'expose JAMAIS le prix d'achat
    (``prix_achat``) ni aucune marge — uniquement le prix public TTC, lu via les
    selectors de stock. La sélection de produits est stockée en liste d'ids
    opaques (jamais un FK cross-app vers stock).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ecatalogues',
        verbose_name='Société',
    )
    titre = models.CharField(
        max_length=200, default='Catalogue', verbose_name='Titre')
    token = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name='Token public')
    produit_ids = models.JSONField(
        default=list, blank=True,
        verbose_name='Produits exposés (ids stock)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    expire_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Expire le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'E-catalogue public'
        verbose_name_plural = 'E-catalogues publics'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.titre} ({self.token[:8]}…)'


# ── FG215 — Bibliothèque de documents de proposition ───────────────────────

class DocumentProposition(models.Model):
    """Annexe réutilisable attachable à un PDF de proposition (FG215).

    Lettre de couverture, page de références, garanties… Le document est un
    bloc de contenu (titre + corps + pièce jointe optionnelle) que le
    commercial sélectionne pour enrichir un devis. Purement additif : ne touche
    NI le générateur de devis NI le moteur PDF — c'est une bibliothèque
    d'annexes côté compta/marketing.
    """
    class TypeDocument(models.TextChoices):
        LETTRE = 'lettre', 'Lettre de couverture'
        REFERENCES = 'references', 'Références / réalisations'
        GARANTIES = 'garanties', 'Garanties'
        AUTRE = 'autre', 'Autre annexe'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='documents_proposition',
        verbose_name='Société',
    )
    titre = models.CharField(max_length=200, verbose_name='Titre')
    type_document = models.CharField(
        max_length=12, choices=TypeDocument.choices,
        default=TypeDocument.AUTRE, verbose_name='Type de document')
    contenu = models.TextField(
        blank=True, default='', verbose_name='Contenu (texte)')
    fichier = models.FileField(
        upload_to='compta/propositions/', null=True, blank=True,
        verbose_name='Pièce jointe')
    ordre = models.PositiveIntegerField(
        default=0, verbose_name="Ordre d'affichage")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Document de proposition'
        verbose_name_plural = 'Documents de proposition'
        ordering = ['type_document', 'ordre', 'titre']

    def __str__(self):
        return f'{self.titre} ({self.type_document})'


# ── FG216 — Simulateur public « configurez votre kit » → lead ──────────────

class SimulationPublique(models.Model):
    """Simulation kWc/économies lancée publiquement → lead pré-rempli (FG216).

    Le visiteur dimensionne un kit (puissance souhaitée / facture mensuelle) et
    laisse ses coordonnées ; on stocke la simulation et, si demandé, on crée un
    lead pré-rempli via le SERVICE crm (jamais ses modèles). La création de
    lead est gardée par un flag (NO-OP par défaut) — voir
    ``services.creer_lead_depuis_simulation``.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='simulations_publiques',
        verbose_name='Société',
    )
    nom_prospect = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Nom du prospect')
    telephone = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Téléphone')
    email = models.EmailField(
        blank=True, default='', verbose_name='Email')
    puissance_kwc = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Puissance estimée (kWc)')
    facture_mensuelle = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Facture mensuelle (MAD)')
    economie_annuelle = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Économie annuelle estimée (MAD)')
    parametres = models.JSONField(
        default=dict, blank=True, verbose_name='Paramètres de simulation')
    lead_cree = models.BooleanField(
        default=False, verbose_name='Lead créé')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead créé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Simulation publique'
        verbose_name_plural = 'Simulations publiques'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Simulation {self.puissance_kwc} kWc ({self.nom_prospect})'


# ── FG217 — Simulation de financement dans le devis (crédit/leasing) ───────

class SimulationFinancement(models.Model):
    """Bloc mensualités crédit/leasing rattaché à un devis (FG217).

    Calcule la mensualité d'un crédit amortissable (montant, durée, taux
    annuel) pour l'afficher au client. N'altère PAS le devis ni son total : le
    devis est référencé par id (jamais un FK cross-app vers ventes). Le calcul
    est fait côté service (``services.calcul_mensualite``) au save.
    """
    class Type(models.TextChoices):
        CREDIT = 'credit', 'Crédit amortissable'
        LEASING = 'leasing', 'Leasing / LOA'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='simulations_financement',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du devis')
    devis_reference = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Référence devis')
    type_financement = models.CharField(
        max_length=10, choices=Type.choices, default=Type.CREDIT,
        verbose_name='Type de financement')
    montant_finance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant financé (MAD)')
    duree_mois = models.PositiveIntegerField(
        default=12, verbose_name='Durée (mois)')
    taux_annuel = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Taux annuel (%)')
    mensualite = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Mensualité estimée (MAD)')
    cout_total_credit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Coût total du crédit (MAD)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Simulation de financement'
        verbose_name_plural = 'Simulations de financement'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.type_financement} {self.montant_finance} MAD / {self.duree_mois} mois'

    def clean(self):
        super().clean()
        if self.duree_mois is not None and self.duree_mois <= 0:
            raise ValidationError('La durée doit être strictement positive.')
        if self.taux_annuel is not None and self.taux_annuel < 0:
            raise ValidationError('Le taux annuel ne peut pas être négatif.')


# ── FG218 — Offres de banques/partenaires de financement ───────────────────

class OffreFinancement(models.Model):
    """Catalogue d'offres de financement sélectionnables sur un devis (FG218).

    Une offre = un partenaire/banque + ses conditions (taux, durée min/max,
    montant min/max, apport). Sert d'amorce à ``SimulationFinancement`` : le
    commercial choisit l'offre, puis simule.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='offres_financement',
        verbose_name='Société',
    )
    partenaire = models.CharField(
        max_length=200, verbose_name='Banque / partenaire')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Libellé de l'offre")
    taux_annuel = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Taux annuel (%)')
    duree_min_mois = models.PositiveIntegerField(
        default=12, verbose_name='Durée minimale (mois)')
    duree_max_mois = models.PositiveIntegerField(
        default=84, verbose_name='Durée maximale (mois)')
    montant_min = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant minimal (MAD)')
    montant_max = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant maximal (MAD)')
    apport_min_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Apport minimal (%)')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Offre de financement'
        verbose_name_plural = 'Offres de financement'
        ordering = ['partenaire', 'taux_annuel']

    def __str__(self):
        return f'{self.partenaire} — {self.taux_annuel} %'


# ── FG219 — Ligne d'incitation / subvention (Tatwir/MASEN) ─────────────────

class LigneIncitation(models.Model):
    """Incitation/subvention déductible affichée sur un devis (FG219).

    Montant déductible (Tatwir, MASEN…) qui réduit le coût client : on affiche
    coût brut → aide → coût net. N'altère PAS le total du devis (statut
    PRÉSERVÉ, CLAUDE.md règle #4) : c'est un encart informatif. Devis référencé
    par id.
    """
    class Programme(models.TextChoices):
        TATWIR = 'tatwir', 'Tatwir'
        MASEN = 'masen', 'MASEN'
        IRESEN = 'iresen', 'IRESEN'
        AUTRE = 'autre', 'Autre dispositif'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_incitation',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du devis')
    devis_reference = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Référence devis')
    programme = models.CharField(
        max_length=10, choices=Programme.choices, default=Programme.AUTRE,
        verbose_name='Programme')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    montant_aide = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Montant de l'aide (MAD)")
    cout_brut = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Coût brut (MAD)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Ligne d'incitation"
        verbose_name_plural = "Lignes d'incitation"
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.programme} -{self.montant_aide} MAD'

    @property
    def cout_net(self):
        """Coût net après déduction de l'aide (jamais négatif)."""
        net = (self.cout_brut or Decimal('0.00')) - (
            self.montant_aide or Decimal('0.00'))
        return net if net > 0 else Decimal('0.00')

    def clean(self):
        super().clean()
        if self.montant_aide is not None and self.montant_aide < 0:
            raise ValidationError("Le montant de l'aide ne peut pas être négatif.")


# ── FG220 — Paiement échelonné (type Tayssir) sur facture ──────────────────

class EcheancierPaiement(models.Model):
    """Échéancier de tranches sur une facture (FG220), type Tayssir.

    Plan de paiement échelonné rattaché à une facture (référencée par id, jamais
    un FK cross-app vers ventes) : N tranches avec dates/montants et suivi des
    versements. ``montant_regle`` / ``reste_a_payer`` agrègent les tranches.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='echeanciers_paiement',
        verbose_name='Société',
    )
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id de la facture')
    facture_reference = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Référence facture')
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant total (MAD)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Échéancier de paiement'
        verbose_name_plural = 'Échéanciers de paiement'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Échéancier {self.facture_reference} ({self.montant_total} MAD)'


class TranchePaiement(models.Model):
    """Une tranche d'un échéancier de paiement (FG220)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='tranches_paiement',
        verbose_name='Société',
    )
    echeancier = models.ForeignKey(
        EcheancierPaiement,
        on_delete=models.CASCADE,
        related_name='tranches',
        verbose_name='Échéancier',
    )
    numero = models.PositiveIntegerField(default=1, verbose_name='N° tranche')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant (MAD)')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    montant_regle = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant réglé (MAD)')
    date_reglement = models.DateField(
        null=True, blank=True, verbose_name='Date de règlement')
    paye = models.BooleanField(default=False, verbose_name='Payée')

    class Meta:
        verbose_name = 'Tranche de paiement'
        verbose_name_plural = 'Tranches de paiement'
        ordering = ['echeancier', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['echeancier', 'numero'],
                name='uniq_tranche_numero',
            ),
        ]

    def __str__(self):
        return f'Tranche {self.numero} — {self.montant} MAD'


# ── FG221 — Comparateur cash vs financement (calcul, sans modèle dédié) ─────
# Voir ComparateurCashFinancementViewSet : calcul pur lu/affiché, aucun stockage.


# ── FG222 — Gestion des appels d'offres (public/privé) ─────────────────────

class AppelOffre(models.Model):
    """Objet appel d'offres (AO) public/privé (FG222).

    Acheteur, deadline, lot, caution… L'industriel/agricole passe par des
    marchés. Lié au lead par id (jamais un FK cross-app vers crm). Sert de
    racine au BOQ (FG223), aux cautions (FG224), au dossier (FG225), à
    l'échéancier (FG226) et à l'analyse résultat (FG227).
    """
    class TypeMarche(models.TextChoices):
        PUBLIC = 'public', 'Public'
        PRIVE = 'prive', 'Privé'

    class Statut(models.TextChoices):
        IDENTIFIE = 'identifie', 'Identifié'
        EN_PREPARATION = 'en_preparation', 'En préparation'
        DEPOSE = 'depose', 'Déposé'
        GAGNE = 'gagne', 'Gagné'
        PERDU = 'perdu', 'Perdu'
        ABANDONNE = 'abandonne', 'Abandonné'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='appels_offres',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=120, verbose_name="Référence de l'AO")
    objet = models.CharField(max_length=255, verbose_name='Objet')
    acheteur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Acheteur')
    type_marche = models.CharField(
        max_length=8, choices=TypeMarche.choices, default=TypeMarche.PUBLIC,
        verbose_name='Type de marché')
    lot = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Lot')
    date_limite = models.DateField(
        null=True, blank=True, verbose_name='Date limite de remise des plis')
    montant_estime = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant estimé (MAD)')
    caution_provisoire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Caution provisoire (MAD)')
    statut = models.CharField(
        max_length=16, choices=Statut.choices, default=Statut.IDENTIFIE,
        verbose_name='Statut')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead lié')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Appel d'offres"
        verbose_name_plural = "Appels d'offres"
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='uniq_appel_offre_reference',
            ),
        ]

    def __str__(self):
        return f'{self.reference} — {self.objet}'


# ── FG223 — Bordereau des prix (BOQ) d'appel d'offres ──────────────────────

class BordereauPrix(models.Model):
    """Bordereau des prix (BOQ) d'un AO (FG223), séparé du devis client.

    Chiffrage interne ligne à ligne de l'AO. Distinct du devis : sert au
    montage de l'offre de prix. ``total_ht`` agrège les lignes.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='bordereaux_prix',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='bordereaux',
        verbose_name="Appel d'offres",
    )
    intitule = models.CharField(
        max_length=200, default='Bordereau des prix', verbose_name='Intitulé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bordereau des prix (BOQ)'
        verbose_name_plural = 'Bordereaux des prix (BOQ)'
        ordering = ['-date_creation']

    def __str__(self):
        return f'BOQ {self.intitule} ({self.appel_offre.reference})'

    @property
    def total_ht(self):
        total = Decimal('0.00')
        for ligne in self.lignes.all():
            total += ligne.montant_ht
        return total


class LigneBordereau(models.Model):
    """Une ligne chiffrée d'un BOQ (FG223)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_bordereau',
        verbose_name='Société',
    )
    bordereau = models.ForeignKey(
        BordereauPrix,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Bordereau',
    )
    numero = models.PositiveIntegerField(default=1, verbose_name='N° ligne')
    designation = models.CharField(max_length=255, verbose_name='Désignation')
    unite = models.CharField(
        max_length=20, blank=True, default='U', verbose_name='Unité')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Quantité')
    prix_unitaire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Prix unitaire HT (MAD)')

    class Meta:
        verbose_name = 'Ligne de bordereau'
        verbose_name_plural = 'Lignes de bordereau'
        ordering = ['bordereau', 'numero']

    def __str__(self):
        return f'{self.numero}. {self.designation}'

    @property
    def montant_ht(self):
        return (self.quantite or Decimal('0')) * (
            self.prix_unitaire or Decimal('0'))


# ── FG224 — Suivi des cautions & garanties de soumission ───────────────────

class CautionSoumission(models.Model):
    """Caution/garantie de soumission d'un AO (FG224).

    Provisoire ou définitive : montant, banque, échéance, restitution. Distincte
    de ``CautionBancaire`` (cautions sur marché en cours) — celle-ci suit le
    cycle soumission AO.
    """
    class TypeCaution(models.TextChoices):
        PROVISOIRE = 'provisoire', 'Provisoire'
        DEFINITIVE = 'definitive', 'Définitive'
        RETENUE_GARANTIE = 'retenue_garantie', 'Retenue de garantie'

    class Statut(models.TextChoices):
        CONSTITUEE = 'constituee', 'Constituée'
        RESTITUEE = 'restituee', 'Restituée'
        APPELEE = 'appelee', 'Appelée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='cautions_soumission',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='cautions',
        verbose_name="Appel d'offres",
    )
    type_caution = models.CharField(
        max_length=16, choices=TypeCaution.choices,
        default=TypeCaution.PROVISOIRE, verbose_name='Type de caution')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant (MAD)')
    banque = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Banque')
    date_emission = models.DateField(
        null=True, blank=True, verbose_name="Date d'émission")
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name="Date d'échéance")
    date_restitution = models.DateField(
        null=True, blank=True, verbose_name='Date de restitution')
    statut = models.CharField(
        max_length=16, choices=Statut.choices, default=Statut.CONSTITUEE,
        verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Caution de soumission'
        verbose_name_plural = 'Cautions de soumission'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.type_caution} {self.montant} MAD ({self.banque})'


# ── FG225 — Dossier de soumission (pièces administratives) ─────────────────

class DossierSoumission(models.Model):
    """Dossier de soumission d'un AO (FG225) : checklist + dépôt des pièces.

    Attestations fiscale/CNSS, RC, déclaration sur l'honneur… Le dossier
    regroupe les pièces (``PieceSoumission``) ; ``complet`` est dérivé du
    pointage des pièces obligatoires.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='dossiers_soumission',
        verbose_name='Société',
    )
    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='dossier',
        verbose_name="Appel d'offres",
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Dossier de soumission'
        verbose_name_plural = 'Dossiers de soumission'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Dossier {self.appel_offre.reference}'

    @property
    def complet(self):
        """Vrai si toutes les pièces obligatoires sont fournies."""
        obligatoires = self.pieces.filter(obligatoire=True)
        if not obligatoires.exists():
            return False
        return not obligatoires.filter(fournie=False).exists()


class PieceSoumission(models.Model):
    """Une pièce administrative d'un dossier de soumission (FG225)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='pieces_soumission',
        verbose_name='Société',
    )
    dossier = models.ForeignKey(
        DossierSoumission,
        on_delete=models.CASCADE,
        related_name='pieces',
        verbose_name='Dossier',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    obligatoire = models.BooleanField(
        default=True, verbose_name='Obligatoire')
    fournie = models.BooleanField(default=False, verbose_name='Fournie')
    fichier = models.FileField(
        upload_to='compta/soumissions/', null=True, blank=True,
        verbose_name='Document')
    date_depot = models.DateField(
        null=True, blank=True, verbose_name='Date de dépôt')

    class Meta:
        verbose_name = 'Pièce de soumission'
        verbose_name_plural = 'Pièces de soumission'
        ordering = ['dossier', 'libelle']

    def __str__(self):
        etat = 'OK' if self.fournie else 'manquante'
        return f'{self.libelle} ({etat})'


# ── FG226 — Échéancier & alertes de deadline d'AO ──────────────────────────

class EcheanceAO(models.Model):
    """Date clé d'un AO avec rappel (FG226).

    Remise des plis, ouverture, validité de l'offre… ``rappel_jours`` avant
    l'échéance déclenche une alerte (calcul des échéances dues dans le service ;
    aucun envoi réseau ici).
    """
    class TypeEcheance(models.TextChoices):
        REMISE_PLIS = 'remise_plis', 'Remise des plis'
        OUVERTURE = 'ouverture', 'Ouverture des plis'
        VALIDITE = 'validite', 'Fin de validité de l\'offre'
        AUTRE = 'autre', 'Autre date clé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='echeances_ao',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='echeances',
        verbose_name="Appel d'offres",
    )
    type_echeance = models.CharField(
        max_length=12, choices=TypeEcheance.choices,
        default=TypeEcheance.AUTRE, verbose_name="Type d'échéance")
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    rappel_jours = models.PositiveIntegerField(
        default=3, verbose_name='Rappel (jours avant)')
    traitee = models.BooleanField(default=False, verbose_name='Traitée')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Échéance d'AO"
        verbose_name_plural = "Échéances d'AO"
        ordering = ['date_echeance']

    def __str__(self):
        return f'{self.type_echeance} {self.date_echeance}'


# ── FG227 — Analyse gagné/perdu des appels d'offres ────────────────────────

class ResultatAO(models.Model):
    """Résultat d'un AO pour l'analyse gagné/perdu (FG227).

    Attributaire, prix gagnant, écart vs notre offre. Agrégé pour le taux de
    réussite (calcul dans le service/viewset). Un seul résultat par AO.
    """
    class Issue(models.TextChoices):
        GAGNE = 'gagne', 'Gagné'
        PERDU = 'perdu', 'Perdu'
        INFRUCTUEUX = 'infructueux', 'Infructueux'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='resultats_ao',
        verbose_name='Société',
    )
    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='resultat',
        verbose_name="Appel d'offres",
    )
    issue = models.CharField(
        max_length=12, choices=Issue.choices, default=Issue.PERDU,
        verbose_name='Issue')
    attributaire = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Attributaire')
    notre_prix = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Notre prix (MAD)')
    prix_gagnant = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Prix gagnant (MAD)')
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif / commentaire')
    date_resultat = models.DateField(
        null=True, blank=True, verbose_name='Date du résultat')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Résultat d'AO"
        verbose_name_plural = "Résultats d'AO"
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.appel_offre.reference} — {self.issue}'

    @property
    def ecart_prix(self):
        """Écart entre notre prix et le prix gagnant (MAD)."""
        if not self.prix_gagnant:
            return None
        return (self.notre_prix or Decimal('0.00')) - self.prix_gagnant


# ── FG228 — Portail self-service client ────────────────────────────────────

class ComptePortailClient(models.Model):
    """Compte d'accès au portail self-service client (FG228).

    Le client consulte ses devis, factures, chantiers et tickets. Le compte se
    lie à un client par id (résolu via le service crm — jamais ses modèles) et
    réutilise l'email du client (pas de 2ᵉ copie d'identité, DC32). L'accès est
    tokenisé ; aucune donnée métier n'est dupliquée ici.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='comptes_portail',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    email = models.EmailField(verbose_name='Email du client')
    token_acces = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name="Token d'accès")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    derniere_connexion = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière connexion')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Compte portail client'
        verbose_name_plural = 'Comptes portail client'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'client_id'],
                name='uniq_compte_portail_client',
            ),
        ]

    def __str__(self):
        return f'Portail {self.email}'


# ── FG229 — Acceptation / e-signature de devis dans le portail ─────────────

class AcceptationDevisPortail(models.Model):
    """Acceptation en ligne d'un devis depuis le portail client (FG229).

    Le client choisit une option (variante chiffrée) puis signe en saisissant
    son nom ; on horodate et on capture l'IP comme preuve légère (loi 53-05 :
    une signature nominative suffit pour un devis solaire résidentiel/PME). Le
    devis est désigné par son id (jamais par import du modèle ``ventes`` —
    cross-app via service/string-id) ; cet enregistrement matérialise
    l'acceptation côté OS sans dupliquer le devis. Une e-signature certifiée
    (Yousign, gated G7) reste optionnelle et hors périmètre ici.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='acceptations_devis_portail',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(verbose_name='Id du devis')
    option_choisie = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Option choisie')
    nom_signataire = models.CharField(
        max_length=200, verbose_name='Nom du signataire')
    signature_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='IP de signature')
    accepte = models.BooleanField(default=False, verbose_name='Accepté')
    signe_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Signé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Acceptation de devis (portail)'
        verbose_name_plural = 'Acceptations de devis (portail)'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Acceptation devis #{self.devis_id} — {self.nom_signataire}'


# ── FG230 — Paiement en ligne des factures (portail) ───────────────────────

class PaiementFacturePortail(models.Model):
    """Intention de paiement en ligne d'une facture depuis le portail (FG230).

    Le client clique « payer » (CMI carte ou virement) ; on enregistre une
    intention de paiement scopée société, puis le rapprochement la passe de
    ``initie`` à ``paye`` (manuel pour le virement, automatique via webhook CMI
    quand l'intégration est branchée). Tant que la passerelle CMI est OFF
    (``CMI_ENABLED``, défaut), aucun appel réseau payant n'est émis : l'intention
    reste ``initie`` avec une référence locale. La facture est désignée par son
    id (cross-app — jamais d'import du modèle ``ventes``).
    """
    class Methode(models.TextChoices):
        CARTE = 'carte', 'Carte (CMI)'
        VIREMENT = 'virement', 'Virement'

    class Statut(models.TextChoices):
        INITIE = 'initie', 'Initié'
        PAYE = 'paye', 'Payé'
        ECHOUE = 'echoue', 'Échoué'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paiements_facture_portail',
        verbose_name='Société',
    )
    facture_id = models.PositiveIntegerField(verbose_name='Id de la facture')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant (MAD)')
    methode = models.CharField(
        max_length=8, choices=Methode.choices, default=Methode.CARTE,
        verbose_name='Méthode')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.INITIE,
        verbose_name='Statut')
    reference = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Référence de transaction')
    paye_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Payé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Paiement de facture (portail)'
        verbose_name_plural = 'Paiements de facture (portail)'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Paiement facture #{self.facture_id} ({self.statut})'


# ── FG231 — Dépôt de documents / factures ONEE par le client ───────────────

class DocumentClientPortail(models.Model):
    """Document téléversé par le client depuis le portail (FG231).

    Le client dépose ses factures ONEE (ou autre justificatif) pour affiner
    l'étude solaire — l'app y lit la consommation. Scopé société ; lié au client
    par id (cross-app, jamais d'import crm) et, optionnellement, au lead. Le
    fichier va dans le stockage objet (MinIO/S3) ; aucun prix/marge ici.
    """
    class TypeDoc(models.TextChoices):
        FACTURE_ONEE = 'facture_onee', 'Facture ONEE'
        PLAN = 'plan', 'Plan / schéma'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='documents_client_portail',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead')
    type_document = models.CharField(
        max_length=14, choices=TypeDoc.choices, default=TypeDoc.FACTURE_ONEE,
        verbose_name='Type de document')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    fichier = models.FileField(
        upload_to='compta/portail_docs/', null=True, blank=True,
        verbose_name='Fichier')
    traite = models.BooleanField(
        default=False, verbose_name='Traité (intégré à l\'étude)')
    date_depot = models.DateTimeField(
        auto_now_add=True, verbose_name='Déposé le')

    class Meta:
        verbose_name = 'Document client (portail)'
        verbose_name_plural = 'Documents client (portail)'
        ordering = ['-date_depot']

    def __str__(self):
        return f'{self.get_type_document_display()} — client #{self.client_id}'


# ── FG232 — Suivi d'avancement du chantier côté client (timeline) ──────────

class JalonChantierPortail(models.Model):
    """Jalon d'avancement d'un chantier exposé au client dans le portail (FG232).

    Timeline lecture-seule côté client : étude → commande → livraison →
    installation → mise en service → réception. Chaque jalon porte un libellé,
    un ordre, un état atteint/non-atteint et une date. Le chantier est désigné
    par son id (cross-app — jamais d'import ``installations``). Scopé société ;
    aucune donnée financière n'est exposée ici.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='jalons_chantier_portail',
        verbose_name='Société',
    )
    chantier_id = models.PositiveIntegerField(verbose_name='Id du chantier')
    libelle = models.CharField(max_length=120, verbose_name='Jalon')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    atteint = models.BooleanField(default=False, verbose_name='Atteint')
    date_jalon = models.DateField(
        null=True, blank=True, verbose_name='Date du jalon')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Jalon de chantier (portail)'
        verbose_name_plural = 'Jalons de chantier (portail)'
        ordering = ['chantier_id', 'ordre', 'id']

    def __str__(self):
        return f'Chantier #{self.chantier_id} — {self.libelle}'


# ── FG233 — Ouverture de ticket SAV depuis le portail ──────────────────────

class DemandeTicketPortail(models.Model):
    """Demande de ticket SAV/garantie ouverte par le client via le portail
    (FG233).

    Le client décrit un problème ; on enregistre la demande scopée société,
    puis le SAV la prend en charge en créant le vrai ticket (app ``sav``, via
    son service — jamais d'import de ses modèles ici). ``ticket_id`` référence
    le ticket SAV créé (cross-app par id). Le client suit l'état de sa demande
    en lecture depuis le portail.
    """
    class Statut(models.TextChoices):
        SOUMISE = 'soumise', 'Soumise'
        PRISE_EN_CHARGE = 'prise_en_charge', 'Prise en charge'
        RESOLUE = 'resolue', 'Résolue'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='demandes_ticket_portail',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du chantier')
    sujet = models.CharField(max_length=200, verbose_name='Sujet')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=16, choices=Statut.choices, default=Statut.SOUMISE,
        verbose_name='Statut')
    ticket_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du ticket SAV créé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Demande de ticket SAV (portail)'
        verbose_name_plural = 'Demandes de ticket SAV (portail)'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Demande SAV #{self.client_id} — {self.sujet}'


# ── FG234 — Portail apporteurs / sous-revendeurs ───────────────────────────

class Partenaire(models.Model):
    """Partenaire commercial : apporteur d'affaires ou sous-revendeur (FG234).

    Fiche minimale ici (compte + accès tokenisé + taux de commission). FG237
    enrichit la fiche (statut d'agrément, zone, onboarding). Un partenaire
    soumet des leads via le portail (``SoumissionLeadPartenaire``) et suit leur
    statut. Scopé société ; le token d'accès est posé côté serveur.
    """
    class Type(models.TextChoices):
        APPORTEUR = 'apporteur', "Apporteur d'affaires"
        SOUS_REVENDEUR = 'sous_revendeur', 'Sous-revendeur'
        INSTALLATEUR = 'installateur', 'Installateur'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='partenaires',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom / raison sociale')
    type_partenaire = models.CharField(
        max_length=16, choices=Type.choices, default=Type.APPORTEUR,
        verbose_name='Type de partenaire')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    taux_commission = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de commission (%)')
    token_acces = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name="Token d'accès")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Partenaire commercial'
        verbose_name_plural = 'Partenaires commerciaux'
        ordering = ['nom']

    def __str__(self):
        return f'{self.nom} ({self.get_type_partenaire_display()})'


class SoumissionLeadPartenaire(models.Model):
    """Lead soumis par un partenaire via le portail (FG234).

    Le partenaire renseigne les coordonnées d'un prospect ; on enregistre la
    soumission scopée société. Après qualification, le lead réel est créé dans
    ``crm`` (via son service, jamais importé ici) et référencé par ``lead_id``.
    Le partenaire suit le statut de sa soumission.
    """
    class Statut(models.TextChoices):
        SOUMIS = 'soumis', 'Soumis'
        QUALIFIE = 'qualifie', 'Qualifié'
        CONVERTI = 'converti', 'Converti'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='soumissions_lead_partenaire',
        verbose_name='Société',
    )
    partenaire = models.ForeignKey(
        Partenaire,
        on_delete=models.CASCADE,
        related_name='soumissions',
        verbose_name='Partenaire',
    )
    nom_prospect = models.CharField(
        max_length=200, verbose_name='Nom du prospect')
    telephone_prospect = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Téléphone du prospect')
    email_prospect = models.EmailField(
        blank=True, default='', verbose_name='Email du prospect')
    ville = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Ville')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.SOUMIS,
        verbose_name='Statut')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead créé')
    date_soumission = models.DateTimeField(
        auto_now_add=True, verbose_name='Soumis le')

    class Meta:
        verbose_name = 'Soumission de lead (partenaire)'
        verbose_name_plural = 'Soumissions de lead (partenaire)'
        ordering = ['-date_soumission']

    def __str__(self):
        return f'{self.nom_prospect} — {self.partenaire.nom}'
