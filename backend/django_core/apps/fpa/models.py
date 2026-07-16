"""NTFPA — FP&A d'entreprise : budgets par département, prévisions glissantes,
scénarios what-if, variance analysis.

Distinct de ``gestion_projet.BudgetProjet``/``LigneBudgetProjet`` (PROJ21/22 —
budget MICRO d'un chantier, matériel/main-d'œuvre/sous-traitance/divers) : ce
module porte le budget MACRO par société/département/période. Les deux
couches ne fusionnent JAMAIS.

Tout est multi-société : ``company`` posée côté serveur (jamais lue du corps
de requête). Pas de nouveau modèle de chatter — le journal (« mail.thread »)
d'un objet FP&A passe par le mixin de chatter générique de fondation
``records.Activity`` (ARC8) via ``apps.records.services`` ; AUCUNE classe
``*Activity`` bespoke n'est créée ici (garde ``check_platform.py``/ARC8).
"""
from django.conf import settings
from django.db import models


class Departement(models.Model):
    """NTFPA1 — Unité organisationnelle FP&A (hiérarchie intra-société)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='fpa_departements', verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    nom = models.CharField(max_length=150, verbose_name='Nom')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fpa_departements_diriges',
        verbose_name='Responsable',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sous_departements', verbose_name='Département parent',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Département'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='fpa_departement_code_unique'),
        ]
        ordering = ['nom']

    def __str__(self):
        return f'{self.code} — {self.nom}'

    def sous_arbre_ids(self):
        """Retourne l'ensemble des ids de ce département + tous ses
        descendants (récursif), utilisé par le périmètre de visibilité
        (NTFPA26) — un responsable de département voit aussi ses
        sous-départements."""
        ids = {self.pk}
        for enfant in Departement.objects.filter(parent_id=self.pk):
            ids |= enfant.sous_arbre_ids()
        return ids


class CycleBudgetaire(models.Model):
    """NTFPA2 — Cycle budgétaire d'entreprise (ex. « Budget 2027 »).

    ``exercice_comptable_id`` référence ``compta.ExerciceComptable`` en
    STRING-ID (jamais un FK dur — cross-app boundary, FPA lit compta via
    ``apps.compta.selectors.get_exercice_label`` uniquement).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        OUVERT_SAISIE = 'ouvert_saisie', 'Ouvert à la saisie'
        EN_VALIDATION = 'en_validation', 'En validation'
        CLOS = 'clos', 'Clos'

    class TypeCycle(models.TextChoices):
        ANNUEL = 'annuel', 'Annuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='fpa_cycles_budgetaires', verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    exercice_comptable_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Exercice comptable (référence)',
    )
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut',
    )
    type_cycle = models.CharField(
        max_length=15, choices=TypeCycle.choices, default=TypeCycle.ANNUEL,
        verbose_name='Type de cycle',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cycle budgétaire'
        ordering = ['-date_debut']

    def __str__(self):
        return self.nom

    @property
    def clos(self):
        return self.statut == self.Statut.CLOS


class Categorie(models.TextChoices):
    """Catégorie budgétaire FP&A — partagée par lignes budget/prévision/scénario."""
    MASSE_SALARIALE = 'masse_salariale', 'Masse salariale'
    MARKETING = 'marketing', 'Marketing'
    IT = 'it', 'IT'
    FRAIS_GENERAUX = 'frais_generaux', 'Frais généraux'
    INVESTISSEMENT = 'investissement', 'Investissement'
    AUTRE = 'autre', 'Autre'


class LigneBudgetDepartement(models.Model):
    """NTFPA3 — Ligne de budget mensuelle d'un département, par catégorie.

    NTFPA6 — verrouillage post-clôture : ``save()``/``delete()`` refusent toute
    écriture dès que ``cycle.statut == CLOS`` (même patron que
    ``compta.EcritureComptable._verifier_periode_ouverte``)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='fpa_lignes_budget', verbose_name='Société',
    )
    cycle = models.ForeignKey(
        CycleBudgetaire, on_delete=models.CASCADE,
        related_name='lignes_budget', verbose_name='Cycle budgétaire',
    )
    departement = models.ForeignKey(
        Departement, on_delete=models.CASCADE,
        related_name='lignes_budget', verbose_name='Département',
    )
    categorie = models.CharField(
        max_length=20, choices=Categorie.choices, verbose_name='Catégorie')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois (1-12)')
    montant_prevu = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Montant prévu')
    commentaire = models.TextField(blank=True, default='', verbose_name='Commentaire')
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ligne de budget département'
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'departement', 'categorie', 'mois'],
                name='fpa_ligne_budget_unique'),
            models.CheckConstraint(
                condition=models.Q(mois__gte=1) & models.Q(mois__lte=12),
                name='fpa_ligne_budget_mois_valide'),
        ]
        ordering = ['departement', 'categorie', 'mois']

    def __str__(self):
        return f'{self.departement_id} {self.categorie} M{self.mois}'

    def _verifier_cycle_ouvert(self):
        """NTFPA6 — refuse toute écriture si le cycle parent est clos."""
        if not self.cycle_id:
            return
        statut = CycleBudgetaire.objects.filter(
            pk=self.cycle_id).values_list('statut', flat=True).first()
        if statut == CycleBudgetaire.Statut.CLOS:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                "Ce cycle budgétaire est clôturé : la ligne "
                f'{self.departement_id}/{self.categorie}/M{self.mois} '
                "ne peut plus être modifiée.")

    def _verifier_non_soumis(self):
        """NTFPA5 — refuse toute écriture si la soumission (cycle, département)
        est ``soumis`` ou ``valide`` (verrouillage le temps de la validation).
        Une soumission ``en_saisie``/``rejete``/absente laisse l'édition
        ouverte (un budget rejeté repasse en saisie, éditable)."""
        soumission = SoumissionBudgetDepartement.objects.filter(
            cycle_id=self.cycle_id, departement_id=self.departement_id,
        ).values_list('statut', flat=True).first()
        if soumission in (
                SoumissionBudgetDepartement.Statut.SOUMIS,
                SoumissionBudgetDepartement.Statut.VALIDE):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                "Ce budget de département est soumis/validé : il est "
                "verrouillé le temps de la décision (rejet pour rouvrir).")

    def save(self, *args, **kwargs):
        self._verifier_cycle_ouvert()
        self._verifier_non_soumis()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._verifier_cycle_ouvert()
        self._verifier_non_soumis()
        return super().delete(*args, **kwargs)


class SoumissionBudgetDepartement(models.Model):
    """NTFPA5 — Workflow soumission/validation d'un budget de département pour
    un cycle donné. Statut LOCAL au workflow (jamais lié à STAGES.py ni au
    ``CycleBudgetaire.statut``, même patron que ``contrats.EtapeApprobation``
    vs ``Contrat.statut``)."""

    class Statut(models.TextChoices):
        EN_SAISIE = 'en_saisie', 'En saisie'
        SOUMIS = 'soumis', 'Soumis'
        VALIDE = 'valide', 'Validé'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='fpa_soumissions_budget', verbose_name='Société',
    )
    cycle = models.ForeignKey(
        CycleBudgetaire, on_delete=models.CASCADE,
        related_name='soumissions', verbose_name='Cycle budgétaire',
    )
    departement = models.ForeignKey(
        Departement, on_delete=models.CASCADE,
        related_name='soumissions_budget', verbose_name='Département',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_SAISIE,
        verbose_name='Statut',
    )
    motif_rejet = models.TextField(blank=True, default='', verbose_name='Motif de rejet')
    soumis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fpa_budgets_soumis',
        verbose_name='Soumis par',
    )
    soumis_le = models.DateTimeField(null=True, blank=True, verbose_name='Soumis le')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fpa_budgets_valides',
        verbose_name='Validé par',
    )
    valide_le = models.DateTimeField(null=True, blank=True, verbose_name='Validé le')

    class Meta:
        verbose_name = 'Soumission de budget département'
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'departement'],
                name='fpa_soumission_cycle_departement_unique'),
        ]

    def __str__(self):
        return f'{self.departement_id} / cycle {self.cycle_id} — {self.statut}'
