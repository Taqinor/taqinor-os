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
        return sum((l.debit for l in self.lignes.all()), Decimal('0'))

    @property
    def total_credit(self):
        return sum((l.credit for l in self.lignes.all()), Decimal('0'))

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
        debit = sum((l.debit for l in lignes), Decimal('0'))
        credit = sum((l.credit for l in lignes), Decimal('0'))
        if debit != credit:
            raise ValidationError(
                "L'écriture comptable doit être équilibrée : "
                f"Σ débit ({debit}) ≠ Σ crédit ({credit})."
            )


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
