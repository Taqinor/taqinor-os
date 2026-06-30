"""
FG308 — Évaluation de performance des sous-traitants chantier.

``EvaluationSousTraitant`` note un sous-traitant (``SousTraitant``, FG304) APRÈS
une prestation : qualité, respect des délais et sécurité, chacune sur 1 à 5. Une
évaluation se rattache de préférence à un ordre de travaux (``OrdreSousTraitance``,
FG305) et/ou un chantier, pour tracer QUELLE prestation est notée. La SCORECARD
cumulée (moyenne des notes sur toutes les prestations d'un sous-traitant) se
calcule en lecture seule via ``selectors.sous_traitant_scorecard`` — aucune
donnée dénormalisée à maintenir.

Couche INDÉPENDANTE des statuts de l'OS. Additif & multi-tenant : on AJOUTE une
table avec une FK ``company`` posée côté serveur, jamais lue du corps de la
requête.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class EvaluationSousTraitant(models.Model):
    """FG308 — note de performance d'un sous-traitant pour une prestation, sur
    trois axes (qualité / délai / sécurité), chacun de 1 à 5.

    Multi-tenant : la société est posée côté serveur. La note globale est la
    moyenne des trois axes (propriété dérivée)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_evaluations_sous_traitant')
    sous_traitant = models.ForeignKey(
        'installations.SousTraitant', on_delete=models.CASCADE,
        related_name='evaluations')
    # Prestation notée (optionnelle) : ordre de travaux et/ou chantier.
    ordre = models.ForeignKey(
        'installations.OrdreSousTraitance', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='evaluations')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_evaluations_sous_traitant')
    # Trois axes notés de 1 (mauvais) à 5 (excellent).
    note_qualite = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    note_delai = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    note_securite = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    commentaire = models.TextField(blank=True, null=True)
    date_evaluation = models.DateField(null=True, blank=True)
    evalue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_evaluations_sous_traitant_faites')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Évaluation sous-traitant'
        verbose_name_plural = 'Évaluations sous-traitant'
        ordering = ['-date_creation']
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'sous_traitant'],
                         name='idx_eval_co_soustrait'),
        ]

    def __str__(self):
        return f'{self.sous_traitant_id} · {self.note_globale}'

    @property
    def note_globale(self):
        """Moyenne arrondie des trois axes (1 décimale)."""
        total = self.note_qualite + self.note_delai + self.note_securite
        return round(total / 3, 1)
